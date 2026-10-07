#!/usr/bin/env python3
"""
Merge YC library resources from new scrape into current skill.

Strategy:
- Overlapping files (392): Replace with new content (has YouTube IDs, cleaner format)
- Current-only files (48): Keep as-is (includes frameworks we created)
- New-only files (9): Add to references (excluding _README.md and KI-test.md)

Format normalization:
- **Source:** -> **URL:**
- **Type:** blog -> **Type:** Essay
- **Type:** video -> **Type:** Video
- Keep **YouTube ID:** field (new)
- Remove **Categories:** field (not used)
"""

import re
import shutil
from pathlib import Path
from datetime import datetime

# Paths
CURRENT_DIR = Path(__file__).parent.parent / "references"
NEW_DIR = Path("/Users/vkrishnaprasad/Downloads/yc_library_final")
BACKUP_DIR = Path(__file__).parent.parent / "references_backup"

# Files to exclude from new scrape
EXCLUDE_NEW = {"_README.md", "KI-test.md"}

# Index files in current that should not be touched
INDEX_FILES = {
    "index.yaml", "summaries.md", "quick-index.md", "learning-paths.md"
}


def normalize_format(content: str) -> str:
    """
    Convert new scrape format to match current skill format.

    Changes:
    - **Source:** -> **URL:**
    - **Type:** blog -> **Type:** Essay
    - **Type:** video -> **Type:** Video
    - Remove **Categories:** line
    """
    lines = content.split('\n')
    new_lines = []

    for line in lines:
        # Replace Source with URL
        if line.startswith('**Source:**'):
            line = line.replace('**Source:**', '**URL:**')
        # Normalize type capitalization
        elif line.startswith('**Type:**'):
            if 'blog' in line.lower():
                line = '**Type:** Essay'
            elif 'video' in line.lower():
                line = '**Type:** Video'
        # Skip Categories line (not used in current format)
        elif line.startswith('**Categories:**'):
            continue
        new_lines.append(line)

    return '\n'.join(new_lines)


def get_file_sets():
    """Get sets of filenames in each directory."""
    # Current files (excluding index files and frameworks directory)
    current_files = set()
    for f in CURRENT_DIR.glob("*.md"):
        if f.name not in INDEX_FILES:
            current_files.add(f.name)

    # Also check frameworks directory
    frameworks_dir = CURRENT_DIR / "frameworks"
    framework_files = set()
    if frameworks_dir.exists():
        for f in frameworks_dir.glob("*.md"):
            framework_files.add(f"frameworks/{f.name}")

    # New scrape files
    new_files = {f.name for f in NEW_DIR.glob("*.md")}

    # Calculate sets
    overlap = current_files & new_files
    current_only = current_files - new_files
    new_only = new_files - current_files - EXCLUDE_NEW

    return overlap, current_only, new_only, framework_files


def create_backup():
    """Create a timestamped backup of the current references directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR.parent / f"references_backup_{timestamp}"

    print(f"Creating backup at {backup_path}...")
    shutil.copytree(CURRENT_DIR, backup_path)
    print(f"  Backup created successfully")

    return backup_path


def merge_resources(dry_run: bool = False):
    """
    Merge resources from new scrape into current skill.

    Args:
        dry_run: If True, only report what would be done without making changes
    """
    overlap, current_only, new_only, framework_files = get_file_sets()

    print(f"\n{'='*60}")
    print("YC Advisor Resource Merge")
    print(f"{'='*60}")
    print(f"\nFile counts:")
    print(f"  Overlapping files: {len(overlap)}")
    print(f"  Current-only files: {len(current_only)}")
    print(f"  New-only files: {len(new_only)}")
    print(f"  Framework files: {len(framework_files)} (untouched)")

    if dry_run:
        print("\n[DRY RUN - No changes will be made]")
    else:
        # Create backup before making changes
        backup_path = create_backup()

    stats = {"replaced": 0, "kept": 0, "added": 0, "errors": []}

    # 1. Replace overlapping files with new content
    print(f"\n1. Processing {len(overlap)} overlapping files...")
    for filename in sorted(overlap):
        try:
            new_content = (NEW_DIR / filename).read_text(encoding='utf-8')
            normalized = normalize_format(new_content)

            if not dry_run:
                (CURRENT_DIR / filename).write_text(normalized, encoding='utf-8')
            stats["replaced"] += 1

        except Exception as e:
            stats["errors"].append((filename, str(e)))
            print(f"  ERROR: {filename}: {e}")

    print(f"  Replaced {stats['replaced']} files")

    # 2. Current-only files: no action needed
    print(f"\n2. Keeping {len(current_only)} current-only files...")
    stats["kept"] = len(current_only)

    if current_only:
        print("  Current-only files:")
        for filename in sorted(current_only):
            print(f"    - {filename}")

    # 3. Add new-only files
    print(f"\n3. Adding {len(new_only)} new files...")
    for filename in sorted(new_only):
        try:
            new_content = (NEW_DIR / filename).read_text(encoding='utf-8')
            normalized = normalize_format(new_content)

            if not dry_run:
                (CURRENT_DIR / filename).write_text(normalized, encoding='utf-8')
            stats["added"] += 1
            print(f"  + {filename}")

        except Exception as e:
            stats["errors"].append((filename, str(e)))
            print(f"  ERROR: {filename}: {e}")

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  Replaced: {stats['replaced']}")
    print(f"  Kept: {stats['kept']}")
    print(f"  Added: {stats['added']}")
    print(f"  Total: {stats['replaced'] + stats['kept'] + stats['added'] + len(framework_files)}")

    if stats["errors"]:
        print(f"\n  Errors: {len(stats['errors'])}")
        for filename, error in stats["errors"]:
            print(f"    - {filename}: {error}")

    if not dry_run:
        print(f"\n  Backup saved to: {backup_path}")

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Merge YC library resources")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be done without making changes")
    args = parser.parse_args()

    merge_resources(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
