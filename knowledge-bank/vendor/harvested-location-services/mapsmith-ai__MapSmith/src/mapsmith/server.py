"""MapSmith MCP server.

Transports:
- stdio (default): ``mapsmith`` — zero infrastructure, for Claude Desktop & co.
- Streamable HTTP: set ``MAPSMITH_TRANSPORT=http`` (env: MAPSMITH_HOST,
  MAPSMITH_PORT). Stateless: any request can hit any replica.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import __version__, catalog, jobs, stacks, ui, workspace
from .engines import dispatch, duckdb_engine, vector
from .plans import Plan
from .provenance import read_provenance

_HTTP = os.environ.get("MAPSMITH_TRANSPORT", "stdio").lower() in {"http", "streamable-http"}
_HOST = os.environ.get("MAPSMITH_HOST", "127.0.0.1")


def _transport_security() -> TransportSecuritySettings:
    """Host/Origin validation for the HTTP transport, always on.

    The SDK enables DNS rebinding protection by itself only when the server
    binds to loopback; bind to 0.0.0.0 — as any container deployment does — and
    the middleware is constructed with protection *disabled* for backwards
    compatibility. Since this transport is stateless, one POST with a forged
    Host header would otherwise be enough for any web page the user visits to
    drive every tool. So we pass the settings explicitly and keep them on.

    MAPSMITH_ALLOWED_HOSTS / MAPSMITH_ALLOWED_ORIGINS (comma-separated) extend
    the allow-list for reverse-proxy setups; loopback and the bind host are
    always included.
    """

    def listed(name: str) -> list[str]:
        return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]

    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if _HOST not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        hosts.append(f"{_HOST}:*")
        origins += [f"http://{_HOST}:*", f"https://{_HOST}:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts + listed("MAPSMITH_ALLOWED_HOSTS"),
        allowed_origins=origins + listed("MAPSMITH_ALLOWED_ORIGINS"),
    )


mcp = FastMCP(
    "mapsmith",
    instructions=(
        "MapSmith is a deterministic geoprocessing toolbox. Geometry and numbers always "
        "come from tool executions, never from the model. Every output dataset has a "
        "lineage manifest (<output>.provenance.json) retrievable with get_provenance. "
        "Use list_operations to discover capabilities before improvising; if an operation "
        "is 'planned', say so instead of approximating it with the wrong tool. "
        "Datasets are file paths; GeoParquet is the fast path, GeoPackage also works."
    ),
    host=_HOST,
    port=int(os.environ.get("MAPSMITH_PORT", "8000")),
    stateless_http=_HTTP,
    json_response=_HTTP,
    transport_security=_transport_security() if _HTTP else None,
)


# Standard MCP tool annotations (readOnlyHint etc. — hints for clients, spec 2025-06-18).
# Writers are marked non-destructive: they only (re)write the declared output_path and are
# deterministic, so re-running with the same arguments reproduces the same dataset.
_READONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
_WRITER = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
# run_sql executes arbitrary SQL (COPY, DDL on attached DBs), so it keeps the honest default.
_SQL = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)


def _guard(**paths: str) -> None:
    """Path containment at the MCP boundary: tool arguments come from an LLM
    agent, so every path is untrusted (see workspace.py for the rules).

    And, when the call names an `output_path`, the two checks `run_operation`
    already made through the plan validator and the dedicated tools did not
    (issue #31): the output must not be one of the inputs, and its extension
    must be one the operation's writer can honour. Otherwise `zonal_statistics`
    with `output_path` equal to its weights raster replaced the raster with a
    directory of shapefiles and died before writing a manifest. The operation
    is the calling tool's name, which is its catalogue name.
    """
    import sys

    from .plans.registry import BINDINGS
    from .plans.validator import _canon, output_extension_refusal

    for arg, value in paths.items():
        workspace.guard(value, arg)
    output = paths.get("output_path")
    if not output:
        return
    for arg, value in paths.items():
        if arg != "output_path" and value and _canon(value) == _canon(output):
            raise ValueError(
                f"output_path '{output}' is the same file as {arg}: writing it would "
                "destroy an input before the result exists. Choose another output."
            )
    binding = BINDINGS.get(sys._getframe(1).f_code.co_name)
    refusal = output_extension_refusal(binding.output_kind if binding else None, output)
    if refusal:
        raise ValueError(refusal)


def _run(
    operation: str, params: dict[str, Any], fn, *args, chose: str | None = None
) -> dict[str, Any]:
    """Execute an engine call as a durable job (no-op ledger without DATABASE_URL).

    `chose` is the CATALOGUE operation that actually ran, when it differs from
    the tool that ran it. Only `run_operation` needs it, and it is the whole
    reason the parameter exists: it passed the literal string "run_operation",
    which is not a name in the catalogue, so every case logged through the
    by-name path recorded `chose: null` and could never be paired with the
    search that led to it. Forty-six operations of seventy-four are reachable
    only by name, so that was most of the log.
    """
    # Every writer passes through here, so one line covers the dedicated tools
    # and `run_operation` alike. Before the call rather than after: a run that
    # failed is still a choice the caller made, and a search that led to a
    # failure is a case worth keeping.
    from . import discovery_log

    discovery_log.record_run(chose or operation)
    with jobs.job(operation, params) as (job_id, res):
        result = fn(*args)
        res.update(result)
    result["job_id"] = job_id
    return result


@mcp.tool(annotations=_READONLY)
def describe_dataset(path: str) -> dict[str, Any]:
    """Inspect a dataset, vector or raster, before analysing it.

    Vector: CRS, geometry types, schema, extent, feature count. A MULTI-LAYER
    container (e.g. a GeoPackage holding several layers) is described per
    layer — name, feature count, geometry type, CRS — because operations
    refuse containers with no chosen layer: extract the layer you mean first
    (run_sql: SELECT * FROM ST_Read(path, layer='name') with an output_path).
    Raster (.tif): CRS, grid size, resolution, bands with dtype, nodata and
    masked statistics (nodata cells counted separately). Call this first on
    any dataset you have not inspected yet — most silent GIS errors start with
    wrong assumptions about CRS, units, nodata or which layer you are on.
    Raster inspection requires the [raster] extra.
    """
    _guard(path=path)
    from .engines import dispatch

    return dispatch.describe_routed(path)


@mcp.tool(annotations=_WRITER)
def buffer_layer(input_path: str, distance_meters: float, output_path: str) -> dict[str, Any]:
    """Buffer all features by a distance in meters.

    Geographic-CRS inputs are reprojected to an estimated UTM zone for the metric
    operation and back; the decision is recorded in the provenance manifest.
    A `warnings` key in the result flags a suspicious-but-valid outcome with a
    hint — e.g. a negative distance that eroded every geometry away.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "buffer_layer",
        {"input": input_path, "distance_meters": distance_meters, "output": output_path},
        vector.buffer,
        input_path,
        distance_meters,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def clip_layer(input_path: str, mask_path: str, output_path: str) -> dict[str, Any]:
    """Clip a layer to the area of a mask layer. CRS are aligned automatically.

    A `warnings` key in the result means the analysis ran but something is worth
    your attention (typically an empty result, or inputs whose extents do not
    overlap); each entry carries a hint. Inputs without a CRS are refused.
    """
    _guard(input_path=input_path, mask_path=mask_path, output_path=output_path)
    return _run(
        "clip_layer",
        {"input": input_path, "mask": mask_path, "output": output_path},
        vector.clip,
        input_path,
        mask_path,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def overlay_layers(
    input_path: str, overlay_path: str, output_path: str, how: str = "intersection"
) -> dict[str, Any]:
    """Set-theoretic overlay of two layers: intersection (default), union,
    identity, symmetric_difference or difference.

    The overlay layer is reprojected to the input CRS when they differ; the
    decision is recorded in the provenance manifest. Overlay pieces of lower
    dimension than the inputs (shared edges, corner contacts) are dropped, and
    the manifest says so. Inputs without a CRS are refused; an empty result
    comes back with a `warnings` entry, never as a silent success.
    """
    _guard(input_path=input_path, overlay_path=overlay_path, output_path=output_path)
    return _run(
        "overlay_layers",
        {"input": input_path, "overlay": overlay_path, "output": output_path, "how": how},
        vector.overlay,
        input_path,
        overlay_path,
        output_path,
        how,
    )


@mcp.tool(annotations=_WRITER)
def dissolve_layer(
    input_path: str, output_path: str, by: str | None = None, aggfunc: str = "first"
) -> dict[str, Any]:
    """Merge features into one geometry per value of `by` (or one feature in all).

    aggfunc — first (default), last, sum, mean, median, min, max or count — is
    applied to the other columns and RECORDED in the manifest: a sum reported
    where a mean was meant is a plausible wrong number nobody can see. Features
    with a null `by` key are dropped by the grouping and the manifest counts
    them. The output feature count is verified against the number of distinct
    keys, so a wrong grouping fails loudly instead of shipping.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "dissolve_layer",
        {"input": input_path, "output": output_path, "by": by, "aggfunc": aggfunc},
        vector.dissolve,
        input_path,
        output_path,
        by,
        aggfunc,
    )


@mcp.tool(annotations=_WRITER)
def nearest_join(
    left_path: str,
    right_path: str,
    output_path: str,
    max_distance_meters: float | None = None,
    distance_column: str = "nearest_distance_m",
) -> dict[str, Any]:
    """Attach each feature's nearest neighbour from another layer, with the
    distance IN METERS in a named column.

    Geographic-CRS inputs are measured in an estimated UTM zone (decision
    recorded in the manifest) and returned in the input CRS — a nearest
    distance in degrees is the classic silent error of this operation, and it
    cannot happen here. max_distance_meters drops pairs farther than that; an
    emptied result comes back with a `warnings` entry, never silently.
    """
    _guard(left_path=left_path, right_path=right_path, output_path=output_path)
    return _run(
        "nearest_join",
        {
            "left": left_path,
            "right": right_path,
            "output": output_path,
            "max_distance_meters": max_distance_meters,
        },
        vector.nearest_join,
        left_path,
        right_path,
        output_path,
        max_distance_meters,
        distance_column,
    )


@mcp.tool(annotations=_WRITER)
def explode_layer(input_path: str, output_path: str) -> dict[str, Any]:
    """Split multi-part geometries into one feature per part (attributes copied).

    The output feature count is verified against the number of parts counted
    before the engine ran, so a lost part fails loudly instead of shipping.
    Inputs without a CRS are refused.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "explode_layer",
        {"input": input_path, "output": output_path},
        vector.explode,
        input_path,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def measure_area(
    input_path: str,
    output_path: str,
    method: str = "geodesic",
    area_column: str = "area_m2",
) -> dict[str, Any]:
    """Area per feature in SQUARE METRES, written to a named column, with the
    total in the result.

    method='geodesic' (default) measures ground area on the ellipsoid the
    layer's CRS names: no map plane, so no projection distortion. method=
    'planar' measures in the layer's own CRS and converts with its declared
    linear unit — a layer in US survey feet is not assumed to be in metres —
    and is refused on a geographic CRS, where an area would be in square
    degrees.

    Two things this tool does that a bare area call cannot: invalid geometry is
    repaired BEFORE measuring (the planar area of a self-intersecting ring is
    the signed shoelace, a number matching no region, returned without
    complaint) and every repair is recorded; and a planar measurement is
    compared against the ground area, so a plane that is not equal-area here
    comes back with a `warnings` entry carrying the ratio — Web Mercator at 42°
    reports 1.80× the land it covers.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "measure_area",
        {"input": input_path, "output": output_path, "method": method},
        vector.measure_area,
        input_path,
        output_path,
        method,
        area_column,
    )


@mcp.tool(annotations=_WRITER)
def merge_layers(input_paths: list[str], output_path: str) -> dict[str, Any]:
    """Append two or more layers into one (schema union, attributes aligned by name).

    Layers are reprojected to the FIRST layer's CRS when they differ; the decision
    is recorded in the provenance manifest. Columns present in only some inputs
    are null-filled in the others and the manifest names them — data that looks
    measured and is actually absent is a silent error. The output feature count
    is verified against the sum of the input counts. Inputs without a CRS are
    refused. This is an append, not a geometric union: use dissolve_layer to
    merge geometries afterwards.
    """
    for path in input_paths:
        workspace.guard(path, "input_paths")
    _guard(output_path=output_path)
    return _run(
        "merge_layers",
        {"inputs": list(input_paths), "output": output_path},
        vector.merge,
        input_paths,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def simplify_layer(
    input_path: str, tolerance_meters: float, output_path: str
) -> dict[str, Any]:
    """Simplify geometries (Douglas-Peucker, topology preserved) with the drift
    measured: the manifest records total area and length before and after.

    Geographic-CRS inputs are simplified in an estimated UTM zone (decision
    recorded) and returned in the input CRS — a tolerance in degrees is a
    different distance at every latitude. On projected CRS the tolerance is
    interpreted in the CRS units. The feature count is verified unchanged;
    vertex counts before/after are in the result. Inputs without a CRS are
    refused.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "simplify_layer",
        {
            "input": input_path,
            "tolerance_meters": tolerance_meters,
            "output": output_path,
        },
        vector.simplify,
        input_path,
        tolerance_meters,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def centroid_layer(input_path: str, output_path: str) -> dict[str, Any]:
    """One point per feature: the geometric centroid, computed in a metric CRS.

    Geographic-CRS inputs are measured in an estimated UTM zone (decision
    recorded in the manifest) and returned in the input CRS — a planar centroid
    of degree coordinates lands in the wrong place, quietly. The output is
    verified: same feature count, Point geometry, input CRS. Note the manifest's
    caveat: the centroid of a concave or multi-part feature can fall outside it.
    Inputs without a CRS are refused.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "centroid_layer",
        {"input": input_path, "output": output_path},
        vector.centroid,
        input_path,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def convert_format(input_path: str, output_path: str) -> dict[str, Any]:
    """Convert a vector dataset between formats; the target is chosen by the
    output extension (.parquet, .gpkg, .geojson).

    The output is re-read and verified: same feature count, same CRS. Two
    conversions are refused with the reason: shapefile (field names truncated to
    10 characters, silently) and GeoJSON for non-WGS84 layers (RFC 7946 is WGS84
    by definition — reproject first). Invalid geometry carried through is
    repaired deterministically and reported in a 'repairs' key.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "convert_format",
        {"input": input_path, "output": output_path},
        vector.convert,
        input_path,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def reproject_layer(input_path: str, target_crs: str, output_path: str) -> dict[str, Any]:
    """Reproject a layer to a target CRS, e.g. 'EPSG:32632' or a WKT string.

    Inputs without a CRS are refused. Geometry passes through unchanged, so an
    invalid input yields an invalid output: mechanically broken geometry is
    repaired deterministically and reported in a `repairs` key — read it, the
    geometry type may have changed.
    """
    _guard(input_path=input_path, output_path=output_path)
    return _run(
        "reproject_layer",
        {"input": input_path, "target_crs": target_crs, "output": output_path},
        vector.reproject,
        input_path,
        target_crs,
        output_path,
    )


@mcp.tool(annotations=_WRITER)
def spatial_join(
    left_path: str,
    right_path: str,
    output_path: str,
    predicate: str = "intersects",
    engine: str = "auto",
) -> dict[str, Any]:
    """Join by spatial predicate (intersects/within/contains).

    engine='auto' routes to the fastest available engine for the inputs:
    SedonaDB (heavy joins, 10-180x) > DuckDB (GeoParquet fast path) > GeoPandas.
    A `warnings` key in the result flags an empty join or inputs whose extents
    do not overlap, each with a hint. Inputs without a CRS are refused.
    """
    _guard(left_path=left_path, right_path=right_path, output_path=output_path)
    return _run(
        "spatial_join",
        {
            "left": left_path,
            "right": right_path,
            "output": output_path,
            "predicate": predicate,
            "engine": engine,
        },
        dispatch.spatial_join_routed,
        left_path,
        right_path,
        output_path,
        predicate,
        engine,
    )


@mcp.tool(annotations=_SQL)
def run_sql(query: str, output_path: str = "") -> dict[str, Any]:
    """Run spatial SQL (DuckDB dialect, ST_* functions, read_parquet/ST_Read for files).

    Without output_path: returns up to 50 preview rows. With output_path (.parquet):
    materializes the full result as GeoParquet with a provenance manifest.
    """
    out = output_path or None
    if out:
        _guard(output_path=out)
    return _run("run_sql", {"query": query, "output": out}, duckdb_engine.run_sql, query, out)


@mcp.tool(annotations=_WRITER)
def zonal_statistics(
    raster_path: str,
    zones_path: str,
    output_path: str,
    stats: list[str] | None = None,
    weights_path: str | None = None,
) -> dict[str, Any]:
    """Statistics of a raster within each vector zone (exact fractional pixel coverage).

    stats: subset of count/sum/mean/median/min/max/stdev/variance/majority/minority/
    variety (default: count, mean, min, max). Zones are aligned to the raster CRS
    automatically; the decision is recorded in the provenance manifest.
    weights_path: a single-band raster of weights on the SAME grid as the values
    (same CRS, cells and registration; otherwise refused with how to align it),
    for weighted_mean/weighted_sum/weighted_stdev/weighted_variance/weighted_frac --
    e.g. mean heat per zone weighted by population (default stats then: count,
    mean, weighted_mean). A cell with a value and no weight counts with weight 0,
    and the record names the zones where that happened.
    Zones without a CRS are refused; `warnings` and `repairs` keys in the result
    flag a suspicious outcome or geometry MapSmith had to repair.
    Requires the [raster] extra.
    """
    _guard(
        raster_path=raster_path, zones_path=zones_path, output_path=output_path,
        **({"weights_path": weights_path} if weights_path else {}),
    )
    from .engines import raster

    return _run(
        "zonal_statistics",
        {
            "raster": raster_path, "zones": zones_path, "output": output_path,
            "stats": stats, "weights": weights_path,
        },
        raster.zonal_statistics,
        raster_path,
        zones_path,
        output_path,
        stats,
        weights_path,
    )


@mcp.tool(annotations=_WRITER)
def hillshade(
    dem_path: str,
    output_path: str,
    azimuth: float = 315.0,
    altitude: float = 30.0,
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Shaded relief from a DEM: GeoTIFF in, GeoTIFF out (values scaled 0-32767).

    azimuth = sun direction in degrees (default 315, NW); altitude = sun angle
    above the horizon (default 30). DEMs without a CRS are rejected.
    Requires the [whitebox] extra.
    """
    _guard(dem_path=dem_path, output_path=output_path)
    from .engines import whitebox_engine

    return _run(
        "hillshade",
        {"dem": dem_path, "output": output_path, "azimuth": azimuth, "altitude": altitude},
        whitebox_engine.hillshade,
        dem_path,
        output_path,
        azimuth,
        altitude,
        z_factor,
    )


@mcp.tool(annotations=_WRITER)
def slope(
    dem_path: str,
    output_path: str,
    units: str = "degrees",
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Slope gradient from a DEM: GeoTIFF in, GeoTIFF out.

    units: degrees (default), percent or radians. DEMs in a geographic CRS are
    refused — degree cells with meter elevations give plausible but wrong values
    everywhere; reproject to a projected CRS first. The CRS decision is recorded
    in the provenance manifest. Requires the [whitebox] extra.
    """
    _guard(dem_path=dem_path, output_path=output_path)
    from .engines import whitebox_engine

    return _run(
        "slope",
        {"dem": dem_path, "output": output_path, "units": units},
        whitebox_engine.slope,
        dem_path,
        output_path,
        units,
        z_factor,
    )


@mcp.tool(annotations=_WRITER)
def aspect(
    dem_path: str,
    output_path: str,
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Aspect from a DEM: downslope azimuth in degrees, 0 = north. GeoTIFF in/out.

    FLAT CELLS ARE -1, not nodata — mask them before averaging aspect over an
    area, or the average is plausibly wrong. DEMs in a geographic CRS are
    refused (see slope): reproject to a projected CRS first.
    Requires the [whitebox] extra.
    """
    _guard(dem_path=dem_path, output_path=output_path)
    from .engines import whitebox_engine

    return _run(
        "aspect",
        {"dem": dem_path, "output": output_path},
        whitebox_engine.aspect,
        dem_path,
        output_path,
        z_factor,
    )


@mcp.tool(annotations=_WRITER)
def flow_accumulation(
    dem_path: str,
    output_path: str,
    out_type: str = "cells",
    log_transform: bool = False,
) -> dict[str, Any]:
    """D8 flow accumulation from a DEM (GeoTIFF in/out). Depressions are filled first.

    out_type: 'cells' (upslope cell count, includes the cell itself) or 'sca'
    (specific catchment area). log_transform=True for visualization-friendly
    values. Requires the [whitebox] extra.
    """
    _guard(dem_path=dem_path, output_path=output_path)
    from .engines import whitebox_engine

    return _run(
        "flow_accumulation",
        {"dem": dem_path, "output": output_path, "out_type": out_type},
        whitebox_engine.flow_accumulation,
        dem_path,
        output_path,
        out_type,
        log_transform,
    )


@mcp.tool(annotations=_WRITER)
def watershed(dem_path: str, pour_points_path: str, output_path: str) -> dict[str, Any]:
    """Watershed of each pour point: DEM + points in, basin raster out (GeoTIFF).

    Basins get 1-based IDs following the pour-point feature order; cells not
    draining to any point stay nodata. Points are aligned to the DEM CRS
    automatically (decision recorded). Requires the [whitebox] extra.
    """
    _guard(dem_path=dem_path, pour_points_path=pour_points_path, output_path=output_path)
    from .engines import whitebox_engine

    return _run(
        "watershed",
        {"dem": dem_path, "pour_points": pour_points_path, "output": output_path},
        whitebox_engine.watershed,
        dem_path,
        pour_points_path,
        output_path,
    )


@mcp.tool(annotations=_READONLY)
def validate_plan(plan: Plan) -> dict[str, Any]:
    """Statically validate a multi-step geoprocessing plan BEFORE running anything.

    Write the plan as steps in execution order; each step has a unique id, an
    operation name from list_operations, and its arguments. Use "$step_id" as an
    argument value to consume the output dataset of an earlier step. Checks:
    operations exist and are installed, arguments complete and well-typed,
    references resolve backwards (mis-ordered steps are rejected), input files
    exist, outputs don't collide, and CRS flow is simulated end-to-end from the
    real input files. Returns machine-actionable errors/warnings/notes plus the
    simulated output CRS per step. Nothing is executed and nothing is written.

    Example plan: {"goal": "wells at risk", "steps": [
      {"id": "buf", "operation": "buffer_layer", "arguments":
        {"input_path": "wells.gpkg", "distance_meters": 300, "output_path": "buf.parquet"}},
      {"id": "cut", "operation": "clip_layer", "arguments":
        {"input_path": "$buf", "mask_path": "zone.gpkg", "output_path": "risk.parquet"}}]}
    """
    from .plans import validate

    return validate(plan).model_dump()


@mcp.tool(annotations=_WRITER)
def execute_plan(plan: Plan) -> dict[str, Any]:
    """Validate, then execute a geoprocessing plan step by step.

    The plan is re-validated first (an invalid plan runs nothing). Steps run in
    order; "$step_id" references resolve to the outputs of earlier steps. Every
    step writes its own provenance manifest, and a plan-level manifest
    (<last output>.plan.json, with the plan sha256 and per-step outcomes) ties
    them together. Execution stops at the first failing step; outputs already
    produced stay on disk with their manifests. Same plan format as
    validate_plan — validate first, then execute.

    A `step_warnings` key in the response means the plan ran but some step
    produced a suspicious result (an empty output, non-overlapping inputs):
    read it before treating a completed plan as a correct one.
    """
    from .plans import execute

    return _run(
        "execute_plan",
        {"goal": plan.goal, "n_steps": len(plan.steps), "plan_sha256": plan.sha256()},
        execute,
        plan,
    )


@mcp.tool(annotations=_READONLY)
def get_provenance(output_path: str) -> dict[str, Any]:
    """Return the manifest of the ONE operation that wrote this dataset.

    Its inputs with their digests, the exact parameters, the CRS decisions with
    reasons, engine and version, and every deterministic check with its result.
    One step, in full. For the whole chain that led here — the operations
    behind the inputs, and the ones behind those — the catalogue operation
    `get_lineage` walks it and returns each step summarised instead of one step
    complete; run it through `run_operation`. It is not a tool of its own on
    purpose: two exposed tools answering the same question about the same file
    is the overlap that makes an agent pick wrong.
    """
    _guard(output_path=output_path)
    return read_provenance(output_path)



@mcp.resource(
    ui.MAP_UI_URI,
    name="map-panel",
    description="Interactive in-chat map panel (MCP Apps): renders preview_map results",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "prefersBorder": True,
            # OSM basemap tiles are a progressive enhancement: the panel probes
            # one tile and falls back to a plain background if the host blocks it.
            "csp": {
                "connectDomains": ["https://tile.openstreetmap.org"],
                "resourceDomains": ["https://tile.openstreetmap.org"],
            },
        }
    },
)
def map_panel() -> str:
    return ui.MAP_HTML


@mcp.tool(
    annotations=_READONLY,
    meta={
        "ui": {"resourceUri": ui.MAP_UI_URI, "visibility": ["model", "app"]},
        "ui/resourceUri": ui.MAP_UI_URI,  # deprecated flat key, kept for pre-final hosts
    },
)
def preview_map(paths: list[str], max_features: int = 2000) -> dict[str, Any]:
    """Show datasets on the interactive in-chat map panel (MCP Apps).

    Pass the paths of one or more MapSmith outputs or source datasets (vector
    or GeoTIFF). Layers are previewed in EPSG:4326 with simplified geometry and
    capped feature counts sized to fit client limits; each layer card shows its
    provenance summary and verification status. Read-only: the datasets of
    record stay on disk. On clients without MCP Apps support the same payload
    is returned as structured data.
    """
    for i, p in enumerate(paths):
        _guard(**{f"paths[{i}]": p})
    from . import preview

    # a negative cap would invert the payload budget (features_floor goes
    # negative and .head(-1) means "all but one"), so clamp at the boundary
    max_features = max(1, min(int(max_features), preview.MAX_FEATURES))

    return preview.map_preview(paths, max_features=max_features)


@mcp.tool(annotations=_READONLY)
def list_operations(
    query: str = "",
    detail: bool = False,
    limit: int = 10,
    input_kind: str | None = None,
    produces: str | None = None,
    category: str | None = None,
    projected: bool | None = None,
    dataset_inputs: int | None = None,
    engine: str = "auto",
    geometry: str | list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find the operation you need. **Say what you have and what you want** — it matters more than the words you search with.

    Ranking alone does not scale, and this is measured rather than assumed. Over
    118 requests written by other models against this catalog, searching by words
    alone finds the right operation in the top 3 a quarter of the time. Declaring
    what you already know does not make the ranking better — it makes the ranking
    unnecessary, because few enough operations survive that you get all of them:

        facets you declare              candidates left   ranked@3   in the answer
        (none)                                       51        25%             25%
        input_kind                                   33        29%             43%
        input_kind + produces                        21        48%            100%

    That last column is not an accuracy figure. It is what happens when nothing is
    dropped: the right operation was in the answer for all 118 requests, by
    construction rather than by ranking.

    So fill these in whenever you know them, and you usually do:

    - **input_kind** — what you are holding: 'vector' (points, lines, polygons),
      'raster' (a grid, a GeoTIFF), 'dataset' (either), 'plan', or 'none'.
    - **produces** — what you want back: 'dataset:vector', 'dataset:raster',
      'answer' (a number, nothing written), 'description' (what something IS,
      rather than a computation over it), 'plan_result'.
    - **category** — the family, when you know it: vector, raster, terrain,
      hydrology, inspection, sql, network, planning, provenance, visualization,
      bridge. Unlike the others this one only ORDERS the results — a wrong guess
      about our families costs you positions, never the answer, so guessing is
      safe.
    - **projected** — pass False if your data is in a geographic CRS (degrees),
      and every operation that would refuse it disappears from the results.
    - **dataset_inputs** — how many datasets you are holding for this step: 1 if
      you have one layer, 2 if the operation combines two. This is the facet that
      makes a large catalog usable: on the current one it takes the surviving set
      from a median of 34 to 9, because "clip these parcels with that boundary"
      and "simplify these parcels" are different questions and you already know
      which one you have.
    - **geometry** — for a vector layer, what it holds: 'point', 'line' or
      'polygon' (describe_dataset tells you), or a list for a mixed layer.
      Operations that cannot take that geometry drop out; operations that take
      any geometry always stay, so declaring it never hides one that fits. With
      two layers, list the geometry of both (points and polygons to count
      points in polygons). Unsure? Leave it out.

    `query` is then plain words for what you are trying to do, and it breaks the
    tie inside what is left. Describe the PROBLEM rather than the operation:
    "the coastline has too many vertices and the browser dies" works as well as
    the name of the tool, and better when you do not know the name.

    **If the answer comes back as a single entry with `status: "choose"`, that is
    the normal case and it is asking you to pick.** It carries every operation
    that survived, in relevance order, each with the sentence saying what it is
    NOT for. The order is a hint and nothing else: our ranking puts the right
    operation in the top three 61% of the time, while a model reading the same
    candidates and choosing gets its first pick right 69% — and 70% is where the two
    model labellers who wrote the ground truth agree with EACH OTHER, so there is
    often no single right answer to rank toward. You have context no ranking has: which
    file is open, what ran a minute ago, what the person actually asked for. Use
    it. **And if two candidates would both be defensible, ask them** — that is a
    better move than picking one silently, and it is what a GIS analyst would do.

    A `order_is_weak` field means the two rankers shared nothing in their top
    three, which usually means the request does not match this catalog well: read
    the candidates instead of trusting the order, and say so if none of them fits.

    **If the answer comes back with `status: "unsure"`, the two ranking engines
    agreed on nothing and the set was too large to hand over** — usually the
    request was not understood rather than impossible. It carries both engines'
    guesses and a question; answering the question with the facets above is the
    fastest way through.

    **If the answer comes back with `status: "none_apply"`, nothing you declared
    can be true at once** — no ranking ran. It lists each declaration and how many
    operations would come back without it, smallest first, so the one that is
    excluding everything is the first line. The common case is `produces`: several
    operations compute the number you want and write it into a column instead of
    returning it, so they declare `dataset:vector`. If nothing in `relax` helps,
    MapSmith probably does not do this — say so rather than running a neighbour.

    `detail=True` adds parameters and worked example calls: use it on the exact
    operation name before calling an unfamiliar tool. An empty `query` lists
    everything that survives the facets, planned operations included.

    `engine` selects the ranker and every result says which one ran: 'auto' (the
    default) prefers embeddings and falls back to BM25 where the model cannot
    load; 'lexical' is BM25 alone, deterministic and network-free; 'vector'
    forces embeddings. The default changed on measurement, not preference, and
    the facets above matter far more than this choice.
    """
    answer = catalog.search(
        query,
        limit=limit,
        detail=detail,
        produces=produces,
        category=category,
        input_kind=input_kind,
        projected=projected,
        dataset_inputs=dataset_inputs,
        engine=engine,
        geometry=geometry,
    )
    # Off unless MAPSMITH_DISCOVERY_LOG names a file. What it records is the
    # pairing between this search and whatever gets run next — the best labels
    # available, because they come from a caller with the context we lack. It
    # does not feed a model: see `discovery_log` for why that would be the wrong
    # shape of learning for this product.
    from . import discovery_log

    shape = (
        answer[0]["status"]
        if len(answer) == 1 and answer[0].get("status") in ("choose", "unsure")
        else "ranked"
    )
    # `unsure` hands over no candidates but does put two suggestion lists in
    # front of the caller, and something run right after one of those is the
    # most valuable row this log can hold: a query the ranker could not place,
    # next to the answer somebody picked anyway.
    if shape == "unsure":
        delivered = list(
            dict.fromkeys(answer[0]["lexical_suggests"] + answer[0]["vector_suggests"])
        )
    else:
        delivered = [entry["name"] for entry in catalog.entries(answer)]
    discovery_log.record_search(
        query,
        {
            "input_kind": input_kind,
            "produces": produces,
            "category": category,
            "projected": projected,
            "dataset_inputs": dataset_inputs,
        },
        answer[0].get("engine") if answer else None,
        delivered,
        shape,
    )
    return answer


@mcp.tool(annotations=_WRITER)
def run_operation(operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Run ANY catalog operation by name, including the ones with no tool of
    their own — which is most of them, and increasingly so.

    The tools above are the handful an agent reaches for constantly. The
    catalog holds every operation MapSmith can perform, and it grows faster
    than the tool list on purpose: tool-selection accuracy degrades past a few
    dozen exposed tools, while capability count has no such ceiling. Discover
    with list_operations (use detail=true to get parameters and worked
    examples), then call it here.

    Arguments are validated against the catalog BEFORE anything runs —
    unknown operation, missing or misnamed argument, wrong type, path outside
    the workspace — and the errors come back with stable codes, so a failed
    call tells the planner what to fix instead of what went wrong. Execution
    goes through the same path as execute_plan, so an operation cannot behave
    one way here and another way in a plan.
    """
    from .plans import executor
    from .plans.models import Plan, PlanStep

    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object of argument name -> value")
    plan = Plan(
        goal=f"single operation: {operation}",
        steps=[PlanStep(id="step", operation=operation, arguments=arguments)],
    )
    # Through the ledger like every other writer. It was not, and the gap was
    # exactly the wrong shape: operations reachable only by name are already most
    # of the catalog and increasingly so, so the audit trail of a product that
    # sells audit trails was thinning with every operation added. Validation
    # failures stay outside it — nothing ran, so there is no job to record.
    result = _run("run_operation", {"operation": operation, "arguments": arguments},
                  executor.execute, plan, chose=operation)
    if not result.get("executed") and "validation" in result:
        # The plan wrapper is an implementation detail; the caller asked for one
        # operation and gets one operation's diagnosis back.
        return {
            "ran": False,
            "operation": operation,
            "reason": result["reason"],
            "errors": [
                {"code": issue["code"], "message": issue["message"]}
                for issue in result["validation"]["errors"]
            ],
        }
    step = result["steps"][0] if result.get("steps") else {}
    flat = {key: value for key, value in step.items() if key not in ("id", "operation")}
    # The job id travels with the answer: a ledger entry nobody can name is an
    # audit trail only in principle.
    return {
        "ran": result.get("executed", False),
        "operation": operation,
        **flat,
        **({"job_id": result["job_id"]} if result.get("job_id") else {}),
    }


@mcp.tool(annotations=_READONLY)
def server_info() -> dict[str, Any]:
    """MapSmith version, licensing, and available engines."""
    ws = workspace.root()
    return {
        "name": "mapsmith",
        "version": __version__,
        "license": "AGPL-3.0-or-later",
        "homepage": "https://github.com/mapsmith-ai/MapSmith",
        "engines": dispatch.available_engines(),
        # Which geoprocessing stack this session is using, said at the START.
        # A caller who asked for a stack this machine does not have should find
        # out before planning five steps around it, not at the first failure
        # (D-056).
        "stack": stacks.describe(),
        # agents plan file paths: tell them the jail root instead of letting
        # them discover it through a failed call
        "workspace": str(ws) if ws else None,
    }


def main() -> None:
    mcp.run(transport="streamable-http" if _HTTP else "stdio")


if __name__ == "__main__":
    main()
