# Limitations

What AnyJev and the Tacit models do not do, and where their numbers stop applying.
The Chinese version is [limitations.zh-CN.md](limitations.zh-CN.md).

- **Accuracy is bounded by the model.** The readout removes order and label-prior effects, and
  self-distillation moves reasoning into one forward pass. Neither adds knowledge the model does not
  have.
- **Tacit's one forward reads the options in the order given.** It is not averaged over rotations.
  `Decider(level="L0")` on a Tacit checkpoint does that at K prefills; we have not measured it.
- **An escalated decision costs seconds, not milliseconds.** It generates a reasoning trace of up to
  `cot_max_tokens`. The cap bounds how many decisions escalate, not how long one takes.
- **On vLLM, Tacit reads the labels from the top 20 log-probabilities**, and a label outside them
  counts as 0.
- **Tacit-9B and Tacit-2B (Qwen3.5) need transformers ≥ 5.** On Hopper GPUs, `vllm serve` compiles a
  kernel for them with `nvcc`, so the CUDA toolkit has to be installed; `engine="vllm"` falls back to
  a Triton kernel by itself.
- **L0's batch prior costs accuracy when one label dominates a batch.** Use `prior="content_free"` or
  `prior="none"` there.

## Also

- At most 26 options in the letter readout.
- Coverage at 5% risk is a high-variance estimate at n = 300.
- Every published decision is scored in isolation, not inside an agent loop.
