"""
Response building functions.
Handles GeoJSON response construction and conversational summaries.
"""

import json
import logging
import pandas as pd
from rapidfuzz import fuzz

from .utils import convert_unit, parse_year_value
from .geometry_enrichment import enrich_with_geometry, get_geometry_lookup

logger = logging.getLogger("mapmover")


def generate_conversational_summary(matches, sort_spec=None, filter_spec=None, metadata=None):
    """
    Generate a human-friendly conversational summary of the query results.

    Args:
        matches: List of GeoJSON features
        sort_spec: Sort specification (sort_by, sort_order, limit)
        filter_spec: Filter specification (column, operator, value)
        metadata: Dataset metadata

    Returns:
        Conversational string summarizing the results
    """
    if not matches:
        return "No results found for your query."

    # Get the name column from the first match
    name_key = None
    for key in ['country', 'name', 'Name', 'Location', 'admin']:
        if key in matches[0]['properties']:
            name_key = key
            break

    if not name_key:
        return f"Found {len(matches)} results."

    # Extract names from matches
    names = [m['properties'].get(name_key, 'Unknown') for m in matches]

    # Get the year from the first match if available
    year = matches[0]['properties'].get('year', '')
    year_str = f" ({year})" if year else ""

    # Get source info
    source_name = metadata.get('source_name', '') if metadata else ''
    source_str = f" based on {source_name} data" if source_name and source_name != 'Unknown' else ""

    # Build conversational response based on query type
    if sort_spec and sort_spec.get('sort_by'):
        sort_col = sort_spec.get('sort_by')
        sort_order = sort_spec.get('sort_order', 'desc')
        limit = sort_spec.get('limit')

        # Format the column name nicely
        col_display = sort_col.upper() if sort_col.lower() in ['gdp', 'co2'] else sort_col.replace('_', ' ').title()

        # Determine superlative based on sort order
        if sort_order == 'desc':
            superlative = "highest" if 'rate' in sort_col.lower() or 'capita' in sort_col.lower() else "largest"
        else:
            superlative = "lowest" if 'rate' in sort_col.lower() or 'capita' in sort_col.lower() else "smallest"

        if limit and limit <= 10:
            # Format as a list for small results
            if len(names) == 1:
                names_str = names[0]
            elif len(names) == 2:
                names_str = f"{names[0]} and {names[1]}"
            else:
                names_str = ", ".join(names[:-1]) + f", and {names[-1]}"

            return f"The top {len(names)} {superlative} {col_display} countries are {names_str}{year_str}{source_str}."
        else:
            return f"Showing {len(names)} countries sorted by {superlative} {col_display}{year_str}{source_str}."

    elif filter_spec:
        filter_col = filter_spec.get('column', '')
        operator = filter_spec.get('operator', '')
        value = filter_spec.get('value', '')

        col_display = filter_col.replace('_', ' ').title()
        op_text = {'>': 'greater than', '<': 'less than', '>=': 'at least', '<=': 'at most', '=': 'equal to'}.get(operator, operator)

        return f"Found {len(names)} locations where {col_display} is {op_text} {value}{year_str}{source_str}."

    else:
        return f"Found {len(names)} results{year_str}{source_str}."


def get_country_coordinates(country_name, country_code=None):
    """
    Get approximate coordinates for a country by name or code.
    First checks the shared world bootstrap geometry lookup, then falls back to
    shared runtime country coordinate helpers.

    Args:
        country_name: Name of the country
        country_code: Optional ISO 3-letter code for faster/more accurate lookup

    Returns:
        Tuple (lat, lon) or None if not found
    """
    from .geography import get_fallback_coordinates

    # First try: Use country code with fallback coordinates (fastest for known missing countries)
    if country_code:
        fallback = get_fallback_coordinates(country_code)
        if fallback:
            return fallback

    # Second try: Look up in shared world bootstrap geometry
    geometry_lookup = get_geometry_lookup()
    if geometry_lookup:
        name_lower = country_name.lower().strip()

        for code, data in geometry_lookup.items():
            stored_name = data.get('country_name', '').lower().strip()
            if stored_name == name_lower:
                lat = data.get('latitude')
                lon = data.get('longitude')
                if lat and lon:
                    return (float(lat), float(lon))
                break

    return None


def build_response(cleaned: list, lookup, filter_spec=None, metadata=None, year_filter=None, sort_spec=None, interest=None):
    """
    Flexibly matches user queries against the selected dataset.
    Auto-detects which columns to search based on available data.

    Args:
        cleaned: List of dicts with 'place' and 'state' keys
        lookup: DataFrame with the data to search
        filter_spec: Optional dict with filter criteria (column, operator, value, unit)
        metadata: Optional metadata dict with column info and unit conversions
        year_filter: Optional dict with year filtering criteria (type: latest/single/range/comparison)
        sort_spec: Optional dict with sort criteria (sort_by: column, sort_order: asc/desc, limit: number)
        interest: What the user is interested in (e.g., "gdp", "population")
    """
    matches = []
    missing = []
    message = []

    # Apply year filter if present and dataset has year column
    if year_filter and metadata:
        data_year = metadata.get('data_year')

        # Only apply filtering if this is a time series dataset
        if isinstance(data_year, dict) and data_year.get('type') == 'time_series':
            year_column = data_year.get('year_column')

            if year_column and year_column in lookup.columns:
                original_rows = len(lookup)
                original_lookup = lookup.copy()  # Store original for fallback
                year_filter_type = year_filter.get('type')

                if year_filter_type == 'latest':
                    # Smart year selection: find year with best data coverage
                    latest_year = data_year.get('latest')
                    columns_needed = []

                    # Add filter column if present
                    if filter_spec:
                        filter_col_name = filter_spec.get('column')
                        for col in original_lookup.columns:
                            if col.lower() == filter_col_name.lower():
                                columns_needed.append(col)
                                break

                    # Add sort column if present (critical for sorting queries)
                    if sort_spec and sort_spec.get('sort_by'):
                        sort_col_name = sort_spec.get('sort_by')
                        for col in original_lookup.columns:
                            if col.lower() == sort_col_name.lower():
                                columns_needed.append(col)
                                break

                    # Add key interest columns (common metrics people query)
                    interest_keywords = ['per_capita', 'rate', 'expectancy', 'emissions',
                                       'population', 'index', 'mortality', 'coverage', 'co2']
                    for col in original_lookup.columns:
                        if any(keyword in col.lower() for keyword in interest_keywords):
                            if col not in columns_needed:
                                columns_needed.append(col)
                                if len(columns_needed) >= 5:  # Limit to avoid too many columns
                                    break

                    if columns_needed:
                        # Calculate data completeness for each year
                        year_scores = {}
                        available_years = sorted(original_lookup[year_column].unique(), reverse=True)

                        for year in available_years[:10]:  # Check last 10 years only for performance
                            year_data = original_lookup[original_lookup[year_column].astype(str) == str(year)]
                            if len(year_data) == 0:
                                continue

                            # Count rows with ALL needed columns populated
                            complete_rows = 0
                            for _, row in year_data.iterrows():
                                has_all_data = all(col in row and pd.notna(row[col]) for col in columns_needed)
                                if has_all_data:
                                    complete_rows += 1

                            if complete_rows == 0:
                                continue

                            # Score = completeness + recency bonus (handle year ranges like "2022-2023")
                            completeness = complete_rows / len(year_data)
                            year_int = parse_year_value(year)
                            if year_int is None:
                                continue
                            latest_year_int = parse_year_value(latest_year) or year_int
                            recency_bonus = (year_int / latest_year_int) * 0.2  # Up to 20% bonus
                            year_scores[year_int] = (completeness + recency_bonus, complete_rows)

                        if year_scores:
                            # Find year with best score
                            best_year = max(year_scores.keys(), key=lambda y: year_scores[y][0])
                            best_score, best_rows = year_scores[best_year]

                            if best_year != int(latest_year):
                                print(f"Smart year selection: {latest_year} has limited complete data")
                                print(f"  Year {best_year}: {best_rows} rows with all data (score: {best_score:.2f})")
                                print(f"  Columns checked: {', '.join(columns_needed[:3])}")
                                latest_year = best_year
                                message.append(f"Using year {latest_year} (best data coverage)")
                            else:
                                print(f"Year {latest_year}: {best_rows} rows with complete data")

                    lookup = lookup[lookup[year_column].astype(str) == str(latest_year)].copy()
                    if f"Using year {latest_year}" not in str(message):
                        message.append(f"Using latest available year: {latest_year}")
                    print(f"Year filter: Final year {latest_year} ({original_rows} -> {len(lookup)} rows)")

                elif year_filter_type == 'single':
                    # Filter to specific year
                    target_year = year_filter.get('year')
                    logger.debug(f"Year filter: year={target_year} in '{year_column}'")
                    filtered = lookup[lookup[year_column].astype(str) == str(target_year)].copy()
                    logger.debug(f"Year filter: {len(filtered)} rows for {target_year}")

                    # Check if we got any results, if not try closest year
                    if len(filtered) == 0:
                        print(f"No data for year {target_year}, looking for closest match...")
                        # Get available years from original unfiltered data (handles ranges like "2022-2023")
                        parsed_years = [parse_year_value(y) for y in original_lookup[year_column].dropna().unique()]
                        available_years = sorted([y for y in parsed_years if y is not None])
                        if available_years:
                            closest_year = min(available_years, key=lambda y: abs(y - target_year))
                            # Filter by parsed year value (handles ranges like "2022-2023")
                            lookup = original_lookup[original_lookup[year_column].apply(parse_year_value) == closest_year].copy()
                            message.append(f"Data for {target_year} not available. Using closest year: {closest_year}")
                            print(f"Using closest year: {closest_year} ({original_rows} -> {len(lookup)} rows)")
                        else:
                            lookup = filtered  # Keep empty if no years available
                    else:
                        lookup = filtered
                        message.append(f"Filtered to year: {target_year}")
                        print(f"Year filter: Using year {target_year} ({original_rows} -> {len(lookup)} rows)")

                elif year_filter_type == 'range':
                    # Filter to year range (handles ranges like "2022-2023")
                    start = year_filter.get('start')
                    end = year_filter.get('end')
                    parsed_years = lookup[year_column].apply(parse_year_value)
                    lookup = lookup[
                        (parsed_years >= start) &
                        (parsed_years <= end)
                    ].copy()
                    message.append(f"Filtered to years: {start}-{end}")
                    print(f"Year filter: Range {start}-{end} ({original_rows} -> {len(lookup)} rows)")

                elif year_filter_type == 'comparison':
                    # Filter to specific years for comparison (handles ranges like "2022-2023")
                    years = year_filter.get('years', [])
                    parsed_years = lookup[year_column].apply(parse_year_value)
                    lookup = lookup[parsed_years.isin(years)].copy()
                    message.append(f"Comparing years: {', '.join(map(str, years))}")
                    print(f"Year filter: Comparison years {years} ({original_rows} -> {len(lookup)} rows)")

    # Detect which column(s) to search - prioritize common name columns
    possible_name_cols = ['Location', 'Official County Name', 'Place Name', 'name', 'Name', 'COUNTY', 'county', 'country', 'country_name', 'Country', 'Country Name']
    possible_state_cols = ['State Name', 'state', 'State', 'STATE']

    name_col = None
    state_col = None

    for col in possible_name_cols:
        if col in lookup.columns:
            name_col = col
            break

    for col in possible_state_cols:
        if col in lookup.columns:
            state_col = col
            break

    if not name_col:
        logger.warning(f"No recognizable name column found in {lookup.columns.tolist()}")
        return {
            "geojson": {"type": "FeatureCollection", "features": []},
            "markers": [],
            "message": ["Error: Could not find name column in dataset"]
        }

    logger.debug(f"build_response: {len(lookup)} rows")

    # Check if this is a "show all" query (filter-based with no specific places)
    # This happens when place names are empty or just ["all"]
    is_show_all = (not cleaned or
                   all(not item.get("place") or item.get("place").strip() == "" or item.get("place").lower() == "all"
                       for item in cleaned))

    # Show all query: no specific places but want to see all data
    # This includes: filter queries, sort queries, or "all countries" queries (region-filtered datasets)
    if is_show_all:
        # Filter/sort-based query: return ALL rows that pass the filter (or all rows if just sorting)
        logger.debug(f"Show all: {len(lookup)} rows")

        # Find the actual filter column name (case-insensitive) if filter_spec exists
        filter_col = None
        operator = None
        threshold = None
        user_unit = None

        if filter_spec:
            filter_col_requested = filter_spec.get("column")

            # Common column name mappings for filters
            column_aliases = {
                "country": ["country_name", "country", "name", "location"],
                "state": ["state_name", "state", "stusab"],
                "name": ["country_name", "state_name", "name", "location"],
                "year": ["data_year", "year"],
            }

            # First try exact case-insensitive match
            for col in lookup.columns:
                if col.lower() == filter_col_requested.lower():
                    filter_col = col
                    break

            # If not found, try aliases
            if not filter_col:
                requested_lower = filter_col_requested.lower()
                if requested_lower in column_aliases:
                    for alias in column_aliases[requested_lower]:
                        for col in lookup.columns:
                            if col.lower() == alias.lower():
                                filter_col = col
                                print(f"Filter column alias: '{filter_col_requested}' -> '{filter_col}'")
                                break
                        if filter_col:
                            break

            if not filter_col:
                print(f"Warning: Filter column '{filter_col_requested}' not found in dataset columns: {list(lookup.columns)[:10]}")
                filter_col = filter_col_requested  # Fall back to original

            operator = filter_spec.get("operator")
            threshold = filter_spec.get("value")
            user_unit = filter_spec.get("unit")

        rows_checked = 0
        rows_with_col = 0
        rows_passing_filter = 0
        rows_with_geometry = 0
        missing_geometry_names = []  # Track places without geometry

        for _, row in lookup.iterrows():
            rows_checked += 1

            # If we have a filter, apply it
            if filter_spec:
                # Check if the filter column exists in the data
                if filter_col not in row or pd.isna(row[filter_col]):
                    continue

                rows_with_col += 1

                try:
                    row_value = row[filter_col]
                    passes_filter = False

                    # Handle string comparisons (for = and != with non-numeric values)
                    if operator in ("=", "!=") and isinstance(threshold, str):
                        row_str = str(row_value).strip().lower()
                        threshold_str = str(threshold).strip().lower()
                        if operator == "=":
                            passes_filter = row_str == threshold_str
                        else:  # !=
                            passes_filter = row_str != threshold_str
                    else:
                        # Numeric comparison
                        row_value = float(row_value)

                        # Convert units if metadata is available
                        if metadata and user_unit:
                            col_metadata = metadata.get("columns", {}).get(filter_col, {})
                            stored_unit = col_metadata.get("unit")

                            if stored_unit and stored_unit != user_unit:
                                # Convert stored value to user's requested unit
                                row_value = convert_unit(row_value, stored_unit, user_unit, col_metadata)
                                if row_value is None:
                                    print(f"Warning: Could not convert {stored_unit} to {user_unit} for {filter_col}")
                                    continue

                        # Apply the comparison operator
                        if operator == ">":
                            passes_filter = row_value > threshold
                        elif operator == "<":
                            passes_filter = row_value < threshold
                        elif operator == ">=":
                            passes_filter = row_value >= threshold
                        elif operator == "<=":
                            passes_filter = row_value <= threshold
                        elif operator == "=":
                            passes_filter = abs(row_value - threshold) < 0.001
                        elif operator == "!=":
                            passes_filter = abs(row_value - threshold) >= 0.001

                    if not passes_filter:
                        continue  # Skip this row

                    rows_passing_filter += 1

                except (ValueError, TypeError) as e:
                    print(f"Warning: Could not apply filter to {filter_col}: {e}")
                    continue
            else:
                # No filter - just collecting all rows for sorting
                rows_passing_filter += 1

            # Check if geometry exists and is valid
            has_geometry = ("geometry" in row and pd.notna(row["geometry"]))
            geom = None

            if has_geometry:
                try:
                    geom_value = row["geometry"]
                    if isinstance(geom_value, str):
                        geom = json.loads(geom_value)
                        rows_with_geometry += 1
                except (json.JSONDecodeError, TypeError):
                    has_geometry = False

            # If no polygon geometry, create a Point fallback using shared world bootstrap coordinates
            if not has_geometry and name_col and name_col in row:
                country_name = str(row[name_col])
                # Look up coordinates from shared world bootstrap geometry via cache
                coords = get_country_coordinates(country_name)
                if coords:
                    lat, lon = coords
                    geom = {"type": "Point", "coordinates": [lon, lat]}
                    rows_with_geometry += 1

            # Track places missing geometry (but still create features - enrichment will try to add geometry)
            if not geom:
                if name_col and name_col in row:
                    place_name = str(row[name_col])
                    if place_name and place_name not in missing_geometry_names:
                        missing_geometry_names.append(place_name)

            # Smart field filtering: show only essential fields based on dataset
            # Goal: Show 3-5 fields (country identifier + filter column + key metrics)
            keep_fields = set()

            # Always include identifier fields (find country/place name column)
            for id_col in ['admin', 'name', 'country', 'Location', 'sovereignt']:
                if id_col in row:
                    keep_fields.add(id_col)
                    break  # Only need one identifier

            # Always include the filter column (the field user queried about)
            if filter_col:
                keep_fields.add(filter_col)

            # Always include the sort column if sorting
            if sort_spec and sort_spec.get("sort_by"):
                sort_by_col = sort_spec.get("sort_by")
                # Find the actual column name (case-insensitive)
                for col in row.keys():
                    if col.lower() == sort_by_col.lower():
                        keep_fields.add(col)
                        break

            # Always include year for popup display
            if 'year' in row and pd.notna(row['year']):
                keep_fields.add('year')
            if 'data_year' in row and pd.notna(row['data_year']):
                keep_fields.add('data_year')

            # Include the interest column (what user asked about, e.g., "gdp", "population")
            if interest:
                interest_lower = interest.lower()
                for col in row.keys():
                    col_lower = col.lower()
                    # Match if interest is in column name or column name is in interest
                    if interest_lower in col_lower or col_lower in interest_lower:
                        keep_fields.add(col)
                        break  # Only add first match

            # Only include explicitly requested fields - chat will guide if more data is needed
            # Always include identifier columns for enrichment lookup
            keep_fields.add(name_col)
            if 'country_code' in row:
                keep_fields.add('country_code')
            if 'iso_code' in row:
                keep_fields.add('iso_code')

            # Build properties dict from relevant columns only
            properties = {
                k: (None if pd.isna(v) else v)
                for k, v in row.items()
                if k != "geometry" and k in keep_fields
            }

            feature = {
                "type": "Feature",
                "geometry": geom,
                "properties": properties
            }
            matches.append(feature)

        print(f"Filter stats: {rows_checked} rows checked, {rows_with_col} have {filter_col}, {rows_passing_filter} pass filter, {rows_with_geometry} have geometry, {len(matches)} final results")

        # Apply sorting and limiting if requested
        if sort_spec and matches:
            sort_by = sort_spec.get("sort_by")
            sort_order = sort_spec.get("sort_order", "desc")
            limit = sort_spec.get("limit")

            if sort_by:
                # Find the actual column name (case-insensitive match)
                sort_column = None
                for feature in matches:
                    if sort_by.lower() in [k.lower() for k in feature["properties"].keys()]:
                        # Find exact key with case-insensitive match
                        for k in feature["properties"].keys():
                            if k.lower() == sort_by.lower():
                                sort_column = k
                                break
                        break

                if sort_column:
                    print(f"Sorting {len(matches)} results by {sort_column} ({sort_order})")

                    # Sort features by the specified column
                    def get_sort_value(feature):
                        val = feature["properties"].get(sort_column)
                        if val is None:
                            return float('-inf') if sort_order == "desc" else float('inf')
                        try:
                            return float(val)
                        except (ValueError, TypeError):
                            return float('-inf') if sort_order == "desc" else float('inf')

                    matches = sorted(matches, key=get_sort_value, reverse=(sort_order == "desc"))
                    message.append(f"Sorted by {sort_column} ({sort_order})")
                else:
                    print(f"Warning: Sort column '{sort_by}' not found in results")

            # Apply limit if specified
            if limit and limit > 0:
                original_count = len(matches)
                matches = matches[:limit]
                print(f"Limited results from {original_count} to {limit}")
                message.append(f"Showing top {limit} results")

        if not sort_spec or not sort_spec.get("limit"):
            message.append(f"Showing {len(matches)} locations matching filter")

        # Enrich features with geometry from shared world bootstrap layer if missing
        logger.debug(f"Before enrichment: {len(matches)} features")
        enriched_matches, still_missing_count, still_missing_names = enrich_with_geometry(
            matches, name_col=name_col, code_col='country_code'
        )
        logger.debug(f"After enrichment: {len(enriched_matches)} features")

        # Only report what's STILL missing after enrichment attempted to add geometry
        all_missing = still_missing_names

        # Add note about missing geometry if any
        if all_missing:
            message.append(f"Note: {len(all_missing)} locations missing map boundaries")

        # Generate conversational summary
        summary = generate_conversational_summary(enriched_matches, sort_spec, filter_spec, metadata)

        return {
            "geojson": {"type": "FeatureCollection", "features": enriched_matches},
            "markers": [],
            "message": message,
            "summary": summary,
            "missing_geometry": all_missing[:10],  # Limit to 10 names
            "missing_geometry_count": len(all_missing)
        }

    # Specific places query: match individual place names
    print(f"Using columns: name='{name_col}', state='{state_col}' for {len(cleaned)} places")

    for item in cleaned:
        place_name = item.get("place", "").lower()
        state_name = item.get("state", "").lower() if item.get("state") else None

        best_score = 0
        best_match = None

        for _, row in lookup.iterrows():
            # Match on place/county name
            candidate = str(row[name_col]).lower()
            score = fuzz.partial_ratio(place_name, candidate)

            # Boost score if state also matches
            if state_col and state_name:
                candidate_state = str(row[state_col]).lower()
                if state_name in candidate_state or candidate_state in state_name:
                    score += 20  # Boost for state match

            if score > best_score:
                best_score = score
                best_match = row

        if best_score >= 70 and best_match is not None:
            # Apply numerical filter if specified
            if filter_spec:
                filter_col = filter_spec.get("column")
                operator = filter_spec.get("operator")
                threshold = filter_spec.get("value")
                user_unit = filter_spec.get("unit")

                # Check if the filter column exists in the data
                if filter_col in best_match:
                    try:
                        row_value = float(best_match[filter_col])

                        # Convert units if metadata is available
                        if metadata and user_unit:
                            col_metadata = metadata.get("columns", {}).get(filter_col, {})
                            stored_unit = col_metadata.get("unit")

                            if stored_unit and stored_unit != user_unit:
                                # Convert stored value to user's requested unit
                                row_value = convert_unit(row_value, stored_unit, user_unit, col_metadata)
                                if row_value is None:
                                    print(f"Warning: Could not convert {stored_unit} to {user_unit} for {filter_col}")
                                    continue

                        # Apply the comparison operator
                        passes_filter = False
                        if operator == ">":
                            passes_filter = row_value > threshold
                        elif operator == "<":
                            passes_filter = row_value < threshold
                        elif operator == ">=":
                            passes_filter = row_value >= threshold
                        elif operator == "<=":
                            passes_filter = row_value <= threshold
                        elif operator == "=":
                            passes_filter = abs(row_value - threshold) < 0.001  # Float comparison
                        elif operator == "!=":
                            passes_filter = abs(row_value - threshold) >= 0.001

                        if not passes_filter:
                            continue  # Skip this match, doesn't meet filter criteria

                    except (ValueError, TypeError) as e:
                        print(f"Warning: Could not apply filter to {filter_col}: {e}")
                        continue

            # Check if geometry exists and is valid (not NaN)
            if "geometry" not in best_match or pd.isna(best_match["geometry"]):
                print(f"Skipping row - missing geometry for {best_match.get(name_col, 'unknown')}")
                continue

            try:
                # Ensure geometry is a string before parsing
                geom_value = best_match["geometry"]
                if not isinstance(geom_value, str):
                    print(f"Skipping row - geometry is not a string (type: {type(geom_value).__name__})")
                    continue
                geometry = json.loads(geom_value)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Skipping row due to invalid geometry: {e}")
                continue

            # Build properties dynamically from available columns, filtering out NaN
            properties = {"name": str(best_match[name_col])}
            if state_col and pd.notna(best_match[state_col]):
                properties["state"] = str(best_match[state_col])
            if "Official County Code" in best_match and pd.notna(best_match["Official County Code"]):
                properties["geoid"] = str(best_match["Official County Code"])
            if "Land Area" in best_match and pd.notna(best_match["Land Area"]):
                properties["land_area"] = str(best_match["Land Area"])
            if "Water Area" in best_match and pd.notna(best_match["Water Area"]):
                properties["water_area"] = str(best_match["Water Area"])

            matches.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": properties
            })
        else:
            missing.append(item)

    message.append(f"Matched {len(matches)} of {len(cleaned)} entries.")
    print(message)

    for item in missing:
        state_info = f" ({item.get('state', 'N/A')})" if item.get('state') else ""
        print(f"No match for: {item.get('place', 'Unknown')}{state_info}")
        message.append(f"No match for: {item.get('place', 'Unknown')}{state_info}")

    return {
        "geojson": {
            "type": "FeatureCollection",
            "features": matches,
        },
        "markers": [],
        "message": message,
    }
