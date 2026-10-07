# Diagrams

System diagrams made with [Archify](https://github.com/tt-a1i/archify) (MIT, cloned in
`knowledge-bank/vendor/abm-visualisation/tt-a1i__archify`). Each diagram is typed JSON
(`candidate.json`). Archify renders it to a self-contained interactive HTML page and checks it:
schema, layout (no crossing or ambiguous routes, readable labels) and a real-browser check.

| Diagram | Static view | Interactive | Source |
|---|---|---|---|
| ABM system and thesis flow | [`abm-thesis-system.png`](abm-thesis-system.png) | [`abm-thesis-system.html`](workflow-abm-thesis-system-20261007-0450/abm-thesis-system.html)  | [`candidate.json`](workflow-abm-thesis-system-20261007-0450/candidate.json) |
| Hybrid agent tiers | [`agent-tiers.png`](agent-tiers.png) | [`agent-tiers.html`](workflow-agent-tiers-20261007/agent-tiers.html) | [`candidate.json`](workflow-agent-tiers-20261007/candidate.json) |
| Theory funnel | [`theory-funnel.png`](theory-funnel.png) | [`theory-funnel.html`](workflow-theory-funnel-20261007/theory-funnel.html) | [`candidate.json`](workflow-theory-funnel-20261007/candidate.json) |

Interactive versions are served on the [research atlas](https://astheno-sphere.github.io/computational_Logistics/) (GitHub Pages from `docs/`).

## How to improve a diagram

1. Edit `candidate.json`: add a node (lane, column, label, `subtitle` for tools, `tag` for status)
   or an edge.
2. Re-render and check:
   ```bash
   ARCHIFY=knowledge-bank/vendor/abm-visualisation/tt-a1i__archify/archify/bin/archify.mjs
   D=docs/diagrams/workflow-abm-thesis-system-20261007-0450
   ARCHIFY_CHROME=/path/to/chrome node $ARCHIFY finalize workflow $D/candidate.json $D/abm-thesis-system.html --quality showcase --json
   ```
3. Only a run that exits 0 counts. If it fails, the diagnostics name the edges that cross or share a
   corridor; move a node or pin an edge's `fromSide`/`toSide`, then run again.
4. Update the PNG (a screenshot of the HTML) and commit both.

For a major revision, start a new folder `workflow-<slug>-<date>/` so earlier versions stay.
