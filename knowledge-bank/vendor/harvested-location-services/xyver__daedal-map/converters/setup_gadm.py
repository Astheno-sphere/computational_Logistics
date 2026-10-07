"""Historical GADM conversion utility; not part of any active build or runtime.

Do not use this script to populate DaedalMap geometry. The active global
baseline is geoBoundaries and country releases use reviewed authority sources.
A future GADM integration, if pursued, belongs in the free external-reference
bridge family and must map identifiers without admitting GADM polygons.

Historical behavior: download and process GADM into per-country Parquet files.

GADM (Global Administrative Areas) provides sub-national boundaries for 267 countries.
This script downloads the GeoPackage and converts it to per-country parquet files
that the app can use for admin1/admin2 choropleth display.

Output: geometry/{ISO3}.parquet (one file per country, all admin levels)

Schema (14 columns):
  loc_id, parent_id, admin_level, name, name_local, code, iso_3166_2,
  centroid_lon, centroid_lat, has_polygon, geometry, bbox_min_lon,
  bbox_min_lat, bbox_max_lon, bbox_max_lat, timezone, iso_a3

Usage:
    python converters/setup_gadm.py --country USA
    python converters/setup_gadm.py --country DEU FRA GBR
    python converters/setup_gadm.py --all
    python converters/setup_gadm.py --country JPN --output data/geometry
    python converters/setup_gadm.py --country BRA --gadm-file /path/to/gadm_410.gpkg

The script will download the GADM GeoPackage (~1.8 GB) on first run if not found.
Subsequent runs use the cached file.

Requirements:
    pip install shapely pandas pyarrow
"""

import sqlite3
import pandas as pd
import json
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from shapely import wkb
from shapely.geometry import mapping
import re

# GADM download URL (version 4.1)
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gadm_410-gpkg.zip"
GADM_TABLE = "gadm_410"

# Default cache location for downloaded GADM file
DEFAULT_GADM_CACHE = Path.home() / ".cache" / "county-map" / "gadm_410.gpkg"


def download_gadm(output_path: Path):
    """Download GADM GeoPackage if not already cached."""
    if output_path.exists():
        print(f"Using cached GADM file: {output_path}")
        return output_path

    print(f"Downloading GADM 4.1 GeoPackage (~1.8 GB)...")
    print(f"  Source: {GADM_URL}")
    print(f"  Destination: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import urllib.request
        import zipfile
        import tempfile

        zip_path = output_path.with_suffix(".zip")
        urllib.request.urlretrieve(GADM_URL, zip_path)

        print("  Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Find the .gpkg file inside
            gpkg_names = [n for n in zf.namelist() if n.endswith(".gpkg")]
            if not gpkg_names:
                print("ERROR: No .gpkg file found in ZIP archive")
                sys.exit(1)
            zf.extract(gpkg_names[0], output_path.parent)
            extracted = output_path.parent / gpkg_names[0]
            if extracted != output_path:
                extracted.rename(output_path)

        zip_path.unlink()
        print(f"  Done. GADM file: {output_path}")

    except Exception as e:
        print(f"ERROR downloading GADM: {e}")
        print("You can manually download from: https://gadm.org/download_world.html")
        print(f"Place the .gpkg file at: {output_path}")
        sys.exit(1)

    return output_path


def normalize_name(name):
    """Normalize name for matching."""
    if not name:
        return ""
    name = str(name).lower().strip()
    for suffix in [" county", " parish", " borough", " census area",
                   " municipality", " city and borough", " city and", " city"]:
        name = name.replace(suffix, "")
    name = name.replace("saint ", "st ")
    name = name.replace("sainte ", "ste ")
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def get_admin_level(row):
    """Determine admin level based on which NAME columns are filled."""
    for level in range(5, -1, -1):
        name = row.get(f"NAME_{level}")
        if name is not None and str(name).strip() != "":
            return level
    return 0


def parse_gpkg_geometry(gpkg_bytes):
    """Parse GeoPackage Binary format to Shapely geometry."""
    if gpkg_bytes is None or len(gpkg_bytes) < 8:
        return None

    magic = gpkg_bytes[:2]
    if magic != b"GP":
        try:
            return wkb.loads(gpkg_bytes)
        except Exception:
            return None

    flags = gpkg_bytes[3]
    envelope_type = (flags >> 1) & 0x07
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    envelope_size = envelope_sizes.get(envelope_type, 0)
    wkb_start = 8 + envelope_size
    wkb_bytes = gpkg_bytes[wkb_start:]

    try:
        return wkb.loads(wkb_bytes)
    except Exception:
        return None


def get_centroid(geom_bytes):
    """Get centroid from GPKG geometry bytes."""
    try:
        geom = parse_gpkg_geometry(geom_bytes)
        if geom is None or geom.is_empty:
            return None, None
        centroid = geom.centroid
        return round(centroid.x, 6), round(centroid.y, 6)
    except Exception:
        return None, None


def get_simplify_tolerance(admin_level):
    """Get simplification tolerance based on admin level."""
    if admin_level == 0:
        return 0.01      # Countries: ~1 km
    elif admin_level <= 2:
        return 0.001     # States/Counties: ~100 m
    else:
        return 0.0001    # Cities/Districts: ~10 m


def geometry_to_geojson(geom_bytes, admin_level=2):
    """Convert GPKG geometry to GeoJSON string with simplification."""
    try:
        geom = parse_gpkg_geometry(geom_bytes)
        if geom is None or geom.is_empty:
            return None
        tolerance = get_simplify_tolerance(admin_level)
        geom = geom.simplify(tolerance, preserve_topology=True)
        return json.dumps(mapping(geom))
    except Exception:
        return None


def get_bbox_from_geometry(geometry_str):
    """Extract bounding box from GeoJSON geometry string."""
    if not geometry_str:
        return None, None, None, None
    try:
        from shapely.geometry import shape
        geom_data = json.loads(geometry_str)
        geom = shape(geom_data)
        bounds = geom.bounds
        return round(bounds[0], 6), round(bounds[1], 6), round(bounds[2], 6), round(bounds[3], 6)
    except Exception:
        return None, None, None, None


def is_placeholder_level(df, level):
    """Check if a level is a placeholder (all names empty/null)."""
    level_df = df[df["admin_level"] == level]
    if len(level_df) == 0:
        return False
    names = level_df["name"].fillna("")
    unique_names = names.unique()
    if len(unique_names) == 1 and unique_names[0] in ["", "Unknown", None]:
        return True
    empty_count = (names == "").sum() + level_df["name"].isna().sum()
    if empty_count / len(level_df) > 0.9:
        return True
    return False


def remove_placeholder_levels(df):
    """Remove placeholder admin levels from the DataFrame."""
    levels = sorted(df["admin_level"].unique())
    removed_levels = []
    for level in reversed(levels):
        if level == 0:
            continue
        if is_placeholder_level(df, level):
            removed_levels.append(level)
            df = df[df["admin_level"] != level]
        else:
            break
    return df, removed_levels


def build_loc_id(row, admin_level):
    """
    Build loc_id from GADM row data.
    Format: {ISO3}[-{admin1_code}[-{admin2_code}[...]]]
    Uses HASC codes where available, else GID suffix.
    """
    iso3 = row.get("GID_0", "")
    if admin_level == 0:
        return iso3

    parts = [iso3]
    for level in range(1, admin_level + 1):
        hasc = row.get(f"HASC_{level}", "")
        cc = row.get(f"CC_{level}", "")

        if hasc and "." in hasc:
            parts.append(hasc.split(".")[-1])
        elif cc:
            parts.append(str(cc))
        else:
            gid = row.get(f"GID_{level}", "")
            if gid:
                suffix = gid.split(".")[-1].split("_")[0]
                parts.append(suffix)
            else:
                parts.append(str(level))

    return "-".join(parts)


def build_parent_id(loc_id):
    """Get parent_id by removing last component."""
    if "-" not in loc_id:
        return None
    return loc_id.rsplit("-", 1)[0]


def process_country(conn, iso3):
    """Process all admin levels for a single country."""
    query = f"SELECT * FROM {GADM_TABLE} WHERE GID_0 = ?"
    cursor = conn.execute(query, (iso3,))
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()

    if not rows:
        return []

    locations = {}

    for row_data in rows:
        row = dict(zip(columns, row_data))
        admin_level = get_admin_level(row)

        for level in range(admin_level, -1, -1):
            loc_id = build_loc_id(row, level)

            if loc_id in locations:
                continue

            geom_bytes = row.get("geom")
            if level < admin_level:
                lon, lat = None, None
                geometry_str = None
                has_polygon = False
            else:
                lon, lat = get_centroid(geom_bytes)
                geometry_str = geometry_to_geojson(geom_bytes, level)
                has_polygon = geometry_str is not None

            name_col = f"NAME_{level}"
            name = row.get(name_col, row.get("NAME_0", ""))

            varname_col = f"VARNAME_{level}" if level > 0 else None
            nlname_col = f"NL_NAME_{level}" if level > 0 else None
            name_local = row.get(varname_col) or row.get(nlname_col)
            if name_local == name:
                name_local = None

            code = row.get(f"CC_{level}", "") if level > 0 else iso3

            iso_3166_2 = None
            if level == 1:
                hasc = row.get("HASC_1", "")
                if hasc:
                    iso_3166_2 = hasc.replace(".", "-")

            bbox_min_lon, bbox_min_lat, bbox_max_lon, bbox_max_lat = get_bbox_from_geometry(geometry_str)

            record = {
                "loc_id": loc_id,
                "parent_id": build_parent_id(loc_id),
                "admin_level": level,
                "name": name,
                "name_local": name_local,
                "code": str(code) if code else "",
                "iso_3166_2": iso_3166_2,
                "centroid_lon": lon,
                "centroid_lat": lat,
                "has_polygon": has_polygon,
                "geometry": geometry_str,
                "bbox_min_lon": bbox_min_lon,
                "bbox_min_lat": bbox_min_lat,
                "bbox_max_lon": bbox_max_lon,
                "bbox_max_lat": bbox_max_lat,
                "timezone": None,
                "iso_a3": iso3
            }

            locations[loc_id] = record

    return list(locations.values())


def process_countries(gadm_file: Path, output_dir: Path, country_list=None):
    """
    Process countries from GADM and create per-country parquet files.

    Args:
        gadm_file: Path to GADM GeoPackage file
        output_dir: Output directory for parquet files
        country_list: List of ISO3 codes, or None for all countries
    """
    print("=" * 60)
    print("GADM Geometry Processor")
    print("=" * 60)
    print(f"Input: {gadm_file}")
    print(f"Output: {output_dir}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if not gadm_file.exists():
        print(f"ERROR: GADM file not found: {gadm_file}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(gadm_file)

    # Get country list
    if country_list:
        cursor = conn.execute(f"SELECT DISTINCT GID_0 FROM {GADM_TABLE}")
        valid = {row[0] for row in cursor.fetchall()}
        countries = [c.upper() for c in country_list if c.upper() in valid]
        invalid = [c for c in country_list if c.upper() not in valid]
        if invalid:
            print(f"Warning: Countries not in GADM: {invalid}")
    else:
        cursor = conn.execute(f"SELECT DISTINCT GID_0 FROM {GADM_TABLE} ORDER BY GID_0")
        countries = [row[0] for row in cursor.fetchall()]

    print(f"Processing {len(countries)} countries\n")

    for i, iso3 in enumerate(countries):
        print(f"  [{i+1}/{len(countries)}] {iso3}...", end=" ")

        records = process_country(conn, iso3)
        if not records:
            print("no records")
            continue

        df = pd.DataFrame(records)
        df = df.sort_values(["admin_level", "loc_id"])

        # Remove placeholder levels
        df, removed = remove_placeholder_levels(df)

        df["admin_level"] = df["admin_level"].astype("int8")
        df["has_polygon"] = df["has_polygon"].astype(bool)

        output_file = output_dir / f"{iso3}.parquet"
        df.to_parquet(output_file, index=False)

        max_depth = df["admin_level"].max()
        removed_str = f" (removed levels: {removed})" if removed else ""
        print(f"{len(df)} records, depth {max_depth}{removed_str}")

    conn.close()

    print(f"\nDone. {len(countries)} countries processed.")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download and process GADM geometry into per-country parquet files."
    )
    parser.add_argument(
        "--country", nargs="+",
        help="ISO3 country codes to process (e.g. --country USA DEU FRA)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Process all 267 countries (takes a while)"
    )
    parser.add_argument(
        "--output", type=str, default="data/geometry",
        help="Output directory for parquet files (default: data/geometry)"
    )
    parser.add_argument(
        "--gadm-file", type=str, default=None,
        help="Path to existing GADM GeoPackage (skips download)"
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Do not download GADM if missing (error instead)"
    )

    args = parser.parse_args()

    if not args.country and not args.all:
        parser.error("Specify --country ISO3 [ISO3 ...] or --all")

    # Resolve output path
    output_dir = Path(args.output).resolve()

    # Find or download GADM file
    if args.gadm_file:
        gadm_file = Path(args.gadm_file).resolve()
        if not gadm_file.exists():
            print(f"ERROR: GADM file not found: {gadm_file}")
            sys.exit(1)
    else:
        gadm_file = DEFAULT_GADM_CACHE
        if not gadm_file.exists():
            if args.no_download:
                print(f"ERROR: GADM file not found: {gadm_file}")
                print("Run without --no-download to auto-download, or use --gadm-file")
                sys.exit(1)
            gadm_file = download_gadm(gadm_file)

    # Process
    country_list = args.country if args.country else None
    process_countries(gadm_file, output_dir, country_list)
