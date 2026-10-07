"""Gather final rows, optional BF16 residual, RMSNorm and FP32 scalar head.

This Open-Jev kernel is independent of the vendored backbone. The normalization
rounds to the hidden dtype before the FP32 head, as the Qwen reference does.
"""
import math


def _validate(hidden, rows, norm_weight, head_weight, head_bias, eps, delta):
    import torch
    if (hidden.ndim != 2 or not hidden.is_contiguous() or hidden.shape[1] > 8192
            or hidden.shape[1] < 1 or hidden.dtype not in (torch.float32, torch.float16, torch.bfloat16)):
        raise ValueError("hidden must be contiguous [rows, hidden_size<=8192] floating point")
    width = hidden.shape[1]
    if (rows.ndim != 1 or not rows.numel() or rows.dtype != torch.int64
            or not rows.is_contiguous()):
        raise ValueError("final row indices must be nonempty contiguous int64")
    if norm_weight.shape != (width,) or head_weight.numel() != width or head_bias.numel() != 1:
        raise ValueError("RMSNorm/scalar head shape differs from hidden width")
    if any(v.device != hidden.device or not v.is_contiguous()
           for v in (rows, norm_weight, head_weight, head_bias)):
        raise ValueError("kernel inputs must be contiguous on one device")
    if any(v.dtype != torch.float32 for v in (norm_weight, head_weight, head_bias)):
        raise ValueError("RMSNorm weights and scalar head must be FP32")
    if not math.isfinite(eps) or eps <= 0:
        raise ValueError("RMSNorm epsilon must be finite and positive")
    if delta is not None and (delta.shape != hidden.shape or delta.device != hidden.device
                              or delta.dtype != hidden.dtype or not delta.is_contiguous()):
        raise ValueError("residual delta must match contiguous hidden states")


def reference_final_rms_head(hidden, rows, norm_weight, head_weight, head_bias,
                             *, eps=1e-6, delta=None, multiplier=False, validate_rows=True):
    """PyTorch numerical reference; valid on CPU and CUDA."""
    import torch
    _validate(hidden, rows, norm_weight, head_weight, head_bias, eps, delta)
    if validate_rows and (rows.min().item() < 0 or rows.max().item() >= hidden.shape[0]):
        raise ValueError("final row index outside hidden states")
    selected = hidden.index_select(0, rows)
    if delta is not None:
        selected = selected + delta.index_select(0, rows)
    x = selected.float()
    scale = norm_weight if multiplier else 1.0 + norm_weight
    normalized = (x * torch.rsqrt(x.square().mean(-1, keepdim=True) + eps)) * scale
    normalized = normalized.to(hidden.dtype).float()
    return torch.nn.functional.linear(normalized, head_weight.reshape(1, -1),
                                      head_bias.reshape(1)).squeeze(-1)


def final_rms_head(hidden, rows, norm_weight, head_weight, head_bias,
                   *, eps=1e-6, delta=None, multiplier=False):
    """Launch the CUDA Triton fusion. Never silently substitutes another path.

    Invalid device row indices produce NaN for the serving finite-logit guard;
    they cannot read outside the input allocation. No host sync is introduced.
    """
    import torch
    _validate(hidden, rows, norm_weight, head_weight, head_bias, eps, delta)
    if hidden.device.type != "cuda" or torch.cuda.get_device_capability(hidden.device)[0] < 8:
        raise RuntimeError("Triton final scoring requires an sm80+ CUDA GPU")
    try:
        from .triton_tail import launch
    except ImportError as error:
        raise RuntimeError("Triton is required for the selected final-scoring kernel") from error
    return launch(hidden, rows, norm_weight, head_weight, head_bias, eps, delta, multiplier)
