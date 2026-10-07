"""
Location lookup utilities for address-based data queries.

Given a ZIP code (or address that resolves to a ZIP), returns
the hierarchy of loc_ids that can be used to query data at
different geographic levels.

Usage:
    from mapmover.reference.usa.location_lookup import LocationLookup

    lookup = LocationLookup()
    result = lookup.by_zip("90210")
    # Returns:
    # {
    #     "zcta": "90210",
    #     "zcta_loc_id": "USA-Z-90210",
    #     "county_loc_id": "USA-CA-6037",
    #     "county_name": "Los Angeles County",
    #     "state_abbrev": "CA",
    #     "state_loc_id": "USA-CA",
    #     "country_loc_id": "USA"
    # }
"""

import json
from pathlib import Path
import pandas as pd
from typing import Optional, Dict, List, Any

from ...duckdb_helpers import duckdb_available, select_columns_from_parquet

class LocationLookup:
    """
    Lookup location hierarchy from ZIP code.

    Provides cascading data lookup: ZIP -> County -> State -> Country
    """

    def __init__(self, reference_dir: Optional[Path] = None):
        """
        Initialize lookup with reference data.

        Args:
            reference_dir: Path to reference/usa directory. Auto-detected if None.
        """
        if reference_dir is None:
            reference_dir = Path(__file__).parent

        self.reference_dir = Path(reference_dir)
        self._zcta_df = None
        self._load_data()

    def _load_data(self):
        """Load crosswalk data lazily."""
        crosswalk_path = self.reference_dir / "zcta_crosswalk.parquet"
        if crosswalk_path.exists():
            if duckdb_available():
                self._zcta_df = select_columns_from_parquet(
                    crosswalk_path,
                    [
                        "zcta",
                        "zcta_loc_id",
                        "primary_county_loc_id",
                        "primary_county_name",
                        "state_abbrev",
                        "state_loc_id",
                        "all_counties_json",
                        "county_count",
                    ],
                )
                if self._zcta_df.empty:
                    self._zcta_df = pd.read_parquet(crosswalk_path)
            else:
                self._zcta_df = pd.read_parquet(crosswalk_path)
            # Create lookup dict for fast access
            self._zcta_dict = self._zcta_df.set_index('zcta').to_dict('index')
        else:
            self._zcta_dict = {}
            print(f"Warning: ZCTA crosswalk not found at {crosswalk_path}")

    def by_zip(self, zip_code: str) -> Optional[Dict[str, Any]]:
        """
        Look up location hierarchy by ZIP code.

        Args:
            zip_code: 5-digit ZIP code (string or int)

        Returns:
            Dictionary with location hierarchy, or None if not found.

            Keys:
            - zcta: The ZCTA code
            - zcta_loc_id: loc_id for ZCTA level data
            - county_loc_id: loc_id for county level data (primary county)
            - county_name: Human-readable county name
            - state_abbrev: Two-letter state abbreviation
            - state_loc_id: loc_id for state level data
            - country_loc_id: Always "USA"
            - all_counties: List of all county loc_ids (for multi-county ZCTAs)
        """
        # Normalize ZIP code to 5 digits with leading zeros
        zip_str = str(zip_code).zfill(5)

        if zip_str not in self._zcta_dict:
            return None

        row = self._zcta_dict[zip_str]

        # Parse all_counties from JSON string
        all_counties = json.loads(row.get('all_counties_json', '[]'))

        return {
            "zcta": zip_str,
            "zcta_loc_id": row['zcta_loc_id'],
            "county_loc_id": row['primary_county_loc_id'],
            "county_name": row['primary_county_name'],
            "state_abbrev": row['state_abbrev'],
            "state_loc_id": row['state_loc_id'],
            "country_loc_id": "USA",
            "all_counties": all_counties,
            "county_count": row['county_count']
        }

    def get_data_loc_ids(self, zip_code: str) -> List[str]:
        """
        Get ordered list of loc_ids to try for data lookup.

        Returns loc_ids from most specific to least specific:
        [zcta_loc_id, county_loc_id, state_loc_id, country_loc_id]

        Use this for cascading data lookup:
        - Try ZCTA-level data first
        - Fall back to county if ZCTA not available
        - Fall back to state if county not available
        - Fall back to country if state not available
        """
        result = self.by_zip(zip_code)
        if result is None:
            return ["USA"]  # Fall back to country level

        return [
            result['zcta_loc_id'],
            result['county_loc_id'],
            result['state_loc_id'],
            result['country_loc_id']
        ]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for ZCTAs by partial ZIP code or county name.

        Args:
            query: Partial ZIP code or county name substring

        Returns:
            List of matching location results (max 20)
        """
        if self._zcta_df is None:
            return []

        query_lower = query.lower()

        # Search by ZIP prefix
        if query.isdigit():
            matches = self._zcta_df[self._zcta_df['zcta'].str.startswith(query)]
        else:
            # Search by county name
            matches = self._zcta_df[
                self._zcta_df['primary_county_name'].str.lower().str.contains(query_lower, na=False)
            ]

        results = []
        for _, row in matches.head(20).iterrows():
            results.append({
                "zcta": row['zcta'],
                "zcta_loc_id": row['zcta_loc_id'],
                "county_loc_id": row['primary_county_loc_id'],
                "county_name": row['primary_county_name'],
                "state_abbrev": row['state_abbrev'],
                "state_loc_id": row['state_loc_id'],
                "country_loc_id": "USA"
            })

        return results

    @property
    def zcta_count(self) -> int:
        """Return total number of ZCTAs in crosswalk."""
        return len(self._zcta_dict)


# Singleton instance for convenience
_lookup_instance = None

def get_lookup() -> LocationLookup:
    """Get singleton LocationLookup instance."""
    global _lookup_instance
    if _lookup_instance is None:
        _lookup_instance = LocationLookup()
    return _lookup_instance


def by_zip(zip_code: str) -> Optional[Dict[str, Any]]:
    """Convenience function for quick ZIP lookup."""
    return get_lookup().by_zip(zip_code)


def get_data_loc_ids(zip_code: str) -> List[str]:
    """Convenience function for cascading loc_id lookup."""
    return get_lookup().get_data_loc_ids(zip_code)


# Quick test when run directly
if __name__ == "__main__":
    print("Location Lookup Test")
    print("=" * 60)

    lookup = LocationLookup()
    print(f"Loaded {lookup.zcta_count:,} ZCTAs")

    test_zips = ["90210", "10001", "60601", "33139", "98101", "00000"]

    print("\nTest lookups:")
    for zip_code in test_zips:
        result = lookup.by_zip(zip_code)
        if result:
            print(f"\n  ZIP {zip_code}:")
            print(f"    County: {result['county_name']}")
            print(f"    State: {result['state_abbrev']}")
            print(f"    loc_ids: {lookup.get_data_loc_ids(zip_code)}")
        else:
            print(f"\n  ZIP {zip_code}: Not found")

    print("\n\nSearch test ('Los Angeles'):")
    results = lookup.search("Los Angeles")
    for r in results[:5]:
        print(f"  {r['zcta']}: {r['county_name']}, {r['state_abbrev']}")
