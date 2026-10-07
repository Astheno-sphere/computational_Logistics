"""Tests for large-result offloading to the sandbox."""

import json

import pytest

from locusync.config import Config, set_config
from locusync.tools.files import _offload_large_features, merge_features


@pytest.fixture
def sandbox(tmp_path):
    cfg = Config()
    cfg.workdir = str(tmp_path)
    cfg.max_inline_features = 5
    set_config(cfg)
    return tmp_path


def _fc(n, start=0):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"id": i},
             "geometry": {"type": "Point", "coordinates": [float(i), 0.0]}}
            for i in range(start, start + n)
        ],
    }


class TestOffloadHelper:
    @pytest.mark.asyncio
    async def test_small_result_stays_inline(self, sandbox):
        data = {"features": _fc(3)["features"], "feature_count": 3}
        out = await _offload_large_features(data, "test")
        assert "output_file" not in out
        assert len(out["features"]) == 3

    @pytest.mark.asyncio
    async def test_large_result_offloaded(self, sandbox):
        data = {"features": _fc(12)["features"], "feature_count": 12}
        out = await _offload_large_features(data, "test")
        assert out["truncated"] is True
        assert out["total_features"] == 12
        assert len(out["features"]) == 10  # preview sample
        # File written into the sandbox results dir and valid GeoJSON.
        path = sandbox / "results"
        written = list(path.glob("test_*.geojson"))
        assert len(written) == 1
        fc = json.loads(written[0].read_text())
        assert len(fc["features"]) == 12


class TestMergeOffload:
    @pytest.mark.asyncio
    async def test_merge_offloads_large_output(self, sandbox):
        result = await merge_features([_fc(6, 0), _fc(6, 100)])
        assert result["success"] is True
        assert result["data"]["truncated"] is True
        assert result["data"]["total_features"] == 12
        assert result["data"]["output_file"].endswith(".geojson")
