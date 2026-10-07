# Castlemap MCP server — container image.
#
# server.mjs reads the atlas from a local GeoJSON file (CASTLES_GEOJSON); on the
# VPS that points at the copy the site already deploys. Here the public copy is
# baked in at build time, so the image runs standalone — no mount, no API key.
# Rebuild to pick up a newer atlas.
#
# Build: docker build -t castlemap-mcp .
# Run:   docker run -p 8891:8891 castlemap-mcp   → http://localhost:8891/mcp
FROM node:22-alpine

WORKDIR /app
COPY server.mjs ./
ADD --chown=node:node https://thecastlemap.com/castles.geojson /app/castles.geojson

# server.mjs defaults to 127.0.0.1, which is unreachable from outside a container.
ENV CASTLES_GEOJSON=/app/castles.geojson \
    HOST=0.0.0.0 \
    PORT=8891

USER node
EXPOSE 8891
CMD ["node", "server.mjs"]
