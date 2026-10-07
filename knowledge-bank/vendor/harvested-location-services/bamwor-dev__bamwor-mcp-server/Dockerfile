# ============================================================
# Bamwor MCP Server — Isolated container
#
# This container is 100% independent from all other stacks.
# It does NOT access any database directly.
# It does NOT join any existing Docker network.
# All data comes from the Bamwor public REST API over HTTPS.
# ============================================================

FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build

# ---- Runtime stage ----
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Non-root user for security
RUN addgroup --system --gid 1001 mcpuser && \
    adduser --system --uid 1001 mcpuser

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

USER mcpuser

# MCP stdio transport uses stdin/stdout
# No ports exposed — this is intentional
# The container communicates via stdio, not HTTP

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD node -e "process.exit(0)"

CMD ["node", "dist/index.js"]
