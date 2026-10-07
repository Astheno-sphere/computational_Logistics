import builtins
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jev import train, train_distributed


@contextmanager
def working_directory(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


@unittest.skipUnless(shutil.which("git"), "requires Git for source-checkout provenance")
class TrainingProvenanceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.git_env = {key: value for key, value in os.environ.items()
                        if not key.startswith("GIT_")}
        environment = patch.dict(os.environ, self.git_env, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.source = self.make_repository("source")
        self.caller = self.make_repository("caller")
        self.source_file = self.source / "jev" / "train.py"
        self.source_commit = self.git(self.source, "rev-parse", "HEAD")
        self.caller_commit = self.git(self.caller, "rev-parse", "HEAD")
        self.assertNotEqual(self.source_commit, self.caller_commit)

    def git(self, root, *arguments):
        return subprocess.check_output(
            ["git", "-C", str(root), "-c", "user.name=Provenance Test",
             "-c", "user.email=provenance@example.invalid", "-c", "commit.gpgsign=false",
             "-c", "core.hooksPath=" + os.devnull, *arguments],
            env=self.git_env, text=True, stderr=subprocess.PIPE).strip()

    def make_repository(self, name):
        root = self.root / name
        (root / "jev").mkdir(parents=True)
        (root / "jev" / "train.py").write_text(f"# {name} fixture\n")
        self.git(root, "init", "--quiet")
        self.git(root, "add", "jev/train.py")
        self.git(root, "commit", "--quiet", "-m", name)
        return root

    def installed_source(self):
        source = self.caller / ".venv/lib/python3.12/site-packages/jev/train.py"
        source.parent.mkdir(parents=True)
        source.write_text("# installed-like package fixture\n")
        return source

    def test_caller_head_is_wrong_but_source_head_is_recorded(self):
        with working_directory(self.caller):
            old_result = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            self.assertEqual(old_result, self.caller_commit)
            self.assertNotEqual(old_result, self.source_commit)
            self.assertEqual(train.source_checkout_commit(self.source_file), self.source_commit)

    def test_source_head_is_recorded_outside_any_repository(self):
        caller = self.root / "not-a-repository"
        caller.mkdir()
        with working_directory(caller):
            old_result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True)
            self.assertNotEqual(old_result.returncode, 0)
            self.assertEqual(train.source_checkout_commit(self.source_file), self.source_commit)

    def test_dirty_source_checkout_remains_supported(self):
        self.source_file.write_text("# modified after commit\n")
        (self.source / "untracked.txt").write_text("untracked\n")
        self.assertTrue(self.git(self.source, "status", "--porcelain"))
        with working_directory(self.caller):
            self.assertEqual(train.source_checkout_commit(self.source_file), self.source_commit)

    def test_real_git_worktree_with_git_file_is_supported(self):
        worktree = self.root / "worktree"
        self.git(self.source, "worktree", "add", "--detach", str(worktree), "HEAD")
        self.assertTrue((worktree / ".git").is_file())
        with working_directory(self.caller):
            self.assertEqual(train.source_checkout_commit(worktree / "jev/train.py"), self.source_commit)

    def test_caller_git_environment_cannot_override_source_checkout(self):
        pollution = {"GIT_DIR": str(self.caller / ".git"),
                     "GIT_WORK_TREE": str(self.caller),
                     "GIT_COMMON_DIR": str(self.caller / ".git")}
        with working_directory(self.caller), patch.dict(os.environ, pollution):
            old_result = subprocess.check_output(
                ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
            self.assertEqual(old_result, self.caller_commit)
            self.assertEqual(train.source_checkout_commit(self.source_file), self.source_commit)
            for name, value in pollution.items():
                self.assertEqual(os.environ[name], value)

    def test_installed_package_cannot_inherit_ancestor_repository(self):
        source = self.installed_source()
        self.assertFalse((source.parent.parent / ".git").exists())
        self.assertEqual(self.git(source.parent, "rev-parse", "HEAD"), self.caller_commit)
        with working_directory(self.caller), self.assertRaisesRegex(RuntimeError, "source checkout") as error:
            train.source_checkout_commit(source)
        self.assertIn("pip install -e", str(error.exception))

    def test_invalid_git_marker_cannot_inherit_ancestor_repository(self):
        source = self.installed_source()
        marker = source.parent.parent / ".git"
        for kind in ("file", "directory"):
            with self.subTest(marker=kind):
                if kind == "file":
                    marker.write_text("not a valid gitfile\n")
                else:
                    marker.mkdir()
                with self.assertRaisesRegex(RuntimeError, "source checkout"):
                    train.source_checkout_commit(source)
                marker.unlink() if marker.is_file() else marker.rmdir()

    def test_both_trainers_reject_before_imports_or_argument_access(self):
        source = self.installed_source()
        output = self.root / "must-not-create-output"
        data = self.root / "must-not-read-data"
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.split(".")[0] in ("torch", "transformers", "peft") or name in ("model", "jev.model"):
                raise AssertionError("Model dependency imported before checkout validation: " + name)
            return original_import(name, *args, **kwargs)

        class UnreadArguments:
            def __init__(self):
                self.output = output
                self.data = data

            def __getattribute__(self, name):
                raise AssertionError("Training argument read before checkout validation: " + name)

        for module in (train, train_distributed):
            with self.subTest(trainer=module.__name__), working_directory(self.caller):
                installed = source.with_name(Path(module.__file__).name)
                installed.touch(exist_ok=True)
                with patch.object(module, "__file__", str(installed)), \
                        patch("builtins.__import__", side_effect=guarded_import), \
                        self.assertRaisesRegex(RuntimeError, "source checkout"):
                    module.run(UnreadArguments())
                self.assertFalse(output.exists())
                self.assertFalse(data.exists())

    def test_both_installed_cli_help_commands_work_without_model_imports(self):
        source = self.installed_source()
        package = source.parent
        for name in ("__init__.py", "train.py", "train_distributed.py"):
            shutil.copyfile(Path(train.__file__).with_name(name), package / name)
        script = """
import builtins
import runpy
import sys
original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name.split('.')[0] in ('torch', 'transformers', 'peft') or name in ('model', 'jev.model'):
        raise AssertionError('Unexpected model import: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import
sys.path.insert(0, sys.argv[1])
module = sys.argv[2]
sys.argv = [module, '--help']
runpy.run_module(module, run_name='__main__')
"""
        for module in ("jev.train", "jev.train_distributed"):
            with self.subTest(trainer=module):
                result = subprocess.run(
                    [sys.executable, "-S", "-c", script, str(package.parent), module],
                    cwd=self.caller, env=self.git_env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertIn("--model", result.stdout)


if __name__ == "__main__":
    unittest.main()
