"""Optional embedding retrieval for the operation catalog.

BM25 (:func:`mapsmith.catalog.rank`) stays the default: deterministic,
dependency-free, and sufficient at the current catalog size. This module is
the embedding layer the catalog docstring promised could be "layered on top of
rank() without changing the public API" — built early, while the catalog is
small, so that its quality can be *measured as the catalog grows* instead of
argued about later.

The model is a static embedder (a token lookup plus pooling — no transformer,
no GPU, and no network at query time): ``potion-retrieval-32M``, MIT, 512
dimensions, pinned to an exact revision below. Determinism has two halves and
only one belongs to the model: the artifact is pinned by revision, and a
golden-vector test pins the numbers themselves, so drift in any layer of the
stack fails a test instead of an analysis. Encoding is bit-identical across
calls in one process (measured); multiprocessing is disabled on purpose.

A hard dependency since 0.3.0, not an extra: the measurement said the embedding
engine should be the default, and a default behind an extra is not a default. The
model (~130 MB of artifacts, once) is fetched from the Hugging Face Hub on first
use and cached; ``HF_HUB_OFFLINE=1``, no network, or a cold cache on an air-gapped
machine all fall back to BM25, and the ``engine`` field of every result says which
one answered. The repository and revision are constants in this file: no tool
argument reaches that fetch.
"""

from __future__ import annotations

from functools import cache
from typing import Any

MODEL_ID = "minishlab/potion-retrieval-32M"
# Pinned 2026-08-25 (MIT). Bump deliberately, never implicitly: the golden
# vectors in tests/test_retrieval.py will fail on any change, on purpose.
MODEL_REVISION = "6fc8051fab2a1e0ee76689cf08c853792ac285e7"


# Only what `StaticModel.from_pretrained` reads. Without this the snapshot also
# pulls `model.onnx`, another 129 MB that nothing here opens -- measured on the
# local cache, which held 520 MB for a model whose payload is 131.
MODEL_FILES = ("*.json", "*.txt", "*.safetensors", "*.md")


def _require():
    try:
        from huggingface_hub import snapshot_download
        from model2vec import StaticModel
    except ImportError as exc:  # pragma: no cover - a dependency, not an extra
        raise ImportError(
            "model2vec is a dependency of mapsmith and appears not to be installed; "
            "reinstall the package"
        ) from exc
    return snapshot_download, StaticModel


@cache
def _model():
    """The pinned static model, fetched once and cached by huggingface_hub.

    The package depends on model2vec, but the model WEIGHTS are still a download
    on first use, and there is no honest way around that in a 30 MB wheel. So
    the failure is handled where it happens rather than promised away: `rank`
    raises, `catalog.search` catches, and a machine with no network still gets
    lexical results and is told which engine answered. A default that needs a
    download is not a default -- but a default that needs a download ONCE, and
    degrades to a working answer when it cannot have it, is.
    """
    snapshot_download, StaticModel = _require()
    # NO FETCH UNDER A WORKSPACE. `SECURITY.md` promises no network egress when
    # `MAPSMITH_WORKSPACE` is set, and states that any way to make a
    # workspace-confined server reach the network is a vulnerability. Making the
    # embedding engine the default in 0.3.0 would have broken that promise on
    # the very first tool an agent calls, on a machine whose whole point is that
    # it does not talk to anything.
    #
    # So under a workspace the model is used only if it is ALREADY cached, and
    # otherwise this raises and `catalog.search` falls back to BM25 with the
    # `engine` field saying so. An operator who wants embeddings in sandbox mode
    # warms the cache once outside it, or uses the container image. The promise
    # stays testable, which was the point of writing it that way.
    from . import workspace

    path = snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        allow_patterns=list(MODEL_FILES),
        local_files_only=workspace.root() is not None,
    )
    return StaticModel.from_pretrained(path)


def warm_cache() -> str:
    """Fetch the model into the local cache, deliberately and outside sandbox mode.

    Exists for the container build, and for an operator who wants embeddings on
    a workspace-confined server: under a workspace `_model` refuses to download,
    so the cache has to be filled by someone who means to fill it. Returns the
    snapshot path so a build step can fail loudly if nothing arrived.
    """
    snapshot_download, _ = _require()
    return snapshot_download(
        MODEL_ID, revision=MODEL_REVISION, allow_patterns=list(MODEL_FILES)
    )


def embed(texts: list[str]):
    """Embed texts to unit-norm float32 vectors, deterministically."""
    return _model().encode(list(texts), use_multiprocessing=False)


@cache
def _index():
    """Embedded catalog corpus, built once per process from the same text BM25 reads."""
    import numpy as np

    from . import catalog

    vectors = embed([catalog.document_text(op) for op in catalog.OPERATIONS])
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


@cache
def _row_of() -> dict[str, int]:
    """Catalog name to its row in :func:`_index`, so a narrowed candidate set
    can be scored against the same embeddings instead of a second index."""
    from . import catalog

    return {op["name"]: row for row, op in enumerate(catalog.OPERATIONS)}


def rank(
    query: str,
    limit: int = 10,
    candidates: list[dict[str, Any]] | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Catalog entries ranked by cosine similarity to the query.

    Same signature and tie-break as :func:`mapsmith.catalog.rank`, so the two
    engines are interchangeable behind one interface and comparable in one
    harness. ``candidates`` restricts the ranking to an already-narrowed subset
    (the deterministic applicability filter runs first, for both engines).
    """
    import numpy as np

    from . import catalog

    operations = catalog.OPERATIONS if candidates is None else candidates
    if not operations:
        return []
    vector = embed([query])[0]
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return [(op, 0.0) for op in operations][:limit]
    rows = _row_of()
    matrix = _index()[[rows[op["name"]] for op in operations]]
    scores = matrix @ (vector / norm)
    ranked = sorted(
        zip(operations, (float(s) for s in scores), strict=True),
        key=lambda pair: (-pair[1], pair[0]["name"]),
    )
    return ranked[:limit]
