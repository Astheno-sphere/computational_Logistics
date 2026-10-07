"""Does discovery still work as the catalog grows? Measured, not assumed.

D-037 made the catalog the reachability layer: an operation that
`list_operations` cannot find does not exist for an agent, and the catalog is
meant to grow to thousands. So retrieval quality is a product property with a
trend, and a trend needs a series rather than a threshold.

Two things this file exists to prevent, both of which happened:

**Measuring ourselves.** The original golden queries were written by whoever
wrote the catalog text, so they share its vocabulary and test lexical overlap
dressed as retrieval. On those, BM25 scores 100% and the embedding engine 60%,
and the conclusion reverses on queries phrased the way a caller phrases them.
The set below is deliberately in the caller's words — 8% token overlap with the
catalog, measured — and it is the one the floors are set on.

**A floor with no series behind it.** The numbers in the docstrings are the
measurement of 2026-08-28 at fifty-one operations. When they move, the
interesting thing is the direction, so the assertions are loose and the print
is precise: run with `-s` to read the curve.
"""

from __future__ import annotations

import random

import pytest

from mapsmith import catalog

# Phrased as somebody with a problem phrases it, not as the catalog is written.
# Written after the catalog, deliberately avoiding its wording, and re-checked:
# these share 8% of their tokens with the entries they should find.
CALLER_QUERIES = {
    "buffer_layer": "I need a 200 m exclusion ring drawn around every borehole",
    "dissolve_layer": "the census tracts should become one shape per municipality",
    "zonal_statistics": "typical rainfall figure for each catchment from the grid",
    "overlay_layers": "which vineyards sit under the proposed reservoir footprint",
    "reproject_layer": "the two datasets do not line up, one is lat lon the other easting",
    "spatial_join": "stamp every accident record with the ward it happened in",
    "nearest_join": "for each bus stop, the pharmacy you would walk to and how many metres",
    "explode_layer": "the archipelago is one record and I need each atoll separately",
    "hillshade": "a background that shows the mountains as if lit from the side",
    "slope": "flag ground above 30 percent incline for the landslide report",
    "measure_area": "the surveyor says 4 hectares but my GIS says something else",
    "validate_geometry": "the tool refuses my file and mumbles about a ring",
    "count_in_polygons": "population of trees per city block",
    "voronoi_polygons": "divide the county into the territory served by each depot",
    "describe_crs": "before I compute anything, what am I actually working in",
    "geodetic_distance": "great circle separation of two airports",
    "convert_format": "the client wants shapefiles, I have parquet",
    "centroid_layer": "reduce every municipality to a single representative dot",
    "simplify_layer": "the coastline is 400000 nodes and the browser dies",
    "flow_direction": "build the pointer grid the watershed tool needs",
}

# Requests MapSmith cannot serve. The last two are the hard ones: they are about
# land and about places, and they are still not operations in this catalog.
OUT_OF_DOMAIN = [
    "send an email to my accountant",
    "train a neural network on cat photos",
    "xyzzy plugh frobnicate",
    "book a flight to Lisbon next tuesday",
    "what is the capital of Peru",
    "refactor this react component to use hooks",
    "summarise the attached pdf in three bullet points",
    "play some music while I work",
    "how do I sort a list in python",
    "who owns this parcel of land",
    "what will the weather be tomorrow in Rome",
]


def _by_name() -> dict[str, dict]:
    return {op["name"]: op for op in catalog.OPERATIONS}


def _subset(expected: str, size: int, seed: int) -> list[dict]:
    """The expected entry plus distractors, deterministically.

    Sorted by name and not by draw order: otherwise the expected entry is always
    first in the list, and any engine that breaks ties by position inherits an
    advantage that has nothing to do with retrieval.
    """
    catalogue = _by_name()
    others = [n for n in catalogue if n != expected]
    rng = random.Random(f"{expected}-{size}-{seed}")
    chosen = rng.sample(others, min(size - 1, len(others)))
    return [catalogue[n] for n in sorted([expected, *chosen])]


def _lexical_top(query: str, candidates: list[dict], k: int = 3) -> list[str]:
    scores = catalog.bm25_scores(
        catalog._tokenize(query), [catalog._document(op) for op in candidates]
    )
    ranked = sorted(
        ((op, s) for op, s in zip(candidates, scores, strict=True) if s > 0),
        key=lambda pair: (-pair[1], pair[0]["name"]),
    )
    return [op["name"] for op, _ in ranked[:k]]


def test_the_caller_queries_really_are_in_the_callers_words():
    """Guard on the guard. If these queries drift into the catalog's vocabulary
    the whole file quietly becomes the lexical-overlap test it was written to
    replace, and the floors below stop meaning anything."""
    shared = total = 0
    catalogue = _by_name()
    for name, query in CALLER_QUERIES.items():
        document = set(catalog._tokenize(catalog.document_text(catalogue[name])))
        tokens = catalog._tokenize(query)
        shared += sum(token in document for token in tokens)
        total += len(tokens)
    overlap = shared / total
    assert overlap < 0.45, (
        f"the caller queries now share {overlap:.0%} of their words with the entries "
        "they should find; they were written at 35% and the point of them is to test "
        "retrieval rather than word overlap"
    )


@pytest.mark.parametrize("size", [10, 20, 30, len(catalog.OPERATIONS)])
def test_lexical_retrieval_degrades_but_stays_above_the_floor(size, capsys):
    """BM25 alone, on a catalog of `size` entries, in the caller's words.

    Measured 2026-08-28 at 51 operations: 20% found@1, 40% found@3, down from
    48% and 78% at ten. It degrades, which is the whole reason the embedding
    engine became a dependency rather than an extra. The floor is set below the
    measurement, not at it: this test is a tripwire for a collapse, and the
    series is what gets read.
    """
    hits = at_three = trials = 0
    for expected, query in CALLER_QUERIES.items():
        for seed in (1, 2, 3):
            top = _lexical_top(query, _subset(expected, size, seed))
            trials += 1
            hits += bool(top) and top[0] == expected
            at_three += expected in top
    with capsys.disabled():
        print(f"\n  lexical  n={size:3}  found@1 {hits / trials:5.0%}  "
              f"found@3 {at_three / trials:5.0%}")
    assert at_three / trials >= 0.25, "lexical retrieval has collapsed, not merely degraded"


def test_the_two_engines_disagree_on_what_they_cannot_place(vector_engine, capsys):
    """The signal the clarification response is built on.

    A similarity threshold was tried and does not exist: "convert this mp4 to a
    gif" scores above sixteen of the twenty real queries. Two independent
    rankers landing on nothing in common is the only thing that separated the
    populations — mean top-3 overlap 0.90 of 3 in domain against 0.25 out.
    """
    pytest.importorskip("model2vec")
    from mapsmith import retrieval

    def overlap(query: str) -> int:
        lexical = {op["name"] for op, _ in catalog.rank(query, limit=3)}
        vector = {op["name"] for op, _ in retrieval.rank(query, limit=3)}
        return len(lexical & vector)

    in_domain = [overlap(q) for q in CALLER_QUERIES.values()]
    outside = [overlap(q) for q in OUT_OF_DOMAIN]
    mean_in = sum(in_domain) / len(in_domain)
    mean_out = sum(outside) / len(outside)
    with capsys.disabled():
        print(f"\n  agreement  in-domain {mean_in:.2f}/3   out-of-domain {mean_out:.2f}/3")
    assert mean_in > mean_out, (
        "the engines no longer agree more on answerable queries than on unanswerable "
        "ones, so the clarification trigger has stopped measuring anything"
    )
    # And the rule the code actually applies: no shared entry at all.
    flagged = sum(1 for value in outside if value < catalog.AGREEMENT_FLOOR)

    # A false alarm is asking INSTEAD OF ANSWERING CORRECTLY. Asking on a query
    # the ranking would have got wrong anyway is not a cost, it is the point:
    # six of these twenty fire the trigger, and in five of the six the answer
    # that would have been returned was wrong. Counting all six as false alarms
    # would score the feature by how often it interrupts rather than by what it
    # interrupts, which is the wrong quantity.
    suppressed = 0
    for expected, query in CALLER_QUERIES.items():
        lexical = {op["name"] for op, _ in catalog.rank(query, limit=3)}
        vector = [op["name"] for op, _ in retrieval.rank(query, limit=3)]
        if len(lexical & set(vector)) >= catalog.AGREEMENT_FLOOR:
            continue
        if expected in vector:  # would have answered, and answered right
            suppressed += 1
    with capsys.disabled():
        print(f"  clarification fires on {flagged}/{len(outside)} out-of-domain, "
              f"and suppresses {suppressed}/{len(CALLER_QUERIES)} correct answers")
    assert flagged >= len(outside) // 2, "the trigger catches less than half of nonsense"
    assert suppressed <= len(CALLER_QUERIES) // 5, (
        "the trigger is now swallowing answers the ranking had right"
    )


def test_every_available_operation_says_how_a_caller_would_ask_for_it():
    """`phrasings` is not optional documentation: it is retrieval corpus.

    Honest note, because the first measurement of it was wrong. Adding phrasings
    moved found@3 from 40% to 100% on the queries they were written against —
    and to 10/20 from 10/20 on queries written afterwards. The effect on unseen
    phrasing is not measurable; what it buys is the case where a caller happens
    to use the words. It stays because it costs nothing, and it is required so
    that a new entry has to think about how somebody would ask for it.
    """
    missing = [
        op["name"]
        for op in catalog.OPERATIONS
        if op["status"] == "available" and not op.get("phrasings")
    ]
    assert not missing, f"these entries do not say how a caller would ask: {missing}"


def _vector_top(query: str, candidates: list[dict], k: int = 3) -> list[str]:
    """The embedding engine over the same subset, so the two are comparable.

    `retrieval.rank` takes `candidates` for exactly this: one interface, two
    engines, one measurement. Without it the vector column of the published
    curve had no harness at all and was a hand-typed number for three catalogue
    sizes.
    """
    from mapsmith import retrieval

    return [op["name"] for op, _ in retrieval.rank(query, limit=k, candidates=candidates)]


def _curve(top) -> dict[int, int]:
    """found@3 per catalogue size, three seeds per query."""
    out = {}
    for size in (10, 30, len(catalog.OPERATIONS)):
        at_three = trials = 0
        for expected, query in CALLER_QUERIES.items():
            for seed in (1, 2, 3):
                trials += 1
                at_three += expected in top(query, _subset(expected, size, seed))
        out[size] = round(100 * at_three / trials)
    return out


@pytest.mark.slow
def test_the_published_degradation_curve_is_what_the_harness_computes(vector_engine):
    """The table on the README, recomputed — both columns.

    It was published at 10/30/51 as 78/83, 47/65, 40/55 and stayed there through
    three catalogue sizes while the sentence under it drew a conclusion the
    numbers had stopped supporting. The BM25 column had a harness that printed
    it and nobody compared; the embeddings column had no harness at all.

    Recomputing here rather than trusting the print is the difference between a
    number that is measured and a number that was measured once.
    """
    pytest.importorskip("model2vec")
    import re
    from pathlib import Path

    lexical, vector = _curve(_lexical_top), _curve(_vector_top)
    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text(
        encoding="utf-8"
    )
    published = {
        int(size): (int(bm25), int(embeddings))
        for size, bm25, embeddings in re.findall(
            r"^\| (\d+) \| (\d+)% \| (\d+)% \|$", readme, re.MULTILINE
        )
    }
    for size, bm25 in lexical.items():
        assert size in published, (
            f"the README's degradation table no longer has a row for {size} "
            "entries, so this check has nothing to compare — regenerate the table"
        )
        assert published[size] == (bm25, vector[size]), (
            f"at {size} entries the harness computes BM25 {bm25}% and embeddings "
            f"{vector[size]}%; the README publishes {published[size]}"
        )


@pytest.mark.slow
def test_the_page_does_not_claim_an_overtake_that_does_not_happen(vector_engine):
    """BM25 leads at every facet level, and the page said otherwise for a while.

    "The embedding engine only overtakes it once the facets have narrowed" was
    printed directly under a table showing BM25 ahead in every row. A sentence
    contradicted by the table above it is the failure this project measures in
    other people's output.
    """
    pytest.importorskip("model2vec")
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "benchmarks"))
    import discovery_report

    rows = discovery_report.answerable(discovery_report.load())
    lexical = discovery_report.ablation(rows, engine="lexical")
    vector = discovery_report.ablation(rows, engine="vector")
    overtakes = [
        i
        for i, (lex, vec) in enumerate(zip(lexical, vector, strict=True))
        if vec["found_at_3"] > lex["found_at_3"]
    ]
    readme = (root / "README.md").read_text(encoding="utf-8")
    claims_overtake = "embedding engine only overtakes" in readme

    assert bool(overtakes) == claims_overtake, (
        f"the vector engine overtakes BM25 at levels {overtakes} and the README "
        f"{'claims' if claims_overtake else 'does not claim'} an overtake. "
        "Whichever changed, the page and the measurement have to say the same thing."
    )
