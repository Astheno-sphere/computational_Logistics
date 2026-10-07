# SMKlog Parcel Shipping Rates — stdio bridge to the hosted MCP endpoint.
# No dependencies, no build step, no keys: the image only forwards JSON-RPC
# from stdin to https://quote-api.smklog.com/mcp and writes the answers back.
#
#   docker build -t smklog-parcel-shipping-rates-mcp .
#   docker run -i --rm smklog-parcel-shipping-rates-mcp
FROM node:22-alpine
WORKDIR /app
COPY package.json initialize.json tools.json ./
COPY bin ./bin
ENV SMKLOG_MCP_URL=https://quote-api.smklog.com/mcp
ENTRYPOINT ["node", "/app/bin/smklog-parcel-shipping-rates-mcp.mjs"]
