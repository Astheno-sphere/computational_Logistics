# Help Us Spread Vessel Traffic MCP

Use this page when asking other people to help share, test, or explain
`vessel-traffic-mcp`. The goal is to make the ask small, specific, and
easy to forward without turning it into spam.

## Canonical Links

- GitHub: https://github.com/tools-mcp/vessel-traffic-mcp
- npm: https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp
- MCP Registry: `io.github.tools-mcp/vessel-traffic-mcp`
- Release: https://github.com/tools-mcp/vessel-traffic-mcp/releases/tag/v0.1.0
- Help wanted issue: https://github.com/tools-mcp/vessel-traffic-mcp/issues/7
- Feedback discussion: https://github.com/tools-mcp/vessel-traffic-mcp/discussions/8

## The Ask

Short version:

```text
If you know people building MCP tools, shipping/logistics software, or
AI workflows for maritime data, please share this with them. I am looking
for real usage feedback, not just stars.

https://github.com/tools-mcp/vessel-traffic-mcp
```

Korean version:

```text
MCP, 물류/포워딩/무역, 선박/해운 데이터 쪽에 관심 있는 분이 있으면
이 프로젝트를 공유해 주시면 좋겠습니다. 단순 홍보보다 실제 업무에서
어떤 기능이 필요한지 피드백을 받고 싶습니다.

https://github.com/tools-mcp/vessel-traffic-mcp
```

## 3 Minute Help

- Star the repository if it looks useful.
- Share the GitHub link with one MCP, logistics, shipping, or trade
  community.
- Send the Korean short ask above to one person who knows forwarding,
  trade, SCM, port logistics, or maritime software.
- Comment with one workflow that would be useful in real operations:
  vessel ETA checks, port-call monitoring, schedule comparison, exception
  alerts, or B/L-to-vessel lookup.

## 15 Minute Help

Install with an MCP client:

```json
{
  "mcpServers": {
    "vessel-traffic-mcp": {
      "command": "npx",
      "args": ["-y", "@tools-mcp/vessel-traffic-mcp"],
      "env": {
        "VESSEL_MCP_TRANSPORT": "stdio",
        "VESSEL_MCP_ENABLE_PUBLIC_PROVIDERS": "myshiptracking,tradlinx,aisfriends"
      }
    }
  }
}
```

Then try:

```text
Find the current position of EVER GIVEN. Include source.provider and source.landingUrl.
Search carrier schedules from KRPUS to NLRTM. Include the source URL.
```

Useful feedback:

- which MCP client was used;
- whether installation worked on the first try;
- which prompt failed or felt unclear;
- which logistics workflow would make this worth using weekly.

Leave feedback in the public discussion:
https://github.com/tools-mcp/vessel-traffic-mcp/discussions/8

## Workflow Baseline And Feedback Boundary

The following are product-reference workflows drawn from the project brief.
They are **not** evidence of active user adoption or completed user research.
Use them to make a specific feedback request, and mark any later feedback with
the client, data-provider class, and workflow context that the contributor
actually used.

| Workflow | Intended outcome | Current boundary | Feedback to ask for |
| --- | --- | --- | --- |
| B/L or shipping-document to vessel candidate | Resolve a vessel name, MMSI, or IMO into ranked candidates with supporting context. | Ambiguous candidates must request confirmation; no document or credential is retained. | Which document fields and confidence explanation make the result trustworthy? |
| Vessel, ETA, and port-call exception check | Review source-attributed position, track, or port-call context for a known vessel. | AIS coverage and freshness may be incomplete; it is never navigation guidance. | Which status, time window, or exception signal changes an operational decision? |
| Port-pair or vessel schedule comparison | Find carrier schedules for a route or vessel and return the original source URL. | Provider coverage, terms, and data freshness vary; commercial sources remain BYOK. | Which route, carrier, and schedule comparison is used often enough to justify follow-up? |

## 1 Hour Help

- Post a tailored write-up in a community where maritime/logistics people
  actually read. Do not post identical text everywhere.
- Add the project to one MCP directory or awesome list that accepts public
  pull requests.
- Open a provider request for a data source you already use and can
  legally access with your own key or account.
- Record a short demo showing the MCP client response and source URL.
- Improve README/client setup instructions for the client you actually
  tested.

## Copy For Korean Logistics And Trade Communities

Title:

```text
AI에서 선박 위치와 해운 스케줄을 출처 URL과 함께 조회하는 오픈소스 도구
```

Body:

```text
Vessel Traffic MCP라는 오픈소스 프로젝트를 공개했습니다.

Claude, ChatGPT, Codex 같은 MCP 지원 AI 클라이언트에서 선박명, MMSI,
IMO, 항만, 선사 스케줄을 읽기 전용으로 조회하는 도구입니다.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

할 수 있는 일:

- 선박명/MMSI/IMO 기반 선박 검색
- AIS 스타일 최신 위치 조회
- 항적, 기항 이력, 선박 스케줄 조회
- KRPUS -> NLRTM 같은 항로 기준 carrier schedule 검색
- 응답마다 원 출처 provider와 source URL 제공

유료 데이터를 우회하거나 재배포하는 프로젝트가 아닙니다.
상용 provider는 사용자가 본인 키를 넣는 BYOK 방식이고, 공개/live 응답은
출처 URL을 함께 보여주는 방향으로 설계했습니다.

물류, 포워딩, 무역 실무에서 어떤 기능이 실제로 쓸모 있을지 피드백을
받고 싶습니다. 예를 들면 ETA 확인, 선박/항차 추적, port-call 모니터링,
스케줄 비교, B/L 문서에서 선박 후보 찾기 같은 workflow입니다.
```

## Copy For MCP Developer Communities

Title:

```text
Vessel Traffic MCP: source-attributed vessel tracking and shipping schedules for AI agents
```

Body:

```text
I open-sourced Vessel Traffic MCP, an MIT-licensed MCP server for vessel
identity lookup, AIS-style positions, tracks, port calls, carrier schedules,
vessel schedules, and simple delay heuristics.

GitHub:
https://github.com/tools-mcp/vessel-traffic-mcp

npm:
https://www.npmjs.com/package/@tools-mcp/vessel-traffic-mcp

The design is read-only and source-attributed. Live/public responses include
source.provider and source.landingUrl so users can verify the original data
source. Commercial providers are BYOK only, and default tests use sanitized
fixtures.

I am looking for feedback from MCP builders and maritime/logistics users:
which tools should be easier to install, which provider adapters matter, and
which real workflows should be supported next?
```

## Copy For Personal Messages

Korean:

```text
혹시 주변에 포워딩/무역/해운 데이터나 MCP 관심 있는 분 있으면 이거 한번
공유해 줄 수 있을까요? 제가 만든 오픈소스인데, 단순 홍보보다 실제 현업
workflow 피드백이 필요합니다.

https://github.com/tools-mcp/vessel-traffic-mcp
```

English:

```text
If you know anyone working on MCP tools, maritime data, logistics, or
shipping software, could you share this with them? I am looking for real
workflow feedback more than promotion.

https://github.com/tools-mcp/vessel-traffic-mcp
```

## Posting Rules

- Disclose that this is an open-source project.
- Tailor the first paragraph to the community.
- Do not post identical text across many places.
- Do not claim real-time navigation reliability.
- Do not claim provider data ownership.
- Do not imply paywall, CAPTCHA, login, or provider-term bypass.
- Always mention source attribution and BYOK for commercial providers.
