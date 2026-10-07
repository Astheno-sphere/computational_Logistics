# Demos

This file describes the built-in example materials and how they support routing inside the skill.

## Built-In Assets

### Layout Atlas

`assets/layout-atlas/` contains several composite-figure wireframes:

- `atlas-01-2x2-grid.svg`
- `atlas-02-hero-plus-row.svg`
- `atlas-03-triptych-with-legend.svg`
- `atlas-04-image-plus-quant.svg`

These are structure references only. Reuse the panel logic, not the placeholder text or exact dimensions.

## Recommended Use

### When choosing a panel arrangement

Open the relevant `assets/layout-atlas/*.svg` file, pick the closest evidence layout, and then write a
matching `compose-figure` JSON spec.

### When recalling the CLI surface

Return to the Quick Reference in `SKILL.md` and verify which command is needed:

- `load-context`
- `list-tables`
- `data-summary`
- `query-data`
- `run-eda`
- `compose-figure`
- `collect-assets`

### When selecting a chart form

Check the references in this order:

1. `references/figure-contract.md`
2. `references/charts.md`
3. `references/chart-recipes.md`
4. `references/common-patterns.md`

## Relation to Project Tests

`packages/agentsociety2/tests/test_analysis_cli.py` already covers the core mechanical behaviors:

- plotting scaffold validation
- SVG text export requirements
- `compose-figure` grid and manual layouts
- companion-file filtering during asset collection

That means most future evolution should happen in the skill contract and reference docs, not in a parallel CLI surface.
