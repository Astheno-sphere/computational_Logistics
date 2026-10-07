# Bundled support for agentsociety-analysis

Read **`references/integrations.md`** for when to invoke each bundle during Stages 2, 4, and 5.

| Bundle                      | Stage     | Read                                           |
| --------------------------- | --------- | ---------------------------------------------- |
| `interactive-viz/`          | 2 Explore | Before `run-eda` mode selection                |
| `scientific-visualization/` | 4 Refine  | When chart QA fails or polish needed           |
| `report-blocks/`            | 5 Produce | **Required** for report-producer HTML assembly |
| `frontend-design/`          | 5 Produce | After content correct — typography/layout only |

Workspace path after preset sync:

```text
.claude/skills/agentsociety-analysis/support/<bundle>/SKILL.md
```

Office skills (`pdf`, `docx`, `pptx`, `xlsx`) live at `.claude/skills/` — Stage 5+ on user request only.

Cross-skill integrations (literature, datasets, hypothesis, paper-toolkit): `references/integrations.md`.
