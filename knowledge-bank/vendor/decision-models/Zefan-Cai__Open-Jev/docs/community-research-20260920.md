# Community use-case research, September 20, 2026

This bounded public-source review identifies three dedicated training gaps:
**tool-history retention, transcript segment classification, and semantic API
failure detection**. Exact implementation contracts are pinned below. The
[tool-history retention](context-retention-data.md),
[transcript segments](sponsor-segment-data.md), and
[silent failure](silent-failure-data.md) follow-ups now contain **30,234**
generated and independently audited rows, published as three additional HF
configs. These are original controlled tasks, not additional trained
capabilities or recovered Jev training data.

The existing [capability inventory](public-capabilities.md),
[training gaps](training-coverage-gaps.md), and
[cookbook follow-up](source-coverage-followup-20260920.md) were checked first.
Customer/workflow decisions, games, browser/drone snapshots, citation checking,
entity alignment and amount/email/phone extraction were not counted again.
The three families had no dedicated corpus in those earlier inventories.

## What was accessible

Public GitHub source and known X post URLs through the public FxTwitter mirror
were readable. A fresh, unauthenticated browser—not the user's Chrome profile—
was used only to verify public search access:

| Entry point | Actual observation | Coverage implication |
| --- | --- | --- |
| X search, `Jev TypeSafe` | Redirected to login | No public search timeline or complete reply tree was obtained |
| Xiaohongshu search, `Jev` | Security restriction `300012`, “IP at risk” | No note or comment was verified; no Xiaohongshu use-case claim is made |
| Google HTTP search | Redirect/JavaScript shell | No usable result evidence |
| DuckDuckGo HTML search | Human challenge, HTTP 202 | Stopped at the challenge |
| Bing queries | Returned mostly unrelated Jev-name matches despite qualifiers | Discovery only; irrelevant results were excluded |
| Three awesome-jev indexes | Readable, with repository links | Leads were independently checked against pinned implementation files |

No login, challenge bypass, account registration, post, purchase, private
conversation, or third-party media download was performed. This is not a search
of all X or Xiaohongshu content. See [access evidence](../reports/community-research-20260920/social-search-access.json)
and the [discovery record](../reports/community-research-20260920/discovery.json).

A later authenticated public-search pass in the user's authorized Chrome
session succeeded. This changes the X access boundary; the earlier anonymous
login redirect does not mean all X research was blocked. Two queries and one
scroll added six deduplicated leads in the
[follow-up record](../reports/community-research-20260920/authenticated-x-followup.json):
multilingual mail triage, live transcript-based agent assistance, FizzBuzz,
emoji-to-film associations, repository-metadata classification, and confidence
escalation to an LLM. This remains a bounded search. No private conversations
were read and no messages were posted. Xiaohongshu remains unverified.

The mail-triage code was pinned to
[`selcukusta/jev-mailroom@06d4488`](https://github.com/selcukusta/jev-mailroom/tree/06d44889231afb209e29275f14a529ba52c9eb0d).
It distinguishes invoice/receipt/promotion from provider category, combines
independent category Nouls in code, and discusses confidence sensitivity when
the candidate taxonomy changes. Its actual mailbox examples are not imported.
The FizzBuzz report prompted an original 1–100 arithmetic probe with explicit
questions and exact modular labels; this does not reproduce the author's
undisclosed prompt or claimed 10,000-run error rate. Emoji interpretations and
unspecified repository fields need a clearer contract before becoming gold
labels. Live agent-assist timing must include the external transcription stage
when making end-to-end claims.

## Direct X observations

Dates below are publication dates returned with the public post, not retrieval
dates. Original X URLs remain the citations. Posts describe their authors'
experiences; their speed and quality claims were not rerun here.

| Author / date UTC | Original post and short excerpt | Task and coverage consequence |
| --- | --- | --- |
| Chetaslua, 2026-09-17 06:35 | [Post](https://x.com/chetaslua/status/2100473581251748216): “every sentence, both candidates, 5 yes/no questions each” | Sentence-level rubric judgments with speaker history and the preceding question. The author explicitly says it is not a fact-check. This is a new inspectable media-analysis lead; it does not supply true/false political labels. |
| Steve Krouse, 2026-09-16 18:15 | [Post](https://x.com/stevekrouse/status/2100287368221659289): “typesafe's jev is fun! live demo you can play with” | A live typing interface; no dataset, accuracy claim or additional task contract can be recovered from this post alone. |
| Shannon / iamMrDuncan, 2026-09-17 06:11 | [Post](https://x.com/iamMrDuncan/status/2100467548298899918): “TypeSafe was way cheaper, and did beat Qwen on performance.” | A previously inventoried Qwen/Cerebras comparator, not a new domain. Its compact-output comparison differs from emitting full probability vectors. |

The [post records](../reports/community-research-20260920/followup-discovery.json)
preserve URL, author, timestamp, retrieval status and response hash. Public
profile biographies and media metadata are omitted. The Chetaslua project was
also checked at `cbf8e117b5b8835e3294c3a8ee652c7dfa737a9a`: its
[`score.py`](https://github.com/ChetasLua/jevmeter/blob/cbf8e117b5b8835e3294c3a8ee652c7dfa737a9a/jevmeter/score.py)
builds one state per sentence and one Noul per rubric. This related source
supports transcript analysis as an application family; it is not the source of
the seven-category sponsor contract below. No direct X announcement was
verified for the three pinned repositories below, so their contracts are
attributed to repository source rather than invented social posts.

## Three concrete additions

### 1. Retain the right tool history

Source: [`tamaratran/fast-jev-compaction`](https://github.com/tamaratran/fast-jev-compaction),
commit `e3f262a7f4d42bd8dd32ced30d26176f7cb545b0`, committed
2026-09-17 22:29:18 UTC. GitHub reports MIT.

The actual state is `{context, goal, history}`. History entries carry
`i`, `role`, `text`, and optional `tool_calls` with `{id, tool, input, result}`.
`result` is an outcome/length note; full outputs are omitted. For every eligible
completed call, [`questionsFor`](https://github.com/tamaratran/fast-jev-compaction/blob/e3f262a7f4d42bd8dd32ced30d26176f7cb545b0/src/compact.ts#L55)
asks two Nouls: whether the call/input still matters, and whether its complete
output must stay verbatim because re-running would not supply what is needed.
Call IDs and the number of calls vary with the input history.

The first and recent messages are pinned by software; unmatched calls are not
candidates. Code keeps a pair if the output is needed, keeps the call but
truncates the result if only the call matters, and otherwise drops the pair.
The source's default threshold is 0.5, not an independently fitted calibration
result. Its demo is described as scripted/dramatized; it is not outcome evidence
for our model.

**Original construction:** generate coding-task histories from explicit task,
artifact and evidence dependency graphs. Include superseded objectives,
persisted results, overwritten versions, needed historical observations, audit
records, and irrelevant calls. Render all facts deciding retention in the
visible goal/history; hidden output contents must not change identical visible
inputs' labels. Use hard targets from a declared local retention policy, not
invented soft probabilities. This extends agent-trace observability with a
different question: what exact evidence can be removed without losing the
stated task dependencies?

Group the whole task graph and all goal revisions, counterfactuals and
paraphrases into one split. Reserve different goal/tool/graph templates for OOD.
A separate dependency walker should check every label; a synthetic transcript
executor should verify preservation of needed evidence, pinned messages and
call/result pairing. Report false deletion of needed outputs separately from
byte reduction. These controls would validate the declared synthetic policy,
not arbitrary real-session compaction.

### 2. Classify transcript segments before skipping

Source: [`valentynkit/jev-skip`](https://github.com/valentynkit/jev-skip), commit
`6837e3e0f1a48cbfc48c85415d99bcfe3eaf0628`, committed
2026-09-19 09:38:56 UTC. GitHub reports MIT.

The [implementation](https://github.com/valentynkit/jev-skip/blob/6837e3e0f1a48cbfc48c85415d99bcfe3eaf0628/lib/questions.ts#L57)
uses **one seven-way Choice per segment**, not one Noul. The state contains
`video_title`, `channel`, an untrusted-transcript note, and
`segments[{id,start,text,has_promo_markers}]`. Each question explicitly names
its target segment. The supplied categories are `sponsor`, `self_promo`,
`intro`, `outro`, `recap`, `content`, and `other`.

A paid third-party read is a sponsor; the creator's own offerings and
subscribe requests are self-promotion; an unpaid product review may be normal
content. Insufficient evidence belongs in `other`. Neighboring segments
provide context in the same request. Timestamp boundaries and skip execution
belong to code. The author's SponsorBlock recall/cost figures were not rerun,
and crowd disagreement about self-promotion is an explicit source limitation.

**Original construction:** generate tutorial, review and podcast timelines
with original fictional brands/channels and disclosed promotional relationships.
Include negated sponsorship, editorial discussion quoting an ad, creator-owned
products, ambiguous fragments, contextual references and transcript injection
attempts. Do not import YouTube transcripts or SponsorBlock labels. Derive the
category from visible evidence under the seven-way rubric; hidden payment
status must not produce labels unsupported by the transcript.

Group whole episodes, adjacent segments, counterfactuals and category-order
permutations together. OOD should use separate topics and discourse templates.
Independently check labels from the editorial timeline, then report macro F1,
sponsor precision/recall, editorial false-skip rate and duration-weighted
interval scores. Fit any skip threshold on calibration only. Original-policy
data does not establish reliable skipping on arbitrary real videos.

### 3. Detect an error hidden inside an HTTP-200 response

Source: [`Vicente-MD/jev-resilience`](https://github.com/Vicente-MD/jev-resilience),
commit `c490e0dc7830758f84bd9d5acb806655e327113e`, committed
2026-09-17 23:52:03 UTC. The README labels the project MIT, but the repository
API returned no detected license. No implementation code is proposed for reuse.

The [client](https://github.com/Vicente-MD/jev-resilience/blob/c490e0dc7830758f84bd9d5acb806655e327113e/src/main/java/ai/jev/resilience/client/JevEvaluationService.java#L50)
sends the **stringified body as state** and one configurable Noul question,
`is_silent_failure`. Its default asks whether the payload represents failure,
maintenance, or an error disguised as success. HTTP status and the circuit
breaker stay in application code. The implementation converts Jev request or
parsing failures into 0.0; that fail-open fallback is not a semantic negative
label and must not contaminate training or reported classifier accuracy.

**Original construction:** create JSON, HTML and plain-text service bodies
under explicit operation contracts. Cover actual failure, maintenance,
permission denial, incomplete operations, empty but valid success, successful
recovery, and harmless historical/quoted error logs. Optimistic outer fields
may conflict with decisive body evidence. Do not label from a hidden server
state: the evidence must be visible in the supplied body.

Group complete operation/provider-contract families and their body variants
together. Hold out schemas, wording and formats for OOD. Check targets with an
independent finite-state contract evaluator and counterfactual current-error /
already-recovered pairs. Report false semantic trips on valid responses,
failure recall by subtype and Brier score, with judge transport/parse failures
kept separate. This fills a different gap from security alert disposition.

## Handoff and provenance

The [machine-readable proposals](../reports/community-research-20260920/domain-proposals.json)
specify input fields, typed outputs, generator constraints, grouping, OOD and
independent checks. Each completed corpus contains 400 source groups. Together
they add 18,915 train, 1,476 calibration, 1,458 validation, 2,145 test and 6,240
OOD rows. All 30,234 passed independent visible-input label and split audits.
The three data cards record exact counts and hashes. The published Open-Jev
models have not been retrained on them; subsequent hosted-provider coverage
checks are documented separately in the [comparison report](provider-comparison.md).

The [repository pins](../reports/community-research-20260920/repository-pins.json)
and [source contracts](../reports/community-research-20260920/source-contracts.json)
include permanent file URLs, line references and content hashes. Social content
and source examples are research evidence only; they are not training rows.
JF100 questions/answers were not read or copied during this review. Existing
frozen corpora and active training checkouts remain unchanged.
