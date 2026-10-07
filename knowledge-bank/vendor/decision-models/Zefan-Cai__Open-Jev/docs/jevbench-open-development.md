# Frozen public development checks

This runner compares the released 2B checkpoint and a fixed-step synthetic
continued-training pilot on the same public inputs. The historical 231-task
public suite has already informed development. A result here is development
evidence, not a fresh blind evaluation or an official JevBench score.

The pinned upstream commit is
`bb05a335bc809e61b20c0f745d25499a82b326fc`. Its public tree contains 231 tasks.
The v1.5 method documents 601 published-open tasks and 904 total open tasks;
the additional 370 published-open tasks are absent from this checkout. This
runner reads only `datasets/public/{original,easy,hard}.jsonl` and the public
method files. It does not read private datasets, evaluator pool or sealed items.

The 64-task sample has 34 Choice, 23 Noul and seven Score tasks. The 128-task
sample has 77 Choice, 41 Noul and ten Score tasks; its first 64 tasks are exactly
the smaller sample. Half the sample comes from six historical aggregate error
families and half provides other-family coverage. Within each half, selection
round-robins file tier, type and family, ordering IDs by a fixed SHA-256 seed.
Gold, state text and pilot outputs do not influence selection. No benchmark
prompt or gold is copied into synthetic training or temperature fitting.

The two method hashes match the observed v1.5.4 reference. Noul uses inclusive
`p_yes <= 0.2` / `p_yes >= 0.8` boundaries; intermediate probabilities abstain
and count wrong. Score uses the distribution's expected level and normalized
absolute error against the uniform random-level baseline. Argmax Score
accuracy is retained only as an auxiliary diagnostic. Choice uses upstream
distribution validation and lexical ties. Tier competence is not clipped;
present tiers renormalize 0.10/0.20/0.30/0.40 weights and types receive equal
weights under the headline amendment. The subset lacks the public judge tier,
so its competence diagnostic is not the official `I_open`.

Prepare a sparse public checkout and immutable sample:

```bash
git clone --filter=blob:none --no-checkout https://github.com/fstandhartinger/jevbench.git runs/jevbench-v15-public-source
git -C runs/jevbench-v15-public-source sparse-checkout init --cone
git -C runs/jevbench-v15-public-source sparse-checkout set jevbench docs datasets/public
git -C runs/jevbench-v15-public-source checkout --detach bb05a335bc809e61b20c0f745d25499a82b326fc
python -m scripts.jevbench_open_development prepare \
  --upstream runs/jevbench-v15-public-source \
  --output runs/jevbench-open-development/frozen64 --size 64
```

Run each checkpoint with the default Torch backend, prefix caching off, the
same maximum input length, and the same pushed execution commit. Preserve each
checkpoint's own saved temperature; fit the pilot temperature only on its
independent synthetic calibration split. Supply each server's seven-field
identity JSON as used by the existing public runner:

```bash
python -m scripts.jevbench_open_development collect \
  --upstream runs/jevbench-v15-public-source \
  --prepared runs/jevbench-open-development/frozen64 \
  --endpoint http://127.0.0.1:8791/v1/systemone \
  --identity runs/jevbench-open-development/baseline-identity.json \
  --output runs/jevbench-open-development/baseline --max-seconds 1800
python -m scripts.jevbench_open_development summarize \
  --upstream runs/jevbench-v15-public-source \
  --run-dir runs/jevbench-open-development/baseline \
  --output runs/jevbench-open-development/baseline-summary.json
```

Repeat collection and summary with the pilot server, identity and a new run
directory, retaining the same prepared input. Then compare:

```bash
python -m scripts.jevbench_open_development compare \
  --baseline runs/jevbench-open-development/baseline-summary.json \
  --trained runs/jevbench-open-development/trained-summary.json \
  --output runs/jevbench-open-development/comparison.json
```

Collection reuses the existing serial loopback HTTP runner: no warmups, retries
or hosted services. Summary verifies every raw response, identity, request hash,
attempt journal and completed count. Incomplete or failed requests prevent a
comparison. A malformed Score makes its competence unavailable because the
public method does not specify a numeric failure MAE. Input/context failures
must be reported; do not drop or replace individual tasks after results.
Keep task text, gold and raw outputs in ignored/private run directories.
Only aggregate reports and gold-free selection manifests are publishable.
