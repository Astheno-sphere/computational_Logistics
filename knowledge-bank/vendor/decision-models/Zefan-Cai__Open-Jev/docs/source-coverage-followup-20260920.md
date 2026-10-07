# Public-source coverage follow-up

Audit: 2026-09-20 UTC. Local implementation reviewed at
`b5e3bb6e3f5a21597f63c1bd1af0746beccdab64`.

**Three concrete cookbook workflows merit dedicated training and end-to-end
checks: contextual citation checking, entity alignment with field judgments,
and candidate-span extraction with semantic attributes.** Their basic adapters
already exist; this audit adds detail about the missing workflow components and
training contracts. It does not supersede the browser, tactical-control, and
stateful-game priorities in [training-coverage-gaps.md](training-coverage-gaps.md).

This is a bounded follow-up to [public-capabilities.md](public-capabilities.md),
not an exhaustive X survey. Five official cookbook pages and one previously
listed public GitHub README were read directly. No search snippets were used as
evidence. No JF100 questions, states, or labels were inspected. No official
example records or model responses were transformed into training data.

## Source records

The official Markdown URLs returned HTTP 200. They are mutable pages: no
immutable source commit was verified. The SHA-256 values identify the exact
retrieved content, not a Git revision.

| Source | Exact URL | Retrieved-content SHA-256 |
| --- | --- | --- |
| Citation checking | <https://docs.typesafe.ai/cookbooks/citation_check.md> | `18f3f5c64f60807392b2d5e3f9a7b6d454e7a379c212025dcb1356b54aaa0635` |
| Entity alignment | <https://docs.typesafe.ai/cookbooks/entity_alignment.md> | `17f4d8fe49bb18fe179d6b0368198f1e35a58605b39e883cbf1c282b27835f7d` |
| Pre-parsed values | <https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md> | `5a2026433afc618ab1ed16994d8c07281399e527482006a92e7e343ddcd96a2d` |
| Structured-extraction cascade | <https://docs.typesafe.ai/cookbooks/sde_cascade.md> | `5d513d682f45ccaa85004d2e5437ae37b862b33e97e80013b458bc73ba6b5ddb` |
| Semantic line search | <https://docs.typesafe.ai/cookbooks/semantic_find.md> | `1fad271a5cf1be3671a153c1ea5e9777974a71e1187f6466d56617ac30a99cd8` |

The existing community trial
[iammrduncan/typesafe-ai-benchmark README](https://github.com/iammrduncan/typesafe-ai-benchmark/blob/cf348cd291bb538ad9fa902334649ef5dd937e92/README.md)
was checked at commit `cf348cd291bb538ad9fa902334649ef5dd937e92`.
Its retrieved README SHA-256 is
`307e389ac96a5fc5d60952f8e0c997d0cf9e0a36cedadb3f4e878f474a1c1df2`.
It lists tickets, routing, driving, guardrails, approvals, answer scoring, and
simulated home control. Its explicit statement, “It does not ask Qwen to emulate
Jev probabilities in this comparison,” confirms that its latency contract
differs from both our full-typed and probability-output generation comparisons.
Its reported measurements were not rerun; they do not supply training labels or
validate the three workflows below.

## 1. Check a citation against its original context

**Original evidence.** The official page says: “we first look for missing quotes
with an ordinary string match”. Its `locate()` normalizes whitespace and curly
quotes, finds a quoted span in numbered source sections, or uses the named
section when no quote is supplied. Surviving cases receive one Choice:
`supports`, `contradicts`, or `says_nothing`. Code then maps these to verdicts and
routes low-confidence results for human review; the example threshold is 0.8.

A quotation can occur verbatim while its surrounding section contradicts the
claim or says nothing about it. Quote presence and contextual support are
therefore separate decisions. The cookbook calls a failed normalized substring
match `fabricated`, but explicitly notes that truncated or lightly reworded
quotes also fail this matcher. That label does not establish deliberate
fabrication. The eight RFC 7519 cases and their displayed outcomes are the
author's demonstration, not our evaluation.

**Current coverage.** [The local recipe](../jev/recipes.py) has
`citation_check(claim, source, quote=None)` and one
supported/contradicted/insufficient Choice. It passes the optional quotation to
the model and partly combines quote accuracy with claim support in the rubric.
It has no source-section locator, deterministic quote-presence gate, or complete
review workflow. Release-v2 has no dedicated citation corpus. The 5,442 training
rows in `reasoning-control-v1` cover exact reasoning families; related evidence
integration does not establish this document workflow.

**2026-09-20 implementation follow-up.** The separate
[citation-control-v1 corpus](citation-control.md) now supplies 200 original
template-generated document groups, 4,000 contextual semantic records and 400
quote-not-found controls. It preserves the current recipe contract and whole
document grouping. This is data preparation only: it has not been trained or
run through a model, and the frozen release-v2/expansion training mixtures remain
unchanged. The original audit above describes coverage before this addition.

**Independent construction.** Generate original policy/manual sections from a
small explicit fact-and-rule model, with scoped exceptions, negation, amounts,
dates, and unrelated paragraphs. Render claim variants whose relation to that
model is provably entailed, contradicted, or undetermined. Construct exact
quotes, absent quotes, and section-only requests separately. Include lexical
overlap that is irrelevant to the claim and examples where the quote occurs but
its surrounding exception reverses the conclusion. Keep source content,
instructions, and labels in separate fields; derive labels before rendering.

The deterministic matcher should return `quote_not_found` without a model call
when appropriate. Train the semantic Choice only for cases with supplied
context. Do not invent a model confidence for a string-match result. Keep all
claims, sections, and counterfactuals derived from one source document in one
split, with separately generated writing templates for OOD evaluation.

**Acceptance evidence.** Report matcher accuracy and quote-normalization limits
separately from three-way semantic accuracy, macro F1, and Brier score. Select
review thresholds using a calibration split and report held-out accepted
accuracy versus coverage. Preserve failures from missing sections, absent
quotes, and unsupported claims instead of silently dropping them. This validates
the original synthetic document workflow, not arbitrary factual verification.

## 2. Align entities and explain field disagreements

**Original evidence.** The page specifies “one request, four questions”: a Score
with different/related/same product levels plus Nouls for same name, same
brewery, and same style. It applies this contract to 450 candidate beer-product
pairs from the Magellan benchmark. Numeric alcohol-content comparison is
explicitly left to code.

The routing code rounds the expected Score:
`OUTCOME[min(int(score_value + 0.5), len(LEVELS) - 1)]`. Although the prose says
there is no threshold to fit, this still creates fixed boundaries at 0.5 and
1.5. Rounding an expectation does not establish merge precision or calibration.
The page dates its cached Jev 1.12 results to 2026-08-11. Those results, including
the displayed merge/review/unlinked counts, remain author-reported.

**Current coverage.** `entity_alignment(left, right)` supplies the ordinal
different/review/same Score. It does not include the three field-agreement
Nouls, route records into a curator queue, or update a graph. Release-v2 has no
dedicated entity-pair training source. Generic Choice/Noul/Score training and
invoice fields are not a substitute for entity-resolution examples.

**2026-09-20 implementation follow-up.** The separate
[entity-alignment-control-v1 corpus and builder](entity-alignment-control.md)
now provide a Score plus name/manufacturer/capacity evidence Nouls, with 200
original catalog family groups and 2,800 pairs. This is a self-defined catalog
contract, not the official brewery/style dataset. No model has been trained or
run on these records; the frozen training mixtures and shared recipe default
are unchanged. The original audit above describes coverage before this addition.

**Independent construction.** Create original catalogs containing product
families, variants, canonical identifiers, manufacturer names, units, and
disclosed alias rules. Render paired records with punctuation/spelling aliases,
unit-equivalent quantities, nearby variants, conflicting identifiers, and
missing evidence. State the merge/review/no-link rubric in the input. Derive
labels from the information visible in both records and that rubric; hidden
entity IDs must not force contradictory labels for identical observations.

Add named field-agreement Nouls alongside the Score. For missing fields, define
an evidence-based criterion explicitly or omit the undefined supervised head;
do not label uncertainty with an arbitrary 0.5 probability. Keep numeric unit
conversion in code. Group all records and candidate pairs belonging to an
underlying product family into the same partition, including pairs that share
an entity. Hold out complete alias/template families for OOD checks.

**Acceptance evidence.** Measure three-way route accuracy, false-merge rate,
merge precision, curator-queue coverage, and each field's error/Brier score.
Evaluate the declared rounding policy as implemented. Any alternative gate
must be chosen using calibration data and reported as a different policy.
No real catalog or knowledge graph is mutated by these tests.

## 3. Select an exact value and its normalization attributes

**Original evidence.** “A regex finds the candidate values, TypeSafe picks the
one the question asks for, and code copies it verbatim.” The cookbook then
works through receipt-destination email selection, mobile-number selection plus
country Choice and E.164 formatting, and invoice-amount selection plus currency
Choice and credit/charge Noul. `phonenumbers` and `Decimal` perform the final
normalization. Every span Choice has a `none` option.

The page explicitly makes candidate recall a prerequisite. It also notes the
255-option Choice limit and the need to narrow the section first for larger
candidate sets. Its amount parser assumes US separators; European formatting
needs a declared convention or additional classification. These limitations
are part of the task contract.

**Current coverage.** `extract_candidates`, `value_extraction`, and
`selected_span` provide regex candidates for email/phone/amount, a span-or-none
Choice, and exact offsets/text. The current amount regex is narrow and does not
cover every sign, symbol placement, or locale. The recipe has no country,
currency, credit/charge, or locale heads, and no complete semantic-attribute to
normalization pipeline. Release-v2 has no dedicated document-span corpus. Its
5,370 invoice-processing training rows teach decisions over generated invoice
records, not extraction of arbitrary document values.

**2026-09-20 amount implementation follow-up.** The separate
[amount-extraction-control-v1 corpus and builders](amount-extraction-control.md)
now provide two stages: span-or-none plus target presence, followed by currency,
known direction and conditional credit/charge heads for an actual candidate.
The original corpus contains 200 document families and 3,200 documents. Its
candidate recall is 2,000/2,400 unique present targets; 400 misses are retained.
Code copies the selected span, parses Decimal exactly under an explicit US/EU
convention, and applies documented grammar/attribute checks before ready/review.
These are reference tasks and deterministic checks, not model performance.
Email/phone normalization remains uncovered by this addition. The frozen
training mixtures and shared recipe default are unchanged; this corpus has not
been used for training or model inference.

**2026-09-20 email implementation follow-up.** The separate
[email-selection-control-v1 corpus and builder](email-selection-control.md)
now provide current-role email span selection and a target-presence Noul, plus
verbatim copying with an explicit partial-span check. The 200 original contact
families contain 2,800 documents; exact candidate recall is 1,000/1,600 unique
current targets, with all 600 misses retained. Copying preserves local-part and
domain case and does not establish role correctness, mailbox validity or
deliverability. The shared regex and frozen training mixtures are unchanged.
This corpus has not been trained or evaluated with a model.

**2026-09-20 phone implementation follow-up.** The separate
[phone-extraction-control-v1 corpus and builders](phone-extraction-control.md)
now provide span/presence selection, an explicit field-region Choice for the
actual candidate, and guarded E.164 formatting. Its 200 original fictional
document families contain 4,000 documents; exact candidate recall is
2,600/3,200, with all 600 misses retained. The pinned `phonenumbers==9.0.14`
metadata checks distinguish complete-number possibility, validity and formatting;
routability remains unverified. The local-only-number rejection is covered by a
runtime regression test, not a new training variant.
The finite example pool repeats across splits: independent normalization finds
424 distinct E.164 values, of which 124 occur in multiple splits. This is a
document-family split, not a number-identity holdout or evidence of unseen-number
generalization. Library metadata reuse is explicitly disclosed in the audit.
These are controlled reference tasks and software checks; no training, model
evaluation or new checkpoint capability is established.

**Independent construction.** Generate original email threads, contact cards,
and invoices from typed records. Include sender/recipient/billing-role
distractors, updated contact instructions, multiple phone roles, subtotal/tax/
due/credit fields, explicit locale facts, and missing requested values. Record
gold character offsets before presenting the text. Candidate construction must
not inspect the gold answer; independently measure whether it found that span.
Keep the span plus `none` candidate count within the API limit or explicitly
use a section-selection stage.

Supervise the span ID and the attributes that are defined for that selected
value. Use an explicit unknown/review path when the country or currency is not
determined by the input. Code copies the chosen span and parses it using the
declared locale and units. Numerical values or phone digits are never regenerated
by the model. Group each document and its role/value counterfactuals together;
reserve document layouts, locale conventions, and role paraphrases for OOD
tests.

**Acceptance evidence.** Report candidate recall, conditional span-selection
accuracy given a present gold candidate, end-to-end exact offset/value accuracy,
attribute accuracy, and `none` precision/recall. Test the normalizer separately
with exact decimal and phone-number expectations. Count absent-candidate cases
as extraction failures where the requested value exists; schema validity alone
must not hide them.

## Evidence limits and release accounting

The reviewed [release-v2 manifest](../reports/data-manifests/release-v2.json)
contains 80,816 training rows and 115,821 rows across all splits. Its SHA-256 is
`56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.
The source inventory and counts in [training-coverage-gaps.md](training-coverage-gaps.md)
show no dedicated sources for these three workflows. Related rows may transfer;
this audit does not measure that transfer. The separate 21,980-row browser
snapshot corpus, including 13,814 train rows, does not change this conclusion
or the frozen release-v2 mixture.

The other two official pages add useful boundaries without requiring more task
recommendations. `semantic_find` uses a line Choice and answer-existence Noul,
already mirrored by `semantic_search`; its example thresholds are not validated
for our documents. The SDE-cascade page explicitly says it **hard-codes** one
canonical mini-model fabrication for a reproducible walkthrough. Its field
verifier then drives an `any_flag` gate; the displayed holistic judgment is not
used by that gate. The separate 100-prompt cost/quality plot is labeled internal
TypeSafe results. Neither a hand-fixed input nor that plot proves an Open-Jev
cascade result or empirical calibration.

At the time of the initial source audit, the generation and evaluation designs
above were proposed work: that audit created no supervised records, changed no
adapter and launched no experiment. The dated implementation additions now link
to separately prepared, versioned control corpora and data checks. They have not
been used for training or model inference and do not alter the frozen training
mixtures. Their availability establishes no new checkpoint capability; model
release claims still require a saved held-out evaluation of the actual model.
