# Credits

AnyJev stands on other people's work. Attribution lives here, not in identifiers.

## Projects we build on

- **TypeSafe AI, Jev**: the product that defined the interface (state, typed questions, calibrated answers in one pass). Not affiliated.
- **Qwen** (Apache-2.0): the base models of the Tacit checkpoints, Qwen3-1.7B, Qwen3-4B, Qwen3-8B, Qwen3.5-2B and Qwen3.5-9B.
- **vLLM** (Apache-2.0): the inference engine behind `Tacit(engine="vllm")`, `engine="server"` and `VLLMBackend`.
- **JevBench** (fstandhartinger/jevbench, MIT) and **bev-decision** (avbiswas/bev-decision): the two benchmarks the Tacit results are reported on.
- The open readout clones that documented the problem first: SemIf, LitJev, the OpenJev servers, poorjev, open-llm-classifier. Their READMEs said the probabilities were not calibrated and the order mattered; this repo measures it.

## Reported and contributed

People outside the project whose reports and patches changed the code. Issue numbers are in the
CHANGELOG next to what they fixed.

- **[@efronh](https://github.com/efronh)** — found that L2 was broken on transformers 5 and
  identified the renamed `create_causal_mask` argument in the report (#4).
- **[@lws2004](https://github.com/lws2004)** — found that the `hf` extra could not build a backend
  at all, traced it to `device_map` and the undeclared `accelerate`, and supplied the change that
  fixes that, the Apple Silicon segfault and the `.model` assumption together (#5).

## Methods implemented

- Contextual calibration: Zhao et al., "Calibrate Before Use", ICML 2021, arXiv:2102.09690
- Batch calibration: Zhou et al., "Batch Calibration", ICLR 2024, arXiv:2309.17249
- Permutation debiasing: Zheng et al., "Large Language Models Are Not Robust Multiple Choice Selectors", ICLR 2024, arXiv:2309.03882
- Surface-form competition (planned span readout): Holtzman et al., EMNLP 2021, arXiv:2104.08315
- Conformal prediction (planned): Angelopoulos and Bates, 2021, arXiv:2107.07511
- Reliability gating (planned): Chen et al., "Routing Without Training: Controllable-Ratio LLM Offloading via Reliability Gating", 2026, arXiv:2607.20481

## Datasets

See `THIRD_PARTY.md` for every dataset and its license.
