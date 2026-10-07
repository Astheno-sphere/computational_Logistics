# Dockerfile for Glama (and other registries that build the server to run
# introspection checks). Image starts the MCP server in stdio mode.
#
# A placeholder ATMOSPORE_API_KEY is set so the server doesn't exit before
# `initialize` / `tools/list` complete — those calls don't hit the upstream
# API. Real tool calls require a real key supplied by the caller's runtime.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY atmospore_mcp ./atmospore_mcp

RUN pip install --no-cache-dir .

# Placeholder so the entry point doesn't sys.exit(2) on missing key.
# Override at runtime: -e ATMOSPORE_API_KEY=atmo_your_real_key
ENV ATMOSPORE_API_KEY=placeholder-set-real-key-at-runtime

ENTRYPOINT ["atmospore-mcp"]
