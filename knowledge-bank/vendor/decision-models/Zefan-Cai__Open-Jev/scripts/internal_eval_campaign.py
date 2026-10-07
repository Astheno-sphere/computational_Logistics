"""Freeze, partition and independently merge a multi-group FSDP4 evaluation.

No inference, GPU access, remote operations, retries or publication occurs here.
Imported old rows keep their original backend identity and exact source bytes.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = "reports/new27b-internal-full-20260923/verify.py"
CODE_FILES = ("scripts/evaluate_internal_shard.py", "scripts/internal_eval_campaign.py",
              "scripts/evaluate_internal_full.py", "scripts/evaluate_checkpoints_parallel.py",
              "jev/model.py", "jev/sharded_model.py", "jev/shared_resources.py", "jev/eval_resources.py",
              "jev/api.py", "jev/data.py", "jev/metrics.py", "jev/train_distributed.py", AUDITOR)
_module = importlib.util.spec_from_file_location("_openjev_independent_full_auditor", ROOT / AUDITOR)
independent = importlib.util.module_from_spec(_module)
_module.loader.exec_module(independent)
canonical = independent.canonical
object_hash = independent.object_hash
file_hash = independent.file_hash
require = independent.require
strict_json = independent.strict_json
PRODUCTION = independent.PRODUCTION
TOKENIZER_MAXIMUM = {
    "id": "browser-control-v1:parent:76dfec94cd14bf434388f3a4:ambiguous_observed_target:operation",
    "row_sha256": "42247ec37eb08b787e0a6c35453ebf187231fd639365a851260f34dea28fbd95",
    "source_report_sha256": "e882a18f5bb243708b83313c9131540269cce0feeea06d09114221c165cdc8c9",
    "candidate_sequences": 8, "max_length": 1756, "padded_tokens": 14048,
}


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(canonical(value) + "\n")
    temporary.replace(path)


def implementation_identity(root=ROOT):
    return {name: file_hash(Path(root) / name) for name in CODE_FILES}


def get_group(manifest, group_id):
    found = [g for g in manifest["groups"] if g["id"] == group_id]
    require(len(found) == 1, "Unknown or duplicate campaign group")
    return found[0]


def group_indices(manifest, group_id):
    group = get_group(manifest, group_id)
    return manifest["remaining_global_indices"][group["ordinal"]::manifest["group_count"]]


def rank_indices(manifest, group_id, rank):
    require(type(rank) is int and 0 <= rank < 4, "Exactly four local ranks are required")
    return group_indices(manifest, group_id)[rank::4]


def probe_contract(manifest, group_id):
    group = get_group(manifest, group_id)
    return object_hash({"schema_version": 1, "checkpoint": manifest["checkpoint"], "data": manifest["data"],
                        "implementation_sha256": manifest["implementation_sha256"],
                        "fixtures_sha256": manifest["probe_fixtures"]["sha256"],
                        "group": {k: group[k] for k in ("id", "node", "policy", "policy_sha256", "paths")}})


def read_campaign(path, expected_sha256=None):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(expected_sha256 is None or digest == expected_sha256, "Campaign manifest changed from external pin")
    manifest = strict_json(raw)
    require(manifest["schema_version"] == 1 and manifest["status"] == "frozen", "Campaign is not frozen")
    require(manifest["partition"] == "remaining_global_indices[ordinal::group_count][rank::4]", "Campaign partition differs")
    groups = manifest["groups"]
    require(groups and len(groups) == manifest["group_count"] and len({g["id"] for g in groups}) == len(groups), "Invalid campaign group set")
    for ordinal, group in enumerate(groups):
        require(group["ordinal"] == ordinal and isinstance(group["id"], str) and group["id"], "Group ordinal/ID differs")
        require(object_hash(group["policy"]) == group["policy_sha256"], "Hardware policy hash differs")
        require(group["probe_contract_sha256"] == probe_contract(manifest, group["id"]), "Group probe contract differs")
    total = sum(manifest["data"]["counts"].values())
    imports = [row["global_index"] for row in manifest["imported_rows"]]
    remaining = manifest["remaining_global_indices"]
    require(all(type(i) is int and 0 <= i < total for i in imports + remaining), "Global index outside frozen data")
    require(imports == sorted(set(imports)) and remaining == sorted(set(remaining)), "Duplicate or unordered campaign index")
    require(not set(imports).intersection(remaining) and set(imports).union(remaining) == set(range(total)), "Campaign partition is not the full disjoint panel")
    require(manifest["total_rows"] == total and manifest["imported_count"] == len(imports)
            and manifest["remaining_count"] == len(remaining), "Campaign denominator differs")
    require(set(manifest["implementation_sha256"]) == set(CODE_FILES), "Campaign implementation inventory differs")
    return manifest, digest


def load_probe_fixtures(campaign_path, manifest):
    name = manifest["probe_fixtures"]["path"]
    require(name == "probe-fixtures.json", "Unexpected probe fixture path")
    path = Path(campaign_path).parent / name
    require(file_hash(path) == manifest["probe_fixtures"]["sha256"], "Frozen probe fixture changed")
    fixtures = strict_json(path.read_bytes())
    require(fixtures["schema_version"] == 1 and fixtures["checkpoint_sha256"] == manifest["checkpoint"]["checkpoint_sha256"]
            and fixtures["data_manifest_sha256"] == manifest["data"]["manifest_sha256"]
            and fixtures["temperature"] == manifest["checkpoint"]["temperature"], "Probe fixture provenance differs")
    indices = [r["global_index"] for r in fixtures["rows"]]
    require(indices and len(indices) == len(set(indices)), "Probe fixtures missing/duplicated")
    require(all(type(row["candidate_count"]) is int and row["candidate_count"] > 0 for row in fixtures["rows"]), "Probe candidate counts missing/invalid")
    return fixtures


def _compare_logits(left, right, name):
    require(type(left.get("input_tokens")) is int and left["input_tokens"] > 0 and type(right.get("input_tokens")) is int
            and left["input_tokens"] == right.get("input_tokens"), name + ": token count differs")
    first, second = left.get("logits"), right.get("logits")
    require(isinstance(first, list) and isinstance(second, list) and first and len(first) == len(second)
            and all(type(v) in (int, float) and math.isfinite(v) for v in first + second), name + ": invalid logits")
    error = max(abs(a - b) for a, b in zip(first, second))
    require(error <= .05 and max(range(len(first)), key=first.__getitem__) == max(range(len(second)), key=second.__getitem__), name + ": logits/argmax differ")
    return error


def validate_probe(report, manifest, fixtures, group_id):
    require(report.get("status") in ("pending", "passed"), "Probe did not pass or cannot be checked")
    require(report["campaign_group_id"] == group_id and report["probe_contract_sha256"] == probe_contract(manifest, group_id)
            and report["fixtures_sha256"] == manifest["probe_fixtures"]["sha256"], "Probe identity differs")
    require(len(report["rows"]) == len(fixtures["rows"]), "Missing or extra probe result")
    maximum, references = 0., 0
    for index, (row, expected) in enumerate(zip(report["rows"], fixtures["rows"])):
        require(row["global_index"] == expected["global_index"] and row["row_sha256"] == expected["row_sha256"]
                and row["rank"] == index % 4, "Probe row identity/order differs")
        require(len(row["different_row"]["logits"]) == expected["candidate_count"], "Probe candidate count differs from source")
        maximum = max(maximum, _compare_logits(row["different_row"], row["same_row"], "Different/same-row probe"))
        if expected["reference"] is not None:
            maximum = max(maximum, _compare_logits(row["different_row"], expected["reference"], "Old/new reference probe"))
            references += 1
    require(references >= 4, "At least four preserved old references are required")
    return {"rows": len(report["rows"]), "old_reference_rows": references, "maximum_logit_absolute_error": maximum}


def _inputs(data, old_data, checkpoint, identity, snapshot, spec):
    independent.checkpoint(Path(checkpoint), identity["checkpoint"], spec, snapshot)
    new = independent.load_data(Path(data), "new-data", spec["new"], snapshot)
    old = independent.load_data(Path(old_data), "old-data", spec["old"], snapshot)
    subsets = {}
    for split in independent.SPLITS:
        mapping = {row["id"]: index for index, row in enumerate(new[split])}
        subsets[split] = []
        for row in old[split]:
            require(row["id"] in mapping and row == new[split][mapping[row["id"]]], "Old held-out record absent or changed")
            subsets[split].append(mapping[row["id"]])
    expected = {"manifest_sha256": spec["new"]["manifest"], "split_sha256": spec["new"]["hashes"],
                "counts": spec["new"]["counts"],
                "ordered_ids_sha256": {s: object_hash([r["id"] for r in new[s]]) for s in independent.SPLITS},
                "old_manifest_sha256": spec["old"]["manifest"], "old_split_sha256": spec["old"]["hashes"],
                "old_counts": spec["old"]["counts"], "old_subset_indices_sha256": object_hash(subsets)}
    require(identity["data"] == expected, "Frozen data identity differs")
    return [(split, index, row) for split in independent.SPLITS for index, row in enumerate(new[split])], subsets


def _validate_result(result, row_fields, temperature):
    require(canonical({key: result.get(key) for key in row_fields}) == canonical(row_fields), "Result coordinate/ID/content identity differs")
    require(result.get("status") == "ok", "Recorded inference errors are fatal; no retries or row removal")
    logits = result.get("logits")
    require(isinstance(logits, list) and len(logits) == len(row_fields["target"])
            and all(type(v) in (int, float) and math.isfinite(v) for v in logits), "Invalid saved logits")
    maximum = max(logits)
    weights = [math.exp((v - maximum) / temperature) for v in logits]
    expected = [v / math.fsum(weights) for v in weights]
    probabilities = result.get("probabilities")
    independent.distribution(probabilities)
    require(len(probabilities) == len(expected) and max(abs(a - b) for a, b in zip(probabilities, expected)) <= 1e-12, "Frozen softmax differs")
    require(type(result.get("input_tokens")) is int and result["input_tokens"] > 0, "Invalid input token count")
    require(type(result.get("wall_seconds")) in (int, float) and math.isfinite(result["wall_seconds"])
            and result["wall_seconds"] >= 0, "Invalid wall time")


def _read_old(directory, items, identity, snapshot, *, role="old-prefix"):
    require(identity["backend"] == "fsdp4" and identity["world_size"] == 4 and identity["row_batch_size"] == 1
            and identity["max_length"] == 4096 and identity["prefix_cache"] is False
            and identity["temperature_fitted"] is False and identity["partition"] == "concatenated_test_ood_index_mod4",
            "Old execution identity differs")
    identity_sha = object_hash(identity)
    probe = snapshot.json(role + "/probe.json", directory / "probe.json")
    require(probe["status"] == "passed" and probe["eval_identity_sha256"] == identity_sha
            and len(probe["checks"]) == 4 and probe["max_logit_error_allowed"] == .05, "Old parity gate is not verified")
    positions = [i * (len(items) - 1) // 3 for i in range(4)]
    require(probe["probe_indices"] == positions, "Old parity fixture indices differ")
    for rank, value in enumerate(probe["checks"]):
        row = items[positions[rank]][2]
        require(value["rank"] == rank and value["row_id"] == row["id"] and value["row_sha256"] == row["row_sha256"]
                and value["passed"] is True and value["argmax_equal"] is True
                and type(value["max_logit_error"]) in (int, float) and 0 <= value["max_logit_error"] <= .05, "Old parity evidence differs")
    found, imports = {}, []
    for rank in range(4):
        for round_index, result in enumerate(snapshot.lines(role + f"/shard-{rank}.jsonl", directory / f"shard-{rank}.jsonl")):
            offset = rank + round_index * 4
            require(offset < len(items), "Extra old prefix record")
            split, index, row = items[offset]
            expected = {**row, "round": round_index, "split": split, "index": index, "rank": rank,
                        "eval_identity_sha256": identity_sha, "checkpoint_sha256": identity["checkpoint"]["checkpoint_sha256"],
                        "data_split_sha256": identity["data"]["split_sha256"][split]}
            _validate_result(result, expected, identity["checkpoint"]["temperature"])
            found[offset] = result
            imports.append({"global_index": offset, "source_rank": rank, "source_line": round_index + 1,
                            "record_sha256": object_hash(result), "source_identity_sha256": identity_sha})
    require(len(found) >= 4, "At least four preserved successful references are required")
    return found, sorted(imports, key=lambda row: row["global_index"])


def _fixtures(data, items, imported, spec=PRODUCTION):
    reference_indices = []
    for rank in range(4):
        owned = [i for i in sorted(imported) if imported[i]["rank"] == rank]
        if owned:
            reference_indices.append(owned[0])
    reference_indices += [i for i in sorted(imported) if i not in reference_indices][:4 - len(reference_indices)]
    selected = {i: ["preserved_old_rank_reference"] for i in reference_indices}
    first_kinds = {}
    for index, (_, _, row) in enumerate(items):
        first_kinds.setdefault(row["kind"], index)
    for kind, index in first_kinds.items():
        selected.setdefault(index, []).append("first_heldout_kind_" + kind)
    maximum_index = None
    if spec["new"]["manifest"] == PRODUCTION["new"]["manifest"]:
        require(set(first_kinds) == {"choice", "noul", "score"}, "Production probe must exercise every decision kind")
        matches = [i for i, (split, _, row) in enumerate(items) if row["id"] == TOKENIZER_MAXIMUM["id"]
                   and split == "ood" and row["kind"] == "choice" and len(row["target"]) == 8]
        require(len(matches) == 1, "Pinned tokenizer maximum row absent or changed")
        maximum_index = matches[0]
        require(items[maximum_index][2]["row_sha256"] == TOKENIZER_MAXIMUM["row_sha256"], "Tokenizer maximum row content differs")
        selected.setdefault(maximum_index, []).extend(["audited_longest_candidate", "audited_largest_padded_row"])
    maxima = {}
    offset = 0
    for split in independent.SPLITS:
        with (Path(data) / (split + ".jsonl")).open("rb") as stream:
            for line in stream:
                row = strict_json(line)
                visible_bytes = len(canonical({k: row[k] for k in ("state", "question", "kind", "options")}).encode())
                sizes = {"most_candidates": len(row["options"]), "largest_visible_utf8": visible_bytes,
                         "largest_candidate_context_product": len(row["options"]) * visible_bytes,
                         "largest_single_candidate_utf8": max(len(v.encode()) for v in row["options"])}
                for name, score in sizes.items():
                    if name not in maxima or (score, -offset) > maxima[name][0]:
                        maxima[name] = ((score, -offset), offset)
                offset += 1
    require(offset == len(items), "Shape selection source count changed")
    for name, (_, index) in maxima.items():
        selected.setdefault(index, []).append(name)
    rows = []
    for index in sorted(selected):
        reference = None
        if index in reference_indices:
            result = imported[index]
            reference = {"logits": result["logits"], "input_tokens": result["input_tokens"],
                         "source_record_sha256": object_hash(result), "source_identity_sha256": result["eval_identity_sha256"]}
        rows.append({"global_index": index, "row_sha256": items[index][2]["row_sha256"],
                     "candidate_count": len(items[index][2]["target"]),
                     "profiles": sorted(selected[index]), "reference": reference,
                     "tokenizer_profile": dict(TOKENIZER_MAXIMUM) if index == maximum_index else None})
    return rows


def create_campaign(old_snapshot, old_implementation_root, data, old_data, checkpoint, implementation_root,
                    groups, output, *, implementation_commit=None, fixtures_path=None, spec=PRODUCTION):
    """Call on a stopped/copied old prefix. Uneven valid rank tails are retained."""
    output, old_snapshot = Path(output), Path(old_snapshot)
    require(not output.exists(), "Use a fresh campaign directory")
    snapshot = independent.Snapshot()
    identity = snapshot.json("old-prefix/identity.json", old_snapshot / "identity.json")
    require(identity["implementation_sha256"] == spec["implementation_sha256"], "Old source identity differs from pinned commit")
    for name, expected in spec["implementation_sha256"].items():
        path = Path(old_implementation_root) / name
        digest = snapshot.remember("old-prefix/implementation/" + name, path, file_hash(path))
        require(digest == expected, "Old runtime source bytes differ")
    items, _ = _inputs(data, old_data, checkpoint, identity, snapshot, spec)
    imported, import_manifest = _read_old(old_snapshot, items, identity, snapshot)
    for rank in range(4):
        path = old_snapshot / f"progress-{rank}.json"
        if path.is_file():
            snapshot.json("old-prefix/" + path.name, path)
    code = implementation_identity(implementation_root)
    if spec["new"]["manifest"] == PRODUCTION["new"]["manifest"]:
        require(all(code[name] == PRODUCTION["implementation_sha256"][name] for name in ("jev/model.py", "jev/api.py")),
                "Tokenizer maximum profile requires its pinned model/API encoding implementation")
    if implementation_commit is not None:
        for name, digest in code.items():
            payload = subprocess.check_output(["git", "-C", str(implementation_root), "show", implementation_commit + ":" + name])
            require(hashlib.sha256(payload).hexdigest() == digest, "New source differs from committed implementation pin")
    for name, digest in code.items():
        snapshot.remember("new-implementation/" + name, Path(implementation_root) / name, digest)
    normalized, occupied = [], set()
    for ordinal, value in enumerate(groups):
        group = dict(value)
        require(set(group) == {"id", "node", "policy", "paths"}, "Group requires id/node/policy/paths only")
        require(isinstance(group["id"], str) and group["id"] and "/" not in group["id"], "Invalid group ID")
        require(set(group["paths"]) == {"data", "old_data", "checkpoint", "resource_policy"}, "Group runtime paths incomplete")
        indices = group["policy"]["gpu_indices"]
        require(len(indices) == 4 and len(set(indices)) == 4, "Every group requires four unique GPUs")
        for gpu in indices:
            require((group["node"], gpu) not in occupied, "Campaign groups overlap a physical GPU")
            occupied.add((group["node"], gpu))
        group.update(ordinal=ordinal, policy_sha256=object_hash(group["policy"]))
        normalized.append(group)
    require(normalized and len({g["id"] for g in normalized}) == len(normalized), "Group list is empty or duplicated")
    fixtures = {"schema_version": 1, "checkpoint_sha256": identity["checkpoint"]["checkpoint_sha256"],
                "data_manifest_sha256": identity["data"]["manifest_sha256"], "temperature": identity["checkpoint"]["temperature"],
                "shape_selection_basis": "First row of each decision kind, deterministic byte/candidate proxies, and the separately audited production longest/largest-padded token row. Byte proxies are not token maxima; real probes check exact cross-group tokens.",
                "rows": _fixtures(data, items, imported, spec)}
    fixture_bytes = (canonical(fixtures) + "\n").encode()
    if fixtures_path is not None:
        require(Path(fixtures_path).read_bytes() == fixture_bytes, "Preserved preflight fixtures differ from final frozen references")
    old_files = {name.removeprefix("old-prefix/"): digest for name, (_, digest) in snapshot.files.items() if name.startswith("old-prefix/")}
    manifest = {"schema_version": 1, "status": "frozen", "partition": "remaining_global_indices[ordinal::group_count][rank::4]",
                "checkpoint": identity["checkpoint"], "data": identity["data"],
                "implementation_commit": implementation_commit, "implementation_sha256": code,
                "old_prefix": {"directory": "old-prefix", "identity_sha256": object_hash(identity),
                               "files_sha256": old_files, "implementation_commit": spec["implementation_commit"]},
                "imported_rows": import_manifest, "imported_count": len(imported),
                "remaining_global_indices": [i for i in range(len(items)) if i not in imported],
                "remaining_count": len(items) - len(imported), "total_rows": len(items),
                "groups": normalized, "group_count": len(normalized),
                "probe_fixtures": {"path": "probe-fixtures.json", "sha256": hashlib.sha256(fixture_bytes).hexdigest()},
                "input_sources_sha256": {name: digest for name, (_, digest) in snapshot.files.items()}}
    for group in normalized:
        group["probe_contract_sha256"] = probe_contract(manifest, group["id"])
    snapshot.stable()
    output.mkdir(parents=True)
    for name, (path, digest) in snapshot.files.items():
        if name.startswith("old-prefix/"):
            payload = path.read_bytes()
            require(hashlib.sha256(payload).hexdigest() == digest, "Old source changed while freezing")
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
    (output / "probe-fixtures.json").write_bytes(fixture_bytes)
    snapshot.stable()
    write_json(output / "manifest.json", manifest)
    frozen, digest = read_campaign(output / "manifest.json")
    require(frozen == manifest, "Campaign round trip failed")
    return {"manifest_sha256": digest, "total_rows": len(items), "imported_rows": len(imported),
            "remaining_rows": len(items) - len(imported), "group_rows": {g["id"]: len(group_indices(manifest, g["id"])) for g in normalized}}


def _group_identity(manifest, campaign_sha, group, actual):
    expected = {"schema_version": 1, "checkpoint": manifest["checkpoint"], "data": manifest["data"],
                "backend": "fsdp4", "world_size": 4, "row_batch_size": 1, "max_length": 4096,
                "prefix_cache": False, "temperature_fitted": False, "partition": manifest["partition"],
                "campaign_sha256": campaign_sha, "campaign_group_id": group["id"], "group_ordinal": group["ordinal"],
                "group_count": manifest["group_count"], "policy": group["policy"],
                "implementation_sha256": manifest["implementation_sha256"]}
    require(all(canonical(actual.get(k)) == canonical(v) for k, v in expected.items()), "Group execution identity differs")
    require(isinstance(actual.get("allocator_config"), str), "Allocator configuration absent")
    return object_hash(actual)


def merge_campaign(campaign_path, expected_sha256, group_directories, data, old_data, checkpoint,
                   implementation_root, output, *, spec=PRODUCTION):
    """Produce scores only after imported and new rows form one complete union."""
    output, campaign_path = Path(output), Path(campaign_path)
    require(not output.exists(), "Use a fresh merge output directory")
    manifest, campaign_sha = read_campaign(campaign_path, expected_sha256)
    require(manifest["checkpoint"]["checkpoint_sha256"] == spec["checkpoint"]
            and manifest["checkpoint"]["temperature"] == spec["temperature"], "Campaign checkpoint/temperature pin differs")
    require(set(group_directories) == {g["id"] for g in manifest["groups"]}, "Missing/extra active group result directory")
    snapshot = independent.Snapshot()
    snapshot.remember("campaign/manifest.json", campaign_path, campaign_sha)
    require(implementation_identity(implementation_root) == manifest["implementation_sha256"], "Campaign runtime source bytes differ")
    for name, digest in manifest["implementation_sha256"].items():
        snapshot.remember("new-implementation/" + name, Path(implementation_root) / name, digest)
    old_root = campaign_path.parent / "old-prefix"
    require(manifest["old_prefix"]["directory"] == "old-prefix", "Old prefix path differs")
    old_identity = snapshot.json("old-prefix/identity.json", old_root / "identity.json")
    require(object_hash(old_identity) == manifest["old_prefix"]["identity_sha256"]
            and old_identity["implementation_sha256"] == spec["implementation_sha256"], "Imported source implementation identity differs")
    require(manifest["checkpoint"] == old_identity["checkpoint"] and manifest["data"] == old_identity["data"], "Campaign/source checkpoint or data identity differs")
    for name, expected in spec["implementation_sha256"].items():
        role, path = "old-prefix/implementation/" + name, old_root / "implementation" / name
        snapshot.remember(role, path, file_hash(path))
        snapshot.check(role, expected)
    items, subsets = _inputs(data, old_data, checkpoint, old_identity, snapshot, spec)
    imported, imported_manifest = _read_old(old_root, items, old_identity, snapshot)
    require(imported_manifest == manifest["imported_rows"], "Frozen imported coordinate/content map differs")
    for name, expected in manifest["old_prefix"]["files_sha256"].items():
        role = "old-prefix/" + name
        if role not in snapshot.files:
            path = old_root / name
            snapshot.remember(role, path, file_hash(path))
        snapshot.check(role, expected)
    fixtures = load_probe_fixtures(campaign_path, manifest)
    snapshot.remember("campaign/probe-fixtures.json", campaign_path.parent / "probe-fixtures.json", manifest["probe_fixtures"]["sha256"])
    require(fixtures["rows"] == _fixtures(data, items, imported, spec), "Probe references/shapes differ from frozen source")
    results = {index: {"global_index": index, "origin": {"type": "imported_old", "source_identity_sha256": object_hash(old_identity)},
                       "result": row} for index, row in imported.items()}
    probes, group_evidence = {}, {}
    for group in manifest["groups"]:
        group_id, directory = group["id"], Path(group_directories[group["id"]])
        prefix = "groups/" + group_id + "/"
        summary = snapshot.json(prefix + "summary.json", directory / "summary.json")
        require(summary.get("status") == "complete", "Group is incomplete; no campaign scores")
        progresses = [snapshot.json(prefix + f"progress-{r}.json", directory / f"progress-{r}.json") for r in range(4)]
        require(all(p.get("status") == "complete" for p in progresses), "Group shard is incomplete")
        identity = snapshot.json(prefix + "identity.json", directory / "identity.json")
        identity_sha = _group_identity(manifest, campaign_sha, group, identity)
        require(summary["identity"] == identity and summary["campaign_sha256"] == campaign_sha
                and summary["campaign_group_id"] == group_id and summary["total_rows"] == len(group_indices(manifest, group_id)), "Group summary identity/count differs")
        original_probe = snapshot.json(prefix + "probe.json", directory / "probe.json")
        require(original_probe["status"] == "passed", "Original group probe failed")
        validate_probe(original_probe, manifest, fixtures, group_id)
        receipt = summary["probe_receipt"]
        name = receipt["path"]
        require(Path(name).name == name and name.startswith("probe") and name.endswith(".json"), "Unsafe/invalid probe receipt path")
        latest_probe = original_probe if name == "probe.json" else snapshot.json(prefix + name, directory / name)
        snapshot.check(prefix + name, receipt["sha256"])
        require(latest_probe["status"] == "passed", "Latest group probe failed")
        group_evidence[group_id] = validate_probe(latest_probe, manifest, fixtures, group_id)
        probes[group_id] = latest_probe
        require(set(summary["raw_sha256"]) == {f"shard-{r}.jsonl" for r in range(4)}, "Group shard inventory differs")
        for rank in range(4):
            assigned = rank_indices(manifest, group_id, rank)
            progress = progresses[rank]
            require(progress["rank"] == rank and progress["planned_rows"] == len(assigned)
                    and progress["successful_rows"] == len(assigned) and progress["failed_rows"] == 0
                    and progress["pending_rows"] == 0 and progress["eval_identity_sha256"] == identity_sha, "Group rank denominator differs")
            count = 0
            role = prefix + f"shard-{rank}.jsonl"
            for result in snapshot.lines(role, directory / f"shard-{rank}.jsonl"):
                require(count < len(assigned), "Extra group shard row")
                global_index = assigned[count]
                split, index, row = items[global_index]
                expected = {**row, "round": count, "split": split, "index": index, "rank": rank,
                            "global_index": global_index, "campaign_sha256": campaign_sha, "campaign_group_id": group_id,
                            "group_ordinal": group["ordinal"], "eval_identity_sha256": identity_sha,
                            "checkpoint_sha256": spec["checkpoint"], "data_split_sha256": spec["new"]["hashes"][split]}
                _validate_result(result, expected, spec["temperature"])
                require(global_index not in results, "Duplicate imported/new global index")
                results[global_index] = {"global_index": global_index, "origin": {"type": "campaign_group", "campaign_group_id": group_id,
                                         "source_identity_sha256": identity_sha}, "result": result}
                count += 1
            require(count == len(assigned), "Missing group shard rows")
            snapshot.check(role, summary["raw_sha256"][f"shard-{rank}.jsonl"])
            snapshot.check(role, progress["output_sha256"])
    require(set(results) == set(range(len(items))) and len(results) == manifest["total_rows"], "Campaign full union is incomplete")
    anchor = probes[manifest["groups"][0]["id"]]
    cross_group_error = 0.
    for group_id, probe in probes.items():
        for first, second in zip(anchor["rows"], probe["rows"]):
            cross_group_error = max(cross_group_error, _compare_logits(first["different_row"], second["different_row"], "Cross-group fixture " + group_id))
    metrics, old_metrics, denominators, offset = {}, {}, {}, 0
    for split in independent.SPLITS:
        count = spec["new"]["counts"][split]
        observed = [independent.observation(results[i]["result"]) for i in range(offset, offset + count)]
        old_observed = [observed[i] for i in subsets[split]]
        require(sum(r["hard"] for r in observed) == spec["new"]["hard_counts"][split]
                and sum(r["hard"] for r in old_observed) == spec["old"]["hard_counts"][split], "Campaign hard denominator differs")
        require(all(r["correct"] in (0., 1.) for r in observed if r["hard"]), "Nonbinary correctness on hard target")
        metrics[split], old_metrics[split] = independent.grouped(observed), independent.grouped(old_observed)
        denominators[split] = {"count": count, "hard_count": sum(r["hard"] for r in observed),
                               "soft_count": sum(not r["hard"] for r in observed),
                               "hard_correct": sum(int(r["correct"]) for r in observed if r["hard"]),
                               "old_count": len(old_observed), "old_hard_count": sum(r["hard"] for r in old_observed),
                               "old_soft_count": sum(not r["hard"] for r in old_observed),
                               "old_hard_correct": sum(int(r["correct"]) for r in old_observed if r["hard"])}
        offset += count
    snapshot.stable()
    output.mkdir(parents=True)
    with (output / "merged-records.jsonl").open("w") as stream:
        for index in range(len(items)):
            stream.write(canonical(results[index]) + "\n")
    report = {"status": "complete", "schema_version": 1, "campaign_sha256": campaign_sha,
              "total_rows": len(items), "imported_rows": len(imported), "new_rows": len(items) - len(imported),
              "old_subset_rows": sum(len(v) for v in subsets.values()), "denominators": denominators,
              "splits": metrics, "old_release_subset": old_metrics, "temperature_fitted": False,
              "padding_included_in_denominators": False, "imported_backend_identity_preserved": True,
              "group_probe_checks": group_evidence, "cross_group_maximum_logit_error": cross_group_error,
              "merged_records_sha256": file_hash(output / "merged-records.jsonl"),
              "input_sources_sha256": {name: digest for name, (_, digest) in sorted(snapshot.files.items())},
              "performance_scope": "Mixed saved original and multi-group shared-node inference; no single-GPU/API latency or measured speedup claim."}
    snapshot.stable()
    write_json(output / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("prepare")
    for name in ("old-snapshot", "old-implementation-root", "data", "old-data", "checkpoint", "implementation-root", "groups", "output"):
        prepare.add_argument("--" + name, required=True, type=Path)
    prepare.add_argument("--implementation-commit", required=True)
    prepare.add_argument("--fixtures", type=Path)
    merge = modes.add_parser("merge")
    for name in ("campaign", "group-directories", "data", "old-data", "checkpoint", "implementation-root", "output"):
        merge.add_argument("--" + name, required=True, type=Path)
    merge.add_argument("--campaign-sha256", required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        result = create_campaign(args.old_snapshot, args.old_implementation_root, args.data, args.old_data, args.checkpoint,
                                 args.implementation_root, strict_json(args.groups.read_bytes()), args.output,
                                 implementation_commit=args.implementation_commit, fixtures_path=args.fixtures)
    else:
        result = merge_campaign(args.campaign, args.campaign_sha256, strict_json(args.group_directories.read_bytes()),
                                args.data, args.old_data, args.checkpoint, args.implementation_root, args.output)
        result = {key: result[key] for key in ("status", "total_rows", "imported_rows", "new_rows", "old_subset_rows", "denominators")}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, OverflowError, subprocess.CalledProcessError) as error:
        print("Campaign failed: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        sys.exit(1)
