#!/usr/bin/env python3
"""
Add cross-references to index.yaml based on topic similarity.
"""

import yaml
from pathlib import Path
from collections import defaultdict

REFERENCES_DIR = Path(__file__).parent.parent / "references"
INDEX_PATH = REFERENCES_DIR / "index.yaml"


def load_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_index(index):
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(index, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)


def compute_similarity(topics1, topics2):
    """Compute Jaccard similarity between two topic sets."""
    set1 = set(topics1)
    set2 = set(topics2)
    if not set1 or not set2:
        return 0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0


def find_related_resources(resources, target_idx, top_n=5):
    """Find the most related resources for a given resource."""
    target = resources[target_idx]
    target_topics = set(target.get('topics', []))
    target_stages = set(target.get('founder_stage', []))
    target_code = target['code']

    scores = []
    for i, resource in enumerate(resources):
        if i == target_idx:
            continue

        resource_topics = set(resource.get('topics', []))
        resource_stages = set(resource.get('founder_stage', []))

        # Topic similarity (weighted more heavily)
        topic_sim = compute_similarity(target_topics, resource_topics)

        # Stage similarity
        stage_sim = compute_similarity(target_stages, resource_stages)

        # Combined score
        score = (topic_sim * 0.7) + (stage_sim * 0.3)

        if score > 0.1:  # Minimum threshold
            scores.append((resource['code'], score))

    # Sort by score and take top N
    scores.sort(key=lambda x: x[1], reverse=True)
    return [code for code, _ in scores[:top_n]]


def add_cross_references():
    index = load_index()
    resources = index['resources']

    updated = 0
    for i, resource in enumerate(resources):
        related = find_related_resources(resources, i, top_n=5)
        if related:
            resource['related'] = related
            updated += 1

    save_index(index)
    print(f"Added cross-references to {updated} resources")
    print(f"Output: {INDEX_PATH}")


if __name__ == "__main__":
    add_cross_references()
