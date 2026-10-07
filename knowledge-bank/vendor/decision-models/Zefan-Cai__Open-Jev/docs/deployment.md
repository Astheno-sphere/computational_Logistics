# Run the released Open-Jev models

Use the [online text/CSV workbench](https://zefan-cai.github.io/open-jev/workbench/)
for a browser-only trial. It runs the released 2B on CPU. For local inference,
start with the trained 2B package below. Base weights download separately on
first use; a generic PEFT text-generation loader does not apply the Open-Jev
scalar head or saved temperature.

## Trained 2B: Linux and NVIDIA

Python 3.10+ and sufficient GPU memory are required. The `train` extra also
supplies inference dependencies; installing it does not start training.

```bash
git clone https://github.com/Zefan-Cai/Open-Jev.git
cd Open-Jev
git checkout 80ca8e81d08992cb2a4cbb6a0caa1355ad3e5aee
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -e '.[train]'
hf download ZefanCai/Open-Jev-2B \
  --revision 0c7aa498b1627be8da4acf34c863ff0ee0a92785 \
  --local-dir models/Open-Jev-2B
python -m jev.server --checkpoint models/Open-Jev-2B/package/checkpoint \
  --device cuda:0 --max-length 4096 --batch-size 1 --no-prefix-cache \
  --host 127.0.0.1 --port 8791
```

In another terminal, wait for the model to load, check readiness and send
an actual request. This example input does not prescribe the model's answer.

```bash
curl --fail http://127.0.0.1:8791/health
curl --fail http://127.0.0.1:8791/v1/systemone \
  -H 'Content-Type: application/json' --data-binary @configs/example-request.json
```

Open <http://127.0.0.1:8791/> for the workbench. The local server returns typed
probabilities and does not execute candidate actions. Overlength requests
are rejected, never silently truncated. Bind to loopback by default; sharing
a service requires your own authenticated HTTPS reverse proxy.

## Choose a deployment

| Target | Released package / command | Evidence and limits |
|---|---|---|
| Linux NVIDIA, 2B | Command above | Actual H200 reference/tail run: maximum allocator peak 6.917 GiB on the recorded batch-32 workloads; leave headroom for your context and CUDA runtime |
| CPU, 2B | Replace `--device cuda:0` with `--device cpu` | Existing HF CPU workbench; substantially slower; start with short requests |
| Apple Silicon, 2B | `JEV_TORCH_DTYPE=float32 python -m jev.server --checkpoint models/Open-Jev-2B/package/checkpoint --device mps --max-length 4096 --batch-size 1 --no-prefix-cache` | MPS support is opt-in; sufficient unified memory required; dtype changes are a separate numerical configuration |
| One 16GB NVIDIA card, 9B | [Consumer GPU recipe](consumer-gpu.md#running-it-on-one-16-gb-card) | Community-tested RTX 4060 Ti / 5060 Ti with explicit placement and request-local cache; batch size 2; preserve author/configuration distinctions |
| NVIDIA H100 80GB, 27B v1.1 | Download pin below, use `models/Open-Jev-27B-v1.1/package/checkpoint` | Full PyTorch/Triton-tail validation passed eight workloads, peak request allocation 54.124 GiB; fast-CUDA failed probability parity; independent sealed evaluation remains pending |
| Docker, 2B / CPU | `docker compose up -d --build` / `docker compose up -d --build open-jev-cpu` | Existing [Docker guide](../docker/README.md); build downloads and verifies package/base, runtime works offline |

MPS does not support bitsandbytes 4/8-bit loading here. Leave
`PYTORCH_ENABLE_MPS_FALLBACK` unset to expose unsupported operations. To
record actual Metal use, run the existing checker after downloading the model:

```bash
JEV_TORCH_DTYPE=float32 python -m scripts.check_mps_engagement \
  --checkpoint models/Open-Jev-2B/package/checkpoint \
  --batch-size 1 --repetitions 3 --output runs/mps-engagement.json
```

MPS support does not imply that every full-size checkpoint fits every Mac.
The 16GB 9B recipe intentionally opts into prefix caching/ragged suffix
batching; it is not the uncached reference configuration used above. Run
numerical parity and task checks for your deployment before treating its
probabilities as interchangeable with the reference.

## Other pinned releases

| Model package | HF repository revision | Pinned upstream base revision |
|---|---|---|
| `ZefanCai/Open-Jev-2B` | `0c7aa498b1627be8da4acf34c863ff0ee0a92785` | Qwen3.5-2B `15852e8c16360a2fea060d615a32b45270f8a8fc` |
| `ZefanCai/Open-Jev-9B` | `47e966881e489511c0c7f5633a9e1960a676a551` | Qwen3.5-9B `c202236235762e1c871ad0ccb60c8ee5ba337b9a` |
| `ZefanCai/Open-Jev-27B-v1.1` | `28cf73067d5b337860bbef3c85b8b82ba8730956` | Qwen3.8-27B `1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` |

```bash
hf download ZefanCai/Open-Jev-9B \
  --revision 47e966881e489511c0c7f5633a9e1960a676a551 \
  --local-dir models/Open-Jev-9B
hf download ZefanCai/Open-Jev-27B-v1.1 \
  --revision 28cf73067d5b337860bbef3c85b8b82ba8730956 \
  --local-dir models/Open-Jev-27B-v1.1
```

Record the loader commit with `git rev-parse HEAD` alongside the package pin
and actual request settings. The [independent evaluation handoff](evaluation-ledger.md#fresh-independent-open-jev-27b-v11-evaluation-pending)
automates these pins and verifies the 27B checkpoint bytes before serving.

## Verification boundaries

The [runtime records](resources.md) and new deployment validation report
separate clean base-wheel/API installation from optional Torch/model tests.
A CPU HTTP fixture tests request/response plumbing, not trained model quality.
GPU kernel execution and full-size model runs need their own hardware evidence;
package imports alone do not establish them.

The separate [fresh Linux installation record](../reports/clean-linux-install-20261002/README.md)
now verifies a new Python 3.11.15 venv with Torch 2.8.0+cu128 and both
`train`/`fast` extras, including FLA 0.5.2. All 77 installed distributions stay
inside the venv; CLI, CPU reference and dependency checks pass. The attributed
extension compiled and loaded for sm90 with CUDA devices hidden and no CUDA
initialization. Its [fully pinned observed dependency lock](../requirements-linux-py311-cu128-20261002.lock)
and public archive origins are preserved. This installation used an existing
Python interpreter and CUDA toolkit; it loaded no model weights and executed
no GPU kernels. It is separate from the H200 runtime below.

The [H200 released-2B report](../reports/efficiency-20261002/h200-2b-summary.md)
records actual checkpoint inference, loopback HTTP and numerical parity. It used
Python 3.12.13, Torch 2.9.0+cu128, Triton 3.5.0, Transformers 5.10.2, PEFT 0.19.1
and Accelerate 1.13.0. The runtime reused a read-only shared installation with an
isolated package overlay; it was not a fresh Linux CUDA installation. The pinned
command above preserves the tested server implementation. Record your resolved
versions with `python -m pip freeze` and the source/package identities alongside
each run. See the [reproducibility receipt](reproducibility-receipt-20261002.md)
for installation and model-execution evidence kept separately.

The separate [released-27B H100 smoke](../reports/efficiency-20261002/ms-27b-smoke.md)
used the pinned 27B package and base weights with the fresh-Linux version family.
It executed PyTorch, Triton-tail and fast-CUDA. Fast-CUDA failed the unchanged
probability tolerance; keep the reference backend for deployment. This single
request validates execution. The [complete safe-backend comparison](../reports/efficiency-20261002/ms-27b-safe-full-summary.md)
subsequently passed 336 checks across eight workloads. Its small sequential
latency differences do not establish a statistically significant speedup or
general model quality improvement.
