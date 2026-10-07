"""The numbers on the README are recomputed here, not remembered.

Two of them were wrong for a day and one for half a day, in both cases because a
measurement changed and a page did not. The pages also say the numbers can be
checked rather than believed, which was not quite true while the request set was
published and the harness that turns it into percentages was not.

So `benchmarks/discovery_report.py` recomputes everything from files in this
repository, and this test asserts the README carries what it produces. Editing
one without the other fails here.

Marked slow: it runs a real search per request per facet level, which loads the
embedding model.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
sys.path.insert(0, str(ROOT / "benchmarks"))


@pytest.fixture(scope="module")
def report(vector_engine):
    """Needs both rankers, because the table publishes both.

    Skips rather than fails where the embedding model cannot be had: the page
    carries a column for each engine precisely so that neither the numbers nor
    this check depend on what a machine could download, and a build that goes
    red on someone else's rate limit teaches people to ignore red builds."""

    import discovery_report

    queries = discovery_report.load()
    answerable = discovery_report.answerable(queries)
    return {
        "agreement": discovery_report.agreement(queries),
        "ablation": discovery_report.ablation(answerable, engine="lexical"),
        "ablation_vector": discovery_report.ablation(answerable, engine="vector"),
        "n": len(answerable),
    }


@pytest.mark.slow
def test_the_readme_ablation_table_is_what_the_harness_computes(report):
    """Every row of the facet table, against the arithmetic that produces it."""
    prose = README.read_text(encoding="utf-8")
    # Five cells now: candidates, BM25, embeddings, delivered. The engine is
    # named in the table because the default picks between the two by whether a
    # model loads, and a single column made the published figures a measurement
    # of the machine — a CI run that met a rate limit recomputed the first row
    # as 28% where the page said 18%.
    rows = re.findall(
        r"^\|[^|]+\|\s*\**(\d+)\**\s*\|\s*\**(\d+)%\**\s*\|"
        r"\s*\**(\d+)%\**\s*\|\s*\**(\d+)%\**\s*\|$",
        prose,
        re.MULTILINE,
    )
    computed = [
        (
            str(lex["candidates"]),
            str(lex["found_at_3"]),
            str(vec["found_at_3"]),
            str(lex["delivered"]),
        )
        for lex, vec in zip(report["ablation"], report["ablation_vector"], strict=True)
    ]
    assert rows, (
        "the facet table is no longer in the README in a shape this can read, so "
        "nothing is checking the numbers it publishes"
    )
    for row in rows:
        assert row in computed, (
            f"the README publishes candidates={row[0]}, found@3={row[1]}%, "
            f"delivered={row[2]}% — the harness computes {computed}. Run "
            "`python benchmarks/discovery_report.py` and put back what it says."
        )


@pytest.mark.slow
def test_the_ceiling_is_quoted_over_the_same_population_as_everything_else(report):
    """Two numbers in one table must be over one denominator.

    Agreement over ALL requests counts the pairs where both labellers said the
    request is unanswerable — true, and the easy half. Quoted next to found@3,
    which is computed over the answerable ones only, it silently compares two
    populations. It did, for half a day: 68% of 155 sitting above 48% of 118.
    """
    prose = README.read_text(encoding="utf-8")
    same_all, n_all = report["agreement"]["all"]
    same_ans, n_ans = report["agreement"]["answerable"]
    over_all = round(100 * same_all / n_all)
    over_answerable = round(100 * same_ans / n_ans)

    assert f"{over_answerable}%" in prose, (
        f"the README does not quote {over_answerable}%, the agreement between the two "
        f"labellers over the same {n_ans} requests every other figure uses"
    )
    if over_all != over_answerable and f"{over_all}%" in prose:
        assert str(n_all) in prose, (
            f"the README quotes {over_all}%, which is agreement over all {n_all} "
            f"requests including the ones both labellers called unanswerable, without "
            f"saying so. Either quote {over_answerable}% (same population as the rest) "
            f"or name the {n_all}."
        )


@pytest.mark.slow
def test_the_population_is_named_wherever_a_percentage_is(report):
    """The count of requests has to be on the page carrying the percentages."""
    prose = README.read_text(encoding="utf-8")
    assert str(report["n"]) in prose, (
        f"the README no longer says how many requests these percentages are over "
        f"({report['n']}), which turns a measurement into a claim"
    )


def test_the_prose_around_the_table_is_checked_too():
    """The sentences, not only the numbers in the grid.

    Two claims went stale unnoticed and were found on 2026-08-29 while adding
    two operations, not by anybody checking: the page said the surviving set
    "has a median of 26 and never exceeded it" when the median was 14 and three
    of the 118 requests exceeded 30, and it called the curve a *median* while
    publishing the *mean*. Both were false before the catalogue reached 72, and
    the reason nobody noticed is that this file read the table and stopped.

    A sentence asserting a property that does not hold is worse than no
    sentence, because people stop thinking about it. So the prose is parsed for
    the numbers it states and each one is compared with the harness.
    """
    import re
    import statistics

    from mapsmith import catalog

    prose = README.read_text(encoding="utf-8")
    import discovery_report

    rows = discovery_report.answerable(discovery_report.load())
    full = discovery_report.LEVELS[discovery_report.FULLEST][1]
    # Through `accepted_of`, like the harness. This was the THIRD file computing
    # this number its own way — `test_published_figures` and the site check were
    # the other two — and all three diverged on 2026-09-01, the moment human
    # answers started deciding which facets a request declares. Each was right by
    # its own arithmetic and none matched the page's own generator. One number,
    # one computation: the rule is now written in three places because it was
    # broken in three.
    sizes = [
        len(
            catalog.applicable(
                **discovery_report.facets_for(discovery_report.accepted_of(r)[0], full)
            )
        )
        for r in rows
    ]
    over = sum(1 for size in sizes if size > catalog.CHOOSABLE)

    # The threshold is read from the catalogue, not written here: on 2026-09-29
    # it was nearly moved to 40, and a literal would have made this test the
    # thing to edit instead of the sentence.
    match = re.search(
        rf"has a median of (\d+) and exceeds {catalog.CHOOSABLE}\s+for (\w+) of them", prose
    )
    assert match, (
        "the sentence stating the median surviving set and how often it exceeds "
        "the threshold has been reworded; update this test with it rather than "
        "deleting it — it exists because that sentence was false for two "
        "catalogue sizes running"
    )
    words = {"none": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    assert int(match.group(1)) == statistics.median(sizes)
    assert words[match.group(2)] == over

    # The curve: every point must be the average the harness computes at that
    # catalogue size. Only the last one can be recomputed here — the earlier
    # ones are history — but the last one is the one that goes stale, so the
    # pattern walks to the end of the list rather than assuming its length.
    curve = re.search(
        r"9 at 51 operations(?:, \d+ at \d+)*, (\d+) at (\d+)\.", prose
    )
    assert curve, "the scaling curve sentence has been reworded; update this test"
    assert int(curve.group(2)) == len(catalog.OPERATIONS)
    assert int(curve.group(1)) == round(sum(sizes) / len(sizes))


def test_the_site_carries_the_same_facet_numbers_as_the_harness():
    """The site is a showcase of its own, and its numbers are hand-written.

    On 2026-08-29 the page said the facets take the candidates "from 51 to 21"
    while its own table two screens down said 74 to 31; claimed the right
    operation comes back "on all 118 requests" where the README spends a
    paragraph explaining why it is 115; and quoted a median of 14 inside a
    sentence about a measurement made at 61 operations, where the number was 9.
    Three contradictions on one page, none of them reachable by the check that
    reads the README.
    """
    import re

    from mapsmith import catalog

    template = ROOT / "site" / "index.template.html"
    prose = template.read_text(encoding="utf-8")

    import discovery_report

    rows = discovery_report.answerable(discovery_report.load())
    # Through `accepted_of`, like the harness. This used to read `label_claude`
    # directly, which was a second implementation of the same number — and on
    # 2026-09-01 the two diverged the moment human answers started deciding the
    # facets: the page said 30 and this test computed 31, both "correct"
    # according to their own arithmetic. A check that recomputes a published
    # figure its own way is a check that will eventually disagree with the thing
    # it is checking.
    def declared_size(row, facets):
        accepted = discovery_report.accepted_of(row)
        return len(catalog.applicable(**discovery_report.facets_for(accepted[0], facets)))

    facets = discovery_report.LEVELS[2][1]  # input kind + produces
    narrowed = [declared_size(r, facets) for r in rows]
    full = discovery_report.LEVELS[discovery_report.FULLEST][1]
    surviving = [declared_size(r, full) for r in rows]
    delivered = sum(1 for size in surviving if size <= catalog.CHOOSABLE)

    match = re.search(r"takes the candidates from (\d+) to (\d+)", prose)
    assert match, "the narrowing sentence has been reworded; update this test with it"
    assert int(match.group(1)) == len(catalog.OPERATIONS)
    assert int(match.group(2)) == round(sum(narrowed) / len(narrowed))

    match = re.search(r"On (\d+) of those (\d+) requests the right", prose)
    assert match, "the delivery sentence has been reworded; update this test with it"
    assert int(match.group(1)) == delivered
    assert int(match.group(2)) == len(rows)


# --- the human answers, and the loop that was missing ----------------------


def _ingest():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
    import ingest_answers

    return ingest_answers


def test_the_truth_is_the_human_answer_where_there_is_one():
    """D-054 says a figure computed against model labels is an *agreement* and
    not an accuracy, and that a person who has done the job is what changes it.

    So the label every figure measures against has to prefer the human answer,
    and until 2026-09-01 it did not: `discovery_report` read `label_claude`
    unconditionally, so answering a question in the dashboard could not move a
    single published number. The field existed, the page could write it, and
    nothing read it.
    """
    import discovery_report

    assert discovery_report.truth_of({"label_claude": "buffer_layer"}) == "buffer_layer"
    assert (
        discovery_report.truth_of(
            {"label_claude": "buffer_layer", "label_human": "spatial_join"}
        )
        == "spatial_join"
    ), "a human answer must beat a model's"
    assert discovery_report.truth_of({}) is None

    # Behavioural, not a grep of the source. The first version asserted the
    # literal line `truth = truth_of(q)`, which broke the moment D-062 replaced
    # it with `accepted_of` — a test that pins a spelling fails on a correct
    # change and passes on a wrong one. This asks the arithmetic instead: give
    # the same request two different human answers and the measured row has to
    # differ, which can only happen if the answer reaches it.
    from mapsmith import catalog

    # A real request, and two answers chosen from what the ranker actually does
    # with it: one the ranker returns and one it does not. Picking two answers it
    # misses would leave both rows at zero and the test would pass on a broken
    # implementation — which is how the first attempt at this test failed.
    request = discovery_report.load()[0]
    found = [
        entry["name"]
        for entry in catalog.entries(
            catalog.search(request["query"], limit=3, engine="lexical")
        )
    ]
    assert found, "the ranker returns nothing for this request; pick another"
    missed = next(
        op["name"] for op in catalog.OPERATIONS if op["name"] not in found
    )

    hit = [{"query": request["query"], "label_claude": found[0], "label_human": found[0]}]
    miss = [{"query": request["query"], "label_claude": found[0], "label_human": missed}]
    assert discovery_report.ablation(hit, engine="lexical") != discovery_report.ablation(
        miss, engine="lexical"
    ), (
        "changing the human answer changed nothing in the measured table, so the "
        "answer is not reaching the figures"
    )


def test_the_coverage_of_human_answers_is_reported_rather_than_blended():
    """A figure over 50 human answers and 105 model ones is neither of the two
    things a reader might take it for. The only honest fix is to say the mix."""
    import discovery_report

    queries = discovery_report.load()
    coverage = discovery_report.human_coverage(queries)
    assert coverage["requests"] == len(queries)
    assert 0 <= coverage["answered_by_a_person"] <= len(queries)
    assert coverage["neither_labeller_was_right"] <= coverage["answered_by_a_person"]


def test_an_answer_naming_nothing_is_refused(tmp_path):
    """The export is a file a person edited. An answer naming an operation that
    does not exist is a typo, and storing it would put a label in the population
    that no search can ever return."""
    import json

    import discovery_report

    # A request that DOES exist, so only the unknown-name check can reject it.
    # The first version of this test used a made-up request as well, so removing
    # the name check left it green: the absent-request check caught it instead
    # and the test passed for the wrong reason. Found by sabotage.
    real = discovery_report.load()[0]["query"]
    export = tmp_path / "answers.json"
    export.write_text(
        json.dumps([{"query": real, "label_human": "not_an_operation_at_all"}]),
        encoding="utf-8",
    )
    assert _ingest().main([str(export)]) == 2


def test_an_answer_to_a_request_that_no_longer_exists_is_refused(tmp_path):
    """Matching is on the text of the request, so a reworded request cannot be
    paired — and pairing it by position would silently reassign every answer
    after it."""
    import json

    export = tmp_path / "answers.json"
    export.write_text(
        json.dumps(
            [{"query": "a request nobody ever wrote", "label_human": "buffer_layer"}]
        ),
        encoding="utf-8",
    )
    assert _ingest().main([str(export)]) == 2


def test_a_real_answer_is_accepted_without_writing_unless_asked(tmp_path):
    """The dry run is the default: this file is data the published figures rest
    on, and a script that rewrites it without being asked is one somebody runs
    by accident."""
    import json

    import discovery_report

    queries = discovery_report.load()
    disagreeing = next(
        q
        for q in queries
        if q.get("label_claude")
        and q.get("label_gemini")
        and q["label_claude"] != q["label_gemini"]
    )
    before = Path(discovery_report.DATA).read_text(encoding="utf-8")

    export = tmp_path / "answers.json"
    export.write_text(
        json.dumps(
            [{"query": disagreeing["query"], "label_human": disagreeing["label_gemini"]}]
        ),
        encoding="utf-8",
    )
    assert _ingest().main([str(export)]) == 0
    assert Path(discovery_report.DATA).read_text(encoding="utf-8") == before, (
        "the dry run wrote to discovery_queries.json"
    )


def test_the_dashboard_carries_answers_that_are_already_recorded():
    """Without this the loop is one-way.

    Answers go from the browser into `discovery_queries.json` through
    `ingest_answers.py`, and until 2026-09-01 the next page generated asked the
    same questions again as though nobody had answered them — the page had no
    way to know. On a different browser, or after clearing site data, half an
    hour of work looked undone.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmarks"))
    import dashboard
    import discovery_report

    queries = discovery_report.load()
    answered = {q["query"]: q["label_human"] for q in queries if q.get("label_human")}
    if not answered:
        pytest.skip("nobody has answered a disagreement yet")

    rows = dashboard.disagreements(queries)
    carried = {row["query"]: row.get("human") for row in rows if row.get("human")}
    for text, label in answered.items():
        if any(row["query"] == text for row in rows):
            assert carried.get(text) == label, (
                f"the page would ask this again as though unanswered: {text[:60]}"
            )


def test_the_site_carries_the_same_ablation_figures_as_the_harness(report):
    """The README's table was guarded and the site's prose version was not.

    The site states the same four rows as a sentence — "74 candidates, 16%
    found@3 with embeddings and 26% with BM25; what data I have → 49, 20% and
    28%..." — and on 2026-09-01 four human answers moved three of those figures
    by a point while every test stayed green. Guarding one surface and not the
    other is the defect this file's own docstring describes: a measurement
    changed and a page did not.

    Deliberately anchored on the sentence rather than on the numbers alone. A
    number that appears somewhere passes while the sentence two screens away
    says something else — the failure `test_published_figures.py` was written
    after.
    """
    template = (
        Path(__file__).resolve().parent.parent / "site" / "index.template.html"
    ).read_text(encoding="utf-8")

    stated = re.search(
        r"→\s*(\d+)\s*candidates,\s*(\d+)% found@3 with embeddings and (\d+)% with BM25;"
        r"\s*what data I have\s*→\s*(\d+),\s*(\d+)% and (\d+)%;"
        r"\s*\+ what I want back\s*→\s*(\d+),\s*(\d+)% and (\d+)%",
        template,
        re.DOTALL,
    )
    assert stated, (
        "the site's ablation sentence no longer matches this pattern. Either it "
        "was reworded — fix the pattern — or it was removed, and this guard has "
        "been silently switched off."
    )

    lex, vec = report["ablation"], report["ablation_vector"]
    # The sentence names the embedding figure first and BM25 second, which is
    # the reverse of the table's column order — so the two engines come from two
    # separate computations here rather than from one row.
    expected = tuple(
        str(value)
        for row in range(3)
        for value in (
            lex[row]["candidates"],
            vec[row]["found_at_3"],
            lex[row]["found_at_3"],
        )
    )
    assert stated.groups() == expected, (
        f"the site says {stated.groups()} and the harness computes {expected}. "
        "Run `python benchmarks/discovery_report.py` and put back what it says."
    )


def test_a_request_can_accept_more_than_one_answer(tmp_path):
    """D-062: two experienced analysts reach the same result with different tools.

    Storing one answer makes the measurement wrong in both directions — a system
    that picks the other defensible operation is scored as having failed, and the
    figure is then called an accuracy when it is not even an agreement.
    """
    import discovery_report

    assert discovery_report.accepted_of(
        {"label_human": "transform_by_control_points", "label_human_also": ["ambiguous"]}
    ) == ("transform_by_control_points", "ambiguous")
    # The chosen one comes first, and a duplicate in `also` is dropped rather
    # than counted twice.
    assert discovery_report.accepted_of(
        {"label_human": "buffer_layer", "label_human_also": ["buffer_layer"]}
    ) == ("buffer_layer",)
    # No human answer: the model's label, as before.
    assert discovery_report.accepted_of({"label_claude": "clip_layer"}) == ("clip_layer",)
    assert discovery_report.accepted_of({}) == ()


def test_a_second_answer_without_a_reason_is_refused(tmp_path):
    """The note is required where there is more than one answer.

    Without it, "both of these are right" and "I could not decide" are the same
    row, and the second is not a datum — it is the absence of one in disguise.
    """
    import json

    import discovery_report

    real = discovery_report.load()[0]["query"]
    export = tmp_path / "answers.json"
    export.write_text(
        json.dumps(
            [
                {
                    "query": real,
                    "label_human": "buffer_layer",
                    "label_human_also": ["clip_layer"],
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        _ingest().main([str(export)])

    # And with the reason, it goes through.
    export.write_text(
        json.dumps(
            [
                {
                    "query": real,
                    "label_human": "buffer_layer",
                    "label_human_also": ["clip_layer"],
                    "label_human_note": "either reading of the request is defensible",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert _ingest().main([str(export)]) == 0


def test_the_measurement_counts_a_hit_against_the_whole_accepted_set():
    """The arithmetic, not the shape of the data.

    Built so that the SECONDARY answer is the one the ranker returns and the
    primary is not. Counting only the primary scores this as a miss; counting the
    set scores it as a hit, which is what D-062 says it is — a system that
    answers the other defensible operation has not failed.

    The first version of this test only checked that rows with two answers had a
    note, so replacing `any(name in accepted ...)` with `accepted[0] in ...` left
    it green. Found by sabotage.
    """
    import discovery_report

    from mapsmith import catalog

    request = discovery_report.load()[0]
    found = [
        entry["name"]
        for entry in catalog.entries(
            catalog.search(request["query"], limit=3, engine="lexical")
        )
    ]
    assert found, "the ranker returns nothing for this request; pick another"
    missed = next(op["name"] for op in catalog.OPERATIONS if op["name"] not in found)

    # Primary is the one the ranker misses; the acceptable secondary is the one
    # it returns. The facets still come from the primary, which is why this is a
    # measurement of the set and not of the label.
    row = discovery_report.ablation(
        [
            {
                "query": request["query"],
                "label_claude": missed,
                "label_human": missed,
                "label_human_also": [found[0]],
                "label_human_note": "both readings of this request are defensible",
            }
        ],
        engine="lexical",
    )
    # Both columns. Asserting only `delivered` left the top-3 counter free to
    # go back to the primary alone — the sabotage that found this.
    assert row[0]["delivered"] == 100, (
        "the ranker returned an answer the person accepts and delivery scored it "
        "as a miss, so the hit is counted against the primary alone"
    )
    assert row[0]["found_at_3"] == 100, (
        "the accepted answer is in the top three and found@3 scored it as a "
        "miss, so that counter is still measuring the primary alone"
    )


def test_every_request_with_two_answers_carries_the_reason():
    """The shape of the data, kept as its own check rather than folded into the
    arithmetic one — where it used to hide the fact that nothing tested the
    arithmetic."""
    import discovery_report

    with_two = [q for q in discovery_report.load() if q.get("label_human_also")]
    if not with_two:
        pytest.skip("no request has a second acceptable answer yet")
    for q in with_two:
        assert len(discovery_report.accepted_of(q)) > 1
        assert (q.get("label_human_note") or "").strip(), (
            "a request with two answers and no reason should not be in the file: "
            "ingest_answers refuses it"
        )


def test_the_dashboard_can_collect_a_second_answer_and_its_reason():
    """The page is where the answers come from, so it has to be able to give
    what the format now accepts — otherwise the format is theory."""
    dashboard_source = (
        Path(__file__).resolve().parent.parent / "benchmarks" / "dashboard.py"
    ).read_text(encoding="utf-8")
    for needed in (
        "function toggleAlso(",
        "label_human_also",
        "label_human_note",
        "shift-click to add as also acceptable",
    ):
        assert needed in dashboard_source, (
            f"the dashboard no longer carries {needed!r}, so a second answer "
            f"cannot be given and D-062's format has nothing to fill it"
        )


def test_the_entry_spec_carries_the_same_facet_numbers_as_the_harness(report):
    """The third copy of one measurement, and it had drifted.

    `docs/catalog-entry-spec.md` opens with "the measurement everything rests
    on" and prints the facet table again, for a reader who arrives at the entry
    format rather than at the README. On 2026-09-21 it said 25% where the
    harness computes 31% and 27% where it computes 32%: a page presenting
    itself as the foundation, publishing figures nothing had recomputed since
    they were typed.

    The README and the site were already checked against the harness. This file
    was not, which is the whole reason it could drift -- and the count of
    places computing one number their own way is exactly what this repository
    keeps finding.
    """
    import re
    from pathlib import Path

    page = Path(__file__).resolve().parent.parent / "docs" / "catalog-entry-spec.md"
    prose = page.read_text(encoding="utf-8")
    rows = re.findall(
        r"^\|[^|]+\|\s*\**(\d+)\**\s*\|\s*\**(\d+)%\**\s*\|\s*\**(\d+)%\**\s*\|$",
        prose,
        re.MULTILINE,
    )
    assert rows, (
        "the facet table is no longer in catalog-entry-spec.md in a shape this "
        "can read, so nothing is checking the numbers that page publishes"
    )
    computed = [
        (str(level["candidates"]), str(level["found_at_3"]), str(level["delivered"]))
        for level in report["ablation"]
    ]
    for row in rows:
        assert row in computed, (
            f"catalog-entry-spec.md publishes candidates={row[0]}, found@3={row[1]}%, "
            f"delivered={row[2]}% - the harness computes {computed}. Run "
            "`python benchmarks/discovery_report.py` and put back what it says."
        )


def test_the_scaling_curve_and_the_median_are_current_on_every_surface():
    """Two sentences nothing was comparing, on two pages, one of them stale.

    The README and the site both print the average surviving set as a series
    over catalogue sizes, and both quote the median beside it. The README's
    copy was checked; the site's was not, so on 2026-09-21 the site still
    ended its series at "17 at seventy-four" -- a value the README had already
    retracted on 2026-09-01, one catalogue size back, in words rather than
    digits so no digit-matching guard could see it.

    The earlier points of the series are history and cannot be recomputed. The
    last one is the one that goes stale, so that is the one checked, on both
    surfaces and in whichever notation each uses.
    """
    import re
    import statistics
    from pathlib import Path

    import discovery_report

    from mapsmith import catalog

    rows = discovery_report.answerable(discovery_report.load())
    full = discovery_report.LEVELS[discovery_report.FULLEST][1]
    sizes = [
        len(
            catalog.applicable(
                **discovery_report.facets_for(discovery_report.accepted_of(row)[0], full)
            )
        )
        for row in rows
    ]
    mean, median = round(sum(sizes) / len(sizes)), int(statistics.median(sizes))
    total = len(catalog.OPERATIONS)

    root = Path(__file__).resolve().parent.parent
    # The DERIVED spelling, shared with `test_published_figures`. This held its
    # own finite map, which stopped at seventy-five: on 2026-09-24 the catalogue
    # reached 76, and a page that correctly said "seventy-six" would have been
    # accused by a guard looking for "76". That is the sixth appearance of one
    # shape here, and `in_words` was written on 2026-09-21 to end it -- this copy
    # was the one nobody moved across.
    from test_published_figures import in_words as spoken

    surfaces = {
        "README.md": (
            rf"(\d+) at {total} operations|, (\d+) at {total}\.",
            rf"the median at {total} is (\d+)",
        ),
        "site/index.template.html": (
            rf", (\w[\w-]*) at {spoken(total)}[.\s]",
            rf"the median at {spoken(total)} is (\d+)",
        ),
    }
    for name, (curve_pattern, median_pattern) in surfaces.items():
        prose = (root / name).read_text(encoding="utf-8")
        curve = re.search(curve_pattern, prose)
        assert curve, (
            f"{name} no longer ends its surviving-set series at the current "
            f"catalogue size ({total}); it is a catalogue behind, or reworded"
        )
        stated = next(group for group in curve.groups() if group)
        assert stated in (str(mean), spoken(mean)), (
            f"{name} says the average surviving set is {stated} at {total} "
            f"operations; the harness computes {mean}"
        )
        found = re.search(median_pattern, prose)
        assert found, f"{name} no longer states the median at the current catalogue size"
        assert int(found.group(1)) == median, (
            f"{name} says the median is {found.group(1)}; the harness computes {median}"
        )


def test_the_site_heading_says_the_breadth_before_the_choice():
    """The number a visitor scanning headings takes away must be the bigger one.

    That section carried the kicker "Operations" over the heading "28 tools, not
    a catalogue", and the sentence putting the two numbers side by side came two
    paragraphs later. Both figures were derived and neither was stale -- what
    was wrong was the framing: a reader who skims headings left with 28 as the
    breadth of a product whose breadth is 75 and whose argument is that it is
    built for thousands.

    A reader flagged it. Nothing here could have: every check on this page
    compares a number with the harness, and both numbers were right.
    """
    import re
    from pathlib import Path

    from mapsmith import catalog

    root = Path(__file__).resolve().parent.parent
    template = (root / "site" / "index.template.html").read_text(encoding="utf-8")
    heading = re.search(r"<h2>([^<]*operations[^<]*)</h2>", template)
    assert heading, (
        "the operations heading has been reworded out of recognition; update this "
        "test with it rather than deleting it -- it exists because the framing, "
        "not the figures, is what misled a reader"
    )
    text = heading.group(1)
    assert "{{CATALOG_COUNT}}" in text and "{{TOOL_COUNT}}" in text, text
    assert text.index("{{CATALOG_COUNT}}") < text.index("{{TOOL_COUNT}}"), (
        f"the heading names the exposed tools before the catalogue: {text!r}. The "
        "bigger number is the one a skimming reader should take away, and "
        f"there are {len(catalog.OPERATIONS)} operations behind the tools."
    )
