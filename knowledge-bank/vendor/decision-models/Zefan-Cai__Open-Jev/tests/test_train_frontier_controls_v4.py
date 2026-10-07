import copy
import json
from pathlib import Path
import tempfile
import unittest

from jev.frontier_controls_v4 import build, records
from scripts.train_frontier_controls_v4 import calibrate, checkpoint_identity, enable_adaptation, load_selection, select_groups


class Parameter:
    def __init__(self):
        self.requires_grad = True

    def requires_grad_(self, value):
        self.requires_grad = value


class FakeModel:
    def __init__(self):
        self.values = {name: Parameter() for name in ["backbone.base_model.layers.0.weight", "backbone.embed_tokens.weight",
                      "backbone.base_model.layers.0.lora_A.default.weight", "backbone.base_model.layers.0.lora_B.default.weight", "head.weight"]}
        self.backbone = self
        self.checkpointing = self.input_grads = False

    def requires_grad_(self, value):
        for parameter in self.values.values():
            parameter.requires_grad_(value)

    def named_parameters(self):
        return self.values.items()

    def gradient_checkpointing_enable(self):
        self.checkpointing = True

    def enable_input_require_grads(self):
        self.input_grads = True


class ContinuedTrainingTest(unittest.TestCase):
    def test_group_sampling_keeps_counterfactuals_and_is_label_independent(self):
        rows = [row for row in records(8) if row["split"] == "train"]
        selected = select_groups(rows, 32, 20261002)
        altered = copy.deepcopy(rows)
        for row in altered:
            row["target"].reverse()
        self.assertEqual([row["id"] for row in selected], [row["id"] for row in select_groups(altered, 32, 20261002)])
        groups = {row["group_id"] for row in selected}
        self.assertEqual(len(groups), 8)
        self.assertTrue(all(sum(row["group_id"] == group for row in selected) == 4 for group in groups))
        with self.assertRaises(ValueError):
            select_groups(rows, 31, 1)

    def test_frozen_input_hashes_and_separate_calibration(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "data"
            build(directory, 8)
            selected, identity = load_selection(directory, 32, 24, 24, 1)
            sets = [{row["group_id"] for row in split} for split in selected.values()]
            self.assertTrue(all(not a & b for i, a in enumerate(sets) for b in sets[i + 1:]))
            self.assertEqual(identity["selected_ids"]["test"], [row["id"] for row in selected["test"]])
            with (directory / "test.jsonl").open("a") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                load_selection(directory, 32, 24, 24, 1)
        with self.assertRaisesRegex(ValueError, "only independent calibration"):
            calibrate([{"split": "test", "logits": [1, 0], "target": [1, 0]}])
        value = calibrate([{"split": "calibration", "logits": [1, 0], "target": [1, 0]}])
        self.assertGreater(value, 0)

    def test_only_existing_lora_and_head_train(self):
        model = FakeModel()
        names = enable_adaptation(model)
        self.assertTrue(model.checkpointing and model.input_grads)
        self.assertEqual(set(names), {"backbone.base_model.layers.0.lora_A.default.weight", "backbone.base_model.layers.0.lora_B.default.weight", "head.weight"})
        self.assertFalse(model.values["backbone.base_model.layers.0.weight"].requires_grad)
        self.assertFalse(model.values["backbone.embed_tokens.weight"].requires_grad)

    def test_identity_binds_head_adapter_and_released_temperature(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "adapter").mkdir()
            (path / "head.pt").write_bytes(b"head")
            (path / "adapter/adapter_model.safetensors").write_bytes(b"adapter")
            (path / "adapter/adapter_config.json").write_text("{}")
            (path / "model.json").write_text(json.dumps({"lora_rank": 8, "model_id": "Qwen/base", "revision": "a" * 40}))
            (path / "temperature.json").write_text('{"temperature": 0.8}')
            first = checkpoint_identity(path)
            self.assertEqual(first["temperature"], 0.8)
            config = json.loads((path / "model.json").read_text())
            for revision in (None, "main", "g" * 40):
                (path / "model.json").write_text(json.dumps({**config, "revision": revision}))
                with self.assertRaisesRegex(ValueError, "pinned 40-character base revision"):
                    checkpoint_identity(path)
            (path / "model.json").write_text(json.dumps(config))
            (path / "head.pt").write_bytes(b"changed")
            self.assertNotEqual(first["sha256"], checkpoint_identity(path)["sha256"])
            (path / "temperature.json").write_text('{"temperature": 0}')
            with self.assertRaisesRegex(ValueError, "Invalid released"):
                checkpoint_identity(path)


if __name__ == "__main__":
    unittest.main()
