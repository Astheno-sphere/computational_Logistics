# Reproducibility receipt: October 2, 2026

The completed H200 evidence covers the isolated final-row operator, released
2B whole-model execution and loopback HTTP comparisons. A natural support
trial also completed with the released checkpoint. A fixed 64-step synthetic
continued-training pilot completed; its public-development transfer comparison
completed on the frozen 64-task development sample.

## Observed execution

The timed operator run used a clean sparse source checkout at
`ed28a2fd9237814fd8175b6c0bdd05f18eadff76`. The test source archive came from
the same pushed commit. Its file manifest and the timed source digest are
preserved in the report. Clean source describes the Git checkout.

The Linux process used the existing `runtime312` Python runtime with a selected
dependency overlay. It was not a fresh clean Linux installation or a new
standalone environment. The observed package versions are execution facts;
they do not establish a clean-install compatibility result. A complete package
origin/path manifest has not been published for this process. The
[selected-version and overlay-origin receipt](../reports/efficiency-20261002/h200-runtime-origin.json)
records the observed packages, read-only shared-runtime modules and task-local
copies. Its Transformers 5.10.2 audit checked 2,434 official-wheel package files
with zero mismatches. Internal account paths are represented by hashes. This
selected audit is not a full environment lock.

| Runtime fact | Observed value |
|---|---|
| Python | 3.12.13 |
| Torch | 2.9.0+cu128 |
| Triton | 3.5.0 |
| Transformers / PEFT | 5.10.2 / 0.19.1; used for the verified released 2B load |
| CUDA runtime / driver | 12.8 / 595.71.05 |
| GPU / capability | NVIDIA H200 / sm90 |
| CUDA compiler on PATH | Absent; this Triton operator required none |
| TF32 matmul | Disabled |
| Model weights loaded | None in isolated operator run; pinned released 2B in model/HTTP runs |

All nine seeded activation cases passed the recorded numerical checks. The
separate suite passed two CUDA checks and ten profile, ownership and reference
checks. Each case retained ten warmups, 100 measured samples per path and the
first-observed cold calls. Reported P50/P95 include Python dispatch and
synchronized CUDA completion. They measure the operator on this runtime.

The separate released 2B experiment verified all five inference files, the
checkpoint tree and all 13 pinned upstream model/tokenizer files. It loaded
the published LoRA adapter, FP32 scalar head and saved temperature against the
pinned base. Eight workloads produced 168 in-process reference comparisons
and 168 loopback HTTP comparisons, all passing the recorded parity checks.
Maximum probability error was 1e-7, with zero decisions changed or audited
threshold flips. The smallest measured candidate margin to audited thresholds
was 0.00142582; this is coverage of those workloads, not all boundary inputs.

Whole-model warm P50 ratios were 1.006–1.020× and HTTP ratios 1.002–1.034×.
These sequential runs used 20 measured samples and three warmups per workload;
no statistical significance is established. Resident allocation was 3.515 GiB
for both paths; both reached 6.917 GiB maximum per-request peak allocation.
Cold loads/checksums and first-observed requests remain separate in the raw
reports. Neither full tree-backbone nor training-memory savings were measured.

## Bound artifacts

- [Operator summary](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-summary.md)
- [Raw timing, numerical and environment report](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-results-ed28.json)
- [Test source manifest](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-test-source-manifest.json)
- [Test output](https://github.com/Zefan-Cai/Open-Jev/blob/4898a2923cecb2fd62b25b5cde8d64741d9cfe2e/reports/efficiency-20261002/h200-kernel-tests-ed28.txt)
- [Machine-readable receipt](../reports/efficiency-20261002/reproducibility-receipt.json)
- [Released 2B model and HTTP summary](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/efficiency-20261002/h200-2b-summary.md)
- [Torch reference model report](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/efficiency-20261002/h200-2b-torch-ed28.json)
- [Triton-tail model report](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/efficiency-20261002/h200-2b-triton-tail-ed28.json)
- [Implementation PR #14](https://github.com/Zefan-Cai/Open-Jev/pull/14)

The source digest is
`5bfeef9c9716d8a451732d03ab32b104c86013154931c628ff01810e584145d6`;
the environment digest is
`816ee72a7bbca4e9aa4271b2ec7e41ce96236e6962f8eecd86b1acdafa856109`;
the report's canonical digest is
`9aeb0f993199bfa5a29640631ca412169739332b64eed65bd11fafceb5ae92ba`.
Both model reports use the same source and environment digests. The reference
report's canonical digest is
`ab0cc377e5e6da5eba53344b070ec14866ccdd119b84160d2a7885a294458d81`;
the Triton-tail report's digest is
`7ba3c85695061439760ecf788d56f2057de98082fbff6bb7cd801ee434f5bc91`.

## Natural support application

The [support aggregate and calibration lock](https://github.com/Zefan-Cai/Open-Jev/tree/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/support-routing-20261002)
bind the released 2B package hash, base revision, saved temperature, code
`80ca8e81d08992cb2a4cbb6a0caa1355ad3e5aee` and 4,096-token limit.
The calibration policy was locked on 96 reserved official-train utterances
before collecting 256 independently selected official-test utterances.

On test, model routing was 166/256 (64.8%) versus BM25 top-1 211/256 (82.4%).
Candidate recall was 249/256 (97.3%). Accepted coverage was 88/256 (34.4%),
with 14/88 accepted errors (15.9%); 168/256 rows require review. The calibration
target did not transfer to test, and no test threshold was fitted afterwards.
The released checkpoint may have prior BANKING77 training exposure; this is
not untouched-task zero-shot or an OOS-detection benchmark.

The actual-model browser smoke exercised 12 natural official-training
examples via an SSH execution bridge. There were no page errors, but no
policy was imported, so all 12 stayed unresolved for review. Human corrections
and completed external human trials were zero. UI timing includes the bridge
and is not an inference-latency benchmark. The static website requires the
reader's local checkpoint server and does not offer a live GPU trial.

## Fixed synthetic continued-training pilot

The released 2B checkpoint completed 64 fixed training steps, consuming 256
training rows, at source
`80ca8e81d08992cb2a4cbb6a0caa1355ad3e5aee`. Separate synthetic calibration
fixed temperature before trained Test/OOD scoring. Argmax accuracy improved
84/128 → 99/128 on Test and 83/128 → 95/128 on controlled OOD variants.
Saved/reloaded probability error was zero, and the original released checkpoint
was retained. The adapted checkpoint is experimental and is not a released
Open-Jev model. All four 128-row journals and their family/kind metrics were
recomputed without model weights; the 64-row calibration temperature and
three reload comparisons also matched the locked records.

The [training summary](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/frontier-controls-v4/continued-2b-20261002/summary.json)
and [completion receipt](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/frontier-controls-v4/continued-2b-20261002/completion-receipt.json)
retain the fixed run, selection, calibration, predictions and reload evidence.
The training runner's checkpoint file-map digest is
`27aebbcb24cccc4d55ad410c8a006cfdb52e023443a555ce0bbbf23491245a73`;
the execution owner's serving-tree digest is
`61e22c91bfbcdcba02ea1c62d039d8169cdf4f73f79cfe2c170322da2bb7c037`.
These digest schemes differ. The bound artifacts publish no checkpoint weights.

Numeric Test stayed 30% → 30%; numeric OOD fell 35% → 30%; timeline OOD fell
58.33% → 54.17%. These failures are retained. This is one fixed synthetic pilot
seed, not a wholly new domain, pretrained-base ablation or natural-support
improvement claim.

## Frozen public-development comparison

The [public-development summary and bound execution receipt](https://github.com/Zefan-Cai/Open-Jev/blob/42e46481da6dd8191d6f510fc3680c70fd4f051d/reports/jevbench-public-development-20261002/summary.md)
compares the released and experimental 2B checkpoints on the same 64 locked
requests. Choice stayed **17/34**, and Noul stayed **9/23** under the documented
inclusive 0.2/0.8 abstention rule. Noul answered coverage changed from 17/23
to 18/23; the extra answer was incorrect. All 34 Choice decisions were
unchanged. Across seven Score items,
expected-position normalized MAE fell **0.22393 → 0.20645**; auxiliary Score
argmax correct stayed 2/7. Score MAE improved on four items and regressed
on three. Equal-type, available-tier-weighted subset competence
changed **22.835 → 24.257**, driven only by Score.

Both runs used source `80ca8e8`, pinned base revision `15852e8` and max length
16,384. The checkpoint and saved temperature both changed: 1.518796342858676
→ 1.5446931834967927. This comparison does not isolate weight adaptation from
recalibration. It is one public development sample with no uncertainty estimate;
historical public feedback informed the controls. The pinned source exposes
231 public tasks, rather than all 601 documented published-open items or the
904-item official open set. No official I_open, blind/sealed score, composite,
rank or broad JevBench improvement is established. Raw benchmark text, gold
and responses remain private; public aggregates retain their identities and
input digest.

## Separate installation evidence

The [macOS deployment validation](../reports/deployment-validation-20261002/README.md)
built and installed a wheel into a fresh Python 3.14.5 environment and exercised
the base-package CLI and HTTP fixture without Torch or model weights. CI
checks on Python 3.10 and 3.14 are separately recorded in
[`ci.json`](../reports/deployment-validation-20261002/ci.json).
Neither record is a fresh Linux CUDA installation or released-model GPU load.

A separate [fresh Linux venv installation](../reports/clean-linux-install-20261002/README.md)
completed with the final wheel, Torch 2.8.0+cu128 and `train`/`fast` extras.
All 77 installed distributions reside in the new venv. Dependency, CLI, CPU
reference, packaged-resource and required FLA symbol checks passed. The
attributed extension also compiled and loaded for explicit sm90 in 60.18
seconds while CUDA devices were hidden; CUDA initialization remained false.
The record binds public package archive hashes and a complete observed version
lock. Python, OS, compiler, toolkit and pip download cache were reused. This is
package-installation and compilation evidence; no model or GPU kernel executed.

The [final portable checks](../reports/deployment-validation-20261002/final-portable-checks.json)
record 859 discovered tests, 85 skipped and no failures, plus six passing
workbench JavaScript tests. The 383,608-byte wheel includes the CUDA/Triton
sources, provenance and third-party notices; its SHA-256 is
`45ac71f6376a41fdbfcf7e05afe544bca66d40a0a19e31b1e55473400b1e8862`.
These checks loaded no model weights. The final local rerun includes the
pinned-revision training guard on top of `4898a29`; its two changed code-file
hashes and test-log digest are recorded. Pushed source `4898a29` separately
passed the [Python 3.10/3.14 Linux CI matrix](https://github.com/Zefan-Cai/Open-Jev/actions/runs/37040427171).

The released 2B package tree verified and loaded in the measured experiment is
`3076462e6356412082e79af909227b39b2863b90def79155ca0821aa506b7ded`.
Its base/tokenizer revision is
`15852e8c16360a2fea060d615a32b45270f8a8fc` and package revision is
`0c7aa498b1627be8da4acf34c863ff0ee0a92785`.
Package projection hashes differ from original
source-evaluated checkpoint hashes. Use the package manifest appropriate to
the downloaded artifact rather than substituting a historical tree hash.

Full 9B/27B checkpoint inference in this H200 efficiency experiment remains
pending. A separate [released-27B H100 smoke](../reports/efficiency-20261002/ms-27b-smoke.md)
now verifies GPU execution of the reference, Triton-tail and vendored tree CUDA
backends. Fast-CUDA failed probability parity. The subsequent
[full safe-backend measurements](../reports/efficiency-20261002/ms-27b-safe-full-summary.md)
passed eight workloads and 336 checks. Fresh Linux venv installation and
compilation are verified separately above.

The execution owner's bounded read-only probes on the measured H200 host
timed out to Hugging Face HTTPS and the MS cache's SSH endpoint. The 27B base
is missing there; `nvcc` and the optional flash-linear-attention distribution
are also absent. These are the observed blockers for full 27B tree-backend
validation on this host. The successful 2B Triton-tail path uses the existing
reference backbone and does not validate the vendored tree CUDA path.
