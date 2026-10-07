# Dockerfile for the qa-probe MCP server.
#
# Used by MCP registries (e.g. glama.ai) to start the server in a container and
# verify it responds to MCP introspection. The qa-probe MCP server needs a config
# file to start; for listing tools a minimal config (just baseUrl) is enough --
# the tools only require a real target when actually invoked.

FROM node:20-slim

WORKDIR /app

# Production dependencies only. Dev deps are test-only; the optional `playwright`
# dependency is lazy-loaded (guarded require in src/analyze/cdp-driver.js) and is
# not needed to start the server or list tools, so it is skipped to keep the
# image small and the build fast.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --omit=optional

# Application source.
COPY . .

# Minimal config so `qa-probe mcp` can start. baseUrl is the only required field;
# this is a placeholder target used purely so the server boots and can advertise
# its tools to an MCP client.
RUN printf "module.exports = { baseUrl: 'http://localhost:8000' };\n" > /app/qa-probe.config.js

# Speak MCP over stdio.
ENTRYPOINT ["node", "bin/qa-probe.js", "mcp", "--config", "/app/qa-probe.config.js"]
