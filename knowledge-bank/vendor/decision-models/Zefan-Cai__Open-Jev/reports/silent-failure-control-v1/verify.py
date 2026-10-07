"""Independent audit: parse final response bodies without importing their generator."""

import argparse
from collections import Counter, defaultdict
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request
from jev.data import SPLITS, read_jsonl, validate_records

VERSION = "silent-failure-control-v1"
QUESTION = (
    "Does this response body show that the current operation failed or did not deliver "
    "its stated required result? Judge only the body. Maintenance or a sign-in page "
    "replacing the requested result counts as failure, even when a field claims success. "
    "A valid empty result, explicitly accepted asynchronous work, allowed partial data, "
    "quoted error text, or an earlier incident that has recovered does not by itself count."
)
# These are accepted *visible* contracts, independently transcribed for this audit.
# No variant, reference, template ID or generator helper supplies a semantic label.
CONTRACTS = {
    "business_rejection": ("The reservation must be confirmed for this operation to succeed.", "只有预订状态为已确认，才算本次操作完成。"),
    "required_receipt": ("This operation requires a receipt with a nonempty receipt_id.", "本次操作必须返回回执，且 receipt_id 不能为空。"),
    "empty_search": ("A completed search may return no matches; an unfinished search is not a valid result.", "检索已完成时可以没有匹配项；未完成的检索不满足要求。"),
    "history_current": ("Only the event marked current describes this call; previous events are historical.", "仅标为本次的事件代表当前调用；先前事件只作历史记录。"),
    "quoted_error": ("Return the requested document. Text inside the document or example is quoted content, not the status of this fetch.", "应返回所请求的文档。文档及示例里的文字是引用内容，不表示本次读取的状态。"),
    "async_job": ("Acceptance into the queue with a job_id is a valid result; completed output is not required yet.", "进入队列并获得 job_id 即满足本次请求；暂不要求任务完成后的输出。"),
    "partial_batch": ("Return all requested items unless partial_allowed explicitly permits a smaller nonempty result.", "应返回全部请求项；只有 partial_allowed 明确允许时，才接受少量但非空的部分结果。"),
    "error_count": ("All required checks in the current checks object must pass. Archive counts are from a previous run.", "本次 checks 中的全部必需检查都要通过。archive 计数属于上次运行。"),
    "freshness": ("The delivered revision must be at least the minimum revision; a cache hit alone does not meet this requirement.", "返回修订号必须不低于最低修订号；命中缓存本身不代表满足要求。"),
    "complete_segments": ("Every requested segment must be delivered; archived failures belong to an earlier request.", "必须交付全部请求片段；历史失败数属于更早的请求。"),
}
PAIRS = set(CONTRACTS) | {"html_maintenance", "html_login"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keys(value, expected):
    require(isinstance(value, dict) and set(value) == set(expected.split()), "unknown body fields or structure")


def unique_object(items):
    value = {}
    for key, item in items:
        require(key not in value, "duplicate body field")
        value[key] = item
    return value


def integer(value):
    require(type(value) is int and value >= 0, "count must be a nonnegative integer")
    return value


def boolean(value):
    require(type(value) is bool, "expected a boolean")
    return value


def success_claim(data):
    require(data["success"] is True, "unsupported or contradictory success claim")


def populated(value):
    return isinstance(value, str) and bool(value.strip())


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_json(body):
    obj = json.loads(body, object_pairs_hook=unique_object)
    require(isinstance(obj, dict), "unknown JSON body structure")
    if "provider" in obj:
        keys(obj, "provider request_id operation terms response")
        return (obj["provider"], obj["request_id"], obj["operation"]), obj["terms"], obj["response"], "flat_en", False
    if "request" in obj:
        keys(obj, "request contract body")
        context = obj["request"]
        keys(context, "provider id operation")
        return (context["provider"], context["id"], context["operation"]), obj["contract"], obj["body"], "envelope_en", False
    if "条目" in obj:
        keys(obj, "调用信息 条目")
        context = obj["调用信息"]
        keys(context, "服务 标识 动作")
        require(isinstance(obj["条目"], list), "unknown entries structure")
        entries = []
        for entry in obj["条目"]:
            keys(entry, "栏目 内容")
            entries.append((entry["栏目"], entry["内容"]))
        fields = unique_object(entries)
        keys(fields, "约定 返回")
        return (context["服务"], context["标识"], context["动作"]), fields["约定"], fields["返回"], "entries_zh", True
    keys(obj, "服务 调用")
    context = obj["调用"]
    keys(context, "标识 动作 交付")
    keys(context["交付"], "约定 返回")
    return (obj["服务"], context["标识"], context["动作"]), context["交付"]["约定"], context["交付"]["返回"], "nested_zh", True


def json_semantics(terms, data, zh):
    matches = [name for name, wording in CONTRACTS.items() if terms == wording[zh]]
    require(len(matches) == 1, "unknown or altered visible contract")
    pair = matches[0]
    if pair == "business_rejection":
        keys(data, "success reservation")
        success_claim(data)
        reservation = data["reservation"]
        keys(reservation, "status reason receipt_id")
        accepted, rejected = ("已确认", "已拒绝") if zh else ("confirmed", "rejected")
        require(reservation["status"] in (accepted, rejected), "unknown reservation status")
        failed = reservation["status"] != accepted
        require(reservation["reason"] is None or populated(reservation["reason"]), "invalid rejection reason")
        require(failed or reservation["reason"] is None, "contradictory reservation reason")
        evidence = {"reservation_status": reservation["status"]}
    elif pair == "required_receipt":
        keys(data, "success receipt")
        success_claim(data)
        receipt = data["receipt"]
        require(receipt is None or isinstance(receipt, dict) and set(receipt) <= {"receipt_id"}, "unknown receipt fields")
        failed = not (receipt and populated(receipt.get("receipt_id")))
        evidence = {"nonempty_required_receipt_id": not failed}
    elif pair == "empty_search":
        keys(data, "success search")
        success_claim(data)
        search = data["search"]
        keys(search, "matches complete error")
        require(isinstance(search["matches"], list), "search matches must be an array")
        require(search["error"] is None or populated(search["error"]), "invalid search error")
        failed = not boolean(search["complete"]) or search["error"] is not None
        evidence = {"complete": search["complete"], "error": search["error"], "match_count": len(search["matches"])}
    elif pair == "history_current":
        keys(data, "events")
        require(isinstance(data["events"], list) and len(data["events"]) == 2, "expected current and historical events")
        scopes = ("先前", "本次") if zh else ("previous", "current")
        status = ("已完成", "失败") if zh else ("completed", "failed")
        events = []
        for event in data["events"]:
            keys(event, "scope status")
            require(event["status"] in status, "unknown event status")
            events.append((event["scope"], event["status"]))
        events = unique_object(events)
        require(set(events) == set(scopes), "unknown event scope")
        failed = events[scopes[1]] != status[0]
        evidence = {"current_event": events[scopes[1]], "ignored_previous_event": events[scopes[0]]}
    elif pair == "quoted_error":
        keys(data, "fetch document documentation_example error")
        keys(data["fetch"], "complete")
        require(populated(data["documentation_example"]), "missing quoted example")
        document = data["document"]
        if document is not None:
            keys(document, "title text")
            require(populated(document["title"]) and populated(document["text"]), "incomplete document")
        require(data["error"] is None or populated(data["error"]), "invalid fetch error")
        failed = not boolean(data["fetch"]["complete"]) or document is None or data["error"] is not None
        evidence = {"fetch_complete": data["fetch"]["complete"], "document_returned": document is not None, "current_error": data["error"]}
    elif pair == "async_job":
        keys(data, "success job result")
        success_claim(data)
        keys(data["job"], "status job_id")
        queued, rejected = ("已入队", "已拒绝") if zh else ("queued", "rejected")
        require(data["job"]["status"] in (queued, rejected), "unknown job state")
        failed = data["job"]["status"] != queued or not populated(data["job"]["job_id"])
        evidence = {"job_status": data["job"]["status"], "job_id_present": populated(data["job"]["job_id"])}
    elif pair == "partial_batch":
        keys(data, "success policy items")
        success_claim(data)
        keys(data["policy"], "partial_allowed requested")
        require(isinstance(data["items"], list) and all(populated(v) for v in data["items"]), "invalid returned items")
        require(len(set(data["items"])) == len(data["items"]), "duplicate returned items")
        allowed = boolean(data["policy"]["partial_allowed"])
        requested, delivered = integer(data["policy"]["requested"]), len(data["items"])
        require(requested > 0 and delivered <= requested, "unsupported batch cardinality")
        failed = delivered != requested and not (allowed and delivered > 0)
        evidence = {"partial_allowed": allowed, "requested": requested, "delivered": delivered}
    elif pair == "error_count":
        keys(data, "success checks archive")
        success_claim(data)
        keys(data["checks"], "required passed failed")
        keys(data["archive"], "failed")
        integer(data["archive"]["failed"])
        required, passed, errors = (integer(data["checks"][name]) for name in ("required", "passed", "failed"))
        require(required > 0 and passed + errors == required, "inconsistent current check counts")
        failed = errors > 0
        evidence = {"required": required, "passed": passed, "current_failed": errors, "ignored_archive_failed": data["archive"]["failed"]}
    else:
        raise ValueError("text contract found in JSON body")
    return pair, bool(failed), evidence


def html_semantics(body):
    zh = body.startswith('<html lang="zh">')
    if zh:
        prefix, suffix = '<html lang="zh"><body><article><h2>调用回执</h2><dl>', '</dl></article></body></html>'
        pattern, names = r"<dt>([^<>]+)</dt><dd>([^<>]*)</dd>", ("服务", "调用", "动作", "约定", "现在", "文档")
        contract = "请在文档字段内返回所请求的文档。"
        maintenance = ("维护已经结束，服务可用。", "服务正在停机维护，尚未生成所请求的文档。")
        login = ("已返回所请求的文档；登录链接只是页面说明。", "需要登录；当前页面取代了所请求的文档。")
    else:
        prefix, suffix = '<html lang="en"><body><main><h1>Service response</h1>', '</main></body></html>'
        pattern, names = r"<p><b>([^<>]+)</b>: ([^<>]*)</p>", ("Provider", "Request", "Operation", "Requirement", "Current", "Document")
        contract = "Return the requested document in the Document field."
        maintenance = ("Service available; maintenance has ended.", "Service offline for maintenance; no requested document was produced.")
        login = ("Requested document returned; the sign-in link is informational.", "Sign-in is required; this page replaces the requested document.")
    require(body.startswith(prefix) and body.endswith(suffix), "unknown HTML structure")
    content = body[len(prefix):-len(suffix)]
    matches = list(re.finditer(pattern, content))
    require("".join(match.group() for match in matches) == content, "unknown HTML content")
    fields = unique_object((unescape(m[1]), unescape(m[2])) for m in matches)
    require(set(fields) == set(names), "unknown HTML fields")
    provider, request, action, terms, current, document = (fields[name] for name in names)
    require(terms == contract, "unknown or altered visible document contract")
    require(current in maintenance + login, "unknown current document status")
    pair = "html_maintenance" if current in maintenance else "html_login"
    failed = current in (maintenance[1], login[1]) or not populated(document)
    return (provider, request, action), pair, failed, {"current": current, "document_present": populated(document)}, "definition_zh" if zh else "paragraph_en", zh


def text_semantics(body):
    lines = body.splitlines()
    zh = lines[0] == "返回单"
    require(lines[0] in ("返回单", "Response record"), "unknown text header")
    separator = " => " if zh else ": "
    require(all(separator in line for line in lines[1:]), "unknown text fields")
    fields = unique_object(line.split(separator, 1) for line in lines[1:])
    names = ("服务", "调用", "动作", "约定", "声明") if zh else ("Provider", "Request", "Operation", "Requirement", "Claim")
    require(all(name in fields for name in names), "missing text fields")
    provider, request, action, terms, claim = (fields[name] for name in names)
    require(claim == ("已就绪" if zh else "ready"), "unknown text claim")
    if terms == CONTRACTS["freshness"][zh]:
        pair = "freshness"
        extra = ("最低修订号", "返回修订号", "缓存") if zh else ("Minimum revision", "Delivered revision", "Cache")
    elif terms == CONTRACTS["complete_segments"][zh]:
        pair = "complete_segments"
        extra = ("请求片段数", "交付片段数", "历史失败数") if zh else ("Requested segments", "Delivered segments", "Archived failed segments")
    else:
        raise ValueError("unknown or altered visible text contract")
    require(set(fields) == set(names + extra), "unknown text fields")
    require(all(re.fullmatch(r"0|[1-9][0-9]*", fields[name]) for name in extra[:2]), "invalid numeric field")
    needed, delivered = (int(fields[name]) for name in extra[:2])
    if pair == "freshness":
        require(fields[extra[2]] == ("命中" if zh else "hit"), "unknown cache field")
        failed = delivered < needed
    else:
        require(re.fullmatch(r"0|[1-9][0-9]*", fields[extra[2]]), "invalid archive count")
        require(needed > 0 and delivered <= needed, "unsupported segment cardinality")
        failed = delivered != needed
    return (provider, request, action), pair, failed, {"required": needed, "delivered": delivered}, "receipt_zh" if zh else "record_en", zh


def derive(body):
    """Return body-derived truth for the corpus grammar; reject unknown bodies."""
    require(isinstance(body, str) and body.strip(), "body must be a nonempty string")
    if body.lstrip().startswith("{"):
        context, terms, data, layout, zh = decode_json(body)
        pair, failed, evidence = json_semantics(terms, data, zh)
        fmt = "json"
    elif body.startswith("<"):
        context, pair, failed, evidence, layout, zh = html_semantics(body)
        fmt = "html"
    else:
        context, pair, failed, evidence, layout, zh = text_semantics(body)
        fmt = "text"
    require(all(populated(value) for value in context), "missing visible request identity")
    return {"is_silent_failure": failed, "pair": pair, "body_format": fmt, "layout": layout,
            "provider": context[0], "request_id": context[1], "operation": context[2], "ood": zh, "evidence": evidence}


def verify(directory, audit_rows_path=None):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest.get("schema_version") == 1, "unexpected schema version")
    require(manifest.get("model_input_fields") == ["state", "question", "kind", "options"], "model input fields differ")
    expected_files = {split + ".jsonl" for split in SPLITS}
    require(set(manifest["files_sha256"]) == expected_files, "split file set differs")
    for name, expected in manifest["files_sha256"].items():
        require(sha256(directory / name) == expected, "file checksum differs: " + name)
    config = manifest["configuration"]
    require(config["generator_version"] == VERSION, "generator version differs")
    require(config["type"] == "synthetic" and config["license"] == "CC0-1.0", "data provenance differs")
    require(type(config["groups"]) is int and type(config["ood_groups"]) is int and 1 <= config["ood_groups"] < config["groups"], "invalid family counts")
    require(type(config["seed"]) is int, "invalid split seed")
    require(config["split_policy"] == "whole_provider_contract_family_and_counterfactual_pairs; hash_id_splits; reserved_zh_schema_layout_and_wording_ood", "split policy differs")
    require(config["source_contract"] == {"repository": "Vicente-MD/jev-resilience",
        "commit": "c490e0dc7830758f84bd9d5acb806655e327113e",
        "url": "https://github.com/Vicente-MD/jev-resilience/blob/c490e0dc7830758f84bd9d5acb806655e327113e/src/main/java/ai/jev/resilience/client/JevEvaluationService.java#L50-L55",
        "source_code_imported": False, "source_examples_imported": False, "question_independently_authored": True}, "source contract provenance differs")
    require(config["runtime_contract"] == {"state": "stringified response body only", "question_id": "is_silent_failure", "type": "noul",
        "transport_status_is_model_input": False, "judge_transport_fallback_is_training_target": False}, "runtime contract declaration differs")
    require(all(manifest.get(name) is False for name in ("training_performed", "model_inference_performed", "frozen_training_datasets_modified")), "unverified training/inference declaration")
    expected_sources = {"jev/silent_failure_data.py", "jev/api.py", "jev/data.py", "reports/silent-failure-control-v1/verify.py"}
    require(set(config["source_files_sha256"]) == expected_sources, "source hash set differs")
    for name, expected in config["source_files_sha256"].items():
        require(sha256(ROOT / name) == expected, "source checksum differs: " + name)
    rows = []
    for split in SPLITS:
        values = list(read_jsonl(directory / (split + ".jsonl")))
        require(all(row["split"] == split for row in values), "row split differs from file")
        rows.extend(values)
    summary = validate_records(rows)
    require(summary == manifest["summary"], "manifest summary differs")
    require(summary["records"] == config["groups"] * 24 and summary["unique_inputs"] == summary["records"], "family size or unique body count differs")
    groups, providers, requests = defaultdict(list), {}, defaultdict(list)
    counts, labels, formats, families, layouts = Counter(), Counter(), Counter(), defaultdict(set), Counter()
    audited = []
    for row in rows:
        result = derive(row["state"])
        expected = [0.0, 1.0] if result["is_silent_failure"] else [1.0, 0.0]
        require(row["target"] == expected, row["id"] + ": target differs from visible body")
        compiled = compile_request(row["state"], {"is_silent_failure": {"type": "noul", "instructions": QUESTION}})[0]
        require(all(row[key] == compiled[key] for key in ("state", "question", "kind", "options")), "runtime request compilation differs")
        require(row["source"] == VERSION, "source differs")
        metadata = row["metadata"]
        require(metadata["question_id"] == "is_silent_failure" and metadata["domain"] == VERSION, "metadata domain/question differs")
        provenance = metadata["provenance"]
        require(metadata["family"] == "evidence" and provenance["type"] == "synthetic" and provenance["license"] == "CC0-1.0", "row provenance differs")
        require(provenance["generator_version"] == VERSION and provenance["seed"] == config["seed"] and provenance["split_policy"] == config["split_policy"], "row generation provenance differs")
        for name in ("pair", "body_format", "layout"):
            require(metadata[name] == result[name], "metadata differs from rendered body: " + name)
        require(metadata["entity_ids"] == [result["provider"], result["request_id"]], "entities differ from visible body")
        require(metadata["template_id"] == f"{VERSION}:{result['layout']}:{result['pair']}", "template differs from body layout")
        code = re.fullmatch(r"service-([0-9a-f]{16})\.example", result["provider"])
        require(code is not None and row["group_id"] == "silent:" + code[1], "visible provider crosses family groups")
        require(re.fullmatch(r"call-[0-9a-f]{16}", result["request_id"]), "unknown request identity")
        require(result["ood"] == (row["split"] == "ood"), "reserved OOD body structure leaked")
        if not result["ood"]:
            digest = hashlib.sha256(json.dumps([config["seed"], row["group_id"]], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            bucket = int(digest[:16], 16) % 10000
            expected_split = next(name for limit, name in ((8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test")) if bucket < limit)
            require(row["split"] == expected_split, "ID family does not follow the sealed hash split")
        require(result["provider"] not in providers or providers[result["provider"]] == row["group_id"], "provider crosses family groups")
        providers[result["provider"]] = row["group_id"]
        groups[row["group_id"]].append(result)
        requests[result["request_id"]].append((row["group_id"], result["pair"], result["is_silent_failure"]))
        label = "yes" if result["is_silent_failure"] else "no"
        counts[(row["split"], result["pair"], label)] += 1
        labels[label] += 1
        formats[result["body_format"]] += 1
        layouts[result["layout"]] += 1
        families[row["split"]].add(row["group_id"])
        audited.append({"id": row["id"], "body_sha256": hashlib.sha256(row["state"].encode()).hexdigest(), **result})
    require(len(groups) == config["groups"] and len(families["ood"]) == config["ood_groups"], "family count differs")
    for group, values in groups.items():
        observed = Counter((value["pair"], value["is_silent_failure"]) for value in values)
        require(observed == Counter({(pair, failed): 1 for pair in PAIRS for failed in (False, True)}), "counterfactual family is incomplete: " + group)
        require(len({value["operation"] for value in values}) == 1, "operation identity differs within family")
    for request, values in requests.items():
        require(len(values) == 2 and values[0][:2] == values[1][:2] and values[0][2] != values[1][2], "request counterfactual leaked or missing: " + request)
    require(manifest["pair_count"] == len(requests) and manifest["records_per_group"] == 24, "manifest pair count differs")
    require(manifest["label_counts"] == dict(labels) and manifest["format_counts"] == dict(formats), "manifest category counts differ")
    family_counts = {split: len(families[split]) for split in SPLITS}
    require(manifest["family_counts"] == family_counts, "manifest family split counts differ")
    audit_sha = None
    if audit_rows_path:
        path = Path(audit_rows_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in audited), encoding="utf-8")
        audit_sha = sha256(path)
    return {"status": "passed", "dataset": VERSION, "method": "independent parsing of the final body; generator not imported",
        "summary": summary, "family_counts": family_counts, "counterfactual_pairs": len(requests), "label_counts": dict(labels),
        "format_counts": dict(formats), "layout_counts": dict(layouts),
        "split_pair_label_counts": [{"split": split, "pair": pair, "label": label, "records": n} for (split, pair, label), n in sorted(counts.items())],
        "body_length_characters": {"min": min(len(row["state"]) for row in rows), "max": max(len(row["state"]) for row in rows)},
        "manifest_sha256": sha256(directory / "manifest.json"), "files_sha256": manifest["files_sha256"],
        "source_files_sha256": config["source_files_sha256"], "body_audit_sha256": audit_sha,
        "all_labels_derived_from_body": True, "all_counterfactuals_isolated": True, "ood_layouts_reserved": True,
        "model_inference_performed": False, "training_performed": False,
        "scope": "Finite original body grammar only; unknown or ambiguous bodies raise instead of receiving a guessed negative label."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit-rows", type=Path)
    args = parser.parse_args()
    result = verify(args.data, args.audit_rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
