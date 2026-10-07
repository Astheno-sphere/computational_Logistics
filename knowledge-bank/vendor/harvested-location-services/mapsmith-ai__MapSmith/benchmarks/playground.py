"""The cases a visitor can step through on the site, each one really executed.

The site already renders one analysis end to end, as a table and a diagram, from
a run performed during the build. This turns that into something a reader
*advances through* — one beat at a time, seeing what was searched, what was
refused, what ran, what each step recorded, and how the whole chain is recovered
afterwards from the final file alone.

**Why the visitor does not upload a file, which is the obvious design.** Running
GDAL on arbitrary files from strangers is one of the most heavily exploited
surfaces there is, and this project tells its users to run MapSmith inside a
workspace jail for that reason: a public upload endpoint would break the
assumption `SECURITY.md` names — a single trusted writer of the filesystem — at
its root. Choosing the question instead of the data keeps every execution here
one that happened on this machine, during the build, on fixtures whose answer is
worked out on paper.

**Everything shown was executed.** No beat is written by hand: the discovery
counts come from the catalogue, the refusals from the validator and the engines,
the checks from the manifests, and the recovered chain from `get_lineage`
walking real digests. If a step changes, the page changes with it — and if a
case stops running, the build fails rather than rendering a stale picture.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _beat(kind: str, title: str, **fields: Any) -> dict[str, Any]:
    """One thing the visitor advances to.

    `kind` drives the rendering; everything else is the content of that beat.
    Keeping them in one flat list rather than a per-case shape is what lets the
    page be written once for every case, including cases added later.
    """
    return {"kind": kind, "title": title, **fields}


# ------------------------------------------------------------------ case 1


def analysis(workdir: Path) -> dict[str, Any]:
    """A whole question, from the words to the answer, and back again.

    Reuses `worked_example.build_trace` rather than re-running the same thing a
    second way: two scripts building one analysis is how a page ends up showing
    a run nobody performed. The beats add what the trace does not carry — the
    walk back up the chain, which is the part that only exists since
    `get_lineage`.
    """
    import worked_example as example

    from mapsmith.lineage import lineage

    trace = example.build_trace(workdir)
    beats = [
        _beat(
            "question",
            "Somebody asks a question, in the words of the problem",
            text=trace["goal"],
            note=(
                "Not the name of a tool. The caller does not know what a "
                "buffer is called here, and should not have to."
            ),
        )
    ]

    for found in trace["discovery"]:
        beats.append(
            _beat(
                "discovery",
                f"What could answer “{found['ask']}”",
                catalogue=found.get("catalog_size"),
                candidates=found.get("candidates"),
                declared=found.get("declared"),
                response=found.get("response"),
                chosen=found.get("chosen"),
                distinguishes=found.get("distinguishes"),
                why=found.get("why"),
                note=(
                    "Narrowed on facts the caller already has — what data is in "
                    "hand, what should come back, how many datasets — and then "
                    "handed over whole. Below thirty survivors nothing is ranked "
                    "away: the answer is in what comes back, by construction."
                ),
            )
        )

    rejected = trace["rejected_plan"]
    beats.append(
        _beat(
            "refused",
            "A plan is submitted with two steps the wrong way round",
            errors=rejected["errors"],
            note=(
                "Refused before anything ran. Nothing was written, so there is "
                "nothing to clean up and no half-finished dataset to mistake "
                "for a result."
            ),
        )
    )

    for step in trace["execution"]:
        beats.append(
            _beat(
                "ran",
                f"{step['operation']}",
                engine=step.get("engine"),
                crs=(step.get("crs_decisions") or {}).get("analysis_crs"),
                reason=(step.get("crs_decisions") or {}).get("reason"),
                checks_passed=step.get("checks_passed"),
                checks_total=step.get("checks_total"),
                checks=step.get("checks"),
                elapsed_ms=step.get("elapsed_ms"),
            )
        )

    beats.append(
        _beat(
            "answer",
            "The answer, which was worked out on paper before any of this ran",
            rows=trace.get("answer"),
            note=trace.get("answer_note"),
        )
    )

    # The part that did not exist before `get_lineage`: from the final file's
    # bytes alone, with no filename read to decide what came before it.
    final = workdir / "answer.parquet"
    if final.exists():
        recovered = lineage(final, scan_root=workdir)
        beats.append(
            _beat(
                "lineage",
                "And from that file alone, the whole analysis comes back",
                summary=recovered["summary"],
                steps=[
                    {
                        "operation": s["operation"],
                        "depth": s["depth"],
                        "claim": s["claim"],
                        "checks": s["verification"]["checks"],
                        "failed": s["verification"]["failed"],
                    }
                    for s in recovered["steps"]
                ],
                stopped=[
                    {"reason": s["reason"], "path": s["path"]}
                    for s in recovered["stopped_at"]
                ],
                verified=recovered["verified"],
                note=(
                    "No field points at another record. The file is hashed, the "
                    "manifest claiming those exact bytes is found, and every "
                    "input digest is followed back — so the chain survives a "
                    "rename and breaks only when the data changes."
                ),
            )
        )
    return {
        "id": "analysis",
        "question": trace["goal"],
        "point": "What a whole analysis looks like, and what it leaves behind.",
        "beats": beats,
    }


# ------------------------------------------------------------------ case 2

#: A raster that carries its georeferencing twice, disagreeing. This is Argleton
#: trap 030, and it is the shape of the failure this product exists for: nothing
#: about the file looks wrong, every tool reads it, and the numbers that come out
#: depend on which of the two readings the library happened to prefer.
_SIDECAR_XML = """<PAMDataset>
  <SRS>EPSG:32610</SRS>
  <GeoTransform>{ox}, {cell}, 0.0, {oy}, 0.0, -{cell}</GeoTransform>
</PAMDataset>
"""
_INTERNAL = (500000.0, 5030000.0, 10.0)
_SIDECAR = (600000.0, 5040000.0, 20.0)
_CRS = "EPSG:32610"
_SIZE = 40


def refusal(workdir: Path) -> dict[str, Any]:
    """A file that looks perfectly fine, and is refused with the reason.

    Everybody demonstrates a success. The distinctive thing this product does is
    decline: this raster carries a georeferencing in its own tags and another in
    the sidecar beside it, they disagree, and GDAL silently prefers the sidecar.
    A number would come back. It would be wrong by a hundred kilometres, and the
    record could not say which reading produced it.
    """
    import geopandas as gpd
    import numpy as np
    import rasterio
    from affine import Affine
    from shapely.geometry import Point

    from mapsmith.engines import dispatch, sampling

    terrain = workdir / "terrain.tif"
    origin_x, origin_y, cell = _INTERNAL
    with rasterio.open(
        terrain, "w", driver="GTiff", height=_SIZE, width=_SIZE, count=1,
        dtype="float32", crs=_CRS,
        transform=Affine(cell, 0.0, origin_x, 0.0, -cell, origin_y),
    ) as destination:
        destination.write(np.tile(np.arange(_SIZE, dtype="float32"), (_SIZE, 1)), 1)
    sidecar_x, sidecar_y, sidecar_cell = _SIDECAR
    Path(f"{terrain}.aux.xml").write_text(
        _SIDECAR_XML.format(ox=sidecar_x, oy=sidecar_y, cell=sidecar_cell),
        encoding="utf-8",
        newline="\n",
    )

    wells = workdir / "wells.parquet"
    gpd.GeoDataFrame(
        {"name": ["Well A", "Well B"]},
        geometry=[
            Point(origin_x + 5 * cell, origin_y - 5 * cell),
            Point(origin_x + 12 * cell, origin_y - 9 * cell),
        ],
        crs=_CRS,
    ).to_parquet(wells)

    described = dispatch.describe_routed(str(terrain))
    # `georeferencing`, and it is the whole point of the beat: describing the
    # file already names both readings and says which one GDAL will use. The
    # refusal below is not MapSmith noticing something obscure -- it is MapSmith
    # declining to proceed on something it has already told the caller about.
    georeferencing = dict(described.get("georeferencing") or {})
    assert georeferencing, (
        "describe_dataset reported no georeferencing block for a raster carrying "
        "two of them; this case renders that block, and an empty one would show "
        "a beat that claims an inspection nobody performed"
    )

    beats = [
        _beat(
            "question",
            "Somebody asks a question, in the words of the problem",
            text="How high is the ground at each of these two wells?",
            note=(
                "An ordinary question, on a raster that opens in every viewer "
                "and looks like terrain."
            ),
        ),
        _beat(
            "inspect",
            "The file is inspected before it is used",
            georeferencing=georeferencing,
            note=(
                "Section 3.8 of the manifest format calls this the configuration "
                "that changes the answer and lives neither in the data nor in "
                "the call. Here it is inside the file, twice, and the two copies "
                "disagree."
            ),
        ),
    ]

    try:
        sampling.sample_raster_at_points(
            str(terrain), str(wells), str(workdir / "sampled.parquet"), "nearest"
        )
        raise AssertionError(
            "sample_raster_at_points accepted a doubly georeferenced raster; this "
            "case exists to show the refusal, and rendering it as a success would "
            "publish a claim this product does not keep"
        )
    except ValueError as refused:
        beats.append(
            _beat(
                "refused",
                "MapSmith declines, and says what it would have had to guess",
                # The file NAME, not the path it happened to be built under.
                # Stripping the temporary directory left the separator behind,
                # so this block came out `…\terrain.tif` on Windows and
                # `…/terrain.tif` on Linux -- a build product that differs by
                # host, which is the defect this project fixed once already in
                # the manifests themselves (issue #30) turning up in a page.
                message=str(refused).replace(str(terrain), terrain.name),
                note=(
                    "The two readings put the same cell a hundred kilometres "
                    "apart and at twice the size. GDAL prefers the sidecar, which "
                    "is correct — that is what an override is for — so a number "
                    "would have come back, from a file nobody named."
                ),
            )
        )

    beats.append(
        _beat(
            "point",
            "This is the failure the product exists for",
            note=(
                "No crash, no warning, no exception: that is what happens "
                "everywhere else. A plausible elevation, from the wrong grid, "
                "with a record that could not say which. Refusing costs the "
                "caller one decision; the alternative costs them the answer and "
                "never tells them."
            ),
        )
    )
    return {
        "id": "refusal",
        "question": "How high is the ground at each of these two wells?",
        "point": "What it refuses, and why that is the feature.",
        "beats": beats,
    }


START = "<!-- cases:start -->"
END = "<!-- cases:end -->"


def markdown(cases: list[dict[str, Any]]) -> str:
    """The two beats a README can carry that the worked example above does not.

    GitHub runs nothing, so the steppable version lives on the site and this is
    its residue: the refusal, and the chain recovered from one file. They are
    the two things a reader cannot get from the table already on that page --
    one shows what MapSmith declines to answer, the other shows an analysis
    coming back out of bytes.

    Generated from the same execution the site renders, and a test regenerates
    it and fails on any difference. That is the only reason it can still be
    trusted after the fourth time somebody edits the prose around it.
    """
    by_id = {case["id"]: case for case in cases}
    out = [START, ""]

    refusal_case = by_id["refusal"]
    inspected = next(b for b in refusal_case["beats"] if b["kind"] == "inspect")
    refused = next(b for b in refusal_case["beats"] if b["kind"] == "refused")
    out += [
        "**What it declines to answer.** Asked "
        f"*“{refusal_case['question']}”* against a GeoTIFF that opens in every viewer:",
        "",
        "| describing the file first | |",
        "|---|---|",
    ]
    for key, value in inspected["georeferencing"].items():
        out.append(f"| `{key}` | {value} |")
    out += [
        "",
        "```",
        refused["message"],
        "```",
        "",
        "A number would have come back. It would have been read off a grid a hundred",
        "kilometres away and at twice the cell size, with nothing in the record able to",
        "say which of the two readings produced it.",
        "",
    ]

    walk = next(b for b in by_id["analysis"]["beats"] if b["kind"] == "lineage")
    out += [
        "**And the analysis comes back out of the file.** Given only the last output of the",
        "five-step run above — no plan, no filenames, no field pointing at another record",
        "— the chain is recovered by hashing it and following every input digest back:",
        "",
        "```",
        walk["summary"],
    ]
    for step in walk["steps"]:
        out.append(f"{'  ' * step['depth']}<- {step['operation']:18} {step['checks']} checks")
    for stop in walk["stopped"]:
        name = Path(stop["path"]).name if stop["path"] else ""
        out.append(f"   ({stop['reason']}) {name}")
    out += ["```", "", END]
    return "\n".join(out)


CASES = (analysis, refusal)


def build(workdir: Path) -> dict[str, Any]:
    """Every case, executed. Raises rather than returning a case that did not run.

    A page of examples that silently drops the one that broke is worse than a
    page with fewer examples: the reader cannot tell the difference, and the
    missing one is always the interesting one.
    """
    cases = []
    for case in CASES:
        directory = workdir / case.__name__
        directory.mkdir(parents=True, exist_ok=True)
        cases.append(case(directory))
    return {"cases": cases}


def main() -> int:
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write the cases here")
    parser.add_argument(
        "--write-readme", action="store_true",
        help="replace the section between the markers in README.md",
    )
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="mapsmith-playground-") as tmp:
        data = build(Path(tmp))
    text = json.dumps(data, indent=2, default=str)
    if arguments.write_readme:
        readme = ROOT / "README.md"
        page = readme.read_text(encoding="utf-8")
        before, _, rest = page.partition(START)
        _, _, after = rest.partition(END)
        readme.write_text(before + markdown(data["cases"]) + after, encoding="utf-8")
        print(f"written: {readme}")
    elif arguments.json:
        arguments.json.write_text(text + "\n", encoding="utf-8")
        print(f"written: {arguments.json}")
    else:
        for case in data["cases"]:
            print(f"\n=== {case['id']}: {case['question']}")
            for index, beat in enumerate(case["beats"], 1):
                print(f"  {index:2}. [{beat['kind']}] {beat['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
