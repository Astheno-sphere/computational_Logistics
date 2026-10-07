# syntax=docker/dockerfile:1.7

# vessel-traffic-mcp container image (F6.AC2).
#
# This image runs the Streamable HTTP MCP transport. TLS is terminated
# OUTSIDE this container by a reverse proxy, load balancer, or platform
# edge (nginx, Caddy, Cloud Run, ALB, Fly proxy, etc.). The container
# itself only speaks HTTP on the bound port and never serves a public
# /mcp without a bearer token in production.
#
# See docs/runbooks/deployment-https.md for the supported HTTPS
# topologies and operator checklist.

# ---------- build stage ----------
FROM node:22-bookworm-slim AS build

WORKDIR /app

# Install dev+prod deps deterministically from the lockfile so the
# TypeScript build is reproducible.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# Compile TypeScript. tsconfig + src are the only inputs the build
# needs; everything else is excluded by .dockerignore so secrets and
# captures can never enter the image.
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Drop dev dependencies before copying node_modules into the runtime
# image so the runtime layer ships production deps only.
RUN npm prune --omit=dev

# ---------- runtime stage ----------
FROM node:22-bookworm-slim AS runtime

# Run as the unprivileged "node" user that the official image already
# provides. Never run the MCP server as root.
ENV NODE_ENV=production \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    VESSEL_MCP_TRANSPORT=http \
    VESSEL_MCP_HTTP_HOST=0.0.0.0 \
    VESSEL_MCP_HTTP_PORT=3000

WORKDIR /app

COPY --from=build --chown=node:node /app/package.json ./package.json
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/dist ./dist

USER node

EXPOSE 3000

# Public health endpoint. Does not require the bearer token and does
# not expose provider credential state.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.VESSEL_MCP_HTTP_PORT||3000)+'/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

ENTRYPOINT ["node", "--enable-source-maps", "dist/index.js"]
