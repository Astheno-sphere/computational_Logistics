"""Offline CPU audit of the exact DecisionModel candidate encoding path.

Only tokenizer/config files are read. Checkouts and datasets stay unchanged;
per-row token lengths and model/source provenance are retained outside them.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time


SPLITS = ("train", "calibration", "validation", "test", "ood")


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def process_identity(pids):
    result = {}
    for pid in pids:
        path = Path("/proc") / str(pid) / "stat"
        try:
            result[str(pid)] = {"exists": True, "start_ticks": path.read_text().rsplit(")", 1)[1].split()[19]}
        except FileNotFoundError:
            result[str(pid)] = {"exists": False}
    return result


class LengthStats:
    def __init__(self, limits):
        self.limits = limits
        self.histogram = Counter()
        self.rows = self.padded_tokens = self.max_candidates = self.max_padded = 0
        self.over_rows, self.over_sequences = Counter(), Counter()
        self.longest = self.largest_padded = None

    def add(self, row, lengths):
        self.rows += 1
        self.histogram.update(lengths)
        maximum, padded = max(lengths), max(lengths) * len(lengths)
        self.padded_tokens += padded
        self.max_candidates = max(self.max_candidates, len(lengths))
        identity = {"id": row["id"], "source": row["source"], "kind": row["kind"], "split": row["split"]}
        if self.longest is None or maximum > self.longest["tokens"]:
            self.longest = {**identity, "tokens": maximum, "candidate_index": lengths.index(maximum)}
        if padded > self.max_padded:
            self.max_padded = padded
            self.largest_padded = {**identity, "candidate_sequences": len(lengths), "max_length": maximum,
                                   "padded_tokens": padded}
        for limit in self.limits:
            self.over_rows[limit] += maximum > limit
            self.over_sequences[limit] += sum(length > limit for length in lengths)

    def report(self):
        total = sum(self.histogram.values())
        tokens = sum(length * count for length, count in self.histogram.items())
        def quantile(fraction):
            rank, seen = max(1, math.ceil(total * fraction)), 0
            for length, count in sorted(self.histogram.items()):
                seen += count
                if seen >= rank:
                    return length
        return {"rows": self.rows, "candidate_sequences": total, "input_tokens": tokens,
                "min_tokens": min(self.histogram, default=None), "max_tokens": max(self.histogram, default=None),
                "mean_tokens": tokens / total if total else None,
                "percentiles_nearest_rank": {str(q): quantile(q / 100) for q in (50, 90, 95, 99)},
                "padded_tokens_if_each_row_encoded_separately": self.padded_tokens,
                "max_candidate_sequences_per_row": self.max_candidates, "longest_candidate": self.longest,
                "largest_padded_row": self.largest_padded,
                "over_limits": {str(limit): {"rows": self.over_rows[limit], "candidate_sequences": self.over_sequences[limit]}
                                for limit in self.limits}}


def run(args):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("Set CUDA_VISIBLE_DEVICES='' explicitly for this CPU-only audit")
    if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
        raise ValueError("A frozen 40-character model revision is required")
    if args.batch_rows < 1 or args.max_length < 1 or any(limit < 1 for limit in args.limits):
        raise ValueError("Batch size and context limits must be positive")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("Output directory must be absent or empty")
    for variable in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
        os.environ[variable] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "1"
    denied_weight_opens = []
    def prohibit_weights(event, values):
        if event == "open" and isinstance(values[0], (str, bytes)):
            name = os.fsdecode(values[0])
            if Path(name).suffix in {".safetensors", ".bin", ".pt", ".pth"}:
                denied_weight_opens.append(name)
                raise RuntimeError("Tokenizer-only audit refuses to open a weight/binary data file")
    sys.addaudithook(prohibit_weights)
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from jev.api import candidate_prompts
    from transformers import AutoTokenizer
    def cuda_initialized():
        module = sys.modules.get("torch")
        return bool(module is not None and module.cuda.is_initialized())
    if cuda_initialized():
        raise RuntimeError("CUDA was initialized in a tokenizer-only process")
    source_names = ("jev/model.py", "jev/api.py", "jev/train.py", "scripts/preflight.py", "scripts/launch_expansion.py")
    source_hashes = {name: digest_file(repo / name) for name in source_names}
    if source_hashes["jev/model.py"] != args.expected_encoder_sha256:
        raise ValueError("DecisionModel implementation changed; review the encoding path before auditing")
    manifest_bytes = (args.data / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if set(manifest.get("sha256", {})) != set(SPLITS) or set(manifest.get("counts", {})) != set(SPLITS):
        raise ValueError("This audit requires a frozen mixture manifest with all five hashes and counts")
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision,
                                            cache_dir=str(args.cache_dir), local_files_only=True)
    tokenizer.padding_side = "right"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    snapshot = args.cache_dir / ("models--" + args.model.replace("/", "--")) / "snapshots" / args.revision
    assets = {name: digest_file(snapshot / name) for name in ("config.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja")}
    config = json.loads((snapshot / "config.json").read_text())
    limits = sorted(set(args.limits + [args.max_length]))
    total = LengthStats(limits)
    split_stats = {split: LengthStats(limits) for split in SPLITS}
    source_stats = defaultdict(lambda: LengthStats(limits))
    parity_counts, parity_mismatches = Counter(), []
    before_pids = process_identity(args.observe_pids)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = args.output_dir / "row-lengths.jsonl.gz"
    started = time.perf_counter()
    observed_hashes = {}
    with detail_path.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as details:
        for split in SPLITS:
            batch = []
            file_digest = hashlib.sha256()
            def process_batch():
                rendered, counts, plain = [], [], []
                for row in batch:
                    prompts = candidate_prompts(row)
                    counts.append(len(prompts))
                    plain.extend(prompts)
                    rendered.extend(tokenizer.apply_chat_template([{"role": "user", "content": prompt}],
                                    tokenize=False, add_generation_prompt=True, enable_thinking=False) for prompt in prompts)
                # Same template and tokenizer defaults as DecisionModel.forward.
                # Padding is omitted only for storage efficiency; attention-mask
                # sums are explicitly checked against padded encoding below.
                encoded = tokenizer(rendered, padding=False, truncation=False, return_attention_mask=True)
                offset = 0
                for row, count in zip(batch, counts):
                    ids = encoded["input_ids"][offset:offset + count]
                    lengths = [sum(mask) for mask in encoded["attention_mask"][offset:offset + count]]
                    if lengths != [len(item) for item in ids]:
                        raise ValueError("Unpadded attention masks do not match input lengths")
                    pair = (split, row["source"])
                    if parity_counts[pair] < 2:
                        padded = tokenizer(rendered[offset:offset + count], padding=True, truncation=False,
                                           return_attention_mask=True)
                        if [sum(mask) for mask in padded["attention_mask"]] != lengths:
                            raise ValueError("Length path differs from padded DecisionModel encoding")
                        for candidate, expected in zip(plain[offset:offset + count], ids):
                            previous = tokenizer.apply_chat_template([{"role": "user", "content": candidate}],
                                        tokenize=True, add_generation_prompt=True, enable_thinking=False)
                            if isinstance(previous, dict) or hasattr(previous, "input_ids"):
                                previous = previous["input_ids"]
                            if previous and isinstance(previous[0], list):
                                previous = previous[0]
                            if previous != expected:
                                parity_mismatches.append({"id": row["id"], "actual_tokens": len(expected),
                                                          "old_preflight_tokens": len(previous)})
                        parity_counts[pair] += 1
                    for stats in (total, split_stats[split], source_stats[row["source"]]):
                        stats.add(row, lengths)
                    entry = {"id": row["id"], "split": split, "source": row["source"], "kind": row["kind"],
                             "model_input_sha256": hashlib.sha256(canonical({key: row[key] for key in ("state", "question", "kind", "options")}).encode()).hexdigest(),
                             "candidate_tokens": lengths}
                    details.write((canonical(entry) + "\n").encode())
                    offset += count
            with (args.data / (split + ".jsonl")).open("rb") as source:
                for line in source:
                    file_digest.update(line)
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if row["split"] != split:
                        raise ValueError("Data row is in the wrong split file")
                    batch.append(row)
                    if len(batch) >= args.batch_rows:
                        process_batch()
                        batch.clear()
                        if total.rows % (args.batch_rows * 100) == 0:
                            print(json.dumps({"event": "progress", "rows": total.rows, "split": split,
                                              "elapsed_seconds": time.perf_counter() - started}), flush=True)
                if batch:
                    process_batch()
            observed_hashes[split] = file_digest.hexdigest()
            if observed_hashes[split] != manifest["sha256"][split] or split_stats[split].rows != manifest["counts"][split]:
                raise ValueError("Frozen dataset checksum/count mismatch: " + split)
            print(json.dumps({"event": "split_complete", "split": split, **split_stats[split].report()}), flush=True)
    if (args.data / "manifest.json").read_bytes() != manifest_bytes or any(digest_file(repo / name) != value for name, value in source_hashes.items()):
        raise ValueError("Dataset manifest or inspected code changed during the audit")
    if cuda_initialized() or denied_weight_opens:
        raise RuntimeError("CPU/tokenizer-only invariant violated")
    result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "complete": True,
              "model": args.model, "revision": args.revision, "hostname": socket.gethostname(),
              "script_sha256": digest_file(__file__), "repo": str(repo),
              "repo_commit": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
              "implementation_sha256": source_hashes, "dataset": str(args.data),
              "dataset_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "dataset_split_sha256": observed_hashes,
              "runtime": {"python": sys.version, "transformers": version("transformers"), "tokenizers": version("tokenizers")},
              "tokenizer": {"class": type(tokenizer).__name__, "is_fast": tokenizer.is_fast,
                            "assets_sha256": assets, "special_tokens_added_by_tokenizer": tokenizer.num_special_tokens_to_add(),
                            "model_type": config["model_type"], "model_max_positions": config.get("text_config", config).get("max_position_embeddings")},
              "encoding": {"chat_template_tokenize": False, "add_generation_prompt": True, "enable_thinking": False,
                           "tokenizer_add_special_tokens": "default True, same as DecisionModel", "truncation": False,
                           "padding": "Unpadded lengths; checked against actual padded encoding on two rows per source/split"},
              "existing_preflight_comparison": {"sampled_rows": sum(parity_counts.values()),
                                                "sampling": "first two rows per source/split", "mismatches": parity_mismatches},
              "required_max_length": args.max_length, "passes_required_limit": total.over_rows[args.max_length] == 0,
              "overall": total.report(), "by_split": {key: value.report() for key, value in split_stats.items()},
              "by_source": {key: value.report() for key, value in sorted(source_stats.items())},
              "row_lengths_file": detail_path.name, "row_lengths_sha256": digest_file(detail_path),
              "cpu_only": {"CUDA_VISIBLE_DEVICES": os.environ["CUDA_VISIBLE_DEVICES"], "offline": True,
                           "cuda_initialized": cuda_initialized(), "denied_weight_opens": denied_weight_opens},
              "observed_training_pids_before": before_pids, "observed_training_pids_after": process_identity(args.observe_pids),
              "elapsed_seconds": time.perf_counter() - started,
              "limits": "Token lengths only; no weights, forward/backward pass, GPU memory fit, throughput or task accuracy measured."}
    (args.output_dir / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"event": "complete", "model": args.model, "report": str(args.output_dir / 'report.json'),
                      "passes_required_limit": result["passes_required_limit"], "overall": result["overall"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--expected-encoder-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-length", type=int, default=4096)
    parser.add_argument("--limits", type=int, nargs="+", default=[1536, 4096, 8192, 16384])
    parser.add_argument("--batch-rows", type=int, default=64)
    parser.add_argument("--observe-pids", type=int, nargs="*", default=[])
    args = parser.parse_args()
    result = run(args)
    return 0 if result["passes_required_limit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
