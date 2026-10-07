# Off-Nadir Delta stdio MCP server.
# Multi-stage: build the TypeScript, then ship a slim runtime image whose
# entrypoint speaks MCP over stdio (this is what registry introspection runs).
# `--ignore-scripts` is used so the `prepare` build hook (meant for `npm publish`)
# does not fire at the wrong time inside the image build.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* tsconfig.json ./
COPY src ./src
RUN npm ci --ignore-scripts --no-audit --no-fund || npm install --ignore-scripts --no-audit --no-fund
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund || npm install --omit=dev --ignore-scripts --no-audit --no-fund
COPY --from=build /app/dist ./dist
# stdio transport: no ports. Introspection works without credentials;
# metered tool calls require OFFNADIR_DELTA_API_KEY at runtime.
ENTRYPOINT ["node", "dist/index.js"]
