# Synthetic browser snapshot controls

`jev.case_browser` generates independently authored training data for the existing
`jev.community.browser_request` contract. The initial `browser-control-v1`
corpus covers finite, templated goals over an observed DOM snapshot. It is
separate from the frozen `release-v2` training mixture and has not been trained
or evaluated on a model as part of this data build.

This is partial browser coverage. It does not provide a browser executor,
multi-page application simulator, arbitrary text generation, hidden-page search,
or evidence of general web-task competence. No external task items, JF100
records, screenshots, real websites, or GPU inference were used to construct it.

## Reproduce

```bash
python -m jev.case_browser --output-dir data/browser-v1 --groups 1000 --ood-groups 200 --seed 42
python -m jev.data validate data/browser-v1
python -m unittest discover -s tests -p test_browser_data.py -v
```

The output directory must be empty or absent; the generator refuses to overwrite
existing data. Generated JSONL files stay under the repository's ignored `data/`
directory. The checked-in [manifest](../reports/data-manifests/browser.json)
records split-file hashes, the full-case hash, generator/runtime source hashes,
supervision counts, and generation settings. Synthetic examples are marked
`CC0-1.0` in their provenance.

## Generated build counts

Seed 42 produces **1,000 parent scenes**, including 200 OOD parents, and
**12,660 distinct requests** after within-parent duplicate removal. Their
**21,980 supervised Choice records** comprise 12,660 operation decisions and 9,320
active conditional decisions. Every row has a deterministic one-hot reference;
these labels do not establish calibrated outcome probabilities.

| Split | Parent scenes | Requests | Supervised records |
| --- | ---: | ---: | ---: |
| Train | 631 | 7,970 | 13,814 |
| Calibration | 40 | 496 | 848 |
| Validation | 28 | 352 | 608 |
| Test | 101 | 1,306 | 2,302 |
| OOD | 200 | 2,536 | 4,408 |

| Reference operation | Requests |
| --- | ---: |
| CLICK | 1,675 |
| TYPE_TEXT | 2,331 |
| SELECT | 2,324 |
| WAIT | 1,000 |
| DONE | 1,665 |
| BLOCKED | 3,665 |

`SCROLL_UP` and `SCROLL_DOWN` remain offered runtime candidates, but this corpus
does not contain positive scrolling examples: its disclosed task policy is
limited to the supplied snapshot.

## Visible task and teacher

The input is an ordinary `browser_request(goal, snapshot, text_candidates)`.
Observed widgets carry opaque shuffled IDs, an exact label, a `scope_path`,
allowed `actions`, and current values. Visible section records carry
`scope_path` and `aria_busy`. These are caller-supplied snapshot facts preserved
by the existing adapter, rather than new hidden adapter state. TYPE_TEXT values
come from a finite caller-supplied ID-to-string catalog; SELECT values come from
the observed widget's ID-to-label options.

The three in-distribution goal forms are:

```text
Turn on "Notifications" in "Workspace <nonce>".
Enter "<candidate address>" into "Contact email" in "Workspace <nonce>".
Select "<candidate order>" for "Sort order" in "Workspace <nonce>".
```

Every goal then includes the complete `CONTROL_POLICY` text from the generator.
That text discloses the following precedence to the model:

1. Match the complete scope path and exact widget label. If exactly one widget
   matches and its current value already satisfies the goal, choose DONE. This
   takes precedence over a busy section or unavailable action.
2. Otherwise, choose WAIT when the requested section is visibly busy.
3. Otherwise, choose BLOCKED for a missing/ambiguous widget, unavailable requested
   action, or a requested value with zero or multiple matching offered IDs.
4. Otherwise, choose the requested action and its observed target ID, plus the
   corresponding finite text/option ID for TYPE_TEXT or SELECT.

The teacher reads only these visible facts and the goal. It does not inspect
case metadata, future observations, trajectories, real browser state, or page
instructions. Completed switches use `aria_checked`; text fields use `value`;
dropdowns resolve `selected_option_id` through the observed `options`. The parser
intentionally accepts only the six declared ID/OOD goal templates with their
disclosed control policy. It is a synthetic reference rule, not a natural-language
browser agent.

Each parent includes same-label controls in other scopes, an alternative target
in the requested scope, and controls for inactive action branches. Variants
change completion, requested-section busy state, target/whole-operation
availability, value availability, ambiguous duplicate targets, the caller's
target, page instructions, IDs/order, and single-candidate conditions. For text
and select tasks, all three symmetric candidate values become requested values
across goal-only counterfactuals with the **identical snapshot**; one is already
satisfied. This prevents a value head from learning a fixed preferred string
without reading the caller's goal. The two authored hostile page-text templates
test instruction boundaries within this synthetic setting only.

## Exact conditional supervision

Each case stores the complete runtime request and only its defined active
answers. `records_from_cases` rebuilds `browser_request`, rejects changed
questions/candidate order, and invokes `compile_request` directly. Training
`state`, `question`, `kind`, and `options` are exactly the compiled runtime input;
targets are mapped through the compiled `answer_keys`. Provenance, group IDs,
variant names, and gold labels are absent from candidate prompts.

For CLICK the active heads are `operation` and `click_target`. TYPE_TEXT and
SELECT additionally activate the value head belonging to the selected widget.
WAIT, DONE, and BLOCKED supervise **only `operation`**. The build omits and counts
**68,218 inactive conditional heads**; it does not assign them arbitrary labels.

The training schema requires at least two options, while the runtime permits
one-candidate Choices. The generator therefore also omits and counts **1,665
forced single-candidate active heads**: 1,000 target heads and 665 value heads.
It retains their exact single-candidate runtime questions in `cases.jsonl` and
never invents competing options. A complete inference response still must be
schema-valid for every requested question; active training gold and full
response validation are separate concerns.

Runtime `text_value_N` indices follow `text_candidates` insertion order, and
`select_value_N` indices follow observed SELECT element order. Accordingly,
`cases.jsonl` preserves mapping order on disk. Do not sort its request mappings
when reserializing them. Split-row serialization is safe because each row
already contains its exact question and ordered option list. Tests exercise
disk round trips, target/value reindexing, complete proposal reconstruction, and
prompt equality after persistence.

## Split boundaries and limits

Every parent's counterfactuals and ID permutations share its group and split.
In-distribution groups use the repository's deterministic group splitter.
Dedicated OOD groups use different labels and candidate vocabulary, rephrased
goals beginning with `Within ...`, nested scope paths, and additional nested or
read-only distractors. OOD templates never enter the ID splits.

This OOD set changes the composition and wording of the same three control
families. It does not measure unfamiliar websites, navigation, a broader
language distribution, or unseen applications. Train and evaluation data both
come from the disclosed generator. Multi-step browser state machines and real
browser execution remain follow-up work; see [training coverage gaps](training-coverage-gaps.md).
