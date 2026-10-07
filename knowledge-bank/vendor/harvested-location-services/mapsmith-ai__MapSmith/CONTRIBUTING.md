# Contributing to MapSmith

Thanks for your interest! A few ground rules keep this project sustainable for a small team.

## Ways to contribute

- **New operations**: open a PR adding an engine function + MCP tool + catalog entry + test. Small, focused PRs merge fastest. (There is deliberately no plugin API yet — new tools land in core through one review queue.)
- **Bug reports**: use the issue template. We aim for a **first response within 48 hours**.
- **Docs & analysis notebooks**: gallery examples (prompt → tool chain → map) are as valuable as code.

## Environment support policy

**Docker (or `uvx` where wheels work) is the only supported install path.** Issues that reduce to a broken local GDAL/compiler setup will be closed with a pointer to the container. This is not unfriendliness — it is how a small team keeps the 48h response promise.

## Development setup

```bash
pip install -e .[test]
pytest -q
ruff check .
```

## Design rules (enforced in review)

1. **Deterministic outputs only.** No geometry or numeric result may originate from an LLM.
2. **Every writer emits provenance.** If your operation writes a dataset, it writes a manifest (`ProvenanceRecord`) — inputs with checksums, parameters, CRS decisions, engine versions.
3. **No silent CRS decisions.** Reprojections and unit assumptions must be recorded in `crs_decisions` — and under the names [the manifest specification](https://github.com/mapsmith-ai/manifest-spec) recommends (`analysis_crs`, `source_crs`, `target_crs`, `transformation`, `reason`). Anything the specification does not name is MapSmith's own and says so: `x-mapsmith:<name>`. Inventing a synonym is the defect this rule was written for — two operations recorded `measurement_crs` and `declared_output_crs`, each defensible alone, and a consumer asking those records what they computed in read `analysis_crs` and found nothing. A test in `tests/test_verify.py` sweeps every writing site, so review is not the only thing holding this.
4. **GPL isolation.** GPL engines (QGIS, GRASS) may only be invoked as external processes (CLI/files/JSON). Never `import qgis` or link GPL libraries in-process.
5. **Few semantic tools.** New MCP tools need a strong case; prefer extending the catalog + existing tools.

## Contributor License Agreement

To keep dual-licensing possible (AGPL + commercial), we ask contributors to sign a lightweight CLA on their first PR. There is no bot yet: if you open the first outside PR, we will agree the wording with you in the thread rather than block the merge on tooling that does not exist. Your code always remains available under AGPL-3.0.

## Code style

Python ≥3.12, `ruff` clean, type hints on public functions, tests for every operation.
