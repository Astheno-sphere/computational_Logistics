"""Validate complete input lengths and pinned model support before GPU work."""
import argparse
import json
from pathlib import Path

from transformers import AutoConfig, AutoTokenizer

from jev.api import candidate_prompts
from jev.data import read_split_directory, validate_records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--revision", required=True)
    p.add_argument("--max-length", type=int, default=1536)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    config = AutoConfig.from_pretrained(args.model, revision=args.revision)
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision)
    rows = list(read_split_directory(args.data))
    validation = validate_records(rows)
    max_seen, longest_id, candidates = 0, None, 0
    for row in rows:
        for prompt in candidate_prompts(row):
            ids = tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                                                tokenize=True, add_generation_prompt=True, enable_thinking=False)
            # Transformers versions may return a BatchEncoding for tokenize=True.
            if isinstance(ids, dict) or hasattr(ids, "input_ids"):
                ids = ids["input_ids"]
            if ids and isinstance(ids[0], list):
                ids = ids[0]
            candidates += 1
            if len(ids) > max_seen:
                max_seen, longest_id = len(ids), row["id"]
    result = {"model": args.model, "revision": args.revision, "model_type": config.model_type,
              "validation": validation, "candidate_sequences": candidates,
              "max_tokens": max_seen, "longest_id": longest_id, "limit": args.max_length}
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    if max_seen > args.max_length:
        raise ValueError("Overlong records found; change the declared limit or dataset policy before launching")


if __name__ == "__main__":
    main()
