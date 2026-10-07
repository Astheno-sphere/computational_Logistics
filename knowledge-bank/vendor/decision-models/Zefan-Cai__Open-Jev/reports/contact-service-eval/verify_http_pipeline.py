"""Independent full-selection audit plus small, explicitly scripted HTTP fixtures.

Only loopback is contacted, through an explicitly injected transport. No model,
tokenizer, SSH, GPU, external benchmark, or non-heldout case target is used.
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
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request, format_response
from scripts import evaluate_contact_service as ev
from scripts import evaluate_drone_service as shared_http

PINS = {
    "scripts/evaluate_contact_service.py": "562dac913d4cebf2732aef9d055dd8dea126c2ec2987573321f1554caf06153a",
    "tests/test_contact_service.py": "3606f0727c3983f833d0ddecf9a6d7218f589d99db0682d2502501e20e4e89eb",
    "reports/contact-service-eval/verify_heldout.py": "e7bcdaa11aa382e8dec2f449a1ec6ffb75e3edea2a8643ad7131d989aec8f861",
    "reports/contact-service-eval/heldout-preflight.json": "3fa7ad7690c309922465744f35727c0575c63b47c3774ee3b4cdeb037c016a62",
}
IDENTITY = {"model": "software-fixture/no-model-loaded", "method": "pretrained_yes_minus_no_no_training",
            "base_revision": "a" * 40, "checkpoint_sha256": None, "temperature": 1.0,
            "code_commit": "software-fixture", "max_length": 4096}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def encoded(value, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def save(path, value):
    with Path(path).open("xb") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b"\n")


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines() if line]


def req(case):
    return case["request"] if case["corpus"] == "email" else case["selection_request"]


def identity(case):
    return {"corpus": case["corpus"], "case_id": case["id"], "group_id": case["group_id"],
            "split": case["split"], "request_sha256": digest(encoded(req(case)))}


def full_selection(output):
    for name, expected in PINS.items():
        require(file_hash(ROOT / name) == expected, "Pinned input changed: " + name)
    path = ROOT / "reports/contact-service-eval/verify_heldout.py"
    spec = importlib.util.spec_from_file_location("independent_heldout", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    preflight = json.loads((ROOT / "reports/contact-service-eval/heldout-preflight.json").read_bytes())
    independent, families, prefix_logs = [], {}, {}
    for corpus in ("email", "phone"):
        directory = ROOT / "data" / helper.PINS[corpus]["dataset"]
        prefix_logs[corpus] = {}
        families[corpus] = helper.heldout_sidecar(directory / "families.jsonl", "families", prefix_logs[corpus])
        rows = helper.heldout_sidecar(directory / "cases.jsonl", "cases", prefix_logs[corpus])
        for row in rows:
            row["corpus"] = corpus
        independent.extend(rows)
        for split in ("test", "ood"):
            selected = [row for row in rows if row["split"] == split]
            frozen = preflight["datasets"][corpus]["splits"][split]
            require([row["id"] for row in selected] == frozen["case_ids"], "Preflight physical ID sequence mismatch")
            require(helper.sequence_sha256([row["id"] for row in selected]) == frozen["case_ids_sha256"], "Preflight ID hash mismatch")
    independent.sort(key=lambda c: (("email", "phone").index(c["corpus"]), ("test", "ood").index(c["split"]),
                                    digest(encoded(["group", c["group_id"]], True)),
                                    digest(encoded(["case", c["id"]], True))))
    decode_counts = {"case_payloads": Counter(), "family_metadata_payloads": Counter()}
    original_decoder = ev.strict_json

    def checked_decode(raw):
        if isinstance(raw, bytes):
            for kind, key in (("cases", "case_payloads"), ("families", "family_metadata_payloads")):
                found = helper.PREFIXES[kind].match(raw[:512])
                if found:
                    split = found.group("split").decode()
                    decode_counts[key][split] += 1
                    if kind == "cases":
                        require(split in ("test", "ood"), "Evaluator decoded a non-heldout case target")
        return original_decoder(raw)

    with patch.object(ev, "strict_json", checked_decode):
        actual, inputs = ev.load_cases(ROOT / "data", ("email", "phone"), ("test", "ood"))
    require(actual == independent, "Default loader differs from independent full heldout reconstruction/order")
    require(len(actual) == 1924, "Changed full document denominator")
    groups = {}
    for corpus in ("email", "phone"):
        groups[corpus] = {}
        require(inputs[corpus]["files_sha256"] == preflight["datasets"][corpus]["files_sha256"], "Corpus pin mismatch")
        for split in ("test", "ood"):
            rows = [c for c in actual if c["corpus"] == corpus and c["split"] == split]
            frozen = preflight["datasets"][corpus]["splits"][split]
            pending = ev.summarize(rows, [{"status": "pending"} for _ in rows])
            denominator = frozen["denominators"]
            require(pending["cases"] == frozen["documents"], "Full split document denominator mismatch")
            require(pending["families"] == frozen["groups"], "Full split group denominator mismatch")
            require(pending["metrics"]["a_span"]["total"] == frozen["documents"], "Pending A denominator changed")
            require(pending["metrics"]["final_value_on_unique_target"]["total"] == denominator["unique_present"], "Unique denominator changed")
            require(pending["candidate_recall"]["correct"] == denominator["unique_present_recalled"], "Recall numerator mismatch")
            require(pending["candidate_recall"]["total"] == denominator["unique_present"], "Recall denominator mismatch")
            if corpus == "phone":
                require(pending["metrics"]["e164_on_reference_formattable_target"]["total"] == denominator["unique_present_recalled_reference_formattable"], "Formattable denominator changed")
            require(all(m["correct"] == 0 for m in pending["metrics"].values()), "Pending cases earned quality credit")
            groups[corpus][split] = {"documents": len(rows), "groups": pending["families"],
                "independent_preflight_denominators": denominator, "pending_summary": pending,
                "evaluator_order_case_ids_sha256": helper.sequence_sha256([row["id"] for row in rows]),
                "ordered_cases_sha256": digest(encoded([identity(c) for c in rows], True))}
    report = {"kind": "independent_full_heldout_selection_audit", "verified": True, "documents": len(actual),
              "selected_splits": ["test", "ood"], "sampling_or_caps": False,
              "ordered_cases_sha256": digest(encoded([identity(c) for c in actual], True)),
              "inputs_sha256": PINS, "by_corpus": groups,
              "independent_prefix_reader_decode_log": prefix_logs,
              "observed_evaluator_json_decodes": decode_counts,
              "nonheldout_case_targets_decoded": 0,
              "family_metadata_exception": "Evaluator decodes all family metadata, including nonheldout IDs/splits/provenance; these payloads have no case targets.",
              "predictions_or_http_calls": 0}
    save(output / "selection-audit.json", report)
    by_id = {case["id"]: case for case in actual}
    fixture_cases = {}
    for corpus in ("email", "phone"):
        family = min(families[corpus], key=lambda row: row["id"])
        fixture_cases[corpus] = [by_id[identifier] for identifier in family["case_ids"]]
    return fixture_cases, inputs, report


def reply(request, choices, *, temperature=1.0, malformed=False):
    # These are manually scripted software outputs. compile/format only serialize
    # the typed HTTP schema; no producer reference is called to choose an answer.
    records = compile_request(**request)
    probabilities = [[1 - choices[row["id"]], choices[row["id"]]] if row["kind"] == "noul" else
                     [float(key == choices[row["id"]]) for key in row["answer_keys"]] for row in records]
    result = format_response(records, probabilities)
    result["model"] = IDENTITY["model"]
    result["metadata"] = {k: v for k, v in IDENTITY.items() if k != "model"}
    result["metadata"].update(temperature=temperature, candidate_sequences=sum(
        1 if row["kind"] == "noul" else len(row["options"]) for row in records))
    if malformed:
        result["answers"]["span"]["choice"] = "invalid-software-fixture-candidate"
    return 200, encoded(result)


def a(case, span, present, **kwargs):
    request = req(case)
    return request, reply(request, {"span": span, "target_present": present}, **kwargs)


def b(case, selected, region, **kwargs):
    # Expected B comes from the already independently audited immutable sidecar,
    # separately from evaluator.phone_attributes(actual A prediction).
    request = next(row["request"] for row in case["attributes"] if row["candidate_id"] == selected)
    return request, reply(request, {"region": region}, **kwargs)


def run_fixture(output, name, cases, responses, full_inputs, *, interrupt_after=None):
    received, server_errors = [], []
    planned = [(encoded({"model": "open-jev", **request}), status, raw) for request, (status, raw) in responses]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw_request = self.rfile.read(int(self.headers["Content-Length"]))
            index = len(received)
            if index >= len(planned) or raw_request != planned[index][0] or self.path != "/v1/systemone":
                server_errors.append({"index": index, "error": "Unexpected request bytes/order/path"})
                status, raw = 500, b"unexpected fixture request"
            else:
                _, status, raw = planned[index]
            received.append({"request_body_base64": base64.b64encode(raw_request).decode(),
                             "request_body_sha256": digest(raw_request), "http_status": status,
                             "response_body_base64": base64.b64encode(raw).decode(), "response_body_sha256": digest(raw)})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/systemone"
    calls = 0

    def transport(url, body, timeout):
        nonlocal calls
        require(url == endpoint and urlsplit(url).hostname == "127.0.0.1", "Only exact loopback endpoint is allowed")
        if interrupt_after is not None and calls == interrupt_after:
            raise KeyboardInterrupt("explicit software fixture interruption")
        calls += 1
        return ev.http_attempt(url, body, timeout)

    directory = output / name
    corpora = tuple(c for c in ("email", "phone") if any(case["corpus"] == c for case in cases))
    splits = tuple(s for s in ("test", "ood") if any(case["split"] == s for case in cases))
    fixture_inputs = {corpus: {**full_inputs[corpus], "software_fixture_subset": True,
                               "fixture_cases": [case["id"] for case in cases if case["corpus"] == corpus]}
                      for corpus in corpora}
    interrupted = False

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            raise ValueError("Software fixture HTTP redirects are prohibited")

    direct_opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with patch.object(ev, "load_cases", return_value=(cases, fixture_inputs)), \
                patch.object(shared_http, "urlopen", direct_opener.open):
            try:
                ev.run_evaluation(ROOT / "data", directory, corpora=corpora, splits=splits,
                                  endpoint=endpoint, expected_model=IDENTITY["model"],
                                  expected_method=IDENTITY["method"], expected_revision=IDENTITY["base_revision"],
                                  timeout=3, transport=transport)
            except KeyboardInterrupt:
                require(interrupt_after is not None, "Unexpected interruption")
                interrupted = True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    require(not server_errors and len(received) == len(planned), "Loopback request bytes/order/count failed")
    require(interrupted == (interrupt_after is not None), "Interruption fixture did not execute")
    report = json.loads((directory / "report.json").read_bytes())
    require(report["evidence_kind"] == "software_fixture" and report["is_model_quality_evidence"] is False,
            "Scripted HTTP fixture incorrectly claims model quality evidence")
    attempts = read_jsonl(directory / "attempts.jsonl")
    requests = read_jsonl(directory / "requests.jsonl")
    outcomes = read_jsonl(directory / "outcomes.jsonl")
    require(len(attempts) == len(received), "Missing raw attempt evidence")
    for observed, logged in zip(received, attempts):
        require(all(logged[key] == value for key, value in observed.items()), "Raw HTTP evidence changed")
    require(len(requests) == len(received) + int(interrupted), "Request logged after/without the expected transport call")
    require(report["documents"] == len(cases), "Fixture fixed document count changed")
    save(directory / "fixture-wire.json", {"evidence_kind": "software_fixture", "no_model_loaded": True,
         "loopback_only": True, "proxy_and_redirects_disabled": True,
         "transport_explicitly_injected": True, "requests": received,
         "fixture_subset_note": "load_cases is patched to explicit frozen cases only for this software check; the normal full default selection was independently audited separately. No fixture accuracy is model performance."})
    return report, outcomes, attempts


def check_metric(summary, name, correct, total):
    require(summary["metrics"][name] == {"correct": correct, "total": total,
            "accuracy": correct / total if total else None}, "Metric mismatch: " + name)


def fixtures(output, cases, inputs):
    e, p = cases["email"], cases["phone"]
    runs, checks = {}, []
    selected = [e[0], e[8], e[9], e[11], p[0], p[6], p[8], p[14]]
    responses = [a(e[0], "span_0", 1), a(e[8], "span_3", 1), a(e[9], "none", 1), a(e[11], "none", 0),
                 a(p[0], "span_0", 0), b(p[0], "span_0", "US"), a(p[6], "span_1", 1), b(p[6], "span_1", "unknown"),
                 a(p[8], "span_1", 1), b(p[8], "span_1", "review"), a(p[14], "none", 1)]
    r, outcomes, _ = run_fixture(output, "scripted-boundaries", selected, responses, inputs)
    require(r["status"] == "complete", "Boundary fixture did not finish")
    for case, outcome in zip(selected, outcomes):
        s = ev.summarize([case], [outcome])
        if case != e[11]:
            check_metric(s, "final_value_on_unique_target", 0, 1)
        if case in (e[0], e[8]):
            require(outcome["guard"]["status"] == "copied", "Wrong-role email was not copied")
            check_metric(s, "exact_raw_span_on_unique_target", 0, 1)
        if case in (e[9], p[14]):
            check_metric(s, "a_span", 1, 1)
            require(outcome["b"]["reason"] == "a_selected_none", "Miss sent B")
        if case == p[0]:
            require(outcome["guard"]["status"] == "formatted" and outcome["a"]["prediction"]["target_present"] is False,
                    "Presence incorrectly gated B or wrong-role formatter did not execute")
            check_metric(s, "b_region_on_actual_selection", 1, 1)
            check_metric(s, "e164_on_reference_formattable_target", 0, 1)
        if case in (p[6], p[8]):
            require(outcome["guard"]["status"] == "review" and outcome["guard"]["e164"] is None, "Review fixture unexpectedly formatted")
            check_metric(s, "exact_raw_span_on_unique_target", 1, 1)
            check_metric(s, "b_region_on_actual_unknown_or_review", 1, 1)
    checks.extend(["wrong_role_email_copy_gets_zero_target_credit", "same_value_wrong_offset_gets_zero_target_credit",
                   "miss_reference_none_is_not_extraction_success", "no_B_after_none",
                   "phone_B_uses_actual_wrong_role_selection", "presence_does_not_gate_B",
                   "unknown_and_review_None_do_not_count_as_value_success"])
    runs["scripted-boundaries"] = {"documents": len(selected), "http_requests": len(responses), "status": r["status"]}

    r, _, _ = run_fixture(output, "scripted-positive-controls", [e[0], p[0]],
                         [a(e[0], "span_5", 1), a(p[0], "span_2", 0), b(p[0], "span_2", "CA")], inputs)
    check_metric(r["by_corpus"]["email"], "complete_output_on_unique_target", 1, 1)
    check_metric(r["by_corpus"]["phone"], "final_value_on_unique_target", 1, 1)
    check_metric(r["by_corpus"]["phone"], "complete_output_on_unique_target", 0, 1)
    checks.append("correct_value_with_false_presence_is_not_complete_output")
    runs["scripted-positive-controls"] = {"documents": 2, "http_requests": 3, "status": r["status"]}

    r, outcomes, attempts = run_fixture(output, "raw-errors", [e[0], e[8], e[9], p[0]],
        [(req(e[0]), (200, b'{"broken":')), (req(e[8]), (503, b'\xfftemporary failure\n')),
         (req(e[9]), (200, b'\xffinvalid UTF8')), a(p[0], "span_2", 1),
         (next(row["request"] for row in p[0]["attributes"] if row["candidate_id"] == "span_2"), (503, b'\xffB unavailable\n'))], inputs)
    require([o["a"]["status"] for o in outcomes] == ["json_error", "http_error", "json_error", "ok"], "Wrong A error classification")
    require(outcomes[-1]["b"]["status"] == "http_error", "Wrong B error classification")
    check_metric(r["by_corpus"]["email"], "final_value_on_unique_target", 0, 3)
    check_metric(r["by_corpus"]["phone"], "e164_on_reference_formattable_target", 0, 1)
    check_metric(r["by_corpus"]["phone"], "b_region_on_actual_selection", 0, 1)
    require(r["status"] == "completed_with_errors", "Error run marked complete")
    require(base64.b64decode(attempts[1]["response_body_base64"]) == b'\xfftemporary failure\n', "503 body not preserved")
    checks.extend(["503_nonUTF8_and_invalid_JSON_preserved_exactly", "A_and_B_errors_keep_fixed_denominators"])
    runs["raw-errors"] = {"documents": 4, "http_requests": 5, "status": r["status"]}

    r, outcomes, _ = run_fixture(output, "identity-drift-on-B", [p[0]],
                                 [a(p[0], "span_2", 1), b(p[0], "span_2", "CA", temperature=2.0)], inputs)
    require(outcomes[0]["b"]["status"] == "identity_error", "B identity drift accepted")
    check_metric(r["by_corpus"]["phone"], "e164_on_reference_formattable_target", 0, 1)
    checks.append("configuration_identity_drift_on_B_rejected")
    runs["identity-drift-on-B"] = {"documents": 1, "http_requests": 2, "status": r["status"]}

    r, outcomes, _ = run_fixture(output, "identity-lock-before-schema", [e[0], e[8]],
                                 [a(e[0], "span_5", 1, malformed=True), a(e[8], "span_6", 1, temperature=2.0)], inputs)
    require([o["a"]["status"] for o in outcomes] == ["schema_error", "identity_error"], "Malformed first answer bypassed identity lock")
    require(r["service_identity"]["temperature"] == 1.0, "Initial identity not locked")
    checks.append("identity_locks_before_first_schema_failure")
    runs["identity-lock-before-schema"] = {"documents": 2, "http_requests": 2, "status": r["status"]}

    r, _, _ = run_fixture(output, "interrupted-pending", [e[0], p[0]], [a(e[0], "span_5", 1)], inputs, interrupt_after=1)
    require(r["status"] == "interrupted_or_failed" and r["status_counts"] == {"ok": 1, "pending": 1}, "Pending case disappeared")
    check_metric(r["by_corpus"]["phone"], "a_span", 0, 1)
    check_metric(r["by_corpus"]["phone"], "e164_on_reference_formattable_target", 0, 1)
    checks.extend(["interruption_retains_unattempted_fixed_denominators", "all_fixture_reports_explicitly_not_model_quality",
                   "actual_received_HTTP_bytes_match_preserved_request_and_response_artifacts"])
    runs["interrupted-pending"] = {"documents": 2, "http_requests": 1, "status": r["status"]}
    return {"runs": runs, "passed_checks": checks, "check_count": len(checks),
            "actual_loopback_requests": sum(run["http_requests"] for run in runs.values()),
            "selection_rule": "Lexicographically first heldout family per corpus, fixed family.case_ids ordinals; never selected by observed label/correctness.",
            "selected_family_ids": {corpus: values[0]["family_id"] for corpus, values in cases.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    require(not args.output_dir.exists() and not args.output_dir.is_symlink() and not output.is_relative_to(ROOT / "data"),
            "Choose a new output directory outside immutable data")
    output.mkdir(parents=True, exist_ok=False)
    cases, inputs, selection = full_selection(output)
    result = fixtures(output, cases, inputs)
    result.update(kind="independent_contact_HTTP_software_audit", verified=True, is_model_quality_evidence=False,
                  evaluator_sha256=file_hash(ROOT / "scripts/evaluate_contact_service.py"),
                  verification_script_sha256=file_hash(__file__), full_default_documents=selection["documents"],
                  full_ordered_cases_sha256=selection["ordered_cases_sha256"],
                  limitations=["Scripted software responses, no learned model; numerical fixture metrics are not quality results.",
                               "Full selection audit reads heldout references; training/calibration/validation case targets are never decoded.",
                               "Normal load_cases is patched only for small fixture runs; complete 1924-document default selection is checked separately without HTTP.",
                               "Typed API serialization and runtime normalizer are exercised, not independently reimplemented."])
    for name, expected in PINS.items():
        require(file_hash(ROOT / name) == expected, "Pinned source changed during audit")
    result["artifact_sha256"] = {str(path.relative_to(output)): file_hash(path) for path in sorted(output.rglob("*")) if path.is_file()}
    save(output / "audit.json", result)
    print(json.dumps({"verified": True, "full_default_documents": selection["documents"],
                      "software_checks": result["check_count"], "actual_loopback_requests": result["actual_loopback_requests"],
                      "is_model_quality_evidence": False}, sort_keys=True))


if __name__ == "__main__":
    main()
