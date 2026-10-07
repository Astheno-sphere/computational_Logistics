import os
import stat
import tempfile
import time

import pytest

from conftest import GIT_ENV, make_repo

import gitutil

posix_only = pytest.mark.skipif(not hasattr(os, "getuid"), reason="needs a uid")


@pytest.fixture
def tmproot(tmp_path, monkeypatch):
    """A temp dir of our own, so nothing here reads or sweeps the real one."""
    d = tmp_path / "tmproot"
    d.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    for k, v in GIT_ENV.items():
        monkeypatch.setenv(k, v)
    return d


def _leftovers(root):
    return sorted(
        os.path.join(dirpath, f)
        for dirpath, _, files in os.walk(root) for f in files
    )


def _write(path):
    with open(path, "w") as f:
        f.write("x")
    return path


def _advance_clock(monkeypatch, seconds):
    """ctime cannot be set, so files are aged by moving the clock instead."""
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + seconds)


class TestTempIndex:
    @posix_only
    def test_copy_lives_in_private_dir_and_is_removed(self, tmp_path, tmproot):
        repo = make_repo(tmp_path / "repo")
        with gitutil._temp_index(str(repo), untracked_paths=[]) as env:
            idx = env["GIT_INDEX_FILE"]
            private = tmproot / f"claude-security-guidance-{os.getuid()}"
            assert os.path.dirname(idx) == str(private)
            assert stat.S_IMODE(os.lstat(private).st_mode) == 0o700
            assert os.path.isfile(idx)
        assert _leftovers(tmproot) == []

    def test_cleanup_removes_what_a_killed_git_leaves(self, tmp_path, tmproot):
        repo = make_repo(tmp_path / "repo")
        with gitutil._temp_index(str(repo), untracked_paths=[]) as env:
            for suffix in (".lock", ".stash.12345", ".stash.12345.lock"):
                _write(env["GIT_INDEX_FILE"] + suffix)
        assert _leftovers(tmproot) == []

    def test_cleanup_when_body_raises(self, tmp_path, tmproot):
        repo = make_repo(tmp_path / "repo")
        with pytest.raises(RuntimeError):
            with gitutil._temp_index(str(repo), untracked_paths=[]):
                raise RuntimeError("boom")
        assert _leftovers(tmproot) == []

    def test_live_copy_keeps_index_mtime_and_survives_a_sweep(self, tmp_path, tmproot):
        repo = make_repo(tmp_path / "repo")
        old = int(time.time()) - 7200
        os.utime(repo / ".git" / "index", (old, old))
        with gitutil._temp_index(str(repo), untracked_paths=[]) as env:
            assert int(os.stat(env["GIT_INDEX_FILE"]).st_mtime) == old
            gitutil._hook_tmpdir()
            assert os.path.isfile(env["GIT_INDEX_FILE"])


class TestSweep:
    @posix_only
    def test_reclaims_stale_files_in_both_dirs(self, tmproot, monkeypatch):
        private = gitutil._hook_tmpdir()
        stale = [
            _write(os.path.join(d, name))
            for d in (private, str(tmproot))
            for name in ("security_hook_idx_dead", "security_hook_idx_dead.lock")
        ]
        _advance_clock(monkeypatch, 3600)
        keep = [
            _write(os.path.join(private, "security_hook_idx_live")),
            _write(os.path.join(str(tmproot), "security_hook_idx_live")),
        ]
        for p in keep:
            os.utime(p, (time.time(), time.time()))
        keep.append(_write(os.path.join(str(tmproot), "unrelated")))
        gitutil._hook_tmpdir()
        assert [p for p in stale if os.path.exists(p)] == []
        assert [p for p in keep if not os.path.exists(p)] == []

    def test_backdated_mtime_alone_is_not_stale(self, tmproot):
        p = _write(str(tmproot / "security_hook_idx_copy2"))
        old = time.time() - 7200
        os.utime(p, (old, old))
        gitutil._hook_tmpdir()
        assert os.path.exists(p)

    @posix_only
    def test_only_our_own_regular_files(self, tmproot, monkeypatch):
        target = _write(str(tmproot / "target"))
        os.symlink(target, tmproot / "security_hook_idx_link")
        (tmproot / "security_hook_idx_dir").mkdir()
        mine = _write(str(tmproot / "security_hook_idx_mine"))
        _advance_clock(monkeypatch, 3600)
        gitutil._sweep_stale_indexes(str(tmproot), os.getuid() + 1)
        assert os.path.exists(mine)
        gitutil._sweep_stale_indexes(str(tmproot), os.getuid())
        assert not os.path.exists(mine)
        assert os.path.lexists(tmproot / "security_hook_idx_link")
        assert os.path.exists(target)
        assert (tmproot / "security_hook_idx_dir").is_dir()

    def test_large_backlog_is_drained_in_slices(self, tmproot, monkeypatch):
        for i in range(3):
            _write(str(tmproot / f"security_hook_idx_{i}"))
        _advance_clock(monkeypatch, 3600)
        monkeypatch.setattr(gitutil, "_SWEEP_BUDGET_S", -1)
        gitutil._sweep_stale_indexes(str(tmproot), None)
        assert len(_leftovers(tmproot)) == 2


class TestPrivateDir:
    @posix_only
    def test_refuses_symlink_or_file_at_the_predictable_path(self, tmp_path, tmproot):
        repo = make_repo(tmp_path / "repo")
        predictable = tmproot / f"claude-security-guidance-{os.getuid()}"
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, predictable)
        assert gitutil._hook_tmpdir() is None
        with gitutil._temp_index(str(repo), untracked_paths=[]) as env:
            assert os.path.dirname(env["GIT_INDEX_FILE"]) == str(tmproot)
        assert list(elsewhere.iterdir()) == []
        predictable.unlink()
        predictable.write_text("")
        assert gitutil._hook_tmpdir() is None

    @posix_only
    def test_refuses_a_directory_owned_by_someone_else(self, tmproot, monkeypatch):
        uid = os.getuid()
        (tmproot / f"claude-security-guidance-{uid + 1}").mkdir()
        monkeypatch.setattr(os, "getuid", lambda: uid + 1)
        assert gitutil._hook_tmpdir() is None

    def test_without_getuid_uses_and_sweeps_the_bare_temp_dir(
            self, tmp_path, tmproot, monkeypatch):
        repo = make_repo(tmp_path / "repo")
        monkeypatch.delattr(os, "getuid", raising=False)
        stale = _write(str(tmproot / "security_hook_idx_dead"))
        _advance_clock(monkeypatch, 3600)
        assert gitutil._hook_tmpdir() is None
        assert not os.path.exists(stale)
        with gitutil._temp_index(str(repo), untracked_paths=[]) as env:
            assert os.path.dirname(env["GIT_INDEX_FILE"]) == str(tmproot)
        assert _leftovers(tmproot) == []
