"""
Geometry joining functions.
Handles auto-joining datasets with geometry and fuzzy matching.
"""

import pandas as pd
from rapidfuzz import process, fuzz


def detect_join_key(primary_df, geometry_df, primary_metadata=None, geometry_metadata=None):
    """
    Automatically detect which columns can be used to join two datasets.
    Validates join quality by testing sample values.

    Args:
        primary_df: DataFrame with primary data (no geometry)
        geometry_df: DataFrame with geometry data
        primary_metadata: Optional metadata for primary dataset
        geometry_metadata: Optional metadata for geometry dataset

    Returns:
        tuple: (primary_key_column, geometry_key_column) or (None, None) if no match found
    """
    # Common join key patterns (in priority order)
    # Geometry files use standardized columns: code, name, abbrev
    join_patterns = [
        # Country-level joins - try 3-letter ISO codes first
        # Data columns -> Geometry columns (geometry uses 'code' as standard)
        (['country_code', 'LocationCode', 'location_code', 'iso3', 'ISO3', 'Country Code', 'ISO_A3', 'iso_a3', 'iso_code'],
         ['code', 'country_code', 'Admin Country Abbr', 'ISO_A3', 'iso_a3', 'postal', 'iso_code', 'abbrev']),

        # County-level joins (FIPS codes) - check before state_name since county_code is more specific
        (['county_code', 'GEOID', 'geoid', 'FIPS', 'fips', 'Official County Code'],
         ['code', 'Official County Code', 'GEOID', 'geoid']),

        # State-level joins (for US data that aggregates to state level only)
        (['state_name', 'STATE_NAME', 'State Name', 'STNAME'],
         ['state_name', 'name']),

        # Name-based joins (fallback)
        (['country_name', 'country', 'Country', 'name', 'Name', 'Location', 'location', 'place', 'Place Name'],
         ['name', 'country_name', 'Sov Country Name', 'name_long', 'Admin Country Name', 'Name', 'Official County Name', 'Place Name'])
    ]

    print("\n=== JOIN KEY DETECTION ===")
    print(f"Primary columns: {primary_df.columns.tolist()[:10]}...")
    print(f"Geometry columns: {geometry_df.columns.tolist()[:10]}...")

    for primary_candidates, geometry_candidates in join_patterns:
        for p_col in primary_candidates:
            if p_col in primary_df.columns:
                for g_col in geometry_candidates:
                    if g_col in geometry_df.columns:
                        # Test join quality with sample data - use unique values to handle datasets with many rows per entity
                        primary_unique = primary_df[p_col].dropna().unique()
                        primary_sample = set(primary_unique[:min(50, len(primary_unique))])  # Sample up to 50 unique values
                        geometry_sample = set(geometry_df[g_col].dropna())

                        # Check how many primary values have matches in geometry
                        matches = primary_sample & geometry_sample
                        match_rate = len(matches) / len(primary_sample) if primary_sample else 0

                        print(f"Testing JOIN: {p_col} <-> {g_col}")
                        print(f"  Sample primary values: {list(primary_sample)[:5]}")
                        print(f"  Sample geometry values: {list(geometry_sample)[:5]}")
                        print(f"  Match rate: {match_rate:.1%} ({len(matches)}/{len(primary_sample)})")

                        # Accept if >50% of sample matches
                        if match_rate >= 0.5:
                            print(f"[OK] Using JOIN: {p_col} = {g_col}")
                            return (p_col, g_col)
                        else:
                            print(f"[SKIP] Low match rate, trying next candidate...")

    print("[ERROR] Could not find suitable JOIN keys")
    return (None, None)


def auto_join_geometry(primary_df, primary_filename, primary_metadata=None, data_catalog=None):
    """
    Automatically join a dataset with appropriate geometry data.

    Args:
        primary_df: DataFrame with data but no geometry
        primary_filename: Name of the primary dataset file
        primary_metadata: Metadata for the primary dataset
        data_catalog: The data catalog for finding geometry sources

    Returns:
        DataFrame: Merged dataframe with geometry, or original if join fails
    """
    from .geometry_enrichment import get_geometry_source

    # Get geographic level from metadata
    if not primary_metadata:
        print("Warning: No metadata available for geometry fallback")
        return primary_df

    geographic_level = primary_metadata.get('geographic_level', 'unknown')
    print(f"Primary dataset geographic level: {geographic_level}")

    # Get appropriate geometry source
    geometry_source = get_geometry_source(geographic_level, data_catalog or [])
    if not geometry_source:
        return primary_df

    print(f"Loading geometry from: {geometry_source['filename']}")

    # Load geometry dataset
    try:
        geometry_df = pd.read_csv(
            geometry_source["path"],
            delimiter=geometry_source["delimiter"],
            dtype=str
        )

        # Get geometry metadata if available
        geometry_metadata = geometry_source.get("metadata")

        # Detect join keys
        primary_key, geometry_key = detect_join_key(
            primary_df,
            geometry_df,
            primary_metadata,
            geometry_metadata
        )

        if not primary_key or not geometry_key:
            print("Cannot join datasets: no common join key found")
            return primary_df

        # Perform the join
        print(f"Joining on: {primary_key} = {geometry_key}")

        # Merge datasets (left join to keep all primary data)
        merged_df = primary_df.merge(
            geometry_df[[geometry_key, 'geometry']],
            left_on=primary_key,
            right_on=geometry_key,
            how='left'
        )

        print(f"Join result: {len(merged_df)} rows (original: {len(primary_df)})")

        # Check how many rows got geometry
        has_geometry = merged_df['geometry'].notna().sum()
        print(f"Rows with geometry after exact join: {has_geometry}/{len(merged_df)}")

        # If many rows are missing geometry and this is a name-based join, try fuzzy matching
        missing_geometry = len(merged_df) - has_geometry
        is_name_join = primary_key.lower() in ['country', 'name', 'location', 'place']

        if missing_geometry > 0 and is_name_join:
            print(f"Trying fuzzy matching for {missing_geometry} rows without geometry...")

            # Try multiple geometry column options (prioritize Sov Country Name for best matches)
            geom_name_columns = ['Sov Country Name', 'name_long', 'Admin Country Name', 'name', 'Location']
            best_geom_col = None
            for col in geom_name_columns:
                if col in geometry_df.columns:
                    best_geom_col = col
                    break

            if best_geom_col:
                print(f"Using geometry column: {best_geom_col}")

                # Build lookup dict for fuzzy matching
                geom_lookup = {}
                for idx, row in geometry_df.iterrows():
                    name_val = row[best_geom_col]
                    if pd.notna(name_val) and pd.notna(row['geometry']):
                        geom_lookup[str(name_val)] = row['geometry']

                # Fuzzy match rows without geometry
                fuzzy_matches = 0
                for idx, row in merged_df.iterrows():
                    if pd.isna(row['geometry']):
                        primary_name = str(row[primary_key])
                        if primary_name and primary_name != 'nan':
                            # Find best match above threshold
                            match_result = process.extractOne(
                                primary_name,
                                geom_lookup.keys(),
                                scorer=fuzz.ratio,
                                score_cutoff=70  # 70% similarity threshold
                            )
                            if match_result:
                                matched_name, score, _ = match_result
                                merged_df.at[idx, 'geometry'] = geom_lookup[matched_name]
                                fuzzy_matches += 1
                                if fuzzy_matches <= 5:  # Log first few matches
                                    print(f"  Fuzzy matched: '{primary_name}' -> '{matched_name}' (score: {score})")

                if fuzzy_matches > 0:
                    print(f"Fuzzy matching added geometry to {fuzzy_matches} additional rows")
                    has_geometry = merged_df['geometry'].notna().sum()
                    print(f"Total rows with geometry: {has_geometry}/{len(merged_df)}")

        return merged_df

    except Exception as e:
        print(f"Error during auto-join: {e}")
        import traceback
        traceback.print_exc()
        return primary_df
