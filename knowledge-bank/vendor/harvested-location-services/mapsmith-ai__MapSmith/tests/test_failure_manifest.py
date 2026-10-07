"""A writer that fails after its output reached the disk still leaves a record.

Invariant 2 says a dataset without a manifest did not come from MapSmith, and
section 4 of the specification says a conforming producer "emits a conforming
record for every dataset it writes, including failed runs". On 2026-09-25 a
pre-release conformance review found about twenty writers breaking both on
their failure path: a write or a check that raised left the dataset on disk
with nothing beside it -- `resample_raster` among them, two days after the
same defect was fixed in its twin `reproject_raster`. Each had been fixed or
left one at a time, which is how the twin was missed. Injecting the failure
into every writer, as this file does, found 28 of the 58 that 0.5.1 shipped
(and a 29th that had not shipped yet).

So the list here is the catalogue, and the failure is injected rather than
waited for, in the two places a writer can die once bytes exist:

- the WRITE: the call that writes the operation's own output leaves partial
  bytes and raises (a full disk, a driver error). Only writers that write
  through Python can be reached this way; Whitebox writes from its own binary.
- the first CHECK built once the output exists raises. Every writer builds its
  checks after writing, so this reaches all of them, Whitebox and `run_sql`
  included, and stands for any failure between the write and the manifest.

Each mode says how many writers it actually reached, and fails if that is
fewer than it should be: a sabotage that never fires proves nothing (D-079).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapsmith import catalog, verify
from mapsmith.plans.registry import BINDINGS

WRITING = [
    entry["name"]
    for entry in catalog.OPERATIONS
    if entry["status"] == "available"
    and (binding := BINDINGS.get(entry["name"])) is not None
    and binding.output_arg is not None
]

COMPLETED = "x-mapsmith:operation_completed"


class Sabotage(RuntimeError):
    """Raised by the test, never by MapSmith."""


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    """Built once for the module. Built per case, 118 cases rebuilt all 59
    inputs each time and the file took six minutes on its own."""
    from test_verify import _spec_fixtures

    return _spec_fixtures(tmp_path_factory.mktemp("writers"))


def _clear(output):
    for path in (output, Path(f"{output}.provenance.json")):
        path.unlink(missing_ok=True)


def _call_and_find_output(name, fixtures, request):
    call = fixtures.get(name)
    if call is None:
        pytest.skip(f"{name}: no conformance fixture (an extra is missing?)")
    result = call()
    output = Path(result["output"])
    # Clear the success so that what the sabotaged run leaves is its own, and
    # clear whatever the sabotage leaves, since the inputs are shared.
    _clear(output)
    request.addfinalizer(lambda: _clear(output))
    return call, output


def _assert_record_beside(name, output, raised):
    manifest = Path(f"{output}.provenance.json")
    assert raised is not None, f"{name}: the sabotaged run did not raise"
    if not output.exists():
        return
    assert manifest.exists(), (
        f"{name} left {output.name} on disk and no manifest beside it after "
        f"{type(raised).__name__}: {raised}"
    )
    record = json.loads(manifest.read_text(encoding="utf-8"))
    failed = [c for c in record["verification"] if c["name"] == COMPLETED]
    assert failed and not failed[0]["passed"] and failed[0]["critical"], (
        f"{name}: the manifest beside a failed run does not say the run failed"
    )


@pytest.mark.parametrize("name", WRITING)
def test_a_check_that_raises_after_the_write_leaves_a_record(
    name, fixtures, request, monkeypatch
):
    call, output = _call_and_find_output(name, fixtures, request)
    original = verify.Check.__init__
    fired = []

    def init(self, *args, **kwargs):
        check_name = args[0] if args else kwargs.get("name")
        if not fired and check_name != COMPLETED and output.exists():
            fired.append(check_name)
            raise Sabotage(f"sabotaged while building check {check_name!r}")
        original(self, *args, **kwargs)

    monkeypatch.setattr(verify.Check, "__init__", init)
    raised = None
    try:
        call()
    except Exception as failure:  # noqa: BLE001 - whatever the writer raises is the finding
        raised = failure
    monkeypatch.undo()
    assert fired, (
        f"{name}: no check was built after the output existed, so this sabotage "
        "reached nothing -- the writer checks before writing, or the output "
        "path is not the one it reports"
    )
    _assert_record_beside(name, output, raised)


#: Writers whose output is written by an engine this test cannot intercept from
#: Python. Derived from what the write sabotage reaches, and pinned so that a
#: writer silently moving out of reach is a failure, not a quieter test.
_WRITE_UNREACHABLE = {
    "aspect",
    "curvature",
    "euclidean_distance",
    "extract_streams",
    "flow_accumulation",
    "flow_direction",
    "focal_statistics",
    "hillshade",
    "idw_interpolation",
    "run_sql",
    "slope",
    "viewshed",
    "watershed",
}


@pytest.mark.parametrize("name", WRITING)
def test_a_write_that_dies_halfway_leaves_a_record(name, fixtures, request, monkeypatch):
    import geopandas as gpd
    import pyarrow.parquet as pq
    import pyogrio
    import rasterio

    call, output = _call_and_find_output(name, fixtures, request)
    hits = []

    def is_output(path):
        try:
            return Path(str(path)).resolve() == output.resolve()
        except (TypeError, ValueError, OSError):
            return False

    def die(path):
        hits.append(path)
        Path(str(path)).write_bytes(b"partial")
        raise Sabotage("sabotaged write")

    def wrap_writer(owner, attr, path_index):
        original = getattr(owner, attr)

        def writer(*args, **kwargs):
            if len(args) > path_index and is_output(args[path_index]):
                die(args[path_index])
            return original(*args, **kwargs)

        monkeypatch.setattr(owner, attr, writer)

    wrap_writer(gpd.GeoDataFrame, "to_parquet", 1)
    wrap_writer(gpd.GeoDataFrame, "to_file", 1)
    wrap_writer(pyogrio, "write_dataframe", 1)
    wrap_writer(pq, "write_table", 1)

    opened = rasterio.open

    class DyingDataset:
        def __init__(self, dataset):
            self._dataset = dataset

        def __getattr__(self, attr):
            if attr in ("write", "write_band"):
                def write(*args, **kwargs):
                    hits.append(output)
                    raise Sabotage("sabotaged raster write")

                return write
            return getattr(self._dataset, attr)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._dataset.close()
            return False

        def close(self):
            self._dataset.close()

    def open_(fp, mode="r", *args, **kwargs):
        dataset = opened(fp, mode, *args, **kwargs)
        if mode in ("w", "w+", "r+") and is_output(fp):
            return DyingDataset(dataset)
        return dataset

    monkeypatch.setattr(rasterio, "open", open_)

    # `resample_raster` and `reproject_raster` never call `write`: the pixels
    # arrive through `warp`, into the band of the dataset opened above. They
    # are the two writers the CHANGELOG names, so they are reached here rather
    # than listed as out of reach.
    import rasterio.warp

    reproject = rasterio.warp.reproject

    def dying_reproject(*args, destination=None, **kwargs):
        target = getattr(destination, "ds", None)
        if target is not None and is_output(getattr(target, "name", None)):
            hits.append(output)
            raise Sabotage("sabotaged warp into the output")
        return reproject(*args, destination=destination, **kwargs)

    monkeypatch.setattr(rasterio.warp, "reproject", dying_reproject)
    raised = None
    try:
        call()
    except Exception as failure:  # noqa: BLE001 - whatever the writer raises is the finding
        raised = failure
    monkeypatch.undo()

    if name in _WRITE_UNREACHABLE:
        assert not hits, (
            f"{name} is listed as out of this sabotage's reach and was reached: "
            "take it off the list so it is tested"
        )
        return
    assert hits, (
        f"{name}: the write sabotage never fired. If its output is now written "
        "by an engine this test cannot intercept, add it to _WRITE_UNREACHABLE -- "
        "the check sabotage above still covers it"
    )
    _assert_record_beside(name, output, raised)
