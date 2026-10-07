# PRD: Vessel Traffic MCP Server

## 1. Summary

`vessel-traffic-mcp` is a read-only MCP server that exposes vessel position and maritime context to ChatGPT, Claude, Claude Code, and other MCP clients. It normalizes many AIS and ship-tracking providers behind one tool surface so a user can ask questions such as:

- "Where is vessel MMSI 123456789 now?"
- "Show vessels near Busan port within the last 30 minutes."
- "What is the latest known track and ETA context for this IMO?"
- "Which source provided this position, and how fresh is it?"
- "This uploaded master B/L only shows a vessel name. Which MMSI/IMO is the best match, and where is it now?"

The long-term goal is an integrated global vessel-location MCP, not a single-provider wrapper. The server should maintain a growing provider registry that covers free/open feeds, commercial APIs, regional government feeds, and authorized web-capture adapters. The system must prioritize authorized data access. Official APIs, open-data sources, and BYOK commercial API credentials are first-class. Browser-network capture is a controlled development workflow for services that present data in web UI but do not publish a suitable API, and only for operator-authorized sessions where terms allow that use.

The capture workflow should reuse lessons and reusable components from the sibling project `<api-capture-checkout>`. That project already implements a local-first browser API capture harness with Playwright control, XHR/fetch/HAR recording, session artifacts, replay validation, traffic IR, OpenAPI generation, a supervisor loop, pacing, and redaction-aware reporting. `vessel-traffic-mcp` should adapt those patterns for maritime sites rather than reinventing capture orchestration from scratch.

The default product model is bring-your-own-key (BYOK): each MCP user or organization connects API keys for vessel-data services they already subscribe to. Since most users will not buy paid AIS access before validating coverage, the initial runtime should also support free, open, trial, or community terrestrial AIS checks. Paid satellite/enterprise providers and authorized capture-assisted adapters are important expansion paths, but they should not block the basic "can this vessel be found with terrestrial AIS?" workflow.

MCP setup must work without paid API keys. In that mode the server uses configured terrestrial AIS sources first. When terrestrial sources return no data, stale data, or a coverage caveat suggesting satellite AIS or a paid provider is needed, tool responses should include provider signup or landing URLs so the user can obtain a key and attach it through BYOK.

The project must maintain an explicit provider discovery and capture backlog. The backlog starts in `docs/provider-catalog.md` and should be promoted into structured config as the implementation matures. Each candidate service must be classified by access class, auth mode, coverage, API documentation, cost/quota model, capture eligibility, implementation status, and source URLs before implementation work begins.

## 2. Background And Research Notes

The vessel-position ecosystem is fragmented. Some services offer official APIs, some offer free or community access with limits, and some expose useful data only in web applications.

Research snapshot, checked May 2026:

| Source | Access model | Notes |
| --- | --- | --- |
| MarineTraffic | Official API services | MarineTraffic documents AIS, events, ships database, voyage forecasts, and other API categories. Online plans do not automatically include API access. Source: https://support.marinetraffic.com/en/articles/9552659-api-services |
| MarineTraffic service docs | Official API docs | Public docs show endpoints such as `exportvesseltrack` and AIS API references. Source: https://servicedocs.marinetraffic.com/tag/AIS-API/ |
| VesselFinder | Official API | Vessel positions API returns AIS, voyage, and master data with JSON/XML output. Source: https://api.vesselfinder.com/docs/vessels.html |
| MyShipTracking | Official API with trial | Provides real-time vessel, zone, history, port, and fleet endpoints; trial API key is available with credit/rate limits. Source: https://api.myshiptracking.com/ |
| AISStream | Free WebSocket API, beta | Streams AIS messages over WebSocket. No SLA. Useful for live ingestion and area subscriptions. Source: https://aisstream.io/documentation.html |
| AISHub | Community API | Aggregated feed is available to members/contributors in XML/JSON/CSV; requests must not exceed once per minute. Source: https://www.aishub.net/api |
| Global Fishing Watch | API with token | Strong for vessel identity, fishing effort, and public registry context; not a universal low-latency global position API. Source: https://globalfishingwatch.org/our-apis/documentation |
| BarentsWatch / Norwegian Coastal Administration | Open regional AIS | Norwegian AIS data is free/open under Norwegian open-data licensing; regional coverage. Source: https://developer.barentswatch.no/docs/AIS/live-ais-api/ |
| OpenAIS | Open AIS-oriented API | Useful as an open/reference provider for specific data scopes. Source: https://open-ais.org/docs/API/ |
| NOAA MarineCadastre / USCG NAIS | Open historical AIS data | US AIS point data is useful for historical/reference workflows, but generally not low-latency vessel tracking. Source: https://www.fisheries.noaa.gov/inport/item/77594 |
| Spire Maritime | Commercial global AIS API | Satellite/terrestrial AIS with GraphQL/GWS, global ocean coverage, static/position/voyage data. Source: https://spire.com/maritime/solutions/standard-ais/ |
| ORBCOMM / CommTrace / exactEarth | Commercial satellite AIS | Satellite AIS data services for beyond-coastal vessel tracking. Source: https://api.commtrace.com/ |
| Datalastic, VesselAPI, Data Docked, Poseidon AIS, ais.now | Commercial/trial APIs | Useful paid/trial providers with documented or claimed REST APIs and broad maritime datasets. Validate current docs, pricing, and terms before adapter work. |
| Kpler / MarineTraffic / FleetMon, Windward, Pole Star, S&P Global Sea-web, Lloyd's List Intelligence | Commercial maritime intelligence | Candidate enterprise sources for future BYOK adapters; availability and terms must be verified per account. |
| AIS Friends and similar contributor networks | Community/free candidate APIs | Candidate providers where users contribute AIS feed or register for API access; terms and docs must be validated before implementation. |

`docs/provider-catalog.md` is the source of truth for this discovery inventory. PRD research notes summarize only the highest-priority sources.

## 3. Goals

1. Provide a provider-neutral MCP interface for vessel data.
2. Support both local stdio MCP and remote Streamable HTTP MCP.
3. Start with safe, documented providers and sanitized fixtures.
4. Add adapter tooling that can analyze authorized HAR/network captures without storing secrets.
5. Make every answer transparent about source, freshness, confidence, and coverage.
6. Keep the default server read-only and safe for AI assistants.
7. Support BYOK credentials so users or organizations can call paid APIs they subscribe to.
8. Resolve vessel names from uploaded documents such as master B/L and house B/L into MMSI/IMO candidates with confidence scoring.
9. Grow toward a global provider registry that can support nearly every practical vessel-location source through adapters.
10. Prepare the project for open-source release and discoverable installation from Claude/Codex-oriented MCP/plugin surfaces.

## 4. Non-Goals

- Do not bypass authentication, paywalls, CAPTCHA, bot defenses, account limits, or provider rate limits.
- No bypassing of paywalls, login gates, CAPTCHA, bot detection, or rate limits.
- No credential collection or hidden browser automation against third-party accounts.
- No safety-critical navigation claims.
- No default live calls to paid providers in CI.
- No redistribution of provider data beyond the user's authorized use.

## 5. Users

- Maritime analysts who need natural-language access to vessel data.
- Logistics teams tracking vessel movement and port-call context.
- Developers who want a provider-neutral MCP wrapper around AIS data.
- Operators testing whether a free/open provider covers their region or fleet.

## 6. Product Surface

### 6.1 MCP Tools

Initial tools:

- `vessel_search`: search by name, MMSI, IMO, callsign, or provider-specific ID.
- `vessel_name_resolve`: resolve a possibly messy vessel name to ranked MMSI/IMO candidates using aliases, provider search, static registries, voyage context, and confidence scoring.
- `document_vessel_lookup`: accept text extracted from documents such as master B/L, house B/L, booking confirmations, arrival notices, and shipping instructions; extract likely vessel names/voyage numbers/ports and return ranked vessel candidates plus latest positions.
- `vessel_position`: latest known position for MMSI/IMO/provider ID.
- `vessel_area`: vessels inside a bounding box or named area.
- `vessel_track`: recent position history for a vessel when supported.
- `port_calls`: recent port-call events by vessel or port when supported.
- `provider_status`: configured providers, auth state, quota/rate hints, and feature support.
- `data_sources`: list available source adapters and caveats.
- `credential_profiles`: list configured credential profile labels, provider type, scope, and health without exposing secret values.

All tool outputs must include:

- `source`: provider name and adapter version.
- `retrievedAt`: server retrieval timestamp.
- `observedAt`: provider/AIS observation timestamp when available.
- `freshnessSeconds` or `staleReason`.
- `coverage`: terrestrial/satellite/regional/open-data caveat where known.
- `confidence`: normalized confidence label or score where feasible.
- `upgradeHints`: optional provider landing URLs and reasons when a paid/satellite provider is likely needed.

### 6.2 Transports

- `stdio`: local use with Claude Desktop, Claude Code, and MCP inspectors.
- `streamable-http`: remote MCP endpoint for ChatGPT connectors, Claude Messages API MCP connector, and hosted deployments.
- Optional compatibility `sse`: only if needed by a target client.

### 6.3 Provider Strategy

Provider adapters should implement:

```ts
interface VesselDataProvider {
  id: string;
  capabilities(): ProviderCapabilities;
  status(): Promise<ProviderStatus>;
  searchVessels(input: VesselSearchInput): Promise<VesselSearchResult[]>;
  getLatestPosition(input: VesselIdentifier): Promise<VesselPositionResult>;
  getArea(input: AreaQuery): Promise<VesselPositionResult[]>;
  getTrack(input: TrackQuery): Promise<VesselTrackResult>;
  getPortCalls(input: PortCallQuery): Promise<PortCallResult>;
}
```

Implementation priority:

1. `fixture`: deterministic local fixture provider for tests.
2. `aisstream`: live stream/cache adapter for free WebSocket AIS messages, used for first-pass terrestrial/global receiver-network checks.
3. `aishub`: member API adapter with strict one-minute throttling.
4. `barentswatch`: regional open AIS adapter.
5. `myshiptracking`: trial/paid REST adapter with credit-aware metadata.
6. `commercial-byok`: adapter family for paid providers where the user supplies their own key, token, account credential, or OAuth grant.
7. `capture-fixture`: sanitized captured-response adapter for authorized web-only services, disabled for live runtime by default.

Runtime routing priority:

1. Use an explicitly requested `provider` and `credentialProfile` when the user has supplied credentials for a paid or enterprise service.
2. If no paid profile is configured, try free/open/trial terrestrial AIS providers first so the user can validate whether the target vessel is visible before buying data.
3. If terrestrial AIS is stale, missing, or outside coverage, return structured no-data plus upgrade hints with signup/landing URLs for relevant paid/satellite providers.
4. Escalate to paid satellite/commercial providers only when credentials exist and the request asks for that source or a fallback policy allows paid routing.
5. Use capture fixtures only for deterministic tests and adapter development; never use browser capture as an implicit live fallback.

### 6.4 BYOK Credential Model

The MCP must allow users and organizations to use paid APIs directly, but it must not casually expose those keys inside chat transcripts.

Supported modes:

1. **Server credential profiles**: operator configures provider keys in environment variables or encrypted config. MCP users refer to a profile label such as `marineTraffic-prod` or `spire-sandbox`.
2. **Per-user credential profiles**: hosted deployments store each user's API credentials encrypted at rest and scoped to that user/workspace.
3. **One-time request credential**: advanced mode where a user provides a key for a single tool call. The key is redacted immediately, never echoed, never logged, and never persisted. This mode should be disabled by default for hosted deployments.
4. **OAuth/dynamic client registration**: future path for providers that support delegated authorization.

Credential rules:

- Tool responses may show provider label, account class, quota state, and expiration hint, but never the raw key.
- The server must support routing by `provider`, `credentialProfile`, and `fallbackPolicy`.
- Default provider order should prefer explicitly requested paid profiles when present, but otherwise start with free/open/trial terrestrial AIS checks before suggesting paid providers with signup URLs.
- Quota/cost metadata should be surfaced before broad area/bulk calls when a provider charges per credit.

### 6.5 Vessel Name Resolution For B/L Workflows

Common workflow:

1. User uploads a master B/L, house B/L, arrival notice, or booking document to ChatGPT/Claude.
2. The model extracts text and calls `document_vessel_lookup` or `vessel_name_resolve`.
3. The MCP server identifies candidate vessel names, voyage numbers, carrier names, ports, dates, container numbers when present, and other context.
4. The resolver searches provider registries and live AIS providers, ranks MMSI/IMO candidates, and returns a confidence explanation.
5. If ambiguous, the model asks the user to choose or supplies top candidates with evidence.

Resolution signals:

- Exact and fuzzy vessel name match, including punctuation, prefixes, suffixes, and transliteration variants.
- IMO/MMSI/callsign if present anywhere in text.
- Carrier/line, voyage number, POL/POD, transshipment ports, ETA/ETD, and document date.
- Vessel type and flag from static registries.
- Recent port calls and track near the ports/dates in the document.
- Provider agreement across multiple sources.

The resolver must return `needsConfirmation: true` when candidates are close or the document context is insufficient.

### 6.6 Capture Harness Reuse From api-capture

The sibling project `<api-capture-checkout>` is the reference implementation for browser-only API capture. Reuse or port these design ideas:

- Site profiles under `config/sites/*` for domain-specific login, scope, session-loss detection, pacing, and safety policy.
- Playwright browser control with XHR/fetch network hooks and HAR backup.
- Session outputs such as `api_log.jsonl`, `network.har`, `events.jsonl`, and generated `openapi.json`.
- Replay validation that calls captured requests with a fresh authorized session and compares HTTP status, business success, and response shape.
- A normalized traffic IR such as `traffic.ndjson` and `traffic_summary.json` before generating provider adapters or OpenAPI specs.
- Worker separation: capture worker, replay worker, schema worker, redaction worker, and report worker.
- Supervisor pacing so broad site exploration does not hammer providers or repeat low-yield actions.
- Secret scanner/redactor before any backup, dashboard export, fixture generation, or commit.

The implementation must not import or expose `api-capture` raw sessions, logs, `.env` files, cookies, or provider credentials. Maritime capture artifacts must live under this project and must be ignored by git until sanitized.

## 7. Authorized Capture Workflow

Some services may show data in a browser without publishing a suitable public API. This project may include a capture-assisted adapter workflow with these limits:

1. The operator manually exports HAR or JSON samples from a browser session they are authorized to use.
2. The importer rejects raw files containing unsanitized `Authorization`, `Cookie`, `Set-Cookie`, known token names, or API keys.
3. The sanitizer produces redacted fixtures and endpoint fingerprints only.
4. Generated adapter candidates remain disabled until a human adds provider-specific authorization notes.
5. The runtime must not replay private cookies or browser sessions.
6. The runtime must enforce configured rate limits and provider terms.

This is a development workflow, not a scraping bypass feature.

## 7.1 Provider Discovery And Capture Execution Program

Autonomous development should treat provider discovery as a first-class workstream:

1. Expand `docs/provider-catalog.md` from web research and official provider documentation.
2. Convert the catalog into structured provider metadata for implementation planning.
3. Prioritize official APIs, open APIs, trial APIs, and BYOK commercial APIs before web capture.
4. Keep the initial no-paid-key path focused on free/open/community terrestrial AIS so users can test coverage before buying a subscription.
5. For web-only services, create a capture ticket only after documenting authorization assumptions, terms review status, allowed origins, forbidden actions, rate limits, and expected endpoints.
6. Use `<api-capture-checkout>` as the reference for execution: site profiles, local browser control, XHR/fetch capture, HAR backup, replay validation, traffic IR, OpenAPI/schema generation, worker separation, supervisor pacing, and redaction.
7. Never run live capture in default CI or default autodev verification. Capture execution requires an operator-authorized browser session or explicit credentials.
8. Store raw capture artifacts only in ignored private paths and promote only sanitized fixtures, endpoint fingerprints, and adapter tickets into git.

## 8. Configuration

Environment variables:

- `VESSEL_MCP_TRANSPORT`: `stdio` or `http`.
- `VESSEL_MCP_HTTP_HOST`, `VESSEL_MCP_HTTP_PORT`.
- `VESSEL_MCP_AUTH_TOKEN`: optional bearer token for remote HTTP.
- Provider-specific keys such as `AISSTREAM_API_KEY`, `AISHUB_USERNAME`, `MYSHIPTRACKING_API_KEY`, `BARENTSWATCH_CLIENT_ID`.

Configuration file:

- `config/providers.example.json` documents providers, priority, rate limits, cache TTL, and feature flags.
- Real config files must be ignored by git.

## 8.1 Open Source And Distribution

The project should be prepared for public open-source release after the security model is mature:

- Include a clear license, contribution guide, security policy, code of conduct if desired, and secret-reporting process.
- Keep all examples runnable without paid keys by using fixtures and terrestrial AIS fallback.
- Publish package metadata, README keywords, GitHub topics, and MCP client setup docs so users can find the project by searches such as "vessel AIS MCP", "ship tracking MCP", "MarineTraffic MCP", and "Claude vessel tracking".
- Provide Claude Desktop, Claude Code, ChatGPT remote MCP, generic MCP Inspector, and Codex setup docs.
- Add Codex plugin metadata or marketplace manifest when ready so the MCP can be discoverable/installable from Codex plugin search.
- Add Claude-oriented installation metadata if a supported Claude MCP/plugin registry path is available; otherwise keep documented local/remote MCP setup as the canonical integration.
- Do not publish any provider credentials, private captures, raw HAR files, or service-specific session artifacts.

## 9. Quality And Verification

Required gates:

- `npm run lint`
- `npm test`
- `npm run build`

Test categories:

- Unit tests for input validation and normalized models.
- Adapter tests using sanitized fixtures.
- MCP tool tests through in-memory or stdio transport.
- HTTP transport tests with local server and fake bearer token.
- Live-provider smoke tests only when explicitly enabled by environment.

## 10. Milestones

### M0: Project Scaffold

Create TypeScript package, docs, autodev requirements, and verification scripts.

### M1: MCP Core

Implement stdio and Streamable HTTP MCP transports with read-only tool registration and fixture provider.

### M2: Provider Layer

Implement provider interface, normalized models, source metadata, caching, throttling, and provider status.

### M3: Free/Open Providers

Add AISStream, AISHub, and BarentsWatch/OpenAIS support where credentials/terms allow.

### M4: Capture-Assisted Adapter Tooling

Adapt the `<api-capture-checkout>` harness patterns for maritime sites. Add sanitized HAR/import tooling, traffic IR generation, replay validation, schema inference, redaction tests, and disabled-by-default capture fixtures.

### M5: Client Setup

Document ChatGPT remote MCP setup, Claude Desktop stdio setup, Claude Code MCP setup, and hosted deployment notes.
