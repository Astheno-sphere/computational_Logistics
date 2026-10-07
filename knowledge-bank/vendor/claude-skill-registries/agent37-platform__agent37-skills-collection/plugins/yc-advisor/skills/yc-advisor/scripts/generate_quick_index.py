#!/usr/bin/env python3
"""
Generate quick-index.md for lightweight discovery and add file sizes to index.yaml.

This script:
1. Reads each reference file and counts lines
2. Updates index.yaml with `lines` field for each resource
3. Generates quick-index.md (~500 lines) with essential discovery info
"""

import yaml
from pathlib import Path

REFERENCES_DIR = Path(__file__).parent.parent / "references"
INDEX_PATH = REFERENCES_DIR / "index.yaml"
QUICK_INDEX_PATH = REFERENCES_DIR / "quick-index.md"


def load_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_index(index):
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(index, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)


def count_lines(file_path):
    """Count lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def add_file_sizes(index):
    """Add line counts to each resource in index."""
    updated = 0
    for resource in index['resources']:
        file_path = REFERENCES_DIR / resource['file']
        lines = count_lines(file_path)
        resource['lines'] = lines
        updated += 1
    return updated


def generate_quick_index(index):
    """Generate a lightweight quick-index.md for discovery."""
    lines = [
        "# YC Library Quick Index",
        "",
        "Lightweight discovery index for routing queries to full resources.",
        "**Do not answer from this index** - always load full source files.",
        "",
        "## Resources",
        "",
    ]

    # Group by topic for easier scanning
    topic_groups = {}
    for resource in index['resources']:
        # Skip 404 pages
        if "File Not Found" in resource.get('title', ''):
            continue

        primary_topic = resource.get('topics', ['general'])[0]
        if primary_topic not in topic_groups:
            topic_groups[primary_topic] = []
        topic_groups[primary_topic].append(resource)

    # Sort topics alphabetically
    for topic in sorted(topic_groups.keys()):
        resources = topic_groups[topic]
        lines.append(f"### {topic.replace('-', ' ').title()}")
        lines.append("")

        for r in sorted(resources, key=lambda x: x.get('title', '')):
            code = r['code']
            title = r.get('title', 'Unknown')
            author = r.get('author', 'Unknown')
            rtype = r.get('type', 'essay')
            line_count = r.get('lines', 0)
            topics = ', '.join(r.get('topics', []))
            stages = ', '.join(r.get('founder_stage', []))

            # Compact format: code | title | author | type | lines | stages
            lines.append(f"- **{code}** | {title} | {author} | {rtype} | {line_count}L | {stages}")

        lines.append("")

    return '\n'.join(lines)


def main():
    print("Loading index.yaml...")
    index = load_index()

    print("Adding file sizes to index...")
    updated = add_file_sizes(index)
    print(f"  Updated {updated} resources with line counts")

    print("Saving updated index.yaml...")
    save_index(index)

    print("Generating quick-index.md...")
    quick_index_content = generate_quick_index(index)

    with open(QUICK_INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(quick_index_content)

    # Count lines in quick-index
    quick_index_lines = quick_index_content.count('\n') + 1
    print(f"  Generated quick-index.md with {quick_index_lines} lines")

    print(f"\nOutput files:")
    print(f"  - {INDEX_PATH} (updated with line counts)")
    print(f"  - {QUICK_INDEX_PATH} (new lightweight index)")


if __name__ == "__main__":
    main()
