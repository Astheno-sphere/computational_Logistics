# Currency Mapping Artifacts

## Source of Truth

- `country_currency_map.csv` is the authoritative country->currency timeline join contract.
- FX runtime mapping logic should use this file directly.

## Derived Artifact

- `currency_lifecycle.csv` is derived from `country_currency_map.csv`.
- It is for QA/reference/transition review and should not be used as primary join input.

## Rule

1. Edit mapping rules in `country_currency_map.csv` (or its generator inputs).
2. Regenerate `currency_lifecycle.csv`.
3. Do not hand-edit `currency_lifecycle.csv`.
