# Container image for the Pedra MCP server.
#
# Primarily used by registries (e.g. Glama) to build the server, start it, and
# verify it answers MCP introspection (tools/list). The server checks for
# PEDRA_API_KEY at startup; tools/list makes no API calls, so a placeholder key
# is enough to boot and introspect. Real usage injects a real key via the MCP
# client's env (which overrides the one below).

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
# Placeholder so the server boots for introspection; override with a real key.
ENV PEDRA_API_KEY=placeholder
ENTRYPOINT ["node", "dist/index.js"]
