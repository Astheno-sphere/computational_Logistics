# The rotation budget: how many cyclic shifts a decision actually needs

L0 shows a K-option `choice` in K rotations so every option sits at every position once. This page is
about not paying for all K. A step-by-step walk through the same material, with the arithmetic written
out, is [`rotation_budget.zh-CN.md`](rotation_budget.zh-CN.md) (Chinese).

From `bench/results_layout/2026-09-27/`: Qwen2.5-7B-Instruct and Qwen3-8B on massive_route (K=18) and
newsgroups (K=20), 900 states per cell, 300 for calibration and 600 held out. The study code that
produced these files is not in the current tree; it is `bench/layout/` at tag `v0.2.0`.

## What the full cycle buys

Accuracy of every single fixed rotation, against the full-K average on the same states
(`pp_*.json`, `per_rotation_acc`):

| model | task | K | single rotation: min / mean / max | full cycle |
|---|---|---|---|---|
| Qwen2.5-7B | massive_route | 18 | 0.575 / 0.646 / 0.692 | 0.668 |
| Qwen3-8B | massive_route | 18 | 0.703 / 0.734 / 0.770 | 0.747 |
| Qwen2.5-7B | newsgroups | 20 | 0.672 / 0.693 / 0.718 | 0.707 |
| Qwen3-8B | newsgroups | 20 | 0.653 / 0.691 / 0.712 | 0.708 |

The full cycle is worth +1.4 to +2.2 points over an average single rotation and +3.9 to +9.3 against
the worst one, and it is at or below the **best** single rotation on every cell. So the K forwards buy
insurance against a bad arrangement, plus the invariance `docs/levels.md` promises — not headroom. The
position bias they cancel is large and stable: 3.90 to 6.81 log units of spread, and
`corr(calibration b, held-out b)` of 0.998 to 1.000.

## Stopping: the statistic, then the threshold

Read rotations in `spread_order` and stop when the running marginal is decided. Two choices decide
whether that is safe.

**The statistic.** A gap between the top two *probabilities* saturates at 1, so once the marginal is
peaked it carries no information — exactly the regime where the rule must decide. An earlier sweep
saw this without naming it: margins of 0.05, 0.1 and 0.2 gave identical results. The **log-odds
margin** — the same gap in log space — is unbounded. Calibrated per (model, question) at a 1% target,
the difference is not a matter of degree (`margin_default.json`):

| stopping rule | worst-cell mean shifts | cells certified of 4 |
|---|---|---|
| probability gap + unanimity (pre-0.6) | 7.89 | **2** |
| probability gap alone | 6.05 | **2** |
| log-odds margin + unanimity | 7.96 | 4 |
| **log-odds margin alone** (`adaptive_stat="logit"`) | **6.12** | **4** |

On two cells no probability-gap threshold certifies 1% at any value. Unanimity costs about 1.8 shifts
and certifies nothing extra.

**The threshold.** The target is agreement with our own full-K answer, not accuracy, so it is measured
on **unlabelled** states — that is what makes the guarantee free. A threshold fit to the calibration
split's observed disagreement does not hold out: at a 1% target, 300 states allow three disagreements
and fitting to exactly three overfits (held-out 0.013–0.025). `Decider.calibrate_adaptive` requires a
Clopper-Pearson 95% upper bound to clear the target instead:

| cell | K | threshold | mean shifts | vs K | held-out disagreement | accuracy (full cycle) |
|---|---|---|---|---|---|---|
| Qwen2.5-7B / massive_route | 18 | 4.50 | 6.12 | 2.9x | 0.008 | 0.663 (0.668) |
| Qwen2.5-7B / newsgroups | 20 | 6.00 | 6.00 | 3.3x | 0.000 | 0.707 (0.707) |
| Qwen3-8B / massive_route | 18 | 9.50 | 5.37 | 3.4x | 0.000 | 0.747 (0.747) |
| Qwen3-8B / newsgroups | 20 | 8.25 | 4.75 | 4.2x | 0.003 | 0.710 (0.708) |

The bound also reports honestly when a calibration set is too small: with zero observed disagreements,
24 states still only bound the rate at 12%, because the floor is `1 - delta**(1/n)`. The method then
returns no threshold and every shift is read. Before calibration the threshold is
`DEFAULT_LOG_MARGIN = 8.5`, the smallest value certifying 1% on all four cells at once (1.9x–3.9x).

## Why stopping early is safe: rotate a canonical listing

Reading a subset of shifts does not cancel the position bias, so applying the subset to *the caller's*
listing would make the answer depend on the order the options were typed in — the property
`docs/levels.md` promises L0 removes. `Decider(canonical_order=True)` rotates a listing
ordered by the option text instead, so the prompts are a function of the option **set**: any two
listings of the same options return identical probabilities, at any shift budget. That is stronger
than the full cycle used to give, since a full cycle equalises positions but not which options sit
next to each other, and the options attend to one another.

## What it costs on an engine

Each shift is a request, and the rule reads them in rounds, each a barrier the batch waits behind.
`adaptive_wave` asks for w shifts per round. Qwen2.5-7B, massive_route, 300 states, threshold certified
at 1% on 600 unlabelled states (10800 requests, 49 s, once), one H100 NVL, runs serial on an idle host
(`vllm_q25_massive.json`, `hf_q25_massive.json`):

| engine | readout | requests / decision | decisions/s | vs full cycle | agreement | accuracy |
|---|---|---|---|---|---|---|
| vLLM 0.7.0 | all 18 shifts | 18.00 | 16.73 | 1.00x | 1.000 | 0.697 |
| vLLM 0.7.0 | adaptive, wave 1 | 7.16 | 22.12 | 1.32x | 0.987 | 0.703 |
| vLLM 0.7.0 | **adaptive, wave 2** | 7.28 | **37.20** | **2.22x** | 0.987 | 0.703 |
| vLLM 0.7.0 | adaptive, wave 4 | 9.25 | 31.84 | 1.90x | 0.987 | 0.703 |
| transformers | all 18 shifts | 18.00 | 7.04 | 1.00x | 1.000 | 0.697 |
| transformers | **adaptive, wave 1 / 2** | 7.24 / 7.43 | 16.47 / 16.46 | **2.34x** | 0.987 | 0.703 |
| transformers | adaptive, wave 4 | 9.23 | 13.15 | 1.87x | 0.987 | 0.703 |

On vLLM, waves of 1 and 2 issue the same requests and differ by 1.7x in wall clock: identical work,
half the rounds. Locally there are no round trips, so 1 and 2 tie. Wider loses on both, which is why
the default is 2. Agreement came in at 0.987 against a 1% target — outside it, which is what a 95%
confidence bound permits, and stated rather than rounded.

**On the variance of the ratio.** A second transformers run of the same command reproduced every stable
quantity exactly — the same certificate (threshold 6.0, bound 0.0079), the same 7.24 and 7.43 requests
per decision, the same 0.987 agreement and 0.703 accuracy — and a different *ratio*, 2.71x instead of
2.34x, because the full-cycle reference came in at 5.98 decisions/s instead of 7.04 while the adaptive
rows held at 16.1-16.2. The ratio inherits the reference's run-to-run variance, so read it as
**2.3x-2.7x on transformers** and the absolute figures as the measurement. The vLLM row is one run.
(`hf_q25_massive.json`, `hf_verify_release.json`.)

## Using it

```python
d = Decider(backend, adaptive_shifts=True, canonical_order=True)   # opt-in
d.calibrate_adaptive(question, unlabelled_states, target=0.01)   # no labels; a few hundred states
d.decide_batch(states, question)                      # diagnostics: shifts_used, stop_threshold
```

Both are opt-in because the published L0 tables were measured with every rotation; they become the defaults when those are regenerated. `adaptive_target` sets the disagreement rate to certify.
`adaptive_margin` pins the threshold by hand and `adaptive_stat="prob"` restores the pre-0.2 rule.
`canonical_order=False` keeps the caller's listing.

## Limits

The saving is bounded by `(P + K*B) / (P + R*B)` for a prefix of P tokens and an option block of B, so
a long agentic context eats it: at R=4 on massive_route the measured speedup falls from 3.7x at a
10-token state to 1.9x at 1500 (`sc_q25_massive.json`). `DEFAULT_LOG_MARGIN` was certified at K=18–20 on
two 7–8B models; outside that, calibrate. And the budget does not go below a few prefills per decision:
where one forward is the requirement, the self-distilled Tacit models answer in one.
