#!/usr/bin/env python3
"""
Generate index.yaml from reference files.
Parses all .md files in references/ and extracts metadata.
"""

import os
import re
import yaml
from pathlib import Path

REFERENCES_DIR = Path(__file__).parent.parent / "references"

# Topic mappings based on SKILL.md categories
# Maps keywords in filename/title to topic tags
TOPIC_KEYWORDS = {
    "co-founder": ["co-founders", "team"],
    "cofounder": ["co-founders", "team"],
    "equity": ["co-founders", "hiring", "compensation"],
    "idea": ["ideas", "getting-started"],
    "startup-idea": ["ideas", "getting-started"],
    "before-the-startup": ["getting-started", "mindset"],
    "student": ["getting-started", "students"],
    "mvp": ["product", "building"],
    "product": ["product", "building"],
    "product-market-fit": ["product", "pmf"],
    "design": ["product", "design"],
    "fundrais": ["fundraising"],
    "investor": ["fundraising", "investors"],
    "seed": ["fundraising", "seed-stage"],
    "series-a": ["fundraising", "series-a"],
    "safe": ["fundraising", "legal"],
    "pitch": ["pitching", "fundraising"],
    "deck": ["pitching", "fundraising"],
    "growth": ["growth", "metrics"],
    "metric": ["metrics", "growth"],
    "kpi": ["metrics"],
    "analytics": ["metrics"],
    "conversion": ["growth", "metrics"],
    "retention": ["growth", "metrics"],
    "user": ["customers", "users"],
    "customer": ["customers", "sales"],
    "talk": ["customers", "user-research"],
    "sales": ["sales", "customers"],
    "pricing": ["sales", "pricing"],
    "enterprise": ["sales", "b2b"],
    "hire": ["hiring", "team"],
    "engineer": ["hiring", "engineering"],
    "team": ["hiring", "team"],
    "employee": ["hiring", "team"],
    "culture": ["culture", "leadership"],
    "ceo": ["leadership", "culture"],
    "leader": ["leadership"],
    "board": ["leadership", "governance"],
    "mistake": ["mistakes", "avoiding-failure"],
    "fail": ["mistakes", "avoiding-failure"],
    "kill": ["mistakes", "avoiding-failure"],
    "runway": ["finance", "mistakes"],
    "money": ["finance", "fundraising"],
    "pivot": ["pivoting", "strategy"],
    "launch": ["launching", "growth"],
    "press": ["launching", "marketing"],
    "scale": ["scaling", "growth"],
    "later-stage": ["scaling"],
    "unicorn": ["scaling", "success"],
    "mindset": ["mindset", "philosophy"],
    "resourceful": ["mindset"],
    "rejection": ["mindset"],
    "setback": ["mindset"],
    "goal": ["mindset", "productivity"],
    "ai": ["ai", "technology"],
    "artificial-intelligence": ["ai", "technology"],
    "llm": ["ai", "technology"],
    "gpt": ["ai", "technology"],
    "vibe-coding": ["ai", "development"],
    "agent": ["ai", "technology"],
    "airbnb": ["case-study", "founder-interview"],
    "stripe": ["case-study", "founder-interview"],
    "coinbase": ["case-study", "founder-interview"],
    "reddit": ["case-study", "founder-interview"],
    "twitch": ["case-study", "founder-interview"],
    "doordash": ["case-study", "founder-interview"],
    "paul-graham": ["founder-interview", "yc"],
    "garry-tan": ["founder-interview", "yc"],
    "elon-musk": ["founder-interview", "tech-leaders"],
    "sam-altman": ["founder-interview", "tech-leaders"],
    "mark-zuckerberg": ["founder-interview", "tech-leaders"],
    "hardware": ["hardware", "deep-tech"],
    "biotech": ["biotech", "deep-tech"],
    "hard-tech": ["hardware", "deep-tech"],
    "dev-tool": ["dev-tools", "b2b"],
    "crypto": ["crypto", "fintech"],
    "fintech": ["fintech"],
    "yc": ["yc", "accelerator"],
    "y-combinator": ["yc", "accelerator"],
    "application": ["yc", "applying"],
    "legal": ["legal", "admin"],
    "mechanic": ["legal", "admin"],
    "join": ["joining-startup", "career"],
    "work-at": ["joining-startup", "career"],
}

# Founder stage mappings
STAGE_KEYWORDS = {
    "pre-idea": ["before-the-startup", "should-i-start", "student"],
    "idea": ["idea", "startup-idea", "get-startup-ideas"],
    "building": ["mvp", "product", "build", "design"],
    "launched": ["launch", "first-customer", "user", "sales", "growth"],
    "scaling": ["scale", "hire", "later-stage", "unicorn", "series-a", "team"],
}


def extract_code_from_filename(filename: str) -> str:
    """Extract the code prefix from filename (e.g., '8z' from '8z-how-to-get-startup-ideas.md')"""
    match = re.match(r'^([A-Za-z0-9]+)-', filename)
    return match.group(1) if match else ""


def parse_reference_file(filepath: Path) -> dict:
    """Parse a reference file and extract metadata."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    # Extract title (first line, remove # prefix)
    title = lines[0].replace('# ', '').strip() if lines else ""

    # Extract author
    author = ""
    for line in lines[:10]:
        if line.startswith('**Author:**'):
            author = line.replace('**Author:**', '').strip()
            break

    # Extract type
    content_type = ""
    for line in lines[:10]:
        if line.startswith('**Type:**'):
            content_type = line.replace('**Type:**', '').strip().lower()
            break

    # Extract URL
    url = ""
    for line in lines[:10]:
        if line.startswith('**URL:**'):
            url = line.replace('**URL:**', '').strip()
            break

    # Extract YouTube ID (for video content)
    youtube_id = ""
    for line in lines[:15]:
        if line.startswith('**YouTube ID:**'):
            youtube_id = line.replace('**YouTube ID:**', '').strip()
            break

    filename = filepath.name
    code = extract_code_from_filename(filename)

    # Determine topics based on filename and title
    topics = set()
    search_text = (filename + " " + title).lower()
    for keyword, tags in TOPIC_KEYWORDS.items():
        if keyword in search_text:
            topics.update(tags)

    # Default topic if none found
    if not topics:
        topics.add("general")

    # Determine founder stages
    stages = set()
    for stage, keywords in STAGE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in search_text:
                stages.add(stage)
                break

    # Default stage if none found
    if not stages:
        stages.add("all")

    resource = {
        "code": code,
        "file": filename,
        "title": title,
        "author": author,
        "type": content_type,
        "url": url,
        "topics": sorted(list(topics)),
        "founder_stage": sorted(list(stages)),
        "related": []  # Will be filled in later phase
    }

    # Only include youtube_id if present
    if youtube_id:
        resource["youtube_id"] = youtube_id

    return resource


def generate_index():
    """Generate the complete index from all reference files."""
    resources = []

    # Index files to skip
    skip_files = {"index.yaml", "summaries.md", "quick-index.md", "learning-paths.md"}

    for filepath in sorted(REFERENCES_DIR.glob("*.md")):
        if filepath.name in skip_files:
            continue

        try:
            resource = parse_reference_file(filepath)
            resources.append(resource)
        except Exception as e:
            print(f"Error parsing {filepath.name}: {e}")

    index = {
        "version": "1.0",
        "total_resources": len(resources),
        "resources": resources
    }

    return index


def main():
    index = generate_index()

    output_path = REFERENCES_DIR / "index.yaml"
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(index, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)

    print(f"Generated index.yaml with {index['total_resources']} resources")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
