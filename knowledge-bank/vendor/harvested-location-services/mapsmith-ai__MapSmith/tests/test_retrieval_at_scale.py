"""What happens at hundreds of operations, measured rather than extrapolated.

The catalog is 74 entries and is meant to grow to thousands (D-031, D-037). Four
points below that do not answer what happens at 800, and filling the gap with
invented entries would answer the wrong question: an invented distractor does not
compete, because it is not a plausible GIS operation written the way somebody
writes one.

So the distractors are real. whitebox-workflows ships 800+ tools with a name, a
category and a description, and they are the HARD case rather than a convenient
one: they are functionally close to each other and to ours, which invariant 6
names as the variable that matters — not the count.

The result is the one that matters for planning, and it reversed a conclusion
this repository had already drawn:

    catalog    BM25 found@3    embeddings found@3
       ours             50%                   40%
        100             48%                   32%
        200             48%                   25%
        400             40%                   25%
        800             35%                   20%

Against near-neighbour distractors the embedding engine degrades FASTER, not
more slowly. This used to contradict `test_retrieval_degradation.py`, which
draws its distractors from our own diverse entries and answers "which engine
suits the catalog we have today" — and used to answer "the embedding one".
The two agree now: recomputed on 2026-08-30 at seventy-four entries, BM25 leads
there from thirty upward, because the near-neighbour effect THIS file predicted
has arrived in our own catalogue. This file answers "which survives the catalog
we plan", and the answer is neither. At 800 entries both are wrong more often
than right, so scale will have to be bought structurally — the applicability filter that narrows before ranking,
facets, and the clarification path — and not by choosing a better ranker.

Marked slow: it embeds ~850 documents. Run it with `-m slow` or in full CI.
"""

from __future__ import annotations

import random

import pytest

from mapsmith import catalog

pytestmark = pytest.mark.slow

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


def _distractor_pool() -> list[dict]:
    """Real GIS operations shaped like catalog entries."""
    wb = pytest.importorskip("whitebox_workflows")
    environment = wb.WbEnvironment()
    environment.verbose = False
    pool: list[dict] = []
    for category_name in dir(environment):
        if category_name.startswith("_"):
            continue
        category = getattr(environment, category_name, None)
        for sub_name in dir(category) if category is not None else []:
            if sub_name.startswith("_"):
                continue
            sub = getattr(category, sub_name, None)
            names = [t for t in dir(sub) if not t.startswith("_")] if sub is not None else []
            if len(names) <= 3:  # not a tool subcategory
                continue
            for tool in names:
                doc = (getattr(getattr(sub, tool, None), "__doc__", None) or "").strip()
                if not doc:
                    continue
                pool.append({
                    "name": f"wbx_{tool}",
                    "status": "available",
                    "category": sub_name.replace("_", " "),
                    "summary": doc.split("Call style:")[0].strip()[:200],
                    "description": doc[:600],
                    "parameters": [],
                    "examples": [],
                    "applicability": {"inputs": ["raster"], "requires_projected_crs": False},
                })
    return pool


@pytest.fixture(scope="module")
def bench():
    import numpy as np

    from mapsmith import retrieval

    pool = _distractor_pool()
    if len(pool) < 500:
        pytest.skip(f"only {len(pool)} real distractors available; need a few hundred")
    ours = {op["name"]: op for op in catalog.OPERATIONS}
    everything = [*ours.values(), *pool]
    vectors = retrieval.embed([catalog.document_text(op) for op in everything])
    vectors = vectors / np.clip(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-12, None)
    rows = {op["name"]: i for i, op in enumerate(everything)}
    return {"pool": pool, "ours": ours, "vectors": vectors, "rows": rows, "np": np,
            "retrieval": retrieval}


def _subset(bench, expected: str, size: int, seed: int) -> list[dict]:
    """Ours first, then real distractors up to `size`. Deterministic."""
    rng = random.Random(f"{expected}-{size}-{seed}")
    ours = bench["ours"]
    chosen = [ours[expected]]
    rest = [op for name, op in ours.items() if name != expected]
    rng.shuffle(rest)
    chosen += rest[: max(0, size - 1)]
    if len(chosen) < size:
        chosen += rng.sample(bench["pool"], min(size - len(chosen), len(bench["pool"])))
    return sorted(chosen, key=lambda op: op["name"])


def _lexical(query, candidates, k=3):
    scores = catalog.bm25_scores(
        catalog._tokenize(query), [catalog._document(op) for op in candidates]
    )
    ranked = sorted(
        ((op, s) for op, s in zip(candidates, scores, strict=True) if s > 0),
        key=lambda pair: (-pair[1], pair[0]["name"]),
    )
    return [op["name"] for op, _ in ranked[:k]]


def _vector(bench, query, candidates, k=3):
    np = bench["np"]
    q = bench["retrieval"].embed([query])[0]
    q = q / max(float(np.linalg.norm(q)), 1e-12)
    rows = [bench["rows"][op["name"]] for op in candidates]
    scores = bench["vectors"][rows] @ q
    return [candidates[int(i)]["name"] for i in np.argsort(-scores)[:k]]


@pytest.mark.parametrize("size", [100, 400, 800])
def test_both_engines_degrade_against_real_neighbours(bench, size, capsys):
    """The series, printed. The assertion is a collapse tripwire, not the point.

    What gets read is the shape: if a future change makes either column stop
    falling, that is the interesting event, and if one falls off a cliff between
    two runs the catalog grew in a way that broke discovery.
    """
    results = {}
    for label in ("lexical", "vector"):
        hits = at_three = trials = 0
        for expected, query in CALLER_QUERIES.items():
            for seed in (1, 2):
                candidates = _subset(bench, expected, size, seed)
                top = (
                    _lexical(query, candidates)
                    if label == "lexical"
                    else _vector(bench, query, candidates)
                )
                trials += 1
                hits += bool(top) and top[0] == expected
                at_three += expected in top
        results[label] = (hits / trials, at_three / trials)
    with capsys.disabled():
        print(f"\n  n={size:4}  "
              f"lexical @1 {results['lexical'][0]:4.0%} @3 {results['lexical'][1]:4.0%}   "
              f"vector @1 {results['vector'][0]:4.0%} @3 {results['vector'][1]:4.0%}")
    best = max(results["lexical"][1], results["vector"][1])
    assert best > 0.15, (
        f"at {size} entries neither engine finds the right operation in the top 3 more "
        "than 15% of the time; ranking has stopped working and no default can fix it"
    )


def test_ranking_alone_does_not_reach_a_thousand_operations(bench, capsys):
    """The finding this file exists to keep in front of us.

    Not a regression guard — a standing statement, asserted so it cannot quietly
    stop being true. At 800 entries the better of the two engines finds the right
    operation in the top 3 about a third of the time. The plan is thousands. So
    the scaling answer is structural: narrow before ranking (the applicability
    filter already does, deterministically), then ask when the two engines cannot
    agree, rather than hoping a ranker improves by a factor of three.
    """
    size = 800
    best = 0.0
    for label in ("lexical", "vector"):
        at_three = trials = 0
        for expected, query in CALLER_QUERIES.items():
            candidates = _subset(bench, expected, size, 1)
            top = (
                _lexical(query, candidates)
                if label == "lexical"
                else _vector(bench, query, candidates)
            )
            trials += 1
            at_three += expected in top
        best = max(best, at_three / trials)
    with capsys.disabled():
        print(f"\n  best engine at 800 entries: found@3 {best:.0%}")
    assert best < 0.80, (
        "ranking at 800 entries has become good enough that the structural argument "
        "above no longer holds; re-read it before deleting it, because the plan was "
        "built on it being false"
    )
