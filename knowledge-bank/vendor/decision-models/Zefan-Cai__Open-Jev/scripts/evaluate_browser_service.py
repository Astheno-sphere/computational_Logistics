"""Evaluate held-out synthetic browser snapshots through a real HTTP service.

This measures snapshot decisions, not browser execution or web-task success.
Every selected case remains in the denominator, including transport, schema and
model-identity failures. No teacher fallback or inactive-head gold is used.
"""

import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
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

from jev.api import compile_request
from jev.case_browser import VERSION, browser_teacher
from jev.community import browser_proposal, browser_request
from jev.data import SPLITS
from jev.metrics import choice_confidence


METHODS = {"lora_decision_head", "pretrained_yes_minus_no_no_training"}


def encoded(value, *, sort_keys=False):
    # Wire requests retain mapping order: conditional value question indices
    # depend on the runtime builder's text/element order.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode()


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def rank(value):
    return sha256(encoded(value, sort_keys=True))


def case_identity(case):
    return {"case_id": case["id"], "group_id": case["group_id"], "split": case["split"],
            "variant": case["variant"], "request_sha256": sha256(encoded(case["request"]))}


def select_cases(cases, splits=("test", "ood"), parents_per_split=20,
                 variants_per_parent=3, seed=42, max_cases=None):
    """Rank parent IDs and variant IDs, without reading any reference answers."""
    if not splits or len(set(splits)) != len(splits) or not set(splits) <= {"test", "ood"}:
        raise ValueError("splits must be distinct held-out test/ood names")
    for name, value in (("parents_per_split", parents_per_split), ("variants_per_parent", variants_per_parent)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if type(seed) is not int or (max_cases is not None and (type(max_cases) is not int or max_cases < 1)):
        raise ValueError("seed must be an integer and max_cases must be positive when supplied")
    pools = {split: defaultdict(list) for split in splits}
    ids, groups, inputs = set(), {}, {}
    for case in cases:
        identifier, group, split = case.get("id"), case.get("group_id"), case.get("split")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("case IDs must be nonempty and unique")
        if not isinstance(group, str) or not group or split not in SPLITS or case.get("source") != VERSION:
            raise ValueError("invalid browser case source/group/split")
        if not isinstance(case.get("variant"), str) or not case["variant"]:
            raise ValueError("case variant must be nonempty text")
        if groups.setdefault(group, split) != split:
            raise ValueError("parent group crosses split boundaries")
        request = case.get("request")
        if not isinstance(request, dict) or set(request) != {"state", "questions"}:
            raise ValueError("case requires an exact state/questions request")
        fingerprint = rank(request)
        if inputs.setdefault(fingerprint, split) != split:
            raise ValueError("identical runtime request crosses split boundaries")
        ids.add(identifier)
        if split in pools:
            pools[split][group].append(case)
    ranked = {}
    for split in splits:
        if len(pools[split]) < parents_per_split:
            raise ValueError(f"{split}: need {parents_per_split} parents; found {len(pools[split])}")
        selected_groups = sorted(pools[split], key=lambda group: rank([seed, split, group]))[:parents_per_split]
        ranked[split] = [sorted(pools[split][group], key=lambda case: rank([seed, case["id"]]))[:variants_per_parent]
                         for group in selected_groups]
    # Round-robin truncation retains both splits and spreads a small --max-cases
    # budget over parents before taking another variant of the same parent.
    selected = [ranked[split][parent][variant]
                for variant in range(variants_per_parent) for parent in range(parents_per_split) for split in splits
                if variant < len(ranked[split][parent])]
    return selected if max_cases is None else selected[:max_cases]


def validate_case(case):
    request, state = case["request"], case["request"]["state"]
    expected = browser_request(state["goal"], state["snapshot"], state["text_candidates"])
    if encoded(request) != encoded(expected):
        raise ValueError("case no longer matches the exact ordered browser runtime request")
    active = browser_teacher(state)
    if case.get("reference_kind") != "independent_synthetic_visible_browser_control" or case.get("active_answers") != active:
        raise ValueError("saved active answers disagree with the disclosed visible-state teacher")
    records = {record["id"]: record for record in compile_request(**request)}
    if any(answer not in records[key]["answer_keys"] for key, answer in active.items()):
        raise ValueError("reference answer is not a runtime candidate")
    return records


def reference_proposal(case):
    """Construct only the reference operation's active proposal, without defaults."""
    active, state = case["active_answers"], case["request"]["state"]
    operation = active["operation"]
    result = {"snapshot_id": state["snapshot"]["snapshot_id"], "operation": operation}
    if operation in {"CLICK", "TYPE_TEXT", "SELECT"}:
        key = active[operation.lower() + "_target"]
        result["target_id"] = key
        if operation == "TYPE_TEXT":
            index = list(state["text_candidates"]).index(key)
            value_id = active[f"text_value_{index}"]
            result.update(value_id=value_id, text=state["text_candidates"][key][value_id])
        elif operation == "SELECT":
            keys = [item["id"] for item in state["snapshot"]["elements"] if "SELECT" in item["actions"]]
            result["option_id"] = active[f"select_value_{keys.index(key)}"]
    return result


def service_identity(response, records, expected):
    if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
        raise ValueError("service response lacks model metadata")
    metadata = response["metadata"]
    identity = {"model": response.get("model"), "method": metadata.get("method"),
                "base_revision": metadata.get("base_revision"), "checkpoint_sha256": metadata.get("checkpoint_sha256"),
                "temperature": metadata.get("temperature"), "code_commit": metadata.get("code_commit"),
                "max_length": metadata.get("max_length")}
    if any(not isinstance(identity[key], str) or not identity[key] for key in ("model", "base_revision")):
        raise ValueError("service must identify its model and base revision")
    if identity["method"] not in METHODS:
        raise ValueError("service method is not an accepted learned scorer")
    temperature = identity["temperature"]
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("service calibration temperature must be finite and positive")
    checkpoint = identity["checkpoint_sha256"]
    if identity["method"] == "lora_decision_head" or checkpoint is not None:
        if not isinstance(checkpoint, str) or re.fullmatch(r"[0-9a-f]{64}", checkpoint) is None:
            raise ValueError("checkpoint scorer must identify its checkpoint SHA-256")
    for key in ("code_commit",):
        if identity[key] is not None and (not isinstance(identity[key], str) or not identity[key]):
            raise ValueError(f"invalid {key}")
    if identity["max_length"] is not None and (type(identity["max_length"]) is not int or identity["max_length"] < 1):
        raise ValueError("invalid service max_length")
    if type(metadata.get("candidate_sequences")) is not int or metadata["candidate_sequences"] != sum(len(r["options"]) for r in records.values()):
        raise ValueError("candidate sequence count does not match the complete request")
    for key, value in expected.items():
        if value is not None and identity[key] != value:
            raise ValueError(f"service {key} differs from the expected value")
    return identity


def head_counts(case, records):
    active = case["active_answers"]
    conditional = [key for key in active if key != "operation"]
    return {"active_conditional": [key for key in conditional if len(records[key]["options"]) > 1],
            "forced_active_conditional": [key for key in conditional if len(records[key]["options"]) == 1]}


def score_response(case, response, records):
    proposal = browser_proposal(case["request"], response,
                                current_snapshot_id=case["request"]["state"]["snapshot"]["snapshot_id"])
    active, answers = case["active_answers"], response["answers"]
    # The proposal adapter validates action selection and distributions. This
    # evaluator also requires complete Choice outputs, including inactive heads.
    for key, record in records.items():
        answer = answers[key]
        confidence = answer.get("confidence")
        derived = choice_confidence([answer["probabilities"][candidate] for candidate in record["answer_keys"]])
        if (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1
                or not math.isclose(confidence, derived, rel_tol=1e-6, abs_tol=1e-6)):
            raise ValueError(f"Choice confidence is missing, invalid or inconsistent: {key}")
    scores = {"operation": int(answers["operation"]["choice"] == active["operation"]),
              "proposal_exact": int(proposal == reference_proposal(case))}
    scores.update({name: sum(answers[key]["choice"] == active[key] for key in keys)
                   for name, keys in head_counts(case, records).items()})
    return scores, proposal


def http_attempt(endpoint, body, timeout):
    started = time.perf_counter()
    status, raw, error = None, b"", None
    request = Request(endpoint, body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except HTTPError as exc:
        with exc:
            status, raw = exc.code, exc.read()
        error = f"HTTP {status}"
    except (URLError, OSError, TimeoutError, HTTPException) as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {"http_status": status, "response_body_base64": base64.b64encode(raw).decode(),
            "response_body_sha256": sha256(raw), "elapsed_seconds": time.perf_counter() - started,
            "transport_error": error}, raw


def summarize(cases, outcomes, records_by_case):
    by_id = {outcome["case_id"]: outcome for outcome in outcomes}
    totals = Counter(operation=len(cases), proposal_exact=len(cases))
    correct, teachers = Counter(), Counter()
    for case in cases:
        teachers[case["active_answers"]["operation"]] += 1
        totals.update({name: len(keys) for name, keys in head_counts(case, records_by_case[case["id"]]).items()})
        outcome = by_id.get(case["id"])
        if outcome is not None and outcome["status"] == "ok":
            correct.update(outcome["correct"])
    return {"cases": len(cases), "parents": len({case["group_id"] for case in cases}),
            "teacher_operations": dict(sorted(teachers.items())),
            "variants": dict(sorted(Counter(case["variant"] for case in cases).items())),
            "metrics": {name: {"correct": correct[name], "total": totals[name],
                               "accuracy": correct[name] / totals[name] if totals[name] else None}
                        for name in ("operation", "active_conditional", "forced_active_conditional", "proposal_exact")}}


def run_evaluation(cases_path, output_dir, *, endpoint="http://127.0.0.1:8791/v1/systemone",
                   splits=("test", "ood"), parents_per_split=20, variants_per_parent=3, seed=42,
                   max_cases=None, model_alias="open-jev", expected_model=None, expected_method=None,
                   expected_revision=None, expected_checkpoint_sha256=None, timeout=300):
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must be an HTTP(S) URL without credentials, query or fragment")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    source, output = Path(cases_path), Path(output_dir)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output directory must be empty or absent")
    source_bytes = source.read_bytes()
    manifest_bytes = source.with_name("manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    all_cases = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
    if (manifest.get("cases_file") != source.name or manifest.get("cases_sha256") != sha256(source_bytes)
            or type(manifest.get("case_count")) is not int or manifest["case_count"] != len(all_cases)):
        raise ValueError("cases file checksum/count does not match its frozen manifest")
    cases = select_cases(all_cases, splits, parents_per_split, variants_per_parent, seed, max_cases)
    records_by_case = {case["id"]: validate_case(case) for case in cases}
    expected = {"model": expected_model, "method": expected_method,
                "base_revision": expected_revision, "checkpoint_sha256": expected_checkpoint_sha256}
    selection = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "source": str(source),
                 "source_sha256": sha256(source_bytes), "source_manifest_sha256": sha256(manifest_bytes),
                 "evaluator_sha256": sha256(Path(__file__).read_bytes()),
                 "endpoint": endpoint, "model_alias": model_alias, "expected_identity": expected,
                 "splits": list(splits), "parents_per_split": parents_per_split,
                 "variants_per_parent": variants_per_parent, "seed": seed, "max_cases": max_cases,
                 "selection_rule": "SHA-256 rank of parent IDs, then variant IDs; round-robin split/parent truncation; no labels",
                 "cases": [case_identity(case) for case in cases]}
    selection["selection_sha256"] = rank(selection["cases"])
    output.mkdir(parents=True, exist_ok=True)
    def write_json(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    write_json("selection.json", selection)
    with (output / "references.jsonl").open("w") as handle:
        for case in cases:
            handle.write(encoded({**case_identity(case), "active_answers": case["active_answers"],
                                  "reference_proposal": reference_proposal(case)}).decode() + "\n")
    outcomes, identity = [], None
    def report(status):
        return {"status": status, "complete": len(outcomes) == len(cases), "selected_cases": len(cases),
                "attempted_cases": len(outcomes), "pending_cases": len(cases) - len(outcomes),
                "error_cases": sum(row["status"] != "ok" for row in outcomes),
                "status_counts": dict(Counter(row["status"] for row in outcomes)), "service_identity": identity,
                "selection_sha256": selection["selection_sha256"], "source_sha256": selection["source_sha256"],
                "overall": summarize(cases, outcomes, records_by_case),
                "by_split": {split: summarize([case for case in cases if case["split"] == split], outcomes, records_by_case) for split in splits},
                "scope": "Synthetic snapshot decisions only; no browser execution or real web-task success. Conditional accuracy uses reference-active heads even when the predicted operation is wrong. Forced one-candidate heads are separate. HTTP/schema/identity errors and pending cases score zero; inactive heads have no gold."}
    write_json("report.json", report("running"))
    try:
        with (output / "requests.jsonl").open("w") as requests, (output / "outcomes.jsonl").open("w") as results:
            for case in cases:
                body = encoded({"model": model_alias, **case["request"]})
                request_record = {**case_identity(case), "request_json": body.decode(), "request_body_sha256": sha256(body)}
                requests.write(encoded(request_record).decode() + "\n")
                requests.flush()
                attempt, raw = http_attempt(endpoint, body, timeout)
                outcome = {**case_identity(case), **attempt, "request_body_sha256": sha256(body),
                           "status": "http_error", "service_identity": None, "response": None, "correct": {}}
                if attempt["transport_error"] is None and attempt["http_status"] == 200:
                    stage = "schema_error"
                    try:
                        response = json.loads(raw)
                        encoded(response)  # Reject non-finite JSON without losing raw bytes.
                        outcome["response"] = response
                        stage = "identity_error"
                        received = service_identity(response, records_by_case[case["id"]], expected)
                        outcome["service_identity"] = received
                        if identity is not None and identity != received:
                            raise ValueError("service model/revision/checkpoint/configuration changed during evaluation")
                        identity = received
                        stage = "schema_error"
                        correct, proposal = score_response(case, response, records_by_case[case["id"]])
                        outcome.update(status="ok", correct=correct, proposal=proposal)
                    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
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
    parser.add_argument("--cases", dest="cases_path", type=Path, default=Path("data/browser-v1/cases.jsonl"))
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
    except (ValueError, OSError) as exc:
        print(f"Browser evaluation configuration/artifact error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output_dir": str(args["output_dir"]), **result}, ensure_ascii=False, indent=2))
    return int(result["error_cases"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
