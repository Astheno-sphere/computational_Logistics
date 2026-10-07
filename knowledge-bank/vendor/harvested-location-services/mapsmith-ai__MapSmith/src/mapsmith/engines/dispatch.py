"""Engine dispatcher: route each workload class to the fastest available engine.

The 2025-2026 published engine benchmarks are unambiguous (upstream figures,
not ours — MapSmith's own measurements live in docs/benchmarks.md):
- SedonaDB wins heavy joins/KNN by 10-180x, in-process, optional dependency.
- DuckDB spatial wins filters/aggregations/point-in-polygon (~2M rows/sec).
- GeoPandas/Shapely stays as the long-tail lane (<~1M features).

Engines are optional imports: the dispatcher degrades gracefully and the
provenance manifest always records which engine actually ran.
"""

from __future__ import annotations

from enum import Enum
from functools import cache


class Workload(str, Enum):
    SQL = "sql"                # filters, aggregations, ad-hoc SQL
    HEAVY_JOIN = "heavy_join"  # polygon overlay, distance joins, KNN
    SMALL_VECTOR = "small_vector"  # long-tail ops on small data
    # Grids. None of the three vector engines applies, and saying so is the
    # point: without this value a raster operation would have to be filed under
    # one of the others, and a router reading the catalog would eventually send
    # a GeoTIFF to DuckDB. Every catalog entry declares its workload (D-041),
    # so the enum has to be able to describe every entry.
    RASTER = "raster"


# Preference order per workload class; first available wins. RASTER has none:
# its engines (rasterio, exactextract, Whitebox) are chosen by the operation,
# not by data size, and pretending otherwise would invite a routing decision
# that has no basis.
_PREFERENCES: dict[Workload, list[str]] = {
    Workload.SQL: ["duckdb", "geopandas"],
    Workload.HEAVY_JOIN: ["sedonadb", "duckdb", "geopandas"],
    Workload.SMALL_VECTOR: ["geopandas"],
    Workload.RASTER: [],
}


@cache
def available_engines() -> dict[str, bool]:
    """Probe optional engines once per process."""
    status: dict[str, bool] = {"geopandas": True}  # hard dependency
    try:
        import duckdb  # noqa: F401

        status["duckdb"] = True
    except ImportError:
        status["duckdb"] = False
    try:
        import sedona.db  # noqa: F401

        status["sedonadb"] = True
    except ImportError:
        status["sedonadb"] = False
    try:
        import exactextract  # noqa: F401
        import rasterio

        status["exactextract"] = bool(rasterio)
    except ImportError:
        status["exactextract"] = False
    # rasterio on its own, which is a different capability from exactextract and
    # the one most raster operations actually need. It was missing, and seven
    # bindings declared `engine_flag="raster"`: `available_engines().get("raster")`
    # returned None, so the plan validator told a caller with rasterio installed
    # to `pip install mapsmith[raster]` and refused the step. The message was
    # right by accident — EXTRA_FOR_FLAG falls back to the flag name — which is
    # probably why nobody noticed.
    try:
        import rasterio

        status["raster"] = bool(rasterio)
    except ImportError:
        status["raster"] = False
    try:
        import whitebox_workflows  # noqa: F401

        status["whitebox"] = True
    except ImportError:
        status["whitebox"] = False
    return status


def pick(workload: Workload, requested: str = "auto") -> str:
    """Pick the engine for a workload. `requested` may force a specific engine."""
    engines = available_engines()
    if requested != "auto":
        if not engines.get(requested, False):
            raise RuntimeError(
                f"Engine '{requested}' is not available in this installation. "
                f"Available: {[k for k, v in engines.items() if v]}"
            )
        return requested
    for name in _PREFERENCES[workload]:
        if engines.get(name, False):
            return name
    raise RuntimeError(f"No engine available for workload {workload}")


# Extensions that are rasters and nothing else. Formats that can hold either
# kind (GeoPackage can, in principle) go down the vector path first and fall
# through on failure.
_RASTER_SUFFIXES = {".tif", ".tiff"}


def describe_routed(path: str) -> dict:
    """Describe a dataset, vector or raster, from one entry point.

    Used by both the MCP tool and the plan executor. Known raster extensions
    go straight to the raster reader; everything else tries the vector reader
    first and falls back to rasterio, re-raising the ORIGINAL vector error if
    both fail — an error about the format the caller most likely meant.
    """
    from pathlib import Path

    if Path(path).suffix.lower() in _RASTER_SUFFIXES:
        from . import raster

        return raster.describe(path)
    try:
        from . import vector

        return vector.describe(path)
    except Exception as vector_error:  # noqa: BLE001 — any reader failure means: try the other family
        try:
            from . import raster

            result = raster.describe(path)
        except Exception:  # noqa: BLE001 — not a raster either: the vector error is the real one
            raise vector_error from None
        return result


def spatial_join_routed(
    left_path: str,
    right_path: str,
    output_path: str,
    predicate: str = "intersects",
    engine: str = "auto",
) -> dict:
    """Run a spatial join on the fastest available engine (single routing source).

    Used by both the MCP tool and the plan executor so routing policy cannot
    drift between the two entry points. The fast engines (SedonaDB, DuckDB)
    require both inputs in the same CRS: with engine='auto' mismatched or
    unknown CRS falls back to the GeoPandas path, which aligns the right layer
    and records the decision; an explicitly requested fast engine raises a
    helpful error instead of failing mid-query.
    """
    from .. import verify
    from . import duckdb_engine, vector

    chosen = pick(Workload.HEAVY_JOIN, engine)
    if chosen == "duckdb" and not duckdb_engine.supports_inputs(left_path, right_path):
        chosen = "geopandas"  # the DuckDB fast path is GeoParquet-only
    if chosen in ("sedonadb", "duckdb"):
        left_crs = verify.probe_crs(left_path)
        right_crs = verify.probe_crs(right_path)
        if left_crs == verify.UNKNOWN_CRS or left_crs != right_crs:
            if engine != "auto":
                raise ValueError(
                    f"engine '{chosen}' requires both inputs in the same CRS "
                    f"(got {left_crs} vs {right_crs}). Reproject first, or use "
                    "engine='auto' for the aligning GeoPandas path."
                )
            chosen = "geopandas"
    if chosen in ("sedonadb", "duckdb"):
        # The GeoPandas path refuses a ring drawn across 180; the fast engines
        # are planar too and read it the same wrong way, so the refusal has to
        # happen here, before the engine is chosen. Found by the 0.6.0
        # pre-release review: GeoParquet inputs in one CRS went to DuckDB and
        # came back `verified: True` with the feature on the far side of the
        # world. Only layers in degrees can carry the defect, so projected
        # inputs keep the fast path without reading a geometry.
        _refuse_naive_antimeridian_at(left_path, left_crs)
        _refuse_naive_antimeridian_at(right_path, right_crs)
    if chosen == "sedonadb":
        from . import sedona_engine

        fn = sedona_engine.spatial_join
    elif chosen == "duckdb":
        fn = duckdb_engine.spatial_join
    else:
        fn = vector.spatial_join
    result = fn(left_path, right_path, output_path, predicate)
    result["engine_used"] = chosen
    return result


def _refuse_naive_antimeridian_at(path: str, crs_label: str) -> None:
    from pyproj import CRS

    from .. import antimeridian
    from . import vector

    try:
        in_degrees = antimeridian._is_in_degrees(CRS.from_user_input(crs_label))
    except Exception:  # noqa: BLE001 - an unreadable label is not a CRS in degrees
        in_degrees = False
    if in_degrees:
        vector._refuse_naive_antimeridian(vector._read(path), path)
