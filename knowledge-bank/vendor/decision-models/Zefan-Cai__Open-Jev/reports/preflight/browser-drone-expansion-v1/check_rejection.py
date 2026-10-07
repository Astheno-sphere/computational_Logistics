"""CPU-only check of the real forward length guard, without constructing weights."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    denied = []

    def prohibit_weights(event, values):
        if event == "open" and isinstance(values[0], (str, bytes)):
            if Path(os.fsdecode(values[0])).suffix in {".safetensors", ".bin", ".pt", ".pth"}:
                denied.append(os.fsdecode(values[0]))
                raise RuntimeError("Model weight/binary data reads are forbidden")

    sys.addaudithook(prohibit_weights)
    sys.path.insert(0, str(args.repo))
    import torch
    from transformers import AutoTokenizer
    from jev.model import DecisionModel

    assert not torch.cuda.is_initialized()

    class ReachedBackbone(Exception):
        pass

    class Sentinel(torch.nn.Module):
        def forward(self, **inputs):
            assert all(not value.is_cuda for value in inputs.values() if isinstance(value, torch.Tensor))
            self.lengths = inputs["attention_mask"].sum(-1).tolist()
            raise ReachedBackbone("Guard passed; no real backbone was constructed or executed")

    results = {}
    for tag in ("2b", "9b", "27b"):
        evidence = json.loads((args.evidence_root / tag / "report.json").read_text())
        assert sha256(args.repo / "jev/model.py") == evidence["implementation_sha256"]["jev/model.py"]
        assert sha256(args.data / "manifest.json") == evidence["dataset_manifest_sha256"]
        longest = evidence["overall"]["longest_candidate"]
        with (args.data / (longest["split"] + ".jsonl")).open() as stream:
            row = next(row for line in stream if line.strip()
                       if (row := json.loads(line))["id"] == longest["id"])
        tokenizer = AutoTokenizer.from_pretrained(evidence["model"], revision=evidence["revision"],
                                                 cache_dir=str(args.cache_dir), local_files_only=True)
        tokenizer.padding_side = "right"
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        # Bypass DecisionModel.__init__: it is the only path that loads weights.
        model = DecisionModel.__new__(DecisionModel)
        torch.nn.Module.__init__(model)
        model.tokenizer = tokenizer
        model.device_name = "cpu"
        model.backbone = Sentinel()
        checks = []
        maximum = longest["tokens"]
        for cap in (512, 1536, maximum - 1, maximum, 2048, 4096):
            model.max_length = cap
            if cap < maximum:
                try:
                    model([row])
                except ValueError as error:
                    expected = f"Input length {maximum} exceeds max_length={cap}; no silent truncation"
                    assert str(error) == expected
                    checks.append({"max_length": cap, "result": "rejected", "error": str(error)})
                else:
                    raise AssertionError("Expected explicit overlength rejection")
            else:
                try:
                    model([row])
                except ReachedBackbone:
                    lengths = model.backbone.lengths
                    assert max(lengths) == maximum
                    checks.append({"max_length": cap, "result": "guard_passed_to_cpu_sentinel",
                                   "candidate_tokens": lengths})
                else:
                    raise AssertionError("Expected the CPU sentinel after the length guard")
        results[tag] = {"model": evidence["model"], "revision": evidence["revision"],
                        "row_id": row["id"], "checks": checks}
    assert not torch.cuda.is_initialized() and not denied
    print(json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                      "script_sha256": sha256(Path(__file__)), "verified": True,
                      "CUDA_VISIBLE_DEVICES": os.environ["CUDA_VISIBLE_DEVICES"],
                      "cuda_initialized": False, "denied_weight_opens": denied,
                      "scope": "Real DecisionModel.forward tokenizer and length guard; CPU sentinel replaces all neural computation.",
                      "models": results}, indent=2))


if __name__ == "__main__":
    main()
