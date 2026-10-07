# Catalog alignment with field evidence

`entity-alignment-control-v1` adds a callable four-head task builder and a
separate original synthetic corpus: **200 family groups, 2,800 record pairs and
11,200 typed records**. It has not been trained, run through a model or added to
either frozen training mixture. The existing `jev.recipes.entity_alignment`
default and shared recipe/API/data source files remain unchanged.

This is our own catalog contract for **name, manufacturer and capacity**. It
does not reproduce the official cookbook's name/brewery/style task or use its
Magellan examples. All names, identifiers, alias tables and paired records are
original controls; no JF100 item or external model result supplies a label.

## Four heads and complete visible policy

| Head | Type | Reference decision |
| --- | --- | --- |
| `match` | Score | 0: different; 1: review; 2: same |
| `name_agrees` | Noul | Visible alias evidence establishes canonical name agreement |
| `manufacturer_agrees` | Noul | Visible alias evidence establishes canonical manufacturer agreement |
| `capacity_agrees` | Noul | Both known quantities convert to the same exact mL value |

Every request contains `left`, `right`, the complete `policy`, and
`capacity_evidence`. Labels and family metadata stay outside model input.
The builder reuses the existing entity recipe's Score levels and adds the three
Nouls in the new module. It does not change shared recipe behavior.

The input declares these rules, in order:

1. Two populated identifiers in the same namespace but with different values
   imply **different** under this policy.
2. Otherwise, any known field conflict implies **review** if the identifiers
   agree, and **different** if identifier agreement has not been established.
3. Otherwise, matching identifiers or agreement of all three fields imply
   **same**.
4. All remaining patterns imply **review**.

Identifier namespaces and values are case-sensitive after trimming outer
whitespace. Different namespaces or missing components provide unknown identity
evidence; they are not themselves conflicts. Text fields collapse whitespace
and casefold, but only the supplied canonical keys and explicit aliases are
recognized. Distinct recognized canonicals conflict. Missing or unlisted text
is unknown, even if two unlisted strings are identical.

Each Noul asks whether agreement is **established**. Both conflict and unknown
therefore have a no reference target; missing evidence is never assigned an
invented 0.5 confidence. A no does not establish physical inequality. Score 1
is the declared review action, not a fitted confidence threshold.

In particular, this policy permits **same with missing attributes when the
identifiers agree and no known conflict exists**. It also permits same without
comparable identifiers when all three fields are established equal. These are
explicit controlled-catalog decisions, not universal facts about entity
identity or permission to merge production records.

## Exact quantity evidence

Capacity is a visible `{value, unit}` object. Values must be positive ordinary
ASCII decimal strings, with no sign, exponent or fraction. Mixed Unicode digit
strings are invalid and provide unknown evidence. The visible unit table
gives `mL = 1`, `L = 1000` and `cL = 10` mL. The builder uses rational arithmetic
to populate each side's `capacity_evidence` as an exact rational mL string; it
does not use binary floating-point comparisons. Missing or invalid values and
unrecognized units yield unknown evidence.

The converted facts are deterministic preprocessing, not model predictions.
The capacity Noul judges whether those facts establish agreement. The audit
recomputes them independently from the raw records and the visible unit table.

## Call the builder

```python
from jev.case_entity_alignment import entity_alignment_fields

request = entity_alignment_fields(
    {
        "identifier": {"namespace": "example-catalog", "value": "VES-17"},
        "name": "Lumen Flask",
        "manufacturer": "Alder Instruments",
        "capacity": {"value": "0.75", "unit": "L"},
    },
    {
        "identifier": {"namespace": "example-catalog", "value": "VES-17"},
        "name": "LF-750",
        "manufacturer": "Alder Instr.",
        "capacity": {"value": "750", "unit": "mL"},
    },
    name_aliases={"Lumen Flask": ["LF-750"]},
    manufacturer_aliases={"Alder Instruments": ["Alder Instr."]},
)
```

The corresponding [request-only example](../examples/entity-alignment-fields.json)
contains no targets or answers. It compiles through the existing API and is
discovered by the server's `/examples.json` listing. No inference response has
been fabricated for it. The builder validates alias tables and rejects one alias
being assigned to two different canonical values.

## Corpus construction and grouping

Each family supplies its own original aliases and identifiers, then 14 observed
pair variants. They cover equivalent units and aliases, conflicting IDs despite
matching fields, equal IDs with a capacity conflict, individual field conflicts,
individual missing fields, equal IDs with a missing name, different namespaces,
unlisted names and a record with all fields missing.

All shared entities, aliases and pairs stay inside the same family group. ID
families use catalog wording and one alias grammar. The 40 reserved OOD families
use procurement wording, a separate alias grammar and cL/mL presentation. These
are controlled wording, alias and unit-presentation changes; they do not test
unrestricted catalog matching, new identity policies or arbitrary unit parsing.

| Split | Families | Pairs | Typed records |
| --- | ---: | ---: | ---: |
| Train | 124 | 1,736 | 6,944 |
| Calibration | 13 | 182 | 728 |
| Validation | 5 | 70 | 280 |
| Test | 18 | 252 | 1,008 |
| OOD | 40 | 560 | 2,240 |

Overall reference routes are 800 different, 1,200 review and 800 same. Each field
includes established agreement, known conflict and unknown evidence. The
reference labels are derived from visible records and policy, never from a
hidden family identifier. These counts are not model performance.

## Generate and verify

Use a new directory in a local checkout; the generator refuses nonempty and
symlinked outputs. Python 3.10+ and the standard library are sufficient.

```bash
python -m jev.case_entity_alignment \
  --output-dir data/entity-alignment-control-v1 --groups 200 --ood-groups 40 --seed 42
python -m jev.data validate data/entity-alignment-control-v1
python reports/entity-alignment-control-v1/verify.py \
  --data data/entity-alignment-control-v1 --output runs/entity-alignment-control-v1-audit.json
python3 -m unittest tests.test_entity_alignment_control -v
```

`--groups` includes OOD families. The ignored corpus contains five standard
split files, `families.jsonl`, `cases.jsonl` and `manifest.json`. The
[tracked manifest](../reports/data-manifests/entity-alignment-control-v1.json)
binds source-code and data hashes. Original generated catalog records and
annotations are CC0-1.0; this does not relicense upstream task documentation or
model weights.

The independent audit reads the final visible records and policy, independently
resolves aliases and quantities, and recomputes all four references. It does not
use the generator's reference function or family specifications as an oracle.
It also checks exact runtime compilation, per-family splitting, alias/identifier
isolation, complete four-head coverage and artifact hashes.

Saved verification is available in the [independent audit](../reports/entity-alignment-control-v1/independent-audit.json),
[build and example checks](../reports/entity-alignment-control-v1/build-verification.json),
[test execution record](../reports/entity-alignment-control-v1/test-verification.json)
and [frozen-input checks](../reports/entity-alignment-control-v1/frozen-inputs-check.json).
The independent audit passed on all 11,200 records. The final unit-test run passed
all 23 tests, with zero failures, errors or skips; its exact command, output and
earlier attempts are retained in the test execution record.
The final corpus uses the explicit ASCII decimal rule; the earlier uncommitted
candidate and its build evidence were preserved under the ignored
`data/entity-alignment-control-v1-draft-unicode-boundary/` directory before the
final corpus was rebuilt.

There is no network executor, curator queue or graph merge. No route accuracy,
false-merge rate, merge precision, Brier score or calibrated acceptance threshold
is claimed. Those require a separate model evaluation after an explicitly
selected future training run; this dataset preparation does not alter current
27B training or any released checkpoint capability.
