"""Decider: the pipeline from (state, questions) to leveled decisions.

raw : one prompt, the options in the order given, restricted softmax over the label tokens.
L0  : permutation marginalization + label-free prior correction (batch mean
      by default, content-free probes optional). Zero labels.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from anyjev.calibrate.contextual import (
    DEFAULT_PROBES,
    apply_contextual,
    batch_prior,
    content_free_prior,
)
from anyjev.calibrate.permute import cyclic_shifts, flip_rate_across_perms, marginalize, spread_order
from anyjev.calibrate.stopping import DEFAULT_LOG_MARGIN, choose_threshold, log_margin
from anyjev.question import Question
from anyjev.readout import DEFAULT_SYSTEM, build_prompt, label_ids_for_perm, render_chat_parts, resolve_labels
from anyjev.result import Decision, DecisionSet
from anyjev.state import render_state

LEVELS = ("raw", "L0")
PRIORS = ("batch", "content_free", "none")


def _softmax(lp: np.ndarray) -> np.ndarray:
    z = np.asarray(lp, dtype=np.float64)
    z = z - z.max()
    p = np.exp(z)
    return p / p.sum()


class Decider:
    DEFAULT_PRIOR_STRENGTH = {"batch": 0.75, "content_free": 1.0, "none": 0.0}

    def __init__(self, backend, *, level: str = "L0", prior: str = "batch", min_prior_n: int = 8,
                 prior_strength: Optional[float] = None,
                 max_permutations: Optional[int] = None, combine: str = "logmean",
                 cf_probes: Sequence[str] = DEFAULT_PROBES, record_content_free: bool = False,
                 system: str = DEFAULT_SYSTEM, shared_prefix="auto", shared_min_prefix_tokens: int = 256,
                 adaptive_shifts: bool = False, adaptive_min_shifts: int = 2,
                 adaptive_margin: Optional[float] = None, adaptive_stat: str = "logit",
                 adaptive_target: float = 0.01, adaptive_wave: int = 2,
                 adaptive_order: str = "spread", canonical_order: bool = False):
        """prior_strength: exponent applied to the prior before dividing (1.0 = full correction,
        0.0 = none). Default 0.75 for the batch prior, 1.0 for the content-free prior: over 230
        (model, question) points the batch prior at 0.75 had the best mean gain and the smallest
        loss on questions whose true label marginal is skewed (docs/when_l0_helps.md).

        shared_prefix: "auto" (default) scores the permutations of one state through the
        backend's `score_shared` when it has one, a state has at least 3 permutations, and the
        shared prefix is at least `shared_min_prefix_tokens` long (below that, one batched
        forward over the full prompts is cheaper than a prefix forward plus a suffix forward);
        True shares whenever there are at least 2 permutations, regardless of length;
        False always sends full prompts.

        adaptive_shifts (opt-in in 0.2; the default once the shipped tables are
        regenerated under it): for choice questions with K >= 3, read the
        cyclic shifts in `spread_order` and stop once the running marginal is decided enough,
        after at least `adaptive_min_shifts`. The marginal is then an average over a subset of
        shifts, so the position bias is reduced rather than cancelled exactly -- which is why the
        threshold is chosen against a stated disagreement rate with the full-K answer instead of
        by hand. Set False to always read every shift.

        adaptive_stat: "logit" (default) compares the log-odds margin, top-1 minus top-2 of the
        marginal in log space; "prob" is the pre-0.6 rule (a probability gap plus unanimity across
        the shifts read) and is kept for callers who pinned `adaptive_margin`. The log-odds margin
        is the default because a probability gap saturates at 1 and stops discriminating exactly
        where the rule has to decide: over four (model, task) cells at K=18-20 it could not certify
        a 1% disagreement rate on two of them at any threshold (docs/rotation_budget.md).

        adaptive_target: the disagreement rate with the full-K answer that `calibrate_adaptive`
        certifies. Until a question is calibrated, the threshold is `DEFAULT_LOG_MARGIN` (8.5), the
        smallest value that certified 1% on all four of those cells at once, worth 1.9x-3.9x;
        calibrating per (model, question) was worth about 1.5x more.

        adaptive_margin: overrides the threshold for every question, in the units of
        `adaptive_stat`. None (default) means the calibrated value, or `DEFAULT_LOG_MARGIN`.

        canonical_order (opt-in in 0.2, and worth turning on whenever `adaptive_shifts`
        is): rotate a canonical listing of the options, ordered by their
        text, instead of the caller's listing. Reading every shift gives every option every position
        either way, but which options sit next to each other still follows the caller's order, and a
        partial shift budget does not cancel the position bias either -- so without this the decision
        can depend on the order the options were typed in. With it the prompts are a function of the
        option *set*, so listing the same options any other way returns the same probabilities
        exactly, at any shift budget. That is what makes `adaptive_shifts` safe to leave on. Note it
        is a different property from `diagnostics["order_flip_l0"]`, which reports whether the shifts
        read disagreed among themselves. Set False to reproduce pre-0.6 prompts.

        adaptive_wave: shifts requested per backend call (default 2). A wave overshoots the stop
        point slightly and in exchange waits on half as many rounds, and a round is a barrier the
        whole batch sits behind. Measured on Qwen2.5-7B / massive_route, 300 states, at a certified 1%
        target: on a vLLM server waves of 2 issue the same requests as waves of 1 (7.28 against 7.16)
        and run 1.7x faster in wall clock (2.22x over the full cycle against 1.32x); on the local
        transformers backend, where there are no round trips, 1 and 2 tie at 2.34x and wider waves
        lose. Hence 2: best remotely, tied-best locally. Wider is worse on both
        (`bench/results_layout/2026-09-27/{vllm,hf}_q25_massive.json`). `adaptive_min_shifts` is
        effectively rounded up to a multiple of the wave."""
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        if prior not in PRIORS:
            raise ValueError(f"prior must be one of {PRIORS}")
        self.backend = backend
        self.level = level
        self.prior = prior
        self.min_prior_n = min_prior_n
        if prior_strength is not None and not 0.0 <= prior_strength <= 1.0:
            raise ValueError("prior_strength must be between 0 and 1")
        self.prior_strength = prior_strength
        self.max_permutations = max_permutations
        self.combine = combine
        self.cf_probes = tuple(cf_probes)
        self.record_content_free = record_content_free
        self.system = system
        if shared_prefix not in ("auto", True, False):
            raise ValueError("shared_prefix must be 'auto', True or False")
        self.shared_prefix = shared_prefix
        self.shared_min_prefix_tokens = shared_min_prefix_tokens
        if adaptive_min_shifts < 1:
            raise ValueError("adaptive_min_shifts must be >= 1")
        if adaptive_margin is not None and adaptive_margin < 0:
            raise ValueError("adaptive_margin must be >= 0")
        if adaptive_stat not in ("logit", "prob"):
            raise ValueError("adaptive_stat must be 'logit' or 'prob'")
        if not 0.0 < adaptive_target < 1.0:
            raise ValueError("adaptive_target must be between 0 and 1")
        if adaptive_wave < 1:
            raise ValueError("adaptive_wave must be >= 1")
        self.adaptive_shifts = adaptive_shifts
        self.adaptive_min_shifts = adaptive_min_shifts
        self.adaptive_margin = adaptive_margin
        self.adaptive_stat = adaptive_stat
        self.adaptive_target = adaptive_target
        self.adaptive_wave = adaptive_wave
        if adaptive_order not in ("spread", "consecutive"):
            raise ValueError("adaptive_order must be 'spread' or 'consecutive'")
        self.adaptive_order = adaptive_order
        self.canonical_order = canonical_order
        self.stats = {"backend_calls": 0, "flat_prompts": 0, "shared_groups": 0, "shared_prompts": 0,
                      "adaptive_items": 0, "adaptive_shifts_total": 0}
        self._stop: Dict[str, Dict[str, Any]] = {}      # q.key -> calibrated stopping certificate
        self._prefix_len_cache: Dict[str, int] = {}
        self._label_ids: Dict[tuple, List[int]] = {}
        self._running: Dict[str, Tuple[np.ndarray, int]] = {}   # q.key -> (sum p_pos_raw [P,K], n)
        self._cf_cache: Dict[str, np.ndarray] = {}                # q.key -> cf prior [P,K]

    # ---- public -------------------------------------------------------
    def decide(self, state: Any, questions: Sequence[Question], level: Optional[str] = None,
               require: Optional[str] = None) -> DecisionSet:
        """require: raise LevelError unless every result reaches this level, e.g. `require="L0"`
        where acting on an uncorrected raw probability would be a bug."""
        level = level or self.level
        decs = self._run([state], list(questions), level)
        items = [decs[(0, qi)] for qi in range(len(questions))]
        out = DecisionSet(items, level)
        return out.require(require) if require else out

    def decide_batch(self, states: Sequence[Any], question: Question,
                     level: Optional[str] = None, require: Optional[str] = None) -> List[Decision]:
        """Many states, one question. The bench path, and the best path for
        batch prior estimation."""
        level = level or self.level
        decs = self._run(list(states), [question], level)
        out = [decs[(si, 0)] for si in range(len(states))]
        if require:
            for d in out:
                d.require(require)
        return out

    def strength(self) -> float:
        """The exponent applied to the prior in use (see prior_strength)."""
        if self.prior_strength is not None:
            return self.prior_strength
        return self.DEFAULT_PRIOR_STRENGTH[self.prior]

    def running_prior(self, question: Question) -> Optional[np.ndarray]:
        """The batch prior accumulated so far for this question, [P, K] by position, or None."""
        entry = self._running.get(question.key)
        if entry is None or entry[1] < self.min_prior_n:
            return None
        return batch_prior(entry[0][None] / entry[1])

    # ---- internals ----------------------------------------------------
    def _labels_for(self, q: Question):
        """(labels, token ids) for this question kind and size, resolved once per tokenizer."""
        key = (q.kind, q.k)
        if key not in self._label_ids:
            self._label_ids[key] = resolve_labels(self.backend.tokenizer, q)
        return self._label_ids[key]

    def _score(self, prompts: List[str], prompt_ids: List[List[int]],
               prompt_parts: List[Tuple[str, str]]) -> List[np.ndarray]:
        """Prompts that share a prefix and the same label ids (the permutations of one
        state) go through the backend's score_shared in one group; the rest go flat."""
        out: List[Optional[np.ndarray]] = [None] * len(prompts)
        use_shared = self.shared_prefix is not False and hasattr(self.backend, "score_shared")
        groups: Dict[tuple, List[int]] = {}
        if use_shared:
            min_size = 2 if self.shared_prefix is True else 3
            for i, (pre, suf) in enumerate(prompt_parts):
                if suf:
                    groups.setdefault((pre, tuple(prompt_ids[i])), []).append(i)
            groups = {k: v for k, v in groups.items() if len(v) >= min_size}
            if self.shared_prefix == "auto":
                groups = {k: v for k, v in groups.items() if self._prefix_tokens(k[0]) >= self.shared_min_prefix_tokens}
        shared = {i for idxs in groups.values() for i in idxs}
        flat = [i for i in range(len(prompts)) if i not in shared]
        if flat:
            self.stats["backend_calls"] += 1
            self.stats["flat_prompts"] += len(flat)
            for i, lp in zip(flat, self.backend.next_token_logprobs([prompts[i] for i in flat],
                                                                   [prompt_ids[i] for i in flat])):
                out[i] = lp
        if groups:
            keys = list(groups)
            g = [(k[0], [prompt_parts[i][1] for i in groups[k]]) for k in keys]
            ids = [list(k[1]) for k in keys]
            self.stats["backend_calls"] += 1
            self.stats["shared_groups"] += len(g)
            self.stats["shared_prompts"] += len(shared)
            for k, lps in zip(keys, self.backend.score_shared(g, ids)):
                for i, lp in zip(groups[k], lps):
                    out[i] = lp
        return out  # type: ignore[return-value]

    def _cf_prior(self, q: Question, perms: List[List[int]], labels, perm_ids) -> np.ndarray:
        """Content-free prior per permutation, [P, K] in position space, cached per question."""
        if q.key not in self._cf_cache:
            prompts, ids, parts = [], [], []
            for perm, pids in zip(perms, perm_ids):
                for probe in self.cf_probes:
                    spec = build_prompt(probe, q, perm, self.system, labels)
                    pre, suf = render_chat_parts(self.backend.tokenizer, spec)
                    prompts.append(pre + suf)
                    ids.append(pids)
                    parts.append((pre, suf))
            lps = self._score(prompts, ids, parts)
            C = len(self.cf_probes)
            self._cf_cache[q.key] = np.stack([
                content_free_prior(np.stack([_softmax(lps[pi * C + c]) for c in range(C)]))
                for pi in range(len(perms))])
        return self._cf_cache[q.key]

    def _stop_rule(self, q: Question) -> Tuple[float, str]:
        """(threshold, statistic) for this question: an explicit `adaptive_margin` wins, then a
        certificate from `calibrate_adaptive`, then the measured default."""
        if self.adaptive_margin is not None:
            return float(self.adaptive_margin), self.adaptive_stat
        cert = self._stop.get(q.key)
        if cert is not None and cert.get("threshold") is not None:
            return float(cert["threshold"]), cert.get("stat", "logit")
        if self.adaptive_stat == "prob":
            return 0.1, "prob"          # the pre-0.6 default; measured at a 2.3% disagreement rate
        return DEFAULT_LOG_MARGIN, "logit"

    def calibrate_adaptive(self, question: Question, states: Sequence[Any], *,
                           target: Optional[float] = None, delta: float = 0.05,
                           level: str = "L0") -> Dict[str, Any]:
        """Certify a stopping threshold for one question from **unlabelled** states.

        Reads every cyclic shift of every state once through the ordinary pipeline -- so whatever
        prior and combine rule this Decider is configured with are included -- and then picks the
        cheapest threshold whose disagreement with the full-K answer is under `target` by a
        Clopper-Pearson upper bound at confidence 1 - `delta`. The reference is our own full-strength
        readout, never a label, which is what makes the guarantee free.

        Returns the certificate: the threshold, how many shifts it would have read on these states,
        and the bound that was achieved. A question with no certificate falls back to
        `DEFAULT_LOG_MARGIN`. If nothing can be certified at this target the threshold is None and
        every shift is read, which is the safe direction.

        Spend a few hundred states on it; at a 1% target, 300 states allow three disagreements and
        the bound is what stops that from being fitted too tightly.
        """
        if question.kind != "choice" or question.ordered or question.k < 3:
            raise ValueError("adaptive shifts only apply to unordered choice questions with k >= 3")
        if not states:
            raise ValueError("calibrate_adaptive needs states")
        target = self.adaptive_target if target is None else target
        want_cf = level != "raw" and (self.prior == "content_free" or self.record_content_free)
        record: List[List[Tuple[float, int]]] = []
        self._run_adaptive_choice([render_state(s) for s in states], question, level, want_cf,
                                  record=record)
        margins = np.asarray([[m for m, _ in tr] for tr in record], dtype=np.float64)
        winners = np.asarray([[w for _, w in tr] for tr in record], dtype=int)
        threshold, info = choose_threshold(margins, winners, target, self.adaptive_min_shifts, delta)
        cert = {"threshold": threshold, "stat": "logit", "question_id": question.id, **info}
        self._stop[question.key] = cert
        return cert

    def _run_adaptive_choice(self, state_texts: List[str], q: Question, level: str, want_cf: bool,
                             record: Optional[List[List[Tuple[float, int]]]] = None) -> List[Decision]:
        """Sequential cyclic shifts with an early stop per state. See __init__ for the rule.

        `record` is the calibration hook: given a list, every shift is read and the running
        (log-odds margin, winner) after each one is appended per state, so `calibrate_adaptive` can
        choose a threshold offline from the same pipeline that will serve."""
        tok = self.backend.tokenizer
        labels, ids = self._labels_for(q)
        perms = self._perms(q, level)
        perm_ids = [label_ids_for_perm(q, ids, perm) for perm in perms]
        P, K, n = len(perms), q.k, len(state_texts)
        cf_prior = self._cf_prior(q, perms, labels, perm_ids) if want_cf else None
        lp_rows: List[List[np.ndarray]] = [[] for _ in range(n)]        # per state, per shift read
        p_rows: List[List[np.ndarray]] = [[] for _ in range(n)]
        used: List[List[int]] = [[] for _ in range(n)]
        sums, counts = self._running.get(q.key, (np.zeros((P, K)), 0))
        if sums.shape != (P, K):
            sums, counts = np.zeros((P, K)), 0
        shift_sum = np.zeros((P, K))                                     # this call's per-shift totals
        shift_n = np.zeros(P, dtype=int)
        active = list(range(n))

        def prior_for(sidx: int) -> Optional[np.ndarray]:
            if self.prior == "content_free":
                return cf_prior[sidx]
            if self.prior != "batch":
                return None
            tot = sums[sidx] + shift_sum[sidx]
            m = counts + shift_n[sidx]
            if m >= self.min_prior_n:
                return batch_prior((tot / m)[None])
            # later shifts see only the hard items: fall back to the pooled position profile
            pooled_n = counts * P + shift_n.sum()
            if pooled_n >= self.min_prior_n:
                return batch_prior(((sums.sum(0) + shift_sum.sum(0)) / pooled_n)[None])
            return None

        strength = self.strength()

        def corrected(si: int) -> np.ndarray:
            rows = []
            for sidx, p in zip(used[si], p_rows[si]):
                pr = prior_for(sidx)
                rows.append(apply_contextual(p, np.power(pr, strength)) if pr is not None else p)
            return np.stack(rows)

        order = spread_order(P) if self.adaptive_order == "spread" else list(range(P))
        threshold, stat = self._stop_rule(q)
        wave = max(1, int(self.adaptive_wave))
        if record is not None:
            threshold, wave = None, 1             # calibration reads every shift, one at a time, and
            trace = [[] for _ in range(n)]        # decides offline once it has the whole trace

        def decided(si: int) -> bool:
            """The stopping rule. `logit` compares the log-odds margin, which does not saturate;
            `prob` keeps the pre-0.6 behaviour (a probability gap plus unanimity across the shifts
            read) for callers who pinned `adaptive_margin`."""
            pc = corrected(si)
            marg = marginalize(pc, [perms[sidx] for sidx in used[si]], self.combine)
            if record is not None:
                trace[si].append((log_margin(marg), int(np.argmax(marg))))
                return False
            if stat == "logit":
                return log_margin(marg) >= threshold
            winners = {perms[sidx][int(np.argmax(pc[j]))] for j, sidx in enumerate(used[si])}
            top = np.sort(marg)[::-1]
            return len(winners) == 1 and top[0] - top[1] >= threshold

        for start in range(0, P, wave):
            batch = order[start:start + wave]
            if start > 0 and (start >= self.adaptive_min_shifts or record is not None):
                active = [si for si in active if not decided(si)]
            if not active:
                break
            # one backend call per wave: `adaptive_wave > 1` trades a little precision in the stop
            # point for fewer round trips, which is what a remote engine charges for.
            prompts, pids, parts, who, which = [], [], [], [], []
            for r in batch:
                for si in active:
                    pre, suf = render_chat_parts(tok, build_prompt(state_texts[si], q, perms[r],
                                                                  self.system, labels))
                    prompts.append(pre + suf)
                    pids.append(perm_ids[r])
                    parts.append((pre, suf))
                    who.append(si)
                    which.append(r)
            for si, r, lp in zip(who, which, self._score(prompts, pids, parts)):
                p = _softmax(lp)
                lp_rows[si].append(lp)
                p_rows[si].append(p)
                used[si].append(r)
                shift_sum[r] += p
                shift_n[r] += 1
        if record is not None:
            for si in range(n):
                decided(si)                       # the margin after the final shift
                record.append(trace[si])
        # fold this call into the running prior (per shift, only the items that ran it)
        # stored as a P x K sum with a single count: use the shift-0 count, which every item ran
        scale = (shift_n[0] / np.maximum(shift_n, 1))[:, None]
        self._running[q.key] = (sums + shift_sum * scale, counts + int(shift_n[0]))

        out: List[Decision] = []
        for si in range(n):
            p_pos_raw = np.stack(p_rows[si])
            used_perms = [perms[sidx] for sidx in used[si]]
            pc = corrected(si)
            probs = marginalize(pc, used_perms, self.combine)
            raw_probs = marginalize(p_pos_raw[:1], used_perms[:1])
            achieved = "L0"
            diag: Dict[str, Any] = {
                "answer_mass": float(np.exp(np.stack(lp_rows[si])).sum(axis=1).mean()),
                "raw_probs": raw_probs, "permutations": len(used_perms), "perms": used_perms,
                "p_pos_raw": p_pos_raw, "shifts_used": len(used_perms), "adaptive": True,
                "stop_threshold": threshold, "stop_stat": stat, "stop_calibrated": q.key in self._stop,
                "prior_method": self.prior if prior_for(used[si][0]) is not None else "none",
                "prior_strength": strength if prior_for(used[si][0]) is not None else 0.0,
                "prior": (np.stack([prior_for(sidx) for sidx in used[si]])
                          if prior_for(used[si][0]) is not None else None),
                "cf_prior": cf_prior[used[si]] if cf_prior is not None else None,
                "batch_prior": None,
                "order_flip_raw": flip_rate_across_perms(p_pos_raw, used_perms),
                "order_flip_l0": flip_rate_across_perms(pc, used_perms),
                "l0_probs": probs,
            }
            self.stats["adaptive_items"] += 1
            self.stats["adaptive_shifts_total"] += len(used_perms)
            out.append(Decision(q, np.asarray(probs), achieved, diag))
        return out

    def _prefix_tokens(self, prefix: str) -> int:
        n = self._prefix_len_cache.get(prefix)
        if n is None:
            n = len(self.backend.tokenizer.encode(prefix, add_special_tokens=False))
            if len(self._prefix_len_cache) > 4096:
                self._prefix_len_cache.clear()
            self._prefix_len_cache[prefix] = n
        return n

    def _perms(self, q: Question, level: str) -> List[List[int]]:
        if level == "raw" or q.ordered:
            return [list(range(q.k))]
        if q.kind == "noul":
            return [[0, 1], [1, 0]]
        shifts = cyclic_shifts(q.k, self.max_permutations)
        if not self.canonical_order:
            return shifts
        # Rotate a canonical listing rather than the caller's. Reading every shift already gives
        # every option every position, but *which options sit next to each other* still follows the
        # caller's order, and options attend to one another (research log entry 21), so the readout
        # is not otherwise invariant to how the list was typed -- and it is much less so when only
        # a few shifts are read. Ordering by the option text first makes the prompts a function of
        # the option *set*, so any two listings of the same options produce the same decision
        # exactly, at any shift budget. Equal texts fall back to the caller's order, which is
        # harmless because equal options are interchangeable.
        canon = sorted(range(q.k), key=lambda i: (str(q.options[i]), i))
        return [[canon[i] for i in perm] for perm in shifts]

    def _run(self, states: List[Any], questions: List[Question], level: str) -> Dict[tuple, Decision]:
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}")
        tok = self.backend.tokenizer
        state_texts = [render_state(s) for s in states]
        want_cf = level != "raw" and (self.prior == "content_free" or self.record_content_free)

        # adaptive choice questions take the sequential path; everything else the batched one
        if self.adaptive_shifts and level != "raw":
            adaptive = [qi for qi, q in enumerate(questions) if q.kind == "choice" and not q.ordered and q.k >= 3]
            if adaptive:
                out: Dict[tuple, Decision] = {}
                for qi in adaptive:
                    for si, dec in enumerate(self._run_adaptive_choice(state_texts, questions[qi], level, want_cf)):
                        out[(si, qi)] = dec
                rest = [qi for qi in range(len(questions)) if qi not in set(adaptive)]
                if rest:
                    sub = self._run(states, [questions[qi] for qi in rest], level)
                    for (si, j), dec in sub.items():
                        out[(si, rest[j])] = dec
                return out

        # 1. collect every prompt once. Content-free probes (shared across states) get their own
        #    registry and their own forward call, so the batch composition of the real prompts --
        #    and with it their bf16 logits -- never depends on whether the probes are cached yet.
        #    Without this, a fresh Decider and a used one score the same states slightly differently,
        #    and `record_content_free` (a diagnostics flag) would move the numbers.
        def registry():
            index: Dict[str, int] = {}
            ids_: List[List[int]] = []
            parts: List[Tuple[str, str]] = []

            def add(spec, ids: List[int]) -> int:
                pre, suf = render_chat_parts(tok, spec)
                text = pre + suf
                if text not in index:
                    index[text] = len(ids_)
                    ids_.append(ids)
                    parts.append((pre, suf))
                return index[text]

            return index, ids_, parts, add

        prompt_index, prompt_ids, prompt_parts, add = registry()
        cf_index, cf_ids, cf_parts, add_cf = registry()

        plan = {}
        for qi, q in enumerate(questions):
            labels, ids = self._labels_for(q)
            perms = self._perms(q, level)
            cf_rows = []
            perm_ids = [label_ids_for_perm(q, ids, perm) for perm in perms]
            if want_cf and q.key not in self._cf_cache:
                for perm, pids in zip(perms, perm_ids):
                    cf_rows.append([add_cf(build_prompt(probe, q, perm, self.system, labels), pids)
                                    for probe in self.cf_probes])
            for si, st in enumerate(state_texts):
                real_rows = [add(build_prompt(st, q, perm, self.system, labels), pids)
                             for perm, pids in zip(perms, perm_ids)]
                plan[(si, qi)] = (perms, real_rows, cf_rows)

        # 2. score every prompt: shared-prefix groups where the backend supports it, flat otherwise.
        #    Real states and content-free probes are scored in separate calls (see step 1).
        def ordered(index: Dict[str, int]) -> List[str]:
            prompts = [None] * len(index)
            for text, i in index.items():
                prompts[i] = text
            return prompts

        logprobs = self._score(ordered(prompt_index), prompt_ids, prompt_parts)
        cf_logprobs = self._score(ordered(cf_index), cf_ids, cf_parts) if cf_index else []

        # 3. per question: raw position-space distributions, priors
        out: Dict[tuple, Decision] = {}
        for qi, q in enumerate(questions):
            perms, _, cf_rows = plan[(0, qi)]
            p_pos_raw_all = []
            for si in range(len(states)):
                lp_real = np.stack([logprobs[r] for r in plan[(si, qi)][1]])   # [P, K]
                p_pos_raw_all.append((lp_real, np.stack([_softmax(lp) for lp in lp_real])))

            cf_prior = None
            if want_cf:
                if cf_rows:
                    self._cf_cache[q.key] = np.stack([
                        content_free_prior(np.stack([_softmax(cf_logprobs[r]) for r in rows]))
                        for rows in cf_rows])                                      # [P, K]
                cf_prior = self._cf_cache[q.key]
            prior_used = b_prior = None
            if level != "raw":
                stack = np.stack([p for _, p in p_pos_raw_all])                    # [N, P, K]
                s, n = self._running.get(q.key, (np.zeros(stack.shape[1:]), 0))
                self._running[q.key] = (s + stack.sum(axis=0), n + len(stack))
                b_prior = self.running_prior(q)
                if self.prior == "batch":
                    prior_used = b_prior
                elif self.prior == "content_free":
                    prior_used = cf_prior

            # 4. assemble per state
            for si, (lp_real, p_pos_raw) in enumerate(p_pos_raw_all):
                answer_mass = float(np.exp(lp_real).sum(axis=1).mean())
                raw_probs = marginalize(p_pos_raw[:1], perms[:1])
                diag: Dict[str, Any] = {"answer_mass": answer_mass, "raw_probs": raw_probs,
                                        "permutations": len(perms), "perms": perms,
                                        "p_pos_raw": p_pos_raw}
                if level == "raw":
                    probs, achieved = raw_probs, "raw"
                else:
                    strength = self.strength()
                    p_pos = (apply_contextual(p_pos_raw, np.power(prior_used, strength))
                             if prior_used is not None else p_pos_raw)
                    probs = marginalize(p_pos, perms, self.combine)
                    achieved = "L0"
                    diag.update({
                        "prior_method": self.prior if prior_used is not None else "none",
                        "prior_strength": strength if prior_used is not None else 0.0,
                        "prior": prior_used,
                        "cf_prior": cf_prior,
                        "batch_prior": b_prior,
                        "order_flip_raw": flip_rate_across_perms(p_pos_raw, perms),
                        "order_flip_l0": flip_rate_across_perms(p_pos, perms),
                        "l0_probs": probs,
                    })
                out[(si, qi)] = Decision(q, np.asarray(probs), achieved, diag)
        return out
