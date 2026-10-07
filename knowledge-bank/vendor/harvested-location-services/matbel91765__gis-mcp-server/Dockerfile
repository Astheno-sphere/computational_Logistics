FROM python:3.12-slim AS base

# Build deps for any sdist-only packages (libpysal/esda). Geo wheels (shapely,
# pyproj, fiona, rasterio, geopandas) ship manylinux binaries, no system GDAL.
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (better layer caching), then the package.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[all]"

# Networked deployment defaults; override via compose/env.
ENV LOCUSYNC_TRANSPORT=http \
    LOCUSYNC_HOST=0.0.0.0 \
    LOCUSYNC_PORT=8000 \
    LOCUSYNC_WORKDIR=/data

# Run as an unprivileged user; /data is the file-I/O sandbox.
RUN useradd --create-home --uid 10001 locusync && \
    mkdir -p /data && chown locusync:locusync /data
USER locusync

EXPOSE 8000
# Liveness only: a reachable port returns *some* HTTP status (200/401/406).
# Connection refused -> non-zero -> unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -s -o /dev/null http://127.0.0.1:8000/mcp || exit 1

CMD ["locusync-server"]
