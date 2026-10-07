FROM python:3.11-slim-bookworm

# Set this to the public commit containing examples/workbench/index.html.
# A full SHA is required; this image never copies the private development tree.
ARG OPEN_JEV_COMMIT
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/user/.cache/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN python -c 'import os,re; assert re.fullmatch(r"[0-9a-f]{40}", os.environ.get("OPEN_JEV_COMMIT", "")), "Set OPEN_JEV_COMMIT to a full public commit SHA"'
RUN git init /opt/open-jev \
    && git -C /opt/open-jev remote add origin https://github.com/Zefan-Cai/Open-Jev.git \
    && git -C /opt/open-jev fetch --depth 1 origin "$OPEN_JEV_COMMIT" \
    && git -C /opt/open-jev checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/open-jev rev-parse HEAD)" = "$OPEN_JEV_COMMIT" \
    && test -f /opt/open-jev/examples/workbench/index.html
RUN python -m pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -e '/opt/open-jev[train]'
RUN useradd -m -u 1000 user && chown -R user:user /opt/open-jev
WORKDIR /app
COPY --chown=user:user app.py /app/app.py
COPY --chown=user:user workbench/ /opt/open-jev/examples/workbench/
USER user
EXPOSE 7860
CMD ["python", "app.py"]
