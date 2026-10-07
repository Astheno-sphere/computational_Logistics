"""
Data Cascade Module

Handles cascading (fallback to parent) and aggregation (roll up children) logic
for indicator data queries.

Cascade DOWN: When data missing for a location, use parent's data
  "What is GDP of Los Angeles?" -> If no city data, use California data

Aggregate UP: Sum/average children to compute parent values
  "What is population of EU?" -> Sum population of 27 member countries

Uses:
  - Geometry data for parent_id lookups
  - conversions.json for regional groupings (EU, G20, ASEAN, etc.)
"""

from typing import Optional, Dict, List, Any, Union

import pandas as pd

from .runtime.geography_reference import load_conversions as load_conversions_impl
from .runtime.admin_hierarchy import (
    get_ancestors as get_ancestors_impl,
    get_children as get_children_impl,
    get_parent_loc_id as get_parent_id_impl,
)


def load_conversions():
    """Load conversions.json through the shared runtime cache."""
    return load_conversions_impl() or {}

def get_parent_id(loc_id: str) -> Optional[str]:
    """Compatibility wrapper over the shared runtime admin hierarchy helper."""
    return get_parent_id_impl(loc_id)


def get_ancestors(loc_id: str) -> List[str]:
    """Compatibility wrapper over the shared runtime admin hierarchy helper."""
    return get_ancestors_impl(loc_id)


def get_children(loc_id: str) -> List[str]:
    """Compatibility wrapper over the shared runtime admin hierarchy helper."""
    return get_children_impl(loc_id)


def get_regional_grouping(group_name: str) -> Optional[Dict]:
    """
    Get a regional grouping definition.

    Examples:
        get_regional_grouping('EU') -> {'code': 'EU', 'countries': ['AUT', 'BEL', ...]}
        get_regional_grouping('G20') -> {'code': 'G20', 'countries': ['ARG', ...]}
    """
    conv = load_conversions()
    groupings = conv.get('regional_groupings', {})

    # Direct lookup
    if group_name in groupings:
        return groupings[group_name]

    # Check aliases
    aliases = conv.get('regional_grouping_aliases', {})
    if group_name in aliases:
        canonical = aliases[group_name]
        return groupings.get(canonical)

    # Case-insensitive search
    group_lower = group_name.lower().replace(' ', '_')
    for name, data in groupings.items():
        if name.lower() == group_lower:
            return data
        if data.get('code', '').lower() == group_lower:
            return data

    return None


def cascade_down(
    loc_id: str,
    get_value_fn,
    max_levels: int = 3
) -> Dict[str, Any]:
    """
    Get a value with cascading fallback to parent locations.

    Args:
        loc_id: The location to query
        get_value_fn: Function(loc_id) -> value or None
        max_levels: Maximum parent levels to try

    Returns:
        {
            'value': <the value or None>,
            'source_loc_id': <loc_id where value was found>,
            'cascaded': <bool: True if used parent data>,
            'cascade_path': [<list of loc_ids tried>]
        }
    """
    path = [loc_id]

    # Try the requested location first
    value = get_value_fn(loc_id)
    if value is not None:
        return {
            'value': value,
            'source_loc_id': loc_id,
            'cascaded': False,
            'cascade_path': path
        }

    # Try ancestors
    ancestors = get_ancestors(loc_id)
    for i, ancestor in enumerate(ancestors[:max_levels]):
        path.append(ancestor)
        value = get_value_fn(ancestor)
        if value is not None:
            return {
                'value': value,
                'source_loc_id': ancestor,
                'cascaded': True,
                'cascade_path': path
            }

    return {
        'value': None,
        'source_loc_id': None,
        'cascaded': False,
        'cascade_path': path
    }


def aggregate_up(
    loc_ids: List[str],
    get_value_fn,
    agg_func: str = 'sum'
) -> Dict[str, Any]:
    """
    Aggregate values from multiple locations.

    Args:
        loc_ids: List of location IDs to aggregate
        get_value_fn: Function(loc_id) -> numeric value or None
        agg_func: 'sum', 'mean', 'min', 'max', 'count'

    Returns:
        {
            'value': <aggregated value>,
            'agg_func': <function used>,
            'source_count': <number of locations with data>,
            'missing_count': <number of locations without data>,
            'sources': [<loc_ids with data>],
            'missing': [<loc_ids without data>]
        }
    """
    values = []
    sources = []
    missing = []

    for loc_id in loc_ids:
        value = get_value_fn(loc_id)
        if value is not None:
            try:
                values.append(float(value))
                sources.append(loc_id)
            except (ValueError, TypeError):
                missing.append(loc_id)
        else:
            missing.append(loc_id)

    if not values:
        return {
            'value': None,
            'agg_func': agg_func,
            'source_count': 0,
            'missing_count': len(missing),
            'sources': sources,
            'missing': missing
        }

    # Apply aggregation
    if agg_func == 'sum':
        result = sum(values)
    elif agg_func == 'mean':
        result = sum(values) / len(values)
    elif agg_func == 'min':
        result = min(values)
    elif agg_func == 'max':
        result = max(values)
    elif agg_func == 'count':
        result = len(values)
    else:
        result = sum(values)  # default to sum

    return {
        'value': result,
        'agg_func': agg_func,
        'source_count': len(sources),
        'missing_count': len(missing),
        'sources': sources,
        'missing': missing
    }


def aggregate_regional_grouping(
    group_name: str,
    get_value_fn,
    agg_func: str = 'sum'
) -> Dict[str, Any]:
    """
    Aggregate values for a regional grouping (EU, G20, etc).

    Args:
        group_name: Name of the grouping (e.g., 'EU', 'G20', 'ASEAN')
        get_value_fn: Function(loc_id) -> numeric value or None
        agg_func: Aggregation function

    Returns:
        Same as aggregate_up, plus 'group_name' and 'group_code'
    """
    grouping = get_regional_grouping(group_name)
    if grouping is None:
        return {
            'value': None,
            'error': f"Unknown regional grouping: {group_name}",
            'group_name': group_name
        }

    countries = grouping.get('countries', [])
    result = aggregate_up(countries, get_value_fn, agg_func)
    result['group_name'] = group_name
    result['group_code'] = grouping.get('code', group_name)
    result['member_count'] = len(countries)

    return result


class DataCascade:
    """
    High-level interface for cascading and aggregation.

    Usage:
        cascade = DataCascade(indicator_df)
        result = cascade.get_value('USA-CA-037', 'gdp', year=2023)
        result = cascade.get_aggregate('EU', 'population', agg_func='sum')
    """

    def __init__(self, data: pd.DataFrame = None):
        """
        Initialize with optional indicator data.

        Args:
            data: DataFrame with columns [loc_id, indicator, year, value]
        """
        self.data = data

    def _get_value_from_data(self, loc_id: str, indicator: str, year: int = None):
        """Get value from the loaded data."""
        if self.data is None:
            return None

        mask = (self.data['loc_id'] == loc_id)

        if 'indicator' in self.data.columns:
            mask &= (self.data['indicator'] == indicator)

        if year is not None and 'year' in self.data.columns:
            mask &= (self.data['year'] == year)

        matches = self.data[mask]
        if len(matches) > 0:
            return matches.iloc[0].get('value')

        return None

    def get_value(
        self,
        loc_id: str,
        indicator: str,
        year: int = None,
        cascade: bool = True
    ) -> Dict[str, Any]:
        """
        Get indicator value for a location with optional cascading.

        Args:
            loc_id: Location ID
            indicator: Indicator name
            year: Optional year filter
            cascade: Whether to try parent locations if no data

        Returns:
            Result dict with value, source, and cascade info
        """
        def get_fn(lid):
            return self._get_value_from_data(lid, indicator, year)

        if cascade:
            return cascade_down(loc_id, get_fn)
        else:
            value = get_fn(loc_id)
            return {
                'value': value,
                'source_loc_id': loc_id if value is not None else None,
                'cascaded': False,
                'cascade_path': [loc_id]
            }

    def get_aggregate(
        self,
        group_or_loc_id: str,
        indicator: str,
        year: int = None,
        agg_func: str = 'sum',
        use_children: bool = False
    ) -> Dict[str, Any]:
        """
        Get aggregated indicator value.

        Args:
            group_or_loc_id: Regional grouping name OR loc_id to aggregate children
            indicator: Indicator name
            year: Optional year filter
            agg_func: Aggregation function
            use_children: If True, aggregate children of loc_id; if False, treat as grouping

        Returns:
            Result dict with aggregated value and source info
        """
        def get_fn(lid):
            return self._get_value_from_data(lid, indicator, year)

        # Check if it's a regional grouping
        grouping = get_regional_grouping(group_or_loc_id)
        if grouping is not None and not use_children:
            return aggregate_regional_grouping(group_or_loc_id, get_fn, agg_func)

        # Otherwise, aggregate children
        children = get_children(group_or_loc_id)
        if not children:
            return {
                'value': None,
                'error': f"No children found for {group_or_loc_id}",
                'loc_id': group_or_loc_id
            }

        result = aggregate_up(children, get_fn, agg_func)
        result['parent_loc_id'] = group_or_loc_id
        return result


def clear_cache():
    """Clear all cached data."""
    global _geometry_cache
    _geometry_cache = {}


# Quick test
if __name__ == "__main__":
    print("=== Data Cascade Module Test ===\n")

    # Test parent lookup
    print("Parent lookups:")
    for loc_id in ['USA-CA-037', 'USA-CA', 'USA', 'FRA']:
        parent = get_parent_id(loc_id)
        print(f"  {loc_id} -> {parent}")

    # Test ancestors
    print("\nAncestors of USA-CA-037:")
    print(f"  {get_ancestors('USA-CA-037')}")

    # Test children
    print("\nChildren of USA (first 5):")
    children = get_children('USA')[:5]
    print(f"  {children}")

    # Test regional groupings
    print("\nRegional groupings:")
    for name in ['EU', 'G20', 'ASEAN']:
        g = get_regional_grouping(name)
        if g:
            print(f"  {name}: {len(g['countries'])} countries")

    print("\nDone!")
