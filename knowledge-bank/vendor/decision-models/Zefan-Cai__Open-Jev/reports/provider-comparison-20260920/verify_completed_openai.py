"""Recheck saved OpenAI quality evidence without making API requests."""
import hashlib
import json
from pathlib import Path

from scripts.summarize_provider_quality import summarize


REPORTS = Path("reports/provider-comparison-20260920")
RAW = Path("runs/provider-comparison-20260920")
SUITES = {
    "coverage": ("coverage-v1", "provider-comparison-v1", 189),
    "jf100": ("jf100-v1", "provider-comparison-jf100-v1", 300),
    "ir-pilot": ("ir-pilot-v1", "provider-ir-pilot-v1", 132),
    "fizzbuzz": ("fizzbuzz-control-v1", "provider-fizzbuzz-control-v1", 100),
    "mailroom": ("mailroom-probe-v1", "provider-mailroom-probe-v1", 87),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    checks = []
    for model in ("gpt-5.6-luna", "gpt-6-astra"):
        for suite, (tag, corpus, requests) in SUITES.items():
            prefix = f"openai-{model}-{suite}"
            audit_path = REPORTS / f"{prefix}-audit.json"
            quality_path = REPORTS / f"{prefix}-quality.json"
            audit = json.loads(audit_path.read_bytes())
            quality = json.loads(quality_path.read_bytes())
            raw = RAW / f"openai-{model}-{tag}"
            gold = Path("data") / corpus / "gold.json"
            assert audit["status"] == "passed" and audit["errors"] == 0
            assert sha(gold) == audit["gold_sha256"] == quality["gold_sha256"]
            for name, expected in audit["raw_file_sha256"].items():
                assert sha(raw / name) == expected, (prefix, name)
            samples = [json.loads(line) for line in (raw / "samples.jsonl").read_bytes().splitlines()]
            assert len(samples) == requests == len({s["request_id"] for s in samples})
            assert all(s["phase"] == "measured" and s["repetition"] == 0 and
                       s["success"] and s["http_status"] == 200 for s in samples)
            for sample in samples:
                response = json.loads(sample["raw_response"])
                assert response == sample["response"] and response["model"] == model
                assert response["tools"] == [] and response["status"] == "completed"
            rescored = summarize(json.loads(gold.read_bytes())["rows"], samples)
            assert rescored["rows"] == quality["rows"]
            assert rescored["overall"] == quality["overall"] == audit["quality_overall"]
            assert rescored["pending_count"] == 0
            checks.append({"model": model, "suite": suite, "requests": requests,
                           "hard_correct": quality["overall"]["hard_correct"],
                           "hard_targets": quality["overall"]["hard_targets"],
                           "soft_targets": quality["overall"]["soft_targets"],
                           "audit_sha256": sha(audit_path), "quality_sha256": sha(quality_path),
                           "samples_sha256": sha(raw / "samples.jsonl"),
                           "gold_sha256": sha(gold)})
    result = {"status": "passed", "stages": len(checks),
              "requests": sum(c["requests"] for c in checks), "request_errors": 0,
              "checks": checks,
              "verification_source_sha256": sha(Path(__file__)),
              "scope": "Local hash and response checks plus deterministic rescoring of all ten completed stages. No API calls or new model inference. Frozen labels and all masks are unchanged. Shared scoring logic is reused, so this is not an independent semantic label audit. Raw coverage bundles are excluded from public export."}
    (REPORTS / "completed-openai-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "stages", "requests", "request_errors")}))


if __name__ == "__main__":
    main()
