# GeoWire 시스템 전체 설계안 (v1)

> 기반 문서: `GeoRelay_project_summary.md`
> 작성일: 2026-07-17
> 상태: v1 확정 — 이름 GeoWire 확정, v0.1에 merge 전략 포함, Python SDK v0.2

---

## 0. 설계 목표와 원칙

### 0.1 목표

1. **오픈소스 우선**: GitHub 스타를 통한 커뮤니티 확보가 1차 목표. 수익화는 그 이후.
2. **표준화 포석**: GeoWire의 통합 Place 스키마와 Provider 인터페이스가
   "AI 에이전트용 지리정보 검색"의 사실상 표준(de facto standard) 초기 형태가 되는 것.
3. **초기 타깃**: AI 에이전트 / MCP 클라이언트 개발자.

### 0.2 설계 원칙 (모든 의사결정의 기준)

| # | 원칙 | 의미 |
|---|---|---|
| P1 | **Time-to-Wow < 5분** | API 키·DB·회원가입 없이 `npx @geowirehq/cli`만으로 실제 검색이 동작해야 한다 |
| P2 | **Zero-dependency 기본** | Postgres, Redis 없이 시작. 필요할 때만 어댑터로 확장 |
| P3 | **MCP-first** | REST보다 MCP가 1등 시민. Claude Desktop / Cursor에 설정 한 줄로 연결 |
| P4 | **Spec-first** | 스키마·매니페스트를 코드와 분리된 버전 관리 스펙으로 공개 |
| P5 | **Provider = 플러그인** | 코어 수정 없이 npm 패키지 하나로 공급자 추가 가능 |
| P6 | **BYOK** | 상용 키는 사용자 소유. 키가 없어도 OSM으로 항상 동작 |
| P7 | **정책 내장** | 공급자 약관(캐시 TTL, 표시 의무)을 코드가 강제한다 — 차별화 요소 |
| P8 | **투명성** | 모든 응답에 출처·비용·캐시 여부·건너뛴 공급자를 meta로 노출 |

### 0.3 스타를 부르는 제품 정의 (한 문장)

> **"Add real-world places to any AI agent in 5 minutes — no API key required."**
>
> 하나의 MCP 서버로, API 키 없이도, 모든 AI 에이전트에 장소 검색을 추가한다.

---

## 1. 전체 아키텍처

```text
┌─────────────────────────────────────────────────────────────┐
│                    Clients / Consumers                       │
│   Claude Desktop · Cursor · LangChain · 자체 앱 · curl       │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│                    Interface Layer                           │
│  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │
│  │MCP Server │ │ REST API │ │ TS/Py SDK │ │ CLI(geowire)│  │
│  │stdio/HTTP │ │ Fastify  │ │           │ │ init/serve   │  │
│  └───────────┘ └──────────┘ └───────────┘ └──────────────┘  │
└───────────────┬─────────────────────────────────────────────┘
                │  (모든 인터페이스는 동일한 Core를 호출)
┌───────────────▼─────────────────────────────────────────────┐
│                    GeoWire Core (Pipeline)                  │
│                                                              │
│  Request Validator ──▶ Query Normalizer ──▶ Route Planner    │
│        │                    │                    │           │
│        ▼                    ▼                    ▼           │
│  Provider Executor ──▶ Response Normalizer ──▶ Deduplicator  │
│  (병렬·타임아웃·CB)      (공통 스키마 변환)      (규칙 점수)   │
│        │                                         │           │
│        ▼                                         ▼           │
│  Ranker ──▶ Policy Enforcer ──▶ Response Builder(meta 포함)  │
│                                                              │
│  ── Cross-cutting ──────────────────────────────────────     │
│  Cache · Cost Controller · Rate Limiter · Circuit Breaker    │
│  Policy Engine · Telemetry(OTel) · Audit Log                 │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│               Provider Plugin Registry                       │
│  ┌────────┐┌──────────┐┌────────┐┌────────┐┌─────────────┐   │
│  │Nominatim││ Google   ││ Mapbox ││ Kakao  ││ Internal    │   │
│  │(기본ON) ││ (BYOK)   ││ (BYOK) ││ (BYOK) ││ (고객 데이터)│   │
│  └────────┘└──────────┘└────────┘└────────┘└─────────────┘   │
│         커뮤니티: geowire-provider-* 네이밍 규약             │
└───────────────┬─────────────────────────────────────────────┘
                │
┌───────────────▼─────────────────────────────────────────────┐
│                  Storage Adapters (선택적)                   │
│  Cache:   memory(기본) → Redis                               │
│  Store:   없음(기본) → SQLite → PostgreSQL + PostGIS         │
└─────────────────────────────────────────────────────────────┘
```

핵심 결정:

- **모든 인터페이스(MCP/REST/SDK/CLI)는 얇은 어댑터**이고, 로직은 전부 `@geowirehq/core`에 있다.
  → 어떤 경로로 호출해도 동일한 결과. SDK는 코어를 직접 임포트하는 embedded 모드도 지원.
- **Storage는 전부 선택 사항**. 기본 모드는 무저장(stateless) + 인메모리 캐시.
  → P1, P2 원칙 충족. Postgres는 고객 데이터·OSM 자체 적재 단계에서만 등장.

---

## 2. 기술 스택 선정과 근거

| 영역 | 선택 | 근거 |
|---|---|---|
| 언어/런타임 | **TypeScript + Node.js 22 LTS** | 타깃 사용자(AI 에이전트 개발자)의 주력 언어. MCP SDK 생태계 최성숙. `npx` 온보딩(P1). 커뮤니티 기여 장벽 최소 |
| 모노레포 | **pnpm workspaces + Turborepo** | 표준적, 진입장벽 낮음 |
| 스키마 | **Zod v4** (단일 진실원) | Zod → JSON Schema → OpenAPI → MCP tool schema 자동 생성. 스펙과 코드의 불일치 원천 차단 (P4) |
| REST | **Fastify** | 성능 + JSON Schema 네이티브 |
| MCP | **@modelcontextprotocol/sdk** | 공식 SDK. stdio + Streamable HTTP 둘 다 |
| 테스트 | **Vitest** + 녹화 픽스처(폴리 패턴) | 공급자 API를 실호출 없이 CI에서 테스트 |
| 캐시 | 인메모리(LRU) 기본 → **Redis** 어댑터 | P2 |
| 저장소 | 없음 기본 → SQLite → **PostgreSQL + PostGIS** | P2. 고객 데이터/OSM 단계에서 도입 |
| 관측성 | **OpenTelemetry** + `/metrics`(Prometheus) | 인프라 프로젝트의 기본기 |
| 배포 | 단일 Docker 이미지 + docker-compose + (v1.0) Helm | `docker run geowire/geowire` 한 줄 |
| 문서 | **Docusaurus** 또는 Fumadocs | docs 사이트 = 스타 전환율의 핵심 |
| 라이선스 | **Apache-2.0** | 기획 문서 §33 그대로 |

**Go/Rust를 선택하지 않은 이유**: 단일 바이너리 배포는 매력적이지만,
(1) MCP·AI 에이전트 생태계가 TS/Python 중심, (2) 커뮤니티 provider 기여 장벽,
(3) `npx` 즉시 실행 경험을 포기해야 함. 성능이 병목이 되는 지점(공간 인덱스)은
PostGIS가 담당하므로 게이트웨이 자체는 I/O 바운드 — Node로 충분.

---

## 3. 모노레포 구조

```text
geowire/
├── apps/
│   ├── server/                 # 통합 서버: REST + MCP(HTTP) 동시 서빙, CLI 진입점
│   ├── playground/             # 공급자 비교 웹 UI (Vite + React)
│   └── docs/                   # 문서 사이트
│
├── packages/
│   ├── core/                   # 파이프라인, 라우팅, 병합, 정책 — 심장부
│   ├── schema/                 # Zod 스키마 (Place, Request, Manifest) = 스펙의 구현체
│   ├── provider-sdk/           # GeoProvider 인터페이스, defineProvider(), 에러 타입
│   ├── provider-testkit/       # ★ 공급자 적합성(conformance) 테스트 키트
│   ├── providers/
│   │   ├── nominatim/          # 기본 활성 (키 불필요)
│   │   ├── google/             # BYOK
│   │   ├── mapbox/             # BYOK
│   │   ├── kakao/  naver/      # BYOK (한국)
│   │   └── internal/           # 고객 CSV / PostgreSQL / PostGIS
│   ├── mcp/                    # MCP 서버 구현 (stdio 단독 실행 가능)
│   ├── sdk/                    # TypeScript SDK (HTTP 클라이언트 + embedded 모드)
│   └── cli/                    # geowire init / serve / test-providers
│
├── sdks/
│   └── python/                 # Python SDK (v0.2)
│
├── specs/                      # ★ 버전 관리되는 공개 스펙 (§4)
│   ├── place-schema/
│   │   └── v1/ (schema.json, SPEC.md, CHANGELOG.md, examples/)
│   ├── provider-manifest/
│   │   └── v1/
│   └── rfcs/                   # 스펙 변경 제안 프로세스
│
├── examples/
│   ├── claude-desktop/         # 설정 JSON 복붙 예제
│   ├── cursor/  langchain/  vercel-ai-sdk/  openai-agents/
│   └── customer-csv/           # 자체 데이터 예제
│
├── deploy/
│   ├── docker/  docker-compose.yml  helm/(v1.0)
│
└── .github/
    ├── workflows/              # CI: lint, test, provider-conformance, release
    └── ISSUE_TEMPLATE/         # "New Provider Request" 템플릿 포함
```

기획 문서 §5와의 차이점:

- `apps/api`와 `apps/mcp-server`를 **`apps/server` 하나로 통합** — 프로세스 하나가
  REST와 MCP(Streamable HTTP)를 함께 서빙. stdio MCP는 `packages/mcp`를 통해
  `npx @geowirehq/mcp`로도 단독 실행 가능. 배포·운영 단순화.
- `provider-testkit` 신설 — 커뮤니티 기여의 핵심 장치 (§6.4).
- `specs/`를 단순 폴더가 아닌 **버전·RFC 체계를 갖춘 스펙 저장소**로 격상 (§4).

---

## 4. Spec-first: 표준화 전략의 구체안

"GEO 기능의 표준 초기 형태"가 되려면 코드보다 **스펙이 자산**이다.

### 4.1 공개 스펙 2종

1. **GeoWire Place Schema** (`specs/place-schema/v1`)
   - 통합 장소 표현의 JSON Schema. GeoJSON과의 상호 변환 규칙 포함
     (`location` ↔ GeoJSON Point — 기존 GIS 생태계와 싸우지 않고 얹혀 간다).
   - 모든 필드에 출처 배열(`sources[]`)과 신뢰도(`confidence`)를 포함하는 것이 차별점.
2. **GeoWire Provider Manifest** (`specs/provider-manifest/v1`)
   - 공급자의 capability, 커버리지, 비용 모델, **캐시/저장 정책, 표시 의무**를
     기계가 읽을 수 있는 형식으로 선언. 이것이 표준이 되면 지도 공급자들이
     스스로 매니페스트를 발행하는 미래를 노릴 수 있다.

### 4.2 운영 방식

- SemVer. v1 스펙은 v0.x 코드 기간 동안 `draft` 상태로 두고, 코드 v1.0과 함께 동결.
- 변경은 `specs/rfcs/`에 RFC 제출 → GitHub Discussion → 머지. 외부인도 제안 가능.
- `packages/schema`(Zod)에서 JSON Schema를 **자동 생성**해 스펙 파일과 diff 검사
  → 스펙과 구현의 불일치를 CI가 차단.
- 스키마를 `https://spec.geowire.dev/place/v1/schema.json` 같은 안정 URL로 호스팅.

---

## 5. 핵심 도메인 모델

### 5.1 Place (기획 문서 §6 계승 + 보강)

```ts
// packages/schema — Zod가 단일 진실원
const Place = z.object({
  id: z.string(),                      // "gwp_" 접두 내부 ID (안정적, 병합 후 유지)
  name: z.string(),
  localizedNames: z.record(z.string()).optional(),  // { ko: "본가", vi: "..." }
  categories: z.array(z.string()),     // GeoWire 표준 카테고리 (§5.3)

  location: z.object({
    latitude: z.number(),
    longitude: z.number(),
  }),

  address: Address.optional(),         // formatted + 구조화 필드
  contact: Contact.optional(),         // phone, website
  business: Business.optional(),       // openingHours(OSM 포맷), rating, priceLevel

  distanceMeters: z.number().optional(),
  confidence: z.number().min(0).max(1).optional(),

  sources: z.array(PlaceSource).min(1),   // ★ 항상 배열, 항상 최소 1개
  attributions: z.array(z.string()),      // ★ 표시 의무 문자열 (Policy Engine이 주입)

  metadata: z.record(z.unknown()).optional(),
});

const PlaceSource = z.object({
  provider: z.string(),                // "google" | "nominatim" | ...
  providerPlaceId: z.string(),
  fetchedAt: z.string().datetime(),
  confidence: z.number().optional(),
  fields: z.array(z.string()).optional(),  // 이 소스가 기여한 필드 목록 (병합 추적)
});
```

기획 대비 추가된 것: `localizedNames`(다국어 시장 필수), `attributions`(약관 준수 자동화, P7),
`PlaceSource.fields`(병합 시 필드 단위 출처 추적 — "영업시간은 google, 좌표는 osm").

### 5.2 응답 봉투 — 투명성(P8)의 구현

```jsonc
{
  "results": [ /* Place[] */ ],
  "meta": {
    "providersUsed":    [{ "provider": "nominatim", "resultCount": 18, "latencyMs": 240 }],
    "providersSkipped": [{ "provider": "google", "reason": "MISSING_CREDENTIALS" }],
    "providersFailed":  [{ "provider": "mapbox", "reason": "TIMEOUT" }],
    "strategy": "merge",
    "dedup": { "before": 44, "after": 27 },
    "cache": { "hit": false, "ttlSeconds": 3600 },
    "estimatedCostUSD": 0.017,
    "attributions": ["© OpenStreetMap contributors"]
  }
}
```

이 meta 블록이 Playground 데모의 재료이자, "단순 래퍼가 아니다"를 증명하는 화면이다.

### 5.3 표준 카테고리

- 자체 발명하지 않고 **OSM 태그 체계를 기본 축**으로 하되 상위 ~120개 카테고리로 평탄화.
- 각 provider 어댑터가 자기 분류 → GeoWire 카테고리 매핑 테이블을 소유.
- 매핑 테이블은 데이터 파일(JSON)로 분리해 커뮤니티가 PR로 개선 가능.

---

## 6. Provider SDK — 생태계의 씨앗

### 6.1 인터페이스 (기획 §7 계승)

```ts
interface GeoProvider {
  manifest: ProviderManifest;

  searchPlaces?(req: SearchPlacesRequest, ctx: ProviderContext): Promise<ProviderResult>;
  geocode?(req: GeocodeRequest, ctx: ProviderContext): Promise<ProviderResult>;
  reverseGeocode?(req: ReverseGeocodeRequest, ctx: ProviderContext): Promise<ProviderResult>;
  getPlace?(req: GetPlaceRequest, ctx: ProviderContext): Promise<ProviderResult>;
  autocomplete?(req: AutocompleteRequest, ctx: ProviderContext): Promise<ProviderResult>;
  healthCheck?(ctx: ProviderContext): Promise<ProviderHealth>;
}
```

- `ProviderContext`: 로거, AbortSignal(타임아웃), fetch(재시도·계측 내장) 주입.
  provider 코드가 인프라를 직접 만들지 않게 해 어댑터를 ~200줄 수준으로 유지.
- `defineProvider()` 헬퍼로 보일러플레이트 제거.

### 6.2 ProviderManifest (스펙 §4.1-2의 구현)

```ts
interface ProviderManifest {
  id: string;
  name: string;
  capabilities: Capability[];          // "search" | "geocode" | ...
  authType: "apiKey" | "oauth" | "none";
  coverage?: string[];                 // ISO 3166 국가코드, 비면 글로벌
  cost?: {                             // ★ 비용 기반 라우팅의 데이터원
    currency: "USD";
    perCall: Partial<Record<Capability, number>>;
  };
  policy: {                            // ★ 약관의 기계화 (P7)
    maxCacheTtlSeconds: number | null; // null = 캐시 금지
    canStorePermanently: boolean;      // providerPlaceId 외 원본 저장 가능 여부
    attributionRequired?: string;      // "© OpenStreetMap contributors"
  };
  rateLimit?: { requestsPerSecond?: number };
}
```

### 6.3 에러 분류 체계

모든 provider 예외는 다음으로 정규화 — fallback·서킷브레이커의 판단 근거:

```text
MISSING_CREDENTIALS | AUTH_FAILED | RATE_LIMITED | QUOTA_EXCEEDED
TIMEOUT | PROVIDER_UNAVAILABLE | INVALID_REQUEST | UNSUPPORTED_CAPABILITY
```

### 6.4 provider-testkit — 커뮤니티 기여 장치 ★

```ts
import { runConformanceTests } from "@geowirehq/provider-testkit";

runConformanceTests(myProvider, {
  fixtures: "./fixtures",      // 녹화된 응답으로 CI 테스트 (실호출 없음)
  live: process.env.LIVE === "1",  // 로컬에서만 실 API 스모크 테스트
});
```

- 스키마 준수, 에러 정규화, 타임아웃 동작, attribution 존재를 자동 검증.
- **"testkit 통과 = 머지 가능"** 규칙으로 리뷰 비용 최소화.
- `geowire-provider-*` 네이밍 규약 + 문서의 "Write a provider in 30 minutes" 가이드
  → 지역별 공급자(Baidu, Amap, Yandex, 2GIS...)를 커뮤니티가 채우는 그림.
  provider 요청/기여는 스타와 컨트리뷰터를 동시에 늘리는 최고의 good-first-issue다.

---

## 7. 검색 파이프라인 상세

### 7.1 단계

```text
1. Validate    : Zod 파싱. 실패 시 필드 단위 오류 메시지 (LLM이 자가 수정 가능한 수준으로)
2. Normalize   : 언어 감지, 국가 추론(near 좌표 → 국가), 쿼리 정리
3. Plan        : 정책/전략에 따라 공급자 호출 계획 수립
                 (국가별 우선순위 → capability 필터 → 자격증명 필터 → 예산 필터)
4. Execute     : 병렬 호출. per-provider 타임아웃(기본 3s), 서킷브레이커,
                 토큰버킷 rate limit. 부분 실패 허용 (P8: meta에 기록)
5. Normalize   : provider 응답 → Place 스키마
6. Dedup       : 규칙 기반 점수 병합 (§7.3)
7. Rank        : 거리·신뢰도·최신성 가중 합 (§7.4)
8. Enforce     : Policy Engine — attribution 주입, 캐시 TTL 상한, 필드 제거
9. Respond     : results + meta
```

### 7.2 전략 (기획 §8 계승)

`first-success`(기본값) + `merge`를 v0.1에 함께 구현 → `fastest` → `weighted` → `cost-aware` 순으로 확장.
merge가 v0.1에 포함되므로 중복 제거(§7.3)도 v0.1 범위다 — 런칭 시점부터
"여러 공급자 결과를 하나로"라는 핵심 차별점을 데모할 수 있다.
전략은 `Strategy` 인터페이스로 추상화해 요청 단위 오버라이드 허용:

```jsonc
{ "query": "pharmacy", "options": { "strategy": "merge", "maxCostUSD": 0.05 } }
```

### 7.3 중복 제거 (기획 §9 계승)

- 규칙 기반 가중 점수: 좌표거리 35 / 이름 유사도 30 / 주소 20 / 전화 10 / 웹 5.
- 이름 유사도: 정규화(소문자, 유니코드 NFKC, 법인 접미사 제거) 후 Jaro-Winkler.
- 좌표: 반경 기반 버킷팅으로 O(n²) 회피 (geohash prefix grouping).
- 병합 시 필드별 우선순위: `provider confidence × 필드별 공급자 강점`
  (예: 영업시간은 Google 우선, 좌표는 OSM 우선) — 테이블은 설정으로 노출.
- 임계값 0.75 이상 병합, 0.6~0.75는 meta에 `possibleDuplicates`로 표기만.

### 7.4 랭킹

`거리 40 / 영업시간 신뢰도 25 / 공급자 신뢰도 20 / 최신성 15` (기획 §19.7) —
가중치는 설정 파일에서 조정 가능하게. LLM 재랭킹은 범위 밖 (호출자가 할 일).

---

## 8. 라우팅 · 정책 · 비용

### 8.1 설정 파일 (기획 §29 계승, 최종 형태)

```yaml
# geowire.config.yaml — 없어도 동작한다 (Zero-config, P1)
providers:
  nominatim: { enabled: true }                      # 기본 ON
  google:    { enabled: true, apiKey: ${GOOGLE_MAPS_API_KEY} }
  internal:  { enabled: true, source: ./my-places.csv, priority: 100 }

routing:
  defaultStrategy: first-success
  countries:
    KR: { providers: [kakao, naver, google], strategy: merge }
    VN: { providers: [internal, google, nominatim] }

budget:
  monthlyUSD: 50            # 초과 시 유료 공급자 자동 제외, 무료로 폴백
  perRequestMaxUSD: 0.10

cache:
  adapter: memory            # memory | redis
  # TTL은 각 provider manifest의 maxCacheTtlSeconds가 상한 (Policy가 강제)
```

### 8.2 Policy Engine

- 입력: ProviderManifest.policy + 사용자 설정.
- 강제 사항: 캐시 TTL 상한, 영속 저장 차단(canStorePermanently=false면
  providerPlaceId + 내부 ID만 저장), attribution 자동 주입.
- 이 계층이 "약관 리스크(기획 §35.2)를 코드로 관리한다"는 GeoWire의 신뢰 스토리다.

**혼합 결과의 캐시 정책 = 가장 엄격한 소스 정책 (불변식).** 캐시는 정규화된
요청 단위 응답을 저장하지만 merge(§7.3) 결과는 여러 공급자 필드를 합친다. Google처럼
`maxCacheTtlSeconds=null`(캐시 금지)인 소스가 병합에 하나라도 기여하면 **혼합 응답
전체를 캐시하지 않는다**. 캐시 가능한 경우의 TTL은 기여한 모든 소스 상한의 **최솟값**을
쓴다. 파이프라인 순서는 `merge → policy → cache`로 고정한다 — 병합이 끝난 뒤 정책을
계산해야 provenance가 온전하다. 필드 단위(부분) 캐시는 v0.1 범위 밖이며, 도입 시
`PlaceSource.fields` provenance와 소스별 허용 목록을 근거로 금지 필드를 제거한 뒤에만
저장한다. 이 규칙은 혼합 정책 계약 테스트로 고정한다.

### 8.3 Cost Controller

- manifest.cost 기반 호출 전 예상 비용 계산 → 예산 초과 시 해당 공급자 제외.
- 사용량 카운터(메모리/Redis) + `/metrics`로 노출 + 응답 meta에 `estimatedCostUSD`.
- "이번 달 Google에 얼마 썼는지"를 게이트웨이가 보여주는 것 자체가 유료 API 사용자에게 강력한 후킹.

### 8.4 저장 정책 (기획 §18 계승)

- **Permanent Store** (opt-in, SQLite/Postgres): 내부 Place ID, provider 참조,
  고객 데이터, OSM, 자체 점수.
- **Temporary Cache** (기본, memory/Redis): 검색 결과·상세정보. TTL은 Policy가 상한 관리.
- 기본 모드는 무저장 — "우리는 당신의 위치 검색을 기록하지 않는다"가 셀링 포인트.

---

## 9. 인터페이스 설계

### 9.1 MCP 서버 (1등 시민)

도구 5개로 고정 (기획 §10):

| 도구 | 설명 |
|---|---|
| `search_places` | 자연어 + 좌표/지역 기반 장소 검색 |
| `get_place` | 내부 ID 또는 provider ID로 상세 조회 |
| `geocode_address` | 주소 → 좌표 (+정규화 주소, confidence) |
| `reverse_geocode` | 좌표 → 주소 |
| `list_geo_providers` | 활성 공급자·capability·상태 (에이전트의 자기 인식용) |

- 도구 설명문은 LLM이 잘 고르도록 신중히 작성 (이것도 제품이다).
- 전송: stdio(`npx @geowirehq/mcp`) + Streamable HTTP(`apps/server` 내장).
- MCP Resources로 `geowire://providers`, `geowire://config` 노출.

Claude Desktop 설정 — README 상단에 이 블록이 그대로 들어간다:

```json
{
  "mcpServers": {
    "geowire": { "command": "npx", "args": ["-y", "@geowirehq/mcp"] }
  }
}
```

### 9.2 REST API

```text
POST /v1/places/search        # body: SearchPlacesRequest
GET  /v1/places/{id}
GET  /v1/geocode?q=...&country=VN
GET  /v1/reverse-geocode?lat=..&lng=..
GET  /v1/providers            # 상태·capability·latency 통계
GET  /v1/health   GET /metrics
```

- OpenAPI 3.1 스펙 자동 생성(Zod 기반) → docs 사이트에 렌더.

#### 9.2.1 인증·바인딩 불변식 (출시 게이트)

REST와 Streamable HTTP MCP(§9.1)는 같은 서버 프로세스에 노출되므로, "무인증 =
로컬"이라는 가정을 코드가 강제해야 한다. Docker 포트 공개나 잘못된 배포에서
무인증으로 원격 노출되면 검색·`get_place`·`geowire://config` 등으로 내부 CSV
데이터가 열람되고 BYOK 유료 호출이 발생한다. 다음을 기동 시 불변식으로 강제한다:

1. **무키 → loopback 전용**: `GEOWIRE_API_KEYS`가 없으면 `127.0.0.1`/`::1`에만
   바인딩한다. 비-loopback 주소(`0.0.0.0` 포함) 바인딩이 요청되면 **기동을 거부**한다.
2. **HTTP MCP도 동일 인증**: `/mcp`(Streamable HTTP) 활성화 시 인증 설정이 없으면
   기동을 거부한다. REST(`/v1/*`)와 `/mcp`에 **동일한 Bearer 검사**를 적용한다
   (stdio MCP는 프로세스 로컬이라 예외).
3. `GEOWIRE_API_KEYS` 설정 시에만 임의 주소 바인딩을 허용하고 모든 인터페이스에
   Bearer를 요구한다.

출시 게이트에 "Docker에서 무인증 원격 접근이 거부되는지" E2E 테스트를 포함한다.

### 9.3 SDK

```ts
// HTTP 모드
const geo = createClient({ baseUrl: "http://localhost:4980" });
// Embedded 모드 — 서버 없이 라이브러리로
const geo = createGeoWire({ providers: { nominatim: {} } });
const r = await geo.searchPlaces({ query: "24-hour pharmacy", near: {...} });
```

Vercel AI SDK / LangChain용 tool 변환 헬퍼(`geo.asTools()`)를 제공하면
MCP를 안 쓰는 프레임워크 사용자까지 커버 — 스타 저변 확대.

### 9.4 CLI

```bash
npx @geowirehq/cli              # zero-config 서버 기동 (nominatim만으로)
npx @geowirehq/cli init         # 대화형 설정 마법사 (기획 §23)
npx @geowirehq/cli serve        # 설정 파일 기반 기동
npx @geowirehq/cli test         # 등록된 공급자 연결 검사 ("✓ Google Places connected")
npx @geowirehq/cli search "coffee near Gangnam"   # 터미널에서 바로 검색 (데모용 킬러 기능)
```

---

## 10. 관측성 · 보안

- **OTel 트레이스**: 요청 → provider 호출별 span. 데모 스크린샷 재료.
- **Prometheus 메트릭**: provider별 latency/error/cost, 캐시 적중률.
- **감사 로그**(v1.0, opt-in): 누가 무엇을 검색했는지 — 기업 수요(기획 §2.6).
- 키 보안: env 전용 권장, 설정 파일 평문 키 감지 시 기동 경고(기획 §27),
  로그에서 키 자동 마스킹, `.env` gitignore 기본 제공.
- 공용 Nominatim 사용 시 1 req/s 제한을 코드가 강제 + 운영 전환 안내 경고
  (OSM 커뮤니티와의 신뢰 관계는 이 프로젝트의 평판 자산).

---

## 11. 개발 로드맵 (커뮤니티 성장과 결합)

### v0.1 — "It works" (목표: 6~8주, 런칭 배포)

핵심: **P1 완성 + merge 데모**. "여러 공급자 결과를 하나로"를 런칭 시점부터 보여준다.

- [ ] `packages/schema` — Place/Request Zod 스키마 + JSON Schema 생성
- [ ] `packages/core` — 파이프라인 (validate→plan→execute→normalize→respond)
- [ ] 전략: `first-success`(기본) + **`merge`** + 중복 제거 v1 (§7.3)
- [ ] `packages/provider-sdk` + `providers/nominatim`(기본), `providers/google`(BYOK)
- [ ] `providers/internal` — CSV 파일 검색 (SQLite in-memory)
- [ ] `packages/mcp` — 도구 5종, stdio
- [ ] `apps/server` — REST + health, 인메모리 캐시
- [ ] 인증·바인딩 불변식(§9.2.1) — 무키 loopback 강제 + Docker 무인증 원격 거부 E2E
- [ ] 혼합 캐시 정책(§8.2) — 캐시 금지 소스 병합 시 미캐시 계약 테스트
- [ ] `packages/cli` — `npx @geowirehq/cli`, `init`, `test`, `search`
- [ ] Docker 이미지, README(§12), Claude Desktop/Cursor 예제
- [ ] CI + provider-testkit 초판

**런칭**: Show HN / r/LocalLLaMA / X / awesome-mcp-servers PR / Smithery·mcp.so·Glama·PulseMCP 등록

### v0.2 — "It shows" (Playground = 스타 엔진)

- Playground: 공급자별 결과·응답시간·병합 전후 **나란히 비교 UI** (README GIF의 원천)
- 공개 데모 인스턴스 (OSM 전용, rate-limited) — 설치 없이 체험
- **Python SDK** (LangChain/LlamaIndex 등 Python 프레임워크 직접 통합 사용자 확보)
- Mapbox·Foursquare provider, Redis 캐시 어댑터, 기본 비용 추적(meta.estimatedCostUSD)
- 중복 제거 v2 (필드별 공급자 강점 병합, possibleDuplicates)

### v0.3 — "It scales"

- 국가별 라우팅, `weighted`/`cost-aware` 전략, 예산 제한
- Kakao·Naver·HERE provider (커뮤니티 기여 유도 목표)
- PostGIS internal provider(고객 데이터 대량), OSM 자체 적재 가이드 문서
- 스펙 v1 draft 공개 + RFC 프로세스 오픈

### v1.0 — "It's infrastructure"

- Provider SDK API 동결 + 스펙 v1.0 동결
- Policy Engine 완성, 감사 로그, OTel 완비, Helm 차트
- 엔터프라이즈 문서 (보안 모델, 배포 토폴로지)
- 이 시점부터 Hosted GeoWire(수익화) 설계 착수 — 오픈소스와 코드베이스 공유

---

## 12. GitHub 스타 획득 전략 (제품 외적 설계)

### 12.1 README 구성 (전환율의 80%)

```text
1. 로고 + 한 줄: "Add real-world places to any AI agent in 5 minutes. No API key required."
2. 데모 GIF: Claude가 search_places로 약국을 찾는 15초 화면
             + Playground의 공급자 비교 화면
3. Quickstart 3종 (각 5줄 이내):
   - Claude Desktop: JSON 복붙
   - 서버: npx @geowirehq/cli
   - Docker: docker run -p 4980:4980 geowire/geowire
4. Why GeoWire: 비교표 (직접 통합 vs 단일 provider MCP vs GeoWire)
   — fallback, 비용 관리, 통합 스키마, 출처 표시, self-host
5. Providers 표: 지원 현황 + "want another? open an issue" 링크
6. 아키텍처 다이어그램 1장
7. 스펙·문서·Discord 링크
```

### 12.2 성장 루프

- **MCP 디렉터리 등록**이 초기 유입의 핵심 채널 (Smithery, mcp.so, Glama, PulseMCP, awesome-mcp-servers).
- **Provider 기여 루프**: "우리 나라 지도 공급자가 없네" → issue 템플릿 → testkit로 셀프 검증 → 머지
  → 기여자가 자국 커뮤니티에 홍보 → 신규 유입. (i18n 강점이 성장 엔진이 된다)
- **비교 콘텐츠**: "Google Places API 비용 60% 줄인 방법(cost-aware routing)" 류의
  블로그 = 검색 유입 + HN 재료.
- **투명한 로드맵**: GitHub Projects 공개 + `good first issue` 상시 20개 유지.
- 배지: CI, coverage, Docker pulls, MCP 디렉터리 배지.

### 12.3 하지 않을 것 (범위 방어, 기획 §35.5)

- 지도 타일·렌더링 ❌ / 내비게이션·경로 탐색 ❌ / 실시간 교통 ❌
- LLM 내장(재랭킹·요약) ❌ — 그것은 호출자(에이전트)의 일
- v1.0 전 과금·계정 시스템 ❌

---

## 13. 주요 리스크와 설계상 대응

| 리스크 (기획 §35) | 설계상 대응 |
|---|---|
| 대형 플랫폼의 지도 MCP 내장 | 단일 공급자 MCP와의 차별점(멀티 공급자·fallback·비용·self-host·고객 데이터)에 집중. 스펙 선점 |
| 공급자 약관 | Policy Engine이 manifest 선언 기반으로 코드 강제. 약관 요약 문서를 provider별로 유지 |
| 비용 폭주 | BYOK 기본 + budget 설정 + 운영자 키 모델은 v1.0 이후로 연기 |
| 데이터 품질 편차 | 필드 단위 출처 추적 + confidence + 공급자별 필드 강점 테이블 |
| 범위 확대 | §12.3의 "하지 않을 것" 목록을 README에 명시 |
| OSM 커뮤니티 마찰 | 공용 Nominatim rate limit 코드 강제 + ODbL attribution 자동 주입 |

---

## 14. 결정 사항 및 미결 사항

### 확정 (2026-07-17)

1. ✅ **이름: GeoWire 확정** — 초안 이름 GeoRelay는 georelay.com(활성 GPS 추적 기업,
   GeoRelay™ 상표 표기, 동일 지리정보 분야)과의 충돌 리스크로 폐기.
   GeoWire는 npm(`geowire`, `@geowirehq/*` 스코프 미사용 확인), GitHub org, geowire.dev
   모두 가용 확인 완료(2026-07-17). 선점 등록을 착수 첫 작업으로 진행.
2. ✅ **v0.1에 `merge` 전략 + 중복 제거 포함** — 런칭 시점부터 핵심 차별점 데모.
   출시 목표는 6~8주로 조정.
3. ✅ **Python SDK는 v0.2** — Playground와 함께 Python 프레임워크 사용자 확보.

### 미결 (착수 후 결정)

1. **Playground 공개 데모 인스턴스의 호스팅 비용/운영 주체**.
2. **커뮤니티 채널**: Discord vs GitHub Discussions 단일화.

---

## 15. 한 문장 요약

> GeoWire는 "API 키 없이 5분 만에 붙는 MCP 장소 검색"으로 개발자를 모으고,
> 공개 스펙(Place Schema + Provider Manifest)과 공급자 플러그인 생태계로
> AI 지리정보 검색의 표준 초기 형태를 선점한 뒤,
> 비용·정책·라우팅 관리 능력을 바탕으로 Hosted/Enterprise로 수익화하는
> 오픈소스 Geo Search Gateway다.
