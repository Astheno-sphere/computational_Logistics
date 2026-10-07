"""Convert the frozen Wikispeedia graph and human endpoints to typed decisions.

Candidates are sampled from real outlinks before shortest-path labels are read.
Only article titles are model input; graph distances and human traces are audit
metadata. No Wikipedia article text or live API calls are needed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import random
import tarfile
from urllib.parse import unquote
from urllib.request import urlopen

from .data import SPLITS, _hash, _json, _write_dataset, split_group


VERSION = "wikispeedia-v1"
SOURCE_URL = "https://snap.stanford.edu/data/wikispeedia.html"
ARCHIVE_URL = "https://snap.stanford.edu/data/wikispeedia/wikispeedia_paths-and-graph.tar.gz"
ARCHIVE_SHA256 = "97697096f5d2dcb77aa69e3992305c6c561de89edb9fb10b5ad9feaf8ba534d5"
ARCHIVE_PREFIX = "wikispeedia_paths-and-graph/"
LICENSE_NOTE = "Source does not declare a separate graph/path license; citation requested."
SPLIT_POLICY = "target_group_sha256_v1_with_seeded_10_percent_goal_holdout"


def decode_title(value: str) -> str:
    return unquote(value).replace("_", " ")


def replay_human_path(tokens: list[str]) -> list[str]:
    """Return visited pages, including browser-back moves, using a page stack.

    A;B;<;C visits A,B,A,C. Removing '<' would invent a B-to-C edge.
    Tokens must already be split on ';' and URL-decoded.
    """
    stack, visited = [], []
    for token in tokens:
        if token == "<":
            if len(stack) < 2:
                raise ValueError("human path backs past its starting page")
            stack.pop()
        elif token:
            stack.append(token)
        else:
            raise ValueError("human path contains an empty article")
        visited.append(stack[-1])
    if not visited:
        raise ValueError("human path is empty")
    return visited


def load_wikispeedia(archive_path: str | Path) -> tuple[dict, list[dict], dict]:
    """Read only graph and finished paths; never retain player IDs or timestamps."""
    archive_path = Path(archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != ARCHIVE_SHA256:
        raise ValueError(f"Wikispeedia archive checksum mismatch: {digest}")
    stats = Counter()
    with tarfile.open(archive_path, "r:gz") as archive:
        def rows(name):
            handle = archive.extractfile(ARCHIVE_PREFIX + name)
            if handle is None:
                raise ValueError(f"archive is missing {name}")
            with handle:
                for raw in handle:
                    line = raw.decode("utf-8").rstrip("\r\n")
                    if line and not line.startswith("#"):
                        yield line.split("\t")

        graph = {decode_title(row[0]): set() for row in rows("articles.tsv")}
        for row in rows("links.tsv"):
            source, target = map(decode_title, row)
            if source not in graph or target not in graph:
                raise ValueError("graph edge refers to an unknown article")
            graph[source].add(target)
        graph = {source: sorted(links) for source, links in sorted(graph.items())}
        pairs = {}
        for index, row in enumerate(rows("paths_finished.tsv"), 1):
            stats["finished_human_paths"] += 1
            # The first three columns contain an identifier, timestamp and
            # duration. Only the fourth column (the path) is ever retained.
            tokens = [decode_title(token) for token in row[3].split(";")]
            visited = replay_human_path(tokens)
            stats["paths_with_browser_back"] += int("<" in tokens)
            stats["browser_back_actions"] += tokens.count("<")
            missing = [[a, b] for token, a, b in zip(tokens[1:], visited, visited[1:])
                       if token != "<" and b not in graph.get(a, ())]
            stats["paths_with_forward_edges_missing_from_graph"] += bool(missing)
            stats["forward_edges_missing_from_graph"] += len(missing)
            if any(page not in graph for page in visited):
                stats["paths_filtered_unknown_article"] += 1
                continue
            source, target = visited[0], visited[-1]
            pairs.setdefault((source, target), {
                "source": source, "target": target,
                "human_path": tokens, "human_replayed_path": visited,
                "human_forward_edges_missing_from_graph": missing,
                "original_id": f"paths_finished.tsv:record:{index}",
            })
    stats.update({"articles": len(graph), "directed_links": sum(map(len, graph.values())),
                  "distinct_human_source_target_pairs": len(pairs)})
    return graph, list(pairs.values()), dict(stats)


def reverse_graph(graph: dict[str, list[str]]) -> dict[str, list[str]]:
    reverse = {page: [] for page in graph}
    for source, links in graph.items():
        for target in links:
            reverse[target].append(source)
    return reverse


def _reverse_bfs(reverse: dict[str, list[str]], target: str) -> dict[str, int]:
    if target not in reverse:
        raise ValueError(f"unknown graph target: {target}")
    distances, queue = {target: 0}, deque([target])
    while queue:
        page = queue.popleft()
        for source in reverse[page]:
            if source not in distances:
                distances[source] = distances[page] + 1
                queue.append(source)
    return distances


def distances_to(graph: dict[str, list[str]], target: str) -> dict[str, int]:
    return _reverse_bfs(reverse_graph(graph), target)


def sample_candidates(outlinks: list[str], current: str, seed: int = 42,
                      max_candidates: int = 12) -> list[str]:
    """Sample without a goal, graph distances, expert path or human next action."""
    if max_candidates < 2:
        raise ValueError("max_candidates must be at least two")
    candidates = sorted(set(outlinks))
    random.Random(int(_hash([VERSION, seed, current, "candidates"]), 16)).shuffle(candidates)
    return candidates[:max_candidates]


def shortest_path(graph: dict[str, list[str]], source: str, target: str,
                  distances: dict[str, int]) -> list[str]:
    if source not in distances:
        raise ValueError("source cannot reach target")
    path = [source]
    while path[-1] != target:
        current = path[-1]
        path.append(min(page for page in graph[current]
                        if distances.get(page) == distances[current] - 1))
    return path


def records_from_graph(graph: dict[str, list[str]], human_pairs: list[dict], *,
                       targets: int = 300, pairs_per_target: int = 12,
                       max_candidates: int = 12, seed: int = 42,
                       input_sha256: str = ARCHIVE_SHA256) -> tuple[list[dict], list[dict], dict]:
    if targets < 1 or pairs_per_target < 1 or max_candidates < 2:
        raise ValueError("targets/pairs must be positive and max_candidates >= 2")
    by_target = defaultdict(dict)
    filtered = Counter()
    for pair in human_pairs:
        source, target = pair["source"], pair["target"]
        if source not in graph or target not in graph:
            filtered["unknown_endpoint"] += 1
        elif source == target:
            filtered["source_already_at_target"] += 1
        elif len(set(graph[source])) < 2:
            filtered["fewer_than_two_outlinks"] += 1
        else:
            by_target[target].setdefault(source, pair)
    chosen_targets = sorted(by_target)
    random.Random(int(_hash([VERSION, seed, "targets"]), 16)).shuffle(chosen_targets)
    chosen_targets = chosen_targets[:targets]
    # A second seeded draw selects a disjoint 10% goal holdout. This is not a
    # semantic-domain or unseen-node OOD claim; all goals inhabit the same graph.
    ood_order = sorted(chosen_targets)
    random.Random(int(_hash([VERSION, seed, "ood-targets"]), 16)).shuffle(ood_order)
    ood_targets = set(ood_order[:len(chosen_targets) // 10])
    reverse = reverse_graph(graph)
    records, workflows = [], []
    target_splits, selected_pairs, full_best_hits = {}, 0, Counter()
    attempted = Counter()
    for target in chosen_targets:
        group_id = f"{VERSION}:target:{_hash(target)[:24]}"
        split = "ood" if target in ood_targets else split_group(group_id, seed)
        target_splits[target] = split
        pairs = sorted(by_target[target].values(), key=lambda pair: pair["source"])
        random.Random(int(_hash([VERSION, seed, target, "pairs"]), 16)).shuffle(pairs)
        distances = _reverse_bfs(reverse, target)
        for pair in pairs[:pairs_per_target]:
            selected_pairs += 1
            attempted[split] += 1
            source = pair["source"]
            # No oracle information is passed to this function. In particular,
            # an optimal neighbor is never inserted if the sample misses it.
            candidates = sample_candidates(graph[source], source, seed, max_candidates)
            candidate_distances = [distances.get(page) for page in candidates]
            reachable = [distance for distance in candidate_distances if distance is not None]
            if not reachable:
                filtered["selected_pairs_all_candidates_unreachable"] += 1
                continue
            best = min(reachable)
            best_count = candidate_distances.count(best)
            full_best = min(distances[page] for page in graph[source] if page in distances)
            full_best_actions = [page for page in graph[source] if distances.get(page) == full_best]
            covers_full_best = best == full_best
            full_best_hits[split] += covers_full_best
            identifier = f"{VERSION}:pair:{_hash([source, target])[:24]}"
            provenance = {
                "type": "import", "input_sha256": input_sha256,
                "source_url": SOURCE_URL, "archive_url": ARCHIVE_URL,
                "original_id": pair["original_id"], "license": LICENSE_NOTE,
                "split_policy": SPLIT_POLICY, "seed": seed,
                "generator_version": VERSION,
            }
            records.append({
                "id": identifier, "group_id": group_id, "split": split,
                "source": VERSION, "kind": "choice",
                "state": {"current_page": source, "target_page": target,
                          "navigation": "Select one of the offered outgoing article links."},
                "question": "Which available link is the best next step toward the target article?",
                "options": candidates,
                "target": [1.0 / best_count if distance == best else 0.0
                           for distance in candidate_distances],
                "metadata": {
                    "family": "wikiracing", "case_name": "wikiracing",
                    "target_basis": "Uniform best available actions under full-graph shortest-path teacher; not human uncertainty or success probabilities.",
                    "candidate_distances": dict(zip(candidates, candidate_distances)),
                    "full_shortest_path_length": distances[source],
                    "best_candidate_path_length": best + 1,
                    "candidate_shortlist_excess_steps": best - full_best,
                    "full_best_actions": full_best_actions,
                    "shortlist_contains_full_best": covers_full_best,
                    "provenance": provenance,
                },
            })
            workflows.append({
                "id": identifier, "group_id": group_id, "split": split,
                "source": source, "target": target,
                "full_outlinks": graph[source], "candidates": candidates,
                "expert_path": shortest_path(graph, source, target, distances),
                "human_path": pair["human_path"],
                "human_replayed_path": pair["human_replayed_path"],
                "human_forward_edges_missing_from_graph": pair["human_forward_edges_missing_from_graph"],
                "original_id": pair["original_id"],
                "evaluation_status": "offline_gold_workflow_only_no_model_rollout",
            })
    split_counts = Counter(row["split"] for row in records)
    stats = {
        "eligible_targets": len(by_target), "requested_targets": targets,
        "selected_targets": len(chosen_targets), "selected_ood_targets": len(ood_targets),
        "selected_target_counts_by_split": dict(Counter(target_splits.values())),
        "emitted_target_counts_by_split": dict(Counter(
            target_splits[target] for target in sorted({row["state"]["target_page"] for row in records}))),
        "selected_human_pairs": selected_pairs,
        "selected_human_pairs_by_split": dict(attempted),
        "emitted_records": len(records), "filtered_counts": dict(filtered),
        "all_candidates_unreachable_filtered": filtered["selected_pairs_all_candidates_unreachable"],
        "full_best_coverage": {
            "covered": sum(full_best_hits.values()), "total": len(records),
            "fraction": sum(full_best_hits.values()) / len(records) if records else None,
            "by_split": {split: {"covered": full_best_hits[split], "total": split_counts[split],
                                 "fraction": full_best_hits[split] / split_counts[split] if split_counts[split] else None}
                         for split in SPLITS},
        },
        "target_split_assignments": dict(sorted(target_splits.items())),
    }
    return records, workflows, stats


def build_dataset(output_dir: str | Path, *, archive_path: str | Path | None = None,
                  targets: int = 300, pairs_per_target: int = 12,
                  max_candidates: int = 12, seed: int = 42) -> dict:
    output = Path(output_dir)
    archive_path = Path(archive_path) if archive_path is not None else output / "upstream" / "wikispeedia_paths-and-graph.tar.gz"
    if not archive_path.exists():
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(ARCHIVE_URL, timeout=60) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != ARCHIVE_SHA256:
            raise ValueError("downloaded Wikispeedia archive checksum mismatch")
        archive_path.write_bytes(content)
    graph, human_pairs, source_stats = load_wikispeedia(archive_path)
    records, workflows, task_stats = records_from_graph(
        graph, human_pairs, targets=targets, pairs_per_target=pairs_per_target,
        max_candidates=max_candidates, seed=seed)
    manifest = _write_dataset(records, output, {
        "type": "import", "generator_version": VERSION, "source_url": SOURCE_URL,
        "archive_url": ARCHIVE_URL, "input_sha256": ARCHIVE_SHA256,
        "license": LICENSE_NOTE, "targets": targets, "pairs_per_target": pairs_per_target,
        "max_candidates": max_candidates, "seed": seed, "split_policy": SPLIT_POLICY,
        "graph_scope": "Full frozen Wikispeedia graph, not the full live Wikipedia graph.",
        "model_input_scope": "Article titles only; privileged graph teacher for heuristic navigation.",
        "candidate_policy": "Seeded uniform subset of full outlinks independent of target and labels; no optimal-action insertion.",
        "citations": [
            "West and Leskovec. Human Wayfinding in Information Networks. WWW 2012.",
            "West, Pineau and Precup. Wikispeedia: An Online Game for Inferring Semantic Distances between Concepts. IJCAI 2009.",
        ],
    })
    (output / "graph.json").write_text(_json(graph) + "\n", encoding="utf-8")
    (output / "workflow_cases.jsonl").write_text(
        "".join(_json(row) + "\n" for row in workflows), encoding="utf-8")
    for name in ("graph.json", "workflow_cases.jsonl"):
        manifest["files_sha256"][name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    manifest["source_statistics"] = source_stats
    manifest["task_statistics"] = task_stats
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/wikiracing"))
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--targets", type=int, default=300)
    parser.add_argument("--pairs-per-target", type=int, default=12)
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    manifest = build_dataset(args.output_dir, archive_path=args.archive, targets=args.targets,
                             pairs_per_target=args.pairs_per_target,
                             max_candidates=args.max_candidates, seed=args.seed)
    report = {key: manifest[key] for key in ("summary", "source_statistics")}
    report["task_statistics"] = {key: value for key, value in manifest["task_statistics"].items()
                                 if key != "target_split_assignments"}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
