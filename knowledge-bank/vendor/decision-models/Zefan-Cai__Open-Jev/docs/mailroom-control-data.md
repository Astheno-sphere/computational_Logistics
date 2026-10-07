# Original multilingual mailroom controls

`mailroom-control-v1` is a separate original-data control set for the public [jev-mailroom example](https://github.com/selcukusta/jev-mailroom/tree/06d44889231afb209e29275f14a529ba52c9eb0d), pinned at `06d44889231afb209e29275f14a529ba52c9eb0d`. The source is MIT licensed. This implementation and its English, Chinese, and Turkish messages were written independently. No source emails, IMAP contents, attachments, or the author's 16 private examples were imported. Original generated email data is CC0-1.0; the implementation follows this repository's license.

The pinned source actually asks **11 questions: two Choice and nine Noul**. Some source comments still refer to fourteen questions and Score; those comments do not describe the implemented contract. Our request preserves the state shape (`email.subject`, `email.from`, `email.date`, `email.body`) and independently words the questions. It is not byte-identical reproduction of the original prompt. All eleven questions remain in each request.

The `kind` Choice distinguishes invoice, payment confirmation, periodic account statement, promotion, newsletter, and other. Four evidence Nouls separately ask about a currently owed amount, the sender issuing its own charges, billing identifiers, and promotion. The `category` Choice distinguishes education, electricity, telecom, banking, airline, and other; five more Nouls ask about these subjects regardless of whether payment is owed.

An invoice link without a repeated amount remains an invoice. A relay delivering another provider's bill remains an invoice but is not the provider issuing its own charges. Already-paid figures and advertised prices are not currently owed money. Promotions and newsletters can still concern a named service. For nonbill/nonreceipt mail, `category` has **no supervised label**, rather than acquiring the source application's `other` fallback. The request retains that question so interface testing still exercises all eleven heads.

The corpus includes provider/service counterfactuals: a student's operator bill versus educational services; a retailer's handset versus telephone service; electrical equipment versus supplied power; power bills paid through a bank versus the bank's own fees; and unknown technology suppliers selling air purifiers. Receipt controls are explicitly delivered by a relay, avoiding an ambiguous claim that sending a receipt is issuing new charges. Unknown-category controls name a known out-of-taxonomy service; genuinely unspecified service text fails the controlled audit instead of receiving invented gold.

Each family includes three languages and nine email actions, plus two English invoice taxonomy variants: reordered categories, and an added insurance category. Insurance changes from `other` to `insurance` only when the visible option exists. Existing category labels remain semantic labels; no confidence shift is assumed or supervised. Unchanged heads across taxonomy variants share their first supervised row instead of duplicating model inputs. Reordered Choice candidates remain an intentional order-control row; the general dataset validator also reports candidate-order-invariant unique inputs separately.

Families are assigned independently of requested corpus size. All translations, actions, services, and taxonomies for a family stay together. Index modulo ten of eight or nine reserves a family for OOD; other families use the repository's fixed hash assignment. Expanding ten families to four hundred preserves every existing request, row, and split. OOD moves the first two body paragraphs to the end; messages with only two paragraphs retain their order. OOD therefore means reserved entities plus some order changes, not a new grammar for every request. These are correlated finite-grammar controls, not unrestricted natural email or evidence of robust multilingual production triage.

`jev.mailroom_audit` does not import the generator. It reads the final visible body, sender, subject, and taxonomy, matches an explicit closed grammar, and derives labels from those facts. It checks file hashes, request/row alignment, family assignments, unique inputs, masks, and targets. Unknown or contradictory lines fail closed. Mutation tests reject jointly corrupted gold and targets; hidden metadata cannot override email evidence. This is independent implementation checking, not an independent human annotation study.

Generate and audit a new small corpus:

```bash
python -m jev.mailroom_data --output-dir data/mailroom-control-v1-probe --groups 10
python -m jev.mailroom_audit --data data/mailroom-control-v1-probe --output reports/mailroom-control-v1/probe-audit.json
python -m unittest tests.test_mailroom_data -v
```

Export all test/OOD requests for the existing real API runner:

```bash
python -m jev.mailroom_probe --data data/mailroom-control-v1-probe --output reports/mailroom-control-v1/probe-requests.json
python -m scripts.benchmark_jev_api_latency --requests reports/mailroom-control-v1/probe-requests.json --output runs/mailroom-control-v1-jev-probe --model jev-1.13.0 --warmup 0 --repetitions 1
python -m jev.mailroom_probe --data data/mailroom-control-v1-probe --samples runs/mailroom-control-v1-jev-probe/samples.jsonl --output reports/mailroom-control-v1/probe-results.json
```

The API runner requires `TYPESAFE_API_KEY` in the environment and preserves every actual response. Exporting requests and running the audit perform no model inference. The evaluator consumes one real saved response per holdout request, verifies identity and typed outputs, and reports valid-answer accuracy plus accuracy including request failures. Nonbill categories are excluded. The Noul decision threshold is 0.5; an exact tie is unresolved. This threshold reads a model prediction and does not generate semantic gold. One call per input is a semantic smoke test, not a reliable latency estimate.

The frozen provider bundle at `data/provider-mailroom-probe-v1` uses the shared provider-quality runner's existing rule instead: `argmax([1-p, p])`, choosing false on exact ties. Its 87 requests contain 957 runtime questions and 921 labelled decisions; 36 category questions remain in requests but have no gold. The common provider report and the standalone mailroom report therefore have explicitly different tie policies. The provider bundle copies the frozen request file byte-for-byte and binds every gold question to the request hash. It does not read provider answers when preparing gold.

The prepared full corpus has 400 families, 11,600 requests, and 114,800 distinct ordered model-input rows: 73,472 train, 4,018 calibration, 6,027 validation, 8,323 test, and 22,960 OOD. The generic validator reports 114,400 inputs after also disregarding candidate order. `reports/mailroom-control-v1/expansion-stability.json` verifies that all 290 small-corpus requests and all 2,870 small-corpus rows remain byte-identical in the same full-corpus files. The frozen 87-request probe remains a fixed subset; expanding the corpus does not expand that evaluation retrospectively.

The separate [`mailroom-control-v1` HF config](https://huggingface.co/datasets/ZefanCai/Open-Jev/tree/c67699e13d0ae25e35b77165a4b6b079bedc8aba/data/mailroom-control-v1)
is published with all five splits. Anonymous `datasets` loading and exact
Parquet/raw JSONL round-trip verification passed for all 114,800 rows. All 219
prior files other than the root dataset card remain byte-identical by their
content identifiers; previous config definitions, the default and frozen
training mixtures are unchanged. The [release evidence](../reports/mailroom-data-release-20260920/README.md)
records the pinned revision, upload hashes and verification results. This
publication does not imply training, live mailbox access or end-to-end customer
email automation.

The first real Jev 1.13.0 probe completed all 87 held-out requests with HTTP 200
and strict typed-output validation. It answered **908 of 921 supervised
decisions correctly**: English 347/351, Chinese 279/285, and Turkish 282/285.
Nine errors concerned whether the sender issued its own charges, two concerned
the bill category, one a billing identifier, and one the banking topic.
The raw requests and outputs are hash-bound in the
[provider evidence record](../reports/provider-comparison-20260920/quality-evidence-identity.json).
Both documented Noul tie policies give the same count on this run.
This is a small correlated original-control probe; it is not a production
multilingual accuracy estimate or a measurement of complete mailbox automation.

Pinned source file SHA-256:

- `mailroom/questions.py`: `d9621c8ccdc9c8bf7dd8132a501390b3d15729a4ef8b1a821ae24d4c14bc5d1d`
- `mailroom/triage.py`: `b28e64711d2ebc53244fd1d85989158934e1fe0e6b1710294e40a60a3e259cf9`
