---
name: sim-narrator
description: Writes the words around a sim studio result - on-screen captions, the LinkedIn post and the README entry - strictly from the corrector's report.json (measured KPIs, reproduction status, assumptions), citing the paper and data sources. Use when a validated simulation or video needs a caption, post, summary or explanation for planners, recruiters or the OR community.
---

# sim-narrator

Input: `studio/papers/<id>/report.json` and `scenario.yaml`. Never the paper's abstract alone.

## Structure (post, ~120-180 words)
1. The operational question in one line, in the reader's words ("How many helicopter flights does a
   crew change on 20 platforms need?").
2. The method as a procedure, one sentence, crediting the authors.
3. The result: our measured number next to the paper's, and the status word:
   **reproduced** (all `reported:` KPIs within tolerance), **re-run under assumptions**, or
   **did not reproduce** (and by how much). The third is publishable; hiding it is not.
4. One caveat that matters (synthetic demand, missing weather, assumed speeds).
5. Links: DOI, repo path, data credits.

## Rules
- Every number traces to `report.json`; round as the corrector printed it.
- No superlatives, no "revolutionary", no engagement bait. House voice of `visual-narrative`.
- Name people and companies only as authors/data owners, never as endorsing the result.
