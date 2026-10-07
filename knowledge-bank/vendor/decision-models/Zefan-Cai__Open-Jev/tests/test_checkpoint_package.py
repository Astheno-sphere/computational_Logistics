"""Synthetic file fixtures exercise packaging; none contain real model weights."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.metrics import evaluate_probabilities, fit_temperature, softmax
from scripts import package_checkpoint as package


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def fixture(root, model="Qwen/Qwen3.5-2B", ddp=False):
    run_path, data_path = root / "run", root / "data"
    run_path.mkdir()
    data_path.mkdir()
    all_rows = {}
    counts = {"train": 8, "calibration": 3, "validation": 2, "test": 4, "ood": 5}
    for split, count in counts.items():
        rows = [{"id": f"{split}-{i}", "group_id": f"group-{split}-{i}", "split": split,
                 "kind": "choice", "source": "source-" + str(i % 2), "target": [float(i % 2 == 0), float(i % 2 != 0)], "metadata": {}}
                for i in range(count)]
        all_rows[split] = rows
        jsonl(data_path / (split + ".jsonl"), rows)
    hashes = {split: package.digest(data_path / (split + ".jsonl"))["sha256"] for split in package.SPLITS}
    dump(data_path / "manifest.json", {"counts": counts, "sha256": hashes})
    run = {"model": model, "revision": package.MODELS[model], "data": str(data_path), "output": str(run_path),
           "steps": 2, "accumulation": 4, "train_rows": 0, "calibration_rows": 2, "eval_rows": 2, "seed": 42,
           "max_length": 4096, "lora_rank": 8, "lr": 5e-5, "head_lr": 1e-4, "brier_weight": 0.1,
           "training_sampling": "shuffled", "commit": "c" * 40, "data_sha256": hashes,
           "pid": 999999, "environment": {"HF_TOKEN": "SENSITIVE_TEST_VALUE_DO_NOT_COPY"},
           "run_identity_sha256": "d" * 64}
    selected = {split: package.select(rows, 0 if split == "train" else 2, 42, split != "train")
                for split, rows in all_rows.items() if split != "validation"}
    for split, key in (("test", "evaluation_ids"), ("ood", "ood_ids"), ("calibration", "calibration_ids")):
        run[key] = [row["id"] for row in selected[split]]
    prediction = lambda row: {k: row[k] for k in ("id", "group_id", "source", "kind", "target")}
    outputs = {split: [{**prediction(row), "question_id": "choice", "target_basis": "hard_label", "logits": [0.2, 0.8],
                       "probabilities": softmax([0.2, 0.8]), "latency_seconds": 0.01} for row in rows]
               for split, rows in selected.items() if split != "train"}
    for split, name in (("test", "trained_test.jsonl"), ("ood", "trained_ood.jsonl"), ("calibration", "calibration.jsonl")):
        jsonl(run_path / name, outputs[split])
    for split in ("test", "ood", "calibration"):
        jsonl(run_path / ("baseline_" + split + ".jsonl"), outputs[split])
    jsonl(run_path / "reload_check.jsonl", outputs["test"][:1])
    log = [{"step": i, "loss": 0.5, "gradient_norm": 0.1, "elapsed_seconds": i} for i in (1, 2)]
    if ddp:
        run.pop("run_identity_sha256")
        run.update(identity_sha256="e" * 64, initialization="fresh_pinned_upstream", distribution={
            "world_size": 4, "local_rows_per_step": 1, "global_batch_size": 4, "backend": "nccl", "device_type": "cuda",
            "implementation_sha256": "f" * 64, "bitwise_single_process_equivalence": False},
            original_baseline_sha256={"baseline_" + s + ".jsonl": package.digest(run_path / ("baseline_" + s + ".jsonl"))["sha256"] for s in ("test", "ood", "calibration")})
        for row in log:
            row.update(world_size=4, global_batch_size=4)
    jsonl(run_path / "training.jsonl", log)
    temperature = fit_temperature([r["logits"] for r in outputs["calibration"]], [r["target"] for r in outputs["calibration"]])
    metrics = {}
    for prefix in ("baseline", "baseline_calibrated", "trained", "calibrated"):
        for split in ("test", "ood"):
            values = outputs[split]
            probabilities = [softmax([x / (temperature if "calibrated" in prefix else 1) for x in r["logits"]]) for r in values]
            metric = evaluate_probabilities([r["target"] for r in values], probabilities)
            metric.update(mean_latency_seconds=0.01,
                          by_kind={"choice": evaluate_probabilities([r["target"] for r in values], probabilities)})
            metric["by_source"] = {source: evaluate_probabilities([r["target"] for r in values if r["source"] == source],
                                      [p for r, p in zip(values, probabilities) if r["source"] == source]) for source in {r["source"] for r in values}}
            metric["by_question"] = {source + "/choice": copy.deepcopy(m) for source, m in metric["by_source"].items()}
            metrics[prefix + "_" + split] = metric
    summary = {"status": "complete", "model": model, "steps": 2, "trained_rows_consumed": 8,
               "temperature": temperature, "baseline_temperature": temperature, "checkpoint_reload_max_error": 0.0, "metrics": metrics}
    if ddp:
        summary["distribution"] = copy.deepcopy(run["distribution"])
    dump(run_path / "run.json", run)
    dump(run_path / "summary.json", summary)
    checkpoint = run_path / "checkpoint"
    dump(checkpoint / "model.json", {"model_id": model, "revision": run["revision"], "max_length": 4096,
                                      "lora_rank": 8, "method": "independent_candidate_lora_nll_brier"})
    dump(checkpoint / "temperature.json", {"temperature": temperature, "split": "calibration", "n": 2,
                                           "ids_sha256": hashlib.sha256(json.dumps(run["calibration_ids"]).encode()).hexdigest()})
    dump(checkpoint / "adapter/adapter_config.json", {"peft_type": "LORA", "r": 8, "lora_alpha": 16,
                                                      "base_model_name_or_path": "", "revision": None, "inference_mode": True})
    (checkpoint / "head.pt").write_bytes(b"OPAQUE SYNTHETIC TEST FIXTURE, NOT MODEL WEIGHTS")
    (checkpoint / "adapter/adapter_model.safetensors").write_bytes(b"OPAQUE SYNTHETIC ADAPTER FIXTURE")
    (checkpoint / "adapter/README.md").write_text("Old automatically generated adapter card, ignored.")
    # Training artifacts remain in the source run and must not enter a bundle.
    (run_path / "optimizer.pt").write_bytes(b"not for release")
    return run_path, data_path


class CheckpointPackageTests(unittest.TestCase):
    def test_completed_single_2b_9b_and_ddp_27b_package_without_source_data(self):
        for model, ddp in (("Qwen/Qwen3.5-2B", False), ("Qwen/Qwen3.5-9B", False), ("Qwen/Qwen3.8-27B", True)):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run, data = fixture(root, model, ddp)
                before = {str(p.relative_to(run)): package.digest(p) for p in run.rglob("*") if p.is_file()}
                result = package.package(run, root / "bundle")
                self.assertFalse(result["uploaded"])
                bundle = root / "bundle"
                manifest = json.loads((bundle / "manifest.json").read_text())
                self.assertEqual(result["manifest_sha256"], package.digest(bundle / "manifest.json")["sha256"])
                self.assertEqual(set(manifest["files"]), {p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()} - {"manifest.json"})
                for name, expected in manifest["files"].items():
                    self.assertEqual(package.digest(bundle / name), expected)
                self.assertEqual(package.digest(bundle / "LICENSE")["sha256"], package.QWEN_LICENSE_SHA256)
                self.assertEqual((bundle / "LICENSE-CODE").read_bytes(), (package.ROOT / "LICENSE").read_bytes())
                self.assertEqual((bundle / "checkpoint/head.pt").read_bytes(), (run / "checkpoint/head.pt").read_bytes())
                for excluded in ("optimizer.pt", "run.json", "baseline_test.jsonl", "checkpoint/adapter/README.md"):
                    self.assertFalse((bundle / excluded).exists())
                text = "\n".join(p.read_text() for p in bundle.rglob("*") if p.is_file() and p.suffix in (".json", ".md"))
                self.assertNotIn("SENSITIVE_TEST_VALUE_DO_NOT_COPY", text)
                self.assertNotIn(str(run), text)
                self.assertNotIn('"pid"', text)
                self.assertIn("2/4 test rows and 2/5 OOD rows", (bundle / "README.md").read_text())
                self.assertIn("does not load tensors or repeat model inference", text)
                provenance = json.loads((bundle / "provenance.json").read_text())
                self.assertTrue(provenance["training"]["one_full_pass"])
                self.assertEqual(provenance["data"]["name"], "custom frozen dataset")
                self.assertEqual(provenance["source_evidence"]["run.json"], package.digest(run / "run.json"))
                self.assertEqual(before, {str(p.relative_to(run)): package.digest(p) for p in run.rglob("*") if p.is_file()})
                self.assertFalse(list(root.glob(".bundle.incomplete-*")))

    def mutate_rejected(self, filename, update, pattern, ddp=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root, "Qwen/Qwen3.8-27B" if ddp else "Qwen/Qwen3.5-2B", ddp)
            path = run / filename
            value = json.loads(path.read_text())
            update(value)
            dump(path, value)
            with self.assertRaisesRegex(ValueError, pattern):
                package.package(run, root / "bundle")
            self.assertFalse((root / "bundle").exists())

    def test_incomplete_resume_only_and_noncontiguous_training_are_rejected(self):
        self.mutate_rejected("summary.json", lambda s: s.update(status="running"), "not complete")
        self.mutate_rejected("summary.json", lambda s: s.update(inference_ready=False), "not complete")
        self.mutate_rejected("summary.json", lambda s: s.update(trained_rows_consumed=400), "record count")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root)
            dump(run / "resume.json", {"kind": "training_resume_only", "complete": True})
            with self.assertRaisesRegex(ValueError, "resume-only"):
                package.package(run, root / "bundle")
            (run / "resume.json").unlink()
            jsonl(run / "training.jsonl", [{"step": 2, "loss": 1, "gradient_norm": 1, "elapsed_seconds": 1}])
            with self.assertRaisesRegex(ValueError, "optimizer cursor"):
                package.package(run, root / "bundle")

    def test_model_revision_adapter_and_ddp_identity_are_bound(self):
        self.mutate_rejected("checkpoint/model.json", lambda s: s.update(revision="0" * 40), "Model/revision mismatch")
        self.mutate_rejected("run.json", lambda s: s.update(revision="0" * 40), "upstream model/revision")
        self.mutate_rejected("checkpoint/adapter/adapter_config.json", lambda s: s.update(revision="0" * 40), "Adapter upstream")
        self.mutate_rejected("checkpoint/adapter/adapter_config.json", lambda s: s.update(base_model_name_or_path="/private/cache/model"), "local path")
        self.mutate_rejected("checkpoint/adapter/adapter_config.json", lambda s: s.update(api_key="hidden"), "Sensitive adapter")
        self.mutate_rejected("summary.json", lambda s: s["distribution"].update(world_size=2), "DDP topology", ddp=True)
        self.mutate_rejected("run.json", lambda s: s["original_baseline_sha256"].update({"baseline_test.jsonl": "0" * 64}), "baseline checksum", ddp=True)

    def test_calibration_split_count_ids_temperature_and_targets_are_bound(self):
        for changes, pattern in (({"split": "test"}, "split/count"), ({"n": 1}, "split/count"),
                                 ({"ids_sha256": "0" * 64}, "ID hash"), ({"temperature": 0}, "Temperature"),
                                 ({"temperature": 1.3}, "Temperature")):
            self.mutate_rejected("checkpoint/temperature.json", lambda s, c=changes: s.update(c), pattern)
        self.mutate_rejected("run.json", lambda s: s["calibration_ids"].reverse(), "selected IDs")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root)
            rows = [json.loads(line) for line in (run / "calibration.jsonl").read_text().splitlines()]
            rows[0]["target"].reverse()
            jsonl(run / "calibration.jsonl", rows)
            with self.assertRaisesRegex(ValueError, "identity/target"):
                package.package(run, root / "bundle")

    def test_reload_requires_finite_equal_shape_real_saved_evidence(self):
        self.mutate_rejected("summary.json", lambda s: s.update(checkpoint_reload_max_error=float("nan")), "nonfinite")
        self.mutate_rejected("summary.json", lambda s: s.update(checkpoint_reload_max_error=0.01), "Reload evidence")
        for logits, pattern in (([float("nan"), 0.8], "nonfinite"), ([0.2], "Invalid prediction logits"), ([0.3, 0.8], "Reload evidence")):
            with self.subTest(logits=logits), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run, _ = fixture(root)
                row = json.loads((run / "reload_check.jsonl").read_text())
                row["logits"] = logits
                if all(package.finite(x) for x in logits):
                    row["probabilities"] = softmax(logits)
                jsonl(run / "reload_check.jsonl", [row])
                with self.assertRaisesRegex(ValueError, pattern):
                    package.package(run, root / "bundle")

    def test_data_relocation_keeps_hashes_and_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, data = fixture(root)
            relocated = root / "relocated"
            data.rename(relocated)
            package.package(run, root / "bundle", relocated)
            with (relocated / "train.jsonl").open("a") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                package.package(run, root / "second-bundle", relocated)

    def test_missing_extra_symlinked_and_ambiguous_checkpoint_files_are_rejected(self):
        for mode in ("missing", "secret", "symlink", "two_weights"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run, data = fixture(root)
                checkpoint = run / "checkpoint"
                if mode == "missing":
                    (checkpoint / "head.pt").unlink()
                elif mode == "secret":
                    (checkpoint / ".env").write_text("TOKEN=secret")
                elif mode == "symlink":
                    (checkpoint / "head.pt").unlink()
                    (checkpoint / "head.pt").symlink_to(data / "train.jsonl")
                else:
                    (checkpoint / "adapter/adapter_model.bin").write_bytes(b"another weight file")
                with self.assertRaises(ValueError):
                    package.package(run, root / "bundle")

    def test_output_no_overwrite_and_source_race_leaves_no_published_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root)
            output = root / "existing"
            output.mkdir()
            (output / "keep").write_text("untouched")
            with self.assertRaisesRegex(ValueError, "new directory"):
                package.package(run, output)
            self.assertEqual((output / "keep").read_text(), "untouched")
            with self.assertRaisesRegex(ValueError, "outside the source run"):
                package.package(run, run / "bundle")
            original_copy = package.shutil.copyfile
            def changed_after_copy(source, destination):
                result = original_copy(source, destination)
                if Path(source).name == "head.pt":
                    Path(source).write_bytes(b"changed after copy")
                return result
            with patch.object(package.shutil, "copyfile", side_effect=changed_after_copy):
                with self.assertRaisesRegex(ValueError, "Source changed"):
                    package.package(run, root / "bundle")
            self.assertFalse((root / "bundle").exists())
            self.assertFalse(list(root.glob(".bundle.incomplete-*")))

    def test_pinned_upstream_license_and_metric_scope_are_required(self):
        self.mutate_rejected("summary.json", lambda s: s["metrics"].update({"JF100": {"count": 100}}), "metric sections")
        self.mutate_rejected("summary.json", lambda s: s["metrics"]["trained_test"].update(count=3), "Coverage denominator|metrics count")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root)
            license_root = root / "license-root"
            (license_root / "third_party/qwen").mkdir(parents=True)
            (license_root / "third_party/qwen/LICENSE").write_text("Apache-2.0 identifier without full license")
            with patch.object(package, "ROOT", license_root):
                with self.assertRaisesRegex(ValueError, "license bytes differ"):
                    package.package(run, root / "bundle")

    def test_stale_metrics_calibration_and_prediction_grouping_are_rejected(self):
        self.mutate_rejected("summary.json", lambda s: s["metrics"]["trained_test"].update(nll=0.7), "metrics disagree")
        self.mutate_rejected("summary.json", lambda s: s.update(baseline_temperature=0.8), "calibration-only refit")
        for key, value in (("question_id", "another-question"), ("target_basis", "another-basis"), ("probabilities", [0.9, 0.1])):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                run, _ = fixture(root)
                rows = [json.loads(line) for line in (run / "trained_test.jsonl").read_text().splitlines()]
                rows[0][key] = value
                jsonl(run / "trained_test.jsonl", rows)
                with self.assertRaisesRegex(ValueError, "identity/target|probabilities disagree"):
                    package.package(run, root / "bundle")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, _ = fixture(root)
            for path in (run / "summary.json", run / "checkpoint/temperature.json"):
                value = json.loads(path.read_text())
                value["temperature"] = 0.8
                dump(path, value)
            with self.assertRaisesRegex(ValueError, "calibration-only refit"):
                package.package(run, root / "bundle")

    def test_duplicate_json_keys_are_rejected(self):
        for text in ('{"status":"running","status":"complete"}', '{"nested":{"revision":"a","revision":"b"}}'):
            with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                package.decode(text)


if __name__ == "__main__":
    unittest.main()
