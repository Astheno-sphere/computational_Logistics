"""
Add last_updated and status columns to event parquet files.

For historical data:
- last_updated = timestamp (same as event time)
- status = 'historical'

This script updates all event parquet files to match the unified event schema.
"""

import sys
import pandas as pd
from pathlib import Path

# Add parent directory to path for mapmover imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from mapmover.paths import COUNTRIES_DIR

# Event parquet files to update
EVENT_FILES = [
    str(COUNTRIES_DIR / "USA" / "usgs_earthquakes" / "events.parquet"),
    str(COUNTRIES_DIR / "USA" / "hurricanes" / "positions.parquet"),
    str(COUNTRIES_DIR / "USA" / "wildfires" / "fires.parquet"),
    str(COUNTRIES_DIR / "USA" / "volcanoes" / "eruptions.parquet"),
    str(COUNTRIES_DIR / "USA" / "tsunamis" / "events.parquet"),
    str(COUNTRIES_DIR / "USA" / "noaa_storms" / "events.parquet"),
]

# Column name that contains the timestamp (varies by file)
TIMESTAMP_COLUMNS = {
    "events.parquet": "timestamp",  # Most files use 'timestamp'
    "positions.parquet": "timestamp",
    "fires.parquet": "timestamp",
    "eruptions.parquet": "timestamp",
}


def get_timestamp_column(filepath: Path) -> str:
    """Get the timestamp column name for a file."""
    filename = filepath.name
    return TIMESTAMP_COLUMNS.get(filename, "timestamp")


def add_temporal_columns(filepath: str, dry_run: bool = False) -> dict:
    """
    Add last_updated and status columns to an event parquet file.

    Args:
        filepath: Path to the parquet file
        dry_run: If True, don't save changes

    Returns:
        dict with stats about the update
    """
    path = Path(filepath)
    if not path.exists():
        return {"file": str(path), "status": "not_found", "error": "File not found"}

    print(f"\nProcessing: {path.name}")
    print(f"  Path: {path}")

    # Read parquet
    df = pd.read_parquet(path)
    original_cols = list(df.columns)
    rows = len(df)

    print(f"  Rows: {rows:,}")
    print(f"  Columns: {original_cols}")

    # Check if already has the columns
    has_last_updated = 'last_updated' in df.columns
    has_status = 'status' in df.columns

    if has_last_updated and has_status:
        print(f"  Already has last_updated and status columns - skipping")
        return {
            "file": str(path),
            "status": "already_updated",
            "rows": rows
        }

    # Find the timestamp column
    ts_col = get_timestamp_column(path)

    # Check for alternative timestamp column names
    if ts_col not in df.columns:
        # Try common alternatives
        alternatives = ['time', 'date', 'datetime', 'event_date', 'ignition_date']
        for alt in alternatives:
            if alt in df.columns:
                ts_col = alt
                break

    if ts_col not in df.columns:
        print(f"  ERROR: No timestamp column found. Available: {list(df.columns)}")
        return {
            "file": str(path),
            "status": "error",
            "error": f"No timestamp column found"
        }

    print(f"  Timestamp column: {ts_col}")

    # Add last_updated column (= timestamp for historical data)
    if not has_last_updated:
        df['last_updated'] = df[ts_col]
        print(f"  Added: last_updated (copied from {ts_col})")

    # Add status column (= 'historical' for all existing data)
    if not has_status:
        df['status'] = 'historical'
        print(f"  Added: status = 'historical'")

    # Save
    if not dry_run:
        df.to_parquet(path, index=False)
        print(f"  Saved: {path}")
    else:
        print(f"  [DRY RUN] Would save: {path}")

    return {
        "file": str(path),
        "status": "updated",
        "rows": rows,
        "timestamp_col": ts_col,
        "added_last_updated": not has_last_updated,
        "added_status": not has_status
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Add temporal columns to event parquets")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    args = parser.parse_args()

    print("=" * 60)
    print("Adding temporal columns to event parquet files")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN MODE - no files will be modified]\n")

    results = []
    for filepath in EVENT_FILES:
        result = add_temporal_columns(filepath, dry_run=args.dry_run)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    updated = sum(1 for r in results if r.get("status") == "updated")
    skipped = sum(1 for r in results if r.get("status") == "already_updated")
    errors = sum(1 for r in results if r.get("status") == "error")
    not_found = sum(1 for r in results if r.get("status") == "not_found")

    print(f"  Updated: {updated}")
    print(f"  Already up-to-date: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Not found: {not_found}")

    if errors > 0:
        print("\nErrors:")
        for r in results:
            if r.get("status") == "error":
                print(f"  {r['file']}: {r.get('error')}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
