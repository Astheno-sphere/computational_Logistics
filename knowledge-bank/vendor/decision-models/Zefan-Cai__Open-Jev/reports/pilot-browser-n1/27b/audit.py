"""Offline, standard-library audit of the frozen 27B browser snapshot pilot.

No evaluator, adapter, teacher, model, HTTP client, or training library is imported.
The source data verifies the saved references; it is not independently relabeled.
"""

import argparse
import base64
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE_SHA256 = "608b0c0623f920c68001c07af2c87234ef1fe95a96102f6a25d5ff0cecc61537"
MANIFEST_SHA256 = "ed2443c14eb5d63a827a0bca569f5369537e59334481bccb4cf6651521325c0d"
SELECTION_SHA256 = "d6845a2e259967d99fd886f381a4150a3812aa79b0c1c855826fdcfff0030707"
COMMIT = "5b11fe38401831a24c886d28040d55f9a6f03b41"
GPU_UUID = "GPU-9ab08bcc-ce17-0461-aaf2-5d57ddcb4775"
METRICS = ("operation", "active_conditional", "forced_active_conditional", "proposal_exact")


def encode(value, *, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def rank(value):
    return digest(encode(value, sort_keys=True))


def lines(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def identity(case):
    return {"case_id": case["id"], "group_id": case["group_id"],
            "split": case["split"], "variant": case["variant"],
            "request_sha256": digest(encode(case["request"]))}


def proposal(state, selected):
    operation = selected["operation"]
    result = {"snapshot_id": state["snapshot"]["snapshot_id"], "operation": operation}
    if operation in ("CLICK", "TYPE_TEXT", "SELECT"):
        target = selected[operation.lower() + "_target"]
        result["target_id"] = target
        if operation == "TYPE_TEXT":
            texts = state["text_candidates"]
            value = selected["text_value_" + str(list(texts).index(target))]
            result.update(value_id=value, text=texts[target][value])
        elif operation == "SELECT":
            targets = [item["id"] for item in state["snapshot"]["elements"]
                       if "SELECT" in item["actions"]]
            result["option_id"] = selected["select_value_" + str(targets.index(target))]
    return result


def audit(source):
    checked, errors = 0, []

    def check(condition, message):
        nonlocal checked
        checked += 1
        if not condition:
            errors.append(message)

    folder = HERE / "browser"
    selection = json.loads((folder / "selection.json").read_bytes())
    report = json.loads((folder / "report.json").read_bytes())
    transfer = json.loads((HERE / "transfer.json").read_bytes())
    manifest_bytes = (HERE / "source-manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    snapshot_path = HERE.parent / transfer["suite_manifest_snapshot"]
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    model = snapshot["models"]["27b"]
    expected_identity = model["expected_identity"]

    for row in transfer["files"]:
        data = (HERE.parent / row["relative"]).read_bytes()
        check(len(data) == row["bytes"], "transfer size: " + row["relative"])
        check(digest(data) == row["remote_sha256_before"] == row["remote_sha256_after"]
              == row["local_sha256"], "transfer SHA-256: " + row["relative"])
    check(digest(snapshot_bytes) == transfer["suite_manifest_sha256"], "suite snapshot SHA-256")
    check(snapshot["status"] == transfer["suite_status"] == "complete", "suite final complete")
    check(snapshot["current_phase"] == "finished", "suite finished phase")
    check(bool(snapshot.get("ended_at_utc")), "suite final timestamp")
    check(digest(snapshot_bytes) == transfer["suite_manifest_sha256_after"], "final manifest stable at source")
    for tag in ("2b", "9b", "27b"):
        archived = json.loads((HERE.parent / tag / "browser/report.json").read_bytes())
        check(snapshot["models"][tag]["measurements"]["browser"]["exit_code"] == 0,
              "all-model measurement exit: " + tag)
        check(snapshot["models"][tag]["expected_identity"] == archived["service_identity"],
              "final manifest matches archived identity: " + tag)
    check(snapshot["hostname"] == "kwade5342000001", "expected hostname")
    check(snapshot["physical_gpu"] == 3 and snapshot["child_cuda_visible_devices"] == GPU_UUID,
          "authorized physical GPU and CUDA UUID")
    check(snapshot["code_commit"] == COMMIT, "suite commit")
    check(model["measurements"]["browser"]["exit_code"] == 0, "measurement process exit")
    check(model["server_exit_code"] == -15, "owned server terminated after measurement")
    for phase in ("gpu_preflight", "gpu_after_shutdown"):
        gpu = model[phase]
        check(gpu["physical_gpu"] == 3 and gpu["uuid"] == GPU_UUID,
              "GPU identity: " + phase)
        check(gpu["memory_used_mib"] == 0 and gpu["compute_processes"] == [],
              "idle GPU snapshot: " + phase)
    check(model["cuda_visible_devices"] == GPU_UUID, "model CUDA UUID")
    check(report["service_identity"] == expected_identity, "report identity matches suite checkpoint")
    check(expected_identity["model"] == "Qwen/Qwen3.8-27B"
          and expected_identity["method"] == "lora_decision_head"
          and expected_identity["code_commit"] == COMMIT, "pilot model/method/commit")
    evaluator = subprocess.run(["git", "show", COMMIT + ":scripts/evaluate_browser_service.py"],
                               cwd=REPO, check=True, capture_output=True).stdout
    check(digest(evaluator) == selection["evaluator_sha256"], "committed evaluator hash")
    check(digest(manifest_bytes) == MANIFEST_SHA256 == selection["source_manifest_sha256"],
          "source manifest frozen hash")
    source_bytes = source.read_bytes()
    check(digest(source_bytes) == SOURCE_SHA256 == selection["source_sha256"]
          == manifest["cases_sha256"] == report["source_sha256"], "source cases frozen hash")
    source_cases = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
    check(len(source_cases) == manifest["case_count"] == 12660, "source case count")
    source_by_id = {case["id"]: case for case in source_cases}
    check(len(source_by_id) == len(source_cases), "unique source case IDs")
    grouped, group_splits = defaultdict(lambda: defaultdict(list)), {}
    for case in source_cases:
        group, split = case["group_id"], case["split"]
        if group in group_splits and group_splits[group] != split:
            errors.append("source group crosses splits: " + group)
        group_splits[group] = split
        if split in ("test", "ood"):
            grouped[split][group].append(case)
    chosen = {}
    for split in ("test", "ood"):
        groups = sorted(grouped[split], key=lambda group: rank([42, split, group]))[:20]
        chosen[split] = [sorted(grouped[split][group], key=lambda case: rank([42, case["id"]]))[:3]
                         for group in groups]
    cases = [chosen[split][parent][variant]
             for variant in range(3) for parent in range(20) for split in ("test", "ood")]
    case_identities = [identity(case) for case in cases]
    check(case_identities == selection["cases"], "independent parent/variant selection")
    check(rank(case_identities) == SELECTION_SHA256 == selection["selection_sha256"]
          == report["selection_sha256"], "pre-inference frozen selection hash")
    check(selection["splits"] == ["test", "ood"] and selection["parents_per_split"] == 20
          and selection["variants_per_parent"] == 3 and selection["seed"] == 42
          and selection["max_cases"] is None, "fixed selection configuration")
    requests, refs, outcomes = (lines(folder / (name + ".jsonl"))
                                for name in ("requests", "references", "outcomes"))
    for name, rows in (("requests", requests), ("references", refs), ("outcomes", outcomes)):
        check(len(rows) == 120, name + " complete row count")
        check([row["case_id"] for row in rows] == [case["id"] for case in cases], name + " exact order")

    totals = {split: Counter() for split in ("overall", "test", "ood")}
    correct = {split: Counter() for split in totals}
    teachers = {split: Counter() for split in totals}
    predictions = {split: Counter() for split in totals}
    confusion = defaultdict(Counter)
    per_case = []
    for case, request, reference, outcome in zip(cases, requests, refs, outcomes):
        cid, state, questions = case["id"], case["request"]["state"], case["request"]["questions"]
        for row in (request, reference, outcome):
            check(all(row[key] == value for key, value in identity(case).items()), cid + " case identity")
        body = request["request_json"].encode()
        decoded = json.loads(body)
        check(set(decoded) == {"model", "state", "questions"}, cid + " wire fields exclude gold")
        check(decoded["model"] == selection["model_alias"] == "open-jev", cid + " wire model alias")
        check(body == encode({"model": "open-jev", **case["request"]}), cid + " exact ordered wire request")
        check(digest(body) == request["request_body_sha256"] == outcome["request_body_sha256"], cid + " request body hash")
        gold = case["active_answers"]
        check(reference["active_answers"] == gold, cid + " reference matches frozen source")
        gold_proposal = proposal(state, gold)
        check(reference["reference_proposal"] == gold_proposal, cid + " independent reference proposal")
        raw = base64.b64decode(outcome["response_body_base64"], validate=True)
        check(digest(raw) == outcome["response_body_sha256"], cid + " raw response bytes hash")
        response = json.loads(raw)
        check(response == outcome["response"], cid + " parsed response matches raw bytes")
        check(outcome["status"] == "ok" and outcome["http_status"] == 200
              and outcome["transport_error"] is None, cid + " successful HTTP/schema/identity status")
        received = {"model": response["model"], **{key: response["metadata"].get(key)
                    for key in expected_identity if key != "model"}}
        check(received == expected_identity == outcome["service_identity"], cid + " fixed service identity")
        check(all(received[key] == value for key, value in selection["expected_identity"].items()), cid + " expected request identity")
        check(response["metadata"]["candidate_sequences"] == sum(len(q["criteria"]) for q in questions.values()),
              cid + " candidate sequence count")
        answers = response["answers"]
        check(set(answers) == set(questions), cid + " complete answer coverage including inactive heads")
        chosen_answers = {}
        for qid, question in questions.items():
            answer = answers[qid]
            check(question["type"] == answer["type"] == "choice", cid + "/" + qid + " Choice schema")
            probs = answer["probabilities"]
            check(set(probs) == set(question["criteria"]), cid + "/" + qid + " exact candidate set")
            check(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values()),
                  cid + "/" + qid + " finite probabilities")
            mass = sum(probs.values())
            check(math.isclose(mass, 1, rel_tol=1e-6, abs_tol=1e-6), cid + "/" + qid + " probability mass")
            check(answer["choice"] in probs and probs[answer["choice"]] == max(probs.values()),
                  cid + "/" + qid + " argmax selected")
            count = len(probs)
            derived = 1.0 if count == 1 else (max(probs.values()) / mass - 1 / count) / (1 - 1 / count)
            confidence = answer["confidence"]
            check(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1
                  and math.isclose(confidence, derived, rel_tol=1e-6, abs_tol=1e-6), cid + "/" + qid + " derived confidence")
            chosen_answers[qid] = answer["choice"]
        predicted = proposal(state, chosen_answers)
        check(predicted == outcome["proposal"], cid + " independent predicted-active proposal")
        counts = Counter(operation=1, proposal_exact=1)
        scores = Counter(operation=int(chosen_answers["operation"] == gold["operation"]),
                         proposal_exact=int(predicted == gold_proposal),
                         active_conditional=0, forced_active_conditional=0)
        for qid, answer in gold.items():
            check(answer in questions[qid]["criteria"], cid + "/" + qid + " reference is offered")
            if qid != "operation":
                metric = "forced_active_conditional" if len(questions[qid]["criteria"]) == 1 else "active_conditional"
                counts[metric] += 1
                scores[metric] += chosen_answers[qid] == answer
        check(dict(scores) == outcome["correct"], cid + " independently recomputed row scores")
        for split in ("overall", case["split"]):
            totals[split].update(counts)
            correct[split].update(scores)
            teachers[split][gold["operation"]] += 1
            predictions[split][chosen_answers["operation"]] += 1
        confusion[gold["operation"]][chosen_answers["operation"]] += 1
        per_case.append({"case_id": cid, "split": case["split"], "reference_operation": gold["operation"],
                         "predicted_operation": chosen_answers["operation"], "correct": dict(scores)})

    metrics, baselines = {}, {}
    for split in totals:
        metrics[split] = {name: {"correct": correct[split][name], "total": totals[split][name],
                                "accuracy": correct[split][name] / totals[split][name] if totals[split][name] else None}
                          for name in METRICS}
        reported = report["overall"] if split == "overall" else report["by_split"][split]
        check(metrics[split] == reported["metrics"], "independent aggregate metrics: " + split)
        check(dict(teachers[split]) == reported["teacher_operations"], "teacher operation counts: " + split)
        check(reported["cases"] == totals[split]["operation"], "reported case count: " + split)
        baselines[split] = {operation: {"operation_correct": teachers[split][operation],
                                       "proposal_exact_correct": teachers[split][operation],
                                       "total": totals[split]["operation"]}
                            for operation in ("BLOCKED", "DONE", "WAIT")}
    check([totals["overall"][name] for name in METRICS] == [120, 98, 16, 120], "frozen overall denominators")
    check([totals["test"][name] for name in METRICS] == [60, 56, 9, 60], "frozen test denominators")
    check([totals["ood"][name] for name in METRICS] == [60, 42, 7, 60], "frozen OOD denominators")
    check(report["status"] == "complete" and report["complete"] is True
          and report["selected_cases"] == report["attempted_cases"] == 120
          and report["pending_cases"] == report["error_cases"] == 0
          and report["status_counts"] == {"ok": 120}, "final complete status")
    return {"status": "passed" if not errors else "failed", "checks": checked, "errors": errors,
            "source_sha256": SOURCE_SHA256, "source_manifest_sha256": MANIFEST_SHA256,
            "selection_sha256": SELECTION_SHA256, "service_identity": expected_identity,
            "metrics": metrics, "teacher_operations": teachers, "predicted_operations": predictions,
            "operation_confusion": confusion, "constant_operation_baselines": baselines,
            "per_case": per_case, "suite_snapshot": transfer["suite_manifest_snapshot"],
            "scope": "Independent offline scoring against saved synthetic references; no independent relabeling, browser execution, or GPU inference. Whole-suite completion is checked against the separately archived final manifest. Constant-operation baselines describe agreement, not goal progress. Forced single-candidate accuracy is not a learned choice result."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REPO / "data/browser-v1/cases.jsonl")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.source)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "per_case"}, indent=2))
    raise SystemExit(result["status"] != "passed")
