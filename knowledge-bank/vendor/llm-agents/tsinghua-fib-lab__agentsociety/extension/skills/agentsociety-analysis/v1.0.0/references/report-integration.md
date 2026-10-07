# Report Integration (EDA → Charts → Final Report)

Goal: **one narrative thread**. Tool outputs stay in `data/` and `charts/`, but the **final report** must synthesize them — not leave EDA in a silo.

## Pipeline

```text
explore: run-eda → presentation/hypothesis_{id}/data/eda_*
         record-phase-artifacts (paths)
claims:  record-claim (evidence pointers)
refine:  chart generation → charts/chart_*.png
         record-contract
produce: prepare-produce  ← builds context; syncs explicit write-side assets
         dispatch report-producer (or equivalent) reading data/report_context.md
         write report_zh.md / report_en.md (sections cite EDA + charts)
         write analysis_summary.json, report_outline.json, artifact_manifest.json
         prepare-produce  ← refresh after report references are final
         validate-release  ← presentation-read-only gate; records harness state
```

## Mechanical preparation (`prepare-produce`)

```bash
$PYTHON_PATH .agentsociety/bin/ags.py analysis prepare-produce \
  --workspace . --hypothesis-id $HYP_ID --experiment-id $EXP_ID
```

Writes:

| File                                                              | Role                                                                                |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `data/evidence_index.json`                                        | Machine index: every source, `kind`, `phase`, target `report_section`               |
| `data/report_context.md`                                          | LLM digest: excerpts grouped by overview / data / findings / conclusions / appendix |
| `.agentsociety/analysis/hypothesis_{id}/prepare_produce_manifest.json` | Input/output fingerprints for idempotent preparation steps                          |

`prepare-produce` plans three independently cached steps: `report_context`,
`report_assets`, and `interactive_eda`. An unchanged rerun returns `UNCHANGED` and does
not rewrite outputs or the manifest. Changed source evidence, report asset references,
EDA inputs, missing outputs, or manually changed outputs invalidate only the affected
steps. The manifest is atomically replaced only after every scheduled step succeeds.
Use `prepare-produce ... --dry-run` to inspect the `RUN` / `SKIP` plan without writing.

Sources pulled from:

- `phase_artifacts` in harness state (EDA paths you registered)
- All files under `data/` (except the index itself)
- `charts/chart_*.png`, `charts/figure_*.png`
- `claims.json` and `figure_contracts` in harness state

## How to write each report section

| Section         | Integrate                                                                                                                                             |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **overview**    | Research question from `analysis_plan.yaml`; experiment design one paragraph                                                                          |
| **data**        | **Synthesize** `eda_quick_stats.md` / profiling HTML takeaways — row counts, missingness, metric ranges; link `data/eda_*.html` in appendix if needed |
| **findings**    | One subsection per confirmatory claim; embed `assets/chart_*.png`; numbers must match SQL/EDA                                                         |
| **conclusions** | Answer research question; copy limitations from plan + explore attestation                                                                            |
| **appendix**    | Artifact table + optional EDA HTML links                                                                                                              |

## Rules

1. **Do not** paste full EDA HTML into the report body — summarize in prose + tables; link full `data/eda_*.html` in appendix (see `report-embeddings.md`).
2. **Do** register every explore output via `record-phase-artifacts` so it enters `evidence_index.json`.
3. **Do** run `prepare-produce` before drafting and again after report references are final. `validate-release` never copies or rewrites presentation artifacts; it only records the resulting harness gate state.
4. HTML (required): LLM-authored `report_zh.html` / `report_en.html` per `references/reports.md` and `assets/report-shell.reference.html` — required for `validate-release` PASS.
5. Missing report-referenced assets make `prepare-produce` fail explicitly; fix the chart path instead of accepting a partial manifest.

## Synthesis (Stage 6)

Run `build-report-context` per hypothesis first. In `synthesis_brief.json` list `source_artifacts` including each `data/report_context.md` or `report_zh.md`. Cross-hypothesis synthesis should **compare** integrated findings, not re-scatter raw EDA files.

See `references/report-template-simulation.md` for the simulation-report structure.
