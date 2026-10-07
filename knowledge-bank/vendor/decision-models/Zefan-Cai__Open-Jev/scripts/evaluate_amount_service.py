"""HTTP evaluation of frozen amount controls; B always follows A's actual span."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from jev.api import compile_request
from jev.case_amount_extraction import amount_selection, amount_attributes, selection_reference, normalize_amount
from scripts.evaluate_contact_service import CASE_ID_PREFIX, SPLITS, call_stage, case_identity, file_hash, metric
from scripts.evaluate_browser_service import encoded, rank, sha256
from scripts.evaluate_drone_service import http_attempt, strict_json

ROOT = Path(__file__).resolve().parents[1]
VERSION = "amount-extraction-control-v1"
MANIFEST_SHA256 = "6f89f81336ac36505c563193da27fca2155fa566175451854f0ac410979ea80b"
IMPLEMENTATION_FILES = (
    "scripts/evaluate_amount_service.py", "scripts/evaluate_contact_service.py",
    "scripts/evaluate_browser_service.py", "scripts/evaluate_drone_service.py", "jev/metrics.py",
)


def check_inputs(data_root):
    directory = Path(data_root)/VERSION
    raw = (directory/"manifest.json").read_bytes()
    if sha256(raw) != MANIFEST_SHA256:
        raise ValueError("Amount manifest differs from the frozen control corpus")
    manifest = strict_json(raw)
    if set(manifest["files_sha256"]) != {f"{split}.jsonl" for split in SPLITS} | {"families.jsonl", "cases.jsonl"}:
        raise ValueError("Unexpected amount artifact manifest")
    for name, digest in manifest["files_sha256"].items():
        if file_hash(directory/name) != digest:
            raise ValueError("Changed amount corpus artifact: " + name)
    for name, digest in manifest["configuration"]["source_files_sha256"].items():
        if Path(name).name != name or file_hash(ROOT/"jev"/name) != digest:
            raise ValueError("Changed frozen amount producer source: " + name)
    return directory, manifest


def validate_case(case):
    request = case["selection_request"]
    if not isinstance(request, dict) or set(request) != {"state", "questions"}:
        raise ValueError("A must contain only the original state and questions")
    state = request["state"]
    expected = amount_selection(state["text"], state["requested_role"], locale=state["policy"]["locale"], layout=state["policy"]["layout"])
    if encoded(request) != encoded(expected) or case["selection_reference"] != selection_reference(request):
        raise ValueError("Amount request/reference differs from the frozen visible-input contract")
    candidates = state["candidates"]
    attributes = case["attributes"]
    if len(attributes) != len(candidates) or {item["candidate_id"] for item in attributes} != set(candidates):
        raise ValueError("Amount sidecar must contain one reference for every actual candidate")
    for item in attributes:
        ref = item["reference"]
        credit_type_valid = type(ref["is_credit"]) is bool if ref["direction_known"] else ref["is_credit"] is None
        if type(ref["direction_known"]) is not bool or not credit_type_valid:
            raise ValueError("Conditional credit reference must be boolean when defined and null otherwise")
    compile_request(**request)


def load_cases(data_root, splits=("test", "ood")):
    """Hash all files, but decode full case references only for held-out family IDs."""
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"test", "ood"}:
        raise ValueError("Only distinct test/ood splits are allowed")
    directory, manifest = check_inputs(data_root)
    families = [strict_json(line) for line in (directory/"families.jsonl").read_bytes().splitlines() if line.strip()]
    index, groups, family_ids = {}, {}, set()
    for family in families:
        if family["id"] in family_ids or family["split"] not in SPLITS:
            raise ValueError("Duplicate family or invalid split")
        family_ids.add(family["id"])
        if groups.setdefault(family["group_id"], family["split"]) != family["split"]:
            raise ValueError("A document group crosses splits")
        for identifier in family["case_ids"]:
            if identifier in index:
                raise ValueError("Duplicate case ID in family index")
            index[identifier] = family
    if len(families) != manifest["family_count"] or len(index) != manifest["document_count"]:
        raise ValueError("Family/case counts differ from the frozen manifest")
    cases, seen = [], set()
    with (directory/"cases.jsonl").open("rb") as stream:
        for raw in stream:
            if not raw.strip():
                continue
            prefix = CASE_ID_PREFIX.match(raw)
            if prefix is None:
                raise ValueError("Frozen amount JSONL must begin with its case ID")
            identifier = strict_json(prefix[1])
            if identifier not in index or identifier in seen:
                raise ValueError("Unexpected or duplicate case ID")
            seen.add(identifier)
            family = index[identifier]
            if family["split"] not in splits:
                continue
            case = strict_json(raw)
            if case["family_id"] != family["id"] or any(case[key] != family[key] for key in ("group_id", "split")):
                raise ValueError("Case identity differs from its indexed family")
            case["corpus"] = "amount"
            validate_case(case)
            cases.append(case)
    if seen != set(index) or any(not any(case["split"] == split for case in cases) for split in splits):
        raise ValueError("Incomplete amount population")
    cases.sort(key=lambda case: (("test", "ood").index(case["split"]), rank(["group", case["group_id"]]), rank(["case", case["id"]])))
    return cases, {"version": VERSION, "manifest_sha256": MANIFEST_SHA256,
                   "files_sha256": manifest["files_sha256"], "source_files_sha256": manifest["configuration"]["source_files_sha256"],
                   "selected_cases": len(cases), "split_counts": dict(Counter(case["split"] for case in cases))}


def evaluate_case(case, outcome, config, stable, requests, attempts, transport):
    original = case["selection_request"]
    outcome["a"] = call_stage(original, "A", case, config, stable, requests, attempts, transport)
    if outcome["a"]["status"] != "ok":
        outcome.update(status="a_error", b={"status": "not_attempted", "reason": "a_error"})
        return
    answers = outcome["a"]["answers"]
    selected_id = answers["span"]["choice"]
    outcome["a"]["prediction"] = {"span": selected_id, "target_present": answers["target_present"]["noul"] >= 0.5,
                                   "target_present_probability": answers["target_present"]["noul"]}
    if selected_id == "none":
        outcome.update(status="ok", b={"status": "not_attempted", "reason": "a_selected_none"})
        return
    outcome["selected"] = original["state"]["candidates"][selected_id]
    # No requested-role reference or gold span participates in dispatch.
    request = amount_attributes(original, selected_id)
    outcome["b"] = call_stage(request, "B", case, config, stable, requests, attempts, transport)
    if outcome["b"]["status"] != "ok":
        outcome["status"] = "b_error"
        return
    answers = outcome["b"]["answers"]
    prediction = {"currency": answers["currency"]["choice"], "direction_known": answers["direction_known"]["noul"] >= 0.5,
                  "is_credit": answers["is_credit"]["noul"] >= 0.5}
    outcome["b"]["prediction"] = prediction
    # Runtime gating uses the predicted known flag, never a reference condition.
    outcome.update(guard=normalize_amount(request, currency=prediction["currency"], direction_known=prediction["direction_known"],
                                          is_credit=prediction["is_credit"] if prediction["direction_known"] else None), status="ok")


def summarize(cases, outcomes):
    totals, correct, reasons, statuses, b_skips, b_statuses, guard_status = (Counter() for _ in range(7))
    undefined_credit = 0
    for case, outcome in zip(cases, outcomes):
        ref, request = case["selection_reference"], case["selection_request"]
        a, b = outcome.get("a", {}), outcome.get("b", {})
        a_ok, b_ok = a.get("status") == "ok", b.get("status") == "ok"
        prediction, attributes = a.get("prediction", {}), b.get("prediction", {})
        span_ok = a_ok and prediction.get("span") == ref["span"]
        eligible = a_ok and prediction.get("span") in request["state"]["candidates"]
        unique = len(ref["target_spans"]) == 1
        exact = unique and eligible and span_ok and outcome.get("selected") == ref["target_spans"][0]
        groups = ["a_presence", "a_span", "a_nonforced_span" if request["state"]["candidates"] else "a_forced_span",
                  "a_span_on_recalled" if ref["reason"] == "recalled" else "a_none_"+ref["reason"]]
        for name in groups:
            totals[name] += 1
            correct[name] += int(a_ok and prediction.get("target_present") == ref["target_present"]) if name == "a_presence" else int(span_ok)
        reasons[ref["reason"]] += 1
        statuses[outcome["status"]] += 1
        joint = False
        if eligible:
            actual = next(item["reference"] for item in case["attributes"] if item["candidate_id"] == prediction["span"])
            b_statuses[b.get("status", "not_built_or_pending")] += 1
            currency_ok = b_ok and attributes.get("currency") == actual["currency"]
            known_ok = b_ok and attributes.get("direction_known") == actual["direction_known"]
            credit_ok = b_ok and attributes.get("is_credit") == actual["is_credit"]
            for name, passed in (("b_currency_on_actual_selection", currency_ok), ("b_direction_known_on_actual_selection", known_ok)):
                totals[name] += 1
                correct[name] += int(passed)
            if actual["direction_known"]:
                totals["b_is_credit_on_reference_known_actual_selection"] += 1
                correct["b_is_credit_on_reference_known_actual_selection"] += int(credit_ok)
            else:
                undefined_credit += 1
            joint = bool(currency_ok and known_ok and (not actual["direction_known"] or credit_ok))
            totals["b_defined_attributes_joint_on_actual_selection"] += 1
            correct["b_defined_attributes_joint_on_actual_selection"] += int(joint)
        else:
            b_skips["a_selected_none" if a_ok else "a_not_valid_or_pending"] += 1
        expected = next((item["normalized_reference"] for item in case["attributes"] if item["candidate_id"] == ref["span"]), None)
        ready = unique and expected is not None and expected["status"] == "ready"
        guard = outcome.get("guard")
        # Compare exact Decimal strings; no float conversion, rounding or None equality.
        value_ok = bool(exact and joint and ready and guard and guard["status"] == "ready"
                        and (guard["currency"], guard["amount"]) == (expected["currency"], expected["amount"]))
        if unique:
            for name, passed in (("exact_raw_span_on_unique_target", exact), ("final_value_on_unique_target", value_ok),
                                 ("complete_output_on_unique_target", value_ok and prediction.get("target_present") is True)):
                totals[name] += 1
                correct[name] += int(passed)
            totals["reference_ready_coverage"] += 1
            correct["reference_ready_coverage"] += int(ready)
        if ready:
            totals["normalized_pair_on_reference_ready_target"] += 1
            correct["normalized_pair_on_reference_ready_target"] += int(value_ok)
        totals["guard_eligible"] += int(eligible)
        if guard is not None:
            correct["guard_eligible"] += 1
            guard_status[guard["status"]] += 1
            guard_status["reason:"+(guard.get("reason") or "accepted")] += 1
    return {"cases": len(cases), "families": len({case["group_id"] for case in cases}), "status_counts": dict(statuses),
            "metrics": {name: metric(correct[name], count) for name, count in sorted(totals.items()) if name not in ("guard_eligible", "reference_ready_coverage")},
            "reference_reasons": dict(reasons), "candidate_recall": metric(reasons["recalled"], reasons["recalled"]+reasons["candidate_miss"]),
            "reference_ready": {"cases": correct["reference_ready_coverage"], "unique_present_cases": totals["reference_ready_coverage"],
                                "coverage": correct["reference_ready_coverage"]/totals["reference_ready_coverage"] if totals["reference_ready_coverage"] else None},
            "b_not_attempted": dict(b_skips), "b_eligible_status_counts": dict(b_statuses), "actual_b_undefined_credit": undefined_credit,
            "guard": {"eligible_actual_non_none": totals["guard_eligible"], "executed": correct["guard_eligible"],
                      "all_case_denominator": len(cases), "status_and_reason_counts": dict(guard_status)}}


def run_evaluation(data_root, output_dir, *, splits=("test", "ood"), endpoint="http://127.0.0.1:8791/v1/systemone",
                   model_alias="open-jev", expected_model=None, expected_method=None, expected_revision=None,
                   expected_checkpoint_sha256=None, expected_temperature=None, timeout=300, transport=None):
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"test", "ood"}:
        raise ValueError("Only distinct test/ood splits are allowed")
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Endpoint must be HTTP(S), without credentials/query/fragment")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be finite and positive")
    if expected_method not in ("lora_decision_head", "pretrained_yes_minus_no_no_training") or not expected_model:
        raise ValueError("Expected model and accepted method are required")
    if not isinstance(expected_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_revision):
        raise ValueError("Expected revision must be an exact 40-character commit")
    if expected_method == "lora_decision_head" or expected_checkpoint_sha256 is not None:
        if not isinstance(expected_checkpoint_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_checkpoint_sha256):
            raise ValueError("Checkpoint runs require the expected checkpoint SHA-256")
    if expected_temperature is not None and (type(expected_temperature) not in (int, float) or not math.isfinite(expected_temperature) or expected_temperature <= 0):
        raise ValueError("Expected temperature must be finite and positive")
    data_root, output = Path(data_root), Path(output_dir)
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(data_root.resolve()):
        raise ValueError("Choose an absent output directory outside the immutable data root")
    cases, inputs = load_cases(data_root, splits)
    implementation = {name: file_hash(ROOT/name) for name in IMPLEMENTATION_FILES}
    config = {"endpoint": endpoint, "model_alias": model_alias, "timeout": timeout,
              "expected_identity": {"model": expected_model, "method": expected_method, "base_revision": expected_revision,
                                    "checkpoint_sha256": expected_checkpoint_sha256, "temperature": expected_temperature}}
    mode = "software_fixture" if transport is not None else "http_service_evaluation"
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "evidence_kind": mode, "inputs": inputs,
                 "implementation_sha256": implementation, "configuration": config, "splits": list(splits),
                 "selection_rule": "All requested held-out cases; test then OOD, SHA-256(group ID), SHA-256(case ID); no labels or sampling",
                 "noul_threshold": 0.5, "cases": [case_identity(case) for case in cases]}
    selection["ordered_cases_sha256"] = rank(selection["cases"])
    output.mkdir(parents=True, exist_ok=False)
    (output/"selection.json").write_bytes(encoded(selection))
    with (output/"references.jsonl").open("x") as stream:
        for case in cases:
            stream.write(encoded({**case_identity(case), "a_reference": case["selection_reference"],
                "b_references": [{key: item[key] for key in ("candidate_id", "reference", "normalized_reference")} for item in case["attributes"]]}).decode()+"\n")
    outcomes = [{**case_identity(case), "status": "pending"} for case in cases]
    stable, state, written = {}, "running", 0
    try:
        with (output/"requests.jsonl").open("x") as requests, (output/"attempts.jsonl").open("x") as attempts, (output/"outcomes.jsonl").open("x") as results:
            for case, outcome in zip(cases, outcomes):
                try:
                    evaluate_case(case, outcome, config, stable, requests, attempts, http_attempt if transport is None else transport)
                except Exception as error:
                    outcome.update(status="pipeline_error", error_type=type(error).__name__, error=str(error))
                finally:
                    results.write(encoded(outcome).decode()+"\n")
                    results.flush()
                    written += 1
        check_inputs(data_root)
        if implementation != {name: file_hash(ROOT/name) for name in IMPLEMENTATION_FILES}:
            raise ValueError("Evaluator/helper implementation changed during the run")
        state = "complete" if all(row["status"] == "ok" for row in outcomes) else "completed_with_errors"
    except BaseException:
        state = "interrupted_or_failed"
        raise
    finally:
        # Keep unattempted documents visible in artifacts as well as denominators.
        if written < len(outcomes):
            with (output/"outcomes.jsonl").open("a") as results:
                for outcome in outcomes[written:]:
                    results.write(encoded(outcome).decode()+"\n")
        report = {"status": state, "evidence_kind": mode,
                  "is_model_quality_evidence": mode == "http_service_evaluation" and state == "complete" and bool(stable),
                  "service_identity": stable or None, "ordered_cases_sha256": selection["ordered_cases_sha256"],
                  "documents": len(cases), "summary": summarize(cases, outcomes),
                  "by_split": {split: summarize([case for case in cases if case["split"] == split],
                                               [row for row in outcomes if row["split"] == split]) for split in splits},
                  "limitations": [
                      "Frozen synthetic invoice controls; not arbitrary invoice/PDF/OCR understanding or a payment authorization.",
                      "This corpus was not included in the pre-existing 2B/9B/27B training runs. Verify future checkpoint provenance separately.",
                      "Raw is_credit is scored only when the actual candidate reference has known direction, independent of predicted known. Normalization gates credit only by predicted known.",
                      "Unknown/review and miss-none are not successful extracted values. Guard acceptance of a wrong-role candidate is not requested-target success.",
                      "Service identity is self-reported metadata checked against expected pins, not independent authentication of weights.",
                      "No server is launched here. Future GPU-backed runs must wait for current training and established final stages to release resources."]}
        (output/"report.json").write_bytes(encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT/"data")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--splits", choices=("test", "ood"), nargs="+", default=["test", "ood"])
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--model-alias", default="open-jev")
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--expected-method", required=True, choices=("lora_decision_head", "pretrained_yes_minus_no_no_training"))
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-checkpoint-sha256")
    parser.add_argument("--expected-temperature", type=float)
    parser.add_argument("--timeout", type=float, default=300)
    report = run_evaluation(**vars(parser.parse_args(argv)))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
