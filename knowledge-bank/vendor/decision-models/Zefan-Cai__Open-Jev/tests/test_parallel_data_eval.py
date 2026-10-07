"""CPU-only data/identity/failure/ownership checks for four-GPU held-out evaluation."""

import argparse
from contextlib import nullcontext
import copy
import hashlib
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from scripts import evaluate_checkpoints_parallel as evaluation


def record(split, index):
    identity = f"{split}-{index}"
    return {"id": identity, "split": split, "group_id": f"{split}-group-{index // 2}",
            "source": f"source-{index % 2}", "state": {"case": identity},
            "question": "Select the correct option", "kind": "choice", "options": ["yes", "no"],
            "target": [1.0, 0.0], "metadata": {"provenance": {"type": "import", "license": "CC0",
                "split_policy": "fixture", "input_sha256": "a" * 64,
                "source_url": "https://example.com/fixture", "original_id": identity}}}


class Scorer:
    def __init__(self, fail=()):
        self.fail = set(fail)

    def score(self, rows):
        if rows[0]["id"] in self.fail:
            raise ValueError("Input length exceeds max_length; no silent truncation")
        return [[4.0, 0.0]], 20


class ParallelDataEvalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = self.root / "release-v2"
        self.data.mkdir()
        counts = {"train": 1, "calibration": 2, "validation": 1, "test": 7, "ood": 5}
        self.hashes = {}
        for split, count in counts.items():
            path = self.data / f"{split}.jsonl"
            path.write_text("".join(json.dumps(record(split, i)) + "\n" for i in range(count)))
            self.hashes[split] = evaluation.file_hash(path)
        evaluation.write_json(self.data / "manifest.json", {"counts": counts, "sha256": self.hashes})
        self.rows, self.data_identity, self.calibration_ids = evaluation.load_data(self.data, self.hashes)
        self.checkpoints = {tag: self.checkpoint(tag) for tag in evaluation.MODELS}
        self.identity = evaluation.checkpoint_identity(self.checkpoints["2b"], "2b", self.data_identity, self.calibration_ids)
        self.gpus = [f"GPU-{i}" for i in range(4)]
        self.plan_sha = "a" * 64

    def checkpoint(self, tag):
        path = self.root / "runs" / tag / "checkpoint"
        (path / "adapter").mkdir(parents=True)
        model, revision = evaluation.MODELS[tag]
        evaluation.write_json(path / "model.json", {"model_id": model, "revision": revision, "max_length": 4096, "lora_rank": 8})
        ids = ["calibration-0", "calibration-1"]
        evaluation.write_json(path / "temperature.json", {"temperature": 2.0, "split": "calibration", "n": 2,
            "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        evaluation.write_json(path.parent / "run.json", {"data_sha256": self.hashes, "calibration_ids": ids,
            "model": model, "revision": revision, "steps": 20204, "accumulation": 4,
            "train_rows": 0, "training_sampling": "shuffled", "max_length": 4096, "lora_rank": 8})
        evaluation.write_json(path.parent / "summary.json", {"status": "complete", "model": model, "temperature": 2.0,
            "steps": 20204, "trained_rows_consumed": 80816, "checkpoint_reload_max_error": 0.001})
        (path / "head.pt").write_bytes(b"fixture, not model weights")
        (path / "adapter/adapter_config.json").write_text("{}")
        (path / "adapter/adapter_model.safetensors").write_bytes(b"fixture, not model weights")
        return path

    def make_shards(self, *, fail=(), directory=None, identity=None, plan_sha=None):
        directory = directory or self.root / "shards"
        directory.mkdir(exist_ok=True)
        identity = identity or self.identity
        for rank in range(4):
            self.make_shard(directory, rank, identity, plan_sha or self.plan_sha, fail)
        return directory

    def make_shard(self, directory, rank, identity, plan_sha, fail=(), data_identity=None):
        path = directory / f"shard-{rank}.jsonl"
        profile_name = identity.get("dataset_profile", "release-v2")
        partition = evaluation.dataset_profile(profile_name)["partition"]
        counts = evaluation.evaluate_shard(self.rows, rank, identity, Scorer(fail), path, partition=partition)
        evaluation.write_json(path.with_suffix(".json"), {"status": "complete", "rank": rank,
            "checkpoint": identity, "plan_sha256": plan_sha, "gpu_uuid": self.gpus[rank],
            "dataset_profile": profile_name, "data_identity": data_identity or self.data_identity,
            "assignment": evaluation.shard_identity(self.rows, rank, partition=partition),
            "output_sha256": evaluation.file_hash(path), "counts": counts})

    def merge(self, directory):
        return evaluation.merge_shards(self.rows, self.identity, directory, self.plan_sha, self.gpus)

    def mutate_rows(self, directory, rank, mutation):
        path = directory / f"shard-{rank}.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        mutation(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        report = evaluation.read_json(path.with_suffix(".json"))
        report["output_sha256"] = evaluation.file_hash(path)
        evaluation.write_json(path.with_suffix(".json"), report)

    def test_shards_cover_every_id_once_in_stable_order(self):
        shards = [evaluation.shard_rows(self.rows, rank) for rank in range(4)]
        self.assertEqual([len(shard) for shard in shards], [4, 3, 3, 2])
        ids = [row["id"] for shard in shards for _, _, row in shard]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(set(ids)), 12)
        self.assertEqual(shards, [evaluation.shard_rows(self.rows, rank) for rank in range(4)])
        for rank, shard in enumerate(shards):
            self.assertTrue(all(index % 4 == rank for _, index, _ in shard))

    def test_dataset_pin_catches_wrong_manifest_and_changed_bytes(self):
        with self.assertRaisesRegex(ValueError, "frozen release-v2"):
            evaluation.load_data(self.data)
        with (self.data / "test.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            evaluation.load_data(self.data, self.hashes)

    def test_checkpoint_requires_final_completion_and_correct_model(self):
        with self.assertRaisesRegex(ValueError, "Wrong checkpoint"):
            evaluation.checkpoint_identity(self.checkpoints["2b"], "9b", self.data_identity, self.calibration_ids)
        summary = self.checkpoints["2b"].parent / "summary.json"
        values = evaluation.read_json(summary)
        values["status"] = "running"
        evaluation.write_json(summary, values)
        with self.assertRaisesRegex(ValueError, "not complete"):
            evaluation.checkpoint_identity(self.checkpoints["2b"], "2b", self.data_identity, self.calibration_ids)

    def test_temperature_must_be_saved_calibration_not_test_or_bad_value(self):
        path = self.checkpoints["2b"] / "temperature.json"
        original = evaluation.read_json(path)
        for change in ({"split": "test"}, {"temperature": True}, {"temperature": 0},
                       {"ids_sha256": "b" * 64}, {"n": 1}):
            with self.subTest(change=change):
                evaluation.write_json(path, {**original, **change})
                with self.assertRaisesRegex(ValueError, "calibration"):
                    evaluation.checkpoint_identity(self.checkpoints["2b"], "2b", self.data_identity, self.calibration_ids)

    def test_short_run_or_failed_reload_cannot_masquerade_as_fullpass(self):
        path = self.checkpoints["2b"].parent / "summary.json"
        original = evaluation.read_json(path)
        for change in ({"steps": 400}, {"trained_rows_consumed": 1600},
                       {"checkpoint_reload_max_error": 0.1}, {"checkpoint_reload_max_error": None}):
            with self.subTest(change=change):
                evaluation.write_json(path, {**original, **change})
                with self.assertRaisesRegex(ValueError, "full pass"):
                    evaluation.checkpoint_identity(self.checkpoints["2b"], "2b", self.data_identity, self.calibration_ids)

    def test_calibration_id_membership_and_checkpoint_content_are_bound(self):
        path = self.checkpoints["2b"]
        (path / "head.pt").write_bytes(b"different fixture")
        current = evaluation.checkpoint_identity(path, "2b", self.data_identity, self.calibration_ids)
        self.assertNotEqual(current["checkpoint_sha256"], self.identity["checkpoint_sha256"])
        with self.assertRaisesRegex(ValueError, "calibration"):
            evaluation.checkpoint_identity(path, "2b", self.data_identity, {"test-0", "test-1"})

    def test_saved_temperature_and_source_group_summaries(self):
        directory = self.make_shards()
        summary = self.merge(directory)
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["splits"]["test"]["count"], 7)
        self.assertEqual(sum(v["count"] for v in summary["splits"]["test"]["by_source"].values()), 7)
        self.assertEqual(sum(v["count"] for v in summary["splits"]["test"]["by_group_id"].values()), 7)
        merged = [json.loads(line) for line in (directory / "merged-test.jsonl").read_text().splitlines()]
        self.assertEqual([row["id"] for row in merged], [row["id"] for row in self.rows["test"]])
        self.assertEqual(merged[0]["probabilities"], evaluation.softmax([4.0, 0.0], 2.0))

    def test_error_rows_remain_in_total_and_confidence_coverage(self):
        directory = self.make_shards(fail=("test-0", "ood-1"))
        summary = self.merge(directory)
        self.assertEqual(summary["status"], "completed_with_errors")
        test = summary["splits"]["test"]
        self.assertEqual((test["count"], test["successful"], test["failed"]), (7, 6, 1))
        self.assertEqual(test["inference_coverage"], 6 / 7)
        self.assertEqual(test["accuracy_all_rows_failures_incorrect"], 6 / 7)
        self.assertEqual(test["coverage"][0]["coverage"], 6 / 7)
        self.assertIsNone(test["probability_metrics_all_rows"])
        self.assertEqual(test["probability_metrics_successful_rows_only"]["count"], 6)
        failed = json.loads((directory / "merged-test.jsonl").read_text().splitlines()[0])
        self.assertEqual(failed["status"], "error")
        self.assertNotIn("probabilities", failed)

    def test_all_failures_and_soft_targets_have_defined_full_denominators(self):
        rows = [{"status": "error", "target": [1.0, 0.0]}, {"status": "error", "target": [0.5, 0.5]}]
        result = evaluation.summarize(rows)
        self.assertEqual((result["count"], result["failed"], result["hard_count"]), (2, 2, 1))
        self.assertEqual(result["expected_accuracy_all_rows_failures_zero"], 0)
        self.assertIsNone(result["probability_metrics_successful_rows_only"])

    def test_missing_duplicate_wrong_split_checkpoint_and_temperature_fail(self):
        mutations = {
            "missing": lambda rows: rows.pop(),
            "duplicate": lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])),
            "split": lambda rows: rows[0].update(split="train"),
            "id": lambda rows: rows[0].update(id="other"),
            "rank": lambda rows: rows[0].update(shard_rank=1),
            "checkpoint": lambda rows: rows[0]["checkpoint"].update(checkpoint_sha256="c" * 64),
            "temperature": lambda rows: rows[0]["checkpoint"].update(temperature=1.0),
            "unscaled_probabilities": lambda rows: rows[0].update(probabilities=evaluation.softmax([4.0, 0.0])),
            "nonfinite": lambda rows: rows[0].update(logits=[float("nan"), 0]),
            "bool_probability": lambda rows: rows[0].update(probabilities=[True, False]),
            "target": lambda rows: rows[0].update(target=[0, 1]),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                directory = self.make_shards(directory=self.root / name)
                self.mutate_rows(directory, 0, mutation)
                with self.assertRaises(ValueError):
                    self.merge(directory)
                self.assertFalse((directory / "merged-test.jsonl").exists())

    def test_missing_worker_report_or_wrong_plan_and_counts_fail(self):
        for field, value in (("status", "failed"), ("plan_sha256", "bad"),
                             ("gpu_uuid", "other"), ("counts", {"rows": 0, "ok": 0, "error": 0})):
            with self.subTest(field=field):
                directory = self.make_shards(directory=self.root / field)
                path = directory / "shard-0.json"
                report = evaluation.read_json(path)
                report[field] = value
                evaluation.write_json(path, report)
                with self.assertRaises(ValueError):
                    self.merge(directory)
        directory = self.make_shards(directory=self.root / "missing-report")
        (directory / "shard-2.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.merge(directory)

    def test_invalid_scorer_output_is_an_explicit_failure(self):
        class InvalidScorer:
            def score(self, rows):
                return [[float("nan"), 0.0]], 20
        path = self.root / "invalid.jsonl"
        counts = evaluation.evaluate_shard(self.rows, 0, self.identity, InvalidScorer(), path)
        self.assertEqual(counts, {"rows": 4, "ok": 0, "error": 4})

    def test_phase_policy_and_fixed_host_required_before_launch(self):
        path = self.root / "policy.json"
        policy = {"expected_hostname": evaluation.HOSTNAME, "allowed_gpu_indices": [0, 1, 2, 3],
                  "parallel_data_evaluation_gpu_indices": [0, 1, 2, 3]}
        evaluation.write_json(path, policy)
        self.assertEqual(evaluation.enforce_host_policy(path, evaluation.HOSTNAME)["gpu_indices"], [0, 1, 2, 3])
        with self.assertRaises(RuntimeError):
            evaluation.enforce_host_policy(path, "datava-004")
        policy.pop("parallel_data_evaluation_gpu_indices")
        evaluation.write_json(path, policy)
        with self.assertRaises(RuntimeError):
            evaluation.enforce_host_policy(path, evaluation.HOSTNAME)

    def test_only_target_four_gpus_must_be_idle_and_complete(self):
        inventory = "".join(f"{i}, GPU-{i}, 0, 0\n" for i in range(4)) + "4, GPU-other, 50000, 100\n"
        with patch.object(evaluation.subprocess, "check_output", side_effect=["GPU-other\n", inventory]):
            self.assertEqual(evaluation.require_free_gpus(), self.gpus)
        for processes, value in (("GPU-3\n", inventory), ("", inventory.replace("3, GPU-3, 0, 0", "3, GPU-3, 512, 0")),
                                 ("", "\n".join(inventory.splitlines()[:3]))):
            with self.subTest(processes=processes, value=value):
                with patch.object(evaluation.subprocess, "check_output", side_effect=[processes, value]), self.assertRaises(RuntimeError):
                    evaluation.require_free_gpus()

    def test_shared_lease_prevents_concurrent_eval_or_training(self):
        with evaluation.gpu_lease(self.root):
            with self.assertRaisesRegex(RuntimeError, "lease already held"):
                with evaluation.gpu_lease(self.root):
                    self.fail("Second scheduler acquired held GPUs")
        with evaluation.gpu_lease(self.root):
            pass

    def controller(self, popen, output_name="controller-output", *, profile_name="release-v2", data_identity=None, calibration_ids=None):
        args = argparse.Namespace(data=self.data, checkpoint_root=self.root / "runs", checkpoint_2b=None,
                                  checkpoint_9b=None, output_root=self.root / output_name, dataset_profile=profile_name)
        with patch.object(evaluation, "load_data", return_value=(self.rows, data_identity or self.data_identity, calibration_ids or self.calibration_ids)), \
             patch.object(evaluation, "enforce_host_policy", return_value={"hostname": evaluation.HOSTNAME}), \
             patch.object(evaluation, "gpu_lease", return_value=nullcontext()), \
             patch.object(evaluation, "require_free_gpus", return_value=self.gpus), \
             patch.object(evaluation.subprocess, "Popen", side_effect=popen):
            return evaluation.run(args)

    def test_controller_runs_four_shards_then_next_model(self):
        events = []
        owner = self

        class Process:
            returncode = 0
            pid = 1234
            def poll(self):
                return 0
            def wait(self, timeout=None):
                events.append("wait")
                return 0

        def popen(command, **kwargs):
            plan_path = Path(command[command.index("--worker-plan") + 1])
            rank = int(command[-1])
            plan = evaluation.read_json(plan_path)
            events.append((plan["tag"], rank))
            self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], self.gpus[rank])
            owner.make_shard(plan_path.parent, rank, plan["checkpoint"], evaluation.file_hash(plan_path))
            return Process()
        result = self.controller(popen)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(events[:4], [("2b", i) for i in range(4)])
        self.assertEqual([event for event in events if isinstance(event, tuple)],
                         [(tag, i) for tag in ("2b", "9b") for i in range(4)])

    def test_controller_worker_crash_stops_only_owned_children_and_fails(self):
        children = []

        class Process:
            def __init__(self, code):
                self.returncode, self.pid, self.terminated = code, 1200 + len(children), False
            def poll(self):
                return self.returncode
            def terminate(self):
                self.terminated, self.returncode = True, -15
            def wait(self, timeout=None):
                return self.returncode

        def popen(command, **kwargs):
            process = Process(1 if not children else None)
            children.append(process)
            return process
        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            self.controller(popen)
        self.assertEqual(len(children), 4)
        self.assertFalse(children[0].terminated)
        self.assertTrue(all(process.terminated for process in children[1:]))
        manifest = evaluation.read_json(self.root / "controller-output/manifest.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["models"]["2b"]["status"], "failed")
        self.assertNotIn("9b", manifest["models"])
        self.assertFalse((self.root / "controller-output/2b/summary.json").exists())

    def test_sigterm_and_sigint_interruptions_reap_all_owned_workers(self):
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signum=signum):
                children, interrupted = [], []

                class Process:
                    returncode = None
                    pid = 1200
                    terminated = False
                    def poll(self):
                        if not interrupted:
                            interrupted.append(True)
                            evaluation.handle_signal(signum, None)
                        return self.returncode
                    def terminate(self):
                        self.terminated, self.returncode = True, -15
                    def wait(self, timeout=None):
                        return self.returncode

                def popen(command, **kwargs):
                    child = Process()
                    children.append(child)
                    return child
                with self.assertRaises(InterruptedError):
                    self.controller(popen, f"signal-{signum}")
                self.assertEqual(len(children), 4)
                self.assertTrue(all(child.terminated for child in children))
                manifest = evaluation.read_json(self.root / f"signal-{signum}/manifest.json")
                self.assertEqual(manifest["status"], "failed")
                self.assertNotIn("9b", manifest["models"])

    def expansion_checkpoint(self):
        """Small CPU checkpoint fixture with the real planned DDP step cursor."""
        profile = evaluation.DATASET_PROFILES["browser-drone-expansion-v1"]
        path = self.checkpoints["27b"]
        ids = [f"calibration-{i}" for i in range(512)]
        # Fixture-only calibration IDs; production pins the independently audited real selection.
        calibration_patch = patch.dict(profile, {"calibration_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        calibration_patch.start()
        self.addCleanup(calibration_patch.stop)
        distribution = {"world_size": 4, "global_batch_size": 4, "local_rows_per_step": 1,
                        "backend": "nccl", "device_type": "cuda"}
        run = evaluation.read_json(path.parent / "run.json")
        run.update(steps=27581, training_rows_consumed=110324, data_sha256=profile["sha256"],
                   calibration_rows=512, calibration_ids=ids, distribution=distribution,
                   seed=20260920,
                   identity_sha256="d" * 64, initialization="fresh_pinned_upstream")
        evaluation.write_json(path.parent / "run.json", run)
        summary = evaluation.read_json(path.parent / "summary.json")
        summary.update(steps=27581, trained_rows_consumed=110324, distribution=distribution)
        evaluation.write_json(path.parent / "summary.json", summary)
        evaluation.write_json(path / "temperature.json", {"temperature": 2.0, "split": "calibration", "n": 512,
            "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
        (path.parent / "calibration.jsonl").write_text("".join(json.dumps({"id": identifier, "logits": [1.0, 0.0]}) + "\n" for identifier in ids))
        (path.parent / "training.jsonl").write_text("".join(json.dumps({"step": step, "world_size": 4, "global_batch_size": 4,
            "loss": 0.5, "gradient_norm": 0.1, "elapsed_seconds": float(step)}) + "\n" for step in range(1, 27582)))
        data_identity = {**self.data_identity, "dataset_profile": "browser-drone-expansion-v1",
                         "partition": profile["partition"], "manifest_sha256": profile["manifest_sha256"],
                         "split_sha256": profile["sha256"], "counts": profile["counts"],
                         "total_rows": sum(profile["counts"].values())}
        return path, data_identity, set(ids)

    def test_model_profile_defaults_and_cross_profile_rejection(self):
        self.assertEqual(evaluation.selected_models("release-v2"), ("2b", "9b"))
        self.assertEqual(evaluation.selected_models("browser-drone-expansion-v1"), ("27b",))
        self.assertEqual(evaluation.selected_models("release-v2", ["9b", "2b"]), ("2b", "9b"))
        for profile, models in (("release-v2", ["27b"]), ("browser-drone-expansion-v1", ["2b"]),
                                ("browser-drone-expansion-v1", ["27b", "27b"]), ("release-v2", [])):
            with self.assertRaises(ValueError):
                evaluation.selected_models(profile, models)

    def test_expansion_40281_rows_use_global_order_without_padding_or_drop(self):
        rows = {split: [{"id": f"{split}-{i}"} for i in range(count)]
                for split, count in (("test", 14902), ("ood", 25379))}
        shards = [evaluation.shard_rows(rows, rank, partition="concatenated_test_ood") for rank in range(4)]
        self.assertEqual([len(shard) for shard in shards], [10071, 10070, 10070, 10070])
        identifiers = [row["id"] for shard in shards for _, _, row in shard]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertEqual(set(identifiers), {row["id"] for split in rows.values() for row in split})
        self.assertIn(("ood", 0, rows["ood"][0]), shards[2])
        self.assertEqual([len(evaluation.shard_rows(rows, rank)) for rank in range(4)], [10071, 10071, 10070, 10069])

    def test_expansion_manifest_and_each_split_are_fixed(self):
        name = "browser-drone-expansion-v1"
        with self.assertRaisesRegex(ValueError, "cannot be overridden"):
            evaluation.load_data(self.data, self.hashes, profile_name=name)
        with self.assertRaisesRegex(ValueError, "frozen"):
            evaluation.load_data(self.data, profile_name=name)
        # Substitute only fixture provenance, then exercise the actual strict byte checks.
        fixture = {"sha256": self.hashes, "manifest_sha256": evaluation.file_hash(self.data / "manifest.json"),
                   "counts": {split: len(self.rows[split]) for split in evaluation.SPLITS}}
        with patch.dict(evaluation.DATASET_PROFILES[name], fixture):
            _, identity, _ = evaluation.load_data(self.data, profile_name=name)
            self.assertEqual(identity["dataset_profile"], name)
            for split in self.hashes:
                path = self.data / f"{split}.jsonl"
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.subTest(split=split), self.assertRaisesRegex(ValueError, "checksum"):
                    evaluation.load_data(self.data, profile_name=name)
                path.write_bytes(original)
            path = self.data / "manifest.json"
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "frozen"):
                evaluation.load_data(self.data, profile_name=name)

    def test_expansion_checkpoint_requires_ddp_full_pass_and_saved_calibration(self):
        path, data, ids = self.expansion_checkpoint()
        def check():
            return evaluation.checkpoint_identity(path, "27b", data, ids, profile_name="browser-drone-expansion-v1")
        identity = check()
        self.assertEqual(identity["training_completion"]["steps"], 27581)
        self.assertEqual(identity["training_completion"]["distribution"]["world_size"], 4)
        mutations = [
            ("run.json", "steps", 20204), ("summary.json", "trained_rows_consumed", 80816),
            ("run.json", "distribution", {"world_size": 1, "global_batch_size": 4, "local_rows_per_step": 1}),
            ("run.json", "initialization", "single_process_migration"),
            ("run.json", "identity_sha256", "not-a-hash"), ("run.json", "calibration_rows", 511),
            ("run.json", "seed", 20260919),
            ("summary.json", "status", "running"), ("summary.json", "checkpoint_reload_max_error", 0.1),
        ]
        for filename, key, value in mutations:
            target = path.parent / filename
            original = target.read_bytes()
            values = evaluation.read_json(target)
            values[key] = value
            evaluation.write_json(target, values)
            with self.subTest(filename=filename, key=key), self.assertRaises(ValueError):
                check()
            target.write_bytes(original)
        run_path, temp_path = path.parent / "run.json", path / "temperature.json"
        run_original, temp_original = run_path.read_bytes(), temp_path.read_bytes()
        run, temp = evaluation.read_json(run_path), evaluation.read_json(temp_path)
        run["calibration_ids"].reverse()
        temp["ids_sha256"] = hashlib.sha256(json.dumps(run["calibration_ids"]).encode()).hexdigest()
        evaluation.write_json(run_path, run)
        evaluation.write_json(temp_path, temp)
        with self.assertRaisesRegex(ValueError, "fixed 512-row"):
            check()
        run_path.write_bytes(run_original)
        temp_path.write_bytes(temp_original)
        for filename in ("calibration.jsonl", "training.jsonl"):
            target = path.parent / filename
            original = target.read_bytes()
            target.write_bytes(b"\n".join(original.splitlines()[:-1]) + b"\n")
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                check()
            target.write_bytes(original)
        for key, value in (("dataset_profile", "release-v2"), ("manifest_sha256", "b" * 64),
                           ("split_sha256", evaluation.RELEASE_V2_HASHES), ("total_rows", 40280)):
            original = data[key]
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                check()
            data[key] = original

    def test_expansion_merge_binds_profile_data_assignment_and_failure_denominator(self):
        name = "browser-drone-expansion-v1"
        with patch.dict(evaluation.DATASET_PROFILES[name], {"counts": {split: len(self.rows[split]) for split in evaluation.SPLITS}}):
            path, data, ids = self.expansion_checkpoint()
            identity = evaluation.checkpoint_identity(path, "27b", data, ids, profile_name=name)
            for mutation in (None, "profile", "hash", "rank", "denominator", "old_partition", "missing", "duplicate"):
                directory = self.root / ("expansion-" + str(mutation))
                directory.mkdir()
                for rank in range(4):
                    self.make_shard(directory, rank, identity, self.plan_sha, ("test-0", "ood-1"), data)
                report_path = directory / "shard-0.json"
                report = evaluation.read_json(report_path)
                if mutation == "profile":
                    report["dataset_profile"] = "release-v2"
                elif mutation == "hash":
                    report["data_identity"]["split_sha256"]["test"] = "b" * 64
                elif mutation == "rank":
                    report["assignment"]["rank"] = 1
                elif mutation == "denominator":
                    report["data_identity"]["total_rows"] -= 1
                elif mutation == "old_partition":
                    report["assignment"] = evaluation.shard_identity(self.rows, 0)
                evaluation.write_json(report_path, report)
                if mutation in ("missing", "duplicate"):
                    self.mutate_rows(directory, 0, (lambda rows: rows.pop()) if mutation == "missing"
                                     else (lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0]))))
                if mutation:
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                        evaluation.merge_shards(self.rows, identity, directory, self.plan_sha, self.gpus,
                                                profile_name=name, data_identity=data)
                    self.assertFalse((directory / "merged-test.jsonl").exists())
                else:
                    summary = evaluation.merge_shards(self.rows, identity, directory, self.plan_sha, self.gpus,
                                                       profile_name=name, data_identity=data)
                    self.assertEqual(summary["total_rows"], 12)
                    self.assertEqual(summary["status"], "completed_with_errors")
                    self.assertEqual(summary["splits"]["test"]["count"], 7)
                    self.assertEqual(summary["splits"]["test"]["inference_coverage"], 6 / 7)

    def test_expansion_controller_runs_only_four_27b_workers(self):
        name = "browser-drone-expansion-v1"
        events = []
        with patch.dict(evaluation.DATASET_PROFILES[name], {"counts": {split: len(self.rows[split]) for split in evaluation.SPLITS}}):
            _, data, ids = self.expansion_checkpoint()
            class Process:
                pid = 5000
                returncode = 0
                def poll(self):
                    return 0
                def wait(self, timeout=None):
                    return 0
            def popen(command, **kwargs):
                plan_path = Path(command[command.index("--worker-plan") + 1])
                rank = int(command[-1])
                plan = evaluation.read_json(plan_path)
                events.append((plan["tag"], rank, plan["dataset_profile"]))
                self.assertEqual(plan["partition"], "concatenated_test_ood")
                self.make_shard(plan_path.parent, rank, plan["checkpoint"], evaluation.file_hash(plan_path), data_identity=data)
                return Process()
            manifest = self.controller(popen, profile_name=name, data_identity=data, calibration_ids=ids)
            self.assertEqual(events, [("27b", rank, name) for rank in range(4)])
            self.assertEqual(manifest["model_order"], ["27b"])
            self.assertEqual(manifest["status"], "complete")


if __name__ == "__main__":
    unittest.main()
