"""Generate the site's figures from real MapSmith outputs.

Nothing on this site is an illustration. Every image is rendered from a dataset
MapSmith produced, and the manifest shown beside it is the one that landed on
disk with it. This script runs in CI, so the pictures cannot quietly drift away
from what the software actually does — which, on a site whose argument is that
you should not have to take an output on trust, is the only defensible way to
make one.

    python site/build.py [output-dir]
"""

from __future__ import annotations

import json
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEM = ROOT / "examples" / "fixtures" / "mount_st_helens_dem.tif"

# Where a reader can follow the project, in one place. Two surfaces name these
# -- the README and this page -- and until 2026-09-04 only the README did, so
# adding a channel meant remembering a file nobody would think to open. The
# test beside this asserts the README lists exactly these, which is what makes
# one place true rather than merely tidy.
UPDATE_CHANNELS = [
    ("LinkedIn", "https://www.linkedin.com/company/mapsmith"),
    ("X", "https://x.com/mapsmith_ai"),
    ("Bluesky", "https://bsky.app/profile/mapsmith.bsky.social"),
]

# Muted, high-contrast, colour-blind safe. Assigned by basin index and never by
# value, so the picture cannot imply an ordering the data does not have — the
# same discipline the manifests apply to numbers.
BASIN_COLOURS = [
    (0xE6, 0x7E, 0x22), (0x27, 0xAE, 0x60), (0x29, 0x80, 0xB9),
    (0x8E, 0x44, 0xAD), (0xC0, 0x39, 0x2B), (0xF1, 0xC4, 0x0F),
]


def run_pipeline(workdir: Path) -> dict[str, Path]:
    """Hillshade and watersheds on a real USGS DEM of Mount St. Helens.

    The same two operations the terrain notebook runs, executed here so the
    figure and its manifest come out of the same process that made them.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import geopandas as gpd
    import rasterio
    from shapely.geometry import Point

    from mapsmith.engines import whitebox_engine

    dem = workdir / "dem.tif"
    shutil.copy(DEM, dem)

    # Where the water actually leaves. A first version put the pour points on a
    # fixed grid, which is defensible and produced almost nothing: most grid
    # positions land on a ridge, and a ridge drains one cell. Flow accumulation
    # says where the drainages are, so the outlets are derived from the terrain
    # instead of asserted over it — and it is a MapSmith operation, so the
    # figure is the product doing a two-step analysis rather than a picture.
    flowacc = workdir / "flowacc.tif"
    whitebox_engine.flow_accumulation(str(dem), str(flowacc))
    outlets_path = workdir / "outlets.gpkg"
    with rasterio.open(flowacc) as ds:
        crs, transform = ds.crs, ds.transform
        outlets = _principal_outlets(ds.read(1, masked=True), transform, count=6)
    gpd.GeoDataFrame(
        {"id": range(1, len(outlets) + 1)},
        geometry=[Point(x, y) for x, y in outlets],
        crs=crs,
    ).to_file(outlets_path, layer="outlets", driver="GPKG")

    hillshade = workdir / "hillshade.tif"
    basins = workdir / "basins.tif"
    whitebox_engine.hillshade(str(dem), str(hillshade))
    whitebox_engine.watershed(str(dem), str(outlets_path), str(basins))
    return {"hillshade": hillshade, "basins": basins, "dem": dem}


def _principal_outlets(accumulation, transform, count: int, separation: int = 60):
    """The `count` highest-accumulation cells, kept `separation` cells apart.

    Without the separation the top cells are all neighbours on one river and
    the result is six nested versions of the same basin. Greedy and
    deterministic: same raster in, same points out, which is what lets the
    figure be a build product rather than a screenshot someone took once.
    """
    import numpy as np

    values = np.ma.filled(accumulation.astype("float64"), -1.0)
    ranked = np.argsort(values, axis=None)[::-1]
    chosen: list[tuple[int, int]] = []
    for flat in ranked:
        row, col = divmod(int(flat), values.shape[1])
        if values[row, col] <= 0:
            break
        if all(max(abs(row - r), abs(col - c)) >= separation for r, c in chosen):
            chosen.append((row, col))
            if len(chosen) == count:
                break
    return [transform * (col + 0.5, row + 0.5) for row, col in chosen]


def png_rgb(pixels: bytes, width: int, height: int) -> bytes:
    """A minimal, deterministic PNG encoder (colour type 2, 8-bit RGB).

    Twenty lines of stdlib instead of a dependency, and deterministic byte for
    byte — which matters because this file is a build product: two builds of the
    same commit produce the same image, so the site cannot drift from the data
    without a diff saying so. `preview.py` carries a sibling of this for
    grayscale-plus-alpha; they stay apart because one is a product feature with
    a lifetime and the other is a page.
    """

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(
        b"\x00" + pixels[y * width * 3:(y + 1) * width * 3] for y in range(height)
    )
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def render(hillshade: Path, basins: Path, destination: Path) -> tuple[int, int]:
    """Shaded relief with the watersheds tinted over it.

    Rendered from the arrays rather than through a plotting library, so what is
    on the page is the pixels of the data: no axes, no resampling the reader
    cannot see, no colour ramp doing work the data does not support. Served at
    native resolution for the same reason — upscaling a terrain image invents
    detail, which would be a strange thing to do on this particular site.
    """
    import numpy as np
    import rasterio

    with rasterio.open(hillshade) as ds:
        shade = ds.read(1, masked=True).astype("float32")
    with rasterio.open(basins) as ds:
        basin_data = ds.read(1, masked=True)

    low, high = float(shade.min()), float(shade.max())
    grey = (shade - low) / (high - low) if high > low else shade * 0
    grey = np.ma.filled(grey, 0.0)
    # Lift the black end: pure black hides the terrain in the shadows, which is
    # exactly where the watershed boundaries are most worth seeing.
    canvas = np.stack([0.09 + 0.88 * grey] * 3, axis=-1)

    for index, colour in enumerate(BASIN_COLOURS, start=1):
        mask = np.ma.filled(basin_data == index, False)
        if not mask.any():
            continue
        tint = np.array(colour, dtype="float32") / 255.0
        # Multiply rather than paint over: an overlay that hid the shading would
        # be decoration, and the relief is the evidence.
        canvas[mask] = canvas[mask] * 0.42 + tint * 0.58

    height, width = canvas.shape[:2]
    raw = (np.clip(canvas, 0, 1) * 255).astype("uint8").tobytes()
    destination.write_bytes(png_rgb(raw, width, height))
    return width, height


def _escape(value) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _beat_body(beat: dict) -> str:
    """The content of one beat, by kind.

    Every value here came out of an execution performed during this build. The
    rendering decides how it looks and never what it says: a beat with nothing
    in it renders as nothing, rather than as a reassuring sentence.
    """
    kind, out = beat["kind"], []
    if text := beat.get("text"):
        out.append(f'<p class="ask">{_escape(text)}</p>')
    if kind == "discovery":
        declared = ", ".join(
            f"{_escape(k)}={_escape(v)}" for k, v in (beat.get("declared") or {}).items()
        )
        out.append(
            f'<p class="figure"><b>{beat.get("catalogue")}</b> operations in the catalogue '
            f'&rarr; <b>{beat.get("candidates")}</b> still applicable once the caller '
            f"declares what it has: <code>{declared}</code></p>"
        )
        if chosen := beat.get("chosen"):
            out.append(f'<p>Chosen: <code>{_escape(chosen)}</code></p>')
        if says := beat.get("distinguishes"):
            out.append(f'<p class="quiet">{_escape(says)}</p>')
    elif kind == "refused":
        for error in beat.get("errors") or []:
            out.append(
                f'<p class="bad"><code>{_escape(error.get("code"))}</code> '
                f'{_escape(error.get("message"))}</p>'
            )
        if message := beat.get("message"):
            out.append(f'<pre class="block bad">{_escape(message)}</pre>')
    elif kind == "inspect":
        rows = "".join(
            f"<tr><td><code>{_escape(k)}</code></td><td>{_escape(v)}</td></tr>"
            for k, v in (beat.get("georeferencing") or {}).items()
        )
        out.append(f'<table class="tools"><tbody>{rows}</tbody></table>')
    elif kind == "ran":
        passed, total = beat.get("checks_passed"), beat.get("checks_total")
        out.append(
            f'<p class="figure">engine <code>{_escape(beat.get("engine"))}</code> '
            f'&middot; CRS <code>{_escape(beat.get("crs"))}</code> '
            f'&middot; <b>{passed}/{total}</b> checks passed</p>'
        )
        if reason := beat.get("reason"):
            out.append(f'<p class="quiet">{_escape(reason)}</p>')
        if names := beat.get("checks"):
            out.append(
                '<p class="quiet">'
                + ", ".join(f"<code>{_escape(n)}</code>" for n in names)
                + "</p>"
            )
    elif kind == "lineage":
        out.append(f'<p class="figure">{_escape(beat.get("summary"))}</p>')
        rows = "".join(
            f'<tr><td style="padding-left:{step["depth"]}rem">'
            f'<code>{_escape(step["operation"])}</code></td>'
            f'<td>{step["checks"]} checks</td>'
            f'<td>{_escape(step["claim"])}</td></tr>'
            for step in beat.get("steps") or []
        )
        out.append(f'<table class="tools"><tbody>{rows}</tbody></table>')
    elif kind == "answer" and (rows := beat.get("rows")):
        out.append(f'<pre class="block">{_escape(rows)}</pre>')
    if note := beat.get("note"):
        out.append(f'<p class="quiet">{_escape(note)}</p>')
    return "".join(out)


def playground_html(cases: list[dict]) -> str:
    """The cases, rendered so they read with JavaScript off and step with it on.

    Progressive on purpose. This page has never carried a line of script and its
    whole argument is that nothing on it is drawn: a visitor with JS disabled,
    or a reader on a mirror, must still see every beat of every case. The script
    only hides beats and puts a button under them.
    """
    blocks = []
    for case in cases:
        beats = "".join(
            f'<li class="beat" data-kind="{_escape(beat["kind"])}">'
            f'<h4>{_escape(beat["title"])}</h4>{_beat_body(beat)}</li>'
            for beat in case["beats"]
        )
        blocks.append(
            f'<section class="case" id="case-{_escape(case["id"])}">'
            f'<p class="kicker">{_escape(case["point"])}</p>'
            f'<ol class="beats">{beats}</ol></section>'
        )
    return "\n".join(blocks)


def worked_example_html() -> str:
    """The end-to-end example, rendered from a run performed during this build.

    Same source as the README section: `benchmarks/worked_example.py` builds the
    fixtures, validates a deliberately mis-ordered plan, runs the correct one and
    reads the manifests. Rendering it here rather than copying the markdown keeps
    one execution behind two surfaces — the failure mode this site has already
    had twice is a number that is true on one page and stale on the other.
    """
    import shutil
    import tempfile

    sys.path.insert(0, str(ROOT / "benchmarks"))
    import worked_example as example

    from mapsmith.plans import executor, models, validator

    workdir = Path(tempfile.mkdtemp(prefix="mapsmith-site-example-"))
    try:
        paths = example.build_fixtures(workdir)
        plan = example.build_plan(paths, workdir)
        rejected = validator.validate(
            models.Plan.model_validate(example.wrong_plan_first(plan))
        )
        result = executor.execute(models.Plan.model_validate(plan))

        rows = []
        by_id = {step["id"]: step for step in result.get("steps", [])}
        for found, step in zip(example.STEPS, example.trace_discovery(), strict=True):
            run = by_id.get(found["id"])
            # Every step of the worked example is inside the plan now, so this
            # is the shape of a step that did not run at all — not one that ran
            # elsewhere. `benchmarks/worked_example.py` says the same thing.
            crs, checks = "—", "did not run"
            if run:
                output = run.get("output_path") or run.get("output")
                manifest = Path(f"{output}.provenance.json")
                if manifest.exists():
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    decisions = data.get("crs_decisions", {})
                    crs = decisions.get("analysis_crs", "—")
                    marks = data.get("verification", [])
                    marks = marks if isinstance(marks, list) else marks.get("checks", [])
                    passed = sum(1 for c in marks if c.get("passed"))
                    checks = f"{passed}/{len(marks)}"
            arguments = ", ".join(
                f"{k}={v}"
                for k, v in next(
                    (s["arguments"] for s in plan["steps"] if s["id"] == found["id"]), {}
                ).items()
                if k not in ("output_path", "input_path", "raster_path")
                and not str(v).startswith(("/", "C:", "D:"))
            )
            rows.append(
                "<tr>"
                f"<td>&ldquo;{step['ask']}&rdquo;</td>"
                f"<td class=\"num\">{step['candidates']}</td>"
                f"<td><code>{step['chosen']}</code>"
                + (f"<br><small>{arguments}</small>" if arguments else "")
                + "</td>"
                f"<td><small>{crs}</small></td>"
                f"<td class=\"num\">{checks}</td>"
                "</tr>"
            )

        message = rejected.errors[0].message if rejected.errors else ""
        return (
            '  <table class="tools" style="margin-top:1.25rem">\n'
            "    <thead><tr><th>what the agent asks for</th>"
            '<th class="num">candidates</th><th>picked, and with what</th>'
            '<th>CRS decision, recorded</th><th class="num">checks</th></tr></thead>\n'
            "    <tbody>\n      " + "\n      ".join(rows) + "\n    </tbody>\n"
            "  </table>\n"
            '  <p class="pull" style="margin-top:1.5rem">'
            "The same plan with two steps swapped never ran.<br>"
            f"<em>{message}</em></p>\n"
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def highlight(value, indent: int = 0) -> str:
    """The manifest as coloured, escaped HTML — the real one, not a sample.

    Emitted from the parsed object rather than by running regular expressions
    over pretty-printed text. The first version did the latter and produced no
    highlighting at all, because `html.escape` had already turned every quote
    into `&quot;` and none of the patterns matched any more. Walking the data
    cannot have that class of bug: the escaping happens at the leaves, where the
    text actually is.

    Rendered at build time rather than fetched by script, because the evidence
    on a page arguing for checkable evidence should not need JavaScript to
    appear.
    """
    import html
    import re

    pad, inner = "  " * indent, "  " * (indent + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = [
            f'{inner}"<span class="k">{html.escape(str(k))}</span>": '
            f"{highlight(v, indent + 1)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(rows) + f"\n{pad}}}"
    if isinstance(value, list):
        if not value:
            return "[]"
        rows = [f"{inner}{highlight(v, indent + 1)}" for v in value]
        return "[\n" + ",\n".join(rows) + f"\n{pad}]"
    if value is None:
        return '<span class="hash">null</span>'
    if isinstance(value, bool):
        return f'<span class="b">{"true" if value else "false"}</span>'
    if isinstance(value, (int, float)):
        return f'<span class="n">{value}</span>'
    text = html.escape(str(value))
    # A checksum gets its own class so it can recede without being hidden: it is
    # the point of the record, but it is not what the eye should land on first.
    cls = "hash" if re.fullmatch(r"[0-9a-f]{64}", str(value)) else "s"
    return f'"<span class="{cls}">{text}</span>"'


CHANGELOG_UNRELEASED = "https://github.com/mapsmith-ai/MapSmith/blob/main/CHANGELOG.md#unreleased"


def unreleased_html(changelog: str, version: str) -> str:
    """The sentence the page promises when `main` runs ahead of the release.

    The template has said since 0.3.0 that "when main runs ahead of the
    published artifact this paragraph says so and names the difference", and
    nothing rendered it: on 2026-09-25, between the fixes and the tag, the page
    said "this page describes 0.5.1" beside 76 operations, one of which 0.5.1
    does not have, and a manifest in a format 0.5.1 does not write.

    Read from `[Unreleased]` rather than from the commits since the tag: the
    Pages checkout is shallow and has no tags, and a commit that touches only
    documentation changes nothing for somebody installing. The difference is
    named by the lead sentence of each entry, which is what the changelog's
    own format puts in bold.
    """
    import html
    import re

    if "## [Unreleased]" not in changelog:
        raise RuntimeError("CHANGELOG.md has no [Unreleased] section to read")
    section = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]

    def inline(text: str) -> str:
        text = html.escape(" ".join(text.split()))
        return re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    # Each lead with the heading it sits under. A "Fixed" entry's lead names
    # the DEFECT ("...had its seam in the wrong place"), and listed bare under
    # "what the release does not have" it read as though main had the defect --
    # found on the live page by the 0.6.1 pre-release showcase review.
    items = []
    for block in re.split(r"^### ", section, flags=re.MULTILINE)[1:]:
        heading, _, body = block.partition("\n")
        for lead in re.findall(r"^- \*\*(.+?)\*\*", body, flags=re.MULTILINE | re.DOTALL):
            items.append(f"<li>{html.escape(heading.strip())}: {inline(lead)}</li>")
    if not items:
        return ""
    return (
        '<p style="font-size:0.94rem;color:var(--ink-soft)">'
        f"<strong><code>main</code> is ahead of {html.escape(version)} today</strong>, "
        "and this page is built from it. What it changes against the installable "
        f"release:</p><ul style=\"font-size:0.94rem;color:var(--ink-soft)\">{''.join(items)}</ul>"
        f'<p style="font-size:0.94rem;color:var(--ink-soft)">Each with what was '
        f'measured: <a href="{CHANGELOG_UNRELEASED}">[Unreleased] in the changelog</a>.</p>'
    )


def _git(*args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=False,
    ).stdout.strip()


def strip_workdir(manifest: dict, workdir: Path) -> dict:
    """The manifest with every mention of the build's temporary directory removed.

    Done on the serialised text, so a path in any field -- inputs, output, a
    note -- goes, including one added by a later version of the format.
    """
    text = json.dumps(manifest)
    for prefix in {workdir.as_posix(), str(workdir), str(workdir.resolve()), workdir.resolve().as_posix()}:
        for spelled in (prefix, json.dumps(prefix)[1:-1]):
            text = text.replace(spelled + "/", "").replace(spelled + "\\\\", "")
    return json.loads(text)


def main(destination: Path) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mapsmith-site-") as tmp:
        workdir = Path(tmp)
        outputs = run_pipeline(workdir)
        dims = render(outputs["hillshade"], outputs["basins"], destination / "terrain.png")
        manifest = json.loads(
            Path(str(outputs["basins"]) + ".provenance.json").read_text(encoding="utf-8")
        )

    # Published as it was written, with only the temporary directory stripped.
    # The reader is meant to check this file, not admire it, so nothing else
    # about it is touched. Stripped EVERYWHERE, not field by field: until
    # 2026-09-26 only the input paths were, and `output.path` went live as
    # `/tmp/mapsmith-site-xxxx/basins.tif` -- and, built on a workstation, as a
    # path carrying the user's home directory.
    manifest = strip_workdir(manifest, workdir)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    # The steppable cases, every one executed here, in its own directory so a
    # case cannot read a file another case wrote. `build` raises rather than
    # returning a case that failed: a page of examples quietly missing the one
    # that broke is worse than a page with fewer examples.
    sys.path.insert(0, str(ROOT / "benchmarks"))
    import playground

    with tempfile.TemporaryDirectory(prefix="mapsmith-cases-") as tmp:
        cases = playground.build(Path(tmp))["cases"]

    sys.path.insert(0, str(ROOT / "src"))
    from mapsmith import __version__

    # Counted from the source, never typed into the page. This number was wrong
    # in our own notes once — 54 instead of 16 — because someone counted regex
    # hits, and a claim on a front page has to be produced the same way a result
    # is. Exposed MCP tools, not catalogue entries: the sentence next to it is
    # about what an agent has to choose between.
    tool_count = (ROOT / "src" / "mapsmith" / "server.py").read_text(
        encoding="utf-8"
    ).count("@mcp.tool(")
    # Test *functions*, which is what the page says, and deliberately not what
    # `pytest -q` prints. Parametrisation expands these into more cases (456 at
    # the time of writing against 303 functions), and asking pytest for the
    # bigger number would make the front page depend on which optional extras
    # the build machine happens to have: every module guarded by
    # `importorskip` drops out of collection. A number on this page has to come
    # out the same on any checkout, so it is counted from the source and
    # labelled for what it is.
    test_count = sum(
        int(row.rsplit(":", 1)[1])
        for row in _git("grep", "-c", "^def test_", "--", "tests/").splitlines()
    )
    # Catalogue entries, which is a different claim from exposed tools and the
    # one the discovery section is about: capability count has no ceiling, the
    # count an agent chooses between does.
    from mapsmith import catalog

    catalog_count = len(catalog.OPERATIONS)
    # Argleton's numbers cannot be counted from this checkout: it is a separate
    # repository in a separate organisation, on purpose. So they are vendored in
    # `docs/argleton-run.json`, written by the publish script as one step of
    # publishing a run, and the page reads them from there rather than carrying
    # them as prose. Hand-typed, this one aged three times in four days.
    argleton = json.loads(
        (ROOT / "docs" / "argleton-run.json").read_text(encoding="utf-8")
    )

    page = (Path(__file__).parent / "index.template.html").read_text(encoding="utf-8")
    for placeholder, value in {
        "{{MANIFEST}}": highlight(manifest),
        # Before {{VERSION}}: the sentence it renders names the version too.
        "{{AHEAD}}": unreleased_html(
            (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), __version__
        ),
        "{{VERSION}}": __version__,
        "{{TOOL_COUNT}}": str(tool_count),
        "{{CATALOG_COUNT}}": str(catalog_count),
        "{{TEST_COUNT}}": str(test_count),
        "{{TRAP_COUNT}}": str(argleton["traps_run"]),
        "{{SILENT_ERRORS}}": f"{argleton['mapsmith_silent_error_rate']:.2f}",
        "{{NAIVE_SILENT_ERRORS}}": f"{argleton['naive_silent_error_rate']:.4f}",
        "{{COMMIT}}": _git("rev-parse", "--short", "HEAD") or "unknown",
        "{{WORKED_EXAMPLE}}": worked_example_html(),
        "{{PLAYGROUND}}": playground_html(cases),
        "{{BUILT}}": manifest["finished_at"][:10],
        "{{UPDATE_CHANNELS}}": " · ".join(
            f'<a href="{url}">{name}</a>' for name, url in UPDATE_CHANNELS
        ),
    }.items():
        page = page.replace(placeholder, value)
    leftovers = [s for s in ("{{",) if s in page]
    if leftovers:
        raise RuntimeError(f"unreplaced placeholder in the template: {page[page.index('{{'):][:40]}")
    (destination / "index.html").write_text(page, encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    (destination / "CNAME").write_text("mapsmith.dev\n", encoding="utf-8")

    weight = (destination / "terrain.png").stat().st_size
    checks = manifest["verification"]
    print(
        f"terrain.png {dims[0]}x{dims[1]} {weight // 1024} KB | "
        f"manifest.json {len(checks)} checks, "
        f"{sum(c['passed'] for c in checks)} passed | "
        f"engine {manifest['engine']['name']} {manifest['engine']['version']} | "
        f"{tool_count} tools, {catalog_count} catalogue entries, "
        f"{test_count} test functions | index.html "
        f"{(destination / 'index.html').stat().st_size // 1024} KB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(
        main(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "site" / "generated"))
    )
