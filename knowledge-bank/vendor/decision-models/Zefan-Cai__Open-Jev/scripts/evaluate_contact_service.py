"""Evaluate frozen email/phone controls through HTTP, retaining every held-out case.

This command never starts a model or trains one. Phone B uses A's actual choice.
Reference-none on an extractor miss is not a successful extraction.
"""
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

from jev.api import compile_request
from jev.case_email_selection import email_selection, reference as email_reference, selected_email
from jev.case_phone_extraction import (
    phone_selection, selection_reference as phone_reference, phone_attributes,
    normalize_phone, phone_library,
)
from scripts.evaluate_browser_service import encoded, rank, sha256
from scripts.evaluate_drone_service import http_attempt, service_identity, strict_json, validate_response

ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "email": ("email-selection-control-v1", "4c18cc791425003c5c8f052ce27ed034dfb54c79ddac24de13f7290ab3b3316c"),
    "phone": ("phone-extraction-control-v1", "1001f1e04795308bf4f68db51076e8e1e1e47802986de54fc33b3b8d33548cfb"),
}
SPLITS = ("train", "calibration", "validation", "test", "ood")
CASE_ID_PREFIX = re.compile(rb'^\{"id":("(?:[^"\\]|\\.)*"),')
IMPLEMENTATION_FILES = (
    "scripts/evaluate_contact_service.py", "scripts/evaluate_browser_service.py",
    "scripts/evaluate_drone_service.py", "jev/metrics.py",
)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def check_inputs(data_root, corpus):
    version, pinned = PROFILES[corpus]
    directory = Path(data_root) / version
    raw = (directory / "manifest.json").read_bytes()
    if sha256(raw) != pinned:
        raise ValueError(f"{corpus}: manifest differs from the frozen control corpus")
    manifest = strict_json(raw)
    expected_files = {f"{split}.jsonl" for split in SPLITS} | {"families.jsonl", "cases.jsonl"}
    if set(manifest["files_sha256"]) != expected_files:
        raise ValueError("Unexpected corpus file manifest")
    # Training/calibration/validation files are hashed as bytes, never parsed.
    for name, digest in manifest["files_sha256"].items():
        if file_hash(directory / name) != digest:
            raise ValueError(f"{corpus}: changed corpus artifact {name}")
    for name, digest in manifest["configuration"]["source_files_sha256"].items():
        if Path(name).name != name or file_hash(ROOT / "jev" / name) != digest:
            raise ValueError(f"{corpus}: changed frozen producer source {name}")
    return directory, manifest


def request_of(case):
    return case["request"] if case["corpus"] == "email" else case["selection_request"]


def reference_of(case):
    return case["reference"] if case["corpus"] == "email" else case["selection_reference"]


def validate_case(case):
    request = request_of(case)
    if not isinstance(request, dict) or set(request) != {"state", "questions"}:
        raise ValueError("A requires an exact original state/questions request")
    state = request["state"]
    builder = email_selection if case["corpus"] == "email" else phone_selection
    if encoded(request) != encoded(builder(state["text"], state["requested_role"], layout=state["policy"]["layout"])):
        raise ValueError("Original A request differs from the frozen visible-input builder")
    reference = email_reference(request) if case["corpus"] == "email" else phone_reference(request)
    if reference != reference_of(case):
        raise ValueError("A reference differs from the visible source fields")
    if case["corpus"] == "phone":
        attributes = case["attributes"]
        if len(attributes) != len(state["candidates"]) or {row["candidate_id"] for row in attributes} != set(state["candidates"]):
            raise ValueError("Phone references must cover every actual candidate")
    return {row["id"]: row for row in compile_request(**request)}


def load_cases(data_root, corpora, splits):
    """Read family IDs first; do not JSON-decode non-held-out case references."""
    selected, evidence = [], {}
    for corpus in corpora:
        directory, manifest = check_inputs(data_root, corpus)
        families = [strict_json(line) for line in (directory / "families.jsonl").read_bytes().splitlines() if line.strip()]
        index, groups, family_ids = {}, {}, set()
        for family in families:
            if family["id"] in family_ids or family["split"] not in SPLITS:
                raise ValueError("Duplicate family or invalid split")
            family_ids.add(family["id"])
            if groups.setdefault(family["group_id"], family["split"]) != family["split"]:
                raise ValueError("A document group crosses splits")
            for identifier in family["case_ids"]:
                if identifier in index:
                    raise ValueError("Duplicate family case ID")
                index[identifier] = family
        if len(families) != manifest["family_count"] or len(index) != manifest["document_count"]:
            raise ValueError("Family/case counts differ from the frozen manifest")
        seen, cases = set(), []
        with (directory / "cases.jsonl").open("rb") as stream:
            for raw in stream:
                if not raw.strip():
                    continue
                prefix = CASE_ID_PREFIX.match(raw)
                if prefix is None:
                    raise ValueError("Frozen JSONL must start with the case ID field")
                identifier = strict_json(prefix[1])
                if identifier not in index or identifier in seen:
                    raise ValueError("Unexpected or duplicate case ID")
                seen.add(identifier)
                family = index[identifier]
                if family["split"] not in splits:
                    continue
                case = strict_json(raw)
                if any(case[key] != family[key] for key in ("group_id", "split")) or case["family_id"] != family["id"]:
                    raise ValueError("Case identity differs from its family index")
                case["corpus"] = corpus
                validate_case(case)
                cases.append(case)
        if seen != set(index) or not cases or any(not any(case["split"] == split for case in cases) for split in splits):
            raise ValueError("Incomplete held-out selection or case file")
        selected.extend(cases)
        evidence[corpus] = {"version": PROFILES[corpus][0], "manifest_sha256": PROFILES[corpus][1],
                            "files_sha256": manifest["files_sha256"],
                            "source_files_sha256": manifest["configuration"]["source_files_sha256"],
                            "selected_cases": len(cases), "split_counts": dict(Counter(case["split"] for case in cases))}
    selected.sort(key=lambda case: (corpora.index(case["corpus"]), ("test", "ood").index(case["split"]),
                                   rank(["group", case["group_id"]]), rank(["case", case["id"]])))
    return selected, evidence


def case_identity(case):
    return {"corpus": case["corpus"], "case_id": case["id"], "group_id": case["group_id"],
            "split": case["split"], "request_sha256": sha256(encoded(request_of(case)))}


def call_stage(request, stage, case, config, stable, requests, attempts, transport):
    body = encoded({"model": config["model_alias"], **request})
    record = {**case_identity(case), "stage": stage, "request_json": body.decode(),
              "request_body_base64": base64.b64encode(body).decode(), "request_body_sha256": sha256(body)}
    requests.write(encoded(record).decode() + "\n")
    requests.flush()
    result = {"status": "http_error", "request_body_sha256": sha256(body)}
    try:
        wire, raw = transport(config["endpoint"], body, config["timeout"])
    except Exception as error:
        raw = b""
        wire = {"http_status": None, "transport_error": f"{type(error).__name__}: {error}"}
    wire.update(response_body_base64=base64.b64encode(raw).decode(), response_body_sha256=sha256(raw))
    attempts.write(encoded({**record, **wire}).decode() + "\n")
    attempts.flush()
    result.update(http_status=wire.get("http_status"), response_body_sha256=sha256(raw))
    phase = "http_error"
    try:
        if wire.get("transport_error") or wire.get("http_status") != 200:
            raise ValueError(wire.get("transport_error") or f"HTTP {wire.get('http_status')}")
        phase = "json_error"
        response = strict_json(raw)
        result["response"] = response
        records = {row["id"]: row for row in compile_request(**request)}
        phase = "identity_error"
        identity = service_identity(response, records, config["expected_identity"])
        result["service_identity"] = identity
        if stable and identity != stable:
            raise ValueError("Service model/artifact/calibration/configuration changed during this run")
        if not stable:
            stable.update(identity)
        phase = "schema_error"
        answers = validate_response(response, records)
        result.update(status="ok", answers=answers)
    except Exception as error:
        result.update(status=phase, error_type=type(error).__name__, error=str(error))
    return result


def evaluate_case(case, outcome, config, stable, requests, attempts, transport):
    request = request_of(case)
    outcome["a"] = call_stage(request, "A", case, config, stable, requests, attempts, transport)
    if outcome["a"]["status"] != "ok":
        outcome.update(status="a_error", b={"status": "not_attempted", "reason": "a_error"})
        return
    answers = outcome["a"]["answers"]
    selected_id = answers["span"]["choice"]
    outcome["a"]["prediction"] = {"span": selected_id,
        "target_present": answers["target_present"]["noul"] >= 0.5,
        "target_present_probability": answers["target_present"]["noul"]}
    if selected_id == "none":
        outcome.update(status="ok", b={"status": "not_attempted", "reason": "a_selected_none"})
        return
    outcome["selected"] = request["state"]["candidates"][selected_id]
    if case["corpus"] == "email":
        outcome.update(guard=selected_email(request, selected_id), status="ok")
        return
    # No reference is consulted to choose or construct this B request.
    b_request = phone_attributes(request, selected_id)
    outcome["b"] = call_stage(b_request, "B", case, config, stable, requests, attempts, transport)
    if outcome["b"]["status"] != "ok":
        outcome["status"] = "b_error"
        return
    region = outcome["b"]["answers"]["region"]["choice"]
    outcome["b"]["prediction"] = {"region": region}
    outcome.update(guard=normalize_phone(b_request, region=region), status="ok")


def metric(correct, total):
    return {"correct": correct, "total": total, "accuracy": correct / total if total else None}


def summarize(cases, outcomes):
    correct, total, reasons, guard_status, b_skips, b_statuses = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    statuses = Counter()
    for case, outcome in zip(cases, outcomes):
        ref, request = reference_of(case), request_of(case)
        a, b = outcome.get("a", {}), outcome.get("b", {})
        a_ok, b_ok = a.get("status") == "ok", b.get("status") == "ok"
        prediction = a.get("prediction", {})
        span_ok = a_ok and prediction.get("span") == ref["span"]
        unique = len(ref["target_spans"]) == 1
        forced = not request["state"]["candidates"]
        groups = ["a_presence", "a_span", "a_forced_span" if forced else "a_nonforced_span"]
        if ref["reason"] == "recalled":
            groups.append("a_span_on_recalled")
        else:
            groups.append("a_none_" + ref["reason"])
        for name in groups:
            total[name] += 1
            correct[name] += int(a_ok and prediction.get("target_present") == ref["target_present"]) if name == "a_presence" else int(span_ok)
        reasons[ref["reason"]] += 1
        statuses[outcome["status"]] += 1
        eligible = a_ok and prediction.get("span") in request["state"]["candidates"]
        exact = unique and eligible and outcome.get("selected") == ref["target_spans"][0] and span_ok
        guard = outcome.get("guard")
        value_ok, region_ok = False, False
        value_available = unique and (case["corpus"] == "email")
        if case["corpus"] == "phone":
            actual_ref = next((row for row in case["attributes"] if row["candidate_id"] == prediction.get("span")), None)
            if eligible:
                total["b_region_on_actual_selection"] += 1
                b_statuses[b.get("status", "not_built_or_pending")] += 1
                region_ok = b_ok and b.get("prediction", {}).get("region") == actual_ref["reference"]["region"]
                correct["b_region_on_actual_selection"] += int(region_ok)
                if actual_ref["reference"]["region"] in ("unknown", "review"):
                    total["b_region_on_actual_unknown_or_review"] += 1
                    correct["b_region_on_actual_unknown_or_review"] += int(region_ok)
            else:
                b_skips["a_selected_none" if a_ok else "a_not_valid_or_pending"] += 1
            expected_ref = next((row for row in case["attributes"] if row["candidate_id"] == ref["span"]), None)
            value_available = unique and expected_ref is not None and expected_ref["normalized_reference"]["status"] == "formatted"
            value_ok = bool(exact and region_ok and guard and guard["status"] == "formatted" and value_available
                            and guard["e164"] == expected_ref["normalized_reference"]["e164"])
            if value_available:
                total["e164_on_reference_formattable_target"] += 1
                correct["e164_on_reference_formattable_target"] += int(value_ok)
        else:
            value_ok = bool(exact and guard and guard["status"] == "copied" and guard["email"] == ref["target_spans"][0]["text"])
        if unique:
            for name, passed in (("exact_raw_span_on_unique_target", exact), ("final_value_on_unique_target", value_ok),
                                 ("complete_output_on_unique_target", value_ok and prediction.get("target_present") is True)):
                total[name] += 1
                correct[name] += int(passed)
            total["reference_value_available_on_unique_target"] += 1
            correct["reference_value_available_on_unique_target"] += int(value_available)
        total["guard_eligible_actual_non_none"] += int(eligible)
        if guard is not None:
            correct["guard_eligible_actual_non_none"] += 1
            guard_status[guard["status"]] += 1
            guard_status["reason:" + (guard.get("reason") or "accepted")] += 1
    quality = {name: metric(correct[name], denominator) for name, denominator in sorted(total.items())
               if name not in ("guard_eligible_actual_non_none", "reference_value_available_on_unique_target")}
    return {"cases": len(cases), "families": len({case["group_id"] for case in cases}), "status_counts": dict(statuses),
            "metrics": quality, "reference_reasons": dict(reasons),
            "candidate_recall": metric(reasons["recalled"], reasons["recalled"] + reasons["candidate_miss"]),
            "reference_value_available": {"cases": correct["reference_value_available_on_unique_target"],
                                          "unique_present_cases": total["reference_value_available_on_unique_target"],
                                          "coverage": correct["reference_value_available_on_unique_target"] / total["reference_value_available_on_unique_target"] if total["reference_value_available_on_unique_target"] else None},
            "b_not_attempted": dict(b_skips), "b_eligible_status_counts": dict(b_statuses),
            "guard": {"eligible_actual_non_none": total["guard_eligible_actual_non_none"],
                      "executed": correct["guard_eligible_actual_non_none"], "all_case_denominator": len(cases),
                      "status_and_reason_counts": dict(guard_status)}}


def run_evaluation(data_root, output_dir, *, corpora=("email", "phone"), splits=("test", "ood"),
                   endpoint="http://127.0.0.1:8791/v1/systemone", model_alias="open-jev", expected_model=None,
                   expected_method=None, expected_revision=None, expected_checkpoint_sha256=None,
                   expected_temperature=None, timeout=300, transport=None):
    if not corpora or len(set(corpora)) != len(corpora) or not set(corpora) <= set(PROFILES):
        raise ValueError("Choose distinct email/phone corpora")
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"test", "ood"}:
        raise ValueError("Only distinct test/ood splits are permitted")
    corpora = tuple(name for name in PROFILES if name in corpora)
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Endpoint must be HTTP(S), without credentials/query/fragment")
    if not math.isfinite(timeout) or timeout <= 0:
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
    output, data_root = Path(output_dir), Path(data_root)
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(data_root.resolve()):
        raise ValueError("Choose an absent output directory outside the immutable data root")
    if "phone" in corpora:
        phone_library()
    cases, inputs = load_cases(data_root, corpora, splits)
    implementation = {name: file_hash(ROOT/name) for name in IMPLEMENTATION_FILES}
    expected = {"model": expected_model, "method": expected_method, "base_revision": expected_revision,
                "checkpoint_sha256": expected_checkpoint_sha256, "temperature": expected_temperature}
    config = {"endpoint": endpoint, "model_alias": model_alias, "timeout": timeout, "expected_identity": expected}
    mode = "software_fixture" if transport is not None else "http_service_evaluation"
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "evidence_kind": mode, "inputs": inputs,
                 "implementation_sha256": implementation, "configuration": config, "corpora": list(corpora), "splits": list(splits),
                 "selection_rule": "All requested test/OOD cases; corpus, split, SHA-256(group ID), SHA-256(case ID); no labels or sampling",
                 "presence_threshold": 0.5, "cases": [case_identity(case) for case in cases]}
    selection["ordered_cases_sha256"] = rank(selection["cases"])
    output.mkdir(parents=True, exist_ok=False)
    (output/"selection.json").write_bytes(encoded(selection))
    with (output/"references.jsonl").open("x") as stream:
        for case in cases:
            stream.write(encoded({**case_identity(case), "a_reference": reference_of(case),
                "b_references": [{key: row[key] for key in ("candidate_id", "reference", "normalized_reference")}
                                 for row in case.get("attributes", [])]}).decode()+"\n")
    outcomes = [{**case_identity(case), "status": "pending"} for case in cases]
    stable, state = {}, "running"
    try:
        with (output/"requests.jsonl").open("x") as requests, (output/"attempts.jsonl").open("x") as attempts, (output/"outcomes.jsonl").open("x") as results:
            for case, outcome in zip(cases, outcomes):
                try:
                    evaluate_case(case, outcome, config, stable, requests, attempts, transport or http_attempt)
                except Exception as error:
                    outcome.update(status="pipeline_error", error_type=type(error).__name__, error=str(error))
                finally:
                    results.write(encoded(outcome).decode()+"\n")
                    results.flush()
        for corpus in corpora:
            check_inputs(data_root, corpus)
        if implementation != {name: file_hash(ROOT/name) for name in IMPLEMENTATION_FILES}:
            raise ValueError("Evaluator/helper implementation changed during the run")
        state = "complete" if all(row["status"] == "ok" for row in outcomes) else "completed_with_errors"
    except BaseException:
        state = "interrupted_or_failed"
        raise
    finally:
        report = {"status": state, "evidence_kind": mode,
                  "is_model_quality_evidence": mode == "http_service_evaluation" and state == "complete" and bool(stable),
                  "service_identity": stable or None, "ordered_cases_sha256": selection["ordered_cases_sha256"],
                  "documents": len(cases), "status_counts": dict(Counter(row["status"] for row in outcomes)),
                  "by_corpus": {}, "limitations": [
                      "These contact corpora were not included in the pre-existing 2B/9B/27B training runs; verify any future checkpoint's training provenance separately.",
                      "Phone uses a finite fictional pool: 424 formatted E.164 values, 124 reused across splits; no unseen-number generalization claim.",
                      "Span-policy correctness on a miss is not successful extraction. Unique-present extraction denominators include misses and stage failures; absence and ambiguity refusals are separate.",
                      "Guard acceptance is deterministic coverage, not model correctness, validity or reachability. Local-only and unsupported cases require review.",
                      "Service identity is self-reported metadata checked against expected pins and held stable; it is not independent authentication of the loaded weights.",
                      "This evaluator does not launch or allocate a model. Future GPU execution must wait for the current 27B run and its established final stages to release resources."]}
        for corpus in corpora:
            indexes = [i for i, case in enumerate(cases) if case["corpus"] == corpus]
            report["by_corpus"][corpus] = summarize([cases[i] for i in indexes], [outcomes[i] for i in indexes])
            report["by_corpus"][corpus]["by_split"] = {split: summarize(
                [cases[i] for i in indexes if cases[i]["split"] == split],
                [outcomes[i] for i in indexes if cases[i]["split"] == split]) for split in splits}
        (output/"report.json").write_bytes(encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT/"data")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--corpora", choices=PROFILES, nargs="+", default=list(PROFILES))
    parser.add_argument("--splits", choices=("test", "ood"), nargs="+", default=["test", "ood"])
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--model-alias", default="open-jev")
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--expected-method", required=True, choices=("lora_decision_head", "pretrained_yes_minus_no_no_training"))
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--expected-checkpoint-sha256")
    parser.add_argument("--expected-temperature", type=float)
    parser.add_argument("--timeout", type=float, default=300)
    args = vars(parser.parse_args(argv))
    report = run_evaluation(**args)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
