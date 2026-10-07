#!/usr/bin/env python3
"""
Generate summaries.md from reference files.
Creates structured summaries for quick resource discovery.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional

REFERENCES_DIR = Path(__file__).parent.parent / "references"
INDEX_PATH = REFERENCES_DIR / "index.yaml"


def load_index():
    """Load the index.yaml file."""
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def is_404_file(content: str) -> bool:
    """Check if file is a 404 placeholder."""
    return "# 404" in content or "File Not Found" in content[:200]


def extract_key_content(content: str, content_type: str) -> tuple:
    """Extract key paragraphs and create a concise summary."""
    lines = content.split('\n')

    # Skip header (title, author, type, url, ---)
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            start_idx = i + 1
            break

    # Skip table of contents if present
    body_lines = lines[start_idx:]
    content_start = 0
    for i, line in enumerate(body_lines):
        if line.strip().startswith('# ') and i > 0:
            content_start = i
            break
        if 'Table of Contents' in line or '[**Table of Contents**]' in line:
            for j in range(i, len(body_lines)):
                if body_lines[j].strip().startswith('# ') or body_lines[j].strip().startswith('## '):
                    if 'Table of Contents' not in body_lines[j]:
                        content_start = j
                        break
            break

    body_text = '\n'.join(body_lines[content_start:])

    # Extract first meaningful paragraph (the "thesis" or introduction)
    paragraphs = []
    current_para = []
    char_count = 0

    for line in body_text.split('\n'):
        line = line.strip()
        if not line:
            if current_para:
                para_text = ' '.join(current_para)
                # Skip very short lines or headings
                if len(para_text) > 50 and not para_text.startswith('#'):
                    paragraphs.append(para_text)
                    char_count += len(para_text)
                current_para = []
            if char_count > 600:
                break
        elif not line.startswith('[') and not line.startswith('**Table') and not line.startswith('YouTube'):
            current_para.append(line)

    if current_para and char_count < 600:
        para_text = ' '.join(current_para)
        if len(para_text) > 50:
            paragraphs.append(para_text)

    # Create a concise summary from first 1-2 paragraphs
    summary_text = ' '.join(paragraphs[:2])
    # Truncate to ~300 chars for the summary
    if len(summary_text) > 350:
        summary_text = summary_text[:347] + '...'

    return summary_text, paragraphs


def extract_topics_from_content(content: str) -> list:
    """Extract likely topics from headings in the content."""
    headings = re.findall(r'^###?\s+\*?\*?([^*\n]+)', content, re.MULTILINE)
    # Clean up headings
    topics = []
    for h in headings[:10]:
        h = h.strip().strip('*').strip()
        if h and len(h) < 50 and 'Table of Contents' not in h:
            topics.append(h)
    return topics


def generate_summary_entry(resource: dict, content: str) -> str:
    """Generate a summary entry for a resource."""
    if is_404_file(content):
        return None

    code = resource['code']
    title = resource['title']
    author = resource['author']
    content_type = resource['type'].title()
    topics = resource['topics']
    stages = resource['founder_stage']

    summary_text, _ = extract_key_content(content, resource['type'])
    content_topics = extract_topics_from_content(content)

    # Format stages nicely
    stage_display = ', '.join(stages) if stages != ['all'] else 'all stages'

    # Create compact summary entry
    entry = f"""## {code} - {title}
**Author:** {author} | **Type:** {content_type} | **Stage:** {stage_display}
**Topics:** {', '.join(topics)}

{summary_text}

**Sections:** {', '.join(content_topics[:5]) if content_topics else 'General discussion'}

---
"""
    return entry


def generate_summaries():
    """Generate the complete summaries.md file."""
    index = load_index()

    summaries = []
    skipped = 0

    for resource in index['resources']:
        filepath = REFERENCES_DIR / resource['file']
        if not filepath.exists():
            skipped += 1
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        summary = generate_summary_entry(resource, content)
        if summary:
            summaries.append(summary)
        else:
            skipped += 1

    # Create header
    header = """# YC Advisor Resource Summaries

This file contains summaries of all YC library resources for quick discovery.

**Usage:** Scan these summaries to identify relevant resources, then load the FULL content of selected resources before answering.

**Important:** Never answer questions using only these summaries. Always load the complete source files.

---

"""

    output = header + '\n'.join(summaries)

    output_path = REFERENCES_DIR / "summaries.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"Generated summaries.md with {len(summaries)} summaries")
    print(f"Skipped {skipped} files (404s or missing)")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    generate_summaries()
