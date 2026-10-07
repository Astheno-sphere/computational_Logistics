"""Where a raster's values actually are — the one place that decides.

A grid of numbers is not a map until something says where each number sits, and
GeoTIFF says it in two ways that differ by half a pixel:

* **`RasterPixelIsArea`** — a value describes the cell it fills. The tie point in
  the header is that cell's upper-left corner. The default.
* **`RasterPixelIsPoint`** — a value is a sample at a grid node. The tie point in
  the header is the position of the first sample itself.

**GDAL folds that difference into the geotransform, so a reader going through it
has nothing to add.** Since RFC 33 (`GTIFF_POINT_GEO_IGNORE`, FALSE by default)
the GTiff driver shifts a PixelIsPoint tie point by half a pixel on read and on
write, so the geotransform is always area-oriented: the Raster Data Model says
AREA_OR_POINT "is not intended to influence interpretation of georeferencing
which remains area oriented". The sample of cell `(row, col)` is at
`transform * (col + 0.5, row + 0.5)` under either tag — which is what
`dataset.xy()` returns.

**This module said the opposite until 2026-09-25**, and so did Argleton trap 024,
whose builder claimed GDAL "leaves the geotransform alone, which is documented".
It is documented the other way. MapSmith added no half cell for a Point file on
top of GDAL's, which put every sample of a point-registered raster half a cell
north-west of where it is: on the Copernicus DEM, whose samples fall on whole
arc-seconds by its own documentation, 10.79986 where the sample is at 10.8. The
premise was never measured; one read with `GTIFF_POINT_GEO_IGNORE=TRUE`, which
shows the raw tie point, would have caught it (D-096).

## What the tag is still for

What a value MEANS: an average over a cell or a sample at a point, which is data
and is recorded in the manifest. And the engines that read the raw tie point
without GDAL's shift: the terrain engine does, and gets a Point file half a cell
wrong in the other direction, so it is handed an area-tagged copy with GDAL's
own geotransform (`whitebox_engine._needs_plain_copy`).

## What it does not fix

Nothing here changes what an operation MEANS. `preserve` carries the declaration
onto an output rather than answering what a resampled point grid represents.
"""

from __future__ import annotations

from typing import Any

#: Where a value sits from the cell's upper-left corner, in cells, as GDAL's
#: geotransform describes the cell. The same for both registrations: GDAL has
#: already applied the difference (see the module docstring).
SAMPLE_OFFSET = 0.5

#: The metadata item GDAL reports the GeoTIFF raster type as. Written once so
#: that a search for it finds every use.
TAG = "AREA_OR_POINT"

#: The two `crs_decisions` keys this module contributes. Declared in
#: `provenance.CRS_EXTENSIONS` with every other extension MapSmith adds to
#: that object, each with the sentence saying why it is not a synonym of a
#: key the specification already has -- one place, so the ratchet has
#: something to be a ratchet over.
from .provenance import (
    REGISTRATION_KEY,
    REGISTRATION_REASON_KEY,
)


def registration(dataset: Any) -> str:
    """`"area"` or `"point"` for an open rasterio dataset, or a literal kind.

    Anything other than a declared `Point` is area: the default is area, most
    formats cannot express anything else, and treating an unreadable tag as
    point would move every position on files that are fine.

    A **closed** dataset raises instead of answering. This is not defensive
    tidiness: `reclassify`, `band_math` and `extract_band` all called `preserve`
    after their input's `with` block had ended, and asking a closed dataset for
    its tags does not raise — GDAL prints `Pointer 'hObject' is NULL` to stderr
    and returns nothing, so this function answered "area" and three writers
    shipped point-registered inputs as area-registered outputs. Half a cell,
    fifteen metres on a thirty-metre DEM, with nothing in the file or the
    manifest to say it happened. A question asked of a closed file has no
    answer, and pretending otherwise is what made it silent.
    """
    if isinstance(dataset, str):
        kind = dataset.strip().lower()
        if kind not in ("area", "point"):
            # The same policy as the closed-dataset guard below, and for the
            # same reason. A path is the natural mistake — every other entry
            # point in this module takes one — and so is passing "Point", the
            # literal GDAL writes and `preserve` writes back. Answering "area"
            # to either makes `preserve` a silent no-op, which is the
            # fifteen-metres-on-a-30 m-DEM defect this module exists to prevent.
            raise ValueError(
                f"registration() got {dataset!r}, which is neither 'area' nor "
                "'point'. Pass an open dataset, or the string registration() "
                "returned for one — a path is not an answer, and neither is the "
                "AREA_OR_POINT tag's own spelling."
            )
        return kind
    if getattr(dataset, "closed", False):
        raise ValueError(
            "registration() was asked about a closed raster. Read it inside the "
            "`with` block that opened the input and pass the string on, or the "
            "answer is whatever GDAL returns for a null pointer."
        )
    try:
        declared = (dataset.tags() or {}).get(TAG)
    except Exception:  # noqa: BLE001 - a driver that cannot report tags is area
        return "area"
    return "point" if str(declared).strip().lower() == "point" else "area"


def offset(dataset: Any) -> float:
    """Where the sample sits in its GDAL cell: always the centre.

    Takes the dataset so that a registration it cannot report still raises
    here, as before; the answer no longer depends on it.
    """
    registration(dataset)
    return SAMPLE_OFFSET


def describe(dataset: Any) -> dict[str, Any]:
    """The registration as an entry in one of OUR objects: what it is and what
    it changed.

    Recorded on every operation that converts between cells and coordinates,
    including the ordinary case. A record that mentions the convention only
    when it is unusual leaves a reader unable to tell "area" from "nobody
    looked", and those are different claims.

    Plain, unprefixed keys, because the places this lands are ours: the answer
    `locate_extreme_cell` hands back, and the `parameters` of `contour_lines`.
    For the manifest's `crs_decisions`, whose other keys belong to the
    specification, use `manifest_decisions`. (`least_cost_path` was named here
    too until 2026-09-06 -- in the same commit that stopped it calling this
    function, so the sentence was written false rather than made false.)
    """
    kind = registration(dataset)
    return {
        "raster_registration": kind,
        # NOT "reason". This dict is merged into `crs_decisions`, which already
        # has one, and the first version of this function silently replaced the
        # sentence explaining a reprojection with a sentence about cell
        # registration. An existing test caught it; two different reasons under
        # one key is a defect wherever it happens.
        "raster_registration_reason": (
            "the file declares AREA_OR_POINT=Point, so each value is a sample at "
            "a grid node; GDAL has already shifted the geotransform by half a cell "
            "for it, so the sample is at the centre of the cell GDAL describes"
            if kind == "point"
            else "the file does not declare point registration, so each value "
            "describes the cell it fills and its position is the cell's centre"
        ),
    }


def manifest_decisions(dataset: Any) -> dict[str, Any]:
    """The same two facts, named for the manifest's `crs_decisions`.

    Prefixed, and that is the whole difference from `describe`. Section 3.7 of
    the manifest specification recommends the keys of `crs_decisions`, and
    since draft.7 requires every other key to be `x-<producer>:<name>` -- the
    rule MapSmith applied before the specification said it. The reason that decided
    the prefix is the reader's rather than the registry's: MapSmith already
    prefixes its check names, for exactly this -- so that a consumer can tell
    the format's vocabulary from one producer's -- and a field is no different.
    Someone holding a manifest and not the specification could not tell
    `raster_registration` from `analysis_crs` before 2026-09-06. (No count
    here on purpose: the first version said "48 check names", the number was
    54, and nothing in the tree derives it.)

    A separate function and not a flag on `describe`, because the two callers
    are answering different questions. `describe` fills objects that are ours
    all the way down, where a prefix would be noise an agent has to read past;
    this fills one whose other keys are the format's, where the absence of a
    prefix is a claim that the key is the format's too.
    """
    plain = describe(dataset)
    return {
        REGISTRATION_KEY: plain["raster_registration"],
        REGISTRATION_REASON_KEY: plain["raster_registration_reason"],
    }


def sample_xy(dataset: Any, row: int, column: int) -> tuple[float, float]:
    """Where the value of this cell IS, as a coordinate.

    The same answer as `dataset.xy(row, col)`, under either registration, and
    kept as the one place that says so: it was the replacement for `xy` while
    this module believed a Point file needed a different answer (D-096).
    """
    shift = offset(dataset)
    return dataset.transform * (column + shift, row + shift)


def sample_index(dataset: Any, x: float, y: float) -> tuple[int, int]:
    """Which cell's value is the one at this position.

    The cell the position falls inside, under either registration: GDAL's
    cell around a point sample is centred on it, so the nearest sample and the
    containing cell are the same cell.

    Returns **(row, column)**, in that order, because that is the order every
    array index is written in. Unpacking it the other way round is the axis-order
    defect this project has a whole Argleton family for, and it happened here
    once already — the existing sampling tests caught it in the same minute.

    A position exactly on a cell edge belongs to the cell east and south of
    it: `floor`, whose rule can be stated, rather than a rounding whose
    tie-breaking alternates.
    """
    import math

    registration(dataset)
    column, row = ~dataset.transform * (x, y)
    return math.floor(row), math.floor(column)


def sample_space(dataset: Any, x: float, y: float) -> tuple[float, float]:
    """The position in *sample space*: (column, row) where integers are samples.

    What bilinear interpolation needs. A coordinate at array position 3.5 is
    exactly on the sample of cell 3, so sample space is array space minus a
    half -- under either registration, because GDAL's geotransform already
    centres its cell on a point sample.
    """
    column, row = ~dataset.transform * (x, y)
    shift = offset(dataset)
    return column - shift, row - shift


def bounds_of_samples(dataset: Any) -> tuple[float, float, float, float]:
    """The envelope of the sample POSITIONS, which is not the dataset's extent.

    The outermost samples sit half a cell inside the extent GDAL reports, under
    either registration. Returned as (left, bottom, right, top).
    """
    shift = offset(dataset)
    left, top = dataset.transform * (shift, shift)
    right, bottom = dataset.transform * (
        dataset.width - 1 + shift,
        dataset.height - 1 + shift,
    )
    return min(left, right), min(top, bottom), max(left, right), max(top, bottom)


def preserve(source: Any, destination: Any) -> str | None:
    """Carry the registration from an input raster onto an output one.

    `profile.copy()` does not include tags, so every raster MapSmith wrote used
    to come back area-registered whatever went in. That is the same silent error
    one step downstream: a point-registered DEM in, an area-registered file out,
    and every position derived from it afterwards half a cell wrong with nothing
    in the file to say so.

    `source` is an open input dataset **or** the string `registration()` already
    returned for it. The second form exists because the output is often written
    after the input's `with` block has closed, and three writers got that wrong
    at once: taking the string while the input is open makes the correct thing
    the easy thing.

    Returns a note for the manifest when something was carried, None otherwise.
    """
    if registration(source) != "point":
        return None
    destination.update_tags(**{TAG: "Point"})
    return (
        "the input declares AREA_OR_POINT=Point and the output declares it too. "
        "Dropping it would have made every position derived from the output half "
        "a cell wrong, with nothing in the file to say so."
    )


#: GDAL variables that change which georeferencing a raster is read with. Only
#: these: a manifest that listed forty variables would bury the one that
#: mattered, and its reader would learn to skip the field.
GEOREF_VARIABLES = ("GDAL_PAM_ENABLED", "GDAL_GEOREF_SOURCES")

#: The keys `georeferencing_source` contributes that are MapSmith's own
#: statements rather than the name of a setting. Section 3.8 asks for the
#: configuration *as the engine reports it* -- `PROJ_NETWORK`, the `GDAL_*`
#: variables -- so a real variable name stays exactly as the
#: engine spells it, and anything we worked out ourselves carries the prefix
#: (D-077). Inside one object the difference is visible at a glance: an
#: UPPER_SNAKE key is a setting, a prefixed one is our reading of it.
#: A dictionary and not a tuple since 2026-09-07, for the reason
#: `CRS_EXTENSIONS` is one: the sentence saying what a key claims lives beside
#: the declaration, and `docs/manifest-vocabulary.md` derives the page from
#: here. A second list kept by hand is a list that goes stale in one place.
DERIVED_ENVIRONMENT = {
    "georeferencing_source": (
        "Which of two georeferencings the reader actually resolved, `internal` "
        "or `sidecar (.aux.xml)`. Not a GDAL setting: it is our comparison of "
        "what the file's own tags give against what came back, transform and "
        "CRS both."
    ),
    "georeferencing_sidecar_present": (
        "The name of the `.aux.xml` sitting beside the raster. A fact about the "
        "directory, not about the configuration -- a reader who sees only the "
        "GDAL variables cannot tell that a second georeferencing was there."
    ),
    "georeferencing_supplied_by_sidecar": (
        "Written only when the file carries no georeferencing of its own, to "
        "say that nothing was overridden because there was only ever one. "
        "Without it `georeferencing_source: sidecar` reads as an override that "
        "did not happen."
    ),
    "georeferencing_internal_would_give": (
        "The cell size and origin the other branch would have produced, in "
        "plain decimals so they can be compared with the ones in front of you. "
        "A counterfactual we computed, which is why it cannot be spelled like a "
        "setting: `there was a choice` is weaker than `here is the other answer`."
    ),
}


def georeferencing_source(path: str) -> dict[str, str]:
    """Which georeferencing produced the numbers, when more than one exists.

    A `.aux.xml` beside a raster georeferences it too, and GDAL prefers the
    sidecar over the file's own tags by documented design — a sidecar is how
    somebody corrects georeferencing they know to be wrong, so an override that
    lost to the thing it overrides would not be an override.

    Both readings are the library behaving exactly as written, and that is what
    makes this a field in a record rather than a bug to file. Measured by
    Argleton trap 030: the same file gives 40 000 m² or 160 000 m² and an origin
    a hundred kilometres apart, and until this function existed nothing MapSmith
    wrote could say which.

    Returns the entries for the manifest's `environment` (specification section
    3.8), and **an empty dict when there is nothing to say** — one georeferencing
    means nothing outside the data and the call influenced the answer, and a
    field that fires on every operation is a field nobody reads.

    Costs one extra open, and only on the rare file that has a sidecar at all.
    """
    import os
    from pathlib import Path

    sidecar = Path(f"{path}.aux.xml")
    if not sidecar.exists():
        # Checked BEFORE importing rasterio. This function is called at the top
        # of twelve raster operations, and importing an optional dependency here
        # turned a missing extra into a bare ImportError instead of the sentence
        # naming what to install. Nothing overrides the file, so there is
        # nothing to open and nothing to say.
        return {}

    import rasterio

    setting = {
        name: os.environ[name] for name in GEOREF_VARIABLES if os.environ.get(name)
    }
    with rasterio.open(path) as used:
        effective, effective_crs = used.transform, used.crs
    with rasterio.Env(GDAL_GEOREF_SOURCES="INTERNAL"), rasterio.open(path) as own:
        internal, internal_crs = own.transform, own.crs

    # The CRS as well as the transform. A PAM sidecar can override the `<SRS>`
    # and leave the geotransform alone, and comparing only the transform then
    # reported `georeferencing_source: internal` — a field affirmatively saying
    # the numbers came from the file's own tags when the coordinate system that
    # produced them came from the sidecar. An absent field claims nothing; that
    # one claimed something false. It is also the more consequential axis: a
    # wrong CRS changes every area, length and reprojection downstream, which is
    # the family Argleton measures as `projection-distortion`.
    transform_differs = effective != internal
    crs_differs = not _same_crs(effective_crs, internal_crs)
    from_sidecar = transform_differs or crs_differs
    # A plain image plus an `.aux.xml` carrying SRS and GeoTransform is the
    # documented GDAL way to georeference something that has none. There is one
    # georeferencing there, not two, so there is nothing for anybody to choose
    # and nothing to refuse — and the refusal's own remedy ("remove the sidecar
    # or read the file's own") would have destroyed or ignored the only
    # georeferencing that exists. The field still records that the sidecar
    # supplied it, because that is worth knowing.
    internal_absent = internal_crs is None and internal.is_identity
    entry = {
        "georeferencing_source": "sidecar (.aux.xml)" if from_sidecar else "internal",
        "georeferencing_sidecar_present": sidecar.name,
        **setting,
    }
    if internal_absent:
        entry["georeferencing_supplied_by_sidecar"] = (
            "the file carries no georeferencing of its own, so the sidecar is the "
            "only one there is and nothing was overridden"
        )
        return entry
    if from_sidecar:
        # The number the other reading would have produced, because "there was
        # a choice" is weaker than "here is what the other branch says".
        # Plain decimals, never scientific notation: `5.03e+06` is a northing
        # nobody can compare with the one in front of them, and this string
        # exists to be compared.
        def plain(number: float) -> str:
            return f"{number:.4f}".rstrip("0").rstrip(".")

        parts = []
        if transform_differs:
            parts.append(
                f"cell {plain(abs(internal.a))} x {plain(abs(internal.e))} at "
                f"({plain(internal.c)}, {plain(internal.f)})"
            )
        if crs_differs:
            # Named, because a CRS override is the half that changes every area
            # and length downstream and the half a reader is least likely to
            # look for.
            parts.append(
                f"CRS {_crs_name(internal_crs)} rather than "
                f"{_crs_name(effective_crs)}"
            )
        entry["georeferencing_internal_would_give"] = "; ".join(parts)
    return entry


def manifest_environment(path: str) -> dict[str, str]:
    """The same facts, named for the manifest's `environment`.

    Section 3.8 asks for the configuration *as the engine reports it*, and
    lists `PROJ_NETWORK` and the `GDAL_*` variables -- so a real variable name
    is left exactly as the engine spells it. (It listed `AREA_OR_POINT` too
    until a clarification after draft.6: that is a tag in the file, and our
    reading of it is in `crs_decisions`, see `manifest_decisions`.) The four keys
    MapSmith works out for itself are not settings, they are our reading of
    them, and they carry the prefix (D-077). Inside one object the difference
    is then visible without the specification in hand: UPPER_SNAKE is a
    setting, `x-mapsmith:` is us.

    A separate function rather than a flag, for the reason
    `manifest_decisions` gives: `georeferencing_source` fills the answer
    `describe_dataset` hands back, which is ours all the way down and where a
    prefix would be noise an agent reads past.
    """
    return {
        (f"x-mapsmith:{key}" if key in DERIVED_ENVIRONMENT else key): value
        for key, value in georeferencing_source(path).items()
    }


def _same_crs(left: Any, right: Any) -> bool:
    """Whether two rasterio CRSs are the same one, missing ones included."""
    if left is None or right is None:
        return left is None and right is None
    try:
        return bool(left == right)
    except Exception:  # noqa: BLE001 - an uncomparable CRS is a difference
        return False


#: How much of an authority-less CRS's own text may reach a manifest. The name
#: inside `PROJCS["..."]` is chosen by whoever wrote the file or its sidecar, and
#: this string goes into `environment`, which SECURITY.md invites people to
#: attach to a bug report and which downstream agents read. An audit put 800
#: characters of prompt-injection prose, a filesystem path and a connection
#: string in a CRS name and watched them arrive intact. Redaction is the right
#: second layer for the credential-shaped part of that and no bound at all for
#: the rest.
_CRS_NAME_LIMIT = 80


def _crs_name(crs: Any) -> str:
    """A short, comparable name for a CRS, or a word saying it has none.

    Prefers the authority code, which no file can choose. Falls back to the
    CRS's own text, truncated: see `_CRS_NAME_LIMIT`.
    """
    if crs is None:
        return "none declared"
    try:
        code = crs.to_epsg()
        if code:
            return f"EPSG:{code}"
        text = (crs.to_string() or "").strip()
    except Exception:  # noqa: BLE001 - a CRS that cannot name itself
        return "an unnamed CRS"
    if not text:
        return "an unnamed CRS"
    if len(text) > _CRS_NAME_LIMIT:
        return f"{text[:_CRS_NAME_LIMIT]}… (truncated, {len(text)} characters)"
    return text


def refuse_ambiguous_georeferencing(path: str, operation: str) -> dict[str, str]:
    """Raise when two georeferencings claim the same raster and nobody chose.

    The twin of `readers.refuse_ambiguous_container` (issue #29), on a different
    axis and for the same reason. There, GDAL's default is the first layer of a
    container; here it is the sidecar over the file's own tags. Both defaults
    answer a question the caller never asked, and in both cases a manifest
    could not honestly say which data produced the numbers.

    Returns the `environment` entry when there is nothing to refuse, so a caller
    writes one line and gets either the refusal or the record.

    **Describe does not call this**, on purpose. Its whole job is to say what a
    file is, and a file with two georeferencings is a thing to be told about,
    not a thing to be refused. Refusing where a number is computed and reporting
    where a file is described is the same principle applied twice, not two
    policies.
    """
    source = georeferencing_source(path)
    if not source or source.get("georeferencing_source") == "internal":
        return source
    if "georeferencing_supplied_by_sidecar" in source:
        # One georeferencing, supplied rather than overridden. Recorded, not
        # refused: refusing here asserted the file was georeferenced twice when
        # it was georeferenced once, and offered a remedy that would have thrown
        # away the only georeferencing there was.
        return source
    raise ValueError(
        f"{path} is georeferenced twice and nobody chose: the GeoTIFF's own tags "
        f"say {source['georeferencing_internal_would_give']}, and "
        f"{source['georeferencing_sidecar_present']} beside it says something else. "
        "GDAL prefers the sidecar, which is correct — that is how an override "
        f"works — but {operation} would then report numbers from a file you did "
        "not name, and this record could not say which. describe_dataset lists "
        "both. To choose, either remove the sidecar or set "
        "GDAL_GEOREF_SOURCES=INTERNAL for a run that must use the file's own."
    )
