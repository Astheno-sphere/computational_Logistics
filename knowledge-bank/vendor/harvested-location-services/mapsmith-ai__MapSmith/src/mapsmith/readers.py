"""The one place MapSmith opens a vector dataset.

Why it has to be one place. GeoParquet 2.0 moved geometry into Parquet's own
``GEOMETRY``/``GEOGRAPHY`` logical types and demoted the ``geo`` metadata key to
optional, so "open a vector file" grew a second branch. In 0.2.2 that branch was
added to two of the six read paths and not to the other four (#28): the same
file that ``describe_layer`` opened, ``preview_map`` refused, in the same
session. A capability that lives in one function cannot be half-applied; one
that is copied into six call sites cannot stay applied.

The other half of #28 was mixing up two different questions. *Resolving* a CRS
declaration answers "what coordinate system is this", and its failure must be
honest — ``None`` plus a reason. *Labelling* a CRS answers "what do we write in
the manifest", and it may compress. Feeding a label back in as if it were a CRS
made a file that states its CRS read as CRS-less, whenever the CRS had no EPSG
code and pyproj happened to name it ``unknown``. So resolution lives here and
returns pyproj objects; presentation lives in :func:`mapsmith.verify.crs_label`
and returns strings, and neither calls the other.
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import geopandas as gpd

if TYPE_CHECKING:
    from pyproj import CRS

# Where an unresolvable CRS declaration leaves its explanation, so the CRS
# precondition can say *why* a file with a visible `crs` field reads as CRS-less
# instead of just reporting "no CRS" and leaving the agent to guess.
CRS_REASON = "mapsmith_crs_reason"

NATIVE_GEO_TYPES = ("Geometry", "Geography")


def native_geometry_columns(path: str) -> list[tuple[str, str]]:
    """Every ``GEOMETRY``/``GEOGRAPHY`` column of a Parquet file, with its raw
    CRS declaration, in schema order. Empty when there are none."""
    import pyarrow.parquet as pq

    try:
        schema = pq.ParquetFile(path).schema
    except Exception:  # noqa: BLE001 — probing must never break the caller
        return []
    found = []
    for index in range(len(schema)):
        column = schema.column(index)
        try:
            described = json.loads(column.logical_type.to_json())
        except Exception:  # noqa: BLE001, S112 — a type with no JSON form is not geometry
            continue
        if described.get("Type") in NATIVE_GEO_TYPES:
            found.append((column.name, described.get("crs") or ""))
    return found


def native_geometry_column(path: str) -> tuple[str, str] | None:
    """Column name and raw CRS declaration of a Parquet file that stores geometry
    in Parquet's own ``GEOMETRY``/``GEOGRAPHY`` logical types, or None.

    That storage is what GeoParquet 2.0 requires, and such a file may carry no
    ``geo`` metadata key at all — the key is optional in 2.0. Files like this are
    already produced by DuckDB (``geoparquet_version 'NONE'`` or ``'BOTH'``) and
    by recent GDAL, so "a Parquet file with geometry in it" no longer implies a
    ``geo`` key, and reading one as CRS-less would refuse valid work for a wrong
    reason (#23).
    """
    found = native_geometry_columns(path)
    return found[0] if found else None


def native_crs(path: str, declaration: str) -> tuple[CRS | None, str | None]:
    """Resolve a native Parquet CRS declaration: ``(CRS, None)`` or ``(None, why)``.

    The Parquet geospatial spec allows several forms, and MapSmith has met four
    of them in the wild: absent (the spec's default, ``OGC:CRS84``), an authority
    string (``EPSG:3857``), ``projjson:<key>`` pointing into the file's key-value
    metadata, and — what DuckDB writes — a whole PROJJSON document inline.

    ``srid:<n>`` is deliberately NOT resolved. The spec defines it as a numeric
    spatial reference identifier and names no authority (its own example is
    ``srid:0``), so reading it as ``EPSG:<n>`` would be MapSmith inventing a
    coordinate system and recording it as fact — the exact bug fixed in 0.2.1
    when ``crs: null`` was being read as CRS84.

    Every refusal carries its reason. Returning a bare ``None`` told the agent
    "this file has no CRS" about a file whose schema visibly has a ``crs``
    field, which is true of the result and false of the file. A malformed
    declaration is refused the same way rather than allowed to raise: a raw
    ``pyproj.CRSError`` reaching the caller beats MapSmith's own message, which
    is what the precondition ordering exists to prevent.
    """
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    text = declaration.strip()
    if not text:
        # Absent is not unknown: the spec's default is OGC:CRS84.
        return CRS.from_user_input("OGC:CRS84"), None
    if text.startswith("{"):
        try:
            return CRS.from_json(text), None
        except (CRSError, ValueError) as exc:
            return None, (
                "the file carries an inline PROJJSON coordinate system that PROJ "
                f"cannot read ({exc}). The file needs rewriting with a CRS its own "
                "toolchain can produce; MapSmith will not guess at the intent."
            )
    if text.lower().startswith("projjson:"):
        import pyarrow.parquet as pq

        key = text.split(":", 1)[1]
        document = (pq.ParquetFile(path).metadata.metadata or {}).get(key.encode())
        if document is None:
            return None, (
                f"the file declares its coordinate system as '{text}', but there is "
                f"no '{key}' entry in its key-value metadata to point at. The file "
                "is internally inconsistent and needs rewriting at the source."
            )
        try:
            return CRS.from_json(document.decode()), None
        except (CRSError, ValueError, UnicodeDecodeError) as exc:
            return None, (
                f"the file's '{key}' metadata entry is not a coordinate system PROJ "
                f"can read ({exc})."
            )
    if text.lower().startswith("srid:"):
        return None, (
            f"the file declares its coordinate system as '{text}'. The Parquet "
            "geospatial spec defines srid as a bare numeric identifier and names no "
            "authority for it (its own example is 'srid:0'), so MapSmith will not "
            f"read it as EPSG:{text.split(':', 1)[1]} — that would be inventing a "
            "coordinate system and recording it as fact. Rewrite the file with an "
            "authority string, or assign the CRS explicitly if you know which one "
            "it means."
        )
    try:
        return CRS.from_user_input(text), None
    except (CRSError, ValueError) as exc:
        return None, (
            f"the file declares its coordinate system as '{text}', which PROJ does "
            f"not recognise ({exc})."
        )


def gpkg_layers(path: str) -> list[str] | None:
    """The layer names of a container, or None when they cannot be listed.

    None and [] must stay distinct: an empty list means "listed, nothing in
    there", while None means "we do not know what is in there" — and the only
    safe thing to do with a container of unknown contents is refuse to rewrite
    it. Collapsing the failure into [] made the caller's fail-closed branch
    unreachable, so an unlistable GeoPackage looked exactly like a single-layer
    one and the repair went ahead.
    """
    with suppress(Exception):
        from pyogrio import list_layers

        return [str(row[0]) for row in list_layers(path)]
    return None


def ambiguous_layers(path: str) -> list[str] | None:
    """Layer names of a MULTI-layer OGR source, or None when there is nothing
    to choose: single layer, unlistable, or not an OGR path at all.

    Despite its name, :func:`gpkg_layers` lists any OGR source; this wrapper
    only adds the question that matters here — is there more than one?
    """
    if str(path).lower().endswith(".parquet"):
        return None
    layers = gpkg_layers(path)
    return layers if layers and len(layers) > 1 else None


def refuse_ambiguous_container(path: str) -> None:
    """Raise for a multi-layer container nobody chose a layer of (issue #29).

    GDAL's default — the first layer — answers a question the caller never
    asked, and the manifest could not honestly record which data produced the
    numbers. Refusing is the only answer every component can give
    consistently; the message tells the agent how to choose instead.
    """
    layers = ambiguous_layers(path)
    if not layers:
        return
    shown = ", ".join(layers[:8]) + (", ..." if len(layers) > 8 else "")
    raise ValueError(
        f"{path} holds {len(layers)} layers ({shown}) and no layer was chosen. "
        "MapSmith will not pick one for you: the format's default is simply the "
        "first layer, which may not be the one you mean, and the provenance "
        "manifest could not honestly say which data produced the numbers. "
        "Inspect the container with describe_dataset, which lists the layers, "
        "then extract the one you mean into its own dataset: "
        "run_operation(operation='extract_layer', arguments={'input_path': "
        f"'{path}', 'layer': '<name>', 'output_path': ...}}). It has no tool of "
        "its own, like most of the catalogue. For a condition on the rows as "
        "well, run_sql can do both at once."
    )


def _read_geoparquet(path: str, *, allow_no_geometry: bool) -> gpd.GeoDataFrame:
    """GeoParquet 1.x through GeoPandas, 2.0-native through pyarrow.

    GeoPandas 1.1 raises ``Missing geo metadata`` on a 2.0-native file, which
    reached the agent as the tool's error — not our message, no hint, and
    misleading, since the file does carry geospatial metadata. The geometry is
    WKB either way, so reading it is a matter of looking in the other place.
    """
    import pyarrow.parquet as pq

    try:
        return gpd.read_parquet(path)
    except ValueError as exc:
        if "geo metadata" not in str(exc).lower():
            raise
        original = exc

    columns = native_geometry_columns(path)
    if not columns:
        if not allow_no_geometry:
            raise original  # genuinely no geometry anywhere: keep the original error
        import pandas as pd

        table = pd.read_parquet(path)
        if len(table):
            # The tolerated case is DuckDB's zero-row COPY output, and only that.
            # A file with rows and no geometry read as an empty geometry column
            # produces "N/N invalid geometries", which is critical, which calls
            # the repair that rewrites the file — the shape of the bug #28 closed.
            raise original
        return gpd.GeoDataFrame(table, geometry=gpd.GeoSeries([], dtype="geometry"))

    frame = pq.read_table(path).to_pandas()
    reason = None
    for name, declaration in columns:
        crs, why = native_crs(path, declaration)
        # `.rename(name)` is load-bearing: `from_wkb` drops the Series name, so
        # the geometry silently became "geometry" — and the mechanical repair
        # then rewrites the user's file under that name, defeating the care
        # `verify._repair_invalid_geometry` takes never to assume it.
        frame[name] = gpd.GeoSeries.from_wkb(frame[name], crs=crs).rename(name)
        if name == columns[0][0]:
            reason = why
    # Every native geometry column is read as geometry, not only the active one:
    # one left as raw bytes survives a round-trip as an opaque binary field and
    # loses both its logical type and its CRS.
    gdf = gpd.GeoDataFrame(frame, geometry=columns[0][0])
    if reason:
        gdf.attrs[CRS_REASON] = reason
    return gdf


def read_vector(path: str) -> gpd.GeoDataFrame:
    """Open a vector dataset. Every operational read path goes through here.

    GeoParquet is read natively rather than through GDAL: GDAL's Parquet driver
    is not bundled in the wheels, so routing ``.parquet`` through ``read_file``
    breaks on a default install.

    A multi-layer container with no chosen layer is REFUSED (issue #29, closed
    the day Argleton's trap 006 measured the old behaviour). GDAL's default —
    the first layer — answered a question the caller never asked, silently:
    quieter even than the bare pyogrio call, whose stderr warning this reader
    used to swallow. Refusal is the one answer every component can give
    consistently; ``verify.probe_crs`` returns ``unknown`` for the same case so
    the dispatcher and the plan validator never inspect a layer no operation
    will read. The single deliberate exception stays in
    :func:`read_vector_or_table`: verification prefers the stem-named layer of
    outputs MapSmith wrote and named itself.
    """
    if str(path).lower().endswith(".parquet"):
        return _read_geoparquet(path, allow_no_geometry=False)
    refuse_ambiguous_container(path)
    return gpd.read_file(path)


def read_named_layer(path: str, layer: str) -> gpd.GeoDataFrame:
    """One named layer of a multi-layer container.

    The counterpart of :func:`refuse_ambiguous_container`: that function exists
    because nobody chose, and this one because somebody did. The ambiguity the
    refusal protects against is gone the moment a name is given, so this is the
    one read that is allowed past it — and it lives here, with every other
    "open a vector dataset" decision, rather than at the call site. #28 was that
    decision in six copies with four of them missing a branch.

    An unknown name is refused with the real list rather than answered with an
    empty frame: a typo and an empty layer are different problems, and only one
    of them is the caller's data.
    """
    # Before asking OGR anything: a GeoParquet has no layers to choose between,
    # and whether GDAL can even list it depends on whether the build has the
    # Arrow driver. Deciding by installed driver is how the same call reads one
    # file two ways on two machines — and `read_vector` routes .parquet away
    # from OGR on purpose, for the 2.0 types and the CRS-declaration branch.
    if str(path).lower().endswith(".parquet"):
        raise ValueError(
            f"{path} is a GeoParquet: a single dataset, with no layers to choose "
            "between. Read it directly — there is nothing to extract."
        )
    available = gpkg_layers(path)
    if not available:
        raise ValueError(
            f"{path} holds no listable layers. It is either a single-dataset format "
            "— a GeoJSON, a shapefile — which needs no extraction and can be read "
            "directly, or it is not an OGR source at all."
        )
    if layer not in available:
        raise ValueError(
            f"{path} has no layer {layer!r}. It holds: {sorted(available)}. Layer "
            "names are case-sensitive; describe_dataset lists them with their "
            "feature counts and geometry types."
        )
    return gpd.read_file(path, layer=layer)


def read_vector_or_table(path: str) -> gpd.GeoDataFrame:
    """As :func:`read_vector`, but a Parquet file with no geometry *at all*
    becomes a frame with an empty geometry column instead of an error.

    Only verification wants this, and it wants one more thing: for a
    GeoPackage, the layer named after the file stem. Verification runs on
    outputs, which MapSmith wrote and named itself, and GDAL handing back the
    first layer would verify a layer the operation never wrote and mark an
    unchecked output as verified. On *inputs* that same preference would fork
    from every other component (see :func:`read_vector`), so it stays here.
    """
    lower = str(path).lower()
    if lower.endswith(".parquet"):
        return _read_geoparquet(path, allow_no_geometry=True)
    if lower.endswith(".gpkg"):
        stem = Path(path).stem
        layers = gpkg_layers(path) or []
        if stem in layers:
            return gpd.read_file(path, layer=stem)
        if len(layers) > 1:
            # Verification-only tolerance, chosen on purpose rather than
            # inherited from GDAL: a foreign multi-layer container must still
            # be INSPECTABLE for its defects so the checks land in a manifest,
            # and the repair separately refuses to rewrite containers.
            # Operational reads refuse this same case outright (#29).
            return gpd.read_file(path, layer=layers[0])
    return read_vector(path)


def read_vector_capped(path: str, cap: int) -> tuple[gpd.GeoDataFrame, int, list[float] | None]:
    """``(at most cap rows, total feature count, full native bounds)``.

    OGR formats read only ``cap`` features and take count and bounds from the
    layer metadata, with no full scan. GeoParquet currently reads fully and
    subsets in memory — a pushdown read is a known follow-up. The count and the
    bounds always describe the WHOLE dataset, so a truncated preview never lies
    about the extent it stands for.
    """
    if str(path).lower().endswith(".parquet"):
        gdf = read_vector(path)
        total = len(gdf)
        bounds = [float(v) for v in gdf.total_bounds] if total else None
        return gdf.head(cap), total, bounds

    import pyogrio

    refuse_ambiguous_container(path)
    info = pyogrio.read_info(path)
    total = int(info.get("features") or -1)
    meta_bounds = info.get("total_bounds")
    if total < 0 or meta_bounds is None:  # driver without cheap metadata
        gdf = read_vector(path)
        total = len(gdf)
        bounds = [float(v) for v in gdf.total_bounds] if total else None
        return gdf.head(cap), total, bounds
    return gpd.read_file(path, max_features=cap), total, [float(v) for v in meta_bounds]


def crs_reason(frame: Any) -> str | None:
    """Why this frame has no CRS, when we know — see :data:`CRS_REASON`."""
    attrs = getattr(frame, "attrs", None) or {}
    return attrs.get(CRS_REASON)


def no_crs_message(frame: Any, base: str) -> str:
    """``base``, plus the reader's explanation when it has one.

    Several operations refuse a CRS-less input themselves, before
    ``verify_loaded_inputs`` can run, and each one used to throw the reason
    away — so the same file got an honest message from ``clip`` and a blind one
    from ``buffer_layer``. The reason belongs to the read, not to the caller
    that happens to notice first.
    """
    reason = crs_reason(frame)
    return f"{base} {reason[0].upper() + reason[1:]}" if reason else base


def refuse_missing_geometry(frame: Any, path: str, consequence: str) -> None:
    """Refuse features with no geometry, or an empty one, saying what they would do.

    An operation that has nowhere to put a feature without a position either
    crashed on it -- `thin_points` with an AttributeError, the sampler turning
    a NaN coordinate into a cell index, the line operations sorting a set
    holding None -- or would have to drop it without saying so. Refused, with
    the count and the consequence, like `cluster_points_by_distance` does
    (found by review, 2026-09-29).
    """
    import shapely

    geoms = frame.geometry.to_numpy()
    missing = int((shapely.is_missing(geoms) | shapely.is_empty(geoms)).sum())
    if missing:
        raise ValueError(
            f"{path} has {missing} feature(s) with no or an empty geometry. "
            f"{consequence} Remove those features first."
        )
