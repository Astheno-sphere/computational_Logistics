# Probability-mapping latency: one small drone request

All three base models returned **3/3 valid decision outputs and 3/3 valid
generative outputs** on the same synthetic three-question drone request.
Independent revalidation found no evidence inconsistency.

| Base model | Decision median | Generation median | Generation / decision | Valid decision / generation | Generated tokens |
| --- | ---: | ---: | ---: | --- | ---: |
| [Qwen3.5-2B](2b.json) | 32.465 ms | 1,776.111 ms | 54.71× | 3/3 · 3/3 | 88 |
| [Qwen3.5-9B](9b.json) | 50.871 ms | 2,807.888 ms | 55.20× | 3/3 · 3/3 | 92 |
| [Qwen3.8-27B](27b.json) | 121.096 ms | 7,848.462 ms | 64.81× | 3/3 · 3/3 | 132 |

These are descriptive latency ratios for this workload, not general speedup,
accuracy, calibration, or Jev-parity results. Each model repeated one greedy
output three times; those repeats are timing samples, not three distinct tasks.
The 27B output used more formatting tokens. No output reached the 2,048-token
limit.

## Workload and execution

- One Choice with three maneuvers, one three-level Score, and one Noul:
  **three questions, seven decision candidate sequences, eight generated
  probability entries**. This is the committed examples/community/drone.json.
- Original pinned Qwen weights, no trained checkpoint or LoRA adapter:
  lora_rank=0, decision temperature 1. The decision readout is initialized
  from the original Yes-minus-No embedding difference. It uses the text
  backbone; generation uses the original autoregressive model.
- N1-1 (kwade5342000001), physical GPU 3, NVIDIA H100 80GB HBM3;
  UUID GPU-9ab08bcc-ce17-0461-aaf2-5d57ddcb4775.
  Models and paths ran serially, decision before generation, with one excluded
  warmup for each path and three measured repeats.
- BF16 backbone, float32 decision readout, SDPA, greedy generation, thinking
  disabled, candidate batch size 32, cached files only.
- Recorded input tokens are 971 across the decision sequences versus 497 for
  the generation prompt. The original state/questions are identical; prompts
  and execution mechanisms differ. Timings include local input/output
  processing and validation, but exclude model loading and warmup.

The run used code commit f703b86025eb945d4313b23653188799634e54fc.
Immutable model revisions, runtime versions, command lines, per-repeat times,
memory counters, exact requests and token IDs are retained in the JSON files.
All three request file hashes are
bd9faa9985df3c158f8b273bbb1ac3f67e184ff0589d8da09896db4a934d058e;
their payload hash is
9c73ee46db3a83d599be64a6f07609914e35302f9c10eda07a4ade7f79e4a11d.

## Difference from full-typed generation

This run explicitly selected **--output-contract probabilities**. Generation
emits only the complete question/candidate probability mappings. Exact
coverage, finite [0,1] values and a normalized distribution within 1e-6
are required. The shared format_response then computes the winning Choice,
Noul, Score expectation, confidence and rubric legend, as in decision scoring.
Malformed JSON or invalid probabilities are not repaired or retried.

The [separate full-typed runs](../generation-full-typed-n1/README.md) required
the model to generate those derived fields itself. Their 0/3 valid generation
results and null ratios remain unchanged. The probability contract changes
the prompt/output workload and uses a stricter simplex tolerance (1e-6
versus 0.002), so differences between contracts cannot be attributed solely
to removing arithmetic. This is a separately measured comparison, not a
retrospective repair of earlier outputs.

## Audit and retained evidence

[manifest.json](manifest.json), all three model JSONs, and all three model logs
were copied byte-for-byte from
/data/zefan/open-jev/evals/generation-probability-contract-n1-v1.
[transfer.json](transfer.json) records source hashes and confirms they were
unchanged before and after transfer.

[audit.json](audit.json) records **991 passed checks, zero inconsistencies**:
the model/revision/code identities, source files against the recorded Git
commit, original request and hashes, contracts, commands, all warmups and
measured trials, raw probability JSON, manually recomputed final typed fields,
valid counts, medians and ratios. Raw decoded text agrees with raw generation
after removing only recorded model special-token spellings. Tokens and text
were retained; the tokenizer and model were not rerun.

The manifest records the same GPU UUID with idle pre/postflight checks for
every model and **zero foreign-process samples**. Its monitor sampled every
two seconds; this does not prove uninterrupted exclusivity between samples.
Other GPUs were not audited here. No semantic gold, equal-quality test, broad
workload distribution, or independent weight-tensor audit is part of this
artifact review.

Reproduce the standard-library audit from the repository root, with the
recorded commit available locally:

    python3 reports/generation-probabilities-n1/audit.py

This recomputes audit.json without network access, GPU work, or importing the
benchmark's validator. The original seven evidence files are never changed.
