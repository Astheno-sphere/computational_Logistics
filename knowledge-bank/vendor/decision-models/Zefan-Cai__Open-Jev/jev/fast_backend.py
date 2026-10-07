"""Explicit experimental inference backends; the default scorer is unchanged."""
import gc
import threading

from .api import candidate_prompts


UPSTREAM_COMMIT = "c52b8bb958c1f0d241d4eb7fce4ecd8d885bf1e4"
PROFILES = {
    "Qwen/Qwen3.5-2B": (2048, 24, 6144, 8, 2, 16, 16),
    "Qwen/Qwen3.5-9B": (4096, 32, 12288, 16, 4, 16, 32),
    "Qwen/Qwen3.8-27B": (5120, 64, 17408, 24, 4, 16, 48),
}
PROFILE_FIELDS = ("hidden_size", "num_hidden_layers", "intermediate_size",
                  "num_attention_heads", "num_key_value_heads",
                  "linear_num_key_heads", "linear_num_value_heads")


def validate_profile(model_id, config, backend):
    if backend not in ("triton-tail", "fast-cuda"):
        raise ValueError("unknown fast backend")
    if model_id not in PROFILES or config.model_type != "qwen3_5_text":
        raise ValueError("fast inference requires an explicit released Qwen 2B/9B/27B profile")
    actual = tuple(getattr(config, field, None) for field in PROFILE_FIELDS)
    if actual != PROFILES[model_id]:
        raise ValueError("model configuration differs from the selected fast profile")
    if (config.head_dim != 256 or config.linear_key_head_dim != 128
            or config.linear_value_head_dim != 128
            or list(config.layer_types) != ["full_attention" if i % 4 == 3 else "linear_attention"
                                          for i in range(config.num_hidden_layers)]):
        raise ValueError("unsupported hybrid attention layout")
    if backend == "fast-cuda" and model_id != "Qwen/Qwen3.8-27B":
        raise ValueError("the vendored tree CUDA kernels are restricted to the 27B profile; use triton-tail for 2B/9B")
    return {"model_id": model_id, "backend": backend, "hidden_size": config.hidden_size,
            "experimental": True, "upstream_commit": UPSTREAM_COMMIT if backend == "fast-cuda" else None}


def release_copied_layer(layer, kind):
    """Drop only source projections already copied into owned merged tensors.

    This transfers inference ownership. Calling the source layer again after
    transfer is intentionally invalid; aliases for output projections survive.
    """
    if kind not in ("linear_attention", "full_attention"):
        raise ValueError("unsupported layer ownership transfer")
    del layer.mlp.gate_proj, layer.mlp.up_proj
    if kind == "linear_attention":
        attention = layer.linear_attn
        del attention.in_proj_qkv, attention.in_proj_z, attention.in_proj_b, attention.in_proj_a
    else:
        attention = layer.self_attn
        del attention.q_proj, attention.k_proj, attention.v_proj


def packed_tree_rows(sequences, groups):
    """Preflight the exact upstream packed row count before dense masks allocate."""
    if not sequences or len(sequences) != len(groups) or any(not s for s in sequences):
        raise ValueError("tree requires nonempty sequences and matching groups")
    if set(groups) != set(range(max(groups) + 1)):
        raise ValueError("tree groups must be contiguous nonnegative integers")

    def lcp(rows, start=0):
        limit = min(map(len, rows)) - 1
        for i in range(start, limit):
            if any(row[i] != rows[0][i] for row in rows[1:]):
                return i
        return limit

    root = lcp(sequences)
    prefixes = [lcp([s for s, g in zip(sequences, groups) if g == group], root) - root
                for group in range(max(groups) + 1)]
    count = root + sum(prefixes) + sum(len(s) - root - prefixes[g] for s, g in zip(sequences, groups))
    return ((count + 31) // 32) * 32


def _encode(model, records):
    if not records:
        raise ValueError("fast scoring requires at least one record")
    prompts, counts, groups = [], [], []
    for group, record in enumerate(records):
        entries = candidate_prompts(record)
        counts.append(len(entries))
        groups.extend([group] * len(entries))
        prompts.extend(model.tokenizer.apply_chat_template(
            [{"role": "user", "content": p}], tokenize=False,
            add_generation_prompt=True, enable_thinking=False) for p in entries)
    encoded = model.tokenizer(prompts, padding=False, truncation=False)["input_ids"]
    lengths = list(map(len, encoded))
    if any(not n for n in lengths) or max(lengths) > model.max_length:
        raise ValueError("input exceeds fast backend max_length; no silent truncation")
    return encoded, counts, groups


def _rows(scores, records, counts):
    import torch
    values, offset = [], 0
    for record, count in zip(records, counts):
        row = scores[offset:offset + count]
        if record["kind"] == "noul":
            row = torch.stack((torch.zeros_like(row[0]), row[0]))
        values.append(row.float().cpu().tolist())
        offset += count
    return values


class FastScorer:
    def __init__(self, model, backend, *, fused_head=True):
        import torch
        from torch import nn
        from .kernels.final_score import final_rms_head
        self.model, self.backend, self.fused_head = model, backend, fused_head
        self.lock = threading.Lock()
        core = model.backbone.get_base_model() if hasattr(model.backbone, "get_base_model") else model.backbone
        self.provenance = validate_profile(model.model_id, core.config, backend)
        device = torch.device(model.device_name)
        if device.type != "cuda" or not torch.cuda.is_available():
            raise RuntimeError("selected fast backend requires CUDA")
        required = 9 if backend == "fast-cuda" else 8
        if torch.cuda.get_device_capability(device)[0] < required:
            raise RuntimeError(f"selected fast backend requires sm{required}0+")
        if any(p.device != device or (p.dtype != torch.bfloat16
                                      and not (".lora_" in "." + name and p.dtype == torch.float32))
               for name, p in core.named_parameters()):
            raise ValueError("fast inference requires a fully resident single-device BF16 backbone")
        if any(p.device != device or p.dtype != torch.float32 for p in model.head.parameters()):
            raise ValueError("fast inference requires a resident FP32 decision head")
        self.final_score = final_rms_head
        if backend == "triton-tail":
            if not fused_head:
                raise ValueError("triton-tail always uses the fused head")
            self.norm_weight = core.norm.weight.detach().float().contiguous()
            self.eps = core.config.rms_norm_eps
            core.norm = nn.Identity()
        else:
            if hasattr(model.backbone, "merge_and_unload"):
                core = model.backbone.merge_and_unload(safe_merge=True)
            from third_party.open_jev_fast.src.fastmodel import FastQwen35
            with torch.cuda.device(device):
                fast = FastQwen35(core, free_original=True).eval()
            model.backbone = fast
            del core
            gc.collect()
            torch.cuda.empty_cache()
            self.provenance.update(low_memory=True, split_k=1, cuda_graphs=False,
                                   fused_final_head=fused_head, max_packed_rows=4096,
                                   max_replicated_tokens=65536)

    def score(self, records):
        import torch
        with self.lock, torch.inference_mode(), torch.cuda.device(self.model.device_name):
            sequences, counts, groups = _encode(self.model, records)
            self.model.last_input_tokens = sum(map(len, sequences))
            device = self.model.device_name
            if self.backend == "triton-tail":
                width = max(map(len, sequences))
                ids = torch.tensor([s + [self.model.tokenizer.pad_token_id] * (width - len(s)) for s in sequences],
                                   dtype=torch.long, device=device)
                lengths = torch.tensor(list(map(len, sequences)), device=device)
                mask = (torch.arange(width, device=device)[None, :] < lengths[:, None]).long()
                hidden = self.model.backbone(input_ids=ids, attention_mask=mask,
                                             use_cache=False, return_dict=True).last_hidden_state
                indices = torch.arange(len(sequences), device=device) * width + lengths - 1
                scores = self.final_score(hidden.reshape(-1, hidden.shape[-1]).contiguous(),
                                          indices.contiguous(), self.norm_weight,
                                          self.model.head.weight, self.model.head.bias, eps=self.eps)
            else:
                rows = packed_tree_rows(sequences, groups)
                replicated = len(sequences) * ((max(map(len, sequences)) + 15) // 16) * 16
                if rows > 4096 or replicated > 65536:
                    raise ValueError("fast tree exceeds explicit packed/replicated memory limits; no fallback")
                fast = self.model.backbone
                ids, layout = fast.gtree_build(sequences, groups, self.model.tokenizer.pad_token_id, dev=device)
                output = fast.forward_gtree(ids, layout, head=self.model.head if self.fused_head else None)
                scores = output if self.fused_head else self.model.head(output.float()).squeeze(-1)
            return _rows(scores, records, counts), self.model.last_input_tokens


def enable_fast_backend(predictor, backend, *, fused_head=True):
    """Transfer one newly loaded inference predictor to the selected backend."""
    if predictor.prefix_cache:
        raise ValueError("fast backend and HF prefix-cache are separate opt-ins; do not combine them")
    scorer = FastScorer(predictor.scorer.model, backend, fused_head=fused_head)
    predictor.scorer = scorer
    predictor.method += "+" + backend
    predictor.provenance.update(fast_backend=scorer.provenance)
    return predictor
