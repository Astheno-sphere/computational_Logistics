# Build stage
#
# node:24-alpine is the ACTIVE LTS line, not the newest tag — roughly half of all
# Node majors never become LTS, so "newest" and "supported" are different things.
# Only the major belongs in this note. A patch version written here would be
# falsified by the next digest bump, which would arrive red for a reason nobody
# needs to act on. CI checks the claim instead, on every run
# (.github/scripts/check-base-image-pin.sh): `node:lts-alpine` and
# `node:24-alpine` must resolve to the same digest, and the digest pinned below
# must be a Node 24 image. The day 24 leaves LTS, that fails.
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev --ignore-scripts

# Runtime
FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1
WORKDIR /app
ENV NODE_ENV=production

# CVE-2026-14456: the pinned base image carries OpenSSL 3.5.7-r0, and Alpine's
# fixed 3.5.8-r0 has not been rebuilt into node:24-alpine yet. Upgrading these
# two packages by name rather than running a blanket `apk upgrade` keeps the
# rest of the image exactly as the digest pins it. Drop this once the base
# image ships the fix.
RUN apk add --no-cache --upgrade libcrypto3 libssl3

# The runtime only ever executes `node dist/index.js` — remove the bundled npm,
# and the yarn and corepack the base image ships beside it, instead of chasing
# CVEs in their vendored dependencies.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
    /usr/local/lib/node_modules/corepack /usr/local/bin/corepack \
    /opt/yarn-v* /usr/local/bin/yarn /usr/local/bin/yarnpkg

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
# The server reports its version from package.json at runtime; the lockfile
# stays out of the image.
COPY package.json ./

# Ownership proof for the MCP Registry: must match server.json's name exactly.
LABEL io.modelcontextprotocol.server.name="io.github.ni-c/osm-mcp"

# Drop root: the node image ships an unprivileged `node` user (uid 1000).
USER node

# stdio transport only — no port, no healthcheck. The server needs no
# credentials at all; ORS_API_KEY merely switches the routing engine.
ENTRYPOINT ["node", "dist/index.js"]
