# The stdio bridge, containerised, for clients and directories that install rather than
# connect.
#
# WHAT THIS IMAGE IS NOT. It is not the DFX exchange. The server lives at the URL in
# `bridge/dfx_mcp_stdio.py` and holds the data, the read plane and the payment ledger;
# nothing in this repository serves a single row. This image is one file that forwards
# JSON-RPC over a pipe to that URL and writes the answer back.
#
# So there is no credential here, nothing to leak and nothing to keep in sync: the tool
# list, the schemas and the coverage numbers are read from the live server on every
# `tools/list`, which is the reason a remote server was the right shape in the first
# place. An installed copy of this bridge does not go stale when DFX publishes a
# seventeenth event family. It cannot: it does not know what a family is.
#
# python:3.12-slim and the standard library only, matching the server. Fewer packages is
# a smaller supply chain, and this one is small enough to read in full before running it.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Non-root. The process opens one outbound HTTPS connection and reads a pipe.
RUN useradd --create-home --shell /usr/sbin/nologin dfx
WORKDIR /app
COPY --chown=dfx:dfx bridge/dfx_mcp_stdio.py /app/dfx_mcp_stdio.py
USER dfx

# The endpoint is overridable so a caller can point the bridge at a staging exchange
# without rebuilding. It defaults to production inside the script.
# ENV DFX_MCP_URL=https://exchange-production-9123.up.railway.app/mcp

# stdio, so no port is exposed and no healthcheck applies: the client IS the health
# check. It launches this, writes an `initialize`, and the answer comes back or does not.
ENTRYPOINT ["python3", "/app/dfx_mcp_stdio.py"]
