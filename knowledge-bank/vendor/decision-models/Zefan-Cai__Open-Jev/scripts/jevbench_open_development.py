"""Frozen public development checks using the documented JevBench v1.5 rules.

The pinned public source exposes 231 of the 601 documented published-open
items. This checks a deterministic 64/128-item subset, not the official 904-item
open set, a sealed evaluation, or a new blind test. Keep inputs and raw outputs
private. Benchmark prompts and gold are never used for synthetic training.
"""
import argparse
from collections import Counter, defaultdict
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from scripts import jevbench_openjev as legacy


UPSTREAM_COMMIT = "bb05a335bc809e61b20c0f745d25499a82b326fc"
METHOD_FILES = {
    "docs/METHOD-v1.5.md": "c25d3d8b8512e4d93370a9e0c99705d19b2a9389956ca33b8a4bd2b0ec501c07",
    "docs/METHOD-v1.5-ADDENDUM-HEADLINE-A-EQUAL-TYPES.md": "752ddccc4e191c81412631ee3121563421c4b9077cb6c3f2243ed1d1545cfab0",
}
PRIORITY_FAMILIES = ("temporal_numeric", "long_policy", "probability", "ambiguous", "judge_hard", "multi_hop")
TIER_WEIGHTS = {"easy": .10, "standard": .20, "judge": .30, "hard": .40}
SEED = "openjev-v15-public-development-20261002"
SCOPE = ("Public development evidence: a fixed subset of the 231 accessible public JevBench items, "
         "scored with documented v1.5 Noul/Score rules. The method reports 601 published-open and "
         "904 total open items. The additional 370 published-open items are absent from this pinned "
         "source. These public items have informed development; this is not a blind or sealed "
         "evaluation, the official I_open, or a leaderboard composite.")


def load_upstream(path):
    path = Path(path).resolve()
    commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    if commit != UPSTREAM_COMMIT or dirty:
        raise ValueError("A clean checkout of the pinned public source is required")
    for name, expected in METHOD_FILES.items():
        if legacy.sha256((path / name).read_bytes()) != expected:
            raise ValueError("Frozen v1.5 method checksum differs")
    for name, module in list(sys.modules.items()):
        if name == "jevbench" or name.startswith("jevbench."):
            if not Path(module.__file__).resolve().is_relative_to(path):
                raise ValueError("A different JevBench source is already imported")
    sys.path.insert(0, str(path))
    try:
        modules = {name: importlib.import_module("jevbench." + name)
                   for name in ("tasks", "scoring", "adapters.base")}
    finally:
        sys.path.pop(0)
    tasks, tiers = [], {}
    for name, (count, expected) in legacy.PUBLIC_FILES.items():
        source = path / "datasets/public" / (name + ".jsonl")
        if legacy.sha256(source.read_bytes()) != expected:
            raise ValueError("Public task checksum differs")
        rows = modules["tasks"].load_jsonl(str(source))
        if len(rows) != count or any(t.split != "public" or t.expected is None for t in rows):
            raise ValueError("Public task count, split or scoring coverage differs")
        for task in rows:
            tiers[task.id] = "standard" if name == "original" else name
        tasks.extend(rows)
    if len({t.id for t in tasks}) != len(tasks):
        raise ValueError("Duplicate public task IDs")
    return SimpleNamespace(tasks=tasks, tiers=tiers, base=modules["adapters.base"],
                           scoring=modules["scoring"], task_module=modules["tasks"])


def select_tasks(upstream, size):
    """Equal priority/coverage quotas; selection reads only ID/family/type/tier."""
    if size not in (64, 128):
        raise ValueError("Development sample size must be 64 or 128")
    buckets = [defaultdict(list), defaultdict(list)]
    for task in upstream.tasks:
        priority = 0 if task.family in PRIORITY_FAMILIES else 1
        key = (upstream.tiers[task.id], task.question["type"], task.family)
        buckets[priority][key].append(task)
    pools = []
    for strata in buckets:
        for group in strata.values():
            group.sort(key=lambda t: legacy.digest([SEED, t.id]))
        pool = []
        while any(strata.values()):
            for key in sorted(strata):
                if strata[key]:
                    pool.append(strata[key].pop(0))
        pools.append(pool)
    if any(len(pool) < size // 2 for pool in pools):
        raise ValueError("Not enough tasks for the fixed priority/coverage quotas")
    return [task for pair in zip(*(pool[:size // 2] for pool in pools)) for task in pair]


def prepared(upstream, size):
    selected = select_tasks(upstream, size)
    document = legacy.request_document(SimpleNamespace(tasks=selected, base=upstream.base))
    raw = legacy.json_bytes(document)
    manifest = {"schema_version": 1, "scope": SCOPE, "protocol": "documented_jevbench_v1.5_public_development",
                "upstream_commit": UPSTREAM_COMMIT, "method_files_sha256": METHOD_FILES,
                "public_files": {name: {"rows": n, "sha256": sha} for name, (n, sha) in legacy.PUBLIC_FILES.items()},
                "accessible_public_items": 231, "documented_published_open_items": 601,
                "official_open_items": 904, "sealed_items_read": 0,
                "sampling": {"seed": SEED, "priority_families": list(PRIORITY_FAMILIES),
                             "priority_quota": size // 2, "coverage_quota": size // 2,
                             "strata": "file tier, request type, family; ascending SHA256(seed, ID) within strata",
                             "priority_basis": "Historical aggregate error families, not individual gold or pilot predictions",
                             "development_feedback": "Historical 231-task public reports already informed original controls"},
                "selected_ids": [t.id for t in selected], "planned_requests": size,
                "selected_by_kind": dict(Counter(t.question["type"] for t in selected)),
                "selected_by_family": dict(Counter(t.family for t in selected)),
                "selected_by_tier": dict(Counter(upstream.tiers[t.id] for t in selected)),
                "requests_sha256": legacy.sha256(raw), "gold_in_requests": False,
                "license_note": "Do not redistribute task text, gold or raw responses; upstream MIT covers the harness and 72 original items only."}
    return selected, raw, manifest


def prepare(upstream_path, output, size=64):
    _, raw, manifest = prepared(load_upstream(upstream_path), size)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "requests.json").write_bytes(raw)
    (output / "manifest.json").write_bytes(legacy.json_bytes(manifest))
    return manifest


def verify_preparation(upstream, directory):
    directory = Path(directory)
    saved = legacy.strict_json((directory / "manifest.json").read_bytes())
    tasks, raw, manifest = prepared(upstream, saved["planned_requests"])
    if saved != manifest or (directory / "requests.json").read_bytes() != raw:
        raise ValueError("Frozen public development input or selection changed")
    return tasks, raw, manifest


def collect(upstream_path, prepared_dir, endpoint, identity, output, timeout=120, max_seconds=1800):
    _, _, manifest = verify_preparation(load_upstream(upstream_path), prepared_dir)
    report = legacy.collect(Path(prepared_dir) / "requests.json", manifest["requests_sha256"],
                            endpoint, identity, output, timeout=timeout, max_seconds=max_seconds,
                            scope=SCOPE, upstream_commit=UPSTREAM_COMMIT)
    (Path(output) / "development-manifest.json").write_bytes(legacy.json_bytes(manifest))
    return report


def score(task, probs, upstream):
    """Reuse upstream validation/ties, replacing legacy Noul/Score decisions."""
    validated = upstream.scoring.score_task(probs or {}, task)
    kind = task.question["type"]
    result = {"kind": kind, "valid": validated["valid"], "correct": False,
              "abstained": False, "normalized_mae": None, "chance_mae": None}
    if kind == "score":
        k, gold = len(task.labels), int(task.expected)
        if k < 2 or task.labels != [str(i) for i in range(k)]:
            raise ValueError("Score levels must be contiguous native positions")
        result["chance_mae"] = sum(abs(level - gold) / (k - 1) for level in range(k)) / k
    if not validated["valid"]:
        return result
    clean = validated["probs"]
    if kind == "noul":
        p = clean["yes"]
        prediction = "no" if p <= .2 else "yes" if p >= .8 else None
        result.update(correct=prediction == task.expected, abstained=prediction is None)
    elif kind == "score":
        prediction = sum(int(label) * value for label, value in clean.items())
        result["normalized_mae"] = abs(prediction - gold) / (len(task.labels) - 1)
        result["correct"] = validated["correct"]  # Explicit auxiliary argmax diagnostic.
    else:
        result["correct"] = validated["correct"]
    return result


def metrics(rows):
    kinds = {r["kind"] for r in rows}
    if len(kinds) != 1 or not rows:
        raise ValueError("Metrics require one nonempty request type")
    kind = rows[0]["kind"]
    out = {"n": len(rows), "invalid": sum(not r["valid"] for r in rows),
           "n_correct": sum(r["correct"] for r in rows),
           "accuracy": sum(r["correct"] for r in rows) / len(rows)}
    if kind == "score":
        values = [r["normalized_mae"] for r in rows if r["normalized_mae"] is not None]
        out.update(argmax_accuracy_auxiliary=out.pop("accuracy"),
                   n_argmax_correct_auxiliary=out.pop("n_correct"),
                   mean_normalized_mae=sum(values) / len(values) if values else None,
                   mean_chance_mae=sum(r["chance_mae"] for r in rows) / len(rows),
                   competence=None)
        # The public method does not specify the numeric MAE assigned to a
        # malformed Score. Do not invent it or exclude failures from a CC claim.
        if not out["invalid"]:
            out["competence"] = 100 * (1 - out["mean_normalized_mae"] / out["mean_chance_mae"])
    else:
        chance = .5 if kind == "noul" else sum(r["chance"] for r in rows) / len(rows)
        out.update(mean_chance=chance, competence=100 * (out["accuracy"] - chance) / (1 - chance))
        if kind == "noul":
            out.update(abstentions=sum(r["abstained"] for r in rows),
                       coverage=sum(r["valid"] and not r["abstained"] for r in rows) / len(rows))
    return out


def summarize(upstream_path, run_dir):
    upstream = load_upstream(upstream_path)
    run_dir = Path(run_dir)
    manifest = legacy.strict_json((run_dir / "development-manifest.json").read_bytes())
    tasks, raw, expected_manifest = prepared(upstream, manifest["planned_requests"])
    if manifest != expected_manifest or (run_dir / "requests.json").read_bytes() != raw:
        raise ValueError("Run input differs from the frozen public selection")
    report = legacy.strict_json((run_dir / "report.json").read_bytes())
    identity = report["expected_identity"]
    legacy.validate_identity_config(identity)
    samples = [legacy.strict_json(line) for line in (run_dir / "samples.jsonl").read_bytes().splitlines()]
    journal = [legacy.strict_json(line) for line in (run_dir / "attempts.jsonl").read_bytes().splitlines()]
    workloads = legacy.strict_json(raw)["workloads"]
    ids = manifest["selected_ids"]
    if (report["input_sha256"] != manifest["requests_sha256"] or report["upstream_commit"] != UPSTREAM_COMMIT
            or report["scope"] != SCOPE or report["prefix_cache"] is not False
            or [s["request_id"] for s in samples] != ids[:len(samples)]
            or [s["request_id"] for s in journal] != ids[:len(journal)]
            or not len(samples) <= len(journal) <= len(samples) + 1):
        raise ValueError("Run report or attempted task prefix differs")
    if report["status"] != "complete" or len(samples) != len(tasks) or len(journal) != len(tasks):
        raise ValueError("A complete failure-free run is required for development comparison")
    counts = {"planned_requests": len(tasks), "started_requests": len(tasks), "attempted_requests": len(tasks),
              "successful_requests": len(tasks), "failed_requests": 0, "pending_requests": 0, "in_flight_requests": 0}
    if any(type(report.get(k)) is not int or report[k] != v for k, v in counts.items()):
        raise ValueError("Run counts differ from durable evidence")
    rows = []
    for task, workload, sample, entry in zip(tasks, workloads, samples, journal):
        if (entry["event"] != "attempt_started" or entry["request_sha256"] != workload["request_sha256"]
                or sample["request_sha256"] != workload["request_sha256"] or sample.get("success") is not True
                or sample.get("fatal") or sample.get("probs_source") != "native"
                or sample.get("model") != identity["model"] or sample["http_status"] != 200):
            raise ValueError("Durable sample differs from frozen task or identity")
        response_raw = sample["raw_response"].encode()
        response = legacy.strict_json(response_raw)
        probs = legacy.native_probs(workload["request"], response, identity)
        if (legacy.sha256(response_raw) != sample["raw_response_sha256"]
                or response != sample["response"] or probs != sample["probs_as_returned"]):
            raise ValueError("Response evidence or probabilities changed")
        row = score(task, probs, upstream)
        row.update(tier=upstream.tiers[task.id], family=task.family, chance=1 / len(task.labels))
        rows.append(row)
    per_type = {}
    for kind in sorted({r["kind"] for r in rows}):
        selected = [r for r in rows if r["kind"] == kind]
        tiers = {tier: metrics([r for r in selected if r["tier"] == tier])
                 for tier in TIER_WEIGHTS if any(r["tier"] == tier for r in selected)}
        competence = None if any(t["competence"] is None for t in tiers.values()) else sum(
            TIER_WEIGHTS[tier] * m["competence"] for tier, m in tiers.items()) / sum(TIER_WEIGHTS[tier] for tier in tiers)
        per_type[kind] = {**metrics(selected), "per_tier": tiers, "tier_weighted_competence": competence,
                          "missing_tiers": [tier for tier in TIER_WEIGHTS if tier not in tiers]}
    values = [r["tier_weighted_competence"] for r in per_type.values()]
    return {"schema_version": 1, "scope": SCOPE, "status": "complete", "input_sha256": manifest["requests_sha256"],
            "upstream_commit": UPSTREAM_COMMIT, "method_files_sha256": METHOD_FILES, "expected_identity": identity,
            "n": len(rows), "sampling": manifest["sampling"], "per_type": per_type,
            "subset_competence_equal_types": sum(values) / len(values) if all(v is not None for v in values) else None,
            "per_family_type": {family: {kind: metrics([r for r in rows if r["family"] == family and r["kind"] == kind])
                                         for kind in sorted({r["kind"] for r in rows if r["family"] == family})}
                               for family in sorted({r["family"] for r in rows})},
            "not_computed": ["official I_open", "sealed competence", "overfit penalty", "calibration axis", "speed/cost axes", "composite", "rank"],
            "score_invalid_policy": "Competence unavailable if any Score distribution is invalid; numeric failure MAE is unspecified in the public method",
            "timing_note": report["latency_note"]}


def compare(baseline, trained):
    if (baseline["status"] != "complete" or trained["status"] != "complete"
            or any(baseline[k] != trained[k] for k in ("input_sha256", "upstream_commit", "method_files_sha256", "sampling", "n"))):
        raise ValueError("Comparison requires complete runs on the same frozen public sample")
    fixed = ("model", "method", "base_revision", "code_commit", "max_length")
    if any(baseline["expected_identity"][k] != trained["expected_identity"][k] for k in fixed):
        raise ValueError("Comparison base, code, request limit or method differs")
    def delta(before, after):
        return None if before is None or after is None else after - before
    changes = {}
    for kind in baseline["per_type"]:
        before, after = baseline["per_type"][kind], trained["per_type"][kind]
        keys = ("mean_normalized_mae", "argmax_accuracy_auxiliary") if kind == "score" else ("accuracy",)
        if kind == "noul":
            keys += ("coverage",)
        changes[kind] = {key: delta(before[key], after[key]) for key in (*keys, "tier_weighted_competence")}
    return {"scope": SCOPE, "status": "complete", "n": baseline["n"], "input_sha256": baseline["input_sha256"],
            "baseline_identity": baseline["expected_identity"], "trained_identity": trained["expected_identity"],
            "delta_trained_minus_baseline": changes,
            "subset_competence_delta": delta(baseline["subset_competence_equal_types"], trained["subset_competence_equal_types"]),
            "limitation": "One fixed development sample. No uncertainty estimate, blind-test gain, official I_open or leaderboard improvement claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--upstream", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--size", type=int, choices=(64, 128), default=64)
    p = sub.add_parser("collect")
    p.add_argument("--upstream", required=True)
    p.add_argument("--prepared", required=True)
    p.add_argument("--endpoint", required=True)
    p.add_argument("--identity", type=Path, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--max-seconds", type=float, default=1800)
    p = sub.add_parser("summarize")
    p.add_argument("--upstream", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("compare")
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--trained", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.upstream, args.output, args.size)
        print(json.dumps({k: result[k] for k in ("planned_requests", "requests_sha256", "selected_by_kind")}))
    elif args.command == "collect":
        result = collect(args.upstream, args.prepared, args.endpoint, legacy.strict_json(args.identity.read_bytes()),
                         args.output, args.timeout, args.max_seconds)
        print(json.dumps({k: result[k] for k in ("status", "planned_requests", "attempted_requests", "failed_requests")}))
        return 0 if result["status"] == "complete" else 1
    else:
        result = (summarize(args.upstream, args.run_dir) if args.command == "summarize" else
                  compare(legacy.strict_json(args.baseline.read_bytes()), legacy.strict_json(args.trained.read_bytes())))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as handle:
            handle.write(legacy.json_bytes(result))
        print(json.dumps({k: result[k] for k in ("status", "n", "input_sha256")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
