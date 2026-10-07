"""Held-out-only Jev Frontier 100 evaluation through native Choice requests.

Protocol/statistical design: softpudding/jev-frontier-100, MIT,
Copyright (c) 2026 JF100 contributors. Original data remains in an external,
commit-pinned checkout and is never converted into a training split.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .api import compile_request


SOURCE_URL = "https://github.com/softpudding/jev-frontier-100"
SOURCE_COMMIT = "9abacec47394f3b393f81fbe3cdd524f028bc088"
SOURCE_FILES = {
    "data/items.jsonl": "dd107ba90de381eaa479408492e81d7222115782e5fe601ab43986f94cd1d0fa",
    "data/manifest.json": "36b770066f7f3f0b17321a41b09699d5101c1b7b3db889fccab5f457fb035060",
    "docs/PROTOCOL.md": "abafc61540543101fdd49593a20245f1d2522bd60f84d45402bf27ee0532a842",
    "LICENSE": "c944509bf87f8d3833d07a1a68339587938fe172b45017972bbaf701385b0763",
    "src/jf100/core.py": "df6f2eeb5da5cfca5d0f180d5dab861f4d8f5526057a391490e55c1159a28b7e",
    "src/jf100/runner.py": "38ed333255b0e88f842abc0b003658a1fce1a9dfb3599a6e22301fd481bfe4de",
    "src/jf100/aggregate.py": "f2dd34ebc074433797ff4c1de38d43720ba262669ea89c87440be7d226f8ea22",
    "results/v0.2-budget/outcomes.jsonl": "0a68aaeb0fa6ac605c42668cc0fe6f66d13e065a433cd63a1d1cbc91a4f8a690",
    "results/v0.2-budget/summary.json": "30bd217e61d960afa7eed5f5049f7eece0ba8dec50eb75ccbb176fcdac28f3c1",
}
TRIAL_SEEDS = (101, 202, 303)
BOOTSTRAP_SEED = 92026
RETRY_STATUSES = {0, 429, 500, 502, 503, 504, 529}
LEARNED_METHODS = {"lora_decision_head", "pretrained_yes_minus_no_no_training"}


def digest(value):
    """Upstream JSON normalization, including its default separator spaces."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def presented_options(item, trial):
    if type(trial) is not int or not 0 <= trial < len(TRIAL_SEEDS):
        raise ValueError("JF100 trial must be 0, 1 or 2")
    options = item["options"]
    if list(options) != list("ABCD") or len(set(options.values())) != 4:
        raise ValueError("JF100 requires four distinct options in original A-D order")
    pairs = list(options.items())
    rotated = pairs[trial:] + pairs[:trial]
    return dict(zip("ABCD", (text for _, text in rotated)))


def build_request(item, trial, model="open-jev"):
    """Only declared visible fields are read; gold/rationale never reach input."""
    request = {"model": model, "state": item["state"], "questions": {
        "answer": {"type": "choice", "instructions": item["question"], "criteria": presented_options(item, trial)}}}
    compile_request(request["state"], request["questions"])
    return request


def presented_gold(item, trial):
    if item["answer"] not in tuple("ABCD"):
        raise ValueError("JF100 original answer must be A-D")
    presented_options(item, trial)  # Validate trial/options before mapping.
    return "ABCD"[("ABCD".index(item["answer"]) - trial) % 4]


def validate_items(items):
    ids, pairs = set(), defaultdict(list)
    for item in items:
        if not isinstance(item.get("id"), str) or not item["id"] or item["id"] in ids:
            raise ValueError("JF100 item IDs must be unique nonempty strings")
        if not all(isinstance(item.get(key), str) and item[key] for key in ("pair_id", "domain", "difficulty", "question")):
            raise ValueError("JF100 requires pair, domain, difficulty and question metadata")
        ids.add(item["id"])
        pairs[item["pair_id"]].append(item)
        for trial in range(3):
            build_request(item, trial)
            presented_gold(item, trial)
    if any(len(pair) != 2 or len({item["domain"] for item in pair}) != 1 for pair in pairs.values()):
        raise ValueError("JF100 counterfactual pairs must contain two items from one domain")


def load_benchmark(source):
    source = Path(source)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError(f"JF100 checkout must be pinned at {SOURCE_COMMIT}")
    for name, expected in SOURCE_FILES.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"JF100 source checksum mismatch: {name}")
    manifest = json.loads((source / "data/manifest.json").read_text())
    items = [json.loads(line) for line in (source / "data/items.jsonl").read_text().splitlines() if line.strip()]
    validate_items(items)
    if len(items) != 100 or manifest["sha256"] != SOURCE_FILES["data/items.jsonl"]:
        raise ValueError("JF100 frozen item count/hash mismatch")
    public_rows = [json.loads(line) for line in (source / "results/v0.2-budget/outcomes.jsonl").read_text().splitlines() if line.strip()]
    reference = [row for row in public_rows if row.get("system") == "jev"]
    audit_outcomes(reference, items, expected_model="jev-1.13.0")
    published = json.loads((source / "results/v0.2-budget/summary.json").read_text())["systems"]["jev"]
    provenance = {"source_url": SOURCE_URL, "source_commit": commit, "dataset_version": manifest["version"],
                  "license": "MIT", "copyright": "Copyright (c) 2026 JF100 contributors",
                  "files_sha256": SOURCE_FILES, "training_use": "prohibited_by_this_integration_held_out_only",
                  "manifest": manifest, "reference_model": "jev-1.13.0", "reference_is_reused_not_new_inference": True}
    return items, reference, published, provenance


def task_order(items):
    for trial, seed in enumerate(TRIAL_SEEDS):
        order = list(items)
        random.Random(seed).shuffle(order)
        for item in order:
            yield item, trial


def audit_outcomes(rows, items, expected_model=None):
    """Require all 300 identities, rotated golds, request hashes and grades."""
    by_id = {item["id"]: item for item in items}
    seen = set()
    for row in rows:
        key = (row.get("item_id"), row.get("trial"))
        if key in seen or key[0] not in by_id or type(key[1]) is not int or not 0 <= key[1] < 3:
            raise ValueError("Unknown or duplicate JF100 item/trial")
        item = by_id[key[0]]
        gold = presented_gold(item, key[1])
        if row.get("gold") != gold or type(row.get("correct")) is not bool:
            raise ValueError("JF100 logged gold/grade differs from frozen reference")
        if row["correct"] != (row.get("status") == "ok" and row.get("answer") == gold):
            raise ValueError("JF100 outcome grade is inconsistent")
        if row.get("status") == "ok" and row.get("answer") not in tuple("ABCD"):
            raise ValueError("JF100 successful outcome lacks a valid answer")
        for field in ("domain", "difficulty", "pair_id"):
            if row.get(field) != item[field]:
                raise ValueError(f"JF100 outcome metadata mismatch: {field}")
        if expected_model is not None:
            expected = build_request(item, key[1], expected_model)
            if row.get("request_sha256") != digest(expected):
                raise ValueError("JF100 reconstructed request hash mismatch")
            if "request" in row and row["request"] != expected:
                raise ValueError("JF100 saved request differs from frozen visible fields")
        seen.add(key)
    if seen != {(item["id"], trial) for item in items for trial in range(3)}:
        raise ValueError("JF100 evaluation must contain every item across all three rotations")


def _quantile(values, probability):
    values = sorted(values)
    index = (len(values) - 1) * probability
    left, right = math.floor(index), math.ceil(index)
    return values[left] + (values[right] - values[left]) * (index - left)


def bootstrap_pair_means(pair_values, pair_domains, draws=5000):
    """Upstream stratified paired-template bootstrap, fixed seed 92026."""
    if type(draws) is not int or draws < 1 or not pair_values:
        raise ValueError("bootstrap requires nonempty pairs and positive draws")
    groups = defaultdict(list)
    for pair, value in pair_values.items():
        groups[pair_domains[pair]].append(value)
    rng, samples = random.Random(BOOTSTRAP_SEED), []
    for _ in range(draws):
        selected = []
        for domain in sorted(groups):
            selected.extend(rng.choices(groups[domain], k=len(groups[domain])))
        samples.append(statistics.mean(selected))
    return [_quantile(samples, 0.025), _quantile(samples, 0.975)]


def summarize(rows, items, draws=5000):
    audit_outcomes(rows, items)
    by_id = {item["id"]: item for item in items}
    item_values, pair_trials = defaultdict(list), defaultdict(list)
    for row in rows:
        item_values[row["item_id"]].append(int(row["correct"]))
        pair_trials[(row["pair_id"], row["trial"])].append(int(row["correct"]))
    per_pair = defaultdict(list)
    for item_id, values in item_values.items():
        per_pair[by_id[item_id]["pair_id"]].append(statistics.mean(values))
    pair_values = {pair: statistics.mean(values) for pair, values in per_pair.items()}
    pair_domains = {item["pair_id"]: item["domain"] for item in items}
    groups = {}
    for field in ("domain", "difficulty"):
        groups[field] = {}
        for value in sorted({item[field] for item in items}):
            matching = [row for row in rows if by_id[row["item_id"]][field] == value]
            groups[field][value] = {"correct": sum(row["correct"] for row in matching), "n": len(matching),
                                    "expected_n": 3 * sum(item[field] == value for item in items),
                                    "accuracy": statistics.mean(row["correct"] for row in matching)}
    valid = [row for row in rows if row["status"] == "ok"]
    consistent, eligible = 0, 0
    for item in items:
        observed = [row for row in rows if row["item_id"] == item["id"]]
        if all(row["status"] == "ok" for row in observed):
            meanings = [presented_options(item, row["trial"])[row["answer"]] for row in observed]
            eligible += 1
            consistent += len(set(meanings)) == 1
    return {"complete": True, "records": len(rows), "expected_records": len(items) * 3,
            "correct": sum(row["correct"] for row in rows), "accuracy": statistics.mean(row["correct"] for row in rows),
            "accuracy_95ci": bootstrap_pair_means(pair_values, pair_domains, draws),
            "status_counts": dict(Counter(row["status"] for row in rows)),
            "valid_completion_rate": len(valid) / len(rows),
            "accuracy_among_valid": statistics.mean(row["correct"] for row in valid) if valid else None,
            "pair_joint_accuracy": statistics.mean(all(values) for values in pair_trials.values()),
            "semantic_consistency": consistent / eligible if eligible else None,
            "consistency_eligible_items": eligible, "latency_median_ms": statistics.median(row["elapsed_ms"] for row in rows),
            "groups": groups, "pair_values": pair_values, "pair_domains": pair_domains}


def paired_comparison(local, reference, draws=5000):
    if local["pair_values"].keys() != reference["pair_values"].keys() or local["pair_domains"] != reference["pair_domains"]:
        raise ValueError("paired comparisons require identical templates and domains")
    differences = {pair: value - reference["pair_values"][pair] for pair, value in local["pair_values"].items()}
    return {"difference": statistics.mean(differences.values()),
            "95ci": bootstrap_pair_means(differences, local["pair_domains"], draws),
            "pairs": len(differences), "draws": draws, "seed": BOOTSTRAP_SEED,
            "by_domain": {domain: statistics.mean(value for pair, value in differences.items() if local["pair_domains"][pair] == domain)
                          for domain in sorted(set(local["pair_domains"].values()))}}


def _service_identity(response):
    metadata = response.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("HTTP service metadata must be an object")
    model, method, temperature = response.get("model"), metadata.get("method"), metadata.get("temperature")
    if not isinstance(model, str) or not model or method not in LEARNED_METHODS:
        raise ValueError("HTTP service did not identify a learned Open-Jev model/method")
    if type(temperature) not in (int, float) or not 0 < temperature < math.inf:
        raise ValueError("HTTP service lacks a valid calibration temperature")
    identity = {"model": model, "method": method, "temperature": temperature}
    for field in ("checkpoint_sha256", "base_revision", "code_commit"):
        value = metadata.get(field)
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError(f"Invalid service provenance: {field}")
            if field == "checkpoint_sha256" and not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("Invalid checkpoint SHA-256")
            identity[field] = value
    return identity


def validate_choice_response(response):
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict) or set(response["answers"]) != {"answer"}:
        raise ValueError("Expected exactly the submitted Choice question ID")
    answer = response["answers"]["answer"]
    if not isinstance(answer, dict) or answer.get("type") != "choice" or answer.get("choice") not in tuple("ABCD"):
        raise ValueError("Invalid native Choice answer")
    probabilities = answer.get("probabilities", {})
    if not isinstance(probabilities, dict) or set(probabilities) != set("ABCD") or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
        raise ValueError("Choice requires finite probabilities for all four positions")
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6):
        raise ValueError("Choice probabilities do not sum to one")
    # Argmax ties are legal, but a lower-probability returned choice is not.
    if probabilities[answer["choice"]] < max(probabilities.values()):
        raise ValueError("Returned choice is not an argmax of the scored candidates")
    return answer["choice"]


def http_request(endpoint, payload, timeout):
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
    request = Request(endpoint, body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read().decode(errors="replace")
    except HTTPError as error:
        status, raw = error.code, error.read().decode(errors="replace")
    except (URLError, TimeoutError, OSError) as error:
        status, raw = 0, str(error)
    try:
        # Reuse the local service's strict parser without loading model weights.
        from .server import strict_json
        parsed = strict_json(raw)
    except (ValueError, TypeError):
        parsed = None
    return {"http_status": status, "raw_body": raw, "body": parsed,
            "elapsed_ms": round((time.monotonic() - started) * 1000)}


def make_manifest(items, provenance, model_alias):
    return {**provenance, "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "evaluation_only": True, "trials": 3, "requests": 3 * len(items),
            "rotations": [0, 1, 2], "task_order_seeds": list(TRIAL_SEEDS),
            "stochastic_model_seed": None, "model_alias": model_alias,
            "trial_interpretation": "Option-position rotations; deterministic scorer, not three stochastic samples",
            "request_identities": [{"item_id": item["id"], "trial": trial,
                                    "state_sha256": digest(item["state"]),
                                    "request_sha256": digest(build_request(item, trial, model_alias)),
                                    "upstream_jev_request_sha256": digest(build_request(item, trial, "jev-1.13.0"))}
                                   for item, trial in task_order(items)]}


def run(source, output_dir, *, endpoint="http://127.0.0.1:8791/v1/systemone", model_alias="open-jev",
        expected_model=None, expected_method=None, audit_only=False, timeout=300, draws=5000):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    items, reference_rows, published, provenance = load_benchmark(source)
    reference = summarize(reference_rows, items, draws)
    for field in ("correct", "accuracy", "pair_joint_accuracy", "semantic_consistency", "groups"):
        if reference[field] != published[field]:
            raise ValueError(f"Recomputed Jev reference differs from published {field}")
    if draws == 5000 and reference["accuracy_95ci"] != published["accuracy_95ci"]:
        raise ValueError("Recomputed Jev reference bootstrap differs from published interval")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ("manifest.json", "requests.jsonl", "outcomes.jsonl", "summary.json", "audit.json")):
        raise ValueError("Use a fresh output directory; previous trials are not overwritten")
    manifest = make_manifest(items, provenance, model_alias)
    manifest.update(endpoint=endpoint, expected_model=expected_model, expected_method=expected_method)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    # Request export contains no item gold, rationale, difficulty or answers.
    (output / "requests.jsonl").write_text("".join(json.dumps({"item_id": item["id"], "trial": trial,
                                                              "request": build_request(item, trial, model_alias)}, ensure_ascii=False) + "\n"
                                                  for item, trial in task_order(items)))
    (output / "UPSTREAM_LICENSE.txt").write_bytes((Path(source) / "LICENSE").read_bytes())
    if audit_only:
        audit = {"status": "source_and_reference_verified", "inference_requests": 0, "reference": reference,
                 "source_commit": SOURCE_COMMIT, "dataset_sha256": SOURCE_FILES["data/items.jsonl"]}
        (output / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
        return audit
    rows, identity = [], None
    current = None
    try:
        with (output / "outcomes.jsonl").open("w") as handle, (output / "attempts.jsonl").open("w") as attempts_file:
            for item, trial in task_order(items):
                current = {"item_id": item["id"], "trial": trial}
                payload = build_request(item, trial, model_alias)
                attempts = []
                for number in range(2):
                    result = http_request(endpoint, payload, timeout)
                    attempts.append(result)
                    attempts_file.write(json.dumps({**current, "request_sha256": digest(payload), "attempt": number, **result}, ensure_ascii=False, allow_nan=False) + "\n")
                    attempts_file.flush()
                    if result["http_status"] not in RETRY_STATUSES:
                        break
                    if number == 0:
                        time.sleep(2)
                if result["http_status"] in (401, 402, 403):
                    raise ValueError("HTTP authentication/access error; evaluation stopped")
                response, answer, error = result["body"], None, None
                status = "service_error" if result["http_status"] != 200 else "ok"
                if status == "ok":
                    if not isinstance(response, dict):
                        status, error = "invalid_output", "Response was not a JSON object"
                    else:
                        received_identity = _service_identity(response)
                        if expected_model is not None and received_identity["model"] != expected_model:
                            raise ValueError("Returned model differs from expected model")
                        if expected_method is not None and received_identity["method"] != expected_method:
                            raise ValueError("Returned method differs from expected method")
                        if identity is not None and received_identity != identity:
                            raise ValueError("Model/checkpoint/code identity changed during JF100 evaluation")
                        identity = received_identity
                        try:
                            answer = validate_choice_response(response)
                        except ValueError as problem:
                            status, error = "invalid_output", str(problem)
                gold = presented_gold(item, trial)
                row = {**current, "pair_id": item["pair_id"], "domain": item["domain"], "difficulty": item["difficulty"],
                       "request": payload, "request_sha256": digest(payload), "state_sha256": digest(item["state"]),
                       "reference_trial_seed": TRIAL_SEEDS[trial], "stochastic_seed": None,
                       "gold": gold, "answer": answer, "correct": status == "ok" and answer == gold,
                       "status": status, "error": error, "elapsed_ms": sum(attempt["elapsed_ms"] for attempt in attempts),
                       "response": response, "attempts": attempts, "service_identity": identity,
                       "timestamp_utc": datetime.now(timezone.utc).isoformat()}
                handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                handle.flush()
                rows.append(row)
                print(json.dumps({"completed": len(rows), **current, "status": status}), flush=True)
        audit_outcomes(rows, items, expected_model=model_alias)
        local = summarize(rows, items, draws)
        report = {"status": "complete", "evaluation_only": True, "service_identity": identity,
                  "source_commit": SOURCE_COMMIT, "dataset_sha256": SOURCE_FILES["data/items.jsonl"],
                  "local": local, "published_jev_reference": reference,
                  "local_minus_jev": paired_comparison(local, reference, draws),
                  "limits": ["100 AI-assisted synthetic English questions without independent expert review",
                             "Three option rotations, not independent stochastic samples; no majority vote or best-of",
                             "Published Jev 1.13.0 is a reused dated reference, not new API inference",
                             "Open-Jev discriminative scoring differs from Q8_0 autoregressive thinking budgets on Apple M5 Max",
                             "Hardware, precision, inference interfaces and timing conditions differ; latency is descriptive",
                             "Exploratory paired-template intervals; not a general reasoning ceiling or equivalence test"]}
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        return report
    except Exception as error:
        (output / "failure.json").write_text(json.dumps({"current": current, "completed": len(rows),
                                                       "error_type": type(error).__name__, "error": str(error)}, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="External checkout at the pinned upstream commit")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--model-alias", default="open-jev")
    parser.add_argument("--expected-model")
    parser.add_argument("--expected-method", choices=sorted(LEARNED_METHODS))
    parser.add_argument("--audit-only", action="store_true", help="Verify source/reference and export target-free requests; no network inference")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--draws", type=int, default=5000)
    report = run(**vars(parser.parse_args()))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
