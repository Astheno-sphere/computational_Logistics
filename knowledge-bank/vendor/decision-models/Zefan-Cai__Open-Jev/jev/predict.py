"""Read one System One style JSON request and return calibrated typed decisions."""
import argparse
import json
from pathlib import Path

import torch

from .api import compile_request, format_response
from .metrics import softmax
from .model import DecisionModel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--output")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--backend", choices=("torch", "triton-tail", "fast-cuda"), default="torch")
    p.add_argument("--fused-final-head", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--prefix-cache", action=argparse.BooleanOptionalAction, default=False,
                   help="Enable token-prefix reuse; default off pending full-checkpoint BF16 validation")
    args = p.parse_args()
    request = json.loads(Path(args.request).read_text())
    if args.backend != "torch":
        from .serving import load_predictor
        predictor = load_predictor(checkpoint=args.checkpoint, device=args.device,
                                   batch_size=args.batch_size, prefix_cache=args.prefix_cache,
                                   backend=args.backend, fused_final_head=args.fused_final_head)
        rendered = json.dumps(predictor.predict(request), ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(rendered + "\n")
        print(rendered)
        return
    records = compile_request(request["state"], request["questions"])
    checkpoint = Path(args.checkpoint)
    temperature = json.loads((checkpoint / "temperature.json").read_text())["temperature"]
    model = DecisionModel.load(checkpoint, device=args.device)
    with torch.inference_mode():
        if args.prefix_cache:
            logits, cache_stats = model.score_cached(records, batch_size=args.batch_size)
        else:
            logits = model(records)
    probs = [softmax(row.float().cpu().tolist(), temperature=temperature) for row in logits]
    result = format_response(records, probs)
    if args.prefix_cache:
        result.update(usage={"input_tokens": cache_stats["logical_input_tokens"], "output_tokens": 0},
                      metadata={"prefix_cache": cache_stats})
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
    print(rendered)


if __name__ == "__main__":
    main()
