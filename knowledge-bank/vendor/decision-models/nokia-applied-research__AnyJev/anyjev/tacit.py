"""Tacit: AnyJev's self-distilled decision models, one forward per decision, with optional escalation
of the least confident decisions to the model's own reasoning.

    from anyjev import Tacit

    tacit = Tacit.from_pretrained("morriszjm/Tacit-9B")                     # one forward per decision
    tacit = Tacit.from_pretrained("morriszjm/Tacit-9B", adaptive=True)      # + reasoning when unsure
    d = tacit.decide(state="Customer: my package was due last Monday and it still has not arrived.",
                     question="What does the customer want?",
                     options=["track_order", "cancel_order", "refund", "change_address"])
    d["answer"], d["probs"], d["route"]          # "track_order", {...}, "one_forward" or "cot"

One forward is AnyJev's own readout (`anyjev.readout`): the prompt the models were trained with,
read once in the order the options are given, and the next-token distribution renormalised over the
option labels. Nothing is generated.

`adaptive=True`: a decision whose margin (log-probability gap between its top two options) is below
`tau` is asked again with the model's thinking on. The reasoning stops at `</think>`, "Answer:" is
appended, and the answer is read the same way, so an escalated decision also carries probabilities
and cannot fail to parse. Every escalation is reported (`route == "cot"`, with the first pass kept
under `first_pass`); nothing is generated unless `adaptive` is on. `max_cot_share` caps the share of
the last `cot_window` decisions that may be escalated (rounded up), so traffic cannot drift into
reasoning on a model that serves for days; `cot_window=None` counts every decision since loading and
`max_cot_share=None` removes the cap.

Engines: "transformers" (default), "vllm" (in this process), "server" (a running `vllm serve`,
reached over its OpenAI-compatible API; the client loads only the tokenizer).
"""
from __future__ import annotations

import collections
import importlib
import importlib.util
import json
import math
import os
import shutil
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from anyjev.question import Question
from anyjev.readout import (
    DEFAULT_SYSTEM,
    build_prompt,
    label_ids_for_perm,
    map_label_tokens,
    render_chat,
    resolve_labels,
)

COT_SYSTEM = "You are a careful assistant that answers questions about a given context."
KINDS = {"choice": "choice", "yes_no": "noul", "noul": "noul", "score": "score"}


def restricted_logprobs(values: Sequence[float]) -> np.ndarray:
    """Log-softmax over the option labels only; a label with no value counts as probability 0."""
    z = np.asarray(values, dtype=np.float64)
    if not np.isfinite(z).any():
        z = np.zeros_like(z)
    m = np.max(z[np.isfinite(z)])
    return z - (m + np.log(np.sum(np.exp(z - m))))


def make_question(question: str, options: Optional[Sequence[str]], kind: str) -> Question:
    """The AnyJev `Question` for a Tacit request: "choice", "yes_no" (or "noul"), or "score" with
    `options` as ordered levels, lowest first."""
    k = KINDS.get(kind)
    if k is None:
        raise ValueError("kind must be one of %s" % sorted(KINDS))
    if k == "noul":
        return Question.noul(str(question))
    opts = [str(o) for o in (options or [])]
    if len(opts) < 2 or len(set(opts)) != len(opts):
        raise ValueError("need at least two distinct options")
    if k == "score":
        return Question.score(str(question), levels=opts)
    return Question.choice(str(question), opts)


def cot_user(state: str, q: Question, labels: Sequence[str]) -> str:
    """The prompt an escalated decision reasons on, ending with the line it answers in."""
    parts = [state.strip(), "", "Question: " + q.text.strip(), ""]
    if q.kind == "noul":
        parts.append("Answer Yes or No.")
        form = "Answer: Yes  or  Answer: No"
    elif q.kind == "score":
        parts += ["Levels:"] + ["%s. %s" % (labels[j], o) for j, o in enumerate(q.options)]
        form = "Answer: <level number>"
    else:
        parts += ["Options:"] + ["%s. %s" % (labels[j], o) for j, o in enumerate(q.options)]
        form = "Answer: <option letter>"
    parts += ["", "Think through the question, then give your final answer on the last line in "
                  "exactly this form:", form]
    return "\n".join(parts)


def _render_thinking(tok, system: str, user: str) -> str:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if not getattr(tok, "chat_template", None):
        return "%s\n\n%s\n" % (system, user)
    try:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=True)
    except TypeError:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def _spaced_label_ids(tok, labels: Sequence[str]) -> List[int]:
    """Label token ids after "Answer:", where the label follows a space."""
    ids = []
    for lab in labels:
        for cand in (" " + lab, lab):
            t = tok.encode(cand, add_special_tokens=False)
            if len(t) == 1:
                ids.append(t[0])
                break
        else:
            raise ValueError("label %r is not a single token for this tokenizer" % lab)
    if len(set(ids)) != len(ids):
        raise ValueError("label tokens collide")
    return ids


def _close_thought(text: str) -> str:
    """The reasoning up to and including </think>; closed by hand when the budget ran out."""
    if "</think>" in text:
        return text[: text.index("</think>") + len("</think>")]
    return text + "\n</think>"


# ---------------------------------------------------------------------- engines
class TransformersEngine:
    def __init__(self, model, tok):
        self.model, self.tok = model, tok

    def read(self, texts: List[str], label_ids: List[List[int]]) -> List[np.ndarray]:
        import torch
        enc = self.tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(self.model.device)
        with torch.no_grad():
            try:                                         # only the last position is read
                logits = self.model(**enc, logits_to_keep=1).logits[:, -1, :].float()
            except TypeError:
                logits = self.model(**enc).logits[:, -1, :].float()
        rows = logits.cpu().numpy()
        return [restricted_logprobs(rows[b, ids]) for b, ids in enumerate(label_ids)]

    def reason_read(self, prompts: List[str], label_ids: List[List[int]], max_tokens: int,
                    sampling: Dict[str, Any]) -> List[Tuple[np.ndarray, int]]:
        import torch
        out = []
        for prompt, ids in zip(prompts, label_ids):
            enc = self.tok(prompt, return_tensors="pt", add_special_tokens=False).to(self.model.device)
            with torch.no_grad():
                gen = self.model.generate(**enc, max_new_tokens=max_tokens, do_sample=True, stop_strings=["</think>"],
                                          tokenizer=self.tok, pad_token_id=self.tok.pad_token_id, **sampling)
            new = gen[0, enc["input_ids"].shape[1]:]
            thought = self.tok.decode(new, skip_special_tokens=False)
            for eos in (self.tok.eos_token or "", "<|im_end|>", "<|endoftext|>"):
                if eos and thought.endswith(eos):
                    thought = thought[: -len(eos)]
            out.append((self.read([prompt + _close_thought(thought) + "\n\nAnswer:"], [ids])[0], int(new.shape[0])))
        return out


class VLLMEngine:
    """vLLM in this process. The labels are read from the top `logprobs` log-probabilities of the full
    vocabulary (faster than restricting the vocabulary, and the same answers)."""

    def __init__(self, llm, tok, logprobs: int = 20):
        self.llm, self.tok, self.k = llm, tok, logprobs

    def _ids(self, text: str) -> List[int]:
        return self.tok(text, add_special_tokens=False).input_ids

    def _read_ids(self, prompts_ids: List[List[int]], label_ids: List[List[int]]) -> List[np.ndarray]:
        SamplingParams = importlib.import_module("vllm").SamplingParams
        sp = SamplingParams(max_tokens=1, temperature=0.0, logprobs=self.k)
        outs = self.llm.generate([{"prompt_token_ids": p} for p in prompts_ids], sp, use_tqdm=False)
        res = []
        for o, ids in zip(outs, label_ids):
            lp = o.outputs[0].logprobs[0]
            res.append(restricted_logprobs([lp[t].logprob if t in lp else -math.inf for t in ids]))
        return res

    def read(self, texts: List[str], label_ids: List[List[int]]) -> List[np.ndarray]:
        return self._read_ids([self._ids(t) for t in texts], label_ids)

    def reason_read(self, prompts: List[str], label_ids: List[List[int]], max_tokens: int,
                    sampling: Dict[str, Any]) -> List[Tuple[np.ndarray, int]]:
        SamplingParams = importlib.import_module("vllm").SamplingParams
        sp = SamplingParams(max_tokens=max_tokens, stop=["</think>"], include_stop_str_in_output=True, **sampling)
        pids = [self._ids(p) for p in prompts]
        outs = self.llm.generate([{"prompt_token_ids": p} for p in pids], sp, use_tqdm=False)
        tail, close = self._ids("\n\nAnswer:"), self._ids("\n</think>")
        reads, ntok = [], []
        for p, o in zip(pids, outs):
            gen = list(o.outputs[0].token_ids)
            closed = "</think>" in o.outputs[0].text
            reads.append(p + gen + ([] if closed else close) + tail)
            ntok.append(len(gen))
        return list(zip(self._read_ids(reads, label_ids), ntok))


class ServerEngine:
    """A running `vllm serve` (OpenAI-compatible /v1/completions). Prompts go as token ids, label
    log-probabilities come back keyed by token id (`return_tokens_as_token_ids`), and one request
    carries a whole batch, which the server schedules in parallel. `base_url` may be the server root
    or its /v1 URL."""

    def __init__(self, base_url: str, model: str, tok, api_key: Optional[str] = None, logprobs: int = 20,
                 timeout: float = 3600.0):
        root = base_url.rstrip("/")
        self.url = (root if root.endswith("/v1") else root + "/v1") + "/completions"
        self.model, self.tok, self.k, self.timeout = model, tok, logprobs, timeout
        self.api_key = api_key or os.environ.get("TACIT_API_KEY") or os.environ.get("OPENAI_API_KEY")

    def _ids(self, text: str) -> List[int]:
        return self.tok(text, add_special_tokens=False).input_ids

    def _complete(self, prompts_ids: List[List[int]], **params) -> List[Dict[str, Any]]:
        body = json.dumps(dict(model=self.model, prompt=prompts_ids, **params)).encode()
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", "Bearer " + self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                choices = json.loads(r.read())["choices"]
        except urllib.error.HTTPError as e:
            raise RuntimeError("vLLM server %s: %s %s" % (self.url, e.code, e.read()[:500])) from None
        return sorted(choices, key=lambda c: c["index"])

    def _read_ids(self, prompts_ids: List[List[int]], label_ids: List[List[int]]) -> List[np.ndarray]:
        choices = self._complete(prompts_ids, max_tokens=1, temperature=0.0, logprobs=self.k,
                                 return_tokens_as_token_ids=True)
        res = []
        for c, ids in zip(choices, label_ids):
            top = c["logprobs"]["top_logprobs"][0] or {}
            lp = {int(k.split(":", 1)[1]): v for k, v in top.items() if k.startswith("token_id:")}
            res.append(restricted_logprobs([lp.get(t, -math.inf) for t in ids]))
        return res

    def read(self, texts: List[str], label_ids: List[List[int]]) -> List[np.ndarray]:
        return self._read_ids([self._ids(t) for t in texts], label_ids)

    def reason_read(self, prompts: List[str], label_ids: List[List[int]], max_tokens: int,
                    sampling: Dict[str, Any]) -> List[Tuple[np.ndarray, int]]:
        choices = self._complete([self._ids(p) for p in prompts], max_tokens=max_tokens, stop=["</think>"],
                                 include_stop_str_in_output=True, skip_special_tokens=False, **sampling)
        texts = [p + _close_thought(c["text"]) + "\n\nAnswer:" for p, c in zip(prompts, choices)]
        ntok = [len(self._ids(c["text"])) for c in choices]
        return list(zip(self.read(texts, label_ids), ntok))


def _needs_native_gdn(repo: str) -> bool:
    """Qwen3.5 (gated delta rule) on a machine where vLLM's default kernel cannot be compiled."""
    try:                                             # config.json itself: older transformers do not know qwen3_5
        if os.path.isdir(repo):
            path = os.path.join(repo, "config.json")
        else:
            from huggingface_hub import hf_hub_download
            path = hf_hub_download(repo, "config.json")
        with open(path) as f:
            cfg = json.load(f)
        mt = str(cfg.get("model_type", "")) + str((cfg.get("text_config") or {}).get("model_type", ""))
    except Exception:
        return False
    cuda = os.environ.get("CUDA_HOME", "/usr/local/cuda")
    has_nvcc = shutil.which("nvcc") or os.path.exists(os.path.join(cuda, "bin", "nvcc"))
    return "qwen3_5" in mt and not has_nvcc


def _patch_native_gdn() -> None:
    os.environ["VLLM_ENABLE_V1_MULTIPROCESSING"] = "0"     # the patch must reach the engine: run it here
    cls = importlib.import_module("vllm.model_executor.models.qwen3_next").ChunkGatedDeltaRule
    if getattr(cls, "_tacit_native", False):
        return
    init = cls.__init__

    def native_init(self, *a, **kw):
        init(self, *a, **kw)
        self._forward_method = self.forward_native
    cls.__init__ = native_init
    cls._tacit_native = True


# ---------------------------------------------------------------------- the decision API
class Tacit:
    def __init__(self, engine, tokenizer, *, adaptive: bool = False, tau: float = 0.5,
                 max_cot_share: Optional[float] = 0.2, cot_window: Optional[int] = 1000, cot_max_tokens: int = 8192,
                 temperature: float = 0.6, top_p: float = 0.95, top_k: int = 20, batch_size: int = 8,
                 system: str = DEFAULT_SYSTEM):
        if max_cot_share is not None and not 0.0 <= max_cot_share <= 1.0:
            raise ValueError("max_cot_share must be between 0 and 1, or None")
        if cot_window is not None and cot_window < 1:
            raise ValueError("cot_window must be at least 1, or None")
        self.engine, self.tok = engine, tokenizer
        self.adaptive, self.tau, self.max_cot_share = adaptive, tau, max_cot_share
        self.cot_window = cot_window
        self._recent = collections.deque(maxlen=cot_window) if cot_window else None
        self.cot_max_tokens, self.batch_size, self.system = cot_max_tokens, batch_size, system
        self.sampling = dict(temperature=temperature, top_p=top_p, top_k=top_k)
        if getattr(self.tok, "padding_side", None) is not None:
            self.tok.padding_side = "left"
        if getattr(self.tok, "pad_token", "") is None:
            self.tok.pad_token = self.tok.eos_token
        self.decisions = 0
        self.escalated = 0
        self._lock = threading.Lock()                    # the cap's bookkeeping, shared by concurrent callers

    @classmethod
    def from_pretrained(cls, repo: str, *, engine: str = "transformers", dtype: str = "bfloat16",
                        device_map: Optional[str] = "auto", vllm_kwargs: Optional[Dict[str, Any]] = None,
                        logprobs: int = 20, native_gdn: Optional[bool] = None, base_url: Optional[str] = None,
                        api_key: Optional[str] = None, served_model: Optional[str] = None, **kwargs) -> "Tacit":
        """engine: "transformers" (default), "vllm" (vLLM in this process; `vllm_kwargs` go to
        `vllm.LLM`) or "server" (a running `vllm serve` at `base_url`, its root or /v1 URL).
        The other keyword arguments go to `Tacit` (adaptive, tau, max_cot_share, cot_window, ...)."""
        if engine == "server":
            from transformers import AutoTokenizer
            if not base_url:
                raise ValueError('engine="server" needs base_url, e.g. "http://127.0.0.1:8000"')
            tok = AutoTokenizer.from_pretrained(repo)
            kwargs.setdefault("batch_size", 1 << 30)
            return cls(ServerEngine(base_url, served_model or repo, tok, api_key, logprobs), tok, **kwargs)
        if engine == "vllm":
            # the engine runs in this process unless the caller says otherwise: a spawned engine
            # re-imports the calling script, which breaks scripts without a __main__ guard and notebooks
            os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
            if native_gdn or (native_gdn is None and _needs_native_gdn(repo)):
                _patch_native_gdn()
            llm_cls = importlib.import_module("vllm").LLM
            vk = dict(dtype=dtype, max_model_len=32768, max_logprobs=max(20, logprobs))
            vk.update(vllm_kwargs or {})
            llm = llm_cls(model=repo, **vk)
            tok = llm.get_tokenizer()
            kwargs.setdefault("batch_size", 1 << 30)       # vLLM batches internally
            return cls(VLLMEngine(llm, tok, logprobs), tok, **kwargs)
        if engine != "transformers":
            raise ValueError('engine must be "transformers", "vllm" or "server"')
        import torch
        import transformers
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(repo)
        if device_map is not None and importlib.util.find_spec("accelerate") is None:
            device_map = None                            # device_map needs accelerate; place the model by hand
        # transformers 5 renamed `torch_dtype` to `dtype`; an older release would drop `dtype` silently
        dtype_kw = "dtype" if int(transformers.__version__.split(".")[0]) >= 5 else "torch_dtype"
        model = AutoModelForCausalLM.from_pretrained(repo, device_map=device_map, **{dtype_kw: getattr(torch, dtype)})
        if device_map is None and torch.cuda.is_available():
            model = model.to("cuda")
        model.eval()
        return cls(TransformersEngine(model, tok), tok, **kwargs)

    # ------------------------------------------------------------------ public API
    def decide(self, state: str, question: str, options: Optional[Sequence[str]] = None,
               kind: str = "choice", first_level: int = 1) -> Dict[str, Any]:
        """One decision. kind: "choice" (pick one of `options`), "yes_no", or "score" (`options` are
        ordered levels, lowest first, numbered from `first_level`: 1 by default, 0 for a rubric that
        counts from 0)."""
        return self.decide_batch([dict(state=state, question=question, options=options, kind=kind,
                                       first_level=first_level)])[0]

    def decide_batch(self, items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Each item: dict(state=..., question=..., options=[...], kind=...). Within a batch the least
        confident decisions are escalated first."""
        norm = [self._normalise(it) for it in items]
        out: List[Dict[str, Any]] = []
        for i in range(0, len(norm), self.batch_size):
            chunk = norm[i:i + self.batch_size]
            texts = [render_chat(self.tok, build_prompt(it["state"], it["q"], list(range(it["q"].k)),
                                                        self.system, it["labels"])) for it in chunk]
            logps = self.engine.read(texts, [it["ids"] for it in chunk])
            out += [self._result(it, lp, "one_forward") for it, lp in zip(chunk, logps)]
        # which decisions escalate is settled and booked under the lock; the reasoning itself runs
        # outside it, so concurrent callers (the gateway's threads) share one cap without waiting
        with self._lock:
            chosen: List[int] = []
            if self.adaptive:
                want = sorted((i for i, d in enumerate(out) if d["margin"] < self.tau), key=lambda i: out[i]["margin"])
                chosen = want[:self._budget(len(out), len(want))]
                self.escalated += len(chosen)
            self.decisions += len(out)
            if self._recent is not None:
                picked = set(chosen)
                self._recent.extend(i in picked for i in range(len(out)))
        if chosen:
            prompts = [_render_thinking(self.tok, COT_SYSTEM,
                                        cot_user(norm[i]["state"], norm[i]["q"], norm[i]["labels"])) for i in chosen]
            reads = self.engine.reason_read(prompts, [_spaced_label_ids(self.tok, norm[i]["labels"]) for i in chosen],
                                            self.cot_max_tokens, self.sampling)
            for i, (lp, n) in zip(chosen, reads):
                out[i] = self._result(norm[i], lp, "cot", first_pass=out[i], reasoning_tokens=n)
        return out

    @property
    def stats(self) -> Dict[str, Any]:
        s = {"decisions": self.decisions, "escalated": self.escalated,
             "cot_share": self.escalated / self.decisions if self.decisions else 0.0}
        if self._recent is not None:
            s["window_cot_share"] = sum(self._recent) / len(self._recent) if self._recent else 0.0
        return s

    # ------------------------------------------------------------------ internals
    def _budget(self, n_new: int, n_want: int) -> int:
        """How many of `n_new` new decisions may be escalated. With `cot_window`, escalations among the
        last `cot_window` decisions (these included) stay at or below `max_cot_share` of them, rounded
        up: unused budget does not pile up over a long run, and a burst of hard traffic gets the same
        share as any other stretch. Without it, the share counts every decision since loading."""
        if self.max_cot_share is None:
            return n_want
        if self._recent is None:
            return max(0, math.ceil(self.max_cot_share * (self.decisions + n_new) - 1e-9) - self.escalated)
        W = self._recent.maxlen
        if n_new >= W:                                   # the batch alone fills the window
            return math.ceil(self.max_cot_share * n_new - 1e-9)
        old = list(self._recent)[max(0, len(self._recent) + n_new - W):]   # what stays in the window
        return max(0, math.ceil(self.max_cot_share * (len(old) + n_new) - 1e-9) - sum(old))

    def _normalise(self, it: Dict[str, Any]) -> Dict[str, Any]:
        if "question" not in it:
            raise ValueError("a decision needs a question")
        q = make_question(it["question"], it.get("options"), it.get("kind", "choice"))
        first = it.get("first_level", 1)
        if first not in (0, 1):
            raise ValueError("first_level must be 0 or 1")
        if q.kind == "score" and first == 0:
            # levels shown and read as 0..K-1, for rubrics that number them that way
            labels = [str(j) for j in range(q.k)]
            ids = map_label_tokens(self.tok, labels)
        else:
            labels, ids = resolve_labels(self.tok, q)
        return dict(state=str(it.get("state", "")), q=q, labels=labels,
                    ids=label_ids_for_perm(q, ids, list(range(q.k))))

    @staticmethod
    def _result(it: Dict[str, Any], logp: np.ndarray, route: str, **extra) -> Dict[str, Any]:
        logp = np.asarray(logp, dtype=np.float64)
        p = np.exp(logp)
        order = np.argsort(-logp)
        j = int(order[0])
        second = float(logp[order[1]]) if len(order) > 1 else -math.inf
        margin = float(logp[j] - second) if math.isfinite(second) else float("inf")
        options = list(it["q"].options)
        return dict(answer=options[j], index=j, probs={o: float(p[i]) for i, o in enumerate(options)},
                    margin=margin, route=route, **extra)
