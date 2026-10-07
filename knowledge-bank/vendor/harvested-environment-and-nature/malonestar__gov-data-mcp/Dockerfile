# Glama and other directories start the server and issue an MCP introspection
# request to verify it is real. The server lists tools without touching the
# network, so tools/list succeeds with no APIFY_TOKEN; only tools/call needs one.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund

COPY src/ ./src/
COPY README.md LICENSE ./

ENTRYPOINT ["node", "src/index.js"]
