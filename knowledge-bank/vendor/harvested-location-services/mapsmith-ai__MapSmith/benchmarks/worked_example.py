"""One real question, end to end: what gets searched, what gets chosen, what runs.

    Which parcels lie within 1.5 km of the river and sit at no more than 120 m,
    and how large is each of them?

Nothing here is illustrative. The script builds fixtures whose answer can be
worked out on paper, asks the catalog the way an agent would ask it — in the
words of the problem, not the name of a tool — writes down what came back at
every step, then validates and runs the plan and reads the manifests. The
diagram on the README and on the site is rendered from the JSON this emits, so
if a step changes, the picture changes with it.

    python benchmarks/worked_example.py            # print the trace
    python benchmarks/worked_example.py --json out.json

The point it exists to make is the middle column. A catalog of dozens of
operations, most of which take a layer and return a layer, and at each step the
question is not "which tool is best" but "how many could plausibly apply, and how
does the caller get from those to one". The answer is: declare two facts, read
what survives, choose. Never a ranker deciding on its own.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------- fixtures

#: Six parcels on a line east of the river, in EPSG:4326 — degrees on purpose,
#: because that is what arrives from a municipal portal and it is the input the
#: benchmark's worst failure class starts from. Placed near the Mount St Helens
#: DEM the notebooks use, so the repository's fixtures stay in one region.
RIVER_LON = -122.19
PARCELS = [
    # name,          longitude offset from the river, in degrees
    ("North Field", 0.000),
    ("Mill Meadow", 0.004),
    ("Old Orchard", 0.009),
    ("Ridge Farm", 0.017),
    ("West Common", 0.026),
    ("High Copse", 0.036),
]
PARCEL_LAT = 46.2000
PARCEL_SIDE = 0.0015

#: Elevation rises west to east across the fixture, so which parcels sit below
#: the threshold is a property of position and can be stated before anything runs.
DEM_WEST_LON, DEM_EAST_LON = -122.20, -122.15
DEM_WEST_M = 90.0
DEM_EAST_M = 160.0
ELEVATION_LIMIT_M = 120


def build_fixtures(workdir: Path) -> dict[str, Path]:
    """Parcels, a river and a DEM whose answer is known before MapSmith sees it."""
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import LineString, box

    parcels = gpd.GeoDataFrame(
        {"name": [name for name, _ in PARCELS]},
        geometry=[
            box(
                RIVER_LON + offset,
                PARCEL_LAT,
                RIVER_LON + offset + PARCEL_SIDE,
                PARCEL_LAT + PARCEL_SIDE,
            )
            for _, offset in PARCELS
        ],
        crs="EPSG:4326",
    )
    parcels_path = workdir / "parcels.gpkg"
    parcels.to_file(parcels_path, layer="parcels", driver="GPKG")

    river = gpd.GeoDataFrame(
        {"name": ["Cold Creek"]},
        geometry=[
            LineString(
                [(RIVER_LON - 0.0005, PARCEL_LAT - 0.003),
                 (RIVER_LON + 0.0005, PARCEL_LAT + 0.006)]
            )
        ],
        crs="EPSG:4326",
    )
    river_path = workdir / "river.gpkg"
    river.to_file(river_path, layer="river", driver="GPKG")

    # A DEM in the same geographic CRS: 0.0005° cells over the whole extent.
    west, east = DEM_WEST_LON, DEM_EAST_LON
    south, north = PARCEL_LAT - 0.005, PARCEL_LAT + 0.010
    step = 0.0005
    cols = round((east - west) / step)
    rows = round((north - south) / step)
    ramp = np.linspace(DEM_WEST_M, DEM_EAST_M, cols, dtype="float32")
    grid = np.tile(ramp, (rows, 1))
    dem_path = workdir / "elevation.tif"
    with rasterio.open(
        dem_path, "w", driver="GTiff", height=rows, width=cols, count=1,
        dtype="float32", crs="EPSG:4326", transform=from_origin(west, north, step, step),
    ) as dst:
        dst.write(grid, 1)

    return {"parcels": parcels_path, "river": river_path, "dem": dem_path}


# ---------------------------------------------------------------- discovery

#: What an agent would type at each step, in the words of the problem, plus the
#: facts it can state about its own situation without knowing our taxonomy --
#: including what geometry it holds: a river is a line and a parcel is a polygon,
#: and since 2026-09-29 a caller that says so gets the whole set back where one
#: that does not gets a shortlist (31 operations take one vector layer to another).
STEPS: list[dict[str, Any]] = [
    {
        "id": "buffer",
        "ask": "everything within one and a half kilometres of the river",
        "facets": {
            "input_kind": "vector", "produces": "dataset:vector", "dataset_inputs": 1,
            "geometry": "line",
        },
        "operation": "buffer_layer",
        "why": (
            "The parcels are in degrees, and 300 of anything is not a distance in "
            "degrees. This is where the benchmark's worst failure class starts."
        ),
    },
    {
        "id": "near",
        "ask": "keep only the parcels that fall inside that strip",
        "facets": {
            "input_kind": "vector", "produces": "dataset:vector", "dataset_inputs": 2,
            "geometry": "polygon",
        },
        "operation": "clip_layer",
        "why": "Two operations could do it and they answer differently at the edges.",
    },
    {
        "id": "height",
        "ask": "how high is the ground under each of these parcels",
        "facets": {
            "input_kind": "raster", "produces": "dataset:vector", "dataset_inputs": 2,
            "geometry": "polygon",
        },
        "operation": "zonal_statistics",
        "why": (
            "A raster in and a vector out: declaring both narrows this to almost "
            "nothing, and the pair is a fact the caller holds."
        ),
    },
    {
        "id": "area",
        "ask": "how big is each one on the ground",
        "facets": {
            "input_kind": "vector", "produces": "dataset:vector", "dataset_inputs": 1,
            "geometry": "polygon",
        },
        "operation": "measure_area",
        "why": (
            "Ground area, not the area of the map. On a geographic CRS the planar "
            "number is meaningless and on Web Mercator at this latitude it is 1.8x out."
        ),
    },
    {
        "id": "filter",
        "ask": "drop the ones where the ground is above 120 metres",
        "facets": {
            "input_kind": "vector", "produces": "dataset:vector", "dataset_inputs": 1,
            "geometry": "polygon",
        },
        "operation": "select_features",
        "why": (
            "This step used to run outside the plan. run_sql could answer it, but it "
            "takes its inputs inside a SQL string, so it declares zero datasets and a "
            "caller who correctly says they hold one layer was never offered it — a "
            "real gap the arity facet created, and one the plan could not close, "
            "because `$step` references resolve only in arguments declared as dataset "
            "inputs. Substituting into arbitrary strings would be a grammar where a "
            "planner assembles a path out of text. select_features takes a layer and "
            "returns a layer, so the last step of the question is now inside the plan "
            "with a manifest of its own."
        ),
    },
]


def trace_discovery() -> list[dict[str, Any]]:
    """For each sub-goal: how many operations could apply, and what came back."""
    from mapsmith import catalog

    out = []
    for step in STEPS:
        survivors = catalog.applicable(**step["facets"])
        # BM25 pinned, not the default. The position column would otherwise
        # depend on whether a 130 MB download succeeded on the machine that
        # built the page, and `tests/test_worked_example.py` compares this
        # section byte for byte — so an offline build would fail with a README
        # diff about something else entirely. Deterministic and network-free is
        # the right property for a published figure; the narrowing, which is the
        # point of the table, is identical on both engines.
        answer = catalog.search(step["ask"], limit=3, engine="lexical", **step["facets"])
        delivered = catalog.entries(answer)
        shape = answer[0].get("status") if len(answer) == 1 else "ranked"
        position = next(
            (i + 1 for i, e in enumerate(delivered) if e["name"] == step["operation"]),
            None,
        )
        entry = next(o for o in catalog.OPERATIONS if o["name"] == step["operation"])
        out.append(
            {
                "id": step["id"],
                "ask": step["ask"],
                "declared": step["facets"],
                "catalog_size": len(catalog.OPERATIONS),
                "candidates": len(survivors),
                "response": shape if shape in ("choose", "unsure") else "ranked",
                "delivered": len(delivered),
                "chosen": step["operation"],
                "rank_of_chosen": position,
                "distinguishes": entry.get("distinguishes"),
                "why": step["why"],
            }
        )
    return out


# ---------------------------------------------------------------- the plan

def build_plan(paths: dict[str, Path], workdir: Path) -> dict[str, Any]:
    """The whole thing as one plan, so the arguments are data and can be checked."""
    return {
        "goal": (
            "Parcels within 1.5 km of the river whose mean ground elevation is at "
            "most 120 m, with the ground area of each"
        ),
        "steps": [
            {
                "id": "buffer",
                "operation": "buffer_layer",
                "arguments": {
                    "input_path": str(paths["river"]),
                    "output_path": str(workdir / "corridor.parquet"),
                    "distance_meters": 1500,
                },
                "comment": "1.5 km of the river. The layer is in degrees; the buffer is not.",
            },
            {
                "id": "near",
                "operation": "clip_layer",
                "arguments": {
                    "input_path": str(paths["parcels"]),
                    "mask_path": "$buffer",
                    "output_path": str(workdir / "near_river.parquet"),
                },
                "comment": "Parcels inside the corridor.",
            },
            {
                "id": "height",
                "operation": "zonal_statistics",
                "arguments": {
                    "raster_path": str(paths["dem"]),
                    "zones_path": "$near",
                    "output_path": str(workdir / "with_height.parquet"),
                    "stats": ["mean", "min"],
                },
                "comment": "Elevation under each surviving parcel.",
            },
            {
                "id": "area",
                "operation": "measure_area",
                "arguments": {
                    "input_path": "$height",
                    "output_path": str(workdir / "measured.parquet"),
                    "method": "geodesic",
                },
                "comment": "Ground area, not map area.",
            },
            {
                "id": "filter",
                "operation": "select_features",
                "arguments": {
                    "input_path": "$area",
                    "output_path": str(workdir / "answer.parquet"),
                    "by": "field_between",
                    "field": "mean",
                    "maximum": ELEVATION_LIMIT_M,
                },
                "comment": (
                    f"At most {ELEVATION_LIMIT_M} m of mean elevation. Inclusive at "
                    "the bound, which is why the goal says 'at most' and not 'below'."
                ),
            },
        ],
    }


def wrong_plan_first(plan: dict[str, Any]) -> dict[str, Any]:
    """The same plan with two steps swapped, run through the validator.

    It earned its keep while this file was being written: the first version of
    the plan below said `distance_m` where the operation declares
    `distance_meters`, and the validator named the argument and listed the three
    it accepts before anything touched a file.

    Mis-ordered steps are the dominant failure class in the agent benchmark, so
    the honest worked example includes one rather than showing only the version
    that works. Whatever the validator says here is what it said; nothing in this
    file writes the message.
    """
    swapped = json.loads(json.dumps(plan))
    swapped["steps"][0], swapped["steps"][1] = swapped["steps"][1], swapped["steps"][0]
    return swapped


# ---------------------------------------------------------------- rendering

START = "<!-- worked-example:start -->"
END = "<!-- worked-example:end -->"


def _label(text: str) -> str:
    """Node text safe for a mermaid label.

    Parentheses and square brackets terminate a node shape in some mermaid
    versions even inside quotes, and a diagram that fails to compile shows a red
    error box at the top of the README rather than degrading quietly. Entities
    render identically and cannot be mistaken for syntax.
    """
    return (
        text.replace("(", "&#40;")
        .replace(")", "&#41;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace('"', "&quot;")
    )


def _mermaid(trace: dict[str, Any]) -> str:
    """The sequence as a diagram, with the numbers that made each choice.

    Mermaid because GitHub renders it inline and it stays diffable text: a
    picture checked into a repository is a number nobody can verify.
    """
    lines = [
        "```mermaid",
        "flowchart TB",
        f'  ASK["<b>{_label(trace["goal"])}</b>"]',
        '  ASK --> PLAN{{"plan validated<br/>before anything runs"}}',
    ]
    for error in trace["rejected_plan"]["errors"]:
        lines.append(
            f'  PLAN -. "rejected: {error["code"]}" .-> BAD["{_label(error["message"])}"]'
        )
    lines.append("  BAD:::bad")

    by_id = {step["id"]: step for step in trace["execution"]}
    previous = "PLAN"
    for found in trace["discovery"]:
        node = found["id"].upper()
        run = by_id.get(found["id"])
        parts = [
            f'<b>{found["chosen"]}</b>',
            (
                f'{found["catalog_size"]} operations &rarr; {found["candidates"]} '
                "candidates &rarr; chosen"
            ),
        ]
        if run:
            crs = run["crs_decisions"].get("analysis_crs")
            if crs:
                parts.append(f"CRS {_label(crs)}")
            parts.append(f'{run["checks_passed"]}/{run["checks_total"]} checks')
        else:
            # Every step of STEPS is in the plan now, so this is the shape of a
            # step that did not run at all — not a step that ran elsewhere.
            parts.append("did not run")
        lines.append(f'  {node}["{"<br/>".join(parts)}"]')
        lines.append(f"  {previous} --> {node}")
        previous = node

    rows = len(trace["answer"])
    lines.append(f'  OUT[["{rows} parcels, each with elevation and ground area"]]')
    lines.append(f"  {previous} --> OUT")
    lines.append("  classDef bad stroke-dasharray: 4 3")
    lines.append("```")
    return "\n".join(lines)


def _tables(trace: dict[str, Any]) -> str:
    """What was searched, what survived, what ran with which arguments."""
    out = [
        "| what the agent asks for | it declares | candidates | picked | at position |",
        "|---|---|---|---|---|",
    ]
    for found in trace["discovery"]:
        declared = ", ".join(
            f"{value} dataset(s)" if key == "dataset_inputs" else str(value)
            for key, value in found["declared"].items()
        )
        out.append(
            f'| “{found["ask"]}” | {declared} | **{found["candidates"]}** of '
            f'{found["catalog_size"]} | `{found["chosen"]}` | {found["rank_of_chosen"]} |'
        )

    out += [
        "",
        # No timings in the table on purpose: they change on every machine and
        # every run, and a page whose numbers move for no reason trains a reader
        # to stop checking them. They are in the JSON for whoever runs it.
        "| step | operation | arguments that mattered | CRS decision, recorded | checks |",
        "|---|---|---|---|---|",
    ]
    for step in trace["execution"]:
        decision = step["crs_decisions"].get("reason", "—")
        crs = step["crs_decisions"].get("analysis_crs")
        decision = f"`{crs}` — {decision}" if crs else decision
        out.append(
            f'| {step["id"]} | `{step["operation"]}` | {step.get("shown_arguments", "—")} '
            f'| {decision} | {step["checks_passed"]}/{step["checks_total"]} |'
        )
    return "\n".join(out)


def markdown(trace: dict[str, Any]) -> str:
    """The whole section, between markers so a test can compare it to the README."""
    answer = trace["answer"]
    header = "| " + " | ".join(answer[0]) + " |" if answer else ""
    divider = "|" + "---|" * len(answer[0]) if answer else ""
    body = "\n".join(
        "| " + " | ".join(str(v) for v in row.values()) + " |" for row in answer
    )
    last = trace["final_filter"]
    return "\n".join(
        [
            START,
            "",
            _mermaid(trace),
            "",
            _tables(trace),
            "",
            (
                f'Every step is inside the plan, the last one included: '
                f'`{last["operation"]}` took {last["rows_in"]} rows and returned '
                f'{last["rows_out"]}, with a manifest like every other write. '
                f'{last["note"]}'
            ),
            "",
            (
                "**The answer**, which can be worked out on paper before MapSmith sees "
                "the files: the parcels are squares of 0.0015° at 46.2°N, so each is about "
                "119 m by 167 m, and the elevation ramps west to east across the fixture."
            ),
            "",
            header,
            divider,
            body,
            "",
            END,
        ]
    )


def build_trace(workdir: Path) -> dict[str, Any]:
    """Run the whole thing and return what happened, once.

    `main()` renders this and `tests/test_worked_example.py` compares the
    rendering with the README. The test used to rebuild this dictionary by
    hand, which bought nothing — a mistake in here would not have been caught,
    because the test never ran this code — and cost a false failure every time
    the trace changed shape. One copy.
    """
    from mapsmith.plans import executor, models, validator

    paths = build_fixtures(workdir)
    discovery = trace_discovery()
    plan = build_plan(paths, workdir)

    rejected = validator.validate(models.Plan.model_validate(wrong_plan_first(plan)))
    accepted = validator.validate(models.Plan.model_validate(plan))
    result = executor.execute(models.Plan.model_validate(plan))

    steps_run = []
    for step in result.get("steps", []):
        record: dict[str, Any] = {
            "id": step.get("id"),
            "operation": step.get("operation"),
            "elapsed_ms": step.get("elapsed_ms"),
        }
        output = step.get("output_path") or step.get("output")
        manifest_path = Path(f"{output}.provenance.json") if output else None
        if manifest_path and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record["crs_decisions"] = manifest.get("crs_decisions", {})
            # `verification` is a list of checks in the emitted manifest and an
            # object in some older records; read both rather than assume.
            verification = manifest.get("verification", [])
            checks = (
                verification
                if isinstance(verification, list)
                else verification.get("checks", [])
            )
            record["checks_passed"] = sum(1 for c in checks if c.get("passed"))
            record["checks_total"] = len(checks)
            record["checks"] = [c.get("name") for c in checks]
            engine = manifest.get("engine", {})
            record["engine"] = f"{engine.get('name')} {engine.get('version')}"
        steps_run.append(record)

    import geopandas as gpd

    # Every step of the question is inside the plan now, so the last output
    # IS the answer — no reading a file some other code wrote afterwards.
    measured = workdir / "measured.parquet"
    final = workdir / "answer.parquet"
    answer_before = gpd.read_parquet(measured) if measured.exists() else None
    answer = gpd.read_parquet(final) if final.exists() else None

    trace = {
        "goal": (
            "Parcels within 1.5 km of the river whose mean ground elevation is "
            "at most 120 m, with the elevation and the ground area of each"
        ),
        "discovery": discovery,
        "rejected_plan": {
            "valid": rejected.valid,
            "errors": [
                {"code": e.code, "step_id": e.step_id, "message": e.message}
                for e in rejected.errors
            ],
        },
        "accepted_plan": {"valid": accepted.valid, "steps": len(plan["steps"])},
        "execution": steps_run,
        "final_filter": {
            "operation": "select_features",
            "rows_in": len(answer_before) if answer_before is not None else None,
            "rows_out": len(answer) if answer is not None else None,
            "note": (
                "This step used to run outside the plan, because the only "
                "operation that could answer it was run_sql — which takes its "
                "inputs inside a SQL string, declares zero datasets, and therefore "
                "cannot join the plan's dataflow. That boundary is deliberate and "
                "has not moved: substituting `$step` into arbitrary strings would "
                "be a grammar in which a planner assembles a path out of text. "
                "What changed is that it is no longer the only way to ask."
            ),
        },
        "answer": (
            [
                {k: (round(v, 2) if isinstance(v, float) else v)
                 for k, v in row.items() if k != "geometry"}
                for row in answer.drop(columns="geometry").to_dict("records")
            ]
            if answer is not None
            else []
        ),
    }

    # The arguments a reader cares about, taken from the plan rather than
    # retyped: a diagram whose parameters are transcribed is a diagram that
    # can disagree with the run it claims to show.
    shown = {
        step["id"]: ", ".join(
            f"`{k}={v}`"
            for k, v in step["arguments"].items()
            if k not in ("output_path",)
            and not (isinstance(v, str) and v.startswith("/"))
            and not (isinstance(v, str) and ":" in v[:3])
        )
        for step in plan["steps"]
    }
    for step in trace["execution"]:
        step["shown_arguments"] = shown.get(step["id"], "—")

    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write the trace here")
    parser.add_argument("--markdown", action="store_true", help="print the README section")
    parser.add_argument(
        "--write-readme", action="store_true",
        help="replace the section between the markers in README.md",
    )
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="mapsmith-worked-"))
    try:
        trace = build_trace(workdir)
        if args.write_readme:
            readme = ROOT / "README.md"
            page = readme.read_text(encoding="utf-8")
            before, _, rest = page.partition(START)
            _, _, after = rest.partition(END)
            readme.write_text(before + markdown(trace) + after, encoding="utf-8")
            print(f"written: {readme}")
        elif args.markdown:
            print(markdown(trace))
        elif args.json:
            args.json.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
            print(f"written: {args.json}")
        else:
            print(json.dumps(trace, indent=2))
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
