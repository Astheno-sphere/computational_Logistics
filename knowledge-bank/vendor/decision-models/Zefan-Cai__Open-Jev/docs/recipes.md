# Cookbook task adapters

`jev.recipes` implements 15 composable request forms. Generate inspectable JSON:

```sh
python -m jev.recipes --write-examples examples/recipes
```

All requests run through the same local `/v1/systemone` endpoint. These are
implemented task interfaces, **not 15 independently trained or validated model
capabilities**. The initial customer/Doom/Wiki pilot did not train these recipes.

| Form | Implemented behavior | Public inspiration |
|---|---|---|
| Classification | Choice over supplied labels | [Confidence classification](https://docs.typesafe.ai/cookbooks/classification_using_confidence) |
| Reranking | Independent ordinal relevance per candidate and rank postprocessor | [Reranking](https://docs.typesafe.ai/cookbooks/rerank_typesafe) |
| Semantic search | Line ID Choice plus answer-existence Noul, up to 255 lines | [Line search](https://docs.typesafe.ai/cookbooks/semantic_find) |
| RAG filtering | Relevance, contradiction, injection judgments per passage | [RAG passages](https://docs.typesafe.ai/cookbooks/classifying_rag_passages) |
| Citation checking | Supported / contradicted / insufficient against supplied source | [Citations](https://docs.typesafe.ai/cookbooks/citation_check) |
| Guardrails | User-defined hazard probabilities; caller chooses action thresholds | [Guardrails](https://docs.typesafe.ai/cookbooks/llm_guardrails) |
| Entity alignment | Different / review / same entity ordinal decision | [Entity alignment](https://docs.typesafe.ai/cookbooks/entity_alignment) |
| Span extraction | Regex candidates for email, phone, currency amount; exact-span or none | [Pre-parsed values](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook) |
| Dates | ISO dates and today/tomorrow/yesterday with mandatory reference date | [Date extraction](https://docs.typesafe.ai/cookbooks/date_extraction_cookbook) |
| Structure recovery | Paragraph/heading/list/code/quote classification and Markdown assembly | [Autoformat](https://docs.typesafe.ai/cookbooks/autoformat) |
| Function calling | Tool plus closed-set arguments; missing-argument review; returns a proposal | [Functions](https://docs.typesafe.ai/cookbooks/function_calling) |
| Skill selection | Skill Choice and whether a skill is needed | [Skill suggestion](https://docs.typesafe.ai/cookbooks/skill_suggestion) |
| Hierarchical classification | One branch decision; caller can repeat over its tree | [Hierarchy](https://docs.typesafe.ai/cookbooks/hierarchical_classification) |
| Extraction verification | Independent support probabilities for proposed fields | [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade) |
| Numeric features | User-defined Noul/Choice/Score feature questions | [Feature discovery](https://docs.typesafe.ai/cookbooks/autoresearch_feature_discovery) |

Parallel questions and speculative fan-out are supported across these forms.
`confidence` is distribution concentration; thresholds require task-specific
validation. There is no automatic external tool execution. The code does not
include a generative extraction fallback, 182-skill catalog, CatBoost feature
search loop, hierarchical beam search, or hard-wrapped line stitching. Date and
span candidate recall is intentionally limited and documented. Missing candidates
cannot be recovered by closed-set scoring. These distinctions matter when
comparing against an end-to-end public cookbook.

The implementations and small examples are original. Links attribute the task
ideas; the upstream datasets, benchmark claims, and model outputs are not copied
into training data. X claims of 5× or 193× speedups are not Open-Jev results.
