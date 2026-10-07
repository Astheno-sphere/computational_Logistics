"""Original response-body controls for the is_silent_failure Noul contract."""

import argparse
from collections import Counter
import hashlib
from html import escape
import json
from pathlib import Path
import random

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group

VERSION = "silent-failure-control-v1"
QUESTION = (
    "Does this response body show that the current operation failed or did not deliver "
    "its stated required result? Judge only the body. Maintenance or a sign-in page "
    "replacing the requested result counts as failure, even when a field claims success. "
    "A valid empty result, explicitly accepted asynchronous work, allowed partial data, "
    "quoted error text, or an earlier incident that has recovered does not by itself count."
)
SOURCE_COMMIT = "c490e0dc7830758f84bd9d5acb806655e327113e"
SOURCE_URL = (
    "https://github.com/Vicente-MD/jev-resilience/blob/" + SOURCE_COMMIT
    + "/src/main/java/ai/jev/resilience/client/JevEvaluationService.java#L50-L55"
)
SPLIT_POLICY = "whole_provider_contract_family_and_counterfactual_pairs; hash_id_splits; reserved_zh_schema_layout_and_wording_ood"
PAIRS = (
    "html_maintenance", "html_login", "business_rejection", "required_receipt",
    "empty_search", "history_current", "quoted_error", "async_job",
    "partial_batch", "error_count", "freshness", "complete_segments",
)
RULES = {
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
    "document": ("Return the requested document in the Document field.", "请在文档字段内返回所请求的文档。"),
}
CURRENT = {
    "html_maintenance": (("Service available; maintenance has ended.", "Service offline for maintenance; no requested document was produced."),
                         ("维护已经结束，服务可用。", "服务正在停机维护，尚未生成所请求的文档。")),
    "html_login": (("Requested document returned; the sign-in link is informational.", "Sign-in is required; this page replaces the requested document."),
                   ("已返回所请求的文档；登录链接只是页面说明。", "需要登录；当前页面取代了所请求的文档。")),
}
SUBJECTS = ("orchid", "granite", "cedar", "amber", "willow", "coral", "maple", "quartz")


def silent_failure_request(body: str) -> dict:
    """Preserve the actual body string; transport status and references stay outside."""
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a nonempty stringified response body")
    return {"state": body, "questions": {"is_silent_failure": {"type": "noul", "instructions": QUESTION}}}


def _ordered(mapping, nonce):
    keys = list(mapping)
    random.Random(nonce).shuffle(keys)
    return {key: mapping[key] for key in keys}


def _json_body(context, pair, failed, zh, nonce, count, layout):
    provider, request_id, action = context
    receipt_id = "r-" + _hash([request_id, "receipt"])[:12]
    job_id = "j-" + _hash([request_id, "job"])[:12]
    terms = RULES[pair][zh]
    if pair == "business_rejection":
        data = {"success": True, "reservation": {"status": (("confirmed", "rejected"), ("已确认", "已拒绝"))[zh][failed],
                "reason": (("capacity exhausted", "预约容量已用尽")[zh] if failed else None), "receipt_id": None if failed else receipt_id}}
    elif pair == "required_receipt":
        # The visible terms establish the requirement; {} alone would be ambiguous.
        shells = ({}, None, {"receipt_id": ""}, {"receipt_id": None}, {"receipt_id": "  "})
        data = {"success": True, "receipt": shells[int(nonce[:4], 16) % len(shells)] if failed else {"receipt_id": receipt_id}}
    elif pair == "empty_search":
        data = {"success": True, "search": {"matches": [], "complete": not failed,
                "error": (("index unavailable; search not executed", "索引不可用，检索尚未执行")[zh] if failed else None)}}
    elif pair == "history_current":
        status = (("completed", "failed"), ("已完成", "失败"))[zh]
        scopes = ("previous", "current") if not zh else ("先前", "本次")
        events = [{"scope": scopes[0], "status": status[not failed]}, {"scope": scopes[1], "status": status[failed]}]
        random.Random(nonce).shuffle(events)
        data = {"events": events}
    elif pair == "quoted_error":
        quote = ("Example only: 'ERROR: upstream unavailable'. This line explains a diagnostic message.",
                 "仅为示例：『错误：上游不可用』。这段话是在解释诊断信息。")[zh]
        data = {"fetch": {"complete": not failed}, "document": None if failed else {"title": action, "text": quote},
                "documentation_example": quote, "error": (("requested document could not be read", "无法读取所请求的文档")[zh] if failed else None)}
    elif pair == "async_job":
        data = {"success": True, "job": {"status": (("queued", "rejected"), ("已入队", "已拒绝"))[zh][failed],
                "job_id": None if failed else job_id}, "result": None}
    elif pair == "partial_batch":
        data = {"success": True, "policy": {"partial_allowed": not failed, "requested": count},
                "items": ["i-" + _hash([request_id, i])[:10] for i in range(count - 1)]}
    elif pair == "error_count":
        errors = min(count, 1 + int(nonce[:4], 16) % 3) if failed else 0
        data = {"success": True, "checks": {"required": count, "passed": count - errors, "failed": errors},
                "archive": {"failed": 0 if failed else count}}
    else:
        raise ValueError("unsupported JSON pair")
    data = _ordered(data, nonce)
    if layout == "flat_en":
        body = {"provider": provider, "request_id": request_id, "operation": action, "terms": terms, "response": data}
    elif layout == "envelope_en":
        body = {"request": {"provider": provider, "id": request_id, "operation": action}, "contract": terms, "body": data}
    elif layout == "entries_zh":
        entries = [{"栏目": key, "内容": value} for key, value in (("约定", terms), ("返回", data))]
        random.Random(nonce).shuffle(entries)
        body = {"调用信息": {"服务": provider, "标识": request_id, "动作": action}, "条目": entries}
    elif layout == "nested_zh":
        body = {"服务": provider, "调用": {"标识": request_id, "动作": action, "交付": {"约定": terms, "返回": data}}}
    else:
        raise ValueError("unsupported JSON layout")
    return json.dumps(_ordered(body, nonce), ensure_ascii=False, indent=2 if int(nonce[0], 16) % 2 else None)


def _document_body(context, pair, failed, zh, nonce):
    provider, request_id, action = context
    labels = ("Provider", "Request", "Operation", "Requirement", "Current", "Document") if not zh else ("服务", "调用", "动作", "约定", "现在", "文档")
    values = (provider, request_id, action, RULES["document"][zh], CURRENT[pair][zh][failed], "" if failed else action + " / " + request_id)
    fields = _ordered(dict(zip(labels, values)), nonce)
    if zh:
        content = "".join(f"<dt>{key}</dt><dd>{escape(value)}</dd>" for key, value in fields.items())
        return '<html lang="zh"><body><article><h2>调用回执</h2><dl>' + content + '</dl></article></body></html>'
    content = "".join(f"<p><b>{key}</b>: {escape(value)}</p>" for key, value in fields.items())
    return '<html lang="en"><body><main><h1>Service response</h1>' + content + '</main></body></html>'


def _text_body(context, pair, failed, zh, nonce, count):
    provider, request_id, action = context
    if pair == "freshness":
        names = ("Minimum revision", "Delivered revision", "Cache") if not zh else ("最低修订号", "返回修订号", "缓存")
        values = (str(count), str(count - 1 if failed else count + int(nonce[:2], 16) % 2), ("hit", "命中")[zh])
    else:
        names = ("Requested segments", "Delivered segments", "Archived failed segments") if not zh else ("请求片段数", "交付片段数", "历史失败数")
        values = (str(count), str(count - 1 if failed else count), str(count + 1))
    base_names = ("Provider", "Request", "Operation", "Requirement", "Claim") if not zh else ("服务", "调用", "动作", "约定", "声明")
    fields = dict(zip(base_names, (provider, request_id, action, RULES[pair][zh], ("ready", "已就绪")[zh])))
    fields.update(zip(names, values))
    separator, heading = (" => ", "返回单") if zh else (": ", "Response record")
    return heading + "\n" + "\n".join(key + separator + value for key, value in _ordered(fields, nonce).items())


def generate(groups=400, seed=42, ood_groups=80):
    if type(groups) is not int or type(ood_groups) is not int or not 1 <= ood_groups < groups:
        raise ValueError("require integer groups > ood_groups >= 1")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rows = []
    for index in range(groups):
        code = _hash([VERSION, seed, index])[:16]
        provider = f"service-{code}.example"
        group_id = "silent:" + code
        zh = index >= groups - ood_groups
        split = "ood" if zh else split_group(group_id, seed)
        subject = SUBJECTS[index % len(SUBJECTS)] + "-" + code[:6]
        for pair_index, pair in enumerate(PAIRS):
            nonce = _hash([code, pair_index])[:16]
            request_id = "call-" + nonce
            action = ("Requested resource " + subject) if not zh else ("请求资源：" + subject)
            context = (provider, request_id, action)
            count = 3 + int(nonce[2:6], 16) % 7
            if pair.startswith("html_"):
                fmt, layout = "html", "definition_zh" if zh else "paragraph_en"
            elif pair in ("freshness", "complete_segments"):
                fmt, layout = "text", "receipt_zh" if zh else "record_en"
            else:
                fmt = "json"
                layout = ("entries_zh", "nested_zh")[index % 2] if zh else ("flat_en", "envelope_en")[index % 2]
            for failed in (False, True):
                if fmt == "html":
                    body = _document_body(context, pair, failed, zh, nonce)
                elif fmt == "text":
                    body = _text_body(context, pair, failed, zh, nonce, count)
                else:
                    body = _json_body(context, pair, failed, zh, nonce, count, layout)
                compiled = compile_request(**silent_failure_request(body))[0]
                rows.append({"id": "sf-" + _hash([nonce, failed])[:24], "group_id": group_id, "split": split,
                    "source": VERSION, **{key: compiled[key] for key in ("state", "question", "kind", "options")},
                    "target": [0.0, 1.0] if failed else [1.0, 0.0],
                    "metadata": {"family": "evidence", "domain": VERSION, "question_id": "is_silent_failure",
                        "template_id": f"{VERSION}:{layout}:{pair}", "pair": pair, "body_format": fmt, "layout": layout,
                        "entity_ids": [provider, request_id], "provenance": {"type": "synthetic", "generator_version": VERSION,
                            "seed": seed, "group_index": index, "variant": 2 * pair_index + int(failed),
                            "license": "CC0-1.0", "split_policy": SPLIT_POLICY}}})
    random.Random(seed).shuffle(rows)
    return rows


def build_dataset(output_dir, groups=400, seed=42, ood_groups=80):
    output = Path(output_dir)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Choose a new empty silent-failure directory; existing corpora are never overwritten")
    root = Path(__file__).resolve().parents[1]
    sources = ("jev/silent_failure_data.py", "jev/api.py", "jev/data.py", "reports/silent-failure-control-v1/verify.py")
    config = {"type": "synthetic", "generator_version": VERSION, "groups": groups, "ood_groups": ood_groups,
        "seed": seed, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
        "source_contract": {"repository": "Vicente-MD/jev-resilience", "commit": SOURCE_COMMIT, "url": SOURCE_URL,
            "source_code_imported": False, "source_examples_imported": False, "question_independently_authored": True},
        "runtime_contract": {"state": "stringified response body only", "question_id": "is_silent_failure", "type": "noul",
            "transport_status_is_model_input": False, "judge_transport_fallback_is_training_target": False},
        "source_files_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sources}}
    rows = generate(groups, seed, ood_groups)
    manifest = _write_dataset(rows, output, config)
    manifest.update(pair_count=groups * len(PAIRS), records_per_group=24,
        label_counts=dict(Counter("yes" if row["target"][1] else "no" for row in rows)),
        format_counts=dict(Counter(row["metadata"]["body_format"] for row in rows)),
        family_counts={split: len({row["group_id"] for row in rows if row["split"] == split}) for split in SPLITS},
        training_performed=False, model_inference_performed=False, frozen_training_datasets_modified=False,
        scope="Controlled original response-body contracts, not arbitrary API correctness or a measured model capability.")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--groups", type=int, default=400)
    parser.add_argument("--ood-groups", type=int, default=80)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed, args.ood_groups), indent=2))


if __name__ == "__main__":
    main()
