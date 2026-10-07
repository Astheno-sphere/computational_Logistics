# Additional Jev use cases and data requirements

Research snapshot: September 21, 2026 UTC. This bounded pass verifies **12 task
families or evaluation gaps against 20 primary code/cookbook sources**, plus
**17 exact public X post readbacks** across two passes (18 URLs attempted; one
failed). It adds no training rows or measured model
results. Existing training, data converters and website work are unchanged.

The [structured inventory](../reports/community-research-20260921-broadening/usecase-inventory.json)
records source revisions, reviewed-file hashes, task contracts, candidate/context
sizes, labels, licenses, split units and evaluation requirements. GitHub revisions
are pinned; official cookbook pages are identified by fetch time and content hash.
All performance numbers below are **author/vendor reports**, not our measurements.

## What this adds

| Family | Verified task and scale | Useful data or evaluation increment |
| --- | --- | --- |
| **F01 — Semantic code search** | [every][every] evaluates a natural-language predicate on each function; about 110 questions/request, four requests in flight. It can add caller/callee context. | Real licensed functions with reviewed behavioral predicates and hard lexical negatives; repository-level splits. The bundled 20-function self-test is too small to establish general accuracy. |
| **F02 — Code and supply-chain review** | [is-malicious][malicious] uses category checks and dynamic file/line selection. [code-audit-jev][audit] adds PR before/after analysis and a 22-rule bank. Its [author's X post][audit-x] links the implementation. | Paired vulnerable/fixed revisions with tests and cross-file evidence. Include safe framework escaping, inherited authorization and operator scripts. Keep published planted-defect probes held out. |
| **F03 — Approval and adversarial framing** | [jev-engineering][injection] reports 300 calls: 60 commands × five framing conditions. [approval-judge-bridge][approval] has a 17-case replay battery and three-way approve/deny/escalate. | Independent policy/command examples, authorization claims embedded in untrusted text, benign near-neighbors and abstention. Evaluate false blocks as well as attack success. |
| **F04 — Real review and commerce triage** | [Column Race][reviews] processes 1,000 real app reviews across 17 apps: sentiment, topic, bug and churn; 20 rows/80 questions per request. [Chinese commerce triage][commerce] adds reply/no-reply, technical versus presales intent and contact-risk checks. | Rights-cleared natural feedback with independently checked topic/bug/churn labels. Split by app/shop and duplicate review groups; include Chinese technical language and multi-intent comments. **The referenced app-review data license is unknown.** |
| **F05 — Dynamic document tags and taxonomies** | [Wagtail][wagtail] asks one Noul per existing tag, in batches of 40, over up to 12,000 body characters. [Janus][janus] uses 145 WoS metadata categories. [Official hierarchy search][hierarchy] explores CPC, Shopify and MeSH trees. | Real document/tag assignments, rare labels, ambiguous siblings and no-fit cases; evaluate leaf/parent accuracy and multilabel F1. Taxonomy traversal is distinct from one flat Choice. |
| **F06 — Large skill catalogs and follow-ups** | [jev-skill-router][router] ranks 50–59 actual skills; chunks at 240 options, then checks the top three. The [official cookbook][skill] uses 182 skills and a host exposing 60-character descriptions. | Natural conversational follow-ups, actual preceding context, near-duplicate skill descriptions and no-action requests. Measure downstream task completion and unnecessary skill loads, not just ranking. |
| **F07 — Database semantics** | [dbt-assay][dbt] evaluates column roles, grain, units, predicate intent and code/document alignment. It publishes a ledger of checked, rewritten and unverified questions. | Original/permissive SQL plus executable invariants and reviewed semantics. Separate missing evidence from contradiction and semantic units from numeric arithmetic. This complements the separately owned SQL converter work. |
| **F08 — SQL relation enrichment** | [duckdb-jev][duckdb] supports mixed typed questions, streaming, batching, duplicate reuse and caches. Its 1,000-row run uses 10 requests at batch 100/concurrency 10. | A batching protocol gap: test different real documents, row identity, neighboring contradictory evidence and option/order effects. This infrastructure case should not inflate semantic domain counts. |
| **F09 — Closed-loop traffic policy** | [Jev Traffic Sim][traffic] exposes a bounded city frame: at most 48 corridors, 64 regions and 24 hotspots. Up to 16 default questions select pressure, switching hints and regional weights. | New maps/demand seeds and complete trajectories; assess trip completion, delay, starvation and stale-observation effects. Deterministic code retains control over legal signal phases. |
| **F10 — Typed tool arguments in Chinese** | [The function-calling example][tools] uses four tools plus `none`, four services, 12 Choice questions and five Noul questions. Optional arguments are applied only when explicitly stated. | Natural requests grounded in real schemas; missing targets, omitted defaults, negation and argument compatibility. Command-string selection is not unrestricted tool generation or a complete execution trajectory. |
| **F11 — Entity alignment** | [The official record-linkage cookbook][entity] evaluates 450 preselected Magellan Beer pairs. A three-level Score distinguishes different, review and same; three Nouls compare semantic fields. | Independent identity-linked records, variants and aliases with reviewed ambiguous cases. Split on entity connected components. Keep the public benchmark pairs outside training. |
| **F12 — Document structure and extraction** | [Span selection][spans] chooses verbatim candidates plus `none`; [date extraction][dates] reads seven typed parts before calendar resolution; [structure recovery][structure] stitches lines, then classifies blocks. | Derive original structure labels from rights-cleared Markdown/HTML before stripping markup. Add real document role/offset labels, candidate-recall tests, impossible dates and ambiguous list/paragraph boundaries. |

These are task families and protocol gaps, not 12 newly trained domains. Several
extend existing support, routing, security or document processing capabilities.

## Findings that should change the data design

**Natural text and usable labels are different requirements.** Column Race's
[public post][reviews-x] links a useful real-text comparison, but its topic agreement
of 84.4% and bug agreement of 92.6% compare two models. Neither measures human-labeled
accuracy. Sentiment–star correlations of 0.803 for Jev and 0.822 for Gemini are weak
proxy metrics. The [upstream Hugging Face metadata check](../reports/community-research-20260921-broadening/app-reviews-upstream-metadata.json)
lists `license: unknown` for `sealuzh/app_reviews`; the demo's MIT license does not
license its source reviews. This source remains research-only until rights are clear.

**High confidence often hides missing context.** The code-audit author reports a
reasoning-agent follow-up on 38 candidates: two confirmed, two accepted risks,
25 false positives and nine operator scripts. This is model adjudication on one
repository, not independent human ground truth. In dbt-assay, two inspected
code-contradiction findings were false despite 0.95 confidence; arithmetic unit
comparisons also failed until the model named the unit and code compared magnitudes.
Training should include cross-file controls and an explicit insufficient-evidence
outcome, with deterministic checks where they apply.

**Preserve difficult benign examples.** The injection report's table has zero
dangerous allows under blunt injection but benign denials rising from 1/30 to 8/30.
Claimed owner approval allows 3/30 dangerous commands. A confidence floor of 0.8
catches its five observed successful attacks while escalating 35/60 clean commands.
This calls for a separate calibration split and a risk–coverage analysis, rather
than training only on easy dangerous/benign examples. The source narrative and table
also disagree on whether one blunt dangerous case was asked or denied; retain the
table's counts as author-reported evidence.

**Catalog and conversation context matter.** The community skill router reports
6/6 sensible scripted single-intent requests on version 0.2.0, but 3/6 sensible real
Japanese follow-ups on 0.1.0. Versions differ, so these are not comparable rates.
The client sends an empty `recent_context` field. A stronger data source is a
request plus its actual preceding dialogue, with whole-conversation splits.
The hook also leaves the host's skill roster in context: it has not demonstrated
the roster-token saving implied by some routing demonstrations.

**Taxonomy and pipeline metrics need precise names.** Janus reports 134 numeric,
133 hierarchical and 145 metadata label systems inside the same WoS archive.
Its 145-class task cannot be scored against the usual 134-class literature as if
the labels matched. Its committed Banking77 sample comes from the official test
split. Both committed holdouts must stay out of training. Similarly, traffic
snapshot accuracy cannot replace a completed trip, and zero-request result-cache
timing cannot be presented as neural inference latency.

## Practical next priorities

1. **Approval:** independently authored policies and natural command contexts,
   paired safe/unsafe counterfactuals, source-of-authorization distinctions and
   explicit escalation. Group all related commands and framing variants before
   splitting; reserve published attack batteries for evaluation.
2. **CMS and document labels:** use licensed documents with actual metadata or
   reviewed labels; support multiple tags and no-fit outcomes. Add taxonomy
   changes, sibling ambiguity and long text. Keep candidate catalog construction
   independent of the answer.
3. **Feedback:** source rights-cleared review text first, then independently label
   bug, topic, churn and reply necessity. Preserve star ratings only as a separate
   weak proxy. Do not ingest `sealuzh/app_reviews` on the strength of a MIT client.
4. **SQL, routing and structure:** extend the existing independently owned
   converters with natural text and real artifacts; preserve original provenance,
   executable checks and document/project/conversation splits. Do not create new
   training rows by paraphrasing external evaluation questions or answers.

For every family, retain source revision, data license, label origin and split
group. Measure candidate count, context length, request count, retries, P50/P95,
concurrency, hardware/network boundary and total cascade cost at a declared quality
target. A fast selected demo is not a full benchmark result.

## Search limits and secondary leads

This pass used bounded public GitHub repository search, selected pinned source
files, official rendered cookbook pages and exact public FxTwitter readbacks.
It did not perform authenticated X search or Xiaohongshu search, obtain private
timelines, download demo media, or execute third-party code. One robotics archive
exceeded the 12 MB fetch bound and was not inspected. The curator index was used
for discovery, not as verification of an author's result.

The inventory separately marks URL-abuse screening, sexual-content moderation,
Japanese preschool verbal-cue reflection and selective test execution as leads
with missing labels, rights, schemas or demonstrated integration. It does not
infer vision support from a moderation anecdote. `skillranker` has an
OpenAI/Anthropic license rider, so it is not an ordinary MIT reuse source. Names
such as `yajev`, Codiv `openjev-0.1` and other clones do not identify our checkpoints.

Evidence files: [source revisions and hashes](../reports/community-research-20260921-broadening/source-fetch-inventory.json),
[public X readbacks](../reports/community-research-20260921-broadening/x-public-readbacks.json),
[official cookbook readbacks](../reports/community-research-20260921-broadening/official-cookbook-readbacks.json).

### Fresh exact-post follow-up

The second pass followed eight additional exact public post URLs from pinned
repository/curator links. [Seven returned public text; one failed](../reports/community-research-20260921-broadening/x-followup-readbacks.json).
This was another bounded source pass, not authenticated X search. It found useful
failure conditions but no newly verified, rights-cleared approval/CMS/review gold corpus:

- [PatronusBen](https://x.com/PatronusBen/status/2101682107860885627) explicitly
  compares security validation with two hard-benign benchmarks. The readback
  supplies no datasets, labels, counts or matched protocol; it motivates hard
  benign controls without supporting a numerical comparison.
- [identityTorn](https://x.com/identityTorn/status/2100475121324728615) reports Jev
  within about five recall points of an internal finetune at matched precision.
  The benchmark/schema are not public. This reinforces evaluating recall at a
  fixed precision rather than a single untuned threshold.
- [ajmeese7](https://x.com/ajmeese7/status/2101786516758667265) describes selecting
  valuable files from 6 TB of old drives for $6. No repository URL or file-level
  labels appear in the fetched post. The 6 TB describes the collection, not a
  verified model-input volume or measured scan throughput.
- [patrickdevivo](https://x.com/patrickdevivo/status/2101693266135539782) proposes
  replacing repository/website embedding-centroid categories with Jev. The
  wording is a proposal, not an implemented or measured multi-label result.
- [iamMrDuncan](https://x.com/iamMrDuncan/status/2100467548298899918) links a
  Cerebras/Qwen 3.8 27B comparison repository. Its post-level claims remain author
  reports; this pass did not run or adopt that benchmark's labels.
- [BogardKc](https://x.com/BogardKc/status/2101479145968636276) describes a partial
  AI-gateway safety demo; [serpinxbt](https://x.com/serpinxbt/status/2101539616188776885)
  describes public-topic stance/sentiment analysis without human gold. Neither
  licenses private operational data for training.

The failed URL was
[`eltokh7/2101793224062881918`](https://x.com/eltokh7/status/2101793224062881918).
No result or capability was inferred from that failed readback. Authenticated X
and Xiaohongshu access remain untested in this pass.

[every]: https://github.com/sufianetaouil/every/tree/aaa72d582a831420dfd23a788e3bc948c798c248
[malicious]: https://github.com/luantak/is-malicious/tree/b6052465eb47cf85f347596385954aa06532718a
[audit]: https://github.com/SecurityMindedSolutions/ai-skills/tree/9d0e6e2495daeb56391c4cad0aa558d05d0d84da/skills/jev/code-audit-jev
[audit-x]: https://x.com/TechNerdings/status/2101737805932044637
[injection]: https://github.com/eugeniughelbur/jev-engineering/tree/3161dbfb44f21bafa2ec7940ec18cfb090c7b43d
[approval]: https://github.com/oppih/approval-judge-bridge/tree/d21037bdacecfcec445d79e60970561e5dfe895b
[reviews]: https://github.com/goodrahstar/jev-column-race/tree/d9ee360ccd84462f4eab9493a7c2c617d0dab9df
[reviews-x]: https://x.com/rahulbuildsmore/status/2100581721515188451
[commerce]: https://github.com/yuyang2230/jev-agent-skill/tree/00a25ddb0e5f8e35246ec0f218dba0191f20d465
[wagtail]: https://github.com/rinti/wagtail-jev/tree/40d4f23680b857fac8c3986979a06efd2205ae7e
[janus]: https://github.com/FirasSX914/Janus/tree/9cb66c488cf884e5997356a0de45f75aa3148774
[hierarchy]: https://docs.typesafe.ai/cookbooks/hierarchical_classification.md
[router]: https://github.com/shimo4228/jev-skill-router/tree/cc1057725f037a7b407ed52934e79c7151a4e144
[skill]: https://docs.typesafe.ai/cookbooks/skill_suggestion.md
[dbt]: https://github.com/ryan-sunny/dbt-assay/tree/ebf8812c9aeb19747f7168a0e08d3d224e170b12
[duckdb]: https://github.com/prasanthj/duckdb-jev/tree/928da7173d53c34cb40d36b2ef1dc66174c9e91c
[traffic]: https://github.com/skcache/jevtrafficsim/tree/6d409df5a9b617097b7e8f708819afa62ec05e03
[tools]: https://github.com/ItBayMax/typesafe-ai-jev-example/tree/009204a7444c897416046cd986d650b09bb56740
[entity]: https://docs.typesafe.ai/cookbooks/entity_alignment.md
[spans]: https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook.md
[dates]: https://docs.typesafe.ai/cookbooks/date_extraction_cookbook.md
[structure]: https://docs.typesafe.ai/cookbooks/autoformat.md
