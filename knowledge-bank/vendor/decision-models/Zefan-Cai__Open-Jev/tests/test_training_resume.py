import argparse
import copy
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

from jev.train import (BASELINE_FILES, SNAPSHOT_FILES, _file_sha256,
                       read_training_checkpoint, restore_training_artifacts,
                       restore_training_state, save_training_checkpoint,
                       training_identity, validate_baseline_identity,
                       validate_resume_identity)


def arguments():
    return argparse.Namespace(model="Qwen/test", revision="pinned-revision", steps=8,
                              train_rows=0, calibration_rows=2, eval_rows=2, max_length=128,
                              lora_rank=8, accumulation=4, lr=0.00005, head_lr=0.0001,
                              brier_weight=0.1, seed=42, output="ignored-path", checkpoint_every=2)


class ResumeIdentityTests(unittest.TestCase):
    def test_identity_binds_training_configuration_dataset_and_order(self):
        args = arguments()
        rows = {"train": [{"id": "a"}, {"id": "b"}], "test": [{"id": "t"}], "calibration": [{"id": "c"}], "ood": [{"id": "o"}]}
        hashes = {"train": "digest-a", "test": "digest-b"}
        original = training_identity(args, hashes, rows, {"torch": "test-version"})
        changed_transport = copy.deepcopy(args)
        changed_transport.output = "other-output"
        changed_transport.checkpoint_every = 100
        validate_resume_identity(original, training_identity(changed_transport, hashes, rows, {"torch": "test-version"}))
        for field, value in (("model", "other-model"), ("revision", "other-revision"), ("lr", 0.01),
                             ("head_lr", 0.02), ("accumulation", 8), ("steps", 20), ("seed", 0),
                             ("max_length", 256), ("training_sampling", "shuffled")):
            altered = copy.deepcopy(args)
            setattr(altered, field, value)
            with self.assertRaises(ValueError, msg=field):
                validate_resume_identity(original, training_identity(altered, hashes, rows, {"torch": "test-version"}))
        for key in ("data_sha256", "selected_ids", "optimizer", "runtime", "implementation_sha256"):
            altered = copy.deepcopy(original)
            altered[key] = {"changed": True}
            with self.assertRaises(ValueError, msg=key):
                validate_resume_identity(original, altered)
        reversed_rows = {**rows, "train": list(reversed(rows["train"]))}
        with self.assertRaises(ValueError):
            validate_resume_identity(original, training_identity(args, hashes, reversed_rows, {"torch": "test-version"}))

    def test_original_baseline_ids_targets_and_order_are_required(self):
        rows = [{"id": str(index), "group_id": "g" + str(index), "source": "source", "kind": "noul", "target": [0, 1]} for index in range(2)]
        values = [{**row, "logits": [0.1, 0.2]} for row in rows]
        validate_baseline_identity(values, rows, "test")
        for changed in (list(reversed(values)), values[:1], [{**values[0], "target": [1, 0]}, values[1]]):
            with self.assertRaises(ValueError):
                validate_baseline_identity(changed, rows, "test")

    def test_snapshot_checksum_and_log_cursor_are_verified_before_tensor_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = {"arguments": {"steps": 5}}
            for name in SNAPSHOT_FILES:
                (root / name).write_text('{"step": 1}\n' if name == "training.jsonl" else "test artifact\n")
            metadata = {"schema_version": 1, "kind": "training_resume_only", "inference_ready": False,
                        "complete": True, "completed_step": 1, "identity": identity,
                        "files_sha256": {name: _file_sha256(root / name) for name in SNAPSHOT_FILES}}
            (root / "resume.json").write_text(json.dumps(metadata))
            self.assertEqual(read_training_checkpoint(root, identity)["completed_step"], 1)
            (root / "training_state.pt").write_text("corrupted artifact\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_training_checkpoint(root, identity)
            metadata["files_sha256"]["training_state.pt"] = _file_sha256(root / "training_state.pt")
            metadata["completed_step"] = 2
            (root / "resume.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "log cursor"):
                read_training_checkpoint(root, identity)
            metadata["kind"] = "inference_checkpoint"
            (root / "resume.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "Not a complete"):
                read_training_checkpoint(root, identity)

    def test_artifact_restore_archives_interrupted_log_and_keeps_final_calibration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, output = root / "snapshot", root / "output"
            snapshot.mkdir()
            output.mkdir()
            for name in BASELINE_FILES:
                (snapshot / name).write_text("baseline\n")
                (output / name).write_text("baseline\n")
            (snapshot / "training.jsonl").write_text('{"step": 1}\n')
            (output / "training.jsonl").write_text('{"step": 1}\n{"step": 2}\n')
            (output / "run.json").write_text('{"interrupted": true}\n')
            (output / "checkpoint").mkdir()
            final = output / "checkpoint" / "temperature.json"
            final.write_text('{"temperature": 0.8}\n')
            restore_training_artifacts(snapshot, output)
            self.assertEqual((output / "training.jsonl").read_text(), '{"step": 1}\n')
            archived = list((output / "resume-history").glob("*/training.jsonl"))
            self.assertEqual(len(archived), 1)
            self.assertIn('"step": 2', archived[0].read_text())
            self.assertEqual(final.read_text(), '{"temperature": 0.8}\n')
            (output / BASELINE_FILES[0]).write_text("different baseline\n")
            with self.assertRaisesRegex(ValueError, "different baseline"):
                restore_training_artifacts(snapshot, output)


@unittest.skipUnless(importlib.util.find_spec("torch"), "requires optional torch runtime")
class ResumeNumericalTests(unittest.TestCase):
    def test_cpu_dropout_rng_optimizer_and_parameter_trajectory_resume_exactly(self):
        import torch
        torch.manual_seed(102)
        random.seed(901)
        model = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Dropout(0.35), torch.nn.Linear(4, 1))
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.02)

        def step(network, optim):
            optim.zero_grad(set_to_none=True)
            # Both Torch and Python RNG materially affect the update.
            values = torch.randn(2, 3) * random.random()
            loss = network(values).square().mean()
            loss.backward()
            optim.step()
            return loss.detach().clone()

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for name in BASELINE_FILES:
                (output / name).write_text('{"id": "held-out"}\n')
            for _ in range(2):
                step(model, optimizer)
            (output / "training.jsonl").write_text('{"step": 1}\n{"step": 2}\n')
            identity = {"arguments": {"steps": 4}}
            snapshot = save_training_checkpoint(model, optimizer, 2, output, identity, {"started_at": 0})
            self.assertFalse((snapshot / "temperature.json").exists())
            self.assertFalse((snapshot / "model.json").exists())
            reference_losses = [step(model, optimizer) for _ in range(2)]
            reference_weights = {name: value.clone() for name, value in model.state_dict().items()}
            reference_python = random.random()
            reference_torch = torch.rand(3)
            restored = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.Dropout(0.35), torch.nn.Linear(4, 1))
            restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=0.02)
            metadata = read_training_checkpoint(snapshot, identity)
            self.assertEqual(restore_training_state(restored, restored_optimizer, snapshot, metadata), 2)
            resumed_losses = [step(restored, restored_optimizer) for _ in range(2)]
            for first, second in zip(reference_losses, resumed_losses):
                self.assertTrue(torch.equal(first, second))
            for name, parameter in restored.state_dict().items():
                self.assertTrue(torch.equal(parameter, reference_weights[name]), name)
            self.assertEqual(random.random(), reference_python)
            self.assertTrue(torch.equal(torch.rand(3), reference_torch))
            with self.assertRaisesRegex(ValueError, "already exists"):
                save_training_checkpoint(restored, restored_optimizer, 2, output, identity, {"started_at": 0})


if __name__ == "__main__":
    unittest.main()
