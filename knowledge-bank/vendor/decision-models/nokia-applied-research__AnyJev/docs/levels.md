# Levels and routes: what an answer promises

Every answer AnyJev returns says how it was read. A `Decision` from `Decider` carries a `level`; a
decision from `Tacit` carries a `route`. Downstream code can check either one before it acts.

## `Decider`: any open LLM, training-free

One typed question (`choice`, `noul`, `score`) becomes one prompt that ends where the answer label
would be written. The model's next-token log-probabilities over the label tokens are the readout.
Nothing is generated and nothing is parsed.

| level | needs | does | does not |
|---|---|---|---|
| `raw` | nothing | one prompt; softmax restricted to the option labels | correct the position bias or the label prior |
| `L0` (default) | nothing | reads the options in each of their K rotations, so every option sits at every position; combines the rotations in log space; divides out the label prior, estimated without labels | calibrate the confidence against labels |

- **The label prior.** By default it comes from the batch being decided (`prior="batch"`, at strength
  0.75, from 8 states on). `prior="content_free"` estimates it from probe states instead, and
  `prior="none"` turns it off. The batch prior assumes the labels in a batch are not dominated by
  one option; when they are, it costs accuracy.
- **The rotation budget.** L0 costs K prefills for a K-option choice. With
  `Decider(adaptive_shifts=True, canonical_order=True)` it reads rotations until the leader is far
  enough ahead, and `calibrate_adaptive` sets that threshold so the answer matches the full cycle's
  at a stated rate, without labels. See [rotation_budget.md](rotation_budget.md).
- **Enforcement.** `decide(..., require="L0")` raises `LevelError` when a decision is below the asked
  level; `Decision.require` and `DecisionSet.require` do the same after the fact.
- **Diagnostics.** Every decision records how it was read: `answer_mass` (the probability the model
  put on the label tokens at all; a low value means the prompt did not land), `order_flip_raw`,
  `permutations`, `prior_method`, `prior_strength`, and with the rotation budget `shifts_used` and
  `stop_threshold`.

0.3.0 removed the label-trained levels (`L1`, temperature on labels, and `L2`, closed-form heads on
hidden states). They remain in `anyjev==0.2.0`.

## `Tacit`: the self-distilled models

The Tacit checkpoints on Hugging Face ([collection](https://huggingface.co/collections/morriszjm/tacit-6ac41d0b50af9e5417c5c234))
answer a typed decision in one forward pass. `Tacit.decide` returns a dict:

| key | meaning |
|---|---|
| `answer`, `index` | the chosen option and its position in `options` |
| `probs` | probability per option |
| `margin` | log-probability gap between the top two options |
| `route` | `"one_forward"` or `"cot"` |
| `first_pass`, `reasoning_tokens` | only on a `"cot"` decision: the one-forward answer it replaced, and the length of the reasoning |

| route | when | how |
|---|---|---|
| `one_forward` | always, unless escalated | one prefill of the prompt the model was trained with, the options in the order given, read like `raw` |
| `cot` | `adaptive=True`, `margin < tau`, and the cap allows it | the model reasons with thinking on; after it closes its thought, `Answer:` is appended and the label distribution is read the same way, so an escalated decision also has probabilities |

- **The cap.** At most `max_cot_share` of the last `cot_window` decisions escalate (rounded up), so
  a burst of hard inputs after a quiet period is still bounded. `cot_window=None` counts every
  decision since loading. One `Tacit` instance, or one `python -m anyjev.serve` gateway, shares its
  cap across threads and clients. When the cap is reached, a low-margin decision keeps its
  one-forward answer.
- **A Tacit checkpoint is also an ordinary causal LM.** `Decider` builds the same prompt, so
  `Decider(HFBackend("morriszjm/Tacit-4B"), level="raw")` reads the same distribution as Tacit's one
  forward; `level="L0"` reads every rotation (K prefills). The published Tacit results use Tacit's own
  routes (one forward, and adaptive for two models), not `L0`.
