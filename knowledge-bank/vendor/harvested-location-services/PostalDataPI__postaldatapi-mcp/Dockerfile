# PostalDataPI MCP Server
#
# Minimal container for running the postaldatapi-mcp MCP server in
# sandboxed environments (e.g., Glama.ai registry health checks).
#
# MCP servers communicate over stdio, not TCP, so no ports are exposed.
# The server starts and responds to MCP introspection requests (initialize,
# tools/list, tools/call schemas) without requiring a POSTALDATAPI_KEY.
# An API key is only needed to actually execute tool calls against the
# live PostalDataPI API, which is set at runtime via environment variable.

FROM python:3.12-slim

WORKDIR /app

# Copy source files from the build context
COPY pyproject.toml README.md LICENSE ./
COPY postaldatapi_mcp.py ./

# Install the MCP server from local source. --no-cache-dir keeps the
# image small and --no-deps would skip transitive deps, so we don't use it.
RUN pip install --no-cache-dir .

# API key is optional at startup. The server will log a warning and
# start normally; tool calls will return an informative error until a
# key is provided. Override at runtime: `docker run -e POSTALDATAPI_KEY=xxx`
ENV POSTALDATAPI_KEY=""

# MCP servers use stdio for protocol communication. No ports exposed.
ENTRYPOINT ["postaldatapi-mcp"]
