# Stage 3: Insight and Visualization

Goal: convert data understanding into a small set of findings with evidence-backed charts.

## Steps

1. Propose 3-5 candidate findings in text first. For each finding, name the supporting table or query and say whether a chart is necessary.
2. For each finding that needs a visual artifact, write a short figure contract using `references/figure-contract.md`: core finding, figure scope, chart role, evidence source, analysis scope, figure archetype, visual center, highlight, legend strategy, output files, and reviewer check.
3. For each approved contract, explain the chart type, query or computation logic, and expected takeaway. Use `references/charts.md` when choosing chart forms.
4. Prefer one clear visual center per finding. If the same finding needs several views, define a panel map first and use `references/composite-figures.md` rather than pasting unrelated screenshots side by side.
5. Wait for the user to confirm, trim, or revise the finding and chart plan before generating visuals.
6. Generate atomic charts one by one by writing Python scripts under `$CHARTS_DIR` and executing them with `$PYTHON_PATH`.
7. Keep generated code and chart outputs under `$CHARTS_DIR`. Name atomic chart files according to `references/harness-contract.md`, for example `chart_{nn}_{description}.png`.
8. When a finding requires panel assembly, write a JSON spec under `$CHARTS_DIR`, then run `$PYTHON_PATH .agentsociety/bin/ags.py analysis compose-figure --workspace . --hypothesis-id ID --spec $CHARTS_DIR/figure_{nn}_{description}.json`. Use the command output `figure_{nn}_{description}.png` as the report-facing artifact and keep the JSON sidecar for traceability.
9. In matplotlib scripts, include the `Agg` backend and an rcParams block that sets sans-serif fonts plus `svg.fonttype = "none"`. When a chart will likely be reused, pull palette and layout defaults from `references/api.md`, `references/charts.md`, and `references/common-patterns.md`. Keep same-stem `.svg` exports whenever later text adjustment is plausible.
10. Legend text must stay in English even if the surrounding discussion is Chinese. Use English-only values for `label=...`, `labels=[...]`, and `legend(...)`.
11. After each chart or composite figure, show the result, explain what it supports, and revise if requested.
12. If a chart needs extra verification, use `$PYTHON_PATH .agentsociety/bin/ags.py analysis query-data` before regenerating it, and run the final pass against `references/harness.md#qa-contract`.
13. If the same chart code fails three times, stop and ask whether to skip, simplify, or revise the finding.
14. Once the user confirms the findings set, prepare a structured claims JSON payload with one entry per confirmed finding. Each entry should include at least `statement`, `confidence`, and `evidence`.

## Exit Conditions

- Findings are confirmed by the user.
- Any approved charts are generated within budget and tied to those findings.
