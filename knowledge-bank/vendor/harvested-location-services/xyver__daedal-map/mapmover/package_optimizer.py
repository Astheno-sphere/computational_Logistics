"""
Package Optimizer - Merges multiple data requests into unified tables.

This is the core of cache deduplication. It provides:
- merge(): Combine multiple GeoJSON FeatureCollections into one
- deduplicate_queue(): Remove redundant requests from a queue
- compute_signature(): Create hash signatures for deduplication

Integrates with cache_signature.py for CacheSignature-based operations.
"""

import hashlib
import json
import logging
from typing import List, Dict, Set, Optional, Any, Tuple

from .cache_signature import CacheSignature

logger = logging.getLogger(__name__)


class PackageOptimizer:
    """
    Merges multiple data requests into unified tables.

    Example:
        Request 1: CA counties, population 2020
        Request 2: CA counties, GDP 2020
        Request 3: TX counties, population 2020

        Output: Unified table with loc_id, year, population, gdp
                for both CA and TX counties
    """

    @staticmethod
    def compute_signature(item: Dict) -> str:
        """
        Create hash signature for deduplication.

        Args:
            item: Order item dict with keys like source_id, metric, region, year, etc.

        Returns:
            12-character MD5 hash prefix
        """
        # Normalize the item for consistent hashing
        normalized = {
            "source_id": item.get("source_id"),
            "type": item.get("type"),
            "region": item.get("region"),
            "metric": item.get("metric"),
            "metrics": sorted(item.get("metrics", [])) if item.get("metrics") else None,
            "year": item.get("year"),
            "year_start": item.get("year_start"),
            "year_end": item.get("year_end"),
            "filters": json.dumps(item.get("filters", {}), sort_keys=True) if item.get("filters") else None,
        }
        # Remove None values for cleaner hash
        normalized = {k: v for k, v in normalized.items() if v is not None}
        return hashlib.md5(json.dumps(normalized, sort_keys=True).encode()).hexdigest()[:12]

    @staticmethod
    def find_overlaps(orders: List[Dict]) -> Dict[str, List[int]]:
        """
        Find orders that request overlapping data.

        Args:
            orders: List of order item dicts

        Returns:
            Dict mapping signature -> list of indices that share that signature
        """
        signature_to_indices = {}
        for i, order in enumerate(orders):
            sig = PackageOptimizer.compute_signature(order)
            if sig not in signature_to_indices:
                signature_to_indices[sig] = []
            signature_to_indices[sig].append(i)
        return signature_to_indices

    @staticmethod
    def merge(data_list: List[Dict]) -> Dict:
        """
        Merge multiple data fetches into unified GeoJSON structure.

        Groups features by (loc_id, year) and merges their properties.
        Later values override earlier ones for the same property.

        Args:
            data_list: List of GeoJSON FeatureCollections

        Returns:
            Single merged FeatureCollection with combined properties
        """
        if not data_list:
            return {"type": "FeatureCollection", "features": []}

        # Group by loc_id + year
        merged_features: Dict[Tuple, Dict] = {}
        sources_seen = set()

        for data in data_list:
            features = data.get("features", [])
            sources = data.get("sources", [])
            if sources:
                sources_seen.update(sources)

            for feature in features:
                props = feature.get("properties", {})
                loc_id = props.get("loc_id")
                year = props.get("year")

                # Handle features without year (country-level, timeless data)
                key = (loc_id, year)

                if key not in merged_features:
                    merged_features[key] = {
                        "type": "Feature",
                        "geometry": feature.get("geometry"),
                        "properties": {"loc_id": loc_id}
                    }
                    if year is not None:
                        merged_features[key]["properties"]["year"] = year

                # Merge properties (new values override)
                for k, v in props.items():
                    if k not in ["loc_id", "year"]:
                        merged_features[key]["properties"][k] = v

        return {
            "type": "FeatureCollection",
            "features": list(merged_features.values()),
            "sources": list(sources_seen),
            "_merged_from": len(data_list),
            "_total_features": len(merged_features)
        }

    @staticmethod
    def merge_year_data(year_data_list: List[Dict[int, Dict[str, Dict]]]) -> Dict[int, Dict[str, Dict]]:
        """
        Merge multiple year_data dicts (for multi-year mode).

        year_data structure: {year: {loc_id: {metric: value, ...}, ...}, ...}

        Args:
            year_data_list: List of year_data dicts

        Returns:
            Single merged year_data dict
        """
        if not year_data_list:
            return {}

        merged = {}

        for year_data in year_data_list:
            for year, loc_data in year_data.items():
                if year not in merged:
                    merged[year] = {}

                for loc_id, metrics in loc_data.items():
                    if loc_id not in merged[year]:
                        merged[year][loc_id] = {}

                    # Merge metrics (new values override)
                    merged[year][loc_id].update(metrics)

        return merged

    @staticmethod
    def deduplicate_queue(queue: List[Dict]) -> List[Dict]:
        """
        Remove redundant requests from queue.

        Currently removes exact duplicates. Future enhancement could
        detect supersets (e.g., CA+TX population vs just CA population).

        Args:
            queue: List of order items

        Returns:
            Deduplicated list
        """
        seen = set()
        deduped = []

        for order in queue:
            sig = PackageOptimizer.compute_signature(order)
            if sig not in seen:
                seen.add(sig)
                deduped.append(order)
            else:
                logger.debug(f"Removed duplicate order: {sig}")

        if len(deduped) < len(queue):
            logger.info(f"Deduplicated queue: {len(queue)} -> {len(deduped)} items")

        return deduped

    @staticmethod
    def extract_signature_from_geojson(geojson: Dict) -> CacheSignature:
        """
        Extract a CacheSignature from GeoJSON result.

        Analyzes the features to determine:
        - loc_ids: All unique loc_id values
        - years: All unique year values
        - metrics: All property keys that look like metrics

        Args:
            geojson: GeoJSON FeatureCollection

        Returns:
            CacheSignature representing the data
        """
        loc_ids = set()
        years = set()
        metrics = set()

        # Standard non-metric properties to exclude
        non_metric_props = {
            'loc_id', 'year', 'name', 'country', 'admin_level',
            'parent_id', 'iso3', 'state', 'county', 'fips',
            'geometry', 'type', 'centroid_lat', 'centroid_lon'
        }

        features = geojson.get("features", [])
        for feature in features:
            props = feature.get("properties", {})

            loc_id = props.get("loc_id")
            if loc_id:
                loc_ids.add(loc_id)

            year = props.get("year")
            if year is not None:
                try:
                    years.add(int(year))
                except (ValueError, TypeError):
                    pass

            # Collect metric keys
            for key in props.keys():
                if key not in non_metric_props:
                    metrics.add(key)

        return CacheSignature(
            loc_ids=frozenset(loc_ids),
            years=frozenset(years),
            metrics=frozenset(metrics)
        )

    @staticmethod
    def can_serve_from_cache(
        cached_sig: CacheSignature,
        requested_sig: CacheSignature
    ) -> bool:
        """
        Check if cached data can serve a request.

        Args:
            cached_sig: Signature of what's in cache
            requested_sig: Signature of what's requested

        Returns:
            True if cache contains all requested data
        """
        return cached_sig.contains(requested_sig)

    @staticmethod
    def compute_delta(
        cached_sig: CacheSignature,
        requested_sig: CacheSignature
    ) -> CacheSignature:
        """
        Compute what data is missing from cache.

        Args:
            cached_sig: Signature of what's in cache
            requested_sig: Signature of what's requested

        Returns:
            Signature of what needs to be fetched
        """
        return requested_sig.subtract(cached_sig)

    @staticmethod
    def filter_geojson(
        geojson: Dict,
        loc_ids: Optional[Set[str]] = None,
        years: Optional[Set[int]] = None,
        metrics: Optional[Set[str]] = None
    ) -> Dict:
        """
        Filter GeoJSON to include only specified data.

        Args:
            geojson: GeoJSON FeatureCollection
            loc_ids: Optional set of loc_ids to include (None = all)
            years: Optional set of years to include (None = all)
            metrics: Optional set of metric keys to include (None = all)

        Returns:
            Filtered GeoJSON FeatureCollection
        """
        features = geojson.get("features", [])
        filtered = []

        for feature in features:
            props = feature.get("properties", {})

            # Filter by loc_id
            if loc_ids is not None and props.get("loc_id") not in loc_ids:
                continue

            # Filter by year
            if years is not None:
                year = props.get("year")
                if year is not None and int(year) not in years:
                    continue

            # Filter by metrics (keep feature but remove unwanted metrics)
            if metrics is not None:
                new_props = {
                    k: v for k, v in props.items()
                    if k in {'loc_id', 'year', 'name', 'country', 'admin_level', 'parent_id'}
                    or k in metrics
                }
                feature = {
                    "type": "Feature",
                    "geometry": feature.get("geometry"),
                    "properties": new_props
                }

            filtered.append(feature)

        return {
            "type": "FeatureCollection",
            "features": filtered,
            "sources": geojson.get("sources", [])
        }


def merge_results(results: List[Dict]) -> Dict:
    """
    Convenience function to merge multiple execute_order results.

    Args:
        results: List of execute_order result dicts

    Returns:
        Merged result dict
    """
    if not results:
        return {
            "type": "data",
            "geojson": {"type": "FeatureCollection", "features": []},
            "summary": "No data",
            "count": 0,
            "sources": []
        }

    if len(results) == 1:
        return results[0]

    # Check if any are multi-year
    multi_year = any(r.get("multi_year") for r in results)

    if multi_year:
        # Merge year_data dicts
        year_data_list = [r.get("year_data", {}) for r in results if r.get("year_data")]
        merged_year_data = PackageOptimizer.merge_year_data(year_data_list)

        # Merge base GeoJSON (geometry only)
        geojson_list = [r.get("geojson", {}) for r in results if r.get("geojson")]
        merged_geojson = PackageOptimizer.merge(geojson_list)

        # Compute year range
        all_years = set(merged_year_data.keys())
        year_range = [min(all_years), max(all_years)] if all_years else [None, None]

        # Collect all sources
        all_sources = []
        for r in results:
            all_sources.extend(r.get("sources", []))
        all_sources = list(set(all_sources))

        return {
            "type": "data",
            "geojson": merged_geojson,
            "year_data": merged_year_data,
            "year_range": year_range,
            "multi_year": True,
            "summary": f"Merged {len(results)} results",
            "count": len(merged_geojson.get("features", [])),
            "sources": all_sources
        }
    else:
        # Single year mode - merge GeoJSON
        geojson_list = [r.get("geojson", {}) for r in results if r.get("geojson")]
        merged_geojson = PackageOptimizer.merge(geojson_list)

        # Collect all sources
        all_sources = []
        for r in results:
            all_sources.extend(r.get("sources", []))
        all_sources = list(set(all_sources))

        return {
            "type": "data",
            "geojson": merged_geojson,
            "summary": f"Merged {len(results)} results",
            "count": len(merged_geojson.get("features", [])),
            "sources": all_sources
        }
