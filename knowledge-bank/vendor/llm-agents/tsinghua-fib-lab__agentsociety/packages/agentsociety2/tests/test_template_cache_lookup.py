"""模板缓存复用判定：以"代码实际必读的变量"为准，而非 variable_keys 快照。

回归背景（300-agent 模拟实测）：
- 指令串逐字符相同、相似度 1.0，仅因调用方多带一个变量即被键集互含过滤
  否决，回退全量 LLM codegen（6064ms vs 1.4ms）；
- 反之 current ⊆ cached 方向会放行缺必读变量的命中，而缓存代码
  max_retries=0，执行失败（KeyError）无回退。
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import faiss
import numpy as np
import pytest

from agentsociety2.env.router_codegen import (
    CacheCodeProvider,
    CacheEntry,
    _code_variable_reads,
    _entry_usable_with,
)

_VOTE_CODE = """
results['status'] = 'ok'
await modules['Voting'].vote(
    ctx['variables']['agent_id'],
    ctx['variables']['proposal_id'],
    ctx['variables']['support'],
)
"""


def _make_entry(
    instruction: str,
    code: str,
    variable_keys: tuple[str, ...] = (),
    success_count: int = 1,
) -> CacheEntry:
    return CacheEntry(
        instruction_template=instruction,
        variable_keys=variable_keys,
        variable_types={k: "str" for k in variable_keys},
        code=code,
        env_class_type="stub_env",
        success_count=success_count,
    )


def _make_router(
    entries: list[CacheEntry], faiss_index: faiss.IndexFlatIP | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        _template_cache_enabled=True,
        _template_cache_lock=asyncio.Lock(),
        _cache_entries=entries,
        _cache_faiss_index=faiss_index,
        _cache_faiss_entry_indices=(
            list(range(len(entries))) if faiss_index is not None else []
        ),
        _env_class_type_key="stub_env",
        _template_cache_similarity_threshold=0.85,
    )


def _stub_embedding(
    monkeypatch: pytest.MonkeyPatch, vector: np.ndarray | None = None
) -> None:
    async def fake(router, text):
        return np.zeros(4, dtype=np.float32) if vector is None else vector

    monkeypatch.setattr(CacheCodeProvider, "_compute_embedding", fake)


@pytest.mark.asyncio
async def test_exact_match_hits_without_embedding_and_extra_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """报告复现用例：代码不读任何变量时，多带的变量不得否决精确命中。

    精确匹配快速路径必须在计算 embedding 之前返回——_compute_embedding
    在此被替换成"一旦调用即失败"，证明该路径无需 embedding 端点。
    """

    async def _must_not_run(router, text):
        raise AssertionError("exact match must not compute embeddings")

    monkeypatch.setattr(CacheCodeProvider, "_compute_embedding", _must_not_run)

    entry = _make_entry(
        "Call list_tasks()",
        code="results['n'] = len(modules['X'].items())",
        variable_keys=("level",),
    )
    router = _make_router([entry])

    for variables in ({}, {"agent_id": 1}, {"agent_id": 1, "level": "M"}):
        hit, reason = await CacheCodeProvider._lookup(
            router, "Call list_tasks()", variables
        )
        assert (hit, reason) == (entry, None)


@pytest.mark.asyncio
async def test_exact_match_requires_code_read_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """模板无占位符不代表代码不读变量：缺必读键必须未命中。"""
    _stub_embedding(monkeypatch)
    entry = _make_entry(
        "Call vote()",
        code=_VOTE_CODE,
        variable_keys=("agent_id", "proposal_id", "support"),
    )
    router = _make_router([entry])

    hit, reason = await CacheCodeProvider._lookup(
        router,
        "Call vote()",
        {"agent_id": 1, "proposal_id": 2, "support": True},
    )
    assert (hit, reason) == (entry, None)

    # 旧逻辑（current ⊆ cached）此处会命中，随后 KeyError 且 max_retries=0
    for variables in ({"agent_id": 1}, {"agent_id": 1, "support": True}):
        hit, reason = await CacheCodeProvider._lookup(router, "Call vote()", variables)
        assert (hit, reason) == (None, "variable_keys_incompatible")


@pytest.mark.asyncio
async def test_exact_match_scans_all_same_instruction_entries() -> None:
    """同一指令多条目、需求不同：首条不满足须继续找，不得整体回退。"""
    needs_more = _make_entry(
        "Call act()",
        code="results['x'] = ctx['variables']['agent_id'] + ctx['variables']['level']",
        variable_keys=("agent_id", "level"),
        success_count=5,
    )
    needs_less = _make_entry(
        "Call act()",
        code="results['x'] = ctx['variables']['agent_id']",
        variable_keys=("agent_id",),
        success_count=1,
    )
    router = _make_router([needs_more, needs_less])

    hit, _ = await CacheCodeProvider._lookup(router, "Call act()", {"agent_id": 1})
    assert hit is needs_less

    # 都满足时取 success_count 高者
    hit, _ = await CacheCodeProvider._lookup(
        router, "Call act()", {"agent_id": 1, "level": 2}
    )
    assert hit is needs_more


@pytest.mark.asyncio
async def test_get_with_default_is_not_required() -> None:
    """.get 带默认值语义，缺键不抛错：不构成必读键。"""
    entry = _make_entry(
        "Call report()",
        code="results['level'] = ctx['variables'].get('level', 'none')",
        variable_keys=("level",),
    )
    router = _make_router([entry])

    # 旧逻辑：current {'unrelated'} 与 cached {'level'} 部分重叠 → 未命中
    hit, reason = await CacheCodeProvider._lookup(
        router, "Call report()", {"unrelated": 1}
    )
    assert (hit, reason) == (entry, None)


@pytest.mark.asyncio
async def test_undeterminable_code_falls_back_to_variable_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """动态下标等不可静态分析的代码：退回 variable_keys ⊆ current 的保守判据。"""
    _stub_embedding(monkeypatch)
    code = "key = ctx['task_name']\nresults['v'] = ctx['variables'][key]"
    assert _code_variable_reads(code) is None

    entry = _make_entry("Call read_task()", code, variable_keys=("a", "b"))
    router = _make_router([entry])

    hit, _ = await CacheCodeProvider._lookup(
        router, "Call read_task()", {"a": 1, "b": 2, "c": 3}
    )
    assert hit is entry

    hit, reason = await CacheCodeProvider._lookup(router, "Call read_task()", {"a": 1})
    assert hit is None
    assert reason == "variable_keys_incompatible"


def _unit_index(dim: int, vectors: list[np.ndarray]) -> faiss.IndexFlatIP:
    index = faiss.IndexFlatIP(dim)
    for vec in vectors:
        emb = np.asarray([vec], dtype=np.float32).copy()
        faiss.normalize_L2(emb)
        index.add(emb)
    return index


@pytest.mark.asyncio
async def test_fuzzy_match_judged_by_code_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """相似度检索路径同样按代码必读键判定，键集部分重叠不再一票否决。"""
    vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

    async def fake(router, text):
        return vec.copy()

    monkeypatch.setattr(CacheCodeProvider, "_compute_embedding", fake)

    entry = _make_entry(
        "list all current tasks please",
        code="results['n'] = len(modules['X'].items())",
        variable_keys=("level",),
    )
    index = _unit_index(4, [vec])
    router = _make_router([entry], faiss_index=index)

    # 指令不完全相同（走相似度路径），current {'agent_id'} 与 cached
    # {'level'} 部分重叠：旧逻辑未命中（全量 codegen），新逻辑命中。
    hit, reason = await CacheCodeProvider._lookup(
        router, "list all current tasks", {"agent_id": 1}
    )
    assert (hit, reason) == (entry, None)


@pytest.mark.asyncio
async def test_fuzzy_match_rejects_missing_required_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vec = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)

    async def fake(router, text):
        return vec.copy()

    monkeypatch.setattr(CacheCodeProvider, "_compute_embedding", fake)

    entry = _make_entry(
        "vote on the active proposal",
        code=_VOTE_CODE,
        variable_keys=("agent_id", "proposal_id", "support"),
    )
    index = _unit_index(4, [vec])
    router = _make_router([entry], faiss_index=index)

    hit, reason = await CacheCodeProvider._lookup(
        router, "vote on the proposal", {"agent_id": 1}
    )
    assert (hit, reason) == (None, "variable_keys_incompatible")


def test_code_variable_reads_extracts_required_keys() -> None:
    code = (
        "v = ctx['variables']\n"
        "w = v\n"
        "results['a'] = ctx[\"variables\"]['agent_id']\n"
        "results['b'] = w[ 'level' ]\n"
        "results['c'] = ctx['variables'].get('optional')\n"
        "results['d'] = ctx['id']\n"
        "results['e'] = len(modules['X'].items())\n"
    )
    assert _code_variable_reads(code) == frozenset({"agent_id", "level"})


def test_code_variable_reads_undeterminable_cases() -> None:
    dynamic_key = "results['v'] = ctx['variables'][ctx['key_name']]"
    iterates = "results['v'] = [k for k in ctx['variables'].items()]"
    escapes = "helper(ctx['variables'])"
    rebinds = "v = ctx['variables']\nv = {}\nresults['x'] = v['k']"
    for code in (dynamic_key, iterates, escapes, rebinds, "def broken(:"):
        assert _code_variable_reads(code) is None


def test_code_variable_reads_handles_await_and_chaining() -> None:
    code = (
        "results['id'] = await modules['M'].tick(ctx['variables']['agent_id'])\n"
        "results['nested'] = ctx['variables']['profile']['name']\n"
    )
    assert _code_variable_reads(code) == frozenset({"agent_id", "profile"})


def test_entry_usable_with_fallback_for_undeterminable_code() -> None:
    entry = _make_entry(
        "Call read_task()",
        code="results['v'] = ctx['variables'][key]",
        variable_keys=("a",),
    )
    assert _code_variable_reads(entry.code) is None
    assert _entry_usable_with(entry, {"a", "other"}) is True
    assert _entry_usable_with(entry, set()) is False
