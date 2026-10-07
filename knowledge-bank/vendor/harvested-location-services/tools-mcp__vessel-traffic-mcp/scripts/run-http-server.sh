#!/usr/bin/env sh
set -eu

if [ ! -f dist/index.js ]; then
  npm run build
fi

: "${VESSEL_MCP_TRANSPORT:=http}"
: "${VESSEL_MCP_HTTP_HOST:=127.0.0.1}"
: "${VESSEL_MCP_HTTP_PORT:=3000}"

export VESSEL_MCP_TRANSPORT
export VESSEL_MCP_HTTP_HOST
export VESSEL_MCP_HTTP_PORT

exec node --enable-source-maps dist/index.js
