# syntax=docker/dockerfile:1.7
#
# Open-Jev 2B serving image. The pinned checkpoint package and the upstream base
# weights it requires are baked in at build time, so the container starts,
# loads the model and listens on JEV_PORT without any network access.
#
#   docker build -t open-jev:2b .
#   docker run --gpus all -p 127.0.0.1:8791:8791 open-jev:2b
#
# CPU-only build:
#   docker build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu -t open-jev:2b-cpu .

ARG PYTHON_VERSION=3.12

# Published revisions from the project README. Point these at the 9B package and
# its base revision to bake that model instead; nothing else has to change.
ARG JEV_PACKAGE_REPO=ZefanCai/Open-Jev-2B
ARG JEV_PACKAGE_REVISION=0c7aa498b1627be8da4acf34c863ff0ee0a92785
ARG JEV_BASE_MODEL=Qwen/Qwen3.5-2B
ARG JEV_BASE_REVISION=15852e8c16360a2fea060d615a32b45270f8a8fc

########################  weights  ########################
# Isolated so the download cache and its tooling never reach the runtime image.
FROM python:${PYTHON_VERSION}-slim AS weights

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    HF_XET_HIGH_PERFORMANCE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    JEV_MODEL_ROOT=/weights

# The fetch step rejects a mismatch between the checkpoint's recorded base model
# and the base revision pinned here, so a wrong pairing fails the build.
ARG JEV_PACKAGE_REPO
ARG JEV_PACKAGE_REVISION
ARG JEV_BASE_MODEL
ARG JEV_BASE_REVISION
ENV JEV_PACKAGE_REPO=${JEV_PACKAGE_REPO} \
    JEV_PACKAGE_REVISION=${JEV_PACKAGE_REVISION} \
    JEV_BASE_MODEL=${JEV_BASE_MODEL} \
    JEV_BASE_REVISION=${JEV_BASE_REVISION}

RUN pip install --no-cache-dir huggingface_hub

COPY docker/fetch_models.py /usr/local/bin/fetch_models.py
# Optional private-repo access: docker build --secret id=hf_token,env=HF_TOKEN
RUN --mount=type=secret,id=hf_token,required=false \
    python /usr/local/bin/fetch_models.py

########################  runtime  ########################
FROM python:${PYTHON_VERSION}-slim AS runtime

# cu128 matches the torch>=2.8 CUDA wheels and current NVIDIA drivers.
# Override with https://download.pytorch.org/whl/cpu for a CPU-only image.
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ARG TORCH_SPEC=torch>=2.8

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TOKENIZERS_PARALLELISM=false

# Inference needs the pinned runtime only; datasets and the training extras stay out.
RUN pip install --no-cache-dir --index-url "${TORCH_INDEX_URL}" "${TORCH_SPEC}" \
 && pip install --no-cache-dir \
        transformers==5.10.2 \
        peft==0.19.1 \
        accelerate==1.13.0 \
        safetensors

# Baked weights: the HF cache holds the base revision, the package holds the
# LoRA adapter, decision head and calibration temperature. Ownership is set by
# the copy itself; a later chown -R would duplicate 4.6 GB into another layer.
COPY --from=weights --chown=10001:10001 /weights /opt/open-jev/models

ENV HF_HOME=/opt/open-jev/hf \
    HF_HUB_CACHE=/opt/open-jev/models/hub \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY jev ./jev
COPY examples ./examples
COPY configs ./configs
COPY docker/entrypoint.sh /opt/open-jev/entrypoint.sh

# --no-deps keeps the pinned runtime above authoritative; the editable install
# leaves examples/ beside the package so the server can serve the task lab.
RUN pip install --no-cache-dir --no-deps -e . \
 && chmod +x /opt/open-jev/entrypoint.sh \
 && useradd --create-home --uid 10001 jev \
 && mkdir -p "${HF_HOME}" \
 && chown -R jev:jev /app "${HF_HOME}"

USER jev

# JEV_CHECKPOINT is left unset: the entrypoint resolves the package baked in
# above, so the same Dockerfile serves a 9B build without further changes.
ENV JEV_MODEL_ROOT=/opt/open-jev/models \
    JEV_DEVICE=auto \
    JEV_HOST=0.0.0.0 \
    JEV_PORT=8791 \
    JEV_MAX_LENGTH=4096 \
    JEV_BATCH_SIZE=32 \
    JEV_PREFIX_CACHE=off

ARG JEV_PACKAGE_REPO
ARG JEV_PACKAGE_REVISION
ARG JEV_BASE_MODEL
ARG JEV_BASE_REVISION
LABEL org.opencontainers.image.title="Open-Jev typed-probability server" \
      org.opencontainers.image.description="Open-Jev decision checkpoint served over HTTP, weights baked in" \
      org.opencontainers.image.source="https://github.com/Zefan-Cai/Open-Jev" \
      org.opencontainers.image.licenses="MIT" \
      org.openjev.package="${JEV_PACKAGE_REPO}@${JEV_PACKAGE_REVISION}" \
      org.openjev.base_model="${JEV_BASE_MODEL}@${JEV_BASE_REVISION}"

EXPOSE 8791

# The port is bound only after the checkpoint is loaded, so passing this health
# check means the service is ready to answer requests.
HEALTHCHECK --interval=15s --timeout=10s --start-period=300s --retries=5 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ['JEV_PORT']+'/health',timeout=5).read()"

ENTRYPOINT ["/opt/open-jev/entrypoint.sh"]
