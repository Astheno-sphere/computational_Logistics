import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from jev.train import BASELINE_FILES, SNAPSHOT_FILES, _file_sha256, _json_sha256, read_rows, validate_resume_identity
from jev.train_distributed import (bind_initialization_identity, distribution_identity,
                                   read_distributed_checkpoint, read_initialization_checkpoint,
                                   validate_initialization_provenance)

HAS_TORCH = importlib.util.find_spec("torch") is not None
MODEL, REVISION, LORA_RANK = "Qwen/tiny-test", "a" * 40, 8


def source_identity():
    return {"arguments": {"model": MODEL, "revision": REVISION, "lora_rank": LORA_RANK, "steps": 9},
            "data_sha256": {"train": "old-data"}, "selected_ids": {"train": ["old-row"]}}


def snapshot_manifest(path, identity=None, completed_step=2):
    path.mkdir(parents=True, exist_ok=True)
    for name in SNAPSHOT_FILES:
        if not (path / name).exists():
            (path / name).write_text("old baseline\n" if name != "training.jsonl" else
                                     "".join(json.dumps({"step": step}) + "\n" for step in range(1, completed_step + 1)))
    metadata = {"schema_version": 2, "kind": "distributed_training_resume_only", "complete": True,
                "inference_ready": False, "completed_step": completed_step,
                "identity": identity or source_identity(), "distribution": distribution_identity("gloo"),
                "files_sha256": {name: _file_sha256(path / name) for name in SNAPSHOT_FILES}}
    (path / "resume.json").write_text(json.dumps(metadata))
    return metadata


class InitializationContractTests(unittest.TestCase):
    def test_weights_initialization_accepts_new_data_but_binds_source_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "old"
            saved = snapshot_manifest(source)
            metadata, provenance = read_initialization_checkpoint(source, MODEL, REVISION, LORA_RANK)
            self.assertEqual(metadata, saved)
            current = {"arguments": {"steps": 50}, "data_sha256": {"train": "new-data"}}
            initialized = bind_initialization_identity(current, initialization=provenance)
            self.assertEqual(initialized["data_sha256"], {"train": "new-data"})
            self.assertEqual(provenance["source_completed_step"], 2)
            self.assertEqual(provenance["step_cursor"], 0)
            self.assertEqual(provenance["source_training_identity_sha256"], _json_sha256(saved["identity"]))
            self.assertNotIn("initialization", current)
            relocated = source.with_name("relocated")
            shutil.copytree(source, relocated)
            self.assertEqual(provenance, read_initialization_checkpoint(relocated, MODEL, REVISION, LORA_RANK)[1])
            self.assertEqual(bind_initialization_identity(current, resume_metadata={"identity": initialized}), initialized)
            self.assertEqual(bind_initialization_identity(current), current)
            for changed in (current, {**initialized, "initialization": {**provenance, "source_manifest_sha256": "0" * 64}}):
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    validate_resume_identity(initialized, changed)

    def test_model_revision_rank_topology_and_complete_snapshot_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            saved = snapshot_manifest(path)
            for model, revision, rank in (("other", REVISION, LORA_RANK), (MODEL, "b" * 40, LORA_RANK),
                                          (MODEL, REVISION, 16), (MODEL, REVISION, 8.0)):
                with self.subTest(model=model, revision=revision, rank=rank), self.assertRaises(ValueError):
                    read_initialization_checkpoint(path, model, revision, rank)
            for field, value in (("complete", False), ("schema_version", 1), ("inference_ready", True),
                                 ("completed_step", True), ("completed_step", 0)):
                (path / "resume.json").write_text(json.dumps({**saved, field: value}))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
            changed = {**saved, "distribution": {**saved["distribution"], "world_size": 2}}
            (path / "resume.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "four-rank"):
                read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
            changed = copy.deepcopy(saved)
            changed["identity"]["arguments"]["lora_rank"] = 0
            (path / "resume.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "four-rank LoRA"):
                read_initialization_checkpoint(path, MODEL, REVISION, 0)

    def test_all_snapshot_artifacts_and_old_log_cursor_are_verified(self):
        for artifact in SNAPSHOT_FILES:
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)
                snapshot_manifest(path)
                (path / artifact).write_text("changed\n")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            saved = snapshot_manifest(path)
            saved["completed_step"] = 3
            (path / "resume.json").write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "log cursor"):
                read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)

    def test_provenance_rejects_missing_extra_malformed_and_reset_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            snapshot_manifest(path)
            _, provenance = read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
            malformed = [{}, None, {**provenance, "unexpected": 1},
                         {key: value for key, value in provenance.items() if key != "source_manifest_sha256"}]
            for key, value in (("source_manifest_sha256", "invalid"), ("source_completed_step", True),
                               ("source_completed_step", 0), ("step_cursor", False), ("step_cursor", 2),
                               ("optimizer", "restored"), ("rng", "restored"), ("baseline_initialization", "pretrained")):
                malformed.append({**provenance, key: value})
            for value in malformed:
                with self.subTest(provenance=value), self.assertRaises(ValueError):
                    validate_initialization_provenance(value)
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                bind_initialization_identity({}, initialization=provenance, resume_metadata={})

    def test_cli_and_programmatic_run_reject_initialization_plus_resume(self):
        from jev.train_distributed import main, run
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            run(argparse.Namespace(initialize_training_weights="source", resume_training="resume"))
        argv = ["trainer", "--model", MODEL, "--revision", REVISION, "--data", "data", "--output", "out",
                "--initialize-training-weights", "source", "--resume-training", "resume"]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 2)


if HAS_TORCH:
    import torch
    from torch import nn
    import torch.distributed as dist
    from jev.train_distributed import (capture_rng, initialize_training_weights, parameter_groups,
                                       restore_distributed_state, seed_training_rank)

    class TinyDecision(nn.Module):
        def __init__(self, *args, **kwargs):
            super().__init__()
            self.backbone = nn.ModuleDict({"base": nn.Linear(3, 4, bias=False),
                                           "lora_A": nn.Linear(3, 2, bias=False),
                                           "lora_B": nn.Linear(2, 4, bias=False)})
            with torch.no_grad():
                self.backbone["base"].weight.copy_(torch.arange(12).reshape(4, 3) / 12)
            self.backbone["base"].requires_grad_(False)
            self.head = nn.Linear(4, 3)
            self.dropout = nn.Dropout(0.2)

        def forward(self, records):
            values = torch.tensor([row["state"]["features"] for row in records])
            if self.training:
                values = values * (0.5 + random.random())
            hidden = self.backbone["base"](values) + self.backbone["lora_B"](self.backbone["lora_A"](values))
            return list(self.head(self.dropout(hidden.tanh())).unbind())

        def save(self, path):
            path.mkdir()
            torch.save(self.state_dict(), path / "tiny.pt")

        @classmethod
        def load(cls, path, **kwargs):
            model = cls()
            model.load_state_dict(torch.load(path / "tiny.pt", weights_only=True))
            return model


def dataset_rows(split, count=3):
    return [{"id": f"new-{split}-{i}", "group_id": f"new-{split}-{i}", "source": "tiny-test",
             "split": split, "kind": "choice", "question": "Choose the label.",
             "state": {"features": [i / 3, (-1)**i, (i % 3) / 2], "split": split},
             "options": ["a", "b", "c"], "target": [float(j == i % 3) for j in range(3)],
             "metadata": {"family": "policy", "template_id": "tiny-" + split,
                          "provenance": {"type": "synthetic", "license": "MIT", "split_policy": "disjoint groups",
                                         "generator_version": "tiny-test", "seed": 11, "group_index": i, "variant": 0}}}
            for i in range(count)]


def optimizer_for(model):
    return torch.optim.AdamW([{"params": [p for p in model.backbone.parameters() if p.requires_grad], "lr": 0.005},
                             {"params": model.head.parameters(), "lr": 0.01}], weight_decay=0.01)


def tensor_snapshot(path, identity=None):
    torch.manual_seed(7)
    random.seed(8)
    model = TinyDecision()
    optimizer = optimizer_for(model)
    for _ in range(2):
        optimizer.zero_grad(set_to_none=True)
        loss = sum(logits.square().sum() for logits in model(dataset_rows("train")))
        loss.backward()
        optimizer.step()
    saved_identity = identity or source_identity()
    state = {"completed_step": 2, "identity_sha256": _json_sha256({"training": saved_identity, "distribution": distribution_identity("gloo")}),
             "trainable_parameters": {name: p.detach().clone() for name, p in model.named_parameters() if p.requires_grad},
             "parameter_groups": parameter_groups(model, optimizer), "optimizer": optimizer.state_dict(),
             "rng_by_rank": [capture_rng(torch.device("cpu")) for _ in range(4)]}
    path.mkdir(parents=True, exist_ok=True)
    torch.save(state, path / "training_state.pt")
    snapshot_manifest(path, saved_identity)
    return model, state


def rewrite_tensor_snapshot(path, state):
    torch.save(state, path / "training_state.pt")
    metadata = json.loads((path / "resume.json").read_text())
    metadata["files_sha256"]["training_state.pt"] = _file_sha256(path / "training_state.pt")
    (path / "resume.json").write_text(json.dumps(metadata))
    return read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)


@unittest.skipUnless(HAS_TORCH, "requires optional torch runtime")
class InitializationNumericalTests(unittest.TestCase):
    def test_only_trainable_weights_copy_without_optimizer_rng_or_base_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            source, saved = tensor_snapshot(path)
            metadata, provenance = read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
            torch.manual_seed(90)
            random.seed(91)
            model = TinyDecision()
            optimizer = optimizer_for(model)
            frozen = model.backbone["base"].weight.clone()
            python_rng, torch_rng = random.getstate(), torch.get_rng_state().clone()
            self.assertTrue(saved["optimizer"]["state"])
            initialize_training_weights(model, path, metadata, provenance)
            self.assertEqual(optimizer.state_dict()["state"], {})
            self.assertEqual(random.getstate(), python_rng)
            self.assertTrue(torch.equal(torch.get_rng_state(), torch_rng))
            self.assertTrue(torch.equal(model.backbone["base"].weight, frozen))
            for name, parameter in model.named_parameters():
                if parameter.requires_grad:
                    self.assertTrue(torch.equal(parameter, dict(source.named_parameters())[name]), name)
            # A new training stage owns new rank streams, independent of source RNG.
            streams = [seed_training_rank(20260921, rank, torch.device("cpu")) for rank in range(4)]
            self.assertEqual(len(set(streams)), 4)
            self.assertNotEqual(torch.get_rng_state().tolist(), saved["rng_by_rank"][0]["torch_cpu"].tolist())

    def test_invalid_tensor_payload_never_partially_copies_weights(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            _, saved = tensor_snapshot(path)
            last = next(reversed(saved["trainable_parameters"]))
            invalid = []
            for field, value in (("identity_sha256", "wrong"), ("completed_step", 1), ("completed_step", 2.0)):
                invalid.append(({**saved, field: value}, "identity/cursor"))
            invalid.append(({**saved, "trainable_parameters": {}}, "names differ"))
            for tensor in (torch.ones(77), saved["trainable_parameters"][last].double(),
                           torch.full_like(saved["trainable_parameters"][last], float("nan")), "not a tensor"):
                changed = copy.deepcopy(saved)
                changed["trainable_parameters"][last] = tensor
                invalid.append((changed, "shape/dtype/value"))
            for state, message in invalid:
                with self.subTest(message=message):
                    metadata, provenance = rewrite_tensor_snapshot(path, state)
                    model = TinyDecision()
                    before = copy.deepcopy(model.state_dict())
                    with self.assertRaisesRegex(ValueError, message):
                        initialize_training_weights(model, path, metadata, provenance)
                    for name, parameter in model.state_dict().items():
                        self.assertTrue(torch.equal(parameter, before[name]), name)

    def test_changed_preflight_bytes_or_provenance_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            tensor_snapshot(path)
            metadata, provenance = read_initialization_checkpoint(path, MODEL, REVISION, LORA_RANK)
            model = TinyDecision()
            for key, value in (("source_training_identity_sha256", "0" * 64),
                               ("source_distribution_sha256", "0" * 64), ("source_completed_step", 3)):
                with self.assertRaisesRegex(ValueError, "provenance differs"):
                    initialize_training_weights(model, path, metadata, {**provenance, key: value})
            for filename in ("resume.json", "training_state.pt"):
                original = (path / filename).read_bytes()
                (path / filename).write_bytes(original + b" ")
                with self.assertRaisesRegex(ValueError, "changed after preflight"):
                    initialize_training_weights(model, path, metadata, provenance)
                (path / filename).write_bytes(original)

    def test_future_resume_tensor_binding_rejects_removed_or_rewritten_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tensor_snapshot(root / "source")
            _, provenance = read_initialization_checkpoint(root / "source", MODEL, REVISION, LORA_RANK)
            initialized = bind_initialization_identity(source_identity(), initialization=provenance)
            tensor_snapshot(root / "new-stage", identity=initialized)
            metadata = read_distributed_checkpoint(root / "new-stage", initialized, distribution_identity("gloo"))
            for altered in (source_identity(), {**initialized, "initialization": {**provenance, "source_manifest_sha256": "0" * 64}}):
                hint = {**metadata, "identity": altered}
                expected = bind_initialization_identity(source_identity(), resume_metadata=hint)
                self.assertEqual(expected, altered)
                model = TinyDecision()
                before = copy.deepcopy(model.state_dict())
                with self.assertRaisesRegex(ValueError, "tensor identity/cursor"):
                    restore_distributed_state(model, optimizer_for(model), root / "new-stage", hint, 0, torch.device("cpu"))
                for name, parameter in model.state_dict().items():
                    self.assertTrue(torch.equal(parameter, before[name]), name)

    def test_four_rank_run_measures_initialized_baseline_and_resumes_new_stage_trajectory(self):
        if not dist.is_available() or not dist.is_gloo_available():
            self.skipTest("requires CPU/Gloo")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, _ = tensor_snapshot(root / "source")
            data = root / "data"
            data.mkdir()
            for split in ("train", "calibration", "validation", "test", "ood"):
                (data / (split + ".jsonl")).write_text("".join(json.dumps(row) + "\n" for row in dataset_rows(split, 9 if split == "train" else 3)))
            torch.multiprocessing.spawn(initialization_worker, args=(str(root),), nprocs=4, join=True)
            full, resumed = root / "full", root / "resumed"
            for name in BASELINE_FILES:
                self.assertEqual((full / name).read_bytes(), (resumed / name).read_bytes())
            baseline = [json.loads(line) for line in (full / BASELINE_FILES[0]).read_text().splitlines()]
            selected = read_rows(data / "test.jsonl", 3, 123, balanced=True)
            source.eval()
            self.assertEqual([row["id"] for row in baseline], [row["id"] for row in selected])
            for row, record in zip(baseline, selected):
                torch.testing.assert_close(torch.tensor(row["logits"]), source([record])[0].detach(), rtol=0, atol=0)
            torch.manual_seed(123)
            fresh = TinyDecision().eval()
            self.assertFalse(torch.equal(fresh(selected)[0], source(selected)[0]))
            original = json.loads((full / "run.json").read_text())
            continued = json.loads((resumed / "run.json").read_text())
            self.assertEqual(original["resume_step"], 0)
            self.assertEqual(continued["resume_step"], 1)
            self.assertEqual(original["baseline_initialization"], "warm_start_checkpoint")
            self.assertEqual(original["initialization_provenance"], continued["initialization_provenance"])
            self.assertFalse((root / "source").exists())
            checkpoints = [torch.load(path / "training-checkpoints/step-00000002/training_state.pt", weights_only=True) for path in (full, resumed)]
            self.assertEqual(checkpoints[0]["completed_step"], 2)
            for key, value in checkpoints[0]["trainable_parameters"].items():
                torch.testing.assert_close(value, checkpoints[1]["trainable_parameters"][key], rtol=2e-6, atol=2e-6)
            for identifier, moments in checkpoints[0]["optimizer"]["state"].items():
                self.assertEqual(moments["step"].item(), 2)
                for key, value in moments.items():
                    torch.testing.assert_close(value, checkpoints[1]["optimizer"]["state"][identifier][key], rtol=2e-6, atol=2e-6)
            for first, second in zip(checkpoints[0]["rng_by_rank"], checkpoints[1]["rng_by_rank"]):
                self.assertEqual(first["python"], second["python"])
                self.assertTrue(torch.equal(first["torch_cpu"], second["torch_cpu"]))
            logs = [[json.loads(line) for line in (path / "training.jsonl").read_text().splitlines()] for path in (full, resumed)]
            self.assertEqual([row["step"] for row in logs[0]], [1, 2])
            torch.testing.assert_close(torch.tensor([row["loss"] for row in logs[0]]),
                                       torch.tensor([row["loss"] for row in logs[1]]), rtol=2e-6, atol=2e-6)
            for rank in range(4):
                self.assertEqual(json.loads((root / f"rank-{rank}.json").read_text()), {"fresh_optimizer": True, "new_rank_rng": True, "new_cursor": True})


def initialization_worker(rank, directory):
    from jev.train_distributed import distributed_step, run
    torch.set_num_threads(1)
    root = Path(directory)
    args = argparse.Namespace(model=MODEL, revision=REVISION, data=str(root / "data"), output=str(root / "full"),
                              steps=2, train_rows=0, calibration_rows=3, eval_rows=3, max_length=128, lora_rank=LORA_RANK,
                              accumulation=4, seed=123, checkpoint_every=1, timeout_seconds=60, lr=0.005, head_lr=0.01,
                              brier_weight=0.1, training_sampling="shuffled", backend="gloo", resource_policy="unused",
                              initialize_training_weights=str(root / "source"), resume_training=None)
    fake_module = types.ModuleType("jev.model")
    fake_module.DecisionModel = TinyDecision
    # This worker is an isolated child. Avoid patch.dict(sys.modules), which
    # would unload Torch's newly imported extension registrations between runs.
    sys.modules["jev.model"] = fake_module
    init_group = dist.init_process_group
    results = {}
    for stage in ("full", "resumed"):
        calls = 0
        def checked_step(ddp, optimizer, row, brier_weight):
            nonlocal calls
            if calls == 0:
                train = read_rows(root / "data/train.jsonl", 0, args.seed)
                expected_index = rank if stage == "full" else 4 + rank
                assert row["id"] == train[expected_index]["id"]
                if stage == "full":
                    assert not optimizer.state
                    seed = int(_json_sha256(["open-jev-ddp-rng-v1", args.seed, rank])[:16], 16) % (2**63 - 1)
                    assert random.getstate() == random.Random(seed).getstate()
                    generator = torch.Generator().manual_seed(seed)
                    assert torch.equal(torch.get_rng_state(), generator.get_state())
                    results.update(fresh_optimizer=True, new_rank_rng=True, new_cursor=True)
                else:
                    assert optimizer.state
            calls += 1
            return distributed_step(ddp, optimizer, row, brier_weight)
        def start_group(backend, **kwargs):
            return init_group(backend, rank=rank, world_size=4,
                              init_method="file://" + str(root / ("rendezvous-" + stage)), **kwargs)
        with patch.dict(os.environ, {"RANK": str(rank), "LOCAL_RANK": str(rank), "WORLD_SIZE": "4", "LOCAL_WORLD_SIZE": "4", "CUDA_VISIBLE_DEVICES": ""}), \
                patch("importlib.metadata.version", return_value="tiny-test"), \
                patch.object(dist, "init_process_group", side_effect=start_group), \
                patch("jev.train_distributed.distributed_step", side_effect=checked_step):
            run(args)
        if stage == "full":
            if rank == 0:
                (root / "source").rename(root / "relocated-source")
            args.output = str(root / "resumed")
            args.resume_training = str(root / "full/training-checkpoints/step-00000001")
            args.initialize_training_weights = None
    (root / f"rank-{rank}.json").write_text(json.dumps(results))


if __name__ == "__main__":
    unittest.main()
