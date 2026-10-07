# Vessel Provider Catalog

Research snapshot checked on 2026-05-15. This catalog is the working backlog
for official API adapters, open-data adapters, free/community APIs, BYOK
commercial adapters, enterprise providers, and authorized capture candidates.
It is intentionally conservative: an entry being listed here does not mean the
project may scrape it or bypass access controls.

## Product Priority

The default product model is BYOK: each MCP user or organization connects API
keys for the vessel-data services they already subscribe to. Since most users
will not buy paid AIS access before validating coverage, the first practical
fallback is free, open, trial, or community terrestrial AIS. Satellite AIS and
enterprise providers are valuable when the user supplies credentials, but they
should not block the basic "can I find this vessel at all?" workflow.

Provider routing should therefore prefer:

1. An explicitly requested BYOK credential profile.
2. Free/open/trial terrestrial AIS providers for initial coverage checks.
3. Community/regional sources with clear rate limits and terms.
4. Paid commercial/satellite providers when the user has supplied credentials.
5. Authorized capture fixtures only for development and adapter discovery, never
   as a default runtime bypass.

When no API key is configured, MCP tools should still run against configured
terrestrial AIS sources. If the result is stale, missing, outside terrestrial
coverage, or likely requires satellite AIS, the response should include
provider-specific signup or landing URLs from this catalog so the user can
obtain their own key and reconnect through BYOK.

## F4.AC5 Catalogue Axes

PRD acceptance criterion F4.AC5 requires this catalogue to document global
provider coverage, auth mode, cost/quota model, supported capabilities, and
implementation status for every entry. The five axes are kept in lock-step
between the human-readable markdown sections below and the structured
`config/provider-catalog.example.json` so docs-review reviewers, adapter
ticketing, and the credential-profile loader read the same source of truth.

| Axis | Where it lives in this doc | Where it lives in `config/provider-catalog.example.json` |
| --- | --- | --- |
| Global provider coverage | "Coverage" column of every category table below | `entries[].coverage` (free-text) plus `entries[].tier` (`fixture` / `terrestrial-open` / `community` / `paid-commercial`) |
| Auth mode | Implied by category placement (Official APIs, Free / Community APIs, Commercial BYOK APIs, Enterprise Providers, Web-Only Capture Candidates) and called out in entry notes | `entries[].auth.mode` plus `entries[].auth.required`, `entries[].auth.profileFields`, and `entries[].auth.envVars` |
| Cost / quota model | Category section intro describes the cost class; per-provider quota/throttle quirks appear in entry notes | `entries[].cost.model` (`fixture` / `free` / `open-data` / `community` / `trial` / `freemium` / `credit-based` / `subscription` / `enterprise`) plus `entries[].cost.quotaNote` |
| Supported capabilities | Implied by the per-row "Coverage" column ("positions", "tracks", "port calls", "carrier schedules", "vessel schedules", etc.) and the tool surface listed in `README.md` | `entries[].capabilities[]` (subset of `provider_status`, `data_sources`, `vessel_search`, `vessel_position`, `vessel_area`, `vessel_track`, `port_calls`, `carrier_schedule_search`, `vessel_schedule`) |
| Implementation status | "Implementation status" row underneath each category table (see one-liners below) | `entries[].implementationStatus` (`fixture` / `not_started` / `planned` / `in_progress` / `implemented` / `capture_only` / `discovery_only`) |

The structured JSON is the machine-readable contract for the five axes. Any
new provider added to a markdown table below must land an entry in
`config/provider-catalog.example.json` covering the same five axes — the
`provider-catalog.test.js`, `provider-catalog-categories.test.js`,
`provider-catalog-live-gating.test.js`, and `provider-catalog-ac5-axes.test.js`
tests fail closed if the two views drift.

## Capture And Access Policy

- Prefer official APIs and open-data feeds.
- Use BYOK for commercial APIs when the user or operator supplies valid
  credentials.
- Use browser/API capture only for operator-authorized sessions and only where
  the provider terms allow that use.
- Never commit raw HAR files, browser sessions, cookies, bearer tokens, API
  keys, `.env` files, or private provider responses.
- Store raw operator capture output only under ignored private paths such as
  `captures/private/`.
- Commit only sanitized fixtures, endpoint fingerprints, traffic IR summaries,
  schema summaries, and provider-adapter tickets.

## Provider Categories

The catalog organizes vessel-data providers into the six AC1-aligned categories
below. Each section is the authoritative list for its category and the source
URLs that adapter tickets, credential-profile loaders, and the structured
`config/provider-catalog.example.json` consume. A single provider may appear in
more than one category — for example, MarineTraffic is both an Official API and
a Commercial BYOK API — because adapter, credential, and capture workflows are
gated on different axes.

### Official APIs

Providers that publish official documented APIs. Prefer the official API
surface over any other access path; capture against these providers is allowed
only with explicit operator authorization and only where provider terms permit
it. Source URLs point to first-party developer docs.

| Provider | Coverage | Source |
| --- | --- | --- |
| MarineTraffic / Kpler | Global AIS, events, ports, vessel data depending on plan | https://servicedocs.marinetraffic.com/ |
| MarineTraffic `exportvesseltrack` | Vessel historical track endpoint family | https://servicedocs.marinetraffic.com/tag/Vessel-Historical-Track |
| VesselFinder | Terrestrial AIS positions, voyage, and master data | https://api.vesselfinder.com/docs/vessels.html |
| MyShipTracking | Terrestrial AIS, vessel position, zones, history, ports | https://api.myshiptracking.com/docs/vessel-current-position-api |
| SeaRates Ship Schedules API | Carrier schedules by points, vessel, and port with SCAC filters; API key via `X-API-KEY` | https://docs.searates.com/reference/schedules/available-carriers |
| Linescape Schedule API | Customer REST API for carriers, vessels, port pairs, voyages, sailings, and port calls | https://linescape-downloads.s3.amazonaws.com/schedule-api/latest/overview.html |
| Routescanner Connect API | Multimodal voyage options by LOCODE/terminal/operator with lead time and emissions | https://docs.routescanner.com/operation/operation-getvoyages |
| Spire Maritime | Global satellite and terrestrial AIS data products | https://spire.com/maritime/solutions/standard-ais/ |
| ORBCOMM / CommTrace / exactEarth | Beyond-coastal satellite AIS | https://api.commtrace.com/ |
| Datalastic | Trial/commercial API for live ship tracking, vessel finder, radius traffic, and vessel history | https://datalastic.com/api-reference/ |
| Global Fishing Watch | Token API for fishing activity, vessel identity search, and public registry context | https://globalfishingwatch.org/our-apis/documentation |

Implementation status: see `entries[].implementationStatus` in `config/provider-catalog.example.json` for each provider above (MarineTraffic `shipsearch`, `exportvessel`, `exportvesseltrack`, `portcalls`, VesselFinder, SeaRates Ship Schedules, Routescanner Connect, VesselAPI, Data Docked, Datalastic, and Global Fishing Watch vessel search are `implemented` behind redacted BYOK profiles; Linescape remains `planned`; other rows are `not_started` or `discovery_only`).

### Open-Data Sources

Governmental, regional, and open-standards data feeds. Coverage is typically
narrower (national waters, historical archives, or special-purpose datasets)
than commercial providers but is licensed for open reuse, sometimes after
account registration.

| Provider | Coverage | Source |
| --- | --- | --- |
| BarentsWatch / Norwegian Coastal Administration | Norway/regional real-time AIS via open data | https://www.barentswatch.no/en/articles/open-data-via-barentswatch/ |
| OpenAIS | Open AIS-oriented API; coverage and freshness vary by contributor | https://open-ais.org/docs/API/ |
| NOAA MarineCadastre / USCG NAIS | United States historical AIS, generally delayed and bulk-distributed | https://www.fisheries.noaa.gov/inport/item/77594 |
| Global Fishing Watch | Public registry context and fishing activity (token-gated open API) | https://globalfishingwatch.org/our-apis/documentation |
| Regional government AIS portals | Various national/regional portals; prioritize official open APIs and static/historical datasets before any UI capture | Discovery only — see Provider Discovery Backlog below |

Implementation status: see `entries[].implementationStatus` in `config/provider-catalog.example.json` (BarentsWatch and Global Fishing Watch vessel search are `implemented`; OpenAIS, NOAA MarineCadastre, and regional portals remain `discovery_only`).

### Free / Community APIs

Free or community-contributor APIs. Typically require account registration or
feed contribution and enforce strict rate limits. Treat them as the no-paid-key
fallback for terrestrial AIS coverage probes.

| Provider | Coverage | Source |
| --- | --- | --- |
| AISStream | Best-effort global terrestrial AIS WebSocket stream | https://aisstream.io/ |
| AISHub | Contributor-pooled terrestrial AIS network; one-request-per-minute member API | https://www.aishub.net/api |
| AIS Friends | Community/contributor public map bounding-box positions; area feed only, no identity resolver | https://www.aisfriends.com/ |

Implementation status: see `entries[].implementationStatus` in `config/provider-catalog.example.json` (AISStream, AISHub, and the AIS Friends `vessel_area` adapter are `implemented`; AIS Friends remains opt-in while terms, quota, and redistribution policy are reviewed).

### Commercial BYOK APIs

Paid commercial APIs that require user-supplied credentials via redacted BYOK
credential profiles. Default verification does not call these; live tests are
gated behind `VESSEL_MCP_LIVE_TEST_*` flags and `VESSEL_MCP_PROFILE_*`
credential slots so the standard `npm test` run never reaches a paid endpoint.

| Provider | Coverage | Source |
| --- | --- | --- |
| MarineTraffic / Kpler | Global AIS, events, ports, vessel data depending on plan | https://servicedocs.marinetraffic.com/ |
| MarineTraffic `exportvesseltrack` | Vessel historical track endpoint family | https://servicedocs.marinetraffic.com/tag/Vessel-Historical-Track |
| VesselFinder | Terrestrial AIS positions, voyage, and master data | https://api.vesselfinder.com/docs/vessels.html |
| MyShipTracking | Trial/commercial API for terrestrial AIS position, zone, history, ports | https://api.myshiptracking.com/docs/vessel-current-position-api |
| Spire Maritime | Commercial satellite/terrestrial AIS API; BYOK adapter candidate | https://spire.com/maritime/solutions/standard-ais/ |
| ORBCOMM / CommTrace / exactEarth | Commercial satellite AIS API; BYOK adapter candidate | https://api.commtrace.com/ |
| SeaRates Ship Schedules API | Ship schedules by points/vessel/port, carrier list, and usage endpoint | https://docs.searates.com/reference/schedules/available-carriers |
| Linescape Schedule API | Schedule data-on-demand API for sailings, voyages, vessels, port pairs, and port calls | https://docs.linescape.com/docs/api-usage/ |
| IQAX Big Schedules | Sailing schedules, vessel schedules, tracking context, alerts, and API integration candidates | https://product.iqax.com/en/products-bigs/ |
| Routescanner Connect API | Voyage options between locations, operators, transfers, lead time, and CO2e | https://docs.routescanner.com/operation/operation-getvoyages |
| VesselAPI | Commercial/trial maritime API; terrestrial AIS ship-tracking, area, historical positions, and port events; product overview at https://vesselapi.com/ship-tracking-api | https://vesselapi.com/docs/vessels |
| Data Docked | Vessel location, historical location, port calls, details by name, route planner, weather; product site at https://datadocked.com/ | https://docs.datadocked.com/api-reference/introduction |
| Datalastic | Live ship tracking, location traffic radius queries, vessel finder, and historical vessel data; product site at https://datalastic.com/ | https://datalastic.com/api-reference/ |
| Poseidon AIS | Vessel details, area/radius search, historical positions | https://poseidonais.com/ |
| ais.now | Commercial API/web platform candidate with REST API claims; validate docs, terms, and coverage before implementation | https://ais.now/ |
| FleetMon / Kpler | Commercial maritime intelligence; treat as BYOK or authorized capture candidate only after account-specific terms review | https://www.fleetmon.com/ |

Implementation status: see `entries[].implementationStatus` in `config/provider-catalog.example.json` (MarineTraffic `shipsearch`, `exportvessel`, `exportvesseltrack`, `portcalls`, VesselFinder, SeaRates Ship Schedules, Routescanner Connect, VesselAPI, Data Docked, and Datalastic are `implemented` behind redacted BYOK profiles; Linescape remains `planned`; the remaining commercial backlog entries are `not_started` or `discovery_only`).

### Enterprise Providers

Enterprise maritime intelligence platforms that typically require contract
negotiation and account-team onboarding before API access is granted. Capture
is blocked across enterprise providers — only BYOK adapters backed by an
explicit operator contract are permitted.

| Provider | Coverage | Source |
| --- | --- | --- |
| Windward | Enterprise maritime intelligence; satellite + terrestrial AIS plus risk overlays | https://windward.ai/ |
| Pole Star Global | Enterprise compliance/tracking provider; likely contract/API review required | https://www.polestarglobal.com/ |
| S&P Global Sea-web | Enterprise ship, ownership, casualty, and movement context candidate | https://www.spglobal.com/marketintelligence/en/solutions/products/sea-web |
| Lloyd's List Intelligence | Enterprise maritime intelligence and vessel movement context candidate | https://www.lloydslistintelligence.com/ |
| CargoSmart Sailing Schedule | Enterprise schedule-search surface with carrier, vessel, voyage, ETD/ETA, transit time, service, and facility details | https://www.cargosmart.com/onlinehelp/CustomerHelp/FlashHelp/CargoSmartHelp_All_Users/Sailing_Schedule/new_schedule_search.htm |

Implementation status: see `entries[].implementationStatus` in `config/provider-catalog.example.json` (all enterprise providers are `discovery_only` pending operator contract; capture is `blocked` across this category).

### Web-Only Capture Candidates

Sites that do not expose a first-class official API for the data we need, or
whose API access is restrictive enough that the operator-authorized web UI is
the only realistic discovery path. Capture only when provider terms allow it.
Always prefer an official API once one becomes available.

| Provider | Capture/API status |
| --- | --- |
| MyShipTracking web UI | Public browser endpoint candidate implemented as an opt-in adapter for autocomplete, selected-MMSI latest position, and bounding-box area rows. Prefer the official API for production contracts; public results must expose the MyShipTracking source URL. |
| ShipFinder | Public browser API candidate implemented as an explicit opt-in adapter for captured autocomplete and `GetShip` shapes; keep it out of default routing until terms/rate review and browser-verification behavior are settled. Structured catalog id: `shipfinder`. |
| ShipXplorer | Web UI/API candidate. Validate whether a supported ship API exists and whether UI capture is allowed. |
| MarineVesselTraffic / similar map sites | MarineVesselTraffic embeds AIS Friends public map data, but its own search autocomplete returned HTTP 403 in browser capture and must not be bypassed. |
| FleetMon web UI | Treat as BYOK or authorized capture candidate only after account-specific terms review (<https://www.fleetmon.com/>). |
| AIS Friends web UI | Public bounding-box map feed implemented as an explicit opt-in `vessel_area` adapter (`aisfriends`); validate terms, contribution requirements, quota, and redistribution policy before production use. |
| Tradelinx Schedule web UI | Public Korean logistics schedule candidate for FCL/LCL route lookup. Browser capture on 2026-05-18 found no-login schedule/detail endpoint shapes; `carrier_schedule_search` is implemented as an explicit opt-in public provider (`VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS=tradlinx`) and should preserve a user-facing source URL (`https://www.tradlinx.com/ko/schedule?tab=fcl`, `https://www.tradlinx.com/ko/schedule?tab=lcl`). |

Implementation status: web-only candidates are not part of the default routing
fallback chain. MyShipTracking, ShipFinder, and AIS Friends are implemented as
explicit opt-in public providers for browser-observed shapes; AIS Friends is
limited to `vessel_area` bounding-box rows and has no search or single-vessel
resolver. These adapters remain disabled by default while terms/rate behavior is
under review. Tradelinx schedule now has an explicit opt-in
`carrier_schedule_search` adapter for captured FCL/LCL route endpoints; the
vesselSchedule/detail/contact endpoints remain documented but are not promoted
as standalone user-facing tools. Other web-only candidates remain tracked by
capture-queue tickets. See
`Provider Discovery Backlog` below.

## Provider Discovery Backlog

The autonomous development process should keep this catalog alive:

1. Maintain the structured provider inventory file `config/provider-catalog.example.json` so it stays in sync with this markdown source.
2. Record each provider's access class, auth mode, cost/quota model, supported capabilities, coverage, freshness expectations, source URLs, implementation status, and capture eligibility.
3. Create adapter tickets for official/open/BYOK providers; the provider-discovery validator must clear the adapter gate before work starts.
4. Create capture tickets only for web-only services where the operator has authorized access and the terms review does not block capture; the validator must clear the capture gate.
5. Feed capture tickets into the api-capture-derived workflow: site profile, controlled Playwright session, HAR/XHR capture, replay validation, redaction, traffic IR, schema summary, sanitized fixture, and disabled-by-default adapter candidate.
