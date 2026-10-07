"""Retrieval-quality eval for the operation catalog.

The catalog is how agents discover capabilities (progressive discovery), so
its search quality is a product property, not an implementation detail. This
module pins a golden set of realistic agent queries and measures any retriever
against it, so we notice degradation before users do — and so future
retrievers (embedding hybrid, learned rerankers) can be compared to the BM25
baseline on the same scorecard.

A retriever is any ``(query, limit) -> ranked operation names`` callable; the
eval is deliberately agnostic to how the ranking is produced. Golden cases
come in two tiers:

- ``core``: paraphrases an agent plausibly emits; these must work today and
  every regression is a test failure.
- ``hard``: deliberate vocabulary mismatch (synonyms absent from the docs).
  They document the known limit of lexical search; the aggregate floor only
  guards against regressions. A future semantic retriever earns its place by
  raising this number, not by hand-tuning the golden set.

Run ``python tests/test_catalog_retrieval.py`` for the baseline report.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from mapsmith import catalog

Retriever = Callable[[str, int], list[str]]


def bm25_retriever(query: str, limit: int = 10) -> list[str]:
    """The production retriever: catalog BM25 ranking."""
    return [op["name"] for op, _ in catalog.rank(query, limit=limit)]


# Golden set: query as an agent would phrase it -> acceptable operations.
# "expected" lists every operation that would genuinely serve the request;
# the eval counts the best-ranked acceptable one.
GOLDEN: list[dict[str, Any]] = [
    # --- core: realistic paraphrases, must work today -----------------------
    {"query": "check the CRS and schema of a dataset before analysis",
     "expected": ["describe_dataset"], "tier": "core"},
    {"query": "how many features and what extent does this layer have",
     "expected": ["describe_dataset"], "tier": "core"},
    {"query": "buffer the roads by 500 meters",
     "expected": ["buffer_layer"], "tier": "core"},
    {"query": "protection zone around drinking water wells",
     "expected": ["buffer_layer"], "tier": "core"},
    {"query": "clip the road network to the city boundary",
     "expected": ["clip_layer"], "tier": "core"},
    {"query": "keep only the buildings inside the study area",
     "expected": ["clip_layer"], "tier": "core"},
    {"query": "reproject a layer to EPSG:32632",
     "expected": ["reproject_layer"], "tier": "core"},
    {"query": "convert a WGS84 dataset to UTM for metric analysis",
     "expected": ["reproject_layer"], "tier": "core"},
    {"query": "join attributes from census tracts to buildings by location",
     "expected": ["spatial_join"], "tier": "core"},
    {"query": "which roads cross protected areas",
     "expected": ["spatial_join"], "tier": "core"},
    {"query": "filter buildings taller than 30 meters with SQL",
     "expected": ["run_sql"], "tier": "core"},
    {"query": "aggregate accident counts per district",
     "expected": ["run_sql"], "tier": "core"},
    {"query": "spatial SQL query on geoparquet files",
     "expected": ["run_sql"], "tier": "core"},
    {"query": "mean elevation per watershed from a DEM",
     "expected": ["zonal_statistics"], "tier": "core"},
    {"query": "average raster value inside each polygon zone",
     "expected": ["zonal_statistics"], "tier": "core"},
    {"query": "statistics of a population raster per municipality",
     "expected": ["zonal_statistics"], "tier": "core"},
    {"query": "how was this output produced, show the audit trail",
     "expected": ["get_provenance"], "tier": "core"},
    {"query": "which engine and parameters created this file",
     "expected": ["get_provenance"], "tier": "core"},
    {"query": "shaded relief from a digital elevation model",
     "expected": ["hillshade"], "tier": "core"},
    {"query": "hillshade with the sun low from the east",
     "expected": ["hillshade"], "tier": "core"},
    {"query": "flow accumulation grid from a DEM",
     "expected": ["flow_accumulation"], "tier": "core"},
    {"query": "extract the drainage network from elevation data",
     "expected": ["flow_accumulation"], "tier": "core"},
    {"query": "delineate the catchment upstream of a gauging station",
     "expected": ["watershed"], "tier": "core"},
    {"query": "drainage basins for several dam sites",
     "expected": ["watershed"], "tier": "core"},
    {"query": "validate my plan before running it",
     "expected": ["validate_plan"], "tier": "core"},
    {"query": "check a multi-step pipeline without executing anything",
     "expected": ["validate_plan"], "tier": "core"},
    {"query": "execute a multi-step plan with full lineage",
     "expected": ["execute_plan"], "tier": "core"},
    {"query": "run a validated geoprocessing pipeline step by step",
     "expected": ["execute_plan"], "tier": "core"},
    {"query": "show the results on an interactive map in the chat",
     "expected": ["preview_map"], "tier": "core"},
    {"query": "visualize the output layers with their verification status",
     "expected": ["preview_map"], "tier": "core"},
    {"query": "travel time polygons around a clinic",
     "expected": ["isochrone"], "tier": "core"},
    {"query": "run a GRASS or SAGA algorithm",
     "expected": ["qgis_processing"], "tier": "core"},
    # --- hard: vocabulary mismatch, the known limit of lexical search -------
    {"query": "point in polygon analysis",
     "expected": ["spatial_join"], "tier": "hard"},
    {"query": "cookie cut a layer using a polygon mask",
     "expected": ["clip_layer"], "tier": "hard"},
    {"query": "dry run of a workflow",
     "expected": ["validate_plan"], "tier": "hard"},
    {"query": "change the datum of my data",
     "expected": ["reproject_layer"], "tier": "hard"},
    {"query": "how much rain fell in each catchment",
     "expected": ["zonal_statistics"], "tier": "hard"},
    {"query": "make the terrain look three dimensional",
     "expected": ["hillshade"], "tier": "hard"},
    {"query": "15 minute walking accessibility map",
     "expected": ["isochrone"], "tier": "hard"},
    {"query": "which parcels touch the new highway",
     "expected": ["spatial_join"], "tier": "hard"},
    {"query": "upstream contributing area for each cell",
     "expected": ["flow_accumulation"], "tier": "hard"},
    {"query": "lineage of the map I just made",
     "expected": ["get_provenance"], "tier": "hard"},
]


def evaluate(
    retriever: Retriever, cases: list[dict[str, Any]], k: int = 3
) -> dict[str, Any]:
    """Score a retriever on golden cases: recall@1, recall@k, MRR, misses."""
    hits_1 = hits_k = 0
    reciprocal_sum = 0.0
    misses: list[dict[str, Any]] = []
    for case in cases:
        ranked = retriever(case["query"], 10)
        best = min(
            (ranked.index(op) for op in case["expected"] if op in ranked),
            default=None,
        )
        if best is not None:
            reciprocal_sum += 1 / (best + 1)
            hits_1 += best == 0
            hits_k += best < k
        else:
            misses.append({"query": case["query"], "got": ranked[:k]})
    n = len(cases)
    return {
        "n": n,
        "recall_at_1": hits_1 / n,
        f"recall_at_{k}": hits_k / n,
        "mrr": reciprocal_sum / n,
        "misses": misses,
    }


CORE = [c for c in GOLDEN if c["tier"] == "core"]
HARD = [c for c in GOLDEN if c["tier"] == "hard"]


@pytest.mark.parametrize("case", CORE, ids=lambda c: c["query"][:48])
def test_core_query_hits_top3(case: dict[str, Any]) -> None:
    ranked = bm25_retriever(case["query"], 10)[:3]
    assert any(op in ranked for op in case["expected"]), (
        f"expected one of {case['expected']} in the top 3, got {ranked}"
    )


def test_core_recall_at_1_floor() -> None:
    """Aggregate floor: lowering it is a product regression, not a test fix."""
    report = evaluate(bm25_retriever, CORE)
    assert report["recall_at_1"] >= 0.90, report


def test_hard_tier_floor() -> None:
    """Known limit of lexical search, pinned. A semantic retriever should
    raise this — that is the improvement target, measured on the same set."""
    report = evaluate(bm25_retriever, HARD)
    assert report["recall_at_3"] >= 0.40, report


def test_every_operation_is_discoverable_by_its_summary() -> None:
    """Self-retrieval sanity: each entry's own summary must rank it first.
    Failing here means an entry's docs are lexically indistinct — fix the
    docs, not the ranking."""
    for op in catalog.OPERATIONS:
        top = bm25_retriever(op["summary"], 3)
        assert top and top[0] == op["name"], (
            f"summary of '{op['name']}' retrieves {top} instead"
        )


if __name__ == "__main__":
    for tier, cases in (("core", CORE), ("hard", HARD)):
        report = evaluate(bm25_retriever, cases)
        print(
            f"{tier:5s} n={report['n']:2d}  recall@1={report['recall_at_1']:.2f}  "
            f"recall@3={report['recall_at_3']:.2f}  mrr={report['mrr']:.2f}"
        )
        for miss in report["misses"]:
            print(f"      miss: {miss['query']!r} -> {miss['got']}")
