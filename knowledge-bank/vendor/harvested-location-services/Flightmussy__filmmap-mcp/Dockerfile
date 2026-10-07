# FilmMap MCP server — container image.
#
# server.mjs reads the atlas from a local JSON file (ATLAS_JSON); on the VPS
# that points at the copy the site already deploys. Here the public copy is
# baked in at build time, so the image runs standalone — no mount, no API key.
# Rebuild to pick up a newer atlas.
#
# Build: docker build -t filmmap-mcp .
# Run:   docker run -p 8896:8896 filmmap-mcp   → http://localhost:8896/mcp
FROM node:22-alpine

WORKDIR /app
COPY server.mjs ./
ADD --chown=node:node https://thefilmmap.com/data/atlas-compact.json /app/atlas-compact.json

# server.mjs defaults to 127.0.0.1, which is unreachable from outside a container.
ENV ATLAS_JSON=/app/atlas-compact.json \
    HOST=0.0.0.0 \
    PORT=8896

USER node
EXPOSE 8896
CMD ["node", "server.mjs"]
