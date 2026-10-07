"""Export compact public metrics from the committed full-data audits."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_INTERNAL_REPORT = "reports/new27b-internal-full-20260923/report.json"
NEW27B_CHECKPOINT = "c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71"
FULL_INTERNAL_PANELS = {
    "old_test": (10532, 10046),
    "old_ood": (15920, 15446),
    "expanded_test": (43301, 42789),
    "expanded_ood": (84486, 83924),
}


def metrics(row):
    measured = row["probability_metrics_all_rows"]
    keys = ("count", "hard_count", "accuracy", "expected_accuracy", "nll",
            "brier", "expected_brier", "multiclass_ece", "ece_bins")
    result = {key: measured[key] for key in keys}
    result["failed"] = row["failed"]
    result["hard_correct"] = round(measured["accuracy"] * measured["hard_count"])
    return result


def full_internal_models():
    """Only export the complete independent audit's sanitized four-panel report."""
    path = ROOT / FULL_INTERNAL_REPORT
    if not path.exists():
        return []
    raw = path.read_bytes()
    report = json.loads(raw)
    if (report.get("schema_version") != 1 or
            report.get("status") != "passed_complete_full24_audit" or
            report.get("publishable") is not True):
        raise ValueError("The full internal report has not passed the complete publication audit")
    checkpoint = report["checkpoint"]
    if (report["model"] != "Open-Jev-27B-v1.1" or
            checkpoint["model"] != "Qwen/Qwen3.8-27B" or
            checkpoint["checkpoint_sha256"] != NEW27B_CHECKPOINT or
            checkpoint["base_revision"] != "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0" or
            checkpoint["temperature"] != 2.5343690298472983):
        raise ValueError("The full internal report has an unexpected checkpoint identity")
    coverage = report["coverage"]
    if (coverage["total"] != 127787 or coverage["successful"] != 127787 or
            any(coverage[key] != 0 for key in ("failed", "missing", "duplicates"))):
        raise ValueError("The full internal report has incomplete coverage")
    panels = report["panels"]
    if set(panels) != set(FULL_INTERNAL_PANELS):
        raise ValueError("The full internal report must contain all four named panels")
    for name, (count, hard_count) in FULL_INTERNAL_PANELS.items():
        panel = panels[name]
        if (panel["count"] != count or panel["hard_count"] != hard_count or
                panel["soft_count"] != count - hard_count or
                type(panel["hard_correct"]) is not int or
                not 0 <= panel["hard_correct"] <= hard_count or
                panel["accuracy"] != panel["hard_correct"] / hard_count):
            raise ValueError(f"Invalid full internal denominator or accuracy: {name}")
        for metric in ("accuracy", "expected_accuracy", "nll", "brier",
                       "expected_brier", "multiclass_ece"):
            if not math.isfinite(panel[metric]):
                raise ValueError(f"Non-finite full internal metric: {name}.{metric}")
    return [{
        "model": report["model"],
        "checkpoint": checkpoint,
        "status": report["status"],
        "publishable": report["publishable"],
        "audit_path": FULL_INTERNAL_REPORT,
        "audit_sha256": hashlib.sha256(raw).hexdigest(),
        "coverage": coverage,
        "panels": panels,
    }]


def export_jevbench(full_model):
    """Append the separately audited 27B quality result without merging timings."""
    source_path = ROOT / "reports/new27b-jevbench-20260922/report.json"
    source_raw = source_path.read_bytes()
    source = json.loads(source_raw)
    audit_path = source_path.parent / source["audit"]["file"]
    audit_raw = audit_path.read_bytes()
    audit = json.loads(audit_raw)
    if (source["status"] != "complete_independently_audited" or audit["status"] != "passed" or
            hashlib.sha256(audit_raw).hexdigest() != source["audit"]["sha256"] or
            source["checkpoint"]["checkpoint_sha256"] != full_model["checkpoint"]["checkpoint_sha256"] or
            source["checkpoint"]["temperature"] != full_model["checkpoint"]["temperature"] or
            any(source[key] != 0 for key in ("failed_requests", "pending_requests", "in_flight_requests"))):
        raise ValueError("The 27B JevBench audit or checkpoint binding is incomplete")
    measured = source["metrics"]
    if (any(measured[key] != 231 for key in ("n_planned", "n_attempted", "n_scorable", "n_valid")) or
            measured["accuracy"] != measured["n_correct"] / 231 or
            measured["schema_validity_strict"] != 1 or measured["n_renormalized"] != 0):
        raise ValueError("The 27B JevBench request accounting is incomplete")
    report = json.loads((ROOT / "reports/jevbench-public-20260921/baseline-summary.json").read_bytes())
    if report["publication_ready"] is not True or report["required_streams"] != ["2b", "9b", "jev", "luna", "astra"]:
        raise ValueError("The original JevBench baselines are not publication ready")
    for key in ("upstream_commit", "input_sha256", "dataset_sha256"):
        if source["benchmark"][key] != report["benchmark"][key]:
            raise ValueError(f"The 27B JevBench benchmark differs: {key}")
    report["schema_version"] = 2
    report["baseline_generated_at"] = report.pop("generated_at")
    report["publication_date"] = "2026-09-23"
    report["title"] = "JevBench public subset: Open-Jev 27B v1.1 and released baselines"
    report["publication_gate"] = "Six complete streams passed their independent JevBench audits; the 27B checkpoint also passed the complete full24 internal publication audit."
    report["required_streams"].insert(2, "new27b")
    report["results"].insert(2, {
        "id": "new27b", "label": "Open-Jev 27B v1.1", "status": "complete", "audit_status": "passed",
        "probability_source": "native", "release_status": "v1.1",
        "metrics": {**measured, "n_strict_valid": 231, "latency": None},
        "per_public_tier": source["per_public_tier"], "per_family": source["per_family"],
        "checkpoint": source["checkpoint"], "execution": source["execution"],
        "timing_comparable": False, "timing_note": source["protocol"]["latency_note"],
        "source_report": str(source_path.relative_to(ROOT)),
        "source_report_sha256": hashlib.sha256(source_raw).hexdigest(),
        "model_url": "https://huggingface.co/ZefanCai/Open-Jev-27B-v1.1",
    })
    report["full_internal_audit"] = {
        "status": full_model["status"], "publishable": full_model["publishable"],
        "checkpoint_sha256": full_model["checkpoint"]["checkpoint_sha256"],
        "report_path": full_model["audit_path"], "report_sha256": full_model["audit_sha256"],
    }
    report["audit"]["new27b"] = {
        "status": "passed", "artifact": str(audit_path.relative_to(ROOT)),
        "sha256": hashlib.sha256(audit_raw).hexdigest(),
    }
    report["benchmark"]["baseline_execution_code_commit"] = report["benchmark"].pop("execution_code_commit")
    report["benchmark"]["new27b_execution_code_commit"] = source["checkpoint"]["code_commit"]
    report["protocol"]["new27b"] = source["protocol"]
    report["next_stage"] = {
        "status": "27b_v1.1_audited", "new_27b_training_completed": True,
        "new_2b_training": "stopped", "new_9b_training": "not_started",
        "note": "Released 2B/9B remain separate historical checkpoints; their expanded-set evaluations are pending.",
    }
    report["report_url"] = "https://github.com/Zefan-Cai/Open-Jev/blob/main/site/jevbench.json"
    report["notes"][0] = "The released 2B/9B adapters are preserved alongside the newly audited 27B v1.1 checkpoint."
    report["notes"].append("27B scored 197/231 and 80/111 Hard, three overall and one Hard behind Jev. Its four-rank direct-execution timings are not comparable to HTTP/HTTPS latency.")
    (ROOT / "site/jevbench.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    models = []
    for model in ("2b", "9b"):
        path = ROOT / f"reports/full-data-eval-n1-v1/{model}-audit.json"
        raw = path.read_bytes()
        audit = json.loads(raw)
        assert audit["status"] == "passed" and audit["model_evaluation_complete"]
        models.append({
            "model": audit["model"], "revision": audit["revision"],
            "evaluation_source_commit": audit["evaluation_source_commit"],
            "audit_path": str(path.relative_to(ROOT)),
            "audit_sha256": hashlib.sha256(raw).hexdigest(),
            "coverage": audit["coverage"],
            "splits": {split: {"overall": metrics(row),
                                "by_source": {key: metrics(value) for key, value in row["by_source"].items()}}
                       for split, row in audit["metrics"].items()},
        })
    corpora = []
    totals = {}
    sources = set()
    for name in ("browser-drone-expansion-v1", "citation-control-v1",
                 "entity-alignment-control-v1", "amount-extraction-control-v1",
                 "email-selection-control-v1", "phone-extraction-control-v1",
                 "context-retention-control-v1", "sponsor-segment-control-v1",
                 "silent-failure-control-v1", "ir-control-v1", "mailroom-control-v1"):
        path = ROOT / f"reports/data-manifests/{name}.json"
        if not path.exists():
            path = ROOT / f"reports/{name}/manifest.json"
        raw = path.read_bytes()
        data = json.loads(raw)
        splits = data["summary"]["splits"]
        sources.update(data["summary"]["sources"])
        for split, count in splits.items():
            totals[split] = totals.get(split, 0) + count
        corpora.append({"name": name, "splits": splits,
                        "manifest_path": str(path.relative_to(ROOT)),
                        "manifest_sha256": hashlib.sha256(raw).hexdigest()})
    full_models = full_internal_models()
    result = {
        "scope": ("Audited released 2B/9B release-v2 evaluation and 27B v1.1 full internal evaluation; "
                  "old and expanded panels overlap. Prepared inventory is separate." if full_models else
                  "Completed release-v2 checkpoint evaluation; broader prepared inventory is separate."),
        "evaluation_models": models,
        "full_internal_models": full_models,
        "prepared_inventory": {"corpora": corpora, "splits": totals,
                               "total_decision_rows": sum(totals.values()), "task_source_identifiers": len(sources)},
        "limitations": [
            "2B and 9B trained on 80,816 release-v2 training rows; broader inventory is not their evaluation set.",
            "Hard accuracy excludes 960 soft-target rows per model; expected accuracy includes all rows.",
            "Synthetic controlled decision accuracy is not an end-to-end task or gameplay success rate.",
            "No full-data base-model baseline was run; no full-data training gain is claimed.",
            ("The 27B v1.1 full internal audit covers 127,787 rows, including 1,074 soft-target rows; "
             "its old-release panels are unchanged-content subsets of the expanded panels." if full_models else
             "27B final evaluation and final-model JF100/service suites are pending."),
            ("Released 2B/9B expanded-set evaluations remain pending. New 2B training stopped; new 9B training did not start. "
             "Final-model JF100/service suites remain pending." if full_models else
             "The new corpora have not been used to retrain the released models; new-domain Open-Jev evaluation remains pending."),
            "JF100 is a separate holdout: 100 questions with three option rotations.",
            "Shared multi-GPU evaluation times are not single-GPU or HTTP/API latency measurements.",
        ],
    }
    output = ROOT / "site/results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    if full_models:
        export_jevbench(full_models[0])
    print(f"Exported {len(models)} release audits, {len(full_models)} full internal audits and {len(corpora)} corpus manifests.")


if __name__ == "__main__":
    main()
