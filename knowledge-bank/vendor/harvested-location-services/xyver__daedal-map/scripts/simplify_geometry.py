"""
Simplify geometry in parquet files to reduce file sizes and improve loading performance.

Applies tolerance-based simplification using Shapely's simplify() with preserve_topology=True.

Tolerances by admin level:
    0 (Countries):     0.01    (~1 km)
    1 (States):        0.001   (~100 m)
    2 (Counties):      0.001   (~100 m)
    3 (ZCTAs):         0.0001  (~10 m)
    4 (Tracts):        0.0001  (~10 m)
    5 (Block Groups):  0.00005 (~5 m)
    6 (Blocks):        0.00001 (~1 m)

Usage:
    python simplify_geometry.py                    # Process all USA geometry files
    python simplify_geometry.py --dry-run          # Show what would be processed
    python simplify_geometry.py --file <path>      # Process single file
    python simplify_geometry.py --level <n>        # Process specific admin level
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# Add parent directory to path for mapmover imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from mapmover.paths import DATA_ROOT

# Lazy import shapely (not always installed)
try:
    from shapely import simplify as shapely_simplify
    from shapely.geometry import shape, mapping
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("WARNING: shapely not installed. Install with: pip install shapely")

# Configuration
BACKUP_DIR = DATA_ROOT / "backups" / f"geometry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# Tolerance by admin level
TOLERANCES = {
    0: 0.01,      # Countries - ~1 km
    1: 0.001,     # States - ~100 m
    2: 0.001,     # Counties - ~100 m
    3: 0.0001,    # ZCTAs - ~10 m
    4: 0.0001,    # Census Tracts - ~10 m
    5: 0.00005,   # Block Groups - ~5 m
    6: 0.00001,   # Blocks - ~1 m
}

# Files to process with their admin levels
GEOMETRY_FILES = {
    # Main USA geometry (mixed levels 0-2)
    "geometry/USA.parquet": "mixed",

    # ZCTA (level 3)
    "geometry/countries/USA/geometry_zcta.parquet": 3,

    # Tracts by state (level 4)
    "geometry/countries/USA/tract": 4,

    # Block Groups by state (level 5)
    "geometry/countries/USA/blockgroup": 5,

    # Blocks by state (level 6)
    "geometry/countries/USA/block": 6,
}


def simplify_geometry_string(geom_str, tolerance):
    """Simplify a GeoJSON geometry string using Shapely."""
    if not geom_str or not isinstance(geom_str, str):
        return geom_str

    try:
        geom = shape(json.loads(geom_str))
        simplified = shapely_simplify(geom, tolerance, preserve_topology=True)
        return json.dumps(mapping(simplified))
    except Exception as e:
        print(f"    Warning: Could not simplify geometry: {e}")
        return geom_str


def get_tolerance_for_row(row, default_level):
    """Get tolerance based on admin_level column or default."""
    if default_level == "mixed":
        # Use admin_level from the row
        level = row.get('admin_level', 2)
        return TOLERANCES.get(level, 0.001)
    else:
        return TOLERANCES.get(default_level, 0.0001)


def process_parquet_file(file_path, admin_level, dry_run=False, backup=True):
    """Process a single parquet file, simplifying geometries."""
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"  SKIP: File not found: {file_path}")
        return None

    # Get file size before
    size_before = file_path.stat().st_size / (1024 * 1024)  # MB

    print(f"  Processing: {file_path.name}")
    print(f"    Size before: {size_before:.2f} MB")
    print(f"    Admin level: {admin_level}")

    if dry_run:
        print(f"    [DRY RUN] Would simplify with tolerance {TOLERANCES.get(admin_level, 'mixed')}")
        return {"file": str(file_path), "size_before": size_before, "dry_run": True}

    # Read parquet
    df = pd.read_parquet(file_path)
    row_count = len(df)
    print(f"    Rows: {row_count}")

    if 'geometry' not in df.columns:
        print(f"    SKIP: No geometry column")
        return None

    # Backup original
    if backup:
        backup_path = BACKUP_DIR / file_path.relative_to(DATA_ROOT)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        print(f"    Backed up to: {backup_path}")

    # Sample geometry size before
    sample_before = len(df.iloc[0]['geometry']) if len(df) > 0 and df.iloc[0]['geometry'] else 0

    # Simplify geometries
    if admin_level == "mixed":
        # Per-row tolerance based on admin_level
        df['geometry'] = df.apply(
            lambda row: simplify_geometry_string(
                row['geometry'],
                get_tolerance_for_row(row, "mixed")
            ),
            axis=1
        )
    else:
        # Fixed tolerance for all rows
        tolerance = TOLERANCES[admin_level]
        df['geometry'] = df['geometry'].apply(
            lambda g: simplify_geometry_string(g, tolerance)
        )

    # Sample geometry size after
    sample_after = len(df.iloc[0]['geometry']) if len(df) > 0 and df.iloc[0]['geometry'] else 0

    # Save back
    df.to_parquet(file_path, index=False)

    # Get file size after
    size_after = file_path.stat().st_size / (1024 * 1024)
    reduction = (1 - size_after / size_before) * 100 if size_before > 0 else 0

    print(f"    Size after: {size_after:.2f} MB ({reduction:.1f}% reduction)")
    print(f"    Sample geometry: {sample_before} -> {sample_after} chars")

    return {
        "file": str(file_path),
        "rows": row_count,
        "size_before": size_before,
        "size_after": size_after,
        "reduction_pct": reduction,
        "sample_before": sample_before,
        "sample_after": sample_after,
    }


def process_directory(dir_path, admin_level, dry_run=False, backup=True):
    """Process all parquet files in a directory."""
    dir_path = Path(dir_path)

    if not dir_path.exists():
        print(f"  SKIP: Directory not found: {dir_path}")
        return []

    results = []
    parquet_files = sorted(dir_path.glob("*.parquet"))

    print(f"\n  Directory: {dir_path}")
    print(f"  Files: {len(parquet_files)}")

    for pq_file in parquet_files:
        result = process_parquet_file(pq_file, admin_level, dry_run, backup)
        if result:
            results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Simplify geometry in parquet files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without making changes")
    parser.add_argument("--file", type=str, help="Process a single file")
    parser.add_argument("--level", type=int, choices=[0,1,2,3,4,5,6], help="Process only files for this admin level")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup (not recommended)")
    args = parser.parse_args()

    if not SHAPELY_AVAILABLE:
        print("ERROR: shapely is required. Install with: pip install shapely")
        return 1

    print("=" * 60)
    print("Geometry Simplification Tool")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    backup = not args.no_backup
    if backup and not args.dry_run:
        print(f"\nBackups will be saved to: {BACKUP_DIR}")

    all_results = []

    # Process single file
    if args.file:
        file_path = Path(args.file)
        # Guess admin level from path
        if "geometry_block/" in str(file_path):
            level = 6
        elif "geometry_blockgroup/" in str(file_path):
            level = 5
        elif "geometry_tract/" in str(file_path):
            level = 4
        elif "geometry_zcta" in str(file_path):
            level = 3
        else:
            level = "mixed"

        result = process_parquet_file(file_path, level, args.dry_run, backup)
        if result:
            all_results.append(result)

    # Process by level
    elif args.level is not None:
        level = args.level
        print(f"\nProcessing admin level {level} only...")

        for path, file_level in GEOMETRY_FILES.items():
            if file_level == level or (file_level == "mixed" and level <= 2):
                full_path = DATA_ROOT / path
                if full_path.is_dir():
                    results = process_directory(full_path, level, args.dry_run, backup)
                    all_results.extend(results)
                elif full_path.is_file():
                    result = process_parquet_file(full_path, file_level, args.dry_run, backup)
                    if result:
                        all_results.append(result)

    # Process all
    else:
        print("\nProcessing all geometry files...")

        for path, admin_level in GEOMETRY_FILES.items():
            full_path = DATA_ROOT / path

            if full_path.is_dir():
                results = process_directory(full_path, admin_level, args.dry_run, backup)
                all_results.extend(results)
            elif full_path.is_file():
                result = process_parquet_file(full_path, admin_level, args.dry_run, backup)
                if result:
                    all_results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if not all_results:
        print("No files processed.")
        return 0

    total_before = sum(r.get('size_before', 0) for r in all_results)
    total_after = sum(r.get('size_after', 0) for r in all_results if 'size_after' in r)

    print(f"Files processed: {len(all_results)}")
    print(f"Total size before: {total_before:.2f} MB")

    if not args.dry_run:
        total_reduction = (1 - total_after / total_before) * 100 if total_before > 0 else 0
        print(f"Total size after: {total_after:.2f} MB")
        print(f"Total reduction: {total_reduction:.1f}%")
        print(f"\nBackups saved to: {BACKUP_DIR}")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
