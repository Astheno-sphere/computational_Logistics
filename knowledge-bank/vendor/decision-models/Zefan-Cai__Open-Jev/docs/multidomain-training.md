# How domains share one decision head

Open-Jev trains a shared candidate scorer. Each model size has one LoRA adapter
and one `Linear(hidden_size, 1)` head. The base language-model parameters are
frozen. A candidate's description is an input to the backbone, so the head has
no fixed class vocabulary and its output dimension does not depend on the
number of candidates.

For a Choice with context `x`, question `q` and candidates `c[1..K]`:

```text
input[i] = candidate_prompt(x, q, c[i])
h[i]     = backbone_with_shared_LoRA(input[i]).last_token_hidden
s[i]     = shared_linear_head(h[i])             # one scalar
p        = softmax([s[1], ..., s[K]])           # only within this question
```

Support candidates such as "refund" and "escalate", and game candidates such
as "left", "right" and "jump", use the same parameters. Their descriptions
and contexts produce different hidden states. Three candidates create three
input sequences; a 255-candidate request creates 255. Candidate sequences can
be batched, and serving bounds that batch size. The original uncached path
encodes the context in every sequence. The new optional
[prefix-cache inference path](prefix-caching.md) encodes shared request and
question prefixes once and continues from separate candidate branches. It is
not used by the training forward pass or the historical evaluations above.

Noul uses one input and one score `s`, constructs logits `[0, s]`, and returns
`sigmoid(s)` as P(yes). Score uses candidate descriptions for ordered rubric
levels, then returns the probability-weighted level index. Each independent
question is a separate decision row, including questions sharing the same
application context. The code-owned executor interprets the resulting answers.

Implementation: [candidate prompts](../jev/api.py),
[backbone and scalar head](../jev/model.py),
[distributed loss](../jev/train_distributed.py).

## Current mixture and weighting

The completed 2B/9B runs consumed 80,816 release-v2 training rows from 13 source
identifiers. The fresh four-GPU 27B run adds browser and drone snapshot controls:
110,324 training rows from 15 source identifiers. Citation, entity alignment,
amount, email and phone controls are separate prepared corpora and are not
part of that running mixture.

The mixer preserves existing splits and concatenates their records. Training
uses a deterministic global shuffle with each selected row once per pass.
There is no domain reweighting in the current full-pass runs. Four DDP ranks
each process one decision row per optimizer step and average their gradients:
27,581 steps cover 110,324 rows. A step need not include four different domains.

| Source | Current 27B train rows |
| --- | ---: |
| Painting geometry | 23,552 |
| Drone snapshots | 15,694 |
| Browser snapshots | 13,814 |
| Snake | 12,508 |
| Security incidents | 8,874 |
| ViZDoom basic | 6,354 |
| Reasoning controls | 5,442 |
| Invoice processing | 5,370 |
| Customer-service workflow | 4,392 |
| Customer-context controls | 4,206 |
| Agent trace observability | 3,780 |
| Tic-tac-toe | 3,264 |
| Wiki navigation | 1,700 |
| Tile platformer | 1,346 |
| T-Rex runner | 28 |
| **Total** | **110,324** |

For each row, with target distribution `y` and predicted probabilities `p`:

```text
loss = -sum(y * log(p)) + 0.1 * sum((p - y) ** 2)
```

Rows have equal explicit loss weight. More candidates or longer contexts add
compute, and equal row weights do not make gradient magnitudes equal across
domains. Several rows may describe the same parent scene: a painting supplies
many pixels and a workflow supplies several action questions. Consequently,
row proportions are not proportions of independent scenarios. Painting is
21.35% of this training mixture; T-Rex is approximately 0.025%.

These runs establish a reproducible first mixture, not an optimal mixture or
proof of positive transfer. There is no controlled single-domain-versus-mixed
ablation establishing the effect of cross-domain sharing. Per-source held-out
results are retained so that aggregate accuracy does not conceal weak domains.
Future mixture comparisons should keep the held-out sets and training budget
fixed; they must not mutate the frozen input of an active run.

The [mixture integrity audit](browser-drone-expansion.md) checks source identity
and parent-group separation. Test and OOD rows remain held out, calibration is
separate, and JF100 is an independent evaluation source excluded from training.
