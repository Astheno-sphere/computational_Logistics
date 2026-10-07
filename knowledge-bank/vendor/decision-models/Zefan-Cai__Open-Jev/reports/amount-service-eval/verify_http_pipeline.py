"""Independent full amount selection audit and bounded loopback software fixtures.

Every HTTP response is manually scripted; no model, SSH, GPU or tokenizer runs.
"""
import argparse
import base64
from collections import Counter
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request, format_response
from scripts import evaluate_amount_service as ev
from scripts import evaluate_drone_service as shared_http

PINS = {
    "reports/amount-service-eval/heldout-preflight.json": "2c146746d55f53a9d72fb8fe8f1b2beea24b2927fa9b2943acd09eeb5eb4cc70",
    "reports/contact-service-eval/verify_heldout.py": "e7bcdaa11aa382e8dec2f449a1ec6ffb75e3edea2a8643ad7131d989aec8f861",
}
IDENTITY = {"model": "software-fixture/no-model-loaded", "method": "pretrained_yes_minus_no_no_training",
            "base_revision": "a" * 40, "checkpoint_sha256": None, "temperature": 1.0,
            "code_commit": "software-fixture", "max_length": 4096}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def encoded(value, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n")


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines() if line]


def identity(case):
    return {"corpus": "amount", "case_id": case["id"], "group_id": case["group_id"],
            "split": case["split"], "request_sha256": digest(encoded(case["selection_request"]))}


def full_selection(output):
    path = ROOT / "reports/contact-service-eval/verify_heldout.py"
    spec = importlib.util.spec_from_file_location("amount_prefix_reader", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    preflight = json.loads((ROOT / "reports/amount-service-eval/heldout-preflight.json").read_bytes())
    directory, decode_log = ROOT / "data/amount-extraction-control-v1", {}
    families = helper.heldout_sidecar(directory / "families.jsonl", "families", decode_log)
    independent = helper.heldout_sidecar(directory / "cases.jsonl", "cases", decode_log)
    for case in independent:
        case["corpus"] = "amount"
    for split in ("test", "ood"):
        rows = [case for case in independent if case["split"] == split]
        prior = preflight["splits"][split]
        require([row["id"] for row in rows] == prior["case_ids"], "Frozen physical case ID order differs")
        require(helper.sequence_sha256([row["id"] for row in rows]) == prior["case_ids_sha256"], "Case ID sequence hash differs")
        observed_requests = []
        for case in rows:
            for stage, candidate, request in [("selection", None, case["selection_request"]),
                    *(("attributes", item["candidate_id"], item["request"]) for item in case["attributes"])]:
                observed_requests.append({"case_id": case["id"], "family_id": case["family_id"], "group_id": case["group_id"],
                    "split": split, "stage": stage, "candidate_id": candidate,
                    "request_sha256": digest(encoded(request)), "canonical_request_sha256": digest(encoded(request, True))})
        require(observed_requests == prior["ordered_requests"], "Original all-candidate A/B request bytes/order differ")
    independent.sort(key=lambda case: (("test", "ood").index(case["split"]),
        digest(encoded(["group", case["group_id"]], True)), digest(encoded(["case", case["id"]], True))))
    observed_decode = {"case_payloads": Counter(), "family_metadata_payloads": Counter()}
    original = ev.strict_json

    def checked_decode(raw):
        if isinstance(raw, bytes):
            for kind, key in (("cases", "case_payloads"), ("families", "family_metadata_payloads")):
                found = helper.PREFIXES[kind].match(raw[:512])
                if found:
                    split = found.group("split").decode()
                    observed_decode[key][split] += 1
                    require(kind != "cases" or split in ("test", "ood"), "Nonheldout case target decoded")
        return original(raw)

    with patch.object(ev, "strict_json", checked_decode):
        actual, inputs = ev.load_cases(ROOT / "data")
    require(actual == independent, "Complete default loader differs from independent heldout content/order")
    require([encoded(case["selection_request"]) for case in actual] ==
            [encoded(case["selection_request"]) for case in independent], "Request mapping order changed")
    require(inputs["files_sha256"] == preflight["files_sha256"], "Frozen input hashes changed")
    pending = ev.summarize(actual, [{"status": "pending"} for _ in actual])
    require(pending["cases"] == 864 and pending["families"] == 54, "Default complete population differs")
    check_metric(pending, "a_span", 0, 864)
    check_metric(pending, "final_value_on_unique_target", 0, 648)
    check_metric(pending, "normalized_pair_on_reference_ready_target", 0, 324)
    require(pending["reference_ready"] == {"cases": 324, "unique_present_cases": 648, "coverage": 0.5}, "Ready coverage differs")
    splits = {}
    for split in ("test", "ood"):
        rows = [case for case in actual if case["split"] == split]
        prior = preflight["splits"][split]
        summary = ev.summarize(rows, [{"status": "pending"} for _ in rows])
        require(summary["cases"] == prior["documents"] and summary["families"] == prior["families"], "Split population differs")
        require(summary["reference_reasons"] == {reason: prior["denominators"][reason] for reason in
                ("target_absent", "ambiguous_target", "candidate_miss", "recalled")}, "Split fixed strata differ")
        check_metric(summary, "final_value_on_unique_target", 0, prior["denominators"]["unique_present"])
        check_metric(summary, "normalized_pair_on_reference_ready_target", 0, prior["denominators"]["unique_present_recalled_reference_ready"])
        splits[split] = {"pending_summary": summary,
                         "ordered_case_ids_sha256": helper.sequence_sha256([case["id"] for case in rows])}
    result = {"kind": "independent_amount_default_selection_audit", "verified": True, "documents": len(actual),
              "sampling_or_caps": False, "ordered_cases_sha256": digest(encoded([identity(case) for case in actual], True)),
              "all_original_A_and_possible_B_request_hashes_match": True, "pending_summary": pending, "by_split": splits,
              "independent_prefix_decode_log": decode_log, "observed_evaluator_JSON_decodes": observed_decode,
              "nonheldout_case_targets_decoded": 0,
              "family_metadata_exception": "The evaluator decodes all family metadata; full nonheldout case targets remain undecoded.",
              "model_or_HTTP_calls": 0}
    save(output / "selection-audit.json", result)
    family = min(families, key=lambda row: row["id"])
    index = {row["id"]: row for row in actual}
    return [index[identifier] for identifier in family["case_ids"]], inputs, result


def reply(request, choices):
    records = compile_request(**request)
    probabilities = [[1 - choices[row["id"]], choices[row["id"]]] if row["kind"] == "noul" else
                     [float(key == choices[row["id"]]) for key in row["answer_keys"]] for row in records]
    result = format_response(records, probabilities)
    result["model"] = IDENTITY["model"]
    result["metadata"] = {key: value for key, value in IDENTITY.items() if key != "model"}
    result["metadata"]["candidate_sequences"] = sum(1 if row["kind"] == "noul" else len(row["options"]) for row in records)
    return 200, encoded(result)


def a(case, span, present=1):
    request = case["selection_request"]
    return request, reply(request, {"span": span, "target_present": present})


def b_request(case, candidate):
    return next(item["request"] for item in case["attributes"] if item["candidate_id"] == candidate)


def b(case, candidate, currency, known, credit):
    request = b_request(case, candidate)
    return request, reply(request, {"currency": currency, "direction_known": known, "is_credit": credit})


def run_fixture(output, name, cases, planned, full_inputs, *, interrupt_after=None):
    plan = [(encoded({"model": "open-jev", **request}), status, raw) for request, (status, raw) in planned]
    received, server_errors = [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            index = len(received)
            if index >= len(plan) or raw != plan[index][0] or self.path != "/v1/systemone":
                server_errors.append(index)
                status, response = 500, b"Unexpected fixture request"
            else:
                _, status, response = plan[index]
            received.append({"request_body_base64": base64.b64encode(raw).decode(), "request_body_sha256": digest(raw),
                             "http_status": status, "response_body_base64": base64.b64encode(response).decode(),
                             "response_body_sha256": digest(response)})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            raise ValueError("Fixture redirects prohibited")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/systemone"
    direct = build_opener(ProxyHandler({}), NoRedirect())
    calls = 0

    def transport(url, body, timeout):
        nonlocal calls
        require(url == endpoint, "Only this exact loopback endpoint is permitted")
        if interrupt_after is not None and calls == interrupt_after:
            raise KeyboardInterrupt("explicit software fixture interruption")
        calls += 1
        return ev.http_attempt(url, body, timeout)

    directory = output / name
    inputs = {**full_inputs, "software_fixture_subset": True, "fixture_cases": [case["id"] for case in cases]}
    interrupted = False
    try:
        with patch.object(ev, "load_cases", return_value=(cases, inputs)), patch.object(shared_http, "urlopen", direct.open):
            try:
                ev.run_evaluation(ROOT / "data", directory, splits=("ood",), endpoint=endpoint,
                    expected_model=IDENTITY["model"], expected_method=IDENTITY["method"],
                    expected_revision=IDENTITY["base_revision"], timeout=3, transport=transport)
            except KeyboardInterrupt:
                require(interrupt_after is not None, "Unexpected interruption")
                interrupted = True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    require(not server_errors and len(received) == len(plan), "Request body/order/count did not match script")
    require(interrupted == (interrupt_after is not None), "Interruption fixture did not execute")
    report = json.loads((directory / "report.json").read_bytes())
    attempts, requests, outcomes = (jsonl(directory / name) for name in ("attempts.jsonl", "requests.jsonl", "outcomes.jsonl"))
    require(report["evidence_kind"] == "software_fixture" and report["is_model_quality_evidence"] is False,
            "Scripted HTTP fixture mislabeled as model evidence")
    require(len(attempts) == len(received) and len(requests) == len(received) + int(interrupted), "Raw evidence count differs")
    for actual, logged in zip(received, attempts):
        require(all(logged[key] == value for key, value in actual.items()), "Raw HTTP evidence not preserved exactly")
    save(directory / "fixture-wire.json", {"evidence_kind": "software_fixture", "no_model_loaded": True,
         "proxy_and_redirects_disabled": True, "explicit_transport_calls_production_http_attempt": True,
         "requests": received, "scope": "Explicit fixed case subset through patched loader, not full-dataset performance. The separate default selection audit checks all 864 documents."})
    return report, outcomes


def check_metric(summary, name, correct, total):
    require(summary["metrics"][name] == {"correct": correct, "total": total,
            "accuracy": correct / total if total else None}, "Metric mismatch: " + name)


def fixtures(output, cases, inputs):
    selected = [cases[i] for i in (0, 13, 5, 7, 6, 8, 15, 11)]
    script = [a(cases[0], "span_0", 0), b(cases[0], "span_0", "GBP", 1, 0),
              a(cases[13], "span_3"), b(cases[13], "span_3", "GBP", 1, 0),
              a(cases[5], "span_3"), b(cases[5], "span_3", "EUR", 1, 0),
              a(cases[7], "span_2"), b(cases[7], "span_2", "GBP", 0, 1),
              a(cases[6], "span_3"), b(cases[6], "span_3", "review", 0, 1),
              a(cases[8], "span_1"), b(cases[8], "span_1", "GBP", 1, 1),
              a(cases[15], "span_3"), b(cases[15], "span_3", "GBP", 1, 1), a(cases[11], "none")]
    report, outcomes = run_fixture(output, "amount-boundaries", selected, script, inputs)
    require(report["status"] == "complete", "Boundary fixture did not complete")
    summaries = [ev.summarize([case], [outcome]) for case, outcome in zip(selected, outcomes)]
    for index in (0, 1):
        require(outcomes[index]["guard"]["status"] == "ready", "Wrong-role candidate did not reach normalization")
        check_metric(summaries[index], "final_value_on_unique_target", 0, 1)
        check_metric(summaries[index], "exact_raw_span_on_unique_target", 0, 1)
    require(outcomes[0]["a"]["prediction"]["target_present"] is False and outcomes[0]["b"]["status"] == "ok", "Presence gated B")
    require(outcomes[2]["guard"]["reason"] == "partial_or_unbound_candidate", "Partial candidate bypassed guard")
    check_metric(summaries[2], "final_value_on_unique_target", 0, 1)
    for index in (2, 3):
        require("b_is_credit_on_reference_known_actual_selection" not in summaries[index]["metrics"] and
                summaries[index]["actual_b_undefined_credit"] == 1, "Undefined is_credit gained supervised score")
    check_metric(summaries[3], "b_defined_attributes_joint_on_actual_selection", 1, 1)
    require(outcomes[3]["guard"]["amount"] is None and outcomes[3]["guard"]["currency"] is None, "Unknown direction produced value")
    check_metric(summaries[3], "final_value_on_unique_target", 0, 1)
    check_metric(summaries[4], "b_is_credit_on_reference_known_actual_selection", 0, 1)
    require(outcomes[4]["b"]["prediction"]["direction_known"] is False, "Fixture did not exercise false predicted known")
    check_metric(summaries[4], "final_value_on_unique_target", 0, 1)
    require(outcomes[5]["guard"]["amount"] == "-4401.40", "Negative credit sign was not applied exactly once")
    require(outcomes[6]["guard"]["amount"] == "-123456789012345678901234567892.03", "Long Decimal rounded or sign changed")
    for index in (5, 6):
        check_metric(summaries[index], "final_value_on_unique_target", 1, 1)
        check_metric(summaries[index], "complete_output_on_unique_target", 1, 1)
    check_metric(summaries[7], "a_span", 1, 1)
    check_metric(summaries[7], "final_value_on_unique_target", 0, 1)
    require(outcomes[7]["b"]["reason"] == "a_selected_none", "Miss-none dispatched B")

    alternate, _ = run_fixture(output, "undefined-credit-alternate", [cases[7]],
                               [a(cases[7], "span_2"), b(cases[7], "span_2", "GBP", 0, 0)], inputs)
    require(alternate["summary"] == summaries[3], "Undefined credit value changed quality/guard scoring")
    error_report, error_outcomes = run_fixture(output, "B-http-error", [cases[0]],
        [a(cases[0], "span_3"), (b_request(cases[0], "span_3"), (503, b"\xffamount fixture unavailable\n"))], inputs)
    require(error_outcomes[0]["b"]["status"] == "http_error" and error_report["status"] == "completed_with_errors", "B failure misclassified")
    for name in ("b_currency_on_actual_selection", "b_direction_known_on_actual_selection",
                 "b_is_credit_on_reference_known_actual_selection", "normalized_pair_on_reference_ready_target"):
        check_metric(error_report["summary"], name, 0, 1)
    pending, _ = run_fixture(output, "interrupted-pending", [cases[0], cases[15]], [], inputs, interrupt_after=0)
    require(pending["status"] == "interrupted_or_failed" and pending["summary"]["status_counts"] == {"pending": 2}, "Pending cases disappeared")
    check_metric(pending["summary"], "final_value_on_unique_target", 0, 2)
    check_metric(pending["summary"], "normalized_pair_on_reference_ready_target", 0, 2)
    checks = ["actual_A_candidate_B_bytes_match_independent_sidecar", "presence_false_still_dispatches_B",
              "wrong_role_ready_gets_zero_target_credit", "same_amount_wrong_offset_gets_zero_target_credit",
              "partial_candidate_rejected_despite_predicted_known", "undefined_is_credit_not_scored",
              "undefined_is_credit_alternate_raw_value_does_not_change_summary", "reference_known_credit_keeps_denominator_when_predicted_unknown",
              "unknown_currency_with_known_direction_credit_is_not_dropped", "None_pair_not_value_success",
              "negative_credit_applied_once", "long_decimal_stays_exact", "miss_none_policy_credit_not_value_success",
              "B_error_raw_nonUTF8_body_retained_with_fixed_denominators", "interrupted_pending_cases_keep_all_denominators",
              "all_HTTP_runs_explicit_software_fixture_not_model_quality"]
    return {"passed_checks": checks, "check_count": len(checks), "actual_loopback_requests": 19,
            "fixture_selection": "Lexicographically first heldout family; fixed variant ordinals, no selection by labels or outcomes.",
            "selected_family_id": cases[0]["family_id"],
            "runs": {"amount-boundaries": {"cases": 8, "HTTP_requests": 15}, "undefined-credit-alternate": {"cases": 1, "HTTP_requests": 2},
                     "B-http-error": {"cases": 1, "HTTP_requests": 2}, "interrupted-pending": {"cases": 2, "HTTP_requests": 0}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--evaluator-sha256", required=True)
    parser.add_argument("--tests-sha256", required=True)
    args = parser.parse_args()
    pins = {**PINS, "scripts/evaluate_amount_service.py": args.evaluator_sha256, "tests/test_amount_service.py": args.tests_sha256}
    for path, expected in pins.items():
        require(file_hash(ROOT / path) == expected, "Pinned input differs: " + path)
    output = args.output_dir.resolve()
    require(not args.output_dir.exists() and not args.output_dir.is_symlink() and not output.is_relative_to(ROOT / "data"), "Choose a new output outside immutable data")
    output.mkdir(parents=True, exist_ok=False)
    cases, inputs, selection = full_selection(output)
    result = fixtures(output, cases, inputs)
    for path, expected in pins.items():
        require(file_hash(ROOT / path) == expected, "Pinned input changed during audit")
    result.update(kind="independent_amount_HTTP_software_audit", verified=True, is_model_quality_evidence=False,
                  input_sha256=pins, verification_script_sha256=file_hash(__file__), full_default_documents=selection["documents"],
                  full_ordered_cases_sha256=selection["ordered_cases_sha256"],
                  scope=["All responses manually scripted; no model, SSH, GPU, tokenizer, external benchmark or nonheldout case targets.",
                         "Only fixture runs patch load_cases to explicit cases; separate read-only default selection checks the full heldout population.",
                         "API serialization and existing runtime normalizer are exercised, not independently reimplemented.",
                         "All HTTP uses an explicitly injected production transport with proxy/redirects disabled."])
    result["artifact_sha256"] = {str(path.relative_to(output)): file_hash(path) for path in sorted(output.rglob("*")) if path.is_file()}
    save(output / "audit.json", result)
    print(json.dumps({"verified": True, "full_default_documents": selection["documents"], "software_checks": result["check_count"],
                      "actual_loopback_requests": result["actual_loopback_requests"], "is_model_quality_evidence": False}, sort_keys=True))


if __name__ == "__main__":
    main()
