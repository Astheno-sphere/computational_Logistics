# Third-party data and code

| What | Where | License | Used for |
|---|---|---|---|
| JevBench, public set | https://github.com/fstandhartinger/jevbench (`datasets/public`: easy, original, hard; 231 items) | MIT | Tacit results, `scripts/eval_tacit.py` (from a local checkout), `bench/results_tacit/` |
| bev-decision | https://huggingface.co/datasets/avbiswas/bev-decision (default config, test split) | not stated on the dataset card (`license: unknown`) | Tacit results, `scripts/eval_tacit.py`, `bench/results_tacit/`; evaluation only |
| banking77 (mteb parquet mirror) | https://huggingface.co/datasets/mteb/banking77 | CC-BY-4.0 | the raw / L0 table (`banking20`, `bench/results_v01/`) and the README GIF |
| 20 Newsgroups (SetFit mirror) | https://huggingface.co/datasets/SetFit/20_newsgroups | see dataset card | `newsgroups` in `bench/results_v01/` and `bench/results_layout/` |
| deepset/prompt-injections | https://huggingface.co/datasets/deepset/prompt-injections | Apache-2.0 | `injection` in `bench/results_v01/` |
| MASSIVE intents (mteb mirror) | https://huggingface.co/datasets/mteb/amazon_massive_scenario | CC-BY-4.0 | `massive_route` in `bench/results_layout/` (18-way utterance routing) |

Datasets are downloaded at run time, never vendored. The Tacit models are derived from Qwen models released under
Apache-2.0 and carry the same license.

# Methods implemented

- Contextual calibration: Zhao et al., ICML 2021, arXiv:2102.09690
- Batch calibration: Zhou et al., ICLR 2024, arXiv:2309.17249
- Permutation debiasing: Zheng et al., ICLR 2024, arXiv:2309.03882
