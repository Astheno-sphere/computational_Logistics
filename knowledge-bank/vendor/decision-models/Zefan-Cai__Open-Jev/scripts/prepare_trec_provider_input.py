"""Freeze text-only TREC provider inputs; keep all real passages under ignored runs/."""
import argparse
import hashlib
import json
from pathlib import Path

import tiktoken

from jev.ir_eval import load_external_holdout

MANIFESTS = {
    "dl19": ("84c7cc23ce0f7309a48432c449e7856aeff96f9e2571f1f18cdb405703a6c297", 43),
    "dl20": ("494d6f39537b65981ea6707c7ba232e890460ad8f51e86628d2c2a5547288ea4", 54),
}
PROTOCOL = {"method": "listwise_score", "request_profile": "general-ir-v1",
            "window_size": 20, "step_size": 10, "top_k": 100,
            "tokenizer": "cl100k_base", "query_max_tokens": 32, "passage_max_tokens": 128}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, output):
    if tiktoken.__version__ != "0.11.0":
        raise ValueError("Use tiktoken==0.11.0 for the frozen truncation contract")
    if not output.resolve().is_relative_to((Path.cwd() / "runs").resolve()):
        raise ValueError("Real TREC inputs must remain inside ignored runs/")
    if output.exists():
        raise ValueError("Output already exists; never replace frozen provider inputs")
    encoding = tiktoken.get_encoding("cl100k_base")
    stats = {kind: {"count": 0, "truncated": 0, "original_max_tokens": 0,
                    "returned_max_tokens": 0, "returned_total_tokens": 0,
                    "new_replacement_characters": 0, "reencoded_above_prefix_limit": 0} for kind in ("query", "passage")}

    def truncate(text, kind):
        limit = PROTOCOL[f"{kind}_max_tokens"]
        tokens = encoding.encode(text)
        value = encoding.decode(tokens[:limit])
        returned = encoding.encode(value)
        if not value.strip():
            raise ValueError("Truncation produced empty text")
        item = stats[kind]
        item["count"] += 1
        item["reencoded_above_prefix_limit"] += len(returned) > limit
        item["truncated"] += len(tokens) > limit
        item["original_max_tokens"] = max(item["original_max_tokens"], len(tokens))
        item["returned_max_tokens"] = max(item["returned_max_tokens"], len(returned))
        item["returned_total_tokens"] += len(returned)
        item["new_replacement_characters"] += max(0, value.count("\ufffd") - text.count("\ufffd"))
        return value

    queries, sources = [], {}
    for benchmark, (expected, count) in MANIFESTS.items():
        path = root / benchmark / "manifest.json"
        if sha(path) != expected:
            raise ValueError("Prepared source manifest differs")
        source = load_external_holdout(path)
        if len(source["queries"]) != count or set(source["queries"]) != set(source["qrels"]):
            raise ValueError("Judged query coverage differs")
        sources[benchmark] = {"manifest_sha256": expected, "query_count": count,
                              "files_sha256": source["manifest"]["files_sha256"]}
        for identifier, row in source["queries"].items():
            queries.append({"benchmark": benchmark, "id": identifier,
                            "query": truncate(row["query"], "query"),
                            "documents": [{"id": doc["id"], "text": truncate(doc["text"], "passage")}
                                          for doc in row["documents"]]})
    document = {"schema_version": 1, "usage": "evaluation_only", "protocol": PROTOCOL, "queries": queries}
    output.mkdir(parents=True)
    path = output / "input.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    report = {"status": "prepared_not_evaluated", "input_sha256": sha(path),
              "input_bytes": path.stat().st_size, "source_manifests": sources,
              "preparation_source_sha256": sha(Path(__file__)), "tiktoken_version": tiktoken.__version__,
              "protocol": PROTOCOL, "truncation": "decode(encode(text)[:limit]) with default replacement decoding, matching the author token-prefix policy. The re-encoded string can exceed the prefix limit; these cases and new U+FFFD characters are counted, not silently repaired.",
              "token_statistics": stats, "queries": len(queries), "candidate_occurrences": 100 * len(queries),
              "planned_requests_per_provider": 9 * len(queries), "qrels_in_provider_input": False,
              "raw_inputs_publicly_redistributed": False, "model_inference_performed": False,
              "scope": "All judged DL19/DL20 queries with their downloaded BM25 top100. Same initial texts, order and algorithm across providers; later sliding windows adapt to each provider's rankings. Full qrels remain separate for later scoring. Truncation limits are approximate cl100k tokens, not Qwen tokenizer limits. Not an exact replay of the community author's prompts, gateway, concurrency or historical mutable model."}
    (output / "preparation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runs/external/ir-holdout/prepared"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.root, args.output)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
