"""Evaluate frozen synthetic drone snapshots through a real HTTP service.

This measures disclosed snapshot rules, not flight or closed-loop outcomes.
Failures and pending cases stay in accuracy denominators. Probability errors
use only complete valid responses and always report their coverage.
"""

import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http.client import HTTPException
import json
import math
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from jev.api import compile_request, format_response
from jev.case_drone import VERSION, derive_decision
from jev.community import drone_request, drone_proposal
from jev.data import SPLITS
from scripts.evaluate_browser_service import METHODS, encoded, rank, sha256


METRICS = ("maneuver", "forced_maneuver", "risk_level", "target_loss", "complete_decision")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("non-finite JSON constant: " + value)

    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    encoded(result)
    return result


def number(value):
    if type(value) not in (int, float):
        raise ValueError("numeric fields cannot be booleans or strings")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("numeric fields must be finite")
    return value


def case_identity(case):
    return {"case_id": case["id"], "group_id": case["group_id"], "split": case["split"],
            "variant": case["variant"], "request_sha256": sha256(encoded(case["request"]))}


def select_cases(cases, splits=("test", "ood"), parents_per_split=20,
                 variants_per_parent=3, seed=42, max_cases=None):
    """Select by parent/case ID hashes without consulting answers or derivations."""
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"test", "ood"}:
        raise ValueError("splits must be distinct held-out test/ood names")
    for value in (parents_per_split, variants_per_parent):
        if type(value) is not int or value < 1:
            raise ValueError("parent and variant limits must be positive integers")
    if type(seed) is not int or (max_cases is not None and (type(max_cases) is not int or max_cases < 1)):
        raise ValueError("seed must be an integer and max_cases must be positive when supplied")
    pools = {split: defaultdict(list) for split in splits}
    ids, groups, inputs = set(), {}, {}
    for case in cases:
        identifier, group, split = case.get("id"), case.get("group_id"), case.get("split")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("case IDs must be nonempty and unique")
        if not isinstance(group, str) or not group or split not in SPLITS or case.get("source") != VERSION:
            raise ValueError("invalid drone case source/group/split")
        if not isinstance(case.get("variant"), str) or not case["variant"]:
            raise ValueError("case variant must be nonempty text")
        if groups.setdefault(group, split) != split:
            raise ValueError("parent group crosses split boundaries")
        request = case.get("request")
        if not isinstance(request, dict) or set(request) != {"state", "questions"}:
            raise ValueError("case requires an exact state/questions request")
        if inputs.setdefault(rank(request), split) != split:
            raise ValueError("identical runtime request crosses split boundaries")
        ids.add(identifier)
        if split in pools:
            pools[split][group].append(case)
    ranked = {}
    for split in splits:
        if len(pools[split]) < parents_per_split:
            raise ValueError(f"{split}: insufficient parent groups")
        parents = sorted(pools[split], key=lambda group: rank([seed, split, group]))[:parents_per_split]
        ranked[split] = [sorted(pools[split][group], key=lambda case: rank([seed, case["id"]]))[:variants_per_parent]
                         for group in parents]
    selected = [ranked[split][parent][variant]
                for variant in range(variants_per_parent) for parent in range(parents_per_split) for split in splits
                if variant < len(ranked[split][parent])]
    return selected if max_cases is None else selected[:max_cases]


def validate_case(case):
    request = case["request"]
    observation = request["state"]["observation"]
    expected = drone_request(observation, observation["permitted_maneuvers"])
    if encoded(request) != encoded(expected):
        raise ValueError("case changed the exact ordered drone runtime request")
    answers, derivation = derive_decision(request["state"])
    if case.get("answers") != answers or case.get("derivation") != derivation:
        raise ValueError("saved drone answers/derivation disagree with the visible-state teacher")
    records = {record["id"]: record for record in compile_request(**request)}
    if any(answer not in records[key]["answer_keys"] for key, answer in answers.items()):
        raise ValueError("reference answer is not a runtime candidate")
    return records


def service_identity(response, records, expected):
    if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
        raise ValueError("service response lacks model metadata")
    metadata = response["metadata"]
    identity = {"model": response.get("model"), **{key: metadata.get(key) for key in (
        "method", "base_revision", "checkpoint_sha256", "temperature", "code_commit", "max_length")}}
    if not isinstance(identity["model"], str) or not identity["model"]:
        raise ValueError("service must identify its model")
    if not isinstance(identity["base_revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", identity["base_revision"]):
        raise ValueError("service must report an exact 40-character base revision")
    if identity["method"] not in METHODS or number(identity["temperature"]) <= 0:
        raise ValueError("invalid learned scoring method or calibration temperature")
    checkpoint = identity["checkpoint_sha256"]
    if identity["method"] == "lora_decision_head" or checkpoint is not None:
        if not isinstance(checkpoint, str) or not re.fullmatch(r"[0-9a-f]{64}", checkpoint):
            raise ValueError("checkpoint scorer must report its checkpoint SHA-256")
    if identity["code_commit"] is not None and (not isinstance(identity["code_commit"], str) or not identity["code_commit"]):
        raise ValueError("invalid service code commit")
    if identity["max_length"] is not None and (type(identity["max_length"]) is not int or identity["max_length"] < 1):
        raise ValueError("invalid service context limit")
    # Noul has two answer probabilities but only ONE Yes/No scoring sequence.
    sequences = sum(1 if record["kind"] == "noul" else len(record["options"]) for record in records.values())
    if type(metadata.get("candidate_sequences")) is not int or metadata["candidate_sequences"] != sequences:
        raise ValueError("candidate sequence count does not match the complete request")
    if any(value is not None and identity[key] != value for key, value in expected.items()):
        raise ValueError("service identity differs from the expected value")
    return identity


def validate_response(response, records):
    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(answers, dict) or set(answers) != set(records):
        raise ValueError("response must answer exactly all requested heads")
    fields = {"choice": {"type", "choice", "probabilities", "confidence"},
              "score": {"type", "score", "probabilities", "confidence", "legend"},
              "noul": {"type", "noul"}}
    probabilities = []
    for key, record in records.items():
        answer, kind = answers[key], record["kind"]
        if not isinstance(answer, dict) or set(answer) != fields[kind] or answer["type"] != kind:
            raise ValueError("typed answer has missing, extra or incorrect fields: " + key)
        if kind == "noul":
            p = number(answer["noul"])
            probabilities.append([1 - p, p])
        else:
            values = answer["probabilities"]
            if not isinstance(values, dict) or set(values) != set(record["answer_keys"]):
                raise ValueError("probabilities must cover exactly the offered candidates")
            probabilities.append([number(values[candidate]) for candidate in record["answer_keys"]])
    derived = format_response(list(records.values()), probabilities)["answers"]
    for key, expected in derived.items():
        actual, kind = answers[key], expected["type"]
        if kind == "choice":
            if (not isinstance(actual["choice"], str) or actual["choice"] not in expected["probabilities"]
                    or expected["probabilities"][actual["choice"]] != max(expected["probabilities"].values())):
                raise ValueError("Choice must select a maximum-probability candidate")
        if kind in ("choice", "score"):
            confidence = number(actual["confidence"])
            if not 0 <= confidence <= 1 or not math.isclose(confidence, expected["confidence"], rel_tol=1e-6, abs_tol=1e-6):
                raise ValueError("confidence differs from the typed probability formula")
        if kind == "score":
            value = number(actual["score"])
            if (not 0 <= value <= len(expected["probabilities"]) - 1
                    or not math.isclose(value, expected["score"], rel_tol=1e-6, abs_tol=1e-6)
                    or actual["legend"] != expected["legend"]):
                raise ValueError("Score scalar or legend differs from its distribution")
    return answers


def score_response(case, response, records):
    answers = validate_response(response, records)
    risk = answers["risk"]
    keys = records["risk"]["answer_keys"]
    # The lowest ordered risk index wins a modal tie; never round the expectation.
    level = max(keys, key=lambda key: risk["probabilities"][key])
    lost = answers["target_truly_lost"]["noul"] >= 0.5
    gold = case["answers"]
    maneuver_key = "forced_maneuver" if len(records["maneuver"]["options"]) == 1 else "maneuver"
    correct = {maneuver_key: int(answers["maneuver"]["choice"] == gold["maneuver"]),
               "risk_level": int(level == gold["risk"]), "target_loss": int(lost == (gold["target_truly_lost"] == "true"))}
    correct["complete_decision"] = int(all(correct.values()))
    error = risk["score"] - int(gold["risk"])
    probability_errors = {"risk_brier": sum((risk["probabilities"][key] - int(key == gold["risk"])) ** 2 for key in keys),
                          "risk_scalar_absolute_error": abs(error), "risk_scalar_squared_error": error ** 2,
                          "target_loss_brier": (answers["target_truly_lost"]["noul"] - int(gold["target_truly_lost"] == "true")) ** 2}
    return {"correct": correct, "probability_errors": probability_errors,
            "decision": {"maneuver": answers["maneuver"]["choice"], "risk_level": level, "target_truly_lost": lost},
            "proposal": drone_proposal(case["request"], response)}


def http_attempt(endpoint, body, timeout):
    started, status, raw, error = time.perf_counter(), None, b"", None
    request = Request(endpoint, body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status, error = exc.code, f"HTTP {exc.code}"
        try:
            with exc:
                raw = exc.read()
        except (OSError, HTTPException) as read_error:
            raw = getattr(read_error, "partial", b"")
            error += f"; {type(read_error).__name__}: {read_error}"
    except (URLError, OSError, TimeoutError, HTTPException) as exc:
        raw = getattr(exc, "partial", b"")
        error = f"{type(exc).__name__}: {exc}"
    return {"http_status": status, "response_body_base64": base64.b64encode(raw).decode(),
            "response_body_sha256": sha256(raw), "elapsed_seconds": time.perf_counter() - started,
            "transport_error": error}, raw


def summarize(cases, outcomes, records_by_case):
    by_id = {row["case_id"]: row for row in outcomes}
    totals = Counter(risk_level=len(cases), target_loss=len(cases), complete_decision=len(cases))
    correct, risk_gold, risk_predicted, maneuvers, losses, sums, distribution = (Counter() for _ in range(7))
    valid = 0
    for case in cases:
        gold = case["answers"]
        key = "forced_maneuver" if len(records_by_case[case["id"]]["maneuver"]["options"]) == 1 else "maneuver"
        totals[key] += 1
        risk_gold[gold["risk"]] += 1
        maneuvers[gold["maneuver"]] += 1
        losses[gold["target_truly_lost"]] += 1
        row = by_id.get(case["id"])
        if row is not None and row["status"] == "ok":
            valid += 1
            correct.update(row["correct"])
            sums.update(row["probability_errors"])
            distribution.update(row["response"]["answers"]["risk"]["probabilities"])
            risk_predicted[row["decision"]["risk_level"]] += 1
    return {"cases": len(cases), "parents": len({case["group_id"] for case in cases}),
            "variants": dict(sorted(Counter(case["variant"] for case in cases).items())),
            "reference_maneuvers": dict(sorted(maneuvers.items())), "reference_target_loss": dict(sorted(losses.items())),
            "metrics": {name: {"correct": correct[name], "total": totals[name],
                               "accuracy": correct[name] / totals[name] if totals[name] else None} for name in METRICS},
            "probability_metrics_valid_only": {"valid_cases": valid, "selected_cases": len(cases),
                "coverage": valid / len(cases) if cases else None,
                **{name: sums[name] / valid if valid else None for name in (
                    "risk_brier", "risk_scalar_absolute_error", "risk_scalar_squared_error", "target_loss_brier")},
                "risk_mean_probabilities": {str(i): distribution[str(i)] / valid if valid else None for i in range(3)}},
            "risk_level_counts": {"reference_all_selected": {str(i): risk_gold[str(i)] for i in range(3)},
                                  "predicted_valid_only": {str(i): risk_predicted[str(i)] for i in range(3)}}}


def run_evaluation(cases_path, output_dir, *, endpoint="http://127.0.0.1:8791/v1/systemone",
                   splits=("test", "ood"), parents_per_split=20, variants_per_parent=3, seed=42,
                   max_cases=None, model_alias="open-jev", expected_model=None, expected_method=None,
                   expected_revision=None, expected_checkpoint_sha256=None, timeout=300):
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must be an HTTP(S) URL without credentials, query or fragment")
    if number(timeout) <= 0:
        raise ValueError("timeout must be positive")
    for value, pattern in ((expected_revision, r"[0-9a-f]{40}"), (expected_checkpoint_sha256, r"[0-9a-f]{64}")):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(pattern, value)):
            raise ValueError("expected artifact identity must be an exact revision/hash")
    source, output = Path(cases_path), Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output directory must be empty or absent")
    source_bytes, manifest_bytes = source.read_bytes(), source.with_name("manifest.json").read_bytes()
    manifest = strict_json(manifest_bytes)
    all_cases = [strict_json(line) for line in source_bytes.splitlines() if line.strip()]
    if (manifest.get("cases_file") != source.name or manifest.get("cases_sha256") != sha256(source_bytes)
            or type(manifest.get("case_count")) is not int or manifest["case_count"] != len(all_cases)):
        raise ValueError("cases file checksum/count does not match its frozen manifest")
    cases = select_cases(all_cases, splits, parents_per_split, variants_per_parent, seed, max_cases)
    records_by_case = {case["id"]: validate_case(case) for case in cases}
    expected = {"model": expected_model, "method": expected_method,
                "base_revision": expected_revision, "checkpoint_sha256": expected_checkpoint_sha256}
    repo = Path(__file__).resolve().parents[1]
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "source": str(source),
                 "source_sha256": sha256(source_bytes), "source_manifest_sha256": sha256(manifest_bytes),
                 "evaluator_sha256": sha256(Path(__file__).read_bytes()),
                 "dependencies_sha256": {name: sha256((repo / name).read_bytes()) for name in (
                     "scripts/evaluate_browser_service.py", "jev/api.py", "jev/metrics.py", "jev/community.py", "jev/case_drone.py")},
                 "endpoint": endpoint, "model_alias": model_alias, "expected_identity": expected,
                 "splits": list(splits), "parents_per_split": parents_per_split, "variants_per_parent": variants_per_parent,
                 "seed": seed, "max_cases": max_cases,
                 "selection_rule": "SHA-256 rank of parent IDs, then case IDs; round-robin split/parent truncation; no labels",
                 "risk_level_rule": "first modal index in ordered levels 0,1,2; not rounded Score expectation",
                 "target_loss_threshold": 0.5, "cases": [case_identity(case) for case in cases]}
    selection["selection_sha256"] = rank(selection["cases"])
    output.mkdir(parents=True, exist_ok=True)

    def write_json(name, value, mode="w"):
        with (output / name).open(mode) as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

    # Exclusive creation also rejects another evaluator racing for this directory.
    write_json("selection.json", selection, "x")
    with (output / "source-manifest.json").open("xb") as handle:
        handle.write(manifest_bytes)
    bodies = []
    with (output / "requests.jsonl").open("x") as requests, (output / "references.jsonl").open("x") as references:
        for case in cases:
            body = encoded({"model": model_alias, **case["request"]})
            bodies.append(body)
            requests.write(encoded({**case_identity(case), "request_json": body.decode(), "request_body_sha256": sha256(body)}).decode() + "\n")
            references.write(encoded({**case_identity(case), "answers": case["answers"], "derivation": case["derivation"]}).decode() + "\n")
    outcomes, identity, attempted = [], None, 0

    def report(status):
        return {"status": status, "complete": len(outcomes) == len(cases), "selected_cases": len(cases),
                "attempted_cases": attempted, "completed_attempts": len(outcomes), "pending_cases": len(cases) - len(outcomes),
                "not_dispatched_cases": len(cases) - attempted, "error_cases": sum(row["status"] != "ok" for row in outcomes),
                "status_counts": dict(Counter(row["status"] for row in outcomes)), "service_identity": identity,
                "selection_sha256": selection["selection_sha256"], "source_sha256": selection["source_sha256"],
                "overall": summarize(cases, outcomes, records_by_case),
                "by_split": {split: summarize([case for case in cases if case["split"] == split], outcomes, records_by_case) for split in splits},
                "scope": "Synthetic snapshot-rule decisions only; no flight or closed-loop outcomes. All selected cases stay in accuracy denominators; failed/pending cases score zero. Probability errors use complete valid responses only, with coverage. Forced maneuvers are separate. Complete decision requires maneuver, modal risk level, and Noul>=0.5 labels to match."}

    write_json("report.json", report("running"))
    try:
        with (output / "outcomes.jsonl").open("x") as results:
            for case, body in zip(cases, bodies):
                attempted += 1
                attempt, raw = http_attempt(endpoint, body, timeout)
                outcome = {**case_identity(case), **attempt, "request_body_sha256": sha256(body),
                           "status": "http_error", "service_identity": None, "response": None}
                if attempt["transport_error"] is None and attempt["http_status"] == 200:
                    stage = "schema_error"
                    try:
                        response = strict_json(raw)
                        outcome["response"] = response
                        stage = "identity_error"
                        received = service_identity(response, records_by_case[case["id"]], expected)
                        outcome["service_identity"] = received
                        if identity is not None and identity != received:
                            raise ValueError("service identity/configuration changed during evaluation")
                        identity = received
                        stage = "schema_error"
                        outcome.update(score_response(case, response, records_by_case[case["id"]]), status="ok")
                    except (ValueError, TypeError, KeyError, OverflowError) as exc:
                        outcome.update(status=stage, error=f"{type(exc).__name__}: {exc}")
                outcomes.append(outcome)
                results.write(encoded(outcome).decode() + "\n")
                results.flush()
                write_json("report.json", report("running"))
    except BaseException:
        write_json("report.json", report("interrupted"))
        raise
    final = report("complete_with_errors" if any(row["status"] != "ok" for row in outcomes) else "complete")
    write_json("report.json", final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", dest="cases_path", type=Path, default=Path("data/drone-control-v1/cases.jsonl"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--split", dest="splits", nargs="+", choices=("test", "ood"), default=["test", "ood"])
    parser.add_argument("--parents-per-split", type=int, default=20)
    parser.add_argument("--variants-per-parent", type=int, default=3)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-alias", default="open-jev")
    parser.add_argument("--expected-model")
    parser.add_argument("--expected-method", choices=sorted(METHODS))
    parser.add_argument("--expected-revision")
    parser.add_argument("--expected-checkpoint-sha256")
    parser.add_argument("--timeout", type=float, default=300)
    args = vars(parser.parse_args())
    try:
        result = run_evaluation(**args)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Drone evaluation configuration/artifact error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output_dir": str(args["output_dir"]), **result}, indent=2))
    return int(result["error_cases"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
