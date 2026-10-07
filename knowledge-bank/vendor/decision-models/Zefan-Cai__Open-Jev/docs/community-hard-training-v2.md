# Diverse hard-data training, version 2

This iteration converts previously verified community use-case categories into
new training examples and starts a separate 27B training stage. It does not
train on JevBench questions, answers, or model mistakes. The frozen released
2B/9B weights and their [JevBench baselines](jevbench-public.md) remain unchanged.

## Frozen data

| Component | All prepared rows | Rows in this training mixture |
| --- | ---: | ---: |
| [Original community controls](community-diversity-v2.md) | 51,200 | 30,720 |
| WANLI decision conversion | 101,207 | 82,045 |
| Earlier task sources, capped replay | Existing corpus | 35,874 |
| Training total | — | **148,639** |

The community controls span support, constrained retrieval, contract clauses,
RAG evidence, browser/tool selection, shell-history selection, game planning,
and explicit-rubric judging. Eight application domains contain 80 authored rule
families, 6,400 parent scenarios, and 25,600 unique semantic contexts. The two
task views of each context are correlated. Whole rule families are held out;
changing candidate IDs or their order does not count as a new context.

These are finite controls over explicit rules and structured attributes. They
are not CUAD annotations, natural-language contract review, human-preference
judgments, or executed racing/UT99 trajectories. The mixed-language support
questions use English rules/attributes and have not had independent linguistic
review. WANLI complements this structured data with natural-language inference.

[WANLI](https://huggingface.co/datasets/alisawuffles/WANLI) is attributed to
Liu, Swayamdipta, Smith and Choi (2022), *WANLI: Worker and AI Collaboration for
Natural Language Inference Dataset Creation*. Its authors generated examples
with a model and had workers label and optionally revise them. We preserve the
published premise, hypothesis and human-reviewed gold, converting the task to
three dynamic Choice candidates. No new teacher API calls were made.

The source is pinned at `61c95318fd71c55b6ba355d76253254615f387ec` and licensed
**CC BY 4.0**. The original community controls are CC0-1.0; the mixed dataset is
not uniformly CC0. Original licenses and attribution remain in every row.
WANLI's official test seed/premise components are reserved before splitting:
6,675 training examples sharing a connected seed/premise component are excluded,
as are two conflicting duplicates and one duplicate. The retained official test
portion has 4,998 rows, so it is not an unfiltered official 5,000-row test score.
The WANLI `ood` partition holds out generation-seed components within the same
English dataset; it is not a new-domain/language benchmark.

Replay selects at most 1,500 training rows per old source, rotating through
hash-ordered parent groups without oversampling. The final mixture contains
328,672 rows across all splits: 148,639 train, 26,764 calibration, 25,482
validation, 43,301 test and 84,486 OOD. Source identifiers are not domain counts.
The [mixture manifest](../reports/community-diversity-v2/training-mixture-manifest.json)
records every input checksum and the exact selected rows' output checksums.

## Training and evaluation

The new stage uses Qwen/Qwen3.8-27B revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, initialized from the complete step
26,500 LoRA/head snapshot of the earlier browser/drone expansion. The optimizer,
random streams and dataset cursor start fresh. The earlier run and its logs are
retained. Baseline measurements in this new run refer to those initialization
weights on the new held-out data, not to untrained Qwen weights.

The predeclared run uses H100 physical GPUs 0–3 on N1-1, global batch four,
37,160 optimizer steps, LoRA rank eight, a 4,096-token input limit, adapter/head
learning rates `2e-5` / `5e-5`, NLL plus Brier weight 0.1, and seed 20260921.
This is one shuffled pass over all training rows, with one wrapped row to fill
the final four-row batch. Complete optimizer snapshots are written every 500
steps. A 512-row calibration set fits temperature; 512 test and 512 OOD rows
measure initialization and final performance. No test metrics select a checkpoint.

After the final checkpoint is saved, calibrated and reloaded successfully, the
owned training processes release their GPUs. A separate owned server then runs
all 231 pinned public JevBench tasks on GPU 0 with caching off and the same
16,384-token evaluation limit as the released baselines. The hosted Jev/GPT
baseline calls are not repeated. Raw responses remain private; all scores,
failures, identity checks and the complete denominator are retained.

The target is to improve on measured Jev's **81/111 hard** and **200/231 overall**.
This is a target, not a result. Only the predeclared final checkpoint is used for
the headline external comparison. New 27B versus released 9B also changes model
size and earlier training history, so it cannot isolate the effect of the new data.

## Verification and reproduction

The [independent WANLI audit](../reports/community-diversity-v2/data-pipeline-audit.json)
reconstructs connected components and checks every retained source label and
text. The [lexical overlap screen](../reports/community-diversity-v2/final-overlap-screen.json)
finds no matching visible inputs, qualifying state leaves or 13-token state
shingles against the frozen JevBench/JF100 requests. This does not rule out
semantic paraphrases or foundation-model pretraining exposure.

```bash
python -m jev.community_diversity_v2 --output-dir data/community-diversity-v2
python -m jev.wanli_data --source-dir runs/wanli-source --output-dir data/wanli-decisions-v1
```

Use `scripts.build_community_hard_mix` with the exact source list and cap in the
mixture manifest. Both new and replay source files are checksum checked. The
trainer's new `--initialize-training-weights` option is mutually exclusive with
`--resume-training`; a later exact resume remains bound to the new run's original
data and initialization provenance.

[Training configuration](../reports/community-diversity-v2/training-plan.json)
and [CPU checks](../reports/community-diversity-v2/cpu-validation.json) record
the reviewed setup. The new job has launched on the four assigned H100 GPUs and is measuring initialization weights before optimizer updates. Model improvement remains pending. The [full tokenizer preflight](../reports/community-diversity-v2/tokenizer-preflight.json) checked all 328,672 rows, with a maximum of 1,756 tokens and no truncation.
