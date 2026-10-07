"""Evaluate real HTTP predictions against held-out local workflow policy labels.

Selection never reads targets. All HTTP responses are saved with exact case,
state and request identities. Fixture or oracle inference is not supported.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import time

from jev.api import compile_request
from jev.case_workflows import evaluate_predictions
from jev.client import Client
from jev.data import SPLITS, read_jsonl
from jev.workflows import ACTION_RULES, select_actions


LEARNED_METHODS = {"lora_decision_head", "pretrained_yes_minus_no_no_training"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def case_identity(case):
    """No labels or reference actions are part of the model request identity."""
    return {"case_id": case["case_id"], "group_id": case["group_id"],
            "workflow": case["workflow"], "split": case["split"],
            "state_sha256": digest(case["state"]),
            "questions_sha256": digest(case["questions"]),
            "request_sha256": digest({"state": case["state"], "questions": case["questions"]})}


def select_cases(cases, splits=("test", "ood"), per_workflow=12, seed=42):
    """Sample one variant per parent, balanced by workflow and held-out split.

    All rows are checked before selection, including cross-split group leakage.
    Ranking uses only identifiers and seed, never labels or policy outcomes.
    """
    if type(per_workflow) is not int or per_workflow < 1:
        raise ValueError("per_workflow must be a positive integer")
    if not splits or len(set(splits)) != len(splits) or any(split not in ("test", "ood") for split in splits):
        raise ValueError("splits must be distinct held-out test/ood names")
    identifiers, groups, inputs = set(), {}, {}
    pools = {(workflow, split): {} for split in splits for workflow in ACTION_RULES}
    for case in cases:
        identifier, group = case.get("case_id"), case.get("group_id")
        workflow, split = case.get("workflow"), case.get("split")
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("case IDs must be nonempty unique strings")
        if not isinstance(group, str) or not group or workflow not in ACTION_RULES or split not in SPLITS:
            raise ValueError(f"invalid workflow, split or group in {identifier}")
        identity = (workflow, split)
        if group in groups and groups[group] != identity:
            raise ValueError(f"parent group crosses workflow/split boundaries: {group}")
        if not {"state", "questions"} <= case.keys():
            raise ValueError(f"missing request fields in {identifier}")
        request_hash = digest({"state": case["state"], "questions": case["questions"]})
        if request_hash in inputs and inputs[request_hash] != split:
            raise ValueError(f"identical model input crosses splits: {identifier}")
        inputs[request_hash] = split
        identifiers.add(identifier)
        groups[group] = identity
        if split in splits:
            pools[(workflow, split)].setdefault(group, []).append(case)
    selected = []
    for split in splits:
        for workflow in ACTION_RULES:
            available = pools[(workflow, split)]
            if len(available) < per_workflow:
                raise ValueError(f"{workflow}/{split}: need {per_workflow} distinct parent groups; found {len(available)}")
            ranked = sorted(available, key=lambda group: digest([seed, workflow, split, group]))
            for group in ranked[:per_workflow]:
                selected.append(min(available[group], key=lambda case: digest([seed, case["case_id"]])))
    return selected


def validate_case(case):
    """Check saved local references without invoking a fixture/oracle function."""
    if case.get("reference_kind") != "deterministic_synthetic_policy_fixture":
        raise ValueError("only this independently generated local policy dataset is supported")
    records = compile_request(case["state"], case["questions"])
    expected = set(ACTION_RULES[case["workflow"]])
    if {record["id"] for record in records} != expected or any(record["kind"] != "noul" for record in records):
        raise ValueError("case question IDs/types do not exactly match the workflow")
    if set(case.get("targets", {})) != expected:
        raise ValueError("case target IDs do not exactly match the workflow")
    positive = set()
    for action, target in case["targets"].items():
        if target not in ([1.0, 0.0], [0.0, 1.0]):
            raise ValueError("this evaluator requires binary local policy references")
        if target[1] == 1:
            positive.add(action)
    reference = case.get("reference_actions")
    if not isinstance(reference, list) or len(reference) != len(set(reference)) or set(reference) != positive:
        raise ValueError("reference action set disagrees with saved targets")


def response_identity(case, response, *, expected_model=None, expected_method=None):
    """Fail before scoring responses from a mismatched or non-learned backend."""
    if not isinstance(response, dict):
        raise ValueError("response must be an object")
    model, metadata = response.get("model"), response.get("metadata")
    if not isinstance(model, str) or not model or not isinstance(metadata, dict):
        raise ValueError("response lacks model/method metadata")
    method = metadata.get("method")
    if method not in LEARNED_METHODS:
        raise ValueError(f"service method is not an accepted learned scorer: {method!r}")
    if expected_model is not None and model != expected_model:
        raise ValueError(f"returned model {model!r} differs from expected model {expected_model!r}")
    if expected_method is not None and method != expected_method:
        raise ValueError(f"returned method {method!r} differs from expected method {expected_method!r}")
    temperature = metadata.get("temperature")
    if type(temperature) not in (int, float) or not 0 < temperature < float("inf"):
        raise ValueError("response requires a finite positive calibration temperature")
    if set(response.get("answers", {})) != set(case["questions"]):
        raise ValueError("response question IDs do not exactly match the submitted case")
    select_actions(case["workflow"], response)  # Validate all typed probabilities.
    if metadata.get("candidate_sequences") != len(case["questions"]):
        raise ValueError("response sequence count disagrees with submitted Noul questions")
    identity = {"model": model, "method": method, "temperature": temperature}
    for field in ("checkpoint_sha256", "base_revision", "code_commit"):
        if field in metadata:
            value = metadata[field]
            if not isinstance(value, str) or not value:
                raise ValueError(f"invalid service provenance field: {field}")
            if field == "checkpoint_sha256" and not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError("checkpoint_sha256 must be a SHA-256 hex digest")
            identity[field] = value
    return identity


def validate_prediction_identities(cases, predictions):
    """Prevent accidentally scoring a reordered/mislabeled response export."""
    expected = {case["case_id"]: case_identity(case) for case in cases}
    seen = set()
    for prediction in predictions:
        identifier = prediction.get("case_id")
        if identifier not in expected or identifier in seen:
            raise ValueError("unknown or duplicate prediction case ID")
        for key, value in expected[identifier].items():
            if prediction.get(key) != value:
                raise ValueError(f"prediction {identifier} mismatches {key}")
        seen.add(identifier)
    if seen != set(expected):
        raise ValueError("predictions do not cover the exact selected cases")


def run_evaluation(cases_path, output_dir, *, endpoint="http://127.0.0.1:8791/v1/systemone",
                   splits=("test", "ood"), per_workflow=12, seed=42, model_alias="open-jev",
                   expected_model=None, expected_method=None, checkpoint_id=None,
                   timeout=300, client=None):
    """Run every selected case over HTTP; preserve partial logs on any failure."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    source = Path(cases_path)
    cases = select_cases(read_jsonl(source), splits, per_workflow, seed)
    for case in cases:
        validate_case(case)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    # Separate invocation directories avoid conflating checkpoints or replacing a
    # previous report with a partial failing run.
    artifacts = ("selected_cases.jsonl", "selection.json", "predictions.jsonl", "responses.jsonl", "report.json", "failure.json")
    if any((output / name).exists() for name in artifacts):
        raise ValueError("output directory already contains evaluation artifacts; choose a fresh directory")
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                 "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                 "splits": list(splits), "per_workflow_per_split": per_workflow, "seed": seed,
                 "rule": "sha256 rank of parent IDs then one case variant; label independent",
                 "endpoint": endpoint, "requested_model_alias": model_alias,
                 "checkpoint_id": checkpoint_id, "checkpoint_id_source": "caller_supplied_not_server_verified" if checkpoint_id else "not_exposed_by_service",
                 "cases": [case_identity(case) for case in cases]}
    (output / "selection.json").write_text(json.dumps(selection, indent=2, ensure_ascii=False) + "\n")
    (output / "selected_cases.jsonl").write_text("".join(json.dumps(case, ensure_ascii=False, allow_nan=False) + "\n" for case in cases))
    client = client or Client(endpoint, timeout=timeout)
    predictions, stable_identity = [], None
    start = time.perf_counter()
    current_case = None
    try:
        with (output / "predictions.jsonl").open("w") as handle, (output / "responses.jsonl").open("w") as raw_handle:
            for case in cases:
                current_case = case["case_id"]
                started = time.perf_counter()
                response = client.ask(state=case["state"], questions=case["questions"], model=model_alias)
                raw_handle.write(json.dumps({**case_identity(case), "response": response}, ensure_ascii=False, allow_nan=False) + "\n")
                raw_handle.flush()
                identity = response_identity(case, response, expected_model=expected_model, expected_method=expected_method)
                if stable_identity is not None and identity != stable_identity:
                    raise ValueError("model, method, calibration or artifact/code identity changed during evaluation")
                stable_identity = identity
                prediction = {**case_identity(case), "predictor_kind": "learned", "service_identity": identity,
                              "elapsed_seconds": time.perf_counter() - started, "response": response}
                handle.write(json.dumps(prediction, ensure_ascii=False, allow_nan=False) + "\n")
                handle.flush()
                predictions.append(prediction)
        validate_prediction_identities(cases, predictions)
        report = evaluate_predictions(cases, predictions)
        report["by_split"] = {split: evaluate_predictions([case for case in cases if case["split"] == split],
                                                         [prediction for prediction in predictions if prediction["split"] == split])
                              for split in splits}
        report.update(service_identity=stable_identity, checkpoint_sha256=stable_identity.get("checkpoint_sha256"), checkpoint_id=checkpoint_id,
                      checkpoint_id_source=selection["checkpoint_id_source"],
                      endpoint=endpoint, source_sha256=selection["source_sha256"],
                      selection_sha256=digest(selection["cases"]),
                      case_counts=dict(sorted(Counter(f"{case['workflow']}/{case['split']}" for case in cases).items())),
                      elapsed_seconds=time.perf_counter() - start,
                      scope="Learned HTTP predictions against synthetic local policy references; no official-eval quality claim.")
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        return report
    except Exception as error:
        (output / "failure.json").write_text(json.dumps({"case_id": current_case, "completed_cases": len(predictions),
                                                       "error_type": type(error).__name__, "error": str(error)}, ensure_ascii=False, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/workflows-v1/workflow_cases.jsonl"))
    parser.add_argument("--split", dest="splits", nargs="+", choices=("test", "ood"), default=["test", "ood"])
    parser.add_argument("--per-workflow", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--model-alias", default="open-jev")
    parser.add_argument("--expected-model")
    parser.add_argument("--expected-method", choices=sorted(LEARNED_METHODS))
    parser.add_argument("--checkpoint-id")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = vars(parser.parse_args())
    args["cases_path"] = args.pop("cases")
    report = run_evaluation(**args)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
