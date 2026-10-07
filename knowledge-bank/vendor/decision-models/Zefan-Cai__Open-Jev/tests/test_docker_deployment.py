"""Offline Docker build/entrypoint contracts; no Docker daemon or model downloads."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class DockerFetchTest(unittest.TestCase):
    def fetch(self, case):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "TestPackage/package"
            checkpoint = package / "checkpoint"
            checkpoint.mkdir(parents=True)
            config = {"model_id": "Qwen/Test", "revision": "a" * 40,
                      "max_length": 4096, "lora_rank": 8, "method": "test"}
            if case == "wrong_base":
                config["revision"] = "b" * 40
            metadata = checkpoint / "model.json"
            metadata.write_text(json.dumps(config))
            raw = metadata.read_bytes()
            manifest = {"files": {"checkpoint/model.json": {
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}}}
            if case == "empty_manifest":
                manifest["files"] = {}
            if case != "missing_manifest":
                (package / "manifest.json").write_text(json.dumps(manifest))
            if case == "tampered":
                metadata.write_bytes(raw + b" ")
            base = root / "hub/snapshot"
            base.mkdir(parents=True)
            for name in ("config.json", "tokenizer.json", "model.safetensors"):
                (base / name).write_text("{}")
            calls = []

            def snapshot_download(**kwargs):
                calls.append(kwargs["repo_id"])
                return str(base if kwargs["repo_id"] == "Qwen/Test" else package.parent)

            env = {"JEV_MODEL_ROOT": str(root), "JEV_BASE_MODEL": "Qwen/Test",
                   "JEV_BASE_REVISION": "a" * 40, "JEV_PACKAGE_REPO": "Test/TestPackage",
                   "JEV_PACKAGE_REVISION": "c" * 40}
            with patch.dict(os.environ, env, clear=True), \
                 patch.dict(sys.modules, {"huggingface_hub": SimpleNamespace(snapshot_download=snapshot_download)}), \
                 contextlib.redirect_stdout(io.StringIO()):
                if case == "valid":
                    runpy.run_path(str(ROOT / "docker/fetch_models.py"), run_name="__main__")
                    record = json.loads((root / "BUILD.json").read_text())
                    self.assertEqual(record["package_files_verified"], 1)
                    self.assertEqual(calls, ["Test/TestPackage", "Qwen/Test"])
                else:
                    with self.assertRaises(SystemExit) as caught:
                        runpy.run_path(str(ROOT / "docker/fetch_models.py"), run_name="__main__")
                    self.assertEqual(caught.exception.code, 1)
                    self.assertFalse((root / "BUILD.json").exists())
                    self.assertEqual(calls, ["Test/TestPackage"], "invalid packages must fail before base download")

    def test_valid_package_records_verified_files(self):
        self.fetch("valid")

    def test_wrong_base_revision_is_rejected(self):
        self.fetch("wrong_base")

    def test_tampered_package_is_rejected(self):
        self.fetch("tampered")

    def test_missing_manifest_is_rejected(self):
        self.fetch("missing_manifest")

    def test_empty_manifest_is_rejected(self):
        self.fetch("empty_manifest")


@unittest.skipUnless(shutil.which("sh"), "requires a POSIX shell")
class DockerEntrypointTest(unittest.TestCase):
    def test_defaults_cache_opt_in_and_command_override(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "Open-Jev-2B/package/checkpoint"
            checkpoint.mkdir(parents=True)
            (checkpoint / "model.json").write_text("{}")
            binary = root / "bin"
            binary.mkdir()
            fake_python = binary / "python"
            fake_python.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake_python.chmod(0o755)
            env = {"PATH": str(binary) + os.pathsep + os.environ["PATH"],
                   "JEV_MODEL_ROOT": str(root), "JEV_DEVICE": "cpu"}
            for cache, flag in (("off", "--no-prefix-cache"), ("on", "--prefix-cache")):
                with self.subTest(cache=cache):
                    result = subprocess.run([shutil.which("sh"), str(ROOT / "docker/entrypoint.sh"),
                                             "--batch-size", "8"],
                                            env={**env, "JEV_PREFIX_CACHE": cache},
                                            capture_output=True, text=True, check=True)
                    args = result.stdout.splitlines()
                    self.assertEqual(args[:2], ["-m", "jev.server"])
                    self.assertIn(str(checkpoint), args)
                    self.assertIn(flag, args)
                    self.assertEqual(args[-2:], ["--batch-size", "8"])
            result = subprocess.run([shutil.which("sh"), str(ROOT / "docker/entrypoint.sh"),
                                     "printf", "replacement"], env=env,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "replacement")


if __name__ == "__main__":
    unittest.main()
