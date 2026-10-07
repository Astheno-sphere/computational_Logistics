# Working agreement for agents and humans in this repo

## Ground rules

1. **No fabricated data, ever.** Published numbers come from committed result JSON under `bench/results_*/<date>/` (the runs behind the shipped tables are `bench/results_v01/2026-09-22/`, `bench/results_layout/2026-09-27/` and `bench/results_tacit/2026-10-06/`). If a run did not happen, the cell is empty. Every number in prose names its JSON, and `tests/test_readme_numbers.py` checks the README tables against theirs.
2. **No hidden generation.** `Decider` never samples tokens. `Tacit` generates only for an escalated decision (`adaptive=True`), and every escalation is reported (`route="cot"`) and counted against the cap. Any other code path that samples tokens is a bug.
3. **Level and route are mandatory.** Every `Decision` carries `level` (`raw` / `L0`); every Tacit decision carries `route` (`one_forward` / `cot`). Tests assert both.
4. **Backends are thin.** A backend implements `next_token_logprobs(prompts, token_ids)`; the transformers backend adds the optional methods the Decider probes for (`score_shared` for shared-prefix scoring, `hidden_states` / `hidden_states_to` for reading an intermediate block). Nothing else goes in `anyjev/backends/`: debiasing and calibration live above the backend and are tested once. Tacit's engines live in `anyjev/tacit.py` and implement `read` and `reason_read`.
5. **Small changes.** One issue, one change, under ~400 lines excluding tests and fixtures.
6. **Tests before features.** A calibration method lands with a unit test on synthetic logits where the correct answer is known analytically (see `anyjev/backends/fake.py`, which also plants hidden states). A Tacit change lands with a test on the fake engine in `tests/test_tacit.py`; the one-forward prompt is pinned there, because the models were trained on it.
7. **Licenses are checked** before any dataset or third-party code is used. Record it in the task loader and in `THIRD_PARTY.md`.
8. **No names we do not own** in identifiers, package names, or API paths beyond the project name itself. Attribution lives in docs.
9. **Git is the maintainer's.** Agents do not run `git add`, `git commit`, or `git push`. Leave the working tree for the maintainer to review and commit.

## Definition of done

- Code + tests + docstring + one line in `CHANGELOG.md`.
- Result changes: the JSON committed with hardware, model and library versions, batch size and dtype, and the README tables updated from it (the README test fails otherwise).
- Backends: a smoke test against a real engine, marked `@pytest.mark.engine`, skipped in CI without the engine.

## Environment

- Python 3.10+. `pip install -e ".[dev]"` for the core; `.[hf]` for real models on transformers (Tacit-9B and Tacit-2B need `transformers>=5`), `.[vllm]` for in-process vLLM, `.[client]` for a running `vllm serve`.
- `ruff check anyjev scripts space tests && pytest -q` is what CI runs; both must be green on CPU with numpy alone.
- Bench runs record `nvidia-smi`, torch, and transformers versions. Do not mix hardware within one results table.

## Ask a human about

- Any change to the public HTTP schema (`anyjev/serve.py`) or to Tacit's one-forward prompt.
- Any new dataset.
- Any claim in docs that compares us to a named product.
- Any dependency with a non-permissive license.
