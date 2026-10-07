"""Tests for filesystem sandboxing (path traversal protection)."""

import json
import os

import pytest

from locusync.config import Config, set_config
from locusync.security import PathSecurityError, safe_path
from locusync.tools.files import read_geo_file, write_geo_file


@pytest.fixture
def sandbox(tmp_path):
    """Point the workspace root at an isolated tmp dir."""
    cfg = Config()
    cfg.workdir = str(tmp_path)
    set_config(cfg)
    return tmp_path


class TestSafePath:
    def test_relative_resolves_inside(self, sandbox):
        p = safe_path("sub/file.geojson")
        assert str(p).startswith(str(sandbox.resolve()))

    def test_traversal_blocked(self, sandbox):
        with pytest.raises(PathSecurityError):
            safe_path("../../../../etc/passwd")

    def test_absolute_outside_blocked(self, sandbox):
        with pytest.raises(PathSecurityError):
            safe_path("/etc/passwd")

    def test_absolute_inside_allowed(self, sandbox):
        target = sandbox / "ok.geojson"
        assert safe_path(str(target)) == target.resolve()

    def test_symlink_escape_blocked(self, sandbox):
        outside = sandbox.parent / "secret.txt"
        outside.write_text("secret")
        link = sandbox / "link.txt"
        os.symlink(outside, link)
        with pytest.raises(PathSecurityError):
            safe_path("link.txt", must_exist=True)

    def test_empty_path_rejected(self, sandbox):
        with pytest.raises(PathSecurityError):
            safe_path("")


class TestFileToolsSandbox:
    @pytest.mark.asyncio
    async def test_read_outside_blocked(self, sandbox):
        result = await read_geo_file("/etc/hosts")
        assert result["success"] is False
        assert "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_write_traversal_blocked(self, sandbox):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {},
                 "geometry": {"type": "Point", "coordinates": [0, 0]}}
            ],
        }
        result = await write_geo_file(fc, "../escape.geojson", driver="GeoJSON")
        assert result["success"] is False
        assert "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_write_then_read_inside(self, sandbox):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"n": 1},
                 "geometry": {"type": "Point", "coordinates": [2.35, 48.85]}}
            ],
        }
        w = await write_geo_file(fc, "out.geojson", driver="GeoJSON")
        assert w["success"] is True
        assert (sandbox / "out.geojson").exists()
        r = await read_geo_file("out.geojson")
        assert r["success"] is True
        assert r["data"]["feature_count"] == 1
        # sanity: file is valid GeoJSON
        json.loads((sandbox / "out.geojson").read_text())
