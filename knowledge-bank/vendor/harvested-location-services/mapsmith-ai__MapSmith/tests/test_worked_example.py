"""The worked example on the README is a recording, and this is what keeps it one.

A diagram is the easiest thing in a repository to lie with. It costs nothing to
draw a step that does not happen, an argument nobody passes or a check nobody
runs, and no reader can tell. So the section between the markers is written by
`benchmarks/worked_example.py` from an actual execution — fixtures built, plan
validated, operations run, manifests read — and this test rebuilds it and
compares. If the catalogue changes, if an operation stops recording a CRS
decision, if the validator's message moves, the README goes stale and the build
says so instead of a reader finding out.

Slow, because it is the real pipeline: buffer, clip, zonal statistics, area and
the attribute filter, over fixtures written to disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
sys.path.insert(0, str(ROOT / "benchmarks"))

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def section() -> str:
    """Regenerate the README section from a real run.

    It calls the script's own `build_trace` rather than rebuilding the trace
    here. This fixture used to hold a second copy of that code — same
    execution, same dictionary, retyped — and the copy bought nothing: a
    mistake inside `build_trace` could not be caught by a test that never ran
    it. What it cost was a false failure every time the trace changed shape,
    which is what happened on 2026-08-29 when the last step moved inside the
    plan.
    """
    import shutil
    import tempfile

    import worked_example as example

    workdir = Path(tempfile.mkdtemp(prefix="mapsmith-worked-test-"))
    try:
        return example.markdown(example.build_trace(workdir))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def test_the_readme_worked_example_is_what_a_real_run_produces(section):
    """Byte-for-byte, because every difference here is a page describing a run
    that did not happen. Regenerate with:

        python benchmarks/worked_example.py --write-readme
    """
    import worked_example as example

    prose = README.read_text(encoding="utf-8")
    assert example.START in prose and example.END in prose, (
        "the worked-example markers are gone from the README, so nothing is "
        "keeping that section attached to a run"
    )
    published = example.START + prose.split(example.START, 1)[1].split(example.END, 1)[0]
    published += example.END
    assert published.strip() == section.strip(), (
        "the worked example on the README is not what the script produces now. "
        "Run `python benchmarks/worked_example.py --write-readme` and read the diff "
        "before committing it: what changed in the product is in there."
    )


def test_the_example_answer_matches_what_the_fixture_makes_it(section):
    """The fixture is built so the answer can be stated before MapSmith runs.

    Squares of 0.0015° at 46.2°N are about 115.6 m by 166.7 m, so 19,270 m²
    against a geodesic measurement; elevation is a linear west-to-east ramp, so
    which parcels fall under the threshold is arithmetic. If a change ever makes
    the run disagree with that arithmetic, the run is wrong, not the arithmetic.
    """
    import worked_example as example

    span = example.DEM_EAST_LON - example.DEM_WEST_LON
    rise = example.DEM_EAST_M - example.DEM_WEST_M
    expected = []
    for name, offset in example.PARCELS:
        centre = example.RIVER_LON + offset + example.PARCEL_SIDE / 2
        elevation = example.DEM_WEST_M + (centre - example.DEM_WEST_LON) / span * rise
        # Inclusive, because that is what `field_between` does. The strict
        # form agreed with it only because no parcel sits exactly on 120.
        if elevation <= example.ELEVATION_LIMIT_M:
            expected.append((name, elevation))

    answer_table = section.split("| name |", 1)[1] if "| name |" in section else section
    for name, elevation in expected:
        assert name in answer_table, (
            f"{name} sits at {elevation:.0f} m, at or under the {example.ELEVATION_LIMIT_M} m "
            "threshold, and is not in the published answer"
        )
    # The exclusions are the half that matters: a filter that drops nothing looks
    # exactly like a filter that works.
    kept = {name for name, _ in expected}
    for name, offset in example.PARCELS:
        if name in kept:
            continue
        centre = example.RIVER_LON + offset + example.PARCEL_SIDE / 2
        elevation = example.DEM_WEST_M + (centre - example.DEM_WEST_LON) / span * rise
        assert name not in answer_table, (
            f"{name} sits at {elevation:.0f} m, above the {example.ELEVATION_LIMIT_M} m "
            "threshold, and is in the published answer anyway"
        )
    # ~19,270 m² by hand; the published figure is geodesic, so allow the ellipsoid
    # its say but not a different order of magnitude.
    assert "1930" in section or "1927" in section, (
        "the published areas are no longer near the 19,270 m² the fixture geometry "
        "implies for a 0.0015° square at this latitude"
    )


# Word-numbers in the prose that describes the generated block, checked against the
# block itself. They are outside the markers, so nothing regenerates them: a reader
# meets "five operations and forty-eight checks" in the opening and has no way to
# know the table underneath has moved on. The suite has been bitten by exactly this
# once already, on 2026-09-02, when a page whose only job was to bound a claim was
# published with four false sentences about its own counts while two guards watched
# other phrasings. So the numbers are derived here and the sentence has to agree.
WORDS = {
    3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve",
}
TENS = {40: "forty", 50: "fifty", 60: "sixty", 70: "seventy"}


def _spell(number: int) -> str:
    if number in WORDS:
        return WORDS[number]
    tens, units = divmod(number, 10)
    if tens * 10 in TENS and units:
        return f"{TENS[tens * 10]}-{WORDS[units]}"
    if tens * 10 in TENS:
        return TENS[tens * 10]
    raise AssertionError(f"no spelling for {number}; extend the table rather than dropping the check")


def test_the_prose_counts_match_the_generated_table(section: str) -> None:
    import re

    ran = re.findall(r"\|\s*(\d+)/(\d+)\s*\|", section)
    assert ran, "the generated table no longer carries per-step check counts"
    steps = len(ran)
    checks = sum(int(done) for done, _ in ran)
    prose = README.read_text(encoding="utf-8").split("## Quickstart", 1)[0]
    for count, noun in ((steps, "operations"), (checks, "checks")):
        spelled = _spell(count)
        assert f"{spelled} {noun}" in prose, (
            f"the opening no longer says '{spelled} {noun}', but the worked example now "
            f"records {count}. Update the sentence or the example, not this test."
        )
