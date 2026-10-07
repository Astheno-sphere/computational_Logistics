"""vLLM backend over the OpenAI-compatible server.

Two server shapes, because vLLM gives one task per instance.

**raw / L0** -- a generate server. One request per prompt with `max_tokens=1`,
`allowed_token_ids` restricted to the label tokens and `logprobs=K`. vLLM reports
logprobs after its logit processors, so the K entries are exactly the labels,
normalized over them (checked on vLLM 0.17.1). A build that reports raw full-vocabulary
logprobs instead can leave a label out (seen on vllm-metal); the backend then raises
rather than guess, and `--logprobs-mode processed_logprobs` on the server fixes it.
Prefix caching makes the K permutations of one state cheap.

    vllm serve Qwen/Qwen3-8B --enable-prefix-caching
    Decider(VLLMBackend("http://localhost:8000", "Qwen/Qwen3-8B"))

**Hidden states** -- an embed server whose pooler is told to return the last position's hidden
state untouched (`hidden_states`). Served on a truncated checkpoint (`anyjev.truncate`), that is
the state of an intermediate block, read without the blocks above it.

    vllm serve ./qwen-b18 --task embed --enable-prefix-caching \
      --override-pooler-config '{"pooling_type":"LAST","normalize":false,"softmax":false}'

Measured against `transformers` on Qwen2.5-7B: cosine 0.9998 between the two vectors, the
difference being bf16 kernel choice. Only the server's **final** layer is available this way.

For the self-distilled Tacit models use `anyjev.Tacit(..., engine="server")`, which reads the
labels from the top log-probabilities and adds escalation to the model's own reasoning.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import urllib.request
from typing import List, Optional, Sequence

import numpy as np

from anyjev.readout import LabelTokenError


class VLLMBackend:
    def __init__(self, base_url: str, model: str, tokenizer_name: str | None = None,
                 api_key: str = "EMPTY", workers: int = 16, timeout: float = 120.0):
        from transformers import AutoTokenizer

        self.base_url = base_url.rstrip("/")
        self.name = model
        self.api_key = api_key
        self.workers = workers
        self.timeout = timeout
        # `model` is what the server answers to, which may be a `--served-model-name` alias;
        # the tokenizer and the config have to come from something loadable.
        self.source = tokenizer_name or model
        self.tokenizer = AutoTokenizer.from_pretrained(self.source)
        self._n_layers: int | None = None

    def _one(self, prompt: str, ids: Sequence[int]) -> np.ndarray:
        body = {
            "model": self.name, "prompt": prompt, "max_tokens": 1, "temperature": 0.0,
            "logprobs": len(ids), "allowed_token_ids": list(ids),
        }
        req = urllib.request.Request(
            self.base_url + "/v1/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        top = out["choices"][0]["logprobs"]["top_logprobs"][0]   # {token_str: logprob}
        # map back by token id: decode each id the same way the server renders it
        by_id = {}
        for tid in ids:
            tok = self.tokenizer.decode([tid])
            conv = self.tokenizer.convert_ids_to_tokens(tid)
            for key in (tok, conv):
                if key in top:
                    by_id[tid] = float(top[key])
                    break
        missing = [tid for tid in ids if tid not in by_id]
        if missing:
            raise LabelTokenError(
                f"the server returned no log-probability for label token ids {missing} (it returned "
                f"{sorted(top)}); start vLLM with --logprobs-mode processed_logprobs")
        return np.array([by_id[tid] for tid in ids], dtype=np.float64)

    def next_token_logprobs(self, prompts: Sequence[str],
                            token_ids: Sequence[Sequence[int]]) -> List[np.ndarray]:
        with cf.ThreadPoolExecutor(self.workers) as ex:
            return list(ex.map(self._one, prompts, token_ids))

    # ---- the last position's hidden state, from a pooling server ----------------------
    @property
    def n_layers(self) -> int:
        """The model's real block count, read from its config.

        A pooling server can only return the final layer, but it must still be *numbered* the
        way the local backend numbers it, or anything fitted on a layer stops being portable
        between the two."""
        if self._n_layers is None:
            from transformers import AutoConfig

            cfg = AutoConfig.from_pretrained(self.source)
            self._n_layers = int(getattr(cfg, "num_hidden_layers", 0))
        return self._n_layers

    def hidden_states(self, prompts: Sequence[str], layers: Optional[Sequence[int]] = None,
                      token_ids=None, positions=None):
        """(feats [N, 1, d], lps, None) from `/v1/embeddings`.

        `layers` may only name the single available layer (0, 1 or -1); anything else is an
        error rather than a silently substituted vector, because a reader fitted on block 24 and
        served on block 36 is a wrong answer with no symptom. `token_ids` is not served here:
        an embed server has no logits."""
        final = self.n_layers
        if layers is not None and any(int(x) not in (-1, final) for x in layers):
            raise ValueError(f"a vLLM pooling server serves only the final layer ({final}); "
                             f"asked for {list(layers)}.")
        if token_ids is not None:
            raise ValueError("an embed server returns no logits; use a generate server for raw / L0")
        if positions is not None:
            raise ValueError("a pooling server returns one vector per prompt, not per position")
        with cf.ThreadPoolExecutor(self.workers) as ex:
            vecs = list(ex.map(self._embed, prompts))
        feats = np.stack(vecs)[:, None, :].astype(np.float32)
        return feats, [None] * len(prompts), None

    def _embed(self, prompt: str) -> np.ndarray:
        body = {"model": self.name, "input": prompt, "encoding_format": "float"}
        req = urllib.request.Request(
            self.base_url + "/v1/embeddings", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        return np.asarray(out["data"][0]["embedding"], dtype=np.float32)
