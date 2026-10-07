# Contributing

Thanks for looking. The fastest way to contribute is to add one file. The open slots are the items marked
**help wanted** in [ROADMAP.md](ROADMAP.md); open an issue first if you want one.

## Add a backend (`anyjev/backends/<engine>.py`)

Implement one method:

```python
def next_token_logprobs(self, prompts: Sequence[str], token_ids: Sequence[Sequence[int]]) -> List[np.ndarray]
```

For prompt `i`, return the log-probability of each id in `token_ids[i]` at the next position, from the full-vocabulary log-softmax. Expose `.tokenizer` (needs `.encode(text, add_special_tokens=False)`; a chat template is used if present) and `.name`. Nothing else goes in a backend: debiasing and calibration live above it and are tested once. Add a parity check against `HFBackend` like `scripts/vllm_parity.py`, marked `@pytest.mark.engine` if it needs the engine.

## Rules

- **No fabricated numbers.** A table row is a committed JSON under `bench/results_*/` plus the command that produced it, with hardware and library versions (the runners record them). If a run did not happen, the cell is empty.
- **No hidden generation.** Only an escalated Tacit decision generates, and it is reported as one. Any other code path that samples tokens in decision mode is a bug.
- **Level and route are mandatory.** Every `Decision` carries `level`, every Tacit decision `route`; tests assert both.
- **Small PRs.** One thing per PR, under about 400 lines excluding tests and fixtures.
- **Tests before features.** Calibration methods land with a unit test on synthetic logits where the answer is known analytically (`anyjev/backends/fake.py` makes this easy).

`pip install -e ".[dev]"`, then `ruff check anyjev scripts space tests && pytest -q` runs what CI runs, on CPU, in a few seconds.
