"""Shared test fixtures.

Each test runs with a clean global config and a disabled result cache so that
cached responses never leak between tests. The file-I/O sandbox root is pointed
at the system temp dir so existing path-based tests keep working; dedicated
traversal tests live in ``test_security.py``.
"""

import tempfile

import pytest

from locusync import cache as cache_mod
from locusync.config import Config, set_config


@pytest.fixture(autouse=True)
def isolate_global_state():
    """Reset config + cache around every test."""
    cfg = Config()
    cfg.workdir = tempfile.gettempdir()
    cfg.temp_dir = tempfile.gettempdir()
    cfg.cache.enabled = False  # opt-in per-test via reset + Config()
    set_config(cfg)
    cache_mod.reset_cache()
    yield
    cache_mod.reset_cache()
    set_config(Config())
