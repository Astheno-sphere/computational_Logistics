#!/usr/bin/env bash
# DFX Real Estate MCP: everything below is free and needs no key.
set -euo pipefail
DFX=https://exchange-production-9123.up.railway.app/mcp

call () {   # call <tool> <json-arguments>
  curl -s "$DFX" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",
         \"params\":{\"name\":\"$1\",\"arguments\":$2}}"
}

echo "== the schemas, with no handshake =="
curl -s "$DFX" | head -c 400; echo

echo "== what can this thing answer? =="
call what_can_dfx_answer '{"objective":"commercial mortgages maturing in Ohio next year"}'

echo "== resolve an address =="
call resolve_address '{"address":"100 Binney St","city":"Cambridge","state":"MA"}'

echo "== measured coverage and the known gaps =="
call dfx_coverage '{}'

echo "== free maturity EVENTS (the paid tool returns the LOAN) =="
call search_property_events '{"event_type":"LOAN_MATURITY_SCHEDULED","state":"OH","within_days":548}'

echo "== a quote for the paid tool. This charges nothing. =="
call debt_maturity_schedule '{"state":"OH"}'
