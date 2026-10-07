# Shared prefixes: reuse context across multiple decisions

[简体中文](shared-prefix-cache_zh.md) · [Back to README](../README.md)

Read [From JevRequest to LLM inputs](request-to-model.md) first to understand why one request produces multiple candidate judgments and how their scores become final answers.

Here, LLM refers to the large language model used for candidate scoring, such as Qwen3. A single LLM2Jev request can ask several questions about the same material. Shared-prefix caching reuses the LLM's intermediate results for identical input prefixes, reducing repeated computation. Long inputs with multiple candidates can benefit even when no earlier request has populated the cache.

This guide covers the local Python `SGLangBackend` and the `/v1/systemone` endpoint served by `llm2jev-serve`. Both default to staged submission. `TransformersBackend` does not currently use this submission strategy.

## Why is the same context processed more than once?

Suppose a customer says, “My parcel arrived two weeks late, and my card was charged twice.” You want to select a department and rate the severity.

LLM2Jev turns each Choice option and each Score level into a separate yes/no judgment. Each judgment needs the customer message and its question. Conceptually, their inputs share this structure:

```text
Customer message
├── Which department?
│   ├── Does shipping apply?
│   ├── Does billing apply?
│   └── Do returns apply?
└── What severity?
    ├── Does the low level apply?
    ├── Does the medium level apply?
    └── Does the high level apply?
```

All candidates share the customer message. Candidates for the same question also share its instructions. Longer context and more candidates make repeated processing more expensive.

As the LLM processes an input, it produces intermediate attention results called a **KV cache**. A later input with the exact same beginning can reuse those results and continue from where it differs. Matching uses actual token prefixes after tokenization: similar meaning or matching text at a different position does not guarantee reuse. The diagram is conceptual; you do not need to mark shared boundaries yourself.

## How does staging help the first request?

Enabling a cache alone does not guarantee reuse among candidates submitted together. In our tests, submitting all candidates at once still repeated prefix computation because those candidates started before the shared cache was available.

Staged submission first scores a real candidate to establish a shared prefix, then submits candidates that can reuse it. Further branches may need additional rounds, while independent branches can run in the same round.

The diagram maps each candidate input to Jev's fields: `state`, its question's `instructions`, and one `criteria` candidate. `department` and `severity` are question IDs; `criteria.shipping` abbreviates `criteria["shipping"]` and includes the option name and definition. Solid blue blocks require new computation; dashed green blocks reuse KV from earlier stages. The right column shows the shared cache after each stage.

![Six criteria candidates scored in three stages, reusing state and question instructions through SGLang Radix Cache.](../assets/shared-prefix-stages.svg)

For the example above, the submission sequence is:

1. Score the shipping candidate to establish the message and department-question cache.
2. Score the remaining department candidates and the first severity candidate, establishing the severity-question cache.
3. Score the remaining severity candidates.

Each candidate is scored once. There is no extra warm-up question. Complete inputs retain their content, and results return in the original question and candidate order. Actual grouping follows token prefixes and is not limited to three rounds.

A **cold request** here has no relevant KV cache, but the model is already loaded and its computation kernels have been warmed up. A **warm request** can reuse existing prefixes. Staging establishes and reuses cache within a single cold request; you do not need to send the request twice. It does not accelerate model loading or initial kernel compilation.

See [Usage guide](usage.md) for examples and mode selection, and [Performance benchmarks](shared-prefix-benchmarks.md) for measurements and test conditions.

## Outputs and cache behavior

Both modes process inputs and read next-token yes/no scores without generating answer text. Choice, Score and Noul response structures remain the same. `usage.input_tokens` counts the logical total across complete candidate inputs, and `usage.output_tokens` is zero. Cache hits reduce computation, not that logical usage count.

With BF16, execution order and batch shape can change probabilities. Close candidates may change their final ranking. Compare the assembled, normalized answers and continuous Score values when evaluating the modes. Two candidates both leaning toward yes does not by itself make the final answer incorrect; shared-prefix reuse also does not guarantee better model judgment.

Staging requires SGLang's Radix Cache. Combining it with the Python option `engine_kwargs={"disable_radix_cache": True}` or the server flag `--disable-radix-cache` raises an error. SGLang manages cache allocation, reuse and eviction: prefixes may survive across requests within the same engine, but can also be evicted when capacity is needed. Cache reuse does not necessarily reduce displayed GPU memory usage because the engine may preallocate a KV pool.

Serialize calls to a Python backend instance. Concurrent performance of staged submission in the HTTP service has not yet been validated either.
