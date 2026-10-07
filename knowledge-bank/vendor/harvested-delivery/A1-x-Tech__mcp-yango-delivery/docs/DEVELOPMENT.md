# Development

## Requirements

- Node.js 20+ (the published package ships compiled `dist/`; `npx` needs no separate
  install). CI runs the suite on Node 20, 22 and 24.

## Commands

```bash
npm install
npm run dev        # run from source with tsx watch
npm test           # unit tests + dist smoke (node:test), no network
npm run typecheck  # type-check src + tests (no emit)
npm run build      # clean dist/ and compile with tsc
npm run smoke      # live READ-ONLY call: claims/search with limit 1
```

## Local run

```bash
npm run build
YANGO_DELIVERY_TOKEN=... node dist/index.js
# optional: YANGO_DELIVERY_BASE_URL, YANGO_DELIVERY_LANG,
#           YANGO_DELIVERY_TIMEOUT_MS, YANGO_DELIVERY_MAX_RETRIES
```

`npm run smoke` needs the same credentials and makes one live read (no writes).
Remember this is a **write API** overall: the unit suite never touches the
network, but manual testing with a real token can create real claims — prefer
`check_price`/`search_claims` when poking around. No test/sandbox environment
is documented for this API, so accepted claims order real couriers.

## Tests

Unit tests mock `globalThis.fetch` (client) or use a fake server + mock/real client
(tools), so the whole suite runs offline. Put a `*.test.ts` next to the code it
covers; `npm run typecheck && npm test` is the gate (also run by `prepublishOnly`).
`test/dist-smoke.test.js` additionally exercises the built `dist/` artifact,
including a real MCP handshake over stdio.

## Usage telemetry

The server sends anonymous events to `usage.gistrec.cloud` (`server_start` when a
client connects to a configured install, `unconfigured_start` with a reason code
when the token is missing, `tool_call` with the tool **name** and `startup_failed`
with a reason code) to count active installations and tool demand. An event carries only
depersonalized technical fields: a random installation id
(`~/.config/mcp-yango-delivery/instance-id`), the package version, the AI client
name and version from the MCP handshake, the Node.js version and the OS.

The token, account data, tool arguments and request texts are never sent or
stored (implementation: `src/telemetry.ts`). Sends happen in the background with
a 2-second timeout and are silently skipped on any error. Opt out for all
Ask Ads MCP servers at once: `ASKADS_TELEMETRY=0`.
