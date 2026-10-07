"""Open-Jev-owned final-row fusion; no third-party source copied."""
import torch
import triton
import triton.language as tl


@triton.jit
def _final_tail(H, D, R, W, HW, HB, O, N: tl.constexpr, WIDTH: tl.constexpr,
                EPS: tl.constexpr, HAS_DELTA: tl.constexpr,
                MULTIPLIER: tl.constexpr, BLOCK: tl.constexpr):
    batch = tl.program_id(0)
    row = tl.load(R + batch)
    columns = tl.arange(0, BLOCK)
    valid_row = (row >= 0) & (row < N)
    mask = (columns < WIDTH) & valid_row
    x = tl.load(H + row * WIDTH + columns, mask=mask, other=0).to(tl.float32)
    if HAS_DELTA:
        delta = tl.load(D + row * WIDTH + columns, mask=mask, other=0).to(tl.float32)
        x = (x + delta).to(H.dtype.element_ty).to(tl.float32)
    variance = tl.sum(x * x, 0) / WIDTH
    inverse = tl.rsqrt(variance + EPS)
    weight = tl.load(W + columns, mask=columns < WIDTH, other=0)
    if not MULTIPLIER:
        weight = 1.0 + weight
    normalized = ((x * inverse) * weight).to(H.dtype.element_ty).to(tl.float32)
    head = tl.load(HW + columns, mask=columns < WIDTH, other=0)
    score = tl.sum(normalized * head, 0) + tl.load(HB)
    tl.store(O + batch, tl.where(valid_row, score, float("nan")))


def launch(hidden, rows, norm_weight, head_weight, head_bias, eps, delta, multiplier):
    output = torch.empty(rows.numel(), dtype=torch.float32, device=hidden.device)
    width = hidden.shape[1]
    _final_tail[(rows.numel(),)](
        hidden, hidden if delta is None else delta, rows, norm_weight,
        head_weight, head_bias, output, hidden.shape[0], width, eps,
        delta is not None, multiplier, triton.next_power_of_2(width),
        num_warps=4 if width <= 4096 else 8, enable_fp_fusion=False)
    return output
