---
title: Open-Jev Workbench
emoji: 🗂️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
license: mit
---

# Open-Jev CPU workbench deployment

This Docker Space runs the [no-code workbench](https://github.com/Zefan-Cai/Open-Jev/blob/main/docs/get-started.md) with the released Open-Jev-2B model. Paste messages or import a CSV, define categories, and download the results. The interface, presets and help are in English; user text and custom categories can use other languages.

**[Open-Jev Workbench](https://huggingface.co/spaces/ZefanCai/Open-Jev-Workbench) is live and has been verified with real CPU classification requests.** The [project workbench page](https://zefan-cai.github.io/open-jev/workbench/) embeds the service. It uses CPU Basic; start with a few rows because this trial can be slow.

A batch accepts up to 200 rows and a CSV up to 2 MB. Exports retain every original column and append classification results. “Download task settings” contains only categories and instructions, without submitted messages or results.

## Original deployment checks

On 2026-09-23, the 16 GB CPU Basic container loaded the model, passed its startup check and completed a real request. A fictional Chinese refund message with four categories returned the refund category through HTTP with a same-origin Origin header. Client wall time was **17.21 seconds**. Invalid input returned HTTP 422. This was one deployment check, not a benchmark or service-speed promise.

Startup logs recorded 28.58 seconds and a process peak RSS of 3,250.45 MiB through readiness. This is not a peak-memory claim for sustained inference. CPU outputs and probabilities have not been compared row by row with the published GPU results.

- Fixed inference source: [`45d5a0e81ab82b70070f05300afc4e821772b1f1`](https://github.com/Zefan-Cai/Open-Jev/commit/45d5a0e81ab82b70070f05300afc4e821772b1f1).
- First verified Space deployment: [`ce8278238af1c9658d19356064293b0f65314176`](https://huggingface.co/spaces/ZefanCai/Open-Jev-Workbench/commit/ce8278238af1c9658d19356064293b0f65314176).

The English interface update overlays only the four workbench static assets. It retains this inference source, `app.py`, model revisions, limits and CPU hardware.

## Prepare the Docker build context

Copy this directory's `Dockerfile`, `app.py` and `README.md` into a staging directory, then copy `examples/workbench/` from the reviewed source checkout into `workbench/` under that directory. Upload those files to the Docker Space root. Set `OPEN_JEV_COMMIT` to the full public inference-source commit SHA. A Space variable with that name is available during Docker build, or the SHA can be supplied as the Dockerfile argument default.

The build fetches that fixed commit from `https://github.com/Zefan-Cai/Open-Jev.git`. It overlays the reviewed workbench assets without changing the inference package. The process runs as UID 1000 on port 7860; the public model requires no access key.

[Hugging Face documentation](https://huggingface.co/docs/hub/spaces-overview) lists CPU Basic as 2 vCPU, 16 GB RAM and 50 GB nonpersistent disk with no hourly hardware fee. Docker Space creation depends on account eligibility. The model must be downloaded again if its cache is lost.

To build locally from the repository root:

```bash
mkdir -p /tmp/open-jev-space/workbench
cp deploy/huggingface-space/{Dockerfile,app.py,README.md} /tmp/open-jev-space/
cp examples/workbench/{index.html,app.js,logic.mjs,styles.css} /tmp/open-jev-space/workbench/
docker build --build-arg OPEN_JEV_COMMIT=45d5a0e81ab82b70070f05300afc4e821772b1f1 \
  -t open-jev-cpu /tmp/open-jev-space
docker run --rm -p 127.0.0.1:7860:7860 --cpus=2 --memory=16g open-jev-cpu
```

Open <http://127.0.0.1:7860/>. The HTTP listener opens first while the model downloads and loads in the background. `/health` reports `loading`, `ready` or `error`; readiness requires a successful fixed two-category startup check. That check is discarded and never shown as a user result. The interface, `/health` and `/v1/systemone` share one origin. GitHub Pages can link to or embed the Space.

## Model and runtime settings

- Adapter: `ZefanCai/Open-Jev-2B`, revision `0c7aa498b1627be8da4acf34c863ff0ee0a92785`, under `package/checkpoint`.
- Base: `Qwen/Qwen3.5-2B`, revision `15852e8c16360a2fea060d615a32b45270f8a8fc`. Startup verifies the packaged base identity.
- Original Open-Jev loader, saved decision head and temperature; BF16 base, FP32 head, CPU, candidate batch size 1 and prefix cache off.
- CPU Torch 2.8.0 with Transformers 5.10.2, PEFT 0.19.1, Accelerate 1.13.0 and Datasets 5.0.0 from the public project's `.[train]` dependencies. No GPU-only FLA or causal-conv1d is installed, and no training is started.
- One Choice question, 2–8 categories, up to 4,000 text characters and a 16 KiB request body. The complete prompt must fit within 1,024 tokens per candidate; oversized inputs are rejected rather than truncated.
- One inference request at a time, without a queue; busy requests return HTTP 429. Up to eight HTTP handler threads and a backlog of eight; excess connections receive 503. CSV rows run sequentially.
- Stopping prevents later rows from being submitted. The current request continues to completion. Failed requests are not automatically retried or replaced with preset answers.

The 2B BF16 weights are about 4.55 GB, with additional memory needed to load and run the model. Transformers 5.10.2 supplies the Qwen3.5 PyTorch CPU path. The original startup and single-request observations do not establish long-input, many-category or sustained-load performance. GPU benchmarks do not establish this deployment's latency or numerical parity.

## Public trial and data

This is a bounded public demo hosted over HTTPS by Hugging Face. Add authentication when deploying a private business service.

Classification sends text and category definitions to the Space's CPU service. The application does not log user text, request bodies or client addresses, retain spreadsheets, or add analytics. Hugging Face's platform privacy terms still apply.

After updating a deployment, verify the actual interface, classification and errors, and record its code and model revisions. To integrate the same request format into your backend, see [Typed decisions](https://github.com/Zefan-Cai/Open-Jev#typed-decisions).
