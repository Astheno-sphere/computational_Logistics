# Usage guide

[简体中文](usage_zh.md) · [Back to README](../README.md)

This guide covers local Python usage, the HTTP service, and candidate submission modes. Complete [installation](installation.md) first. The examples use a local Hugging Face-compatible causal language model; replace `/path/to/model` with its directory.

## SGLang Python API

A `JevRequest` contains `state`, `model`, and `questions`. This example submits Choice, Score, and Noul questions together. The local SGLang backend defaults to staged submission:

```python
from llm2jev import Choice, JevRequest, LLM2Jev, Noul, Score, SGLangBackend

if __name__ == "__main__":
    model_path = "/path/to/model"
    request = JevRequest(
        model=model_path,
        state="My parcel arrived two weeks late, and my card was charged twice.",
        questions={
            "department": Choice(
                instructions="Which department should handle this request?",
                criteria={
                    "shipping": "Delivery problems",
                    "billing": "Charges and billing problems",
                    "returns": "Returns and exchanges",
                },
            ),
            "severity": Score(
                instructions="How severe is the problem?",
                criteria=["Low: minor impact", "Medium: impaired but usable", "High: unusable"],
            ),
            "delivery": Noul(
                instructions="Is this a delivery issue?",
            ),
        },
    )
    with SGLangBackend(model_path, submission="staged") as backend:
        response = LLM2Jev(backend=backend).evaluate(request)
        print(response.to_dict())
```

You can omit `submission="staged"`; specifying it makes the selected mode explicit. Keep the main guard because SGLang starts worker processes. For multiple requests, reuse the backend inside the same `with` block to avoid loading the model repeatedly.

The context manager shuts down the engine on exit. Pass SGLang engine options through `engine_kwargs`.

To submit all candidates together, use:

```python
with SGLangBackend(model_path, submission="all") as backend:
    response = LLM2Jev(backend=backend).evaluate(request)
```

The repository example supports both modes:

```bash
python examples/sglang_inference.py --model-path /path/to/model --submission staged
python examples/sglang_inference.py --model-path /path/to/model --submission all
```

## Transformers Backend

Run the example in the Transformers-only environment:

```bash
python examples/transformers_inference.py --model-path /path/to/model
```

Using `model_path` and `request` from the example above, replace the backend call with:

```python
from llm2jev import LLM2Jev, TransformersBackend

backend = TransformersBackend(model_path)
response = LLM2Jev(backend=backend).evaluate(request)
print(response.to_dict())
```

The Transformers backend uses CUDA when available and otherwise falls back to CPU.

## System One HTTP API

`llm2jev-serve` adds `POST /v1/systemone` to SGLang's native HTTP server.
SGLang continues to provide model listing, health checks, authentication, and
its other native endpoints.

```bash
export LLM2JEV_API_KEY="replace-with-your-api-key"
llm2jev-serve \
  --model-path /path/to/model \
  --served-model-name local-model \
  --host 0.0.0.0 \
  --port 30000 \
  --api-key "$LLM2JEV_API_KEY"
```

List models through SGLang's native endpoint:

```bash
curl http://localhost:30000/v1/models \
  -H "Authorization: Bearer $LLM2JEV_API_KEY"
```

Submit a System One request:

```bash
curl http://localhost:30000/v1/systemone \
  -H "Authorization: Bearer $LLM2JEV_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "state": "The customer package has not arrived.",
    "model": "local-model",
    "questions": {
      "delivery": {
        "type": "noul",
        "instructions": "Is this a delivery issue?"
      }
    }
  }'
```

Use `--submission staged|all` to select candidate submission for `/v1/systemone`
(default: `staged`). The startup setting applies to all `/v1/systemone` requests
served by that process. This does not change the Jev request body or other native
SGLang endpoints. `staged` requires Radix Cache; use `all` with
`--disable-radix-cache`. See [Choosing a mode](#choosing-a-mode) below.

The command also accepts SGLang's normal server arguments. It currently requires
the default single-tokenizer HTTP mode and does not support
`--skip-tokenizer-init`.

## Choosing a mode

| Request pattern | Starting point | Reason |
| --- | --- | --- |
| Long context, many candidates, no relevant cached prefix | `staged` (default) | Avoids repeated processing within a cold request |
| Short input, few candidates | `all` | Extra submission rounds may cost more than they save |
| Repeated requests with mostly cached prefixes | `all` | Existing cache can be reused without establishing it in stages |
| Partial cache hits or highly varied inputs | Compare both | The benefit depends on shared computation and submission overhead |

The backend does not detect cache state and switch modes automatically. A single candidate or inputs without reusable prefixes can go in one batch even in staged mode. Having a shared prefix does not guarantee that additional rounds will be faster.

See [Performance benchmarks](shared-prefix-benchmarks.md) for measurements and test conditions.

See [Shared-prefix caching](shared-prefix-cache.md) for the reuse mechanism and output considerations.
