"""The embedding retrieval layer: pinned, deterministic, measured.

The golden vector pins the whole stack — model artifact (revision-pinned),
tokenizer, pooling, numerics. If any layer drifts, these numbers move and the
test says so before an agent's tool choice does. The ranking floors are loose
on purpose: they guard against total breakage (a swapped or corrupted model),
while the real quality tracking lives in the found@k comparison, which prints
its table rather than asserting taste.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("model2vec")

from mapsmith import catalog, retrieval

QUERY = "buffer the wells by 500 meters"
# First six dimensions of the 512-dim embedding of QUERY, observed 2026-08-25
# on model revision 6fc8051f. Tolerance covers BLAS differences across
# platforms, not model changes: a revision bump moves these far outside it.
GOLDEN_HEAD = [0.065633, 0.089767, 0.026056, 0.112892, -0.061732, -0.056281]

# One realistic ask per operation family exercised so far. found@3 floors are
# deliberately loose; the printed table is the measurement.
GOLDEN_QUERIES = {
    "slope": "slope of a DEM in degrees",
    "dissolve_layer": "merge polygons that share an attribute value",
    "zonal_statistics": "mean elevation inside each zone polygon",
    "overlay_layers": "intersect two polygon layers",
    "buffer_layer": "protection zone of 500 meters around wells",
    "reproject_layer": "convert a layer to a different coordinate system",
    "hillshade": "shaded relief image from elevation data",
    "spatial_join": "attach census attributes to buildings by location",
    "nearest_join": "find the nearest hospital to each school with the distance",
    "explode_layer": "split multipart geometries into single features",
}


@pytest.fixture(scope="module")
def warm_model():
    try:
        retrieval.embed(["warm-up"])
    except Exception as exc:  # noqa: BLE001 — no network/model here means skip, not fail
        pytest.skip(f"embedding model not available: {exc}")


def test_encoding_is_bit_identical_within_a_process(warm_model):
    first = retrieval.embed([QUERY, "a second sentence"])
    second = retrieval.embed([QUERY, "a second sentence"])
    assert np.array_equal(first, second)


def test_the_golden_vector_pins_the_whole_stack(warm_model):
    vector = retrieval.embed([QUERY])[0]
    assert vector.shape == (512,)
    assert float(np.linalg.norm(vector)) == pytest.approx(1.0, abs=1e-5)
    assert np.allclose(vector[:6], GOLDEN_HEAD, atol=1e-4), (
        "golden vector moved — model revision, tokenizer or pooling changed"
    )


def test_found_at_3_stays_above_the_breakage_floor(warm_model):
    hits = {}
    for expected, query in GOLDEN_QUERIES.items():
        top3 = [op["name"] for op, _ in retrieval.rank(query, limit=3)]
        hits[expected] = expected in top3
    table = ", ".join(f"{name}={'ok' if hit else 'MISS'}" for name, hit in hits.items())
    found = sum(hits.values())
    print(f"\nembedding found@3: {found}/{len(hits)} [{table}]")
    assert found >= len(hits) - 2, f"embedding retrieval collapsed: {table}"


def test_bm25_and_embedding_read_the_same_corpus(warm_model):
    """The comparison is honest only if both engines rank the same text — and
    it reports quality AND latency side by side, because the decision that
    would supersede the BM25 default needs both curves, not one."""
    import time

    texts = [catalog.document_text(op) for op in catalog.OPERATIONS]
    assert len(texts) == len(catalog.OPERATIONS)
    assert all(isinstance(t, str) and t for t in texts)

    retrieval.rank("warm the index", limit=1)  # index build must not bill the first query
    both = {}
    timings = {"bm25": 0.0, "embedding": 0.0}
    for expected, query in GOLDEN_QUERIES.items():
        start = time.perf_counter()
        bm25_top = [op["name"] for op, _ in catalog.rank(query, limit=3)]
        timings["bm25"] += time.perf_counter() - start
        start = time.perf_counter()
        embed_top = [op["name"] for op, _ in retrieval.rank(query, limit=3)]
        timings["embedding"] += time.perf_counter() - start
        both[expected] = (expected in bm25_top, expected in embed_top)

    bm25_found = sum(1 for hit, _ in both.values() if hit)
    embed_found = sum(1 for _, hit in both.values() if hit)
    per_query = {name: total / len(both) * 1000 for name, total in timings.items()}
    print(
        f"\ncatalog size {len(catalog.OPERATIONS)} | found@3 on {len(both)} golden queries: "
        f"bm25={bm25_found} ({per_query['bm25']:.2f} ms/query), "
        f"embedding={embed_found} ({per_query['embedding']:.2f} ms/query)"
    )
    # No winner asserted: the point of running both is the printed curve over
    # time, and the decision that would supersede the BM25 default is taken on
    # accumulated numbers, not on one test run.
    assert bm25_found + embed_found > 0
