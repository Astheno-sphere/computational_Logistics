# greeks-mcp — Model Context Protocol server (stdio).
#
# Builds a self-contained image that starts the server and responds to MCP
# introspection (initialize + tools/list) with NO API key required — which is
# all Glama needs to evaluate the server. Public tools work keyless; the
# authenticated analytics tools attach GREEKS_API_KEY at runtime when present.
#
#   docker build -t greeks-mcp .
#   docker run --rm -i greeks-mcp                       # stdio (what MCP clients spawn)
#   docker run --rm -i -e GREEKS_API_KEY=grk_... greeks-mcp
FROM python:3.12-slim

# Faster, quieter, no .pyc clutter; unbuffered so stdio streams promptly.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first (better layer caching): copy only the metadata
# needed to resolve the build, then the source.
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package itself (pulls mcp[cli] + httpx from pyproject).
RUN pip install --no-cache-dir .

# Run as a non-root user — good hygiene and required by some scanners.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# stdio is the default transport MCP clients (and Glama) spawn. The console
# script is installed by pyproject's [project.scripts].
ENTRYPOINT ["greeks-mcp"]
