# Community Post Drafts

Use these drafts for overseas community launch posts. Tailor the first
sentence to each community and avoid posting identical text everywhere.

For smaller asks that other people can forward, use
[`help-us-spread.md`](./help-us-spread.md).

## Korean Communities - OKKY / GeekNews / Velog / Brunch

Title:

```text
Vessel Traffic MCP를 오픈소스로 공개했습니다 - 선박 위치, AIS, 해운 스케줄을 MCP로 조회
```

Body:

```text
선박 조회와 해운 스케줄 확인을 AI 클라이언트에서 바로 사용할 수 있게 하는
Vessel Traffic MCP를 공개했습니다.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

npm:
https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp

할 수 있는 일:

- 선박명, MMSI, IMO, callsign으로 선박 검색
- AIS 스타일 최신 위치 조회
- 특정 해역 bounding box 내 선박 조회
- 항적, 기항 이력, 선박 스케줄 조회
- 출발/도착 항 기준 carrier schedule 검색
- 간단한 schedule delay heuristic 실행

Claude, ChatGPT, Codex, MCP Inspector 등 MCP 클라이언트에서 쓸 수 있고,
로컬 stdio 서버와 Streamable HTTP 서버를 모두 지원합니다.

설계 원칙은 read-only와 source attribution입니다. 공개/라이브 provider 응답에는
`source.provider`와 `source.landingUrl`을 넣어서 사용자가 원 출처를 확인할 수 있게 했습니다.
상용 provider는 BYOK 방식으로만 사용하고, 기본 테스트는 sanitized fixture만 사용합니다.

설치:

```bash
npm install -g @tools-mcp/vessel-traffic-mcp
VESSEL_MCP_TRANSPORT=stdio vessel-traffic-mcp
```

해운/물류 현업에서 어떤 workflow가 가장 쓸모 있을지 피드백을 받고 싶습니다.
예를 들면 ETA 확인, 선박/항차 추적, port-call 모니터링, B/L 문서에서 선박 후보 추출,
carrier schedule 비교 같은 사용 사례입니다.
```

## Korean Maritime / Logistics Communities

Title:

```text
AI 클라이언트에서 선박 위치와 해운 스케줄을 조회하는 오픈소스 MCP 서버
```

Body:

```text
Vessel Traffic MCP라는 오픈소스 프로젝트를 공개했습니다.
목표는 Claude, ChatGPT, Codex 같은 MCP 지원 AI 클라이언트에서 선박/해운 데이터를
읽기 전용으로 조회하는 것입니다.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

주요 기능:

- 선박명, MMSI, IMO 기반 선박 식별
- 최신 AIS 스타일 위치 조회
- 항적/기항 이력 조회
- carrier schedule, vessel schedule 조회
- 지연 가능성에 대한 단순 heuristic
- 응답마다 출처 provider와 source URL 제공

원 데이터를 숨기거나 재브랜딩하지 않고, 사용자가 원 출처를 직접 확인할 수 있게 하는 쪽으로
설계했습니다. 상용 데이터 provider는 사용자가 본인 키를 넣는 BYOK 방식만 지원합니다.

물류/포워딩/해운 쪽에서 실제로 필요한 기능이 무엇인지 의견을 듣고 싶습니다.
```

## Hacker News - Show HN

Title:

```text
Show HN: Vessel Traffic MCP - vessel tracking and shipping schedules for AI agents
```

Body:

```text
Hi HN,

I built Vessel Traffic MCP, an MIT-licensed Model Context Protocol server for maritime data workflows.

It gives MCP clients a read-only tool surface for:

- Vessel search by name, MMSI, IMO, and callsign
- Latest AIS-style position lookup
- Bounding-box vessel lookup
- Recent tracks and port calls
- Carrier schedules and vessel schedules
- Simple schedule delay heuristics

The project is deliberately source-attributed. Live and public-provider responses include source.provider and source.landingUrl, so the user can verify the original provider and visit the source service. Commercial providers are BYOK only, and the default test path uses sanitized fixtures with no live calls.

It currently supports a local stdio MCP server, a Streamable HTTP server, a small map UI, public opt-in providers, and BYOK adapters for providers like MarineTraffic, VesselFinder, AISStream, AISHub, SeaRates, Routescanner, and others.

GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
npm: https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp

I would like feedback on the MCP tool design, provider attribution model, and what maritime/logistics workflows would be most useful to support next.
```

## Reddit - r/mcp / r/MCPservers

Title:

```text
I open-sourced Vessel Traffic MCP: vessel positions, schedules, and source-attributed maritime data for MCP clients
```

Body:

````text
I open-sourced Vessel Traffic MCP, a read-only MCP server for vessel tracking and maritime schedule workflows.

What it does:

- Search vessels by name, MMSI, IMO, or callsign
- Get latest AIS-style vessel positions
- Query vessel tracks, port calls, and map areas
- Search carrier schedules and vessel schedules
- Run simple schedule delay heuristics
- Return source.provider and source.landingUrl so users can verify the original source

It is designed for Claude, ChatGPT, Codex, MCP Inspector, and other MCP clients.

Install:

```bash
npm install -g @tools-mcp/vessel-traffic-mcp
VESSEL_MCP_TRANSPORT=stdio vessel-traffic-mcp
```

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

npm:
https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp

Notes:

- MIT licensed
- Read-only tools only
- Default tests use sanitized fixtures
- Public providers are opt-in
- Commercial providers are BYOK
- The project is meant to send users back to the original source service, not hide attribution

Feedback welcome, especially from anyone building logistics, maritime, or supply-chain MCP workflows.
````

## Reddit - r/opensource / r/SideProject

Title:

```text
I built an open-source MCP server for vessel tracking and shipping schedules
```

Body:

```text
I built Vessel Traffic MCP, an MIT-licensed MCP server that lets AI agents query vessel identity, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and simple delay heuristics.

The main design principle is source attribution. Responses from live/public providers include the provider name and source URL so the user can verify the original service. Commercial providers are Bring Your Own Key only.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

npm:
https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp

It also includes a small local map UI for trying vessel lookup from a browser.

I am looking for contributors interested in MCP, maritime data, logistics, schedule prediction, provider adapters, and better UI around vessel position/schedule workflows.
```

## Reddit - Maritime / Logistics Communities

Title:

```text
Open-source tool for vessel lookup, AIS-style positions, and shipping schedules
```

Body:

```text
I am working on Vessel Traffic MCP, an open-source read-only tool for vessel and shipping schedule workflows.

It can be used from AI clients that support MCP, but the domain goal is simple:

- Enter a vessel name, MMSI, or IMO
- Resolve possible vessel identities
- Fetch latest AIS-style position or schedule data from configured providers
- Show the original source provider and source URL
- Support carrier schedules and simple delay heuristics

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

The project does not try to hide the original data source. Provider attribution and links are part of the response model. Commercial provider integrations are BYOK only.

I would appreciate feedback from maritime/logistics users about which workflows are actually useful: vessel ETA checks, port-call monitoring, route schedule comparison, exception alerts, or document-to-vessel lookup.
```

## DEV Community / Hashnode

Title:

```text
Building a Source-Attributed MCP Server for Vessel Tracking and Shipping Schedules
```

Outline:

```text
1. Why maritime data is awkward for AI agents
2. Why MCP is a useful interface
3. Tool surface: vessel_search, vessel_position, vessel_area, vessel_track, port_calls, carrier_schedule_search, vessel_schedule, schedule_delay_predict
4. Source attribution as a hard rule
5. Public providers vs BYOK commercial providers
6. Local map UI demo
7. How to install and test
8. What contributors can help with next
```

Opening:

```text
I open-sourced Vessel Traffic MCP, a read-only Model Context Protocol server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics.

The project is built around a simple rule: if data comes from a provider, the response should expose the provider and source URL so the user can verify it and visit the original service.
```

## Lobsters

Title:

```text
Vessel Traffic MCP: source-attributed vessel tracking and shipping schedules for MCP clients
```

Description:

```text
An MIT-licensed MCP server for vessel identity lookup, AIS-style positions, tracks, port calls, carrier schedules, vessel schedules, and delay heuristics. The interesting part is the attribution and provider boundary: default tests are fixture-only, public providers are opt-in, commercial providers are BYOK, and tool responses preserve source.provider/source.landingUrl.
```

Suggested tags:

```text
ai, api, javascript, typescript, web
```

## Indie Hackers

Title:

```text
Launching an open-source MCP server for vessel tracking and maritime schedules
```

Body:

```text
I launched Vessel Traffic MCP, an open-source MCP server for vessel lookup, AIS-style positions, and shipping schedule workflows.

The initial use case is: type a vessel name, MMSI, or IMO and let an AI client retrieve current status, coordinates, schedules, and the original source URL.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

I am exploring where this is useful commercially: logistics exception monitoring, shipment ETA checks, broker/forwarder workflows, or document-to-vessel lookup. Feedback from shipping/logistics builders would be useful.
```
