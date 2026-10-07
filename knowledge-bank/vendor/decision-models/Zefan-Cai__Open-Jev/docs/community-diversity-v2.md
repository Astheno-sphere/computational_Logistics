# Community diversity v2

This corpus adds **51,200 original synthetic decision records** across eight operational domains. Its 80 authored policy families use explicit, verifiable conditions, including conjunctions, negation, exceptions, joins, time windows, arithmetic, missing evidence and near-identical candidates. Community posts motivate the task categories; no post examples, benchmark items, model errors or gold answers are generation inputs.

Generate the frozen default corpus with:

```bash
python -m jev.community_diversity_v2 \
  --output-dir data/community-diversity-v2 \
  --groups-per-family 80 --seed 20260921
```

The generator refuses a nonempty output directory. It uses only the Python standard library and the repository's existing schema writer. It makes no network requests, reads no source dataset, and does not train a model. Its source SHA-256 and all output-file hashes are in the [manifest](../reports/community-diversity-v2/manifest.json).

| Domain | Records | Authored families | Examples of distinct policies |
| --- | ---: | ---: | --- |
| Customer support | 6,400 | 10 | Refund eligibility, warranty exceptions, recovery factors, duplicate charges, partial returns, privacy exports |
| Information retrieval | 6,400 | 10 | Exact revisions, upgrade edges, regional/time scope, connecting routes, stock after reservations, authentication migration |
| Contract clauses | 6,400 | 10 | Non-competes, renewal, audit rights, liability carve-outs, assignment, confidentiality, cure periods, venue, exclusivity, control changes |
| RAG grounding | 6,400 | 10 | Two-hop joins, temporal facts, superseding evidence, unit-consistent totals, citation coverage, explicit negative evidence |
| Browser and tool decisions | 6,400 | 10 | Stale DOM targets, typing fallback, pagination, date ranges, capability scopes, argument binding, idempotent retries |
| Shell-history ranking | 6,400 | 10 | Repository/environment match, quoted paths, literal searches, Git inspection, extraction, lockfiles, port inspection |
| Game planning | 6,400 | 10 | Safe paths, dodging, ammunition, reload cover, healing, escort, braking, overtaking, pit stops, crafting dependencies |
| Rubric judging | 6,400 | 10 | Grounded summaries, negation, content plus schema, conversions, abstention, fair comparisons, instruction priority, trace consistency |

There are **6,400 source scenarios**, each with four related contexts and two task views per context. These yield **25,600 distinct contexts**, not 51,200 independent situations. Context deduplication ignores candidate names, ordering, serialization and a uniform shift of all ranking values. The corpus includes 19,200 counterfactual pairs; each pair changes exactly one visible fact and changes the selected decision. Each four-context group includes a case requiring abstention.

The first six authored families in every domain belong to training. One whole family per domain is assigned to each of calibration, validation, test and OOD. This gives 30,720 training rows and 5,120 rows in each held-out split. Families, generator source identifiers, source scenarios and semantic contexts do not cross splits. These are held-out specifications within a shared construction grammar, rather than claims of arbitrary real-world generalization.

All examples use the existing `state`, `question`, `kind`, `options`, `target`, and provenance schema. Only `state`, `question`, `kind` and `options` are model inputs. Rules and candidate facts are visible; computed eligibility, targets, provenance and counterfactual annotations are excluded from the input. Choice candidates are shuffled, use varying IDs and contain an explicit abstention option. The 25,600 Choice, 12,800 Noul and 12,800 Score rows retain their exact target-to-option alignment. Score options remain ordered from zero through four established requirements.

Missing facts have three-valued semantics: unknown evidence does not establish a requirement. A false antecedent makes a conditional true; an unknown antecedent with a true consequent also makes it true. Nested expressions count as one numbered requirement. Noul asks whether all four requirements are established; it does not assign fabricated probabilities to uncertain facts. Targets are exact one-hot supervision.

The language inventory is 46,400 English rows and 1,600 each with Chinese, Japanese or Korean questions paired with English rules and attribute names. These **mixed-language controls** have not received independent linguistic review and are not a native-language customer-service corpus. Noul has 9,871 negative and 2,929 positive examples; the data are not label-balanced. Score counts for levels 0–4 are 271, 1,312, 2,679, 4,934 and 3,604.

There are 80 generator source identifiers and nine external inspiration URLs. These must not be described as 80 independently collected datasets. The synthetic records are original CC0-1.0 material; links are retained solely for attribution of use-case inspiration.

The task scope remains finite controls: retrieval rows are constrained relevance/eligibility decisions, contracts are not CUAD annotations, game rows are not simulator trajectories, shell rows are generated attributes rather than private histories, and judge labels are not human preference annotations. The rules are deliberately explicit. Natural-document training and independently collected evaluations are complementary evidence. Generating this data does not establish an improvement on JevBench or any other benchmark.

Validation:

```bash
python -m unittest tests.test_community_diversity_v2 -v
python -m jev.data validate data/community-diversity-v2
```

Tests cover boundary and missing-evidence semantics, family/source separation, all task forms, target permutations, single-fact counterfactuals, target/policy corruption, input-file isolation and deterministic output hashes. The full build also recomputes every target and audits every counterfactual edge before writing the dataset.

An additional [independent audit](../reports/community-diversity-v2/independent-oracle-audit.json) parses the visible rule strings with a separate tokenizer, parser and three-valued interpreter. It imports neither the generator nor its rule AST. It verified all 51,200 targets and 19,200 single-fact counterfactual edges, including the four variants' expected 2/1/3/0 admissible-candidate counts. Its separate tests cover the complete three-valued Boolean truth tables, arithmetic, set membership, ranking ties, unknown evidence and deliberate target corruption.

```bash
python -m unittest tests.test_community_diversity_v2_audit -v
python -m scripts.audit_community_diversity_v2 \
  --data-dir data/community-diversity-v2 \
  --output runs/community-diversity-v2-recheck/audit.json
```
