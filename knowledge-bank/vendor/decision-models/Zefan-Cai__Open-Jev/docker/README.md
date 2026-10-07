# Open-Jev in Docker

[`../Dockerfile`](../Dockerfile) builds a self-contained Open-Jev service. The
published checkpoint package and the exact upstream base revision it requires
are baked into the image at build time, so a started container loads the model
and listens on its port with no network access, no volumes and no download step.

The released checkpoint is a LoRA adapter plus a trained scalar decision head
and a calibration temperature. It only runs together with the pinned
`Qwen/Qwen3.5-2B` revision named in its `model.json`, so both are baked in and
the build fails if that pairing ever stops matching.

## Quick start

```bash
docker compose up -d --build                  # NVIDIA GPU
docker compose up -d --build open-jev-cpu     # CPU only, much slower
```

The first build downloads about 4.6 GB of weights plus the CUDA wheels and
produces an image of roughly 12 GB. When the container reports healthy, the
model is loaded and the service is answering requests:

```bash
docker compose ps                             # STATUS shows (healthy)
curl -s http://127.0.0.1:8791/health
curl -s -X POST http://127.0.0.1:8791/v1/systemone \
  -H 'Content-Type: application/json' \
  --data-binary @configs/example-request.json
```

The text/CSV workbench is served from inside the image at <http://127.0.0.1:8791>,
the developer task lab at <http://127.0.0.1:8791/examples/index.html>, and
probability painting at
<http://127.0.0.1:8791/examples/painting/index.html>.

Without compose:

```bash
docker build -t open-jev:2b .
docker run -d --gpus all -p 127.0.0.1:8791:8791 --name open-jev open-jev:2b
```

## What the image contains

| Path | Contents |
| --- | --- |
| `/opt/open-jev/models/Open-Jev-2B/package` | Published checkpoint package: LoRA adapter, decision head, calibration temperature, manifest and provenance |
| `/opt/open-jev/models/hub` | Hugging Face cache holding the pinned base revision |
| `/opt/open-jev/models/BUILD.json` | Repositories, revisions and digests recorded at build time |
| `/app` | The `jev` package, the `examples/` task lab and `configs/` |

`HF_HUB_OFFLINE=1` is set, so nothing is fetched at run time. Every file each
package lists in its own `manifest.json` is verified against the published
SHA-256 during the build, and the build stops if the checkpoint asks for a
different base revision than the one being baked in.

## Configuration

Every setting is an environment variable; compose reads them from your shell or
a `.env` file next to `docker-compose.yml`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `JEV_DEVICE` | `cuda:0` (compose), `auto` (image) | Torch device. `auto` uses the GPU when one is visible and otherwise falls back to CPU |
| `JEV_PORT` | `8791` | Port inside the container and on the host |
| `JEV_BIND_ADDRESS` | `127.0.0.1` | Host interface compose publishes on |
| `JEV_MAX_LENGTH` | `4096` | Token limit per candidate sequence; longer inputs are rejected rather than truncated |
| `JEV_BATCH_SIZE` | `32` | Candidate sequences per forward pass. Lower it if a small GPU runs out of memory on wide Choice questions |
| `JEV_PREFIX_CACHE` | `off` | Request-local prefix reuse. Off by default: it exceeded the probability tolerance on 9 of 11 measured workloads ([`docs/inference-latency.md`](../docs/inference-latency.md)) |
| `JEV_CHECKPOINT` | discovered | Checkpoint directory; unset means the package baked into the image |

Anything after the image name is passed to `python -m jev.server` and wins over
the variables above:

```bash
docker run --rm --gpus all -p 127.0.0.1:8791:8791 open-jev:2b --batch-size 8
```

A non-flag argument runs instead of the server, which is how to score a single
saved request without starting the service:

```bash
docker run --rm --gpus all open-jev:2b python -m jev.predict \
  --checkpoint /opt/open-jev/models/Open-Jev-2B/package/checkpoint \
  --request configs/example-request.json
```

## Other builds

CPU-only image:

```bash
docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu \
  -t open-jev:2b-cpu .
```

The 9B package, which needs a correspondingly larger GPU:

```bash
docker build \
  --build-arg JEV_PACKAGE_REPO=ZefanCai/Open-Jev-9B \
  --build-arg JEV_PACKAGE_REVISION=47e966881e489511c0c7f5633a9e1960a676a551 \
  --build-arg JEV_BASE_MODEL=Qwen/Qwen3.5-9B \
  --build-arg JEV_BASE_REVISION=c202236235762e1c871ad0ccb60c8ee5ba337b9a \
  -t open-jev:9b .
```

A different CUDA build of torch, for older drivers:

```bash
docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126 -t open-jev:2b .
```

If a repository ever requires authentication, pass a token as a build secret
rather than a build argument:

```bash
HF_TOKEN=hf_... docker build --secret id=hf_token,env=HF_TOKEN -t open-jev:2b .
```

## Checking a build

```bash
docker compose ps                     # healthy means the checkpoint is loaded
docker compose logs --no-log-prefix   # ends with the bound URL and the model
docker compose exec open-jev cat /opt/open-jev/models/BUILD.json
docker image inspect open-jev:2b --format '{{json .Config.Labels}}'
```

Responses carry `checkpoint_sha256` in their metadata, so the same checkpoint
can be confirmed across rebuilds and hosts.

On one RTX 5070 Ti with driver 596.21, this image reported healthy about ten
seconds after `docker compose up`, answered the three-question
`configs/example-request.json` in roughly 215 ms per request after the first
call, and used about 6.9 GB of GPU memory on the widest bundled example
(`examples/painting/hsl-request.json`, 272 candidate sequences) at the default
`JEV_BATCH_SIZE=32`. Those are single-machine smoke-test observations rather
than a benchmark; [`docs/inference-latency.md`](../docs/inference-latency.md)
holds the measured protocol and results.

## Limits

- The GPU service needs the NVIDIA Container Toolkit; without it, Docker reports
  that it cannot select the `nvidia` device driver. Start `open-jev-cpu`
  instead.
- CPU serving works but is far slower than the measured GPU latencies, and the
  CPU service allows a 15-minute start period for the first load.
- The server has no authentication and applies no rate limiting. Compose
  publishes it on loopback only; exposing it more widely is your decision.
- Requests are serialised by a lock in the server, so one container answers one
  request at a time regardless of `JEV_BATCH_SIZE`.
- Response metadata reports `code_commit: null`, because the image ships the
  source tree without its git history. The checkpoint's own SHA-256 is still
  reported in `checkpoint_sha256`, and the image labels record the baked
  package and base revisions.
- No live business action is performed by the server.
