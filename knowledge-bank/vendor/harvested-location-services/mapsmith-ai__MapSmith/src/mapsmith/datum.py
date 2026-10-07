"""Which coordinate operation PROJ uses between two CRSs, and whether it shifts anything.

Argleton trap 021 is the reason this module exists. When no datum transformation
is available for a pair, PROJ does not fail: it falls back to a *ballpark*
operation, which carries the coordinates across as if the two datums coincided.
The geometry is plausible, the output CRS is genuinely the one that was asked
for, and every downstream check passes -- while the numbers are tens of metres
out. In Italy the NAD27/WGS84 style of mistake is worth about 74 m.

`engines/vector.py` has answered that for `reproject_layer` since 0.4.0. It was
the only answer anywhere: on 2026-09-02 a sweep found `transformation` in one
manifest out of fifty-eight, and `reproject_raster` -- which is the head example
of section 3.7 of the manifest specification -- recorded the two CRS labels and
said nothing about the operation between them. The trap we measure in other
people's software survived intact on our own raster side.

**The distinction this module exists to keep**, and getting it wrong would be
worse than saying nothing:

- `best_operation` is for callers that *choose*. It hands back a transformer and
  will pick a stated-accuracy operation over a ballpark one when both exist. The
  vector path uses it, so the record describes what actually happened.
- `default_operation` is for callers that *do not choose* -- rasterio's warp,
  GDAL, anything that takes the two CRSs and reaches for PROJ itself. It reports
  the operation PROJ picks on its own. Recording a better operation's accuracy
  beside a raster that was warped with the default would be a false manifest,
  which is a worse failure than an incomplete one.

Both are plain pyproj. Nothing here needs a provenance format, which is the
point: a caller can check this without adopting anything of ours.
"""

from __future__ import annotations

import math
from typing import Any

# A ballpark operation reports accuracy -1 (or nothing at all). Anything >= 0 is
# a real, published operation with a stated accuracy in metres.
#
# That reading is true of the EPSG database, which is where the number comes
# from for a published operation, and it is NOT enough on its own: see
# `shares_a_datum`, whose comment records the day the same value started
# meaning two different things.
_STATED = 0.0


def shares_a_datum(source_crs: Any, target_crs: Any) -> bool:
    """Do these two CRSs sit on the same datum, so there is no shift to apply?

    Asked of the datums rather than inferred from an accuracy, and that is the
    whole point of this function existing.

    PROJ used to report a stated accuracy of 0.0 for a projection change within
    one datum, so `accuracy >= 0` happened to mean "not a ballpark". PROJ 9.8
    reports **-1.0** for the same pair — the value it also uses for a ballpark —
    so the discriminator stopped discriminating, and MapSmith on a current
    pyproj wrote `is_ballpark: true` into the manifest of a plain UTM
    projection. That is not a cosmetic slip: a record saying a datum shift was
    skipped, on an operation where none was ever needed, accuses the engine of
    something it did not do, and this module exists to prevent exactly that
    sentence in the other direction.

    Measured 2026-09-06 on EPSG:4326 -> EPSG:32633, the same call on two
    builds::

        PROJ 9.5.1   get_last_used_operation().accuracy ==  0.0
        PROJ 9.8.1   get_last_used_operation().accuracy == -1.0

    while `CRS.datum == CRS.datum` answers True on both. It was found by CI
    going red on Python 3.14, which resolves pyproj to 3.8 — the weekly
    "latest versions" job this repository has on its list precisely to tell
    "broken by us" from "broken by them" apart, arriving here by accident
    before it was built.

    Returns False whenever the question cannot be answered — a CRS with no
    datum, a comparison that raises — because the caller then falls back to
    asking PROJ, which is the behaviour that was there before.
    """
    from contextlib import suppress

    with suppress(Exception):
        source_datum = getattr(_as_crs(source_crs), "datum", None)
        target_datum = getattr(_as_crs(target_crs), "datum", None)
        if source_datum is not None and target_datum is not None:
            return bool(source_datum == target_datum)
    return False


def _within_one_datum(pipeline: str | None) -> dict[str, Any]:
    """The record for a pair that needs no datum shift at all.

    Accuracy 0.0 rather than None: a projection change within one datum is
    exact to floating point, it is what PROJ itself reported until 9.8, and it
    is what section 3.7 wants — a number, not an absence a reader has to
    interpret.
    """
    return {"pipeline": pipeline, "accuracy_m": 0.0, "is_ballpark": False}


def _as_crs(value: Any) -> Any:
    """Whatever the caller has, as a pyproj CRS that still knows where it is used.

    Not defensive tidying, and the WKT route is not good enough -- measured on
    2026-09-03, on the pair this module exists for:

        CRS.from_user_input("EPSG:4267")        area_of_use present   ->  7.0 m
        CRS.from_user_input(<the same as WKT>)  area_of_use ABSENT    ->  ballpark

    `area_of_use` comes from the EPSG registry, not from the WKT, and rasterio's
    WKT does not carry it. `accuracy_of` probes a point inside that area to see
    which operation PROJ selects; with no area it falls back to (0, 0), the Gulf
    of Guinea, which is outside almost every real transformation's extent. So
    the same pair came back a ballpark or not **depending on how the caller
    happened to hold the CRS** -- and a wrong `is_ballpark: true` is a manifest
    accusing an engine of something it did not do, which is worse than the
    silence this module replaces.

    Rebuilding from the authority code brings the registry's area back. When
    there is no code (a genuinely custom CRS) the probe is weaker and the record
    says so, rather than asserting a ballpark it cannot see.
    """
    from pyproj import CRS

    crs = value if isinstance(value, CRS) else CRS.from_user_input(
        value.to_wkt() if hasattr(value, "to_wkt") else value
    )
    if crs.area_of_use is not None:
        return crs
    code = crs.to_epsg()
    return CRS.from_epsg(code) if code else crs


def accuracy_of(transformer: Any, source_crs: Any) -> float | None:
    """The stated accuracy in metres of the operation this transformer used.

    PROJ reports the operation only after one has been used, so use one.
    `Transformer.accuracy` is -1 until `proj_trans` runs; the honest value comes
    from `get_last_used_operation()` after a transform. A point inside the CRS's
    own area of use is what gets asked, because which operation PROJ selects can
    depend on where the coordinate is.
    """
    try:
        x, y = _probe_point(source_crs)
        transformer.transform(x, y)
        used = transformer.get_last_used_operation()
    except Exception:  # noqa: BLE001 — no operation to inspect is itself the answer
        return None
    return used.accuracy


def _probe_point(source_crs: Any) -> tuple[float, float]:
    """A coordinate inside the CRS's own area of use, IN THAT CRS'S OWN UNITS.

    `area_of_use` is always in degrees, even for a projected CRS. Feeding its
    midpoint straight to the transformer therefore hands degrees to something
    that expects metres -- measured on 2026-09-03 with EPSG:3003 (Gauss-Boaga,
    Italy zone 1), whose area of use is 5.93..12.0 by 36.53..47.04: the probe
    landed at x=8.965 m, y=41.785 m, nine metres from the false origin and
    nowhere near Italy. No location-restricted operation matches there, so PROJ
    returned the ballpark and the record said the default applied no datum
    shift.

    It does. The default for EPSG:3003 -> EPSG:4326 is "Monte Mario to WGS 84
    (4)", stated accuracy 4 m, and it produces coordinates identical to the ones
    the "better" operation this module would have substituted. So the shipped
    note -- "the transformation this library selects by default for this pair is
    a ballpark one, which applies no datum shift at all" -- was false for every
    projected source, which in this domain is most of them.
    """
    area = getattr(source_crs, "area_of_use", None)
    if area is None:
        return (0.0, 0.0)
    # A bounding box that crosses the antimeridian has west > east, and a plain
    # midpoint of it lands on the far side of the planet -- which is outside
    # every real transformation's extent and therefore always ballpark. This
    # cost an afternoon on 2026-08-26.
    lat = (area.south + area.north) / 2
    lon = (area.west + area.east) / 2
    if area.west > area.east:
        lon = ((area.west + area.east + 360) / 2 + 180) % 360 - 180
    if getattr(source_crs, "is_geographic", False):
        return (lon, lat)
    from pyproj import CRS, Transformer

    into = Transformer.from_crs(CRS.from_epsg(4326), source_crs, always_xy=True)
    x, y = into.transform(lon, lat)
    if not (math.isfinite(x) and math.isfinite(y)):
        # Outside the projection's valid domain: no honest probe exists, and a
        # silent (0, 0) would answer "ballpark" for a pair nobody asked about.
        return (0.0, 0.0)
    return (x, y)


def pipeline_of(transformer: Any) -> str | None:
    try:
        return transformer.to_proj4() or None
    except Exception:  # noqa: BLE001 — a missing pipeline string is not a failure
        return None


def _stated_operations(source_crs: Any, target_crs: Any) -> list[Any]:
    """Every published operation for this pair, best accuracy first.

    No `area_of_interest`, and that is measured rather than assumed. Handing
    PROJ the data's own extent looks obviously right and makes the answer worse:
    on EPSG:4806 with the extent of the data the group comes back holding ONLY
    the ballpark -- the 44 m operation disappears -- so the "better" call would
    fall back to no datum shift at all. Checked on PROJ 9.5.1, 2026-08-27.
    """
    from pyproj.transformer import TransformerGroup

    source_crs, target_crs = _as_crs(source_crs), _as_crs(target_crs)
    return [
        candidate
        for candidate in TransformerGroup(source_crs, target_crs, always_xy=True).transformers
        if candidate.accuracy is not None and candidate.accuracy >= _STATED
    ]


def best_operation(source_crs: Any, target_crs: Any) -> tuple[Any, dict[str, Any]]:
    """The transformer to use when the caller gets to choose, and its record.

    Returns the transformer and the `crs_decisions.transformation` object that
    section 3.7 of the manifest specification asks for.
    """
    from pyproj import Transformer

    source_crs, target_crs = _as_crs(source_crs), _as_crs(target_crs)
    chosen = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    if shares_a_datum(source_crs, target_crs):
        return chosen, _within_one_datum(pipeline_of(chosen))
    accuracy = accuracy_of(chosen, source_crs)
    if accuracy is not None and accuracy >= _STATED:
        return chosen, {
            "pipeline": pipeline_of(chosen),
            "accuracy_m": float(accuracy),
            "is_ballpark": False,
        }

    stated = _stated_operations(source_crs, target_crs)
    if not stated:
        # Every route is a ballpark: there is no datum shift to apply, and
        # saying so is the only honest answer. Recording `is_ballpark: true`
        # rather than refusing keeps the operation usable where the caller
        # knows the datums are equivalent -- the point is that the record says
        # which case this was.
        return chosen, {
            "pipeline": pipeline_of(chosen),
            "accuracy_m": None,
            "is_ballpark": True,
        }
    best = stated[0]
    return best, {
        "pipeline": pipeline_of(best),
        "accuracy_m": float(best.accuracy),
        "is_ballpark": False,
        # The caller is owed this: the transformation the library would have
        # picked by itself applied no datum shift, and this one was chosen
        # instead. Without it the record says the right thing and hides that
        # anything happened.
        "x-mapsmith:default_was_ballpark": True,
    }


def default_operation(source_crs: Any, target_crs: Any) -> dict[str, Any]:
    """What PROJ does on its own, for engines that do not let us choose.

    rasterio's warp, GDAL and DuckDB all take two CRSs and reach for PROJ
    themselves. The record has to describe the operation they will actually get,
    so this never substitutes a better one -- it *reports* that a better one
    exists, under `better_available_m`, which is the fact a caller needs in
    order to go and install the missing grid.

    Returns the `crs_decisions.transformation` object. There is no transformer
    to hand back: the engine builds its own.
    """
    from pyproj import Transformer

    source_crs, target_crs = _as_crs(source_crs), _as_crs(target_crs)
    chosen = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    if shares_a_datum(source_crs, target_crs):
        return _within_one_datum(pipeline_of(chosen))
    accuracy = accuracy_of(chosen, source_crs)
    if accuracy is not None and accuracy >= _STATED:
        return {
            "pipeline": pipeline_of(chosen),
            "accuracy_m": float(accuracy),
            "is_ballpark": False,
        }

    record: dict[str, Any] = {
        "pipeline": pipeline_of(chosen),
        "accuracy_m": None,
        "is_ballpark": True,
        # Deliberately not "chosen_by": the engine chose, and this module is
        # only reporting. Naming us as the chooser is how a manifest starts
        # describing an operation that never ran.
        "x-mapsmith:chosen_by": "the engine, not MapSmith",
    }
    stated = _stated_operations(source_crs, target_crs)
    if stated:
        # The distinction that matters to whoever reads this: "there is no datum
        # shift for this pair" and "there is one and this machine has not got
        # it" are different problems with different fixes.
        record["better_available_m"] = float(stated[0].accuracy)
    return record

