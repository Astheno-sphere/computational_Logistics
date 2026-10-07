import copy
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

from jev.train import BASELINE_FILES, SNAPSHOT_FILES, _file_sha256, _json_sha256
from jev.train_distributed import (checked_reload_error, distribution_identity, rank_row_index,
                                  read_distributed_checkpoint, validate_allocation)

HAS_TORCH = importlib.util.find_spec("torch") is not None
if HAS_TORCH:
    import torch
    from torch import nn
    import torch.distributed as dist
    from torch.nn.parallel import DistributedDataParallel
    from jev.train_distributed import (capture_rng, distributed_step, parameter_groups,
                                      restore_distributed_state, save_distributed_checkpoint,
                                      seed_training_rank, on_rank_zero)

    class TinyDecision(nn.Module):
        def __init__(self, stochastic=False):
            super().__init__()
            self.backbone = nn.Linear(3, 5)
            self.head = nn.Linear(5, 3)
            self.dropout = nn.Dropout(0.25 if stochastic else 0)
            self.stochastic = stochastic

        def forward(self, records):
            values = torch.tensor([row["features"] for row in records])
            if self.stochastic:
                values = values * (0.5 + random.random())
            logits = self.head(self.dropout(torch.tanh(self.backbone(values))))
            return list(logits.unbind())


def identity():
    return {"arguments": {"steps": 5, "accumulation": 4}, "selected_ids": {"train": [str(i) for i in range(13)]},
            "data_sha256": {"train": "frozen"}, "runtime": {"torch": "test"}, "implementation_sha256": {"train.py": "frozen"}}


def fake_snapshot(root):
    for name in SNAPSHOT_FILES:
        (root / name).write_text('{"step": 1}\n' if name == "training.jsonl" else "original\n")
    info = {"schema_version": 2, "kind": "distributed_training_resume_only", "complete": True,
            "inference_ready": False, "completed_step": 1, "identity": identity(), "distribution": distribution_identity("gloo"),
            "files_sha256": {name: _file_sha256(root / name) for name in SNAPSHOT_FILES}}
    (root / "resume.json").write_text(json.dumps(info))
    return info


class DistributedContractTests(unittest.TestCase):
    def test_reload_rejects_nonfinite_length_mismatch_and_large_error(self):
        self.assertAlmostEqual(checked_reload_error([1, 2], [1.01, 2]), 0.01)
        for reference, actual in (([1], [float("nan")]), ([float("inf")], [1]),
                                  ([1, 2], [1]), ([], []), ([1], [1.06])):
            with self.assertRaises(ValueError):
                checked_reload_error(reference, actual)

    def test_full_pass_has_no_padding_skips_or_reordering(self):
        indices = [rank_row_index(step, rank, 110324) for step in range(27581) for rank in range(4)]
        self.assertEqual(indices, list(range(110324)))
        self.assertEqual([rank_row_index(27580, r, 110324) for r in range(4)], [110320, 110321, 110322, 110323])
        self.assertEqual([rank_row_index(3, r, 13) for r in range(4)], [12, 0, 1, 2])
        for args in ((0, 0, 13, 2), (-1, 0, 13, 4), (0, 4, 13, 4), (0, 0, 0, 4)):
            with self.assertRaises(ValueError):
                rank_row_index(*args)

    def test_resource_policy_requires_exact_host_and_physical_uuids(self):
        policy = {"expected_hostname": "n1", "allowed_gpu_indices": [0, 1, 2, 3], "distributed_training_gpu_indices": [0, 1, 2, 3]}
        inventory = "\n".join(f"{i}, GPU-{i}" for i in range(8))
        visible = "GPU-0,GPU-1,GPU-2,GPU-3"
        self.assertEqual(validate_allocation(policy, "n1", visible, inventory)["physical_gpu_indices"], [0, 1, 2, 3])
        for host, devices in (("other", visible), ("n1", "0,1,2,3"), ("n1", "GPU-3,GPU-2,GPU-1,GPU-0"), ("n1", "GPU-0,GPU-1,GPU-2,GPU-4")):
            with self.assertRaises(ValueError):
                validate_allocation(policy, host, devices, inventory)
        with self.assertRaises(ValueError):
            validate_allocation({**policy, "distributed_training_gpu_indices": [4, 5, 6, 7]}, "n1", visible, inventory)

    def test_resume_rejects_changed_data_order_schedule_runtime_topology_and_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = fake_snapshot(root)
            self.assertEqual(read_distributed_checkpoint(root, identity(), info["distribution"])["completed_step"], 1)
            for field in ("arguments", "selected_ids", "data_sha256", "runtime", "implementation_sha256"):
                changed = copy.deepcopy(identity())
                changed[field] = {"changed": True}
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    read_distributed_checkpoint(root, changed, info["distribution"])
            for key, value in (("world_size", 2), ("implementation_sha256", "other"), ("backend", "nccl")):
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    read_distributed_checkpoint(root, identity(), {**info["distribution"], key: value})
            info["schema_version"] = 1
            (root / "resume.json").write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "single-process migration is unsupported"):
                read_distributed_checkpoint(root, identity(), info["distribution"])

    def test_snapshot_checksums_and_optimizer_cursor_are_checked_before_tensors(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = fake_snapshot(root)
            (root / BASELINE_FILES[0]).write_text("replaced baseline")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_distributed_checkpoint(root, identity(), info["distribution"])
            info["files_sha256"][BASELINE_FILES[0]] = _file_sha256(root / BASELINE_FILES[0])
            info["completed_step"] = 2
            (root / "resume.json").write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError, "log cursor"):
                read_distributed_checkpoint(root, identity(), info["distribution"])


def make_optimizer(model):
    return torch.optim.AdamW([{"params": model.backbone.parameters(), "lr": 0.005},
                             {"params": model.head.parameters(), "lr": 0.01}], weight_decay=0.01)


def rows():
    return [{"id": str(i), "features": [i / 13, (-1)**i, (i % 3) / 2],
             "target": [float(j == i % 3) for j in range(3)]} for i in range(13)]


def serial_step(model, optimizer, selected):
    optimizer.zero_grad(set_to_none=True)
    total = 0
    for row in selected:
        logits = model([row])[0].float()
        target = torch.tensor(row["target"])
        loss = -(target * logits.log_softmax(-1)).sum() + 0.1 * ((logits.softmax(-1) - target)**2).sum()
        (loss / 4).backward()
        total += loss.item() / 4
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
    optimizer.step()
    return total, norm.item()


def assert_tensor_states_equal(first, second, tolerance=2e-6):
    if isinstance(first, torch.Tensor):
        torch.testing.assert_close(first, second, rtol=tolerance, atol=tolerance)
    elif isinstance(first, dict):
        assert first.keys() == second.keys()
        for key in first:
            assert_tensor_states_equal(first[key], second[key], tolerance)
    elif isinstance(first, (list, tuple)):
        assert len(first) == len(second)
        for left, right in zip(first, second):
            assert_tensor_states_equal(left, right, tolerance)
    else:
        assert first == second, (first, second)


def numerical_worker(rank, rendezvous, directory, stochastic):
    torch.set_num_threads(1)
    dist.init_process_group("gloo", rank=rank, world_size=4, init_method="file://" + rendezvous)
    try:
        torch.manual_seed(100)
        model = TinyDecision(stochastic)
        reference = copy.deepcopy(model)
        optimizer = make_optimizer(model)
        reference_optimizer = make_optimizer(reference)
        ddp = DistributedDataParallel(model, broadcast_buffers=False)
        device = torch.device("cpu")
        seed_training_rank(20260920, rank, device)
        root = Path(directory)
        if rank == 0:
            for name in BASELINE_FILES:
                (root / name).write_text('{"id":"original-fresh-baseline"}\n')
            (root / "training.jsonl").write_text("")
        dist.barrier()
        data = rows()
        trajectory = []
        for step in range(5):
            measured = distributed_step(ddp, optimizer, data[rank_row_index(step, rank, len(data))], 0.1)
            if not stochastic:
                serial = serial_step(reference, reference_optimizer, [data[rank_row_index(step, r, len(data))] for r in range(4)])
                torch.testing.assert_close(torch.tensor(measured), torch.tensor(serial), rtol=2e-6, atol=2e-6)
                assert_tensor_states_equal(model.state_dict(), reference.state_dict())
                assert_tensor_states_equal(optimizer.state_dict(), reference_optimizer.state_dict())
            trajectory.append(measured)
            if rank == 0:
                with (root / "training.jsonl").open("a") as handle:
                    handle.write(json.dumps({"step": step + 1, "elapsed_seconds": 0, "loss": measured[0]}) + "\n")
            if step == 1:
                snapshot = save_distributed_checkpoint(model, optimizer, 2, root, identity(), distribution_identity("gloo"), {"started_at": 0}, device)
        expected_parameters = copy.deepcopy(model.state_dict())
        expected_optimizer = copy.deepcopy(optimizer.state_dict())
        expected_python, expected_torch = random.random(), torch.rand(3)
        # Assert all rank replicas, including the trained head, are synchronized.
        flattened = torch.cat([p.detach().flatten() for p in model.parameters()])
        replicas = [torch.zeros_like(flattened) for _ in range(4)]
        dist.all_gather(replicas, flattened)
        for replica in replicas:
            torch.testing.assert_close(replica, flattened, rtol=0, atol=0)
        del ddp, model, optimizer
        torch.manual_seed(999)
        restored = TinyDecision(stochastic)
        restored_optimizer = make_optimizer(restored)
        restored_ddp = DistributedDataParallel(restored, broadcast_buffers=False)
        info = read_distributed_checkpoint(snapshot, identity(), distribution_identity("gloo"))
        cursor = restore_distributed_state(restored, restored_optimizer, snapshot, info, rank, device)
        assert cursor == 2
        assert [rank_row_index(cursor, r, len(data)) for r in range(4)] == [8, 9, 10, 11]
        for step in range(cursor, 5):
            measured = distributed_step(restored_ddp, restored_optimizer, data[rank_row_index(step, rank, len(data))], 0.1)
            torch.testing.assert_close(torch.tensor(measured), torch.tensor(trajectory[step]), rtol=2e-6, atol=2e-6)
        assert_tensor_states_equal(restored.state_dict(), expected_parameters)
        assert_tensor_states_equal(restored_optimizer.state_dict(), expected_optimizer)
        assert random.random() == expected_python
        assert torch.equal(torch.rand(3), expected_torch)
        for name in BASELINE_FILES:
            assert (Path(snapshot) / name).read_bytes() == (root / name).read_bytes()
        assert len(list((root / "training-checkpoints").glob("step-*"))) == 1
        assert not list((root / "training-checkpoints").glob(".incomplete-*"))
        # A rank-zero failure must reach every process rather than strand peers.
        try:
            on_rank_zero(lambda: (_ for _ in ()).throw(ValueError("injected failure")))
        except RuntimeError as error:
            assert "injected failure" in str(error)
        else:
            raise AssertionError("Rank-zero error was swallowed")
        before_failure = copy.deepcopy(restored.state_dict())
        bad_row = copy.deepcopy(data[0])
        if rank == 2:
            bad_row["features"][0] = float("nan")
        try:
            distributed_step(restored_ddp, restored_optimizer, bad_row, 0.1)
        except FloatingPointError as error:
            assert "Nonfinite loss" in str(error)
        else:
            raise AssertionError("A rank's nonfinite loss did not stop all ranks")
        assert_tensor_states_equal(restored.state_dict(), before_failure, tolerance=0)
        (root / f"rank-{rank}.json").write_text(json.dumps({"global_batch_correspondence": not stochastic, "stochastic_resume": stochastic, "replicas_synchronized": True, "cursor": cursor, "steps": 5}))
    finally:
        dist.destroy_process_group()


@unittest.skipUnless(HAS_TORCH, "requires optional torch runtime")
class DistributedNumericalTests(unittest.TestCase):
    def test_cpu_final_evaluation_fits_calibration_and_preserves_original_baselines(self):
        from unittest.mock import patch
        from jev.metrics import fit_temperature
        from jev.train_distributed import evaluate, final_evaluation
        torch.manual_seed(21)
        model = TinyDecision()
        optimizer = make_optimizer(model)
        selected = {split: [{**row, "id": split + row["id"], "group_id": split + row["id"],
                             "source": "tiny", "kind": "score" if i % 2 else "choice", "metadata": {}}
                            for i, row in enumerate(rows()[:count])]
                    for split, count in (("calibration", 4), ("test", 3), ("ood", 5))}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = {split: evaluate(model, selected[split], root / name)
                        for split, name in zip(("test", "ood", "calibration"), BASELINE_FILES)}
            original = {name: (root / name).read_bytes() for name in BASELINE_FILES}
            model.train()
            for _ in range(3):
                serial_step(model, optimizer, rows()[:4])
            def save(path):
                path.mkdir()
                torch.save(model.state_dict(), path / "tiny.pt")
            model.save = save
            with patch("jev.metrics.fit_temperature", wraps=fit_temperature) as fitted:
                result, reference = final_evaluation(model, None, root, selected, baseline,
                                                     {"calibration_ids": [r["id"] for r in selected["calibration"]]})
            self.assertEqual(fitted.call_count, 2)
            for call in fitted.call_args_list:
                self.assertEqual(call.args[1], [r["target"] for r in selected["calibration"]])
            for name in BASELINE_FILES:
                self.assertEqual((root / name).read_bytes(), original[name])
            self.assertEqual(result["metrics"]["trained_test"]["count"], 3)
            self.assertEqual(result["metrics"]["trained_ood"]["count"], 5)
            calibration = json.loads((root / "checkpoint/temperature.json").read_text())
            self.assertEqual((calibration["split"], calibration["n"]), ("calibration", 4))
            restored = TinyDecision()
            restored.load_state_dict(torch.load(root / "checkpoint/tiny.pt", weights_only=True))
            actual = evaluate(restored, selected["test"][:1], root / "reload.jsonl")[0]["logits"]
            self.assertEqual(checked_reload_error(reference, actual), 0)

    def launch(self, stochastic):
        if not dist.is_available() or not dist.is_gloo_available():
            self.skipTest("requires CPU/Gloo")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            torch.multiprocessing.spawn(numerical_worker, args=(str(root / "rendezvous"), str(root), stochastic), nprocs=4, join=True)
            reports = [json.loads((root / f"rank-{rank}.json").read_text()) for rank in range(4)]
            self.assertTrue(all(r["replicas_synchronized"] and r["cursor"] == 2 and r["steps"] == 5 for r in reports))

    def test_four_rank_global_batch_matches_serial_parameters_optimizer_and_losses(self):
        self.launch(False)

    def test_four_rank_dropout_python_torch_rng_and_optimizer_resume(self):
        self.launch(True)

    def test_restore_rejects_missing_optimizer_moment_and_reordered_parameter_groups(self):
        torch.manual_seed(11)
        model = TinyDecision()
        optimizer = make_optimizer(model)
        serial_step(model, optimizer, rows()[:4])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            meta = {"completed_step": 1, "identity": identity(), "distribution": distribution_identity("gloo")}
            state = {"completed_step": 1, "identity_sha256": _json_sha256({"training": identity(), "distribution": meta["distribution"]}),
                     "trainable_parameters": {n: p.detach().clone() for n, p in model.named_parameters()},
                     "parameter_groups": parameter_groups(model, optimizer), "optimizer": optimizer.state_dict(),
                     "rng_by_rank": [capture_rng(torch.device("cpu")) for _ in range(4)]}
            def reject(changed, message):
                torch.save(changed, root / "training_state.pt")
                fresh = TinyDecision()
                with self.assertRaisesRegex(ValueError, message):
                    restore_distributed_state(fresh, make_optimizer(fresh), root, meta, 0, torch.device("cpu"))
            changed = copy.deepcopy(state)
            del changed["optimizer"]["state"][0]["exp_avg"]
            reject(changed, "optimizer state")
            changed = copy.deepcopy(state)
            changed["parameter_groups"][0].reverse()
            reject(changed, "group order")
            changed = copy.deepcopy(state)
            changed["rng_by_rank"].pop()
            reject(changed, "four saved rank RNG")
            changed = copy.deepcopy(state)
            changed["optimizer"]["param_groups"][0]["lr"] = 0.5
            reject(changed, "hyperparameters")


if __name__ == "__main__":
    unittest.main()
