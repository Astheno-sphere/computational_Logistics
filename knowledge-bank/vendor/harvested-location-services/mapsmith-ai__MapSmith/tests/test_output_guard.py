"""An output that is an input, or has an extension its writer cannot honour (issue #31).

`zonal_statistics` with `output_path` equal to its weights raster replaced the
raster with a directory of shapefiles -- a vector writer given `.tif` falls back
to the Shapefile driver -- and died before a manifest existed. `run_operation`
refused the collision through the plan validator and only warned about the
extension; the dedicated tools checked neither.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

import geopandas as gpd
from rasterio.transform import from_origin
from shapely.geometry import box

from mapsmith import server
from mapsmith.plans.registry import BINDINGS

ROOT = Path(__file__).resolve().parents[1]


def _raster(path: Path) -> str:
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:32631", transform=from_origin(0.0, 4.0, 1.0, 1.0),
    ) as dst:
        dst.write(np.ones((1, 4, 4), dtype="float32"))
    return str(path)


def _zones(path: Path) -> str:
    gpd.GeoDataFrame(geometry=[box(0, 0, 2, 2)], crs="EPSG:32631").to_file(path)
    return str(path)


def _digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def ws(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(tmp_path))
    return tmp_path


def test_an_output_that_is_the_weights_raster_is_refused_and_the_raster_survives(ws):
    values, weights = _raster(ws / "v.tif"), _raster(ws / "w.tif")
    zones = _zones(ws / "z.gpkg")
    before = _digest(weights)
    with pytest.raises(ValueError, match="same file as weights_path"):
        server.zonal_statistics(
            raster_path=values, zones_path=zones, output_path=weights,
            stats=["weighted_mean"], weights_path=weights,
        )
    assert Path(weights).is_file() and _digest(weights) == before


def test_an_output_that_is_the_value_raster_is_refused(ws):
    values, zones = _raster(ws / "v.tif"), _zones(ws / "z.gpkg")
    with pytest.raises(ValueError, match="same file as raster_path"):
        server.zonal_statistics(
            raster_path=values, zones_path=zones, output_path=values, stats=["mean"]
        )


def test_a_vector_output_with_a_raster_extension_is_refused_before_anything_is_written(ws):
    values, zones = _raster(ws / "v.tif"), _zones(ws / "z.gpkg")
    target = ws / "stats.tif"
    with pytest.raises(ValueError, match="extension '.tif'"):
        server.zonal_statistics(
            raster_path=values, zones_path=zones, output_path=str(target), stats=["mean"]
        )
    assert not target.exists(), "a directory of shapefiles was created before the refusal"


def test_a_raster_output_with_a_vector_extension_is_refused(ws):
    dem = _raster(ws / "dem.tif")
    pytest.importorskip("whitebox_workflows")
    with pytest.raises(ValueError, match="writes a raster"):
        server.slope(dem_path=dem, output_path=str(ws / "slope.parquet"))


def test_the_plan_validator_refuses_the_extension_rather_than_warning(ws):
    from mapsmith.plans import validator
    from mapsmith.plans.models import Plan

    values, zones = _raster(ws / "v.tif"), _zones(ws / "z.gpkg")
    plan = Plan.model_validate({
        "steps": [{
            "id": "z", "operation": "zonal_statistics",
            "arguments": {"raster_path": values, "zones_path": zones,
                          "output_path": str(ws / "stats.tif"), "stats": ["mean"]},
        }],
    })
    report = validator.validate(plan)
    assert "OUTPUT_EXTENSION_REFUSED" in [issue.code for issue in report.errors]


def test_every_dedicated_writer_tool_is_named_after_a_binding_that_says_what_it_writes():
    """`_guard` finds the operation by the calling tool's name. A tool renamed
    away from its catalogue name would skip the extension check in silence, so
    the list is derived from the source: every function in server.py that
    passes `output_path` to `_guard` must be a binding with an output kind."""
    tree = ast.parse((ROOT / "src" / "mapsmith" / "server.py").read_text(encoding="utf-8"))
    writers = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and getattr(call.func, "id", None) == "_guard"
                    and any(k.arg == "output_path" for k in call.keywords)
                ):
                    writers.add(node.name)
    assert len(writers) >= 15, f"only {len(writers)} writer tools found -- the scan is broken"
    unbound = sorted(w for w in writers if not (w in BINDINGS and BINDINGS[w].output_kind))
    # get_provenance READS: its `output_path` names a dataset already written, whose
    # manifest it returns, so there is no writer and no extension to check.
    assert set(unbound) <= {"get_provenance"}, unbound
