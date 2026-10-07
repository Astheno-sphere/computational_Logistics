from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.launch_expansion import enforce_resource_policy, main


POLICY = {"expected_hostname": "kwade5342000001", "allowed_gpu_indices": [0, 1, 2, 3],
          "training_gpu_indices": [0, 1, 2], "serial_evaluation_gpu_index": 3,
          "prohibited_nodes": ["datava-004"]}


class LauncherResourcePolicyTests(unittest.TestCase):
    def policy_root(self, temporary, policy=POLICY):
        root = Path(temporary)
        path = root / "state/auto_research/resource_policy.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(policy))
        return root

    def test_wrong_host_and_prohibited_training_cards_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.policy_root(temporary)
            for hostname in ("datava-004", "another-node"):
                with self.assertRaisesRegex(ValueError, "forbids host"):
                    enforce_resource_policy(root, [0, 1, 2], hostname=hostname)
            for gpus in ([0, 1, 3], [0, 1, 4], [0, 1, -1]):
                with self.assertRaises(ValueError):
                    enforce_resource_policy(root, gpus, hostname="kwade5342000001")

    def test_matching_n1_hostname_and_training_cards_are_accepted_and_audited(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.policy_root(temporary)
            result = enforce_resource_policy(root, [2, 0, 1], hostname="kwade5342000001.cluster.internal")
            self.assertTrue(result["enforced"])
            self.assertEqual(result["policies"][0]["training_gpu_indices"], [0, 1, 2])
            self.assertEqual(len(result["policies"][0]["sha256"]), 64)

    def test_explicit_policy_cannot_bypass_repository_restriction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.policy_root(temporary)
            extra = root / "other-policy.json"
            extra.write_text(json.dumps({**POLICY, "expected_hostname": "datava-004", "prohibited_nodes": []}))
            with self.assertRaisesRegex(ValueError, "forbids host"):
                enforce_resource_policy(root, [0, 1, 2], extra, hostname="datava-004")
            with self.assertRaisesRegex(ValueError, "does not exist"):
                enforce_resource_policy(root, [0, 1, 2], root / "missing.json", hostname="kwade5342000001")

    def test_malformed_or_contradictory_policy_fails_closed(self):
        for update in ({"training_gpu_indices": [0, 1, 4]}, {"allowed_gpu_indices": [False, 1, 2, 3]},
                       {"training_gpu_indices": []}, {"serial_evaluation_gpu_index": 2}, {"expected_hostname": ""}):
            with tempfile.TemporaryDirectory() as temporary:
                root = self.policy_root(temporary, {**POLICY, **update})
                with self.assertRaises(ValueError):
                    enforce_resource_policy(root, [0, 1, 2], hostname="kwade5342000001")
        with tempfile.TemporaryDirectory() as temporary:
            self.assertFalse(enforce_resource_policy(temporary, [0, 1, 2], hostname="generic-node")["enforced"])

    def test_main_rejects_wrong_host_before_any_subprocess_or_gpu_query(self):
        argv = ["launch_expansion.py", "--data", "unused", "--run-root", "unused"]
        with tempfile.TemporaryDirectory() as temporary:
            root = self.policy_root(temporary)
            with patch("scripts.launch_expansion.__file__", str(root / "scripts/launch_expansion.py")), \
                    patch("sys.argv", argv), patch("scripts.launch_expansion.socket.gethostname", return_value="datava-004"), \
                    patch("scripts.launch_expansion.subprocess.run") as run, \
                    patch("scripts.launch_expansion.subprocess.check_output") as output, \
                    patch("scripts.launch_expansion.subprocess.Popen") as popen:
                with self.assertRaisesRegex(ValueError, "forbids host"):
                    main()
                run.assert_not_called()
                output.assert_not_called()
                popen.assert_not_called()

    def test_main_binds_accepted_physical_indices_to_their_gpu_uuids(self):
        def command_output(command, **kwargs):
            if command[0] == "git":
                return "a" * 40 + "\n"
            if "--query-compute-apps=gpu_uuid" in command:
                return ""
            return "0, GPU-physical-zero, 0, 0\n1, GPU-physical-one, 0, 0\n2, GPU-physical-two, 0, 0\n3, GPU-evaluation-only, 0, 0\n"

        with tempfile.TemporaryDirectory() as temporary:
            root = self.policy_root(temporary)
            output_dir = root / "runs"
            argv = ["launch_expansion.py", "--data", temporary, "--run-root", str(output_dir), "--gpus", "2", "0", "1"]
            with patch("scripts.launch_expansion.__file__", str(root / "scripts/launch_expansion.py")), \
                    patch("sys.argv", argv), patch("scripts.launch_expansion.socket.gethostname", return_value="kwade5342000001"), \
                    patch("scripts.launch_expansion.subprocess.run"), \
                    patch("scripts.launch_expansion.subprocess.check_output", side_effect=command_output), \
                    patch("scripts.launch_expansion.subprocess.Popen", side_effect=[Mock(pid=10), Mock(pid=11), Mock(pid=12)]) as popen, \
                    redirect_stdout(io.StringIO()):
                main()
            self.assertEqual([call.kwargs["env"]["CUDA_VISIBLE_DEVICES"] for call in popen.call_args_list],
                             ["GPU-physical-two", "GPU-physical-zero", "GPU-physical-one"])
            manifest = json.loads((output_dir / "launch.json").read_text())
            self.assertTrue(manifest["resource_policy"]["enforced"])
            self.assertEqual([row["gpu"] for row in manifest["runs"]], [2, 0, 1])
            self.assertTrue(all(row["gpu_uuid"] != "GPU-evaluation-only" for row in manifest["runs"]))


if __name__ == "__main__":
    unittest.main()
