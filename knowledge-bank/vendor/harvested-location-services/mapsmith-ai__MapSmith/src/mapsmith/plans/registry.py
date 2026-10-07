"""Executable operation registry: binds catalog operations to engine functions.

The catalog (`mapsmith.catalog`) is the documentation layer; this module is the
runtime layer. A test enforces that the two stay in sync (every `available`
catalog operation has exactly one binding here), so agent-facing docs and
executable reality cannot drift apart.

Loaders import lazily: operations behind optional extras must not break import
of the plans package when the extra is absent — availability is a validation
outcome, not an ImportError.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Binding:
    """Runtime binding of one catalog operation."""

    loader: Callable[[], Callable[..., dict[str, Any]]]
    input_args: tuple[str, ...]  # path arguments read by the operation
    output_arg: str | None  # path argument the operation writes (None = no dataset)
    engine_flag: str | None  # key in dispatch.available_engines(), None = core
    crs_effect: tuple[str, str] | None  # ("same_as"|"target", arg) | ("unknown","") | None
    output_kind: str | None = None  # "vector" | "raster" | None
    #: Path arguments that arrive as a LIST of paths rather than one string.
    #:
    #: They need naming separately because the validator reads `input_args` and
    #: skips anything that is not a `str`, so a list of paths was invisible to it
    #: twice over. That is not a hypothetical: `merge_layers` declares
    #: `input_paths` and no `input_args`, so until 2026-08-29 `run_operation`
    #: and `execute_plan` would read a file from outside `MAPSMITH_WORKSPACE`
    #: and write it INSIDE, where the next `describe_dataset` hands it to the
    #: model — while the dedicated `merge_layers` tool refused the identical
    #: call. `test_every_path_parameter_is_covered_by_its_binding` is what stops
    #: this recurring: a hand-maintained enumeration of a growing set is wrong
    #: somewhere between one addition and the next, and only a mechanical check
    #: notices.
    list_input_args: tuple[str, ...] = ()


def _describe() -> Callable[..., dict[str, Any]]:
    from ..engines import dispatch

    return dispatch.describe_routed


def _buffer() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.buffer


def _clip() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.clip


def _overlay() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.overlay


def _dissolve() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.dissolve


def _nearest_join() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.nearest_join


def _explode() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.explode


def _measure_area() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.measure_area


def _merge() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.merge


def _simplify() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.simplify


def _centroid() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.centroid


def _convert() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.convert


def _select_features() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.select_features


def _extract_layer() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.extract_layer


def _reproject() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.reproject


def _spatial_join() -> Callable[..., dict[str, Any]]:
    from ..engines import dispatch

    return dispatch.spatial_join_routed


def _run_sql() -> Callable[..., dict[str, Any]]:
    from ..engines import duckdb_engine

    return duckdb_engine.run_sql



def _sample_raster_at_points() -> Callable[..., dict[str, Any]]:
    from ..engines import sampling

    return sampling.sample_raster_at_points


def _elevation_profile() -> Callable[..., dict[str, Any]]:
    from ..engines import sampling

    return sampling.elevation_profile


def _line_of_sight() -> Callable[..., dict[str, Any]]:
    from ..engines import sampling

    return sampling.line_of_sight


def _viewshed() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.viewshed


def _network_shortest_path() -> Callable[..., dict[str, Any]]:
    from ..engines import network

    return network.network_shortest_path


def _service_area() -> Callable[..., dict[str, Any]]:
    from ..engines import network

    return network.service_area


def _hot_spots() -> Callable[..., dict[str, Any]]:
    from ..engines import spatial_stats

    return spatial_stats.hot_spots


def _smooth_rates() -> Callable[..., dict[str, Any]]:
    from ..engines import spatial_stats

    return spatial_stats.smooth_rates


def _aggregate_to_threshold() -> Callable[..., dict[str, Any]]:
    from ..engines import spatial_stats

    return spatial_stats.aggregate_to_threshold


def _thin_points() -> Callable[..., dict[str, Any]]:
    from ..engines import spatial_stats

    return spatial_stats.thin_points


def _cluster_points_by_distance() -> Callable[..., dict[str, Any]]:
    from ..engines import spatial_stats

    return spatial_stats.cluster_points_by_distance


def _resample_raster() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.resample


def _clip_raster() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.clip_raster


def _reclassify_raster() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.reclassify


def _band_math() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.band_math


def _join_table() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.join_table


def _measure_length() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.measure_length


def _aggregate_weighted() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.aggregate_weighted


def _parse_coordinates() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.parse_coordinates


def _point_on_surface() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.point_on_surface


def _hull_layer() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.hull


def _validate_geometry() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.validate_geometry


def _count_in_polygons() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.count_in_polygons


def _summarize_points_in_polygons() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.summarize_points_in_polygons


def _focal_statistics() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.focal_statistics


def _extract_streams() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.extract_streams


def _zonal_statistics() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.zonal_statistics


def _hillshade() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.hillshade


def _slope() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.slope


def _aspect() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.aspect


def _flow_accumulation() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.flow_accumulation


def _watershed() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.watershed


def _reproject_raster() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.reproject_raster


def _extract_band() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.extract_band


def _band_statistics() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.band_statistics


def _curvature() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.curvature


def _flow_direction() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.flow_direction


def _euclidean_distance() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.euclidean_distance


def _idw_interpolation() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.idw_interpolation


def _voronoi_polygons() -> Callable[..., dict[str, Any]]:
    from ..engines import vector

    return vector.voronoi_polygons


def _locate_extreme_cell() -> Callable[..., dict[str, Any]]:
    from ..engines import raster

    return raster.locate_extreme_cell

def _summarize_field() -> Callable[..., dict[str, Any]]:
    from ..engines import summaries

    return summaries.summarize_field


def _spatial_autocorrelation() -> Callable[..., dict[str, Any]]:
    from ..engines import summaries

    return summaries.spatial_autocorrelation


def _nearest_neighbour_index() -> Callable[..., dict[str, Any]]:
    from ..engines import summaries

    return summaries.nearest_neighbour_index


def _compare_layers() -> Callable[..., dict[str, Any]]:
    from ..engines import summaries

    return summaries.compare_layers


def _snap_layer() -> Callable[..., dict[str, Any]]:
    from ..engines import linework

    return linework.snap_layer


def _points_along_lines() -> Callable[..., dict[str, Any]]:
    from ..engines import linework

    return linework.points_along_lines


def _line_intersections() -> Callable[..., dict[str, Any]]:
    from ..engines import linework

    return linework.line_intersections


def _transform_by_control_points() -> Callable[..., dict[str, Any]]:
    from ..engines import linework

    return linework.transform_by_control_points


def _contour_lines() -> Callable[..., dict[str, Any]]:
    from ..engines import whitebox_engine

    return whitebox_engine.contour_lines


def _least_cost_path() -> Callable[..., dict[str, Any]]:
    from ..engines import network

    return network.least_cost_path

def _describe_crs() -> Callable[..., dict[str, Any]]:
    from ..engines import geodesy

    return geodesy.describe_crs


def _geodetic_distance() -> Callable[..., dict[str, Any]]:
    from ..engines import geodesy

    return geodesy.geodetic_distance


def _get_provenance() -> Callable[..., dict[str, Any]]:
    from ..provenance import read_provenance

    return read_provenance


def _get_lineage() -> Callable[..., dict[str, Any]]:
    from ..lineage import lineage

    return lineage


BINDINGS: dict[str, Binding] = {
    "describe_dataset": Binding(_describe, ("path",), None, None, None),
    "buffer_layer": Binding(
        _buffer, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "clip_layer": Binding(
        _clip,
        ("input_path", "mask_path"),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "overlay_layers": Binding(
        _overlay,
        ("input_path", "overlay_path"),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "dissolve_layer": Binding(
        _dissolve, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "nearest_join": Binding(
        _nearest_join,
        ("left_path", "right_path"),
        "output_path",
        None,
        ("same_as", "left_path"),
        "vector",
    ),
    "explode_layer": Binding(
        _explode, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "measure_area": Binding(
        _measure_area, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    # merge_layers takes a LIST of input paths; static analysis tracks only
    # string path arguments, so its inputs are opaque here, like run_sql's.
    "sample_raster_at_points": Binding(
        _sample_raster_at_points,
        ("raster_path", "points_path"),
        "output_path",
        "raster",
        ("same_as", "raster_path"),
        "vector",
    ),
    "elevation_profile": Binding(
        _elevation_profile,
        ("raster_path", "line_path"),
        "output_path",
        "raster",
        # The line's: distances are measured there and the points are written
        # there. It said the raster's until 2026-09-25, hours after the operation
        # stopped writing in it, so a plan simulated the wrong CRS downstream.
        ("same_as", "line_path"),
        "vector",
    ),
    # Reads only: an answer, no dataset, so no manifest and nothing to place.
    "line_of_sight": Binding(_line_of_sight, ("raster_path",), None, "raster", None),
    "viewshed": Binding(
        _viewshed,
        ("dem_path", "stations_path"),
        "output_path",
        "whitebox",
        ("same_as", "dem_path"),
        "raster",
    ),
    "network_shortest_path": Binding(
        _network_shortest_path,
        ("network_path",),
        "output_path",
        None,
        ("same_as", "network_path"),
        "vector",
    ),
    "service_area": Binding(
        _service_area,
        ("network_path",),
        "output_path",
        None,
        ("same_as", "network_path"),
        "vector",
    ),
    "hot_spots": Binding(
        _hot_spots,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "smooth_rates": Binding(
        _smooth_rates,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "aggregate_to_threshold": Binding(
        _aggregate_to_threshold,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "thin_points": Binding(
        _thin_points,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "cluster_points_by_distance": Binding(
        _cluster_points_by_distance,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "merge_layers": Binding(
        _merge, (), "output_path", None, ("unknown", ""), "vector",
        list_input_args=("input_paths",),
    ),
    "simplify_layer": Binding(
        _simplify, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "centroid_layer": Binding(
        _centroid, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "convert_format": Binding(
        _convert, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "select_features": Binding(
        _select_features, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "extract_layer": Binding(
        _extract_layer, ("input_path",), "output_path", None, ("same_as", "input_path"), "vector"
    ),
    "reproject_layer": Binding(
        _reproject, ("input_path",), "output_path", None, ("target", "target_crs"), "vector"
    ),
    "spatial_join": Binding(
        _spatial_join,
        ("left_path", "right_path"),
        "output_path",
        None,
        ("same_as", "left_path"),
        "vector",
    ),
    # run_sql reads whatever the query names: inputs are opaque to static analysis.
    "run_sql": Binding(_run_sql, (), "output_path", None, ("unknown", ""), "vector"),
    "resample_raster": Binding(
        _resample_raster,
        ("input_path",),
        "output_path",
        "exactextract",
        ("same_as", "input_path"),
        "raster",
    ),
    "clip_raster": Binding(
        _clip_raster,
        ("raster_path", "mask_path"),
        "output_path",
        "exactextract",
        ("same_as", "raster_path"),
        "raster",
    ),
    "reclassify_raster": Binding(
        _reclassify_raster,
        ("input_path",),
        "output_path",
        "exactextract",
        ("same_as", "input_path"),
        "raster",
    ),
    "band_math": Binding(
        _band_math,
        ("input_path",),
        "output_path",
        "exactextract",
        ("same_as", "input_path"),
        "raster",
    ),
    "join_table": Binding(
        _join_table,
        ("input_path", "table_path"),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "measure_length": Binding(
        _measure_length,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "aggregate_weighted": Binding(
        _aggregate_weighted,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "parse_coordinates": Binding(
        _parse_coordinates,
        ("table_path",),
        "output_path",
        None,
        ("same_as", "output_path"),
        "vector",
    ),
    "point_on_surface": Binding(
        _point_on_surface,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "hull_layer": Binding(
        _hull_layer,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "validate_geometry": Binding(
        _validate_geometry,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "count_in_polygons": Binding(
        _count_in_polygons,
        ("points_path", "polygons_path"),
        "output_path",
        None,
        ("same_as", "polygons_path"),
        "vector",
    ),
    "summarize_points_in_polygons": Binding(
        _summarize_points_in_polygons,
        ("points_path", "polygons_path"),
        "output_path",
        None,
        ("same_as", "polygons_path"),
        "vector",
    ),
    "focal_statistics": Binding(
        _focal_statistics,
        ("input_path",),
        "output_path",
        "whitebox",
        ("same_as", "input_path"),
        "raster",
    ),
    "extract_streams": Binding(
        _extract_streams,
        ("flow_accumulation_path",),
        "output_path",
        "whitebox",
        ("same_as", "flow_accumulation_path"),
        "raster",
    ),
    "zonal_statistics": Binding(
        _zonal_statistics,
        ("raster_path", "zones_path", "weights_path"),
        "output_path",
        "exactextract",
        ("same_as", "zones_path"),
        "vector",
    ),
    "hillshade": Binding(
        _hillshade, ("dem_path",), "output_path", "whitebox", ("same_as", "dem_path"), "raster"
    ),
    "slope": Binding(
        _slope, ("dem_path",), "output_path", "whitebox", ("same_as", "dem_path"), "raster"
    ),
    "aspect": Binding(
        _aspect, ("dem_path",), "output_path", "whitebox", ("same_as", "dem_path"), "raster"
    ),
    "flow_accumulation": Binding(
        _flow_accumulation,
        ("dem_path",),
        "output_path",
        "whitebox",
        ("same_as", "dem_path"),
        "raster",
    ),
    "watershed": Binding(
        _watershed,
        ("dem_path", "pour_points_path"),
        "output_path",
        "whitebox",
        ("same_as", "dem_path"),
        "raster",
    ),
    "reproject_raster": Binding(
        _reproject_raster,
        ("input_path",),
        "output_path",
        "raster",
        ("target", "target_crs"),
        "raster",
    ),
    "extract_band": Binding(
        _extract_band,
        ("input_path",),
        "output_path",
        "raster",
        ("same_as", "input_path"),
        "raster",
    ),
    # Reads only: no output_arg, so no manifest and nothing to place in a workspace.
    "band_statistics": Binding(_band_statistics, ("input_path",), None, "raster", None),
    "curvature": Binding(
        _curvature, ("dem_path",), "output_path", "whitebox", ("same_as", "dem_path"), "raster"
    ),
    "flow_direction": Binding(
        _flow_direction,
        ("dem_path",),
        "output_path",
        "whitebox",
        ("same_as", "dem_path"),
        "raster",
    ),
    "euclidean_distance": Binding(
        _euclidean_distance,
        ("input_path",),
        "output_path",
        "whitebox",
        ("same_as", "input_path"),
        "raster",
    ),
    "idw_interpolation": Binding(
        _idw_interpolation,
        ("points_path",),
        "output_path",
        "whitebox",
        ("same_as", "points_path"),
        "raster",
    ),
    "voronoi_polygons": Binding(
        _voronoi_polygons,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    # Neither of these two touches a dataset: they answer a question about a CRS
    # or about two coordinates, so there are no path arguments at all.
    "describe_crs": Binding(_describe_crs, (), None, None, None),
    "geodetic_distance": Binding(_geodetic_distance, (), None, None, None),
    # Four operations that answer instead of writing. `output_arg` is None and
    # so is `crs_effect`: nothing is produced, so nothing carries a CRS, and a
    # plan step that tries to feed one of these into the next step is refused by
    # the validator rather than silently passing a number where a path goes.
    "locate_extreme_cell": Binding(
        _locate_extreme_cell, ("input_path",), None, "raster", None
    ),
    "summarize_field": Binding(_summarize_field, ("input_path",), None, None, None),
    "spatial_autocorrelation": Binding(
        _spatial_autocorrelation, ("input_path",), None, None, None
    ),
    "nearest_neighbour_index": Binding(
        _nearest_neighbour_index, ("input_path", "area_path"), None, None, None
    ),
    "compare_layers": Binding(
        _compare_layers, ("input_path", "other_path"), None, None, None
    ),
    "snap_layer": Binding(
        _snap_layer,
        ("input_path", "reference_path"),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "points_along_lines": Binding(
        _points_along_lines,
        ("input_path",),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    "line_intersections": Binding(
        _line_intersections,
        ("input_path", "other_path"),
        "output_path",
        None,
        ("same_as", "input_path"),
        "vector",
    ),
    # The one operation whose output CRS is neither an input's nor a named
    # target argument in the usual sense: the fit onto the control points IS the
    # georeferencing, so the declared CRS comes from `target_crs`.
    "transform_by_control_points": Binding(
        _transform_by_control_points,
        ("input_path", "control_path"),
        "output_path",
        None,
        ("target", "target_crs"),
        "vector",
    ),
    "contour_lines": Binding(
        _contour_lines,
        ("dem_path",),
        "output_path",
        "whitebox",
        ("same_as", "dem_path"),
        "vector",
    ),
    "least_cost_path": Binding(
        _least_cost_path,
        ("cost_path", "start_path", "end_path"),
        "output_path",
        # `rasterio`, not core: this reads a raster and rasterio lives in the
        # [raster] extra. Declared core, the validator called the plan runnable
        # and the operation then raised a bare ModuleNotFoundError on a plain
        # `pip install mapsmith` — where every other extra gives a sentence
        # naming what to install.
        "raster",
        ("same_as", "cost_path"),
        "vector",
    ),
    "get_provenance": Binding(_get_provenance, ("output_path",), None, None, None),
    "get_lineage": Binding(_get_lineage, ("output_path",), None, None, None),
}

# Python types accepted for each catalog parameter type declaration.
PARAM_TYPES: dict[str, tuple[type, ...]] = {
    "str": (str,),
    "float": (int, float),
    "int": (int,),
    "bool": (bool,),
    # `list` alone, because a tuple of types cannot express "a list OF strings".
    # The element type is not checked here and does not need to be: the wire
    # contract in `models.ArgValue` refuses a list containing anything but
    # strings before a Plan exists, and `Plan` is the only way into the
    # validator. `test_the_wire_contract_refuses_a_list_of_non_strings` pins
    # that, so the day the contract loosens this stops being someone else's
    # problem.
    "list[str]": (list,),
}
