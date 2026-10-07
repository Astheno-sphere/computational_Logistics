# GeoWire v0.1 구현 계획

> 기준 문서: `GeoWire_system_design.md`
> 목표: **v0.1 "It works" 런칭** — 6~8주
> 작성일: 2026-07-17

---

## 0. 현재 상태 (Phase 0~9 완료 ✅ · Docker 검증됨 · 외부 런칭 작업만 잔여)

- [x] 모노레포 스캐폴딩 (pnpm + Turborepo + TS strict/ESM)
- [x] `@geowirehq/schema` — Place / PlaceSource / ProviderManifest / 요청·응답 / CountryCode 스키마 (Zod v4, 테스트 23개 통과)
- [x] `@geowirehq/provider-sdk` — GeoProvider / ProviderContext(재시도·타임아웃 fetch) / GeoProviderError / defineProvider (테스트 21개 통과)
- [x] `@geowirehq/provider-testkit` — runConformanceChecks/Tests(6축) + mock-server + 픽스처 로더/레코더 (테스트 7개 통과)
- [x] `@geowirehq/provider-nominatim` — search/geocode/reverse, 카테고리 맵, 1req/s rate limit·UA 강제, baseUrl 교체 (테스트 11개 통과)
- [x] `@geowirehq/core` — config(zero-config)·registry·pipeline·first-success·merge·dedup v1·rank·cache(LRU)·policy·cost·circuit-breaker·**getPlace**·createGeoWire 퍼사드 (테스트 94개, 3-공급자 E2E 포함)
- [x] `@geowirehq/provider-google` — BYOK, Places API(New) search/getPlace + Geocoding geocode/reverse, 카테고리 맵, cost.perCall 공식단가, 키 없으면 MISSING_CREDENTIALS (테스트 7개 통과)
- [x] `@geowirehq/provider-internal` — CSV 로더(RFC4180, 컬럼 별칭), 인메모리 이름 부분일치 + Haversine 반경 검색, priority 100 권장 (테스트 9개 통과)
- [x] `@geowirehq/mcp` — 도구 5종(search_places/get_place/geocode_address/reverse_geocode/list_geo_providers), inputSchema z.toJSONSchema 자동생성, 요약텍스트+structuredContent, stdio bin(geowire-mcp), 자가수정 에러 (테스트 12개 통과, InMemoryTransport E2E + stdio 스모크)
- [x] `@geowirehq/server` (apps/server) — Fastify REST(/v1 검색·상세·지오코딩·providers·health), OpenAPI 3.1 자동생성+/docs, prom-client /metrics, 선택적 Bearer 인증, MCP Streamable HTTP /mcp 마운트 (테스트 14개 통과, 실서버 curl 스모크)
- [x] `geowire` (packages/cli) — `serve`(기본, 서버 기동)·`search`(원샷 테이블/JSON)·`test`(연결 검사)·`init`(대화형 마법사→.env+config+.gitignore)·help/version, 경량 argv 파서, .env 로더 (테스트 18개 통과, serve 실기동 스모크)
- [x] 배포·문서 산출물 — CI(ci.yml/release.yml, node22 ubuntu·windows 매트릭스 + conformance job), Changesets, 멀티스테이지 Dockerfile+compose, README 완성, CONTRIBUTING("provider in 30 min"), Issue 템플릿 3종, examples 6종
- [x] git 초기화 + baseline 커밋, Apache-2.0, README 스켈레톤
- [ ] **(사용자 작업)** GitHub org·npm publish·데모 GIF·MCP 디렉터리 등록·Show HN (외부 계정/수동)
- [ ] **(사용자 작업)** GitHub org `geowire` 생성, npm `@geowirehq` 스코프 확보(`@geowire`는 선점됨), geowire.dev 구매

---

## 1. 전체 구현 순서와 의존 관계

```text
Phase 0  schema ✅
            │
Phase 1  provider-sdk          ← 인터페이스가 모든 것의 계약
            │
Phase 2  provider-testkit      ← 이후 모든 provider의 품질 게이트
            │
Phase 3  providers/nominatim   ← 첫 실제 공급자 (키 불필요 → 즉시 검증 가능)
            │
Phase 4  core                  ← 파이프라인·전략·중복제거·정책 (최대 작업)
            │
Phase 5  providers/google + providers/internal(CSV)
            │
Phase 6  mcp                   ← 1등 시민 인터페이스
            │
Phase 7  apps/server (REST)    ─┐ 6·7·8은 core 완성 후
Phase 8  cli                   ─┘ 부분 병행 가능
            │
Phase 9  배포·CI·문서·런칭 준비
```

원칙: **각 Phase는 "동작하는 수직 슬라이스"로 끝난다.**
Phase 3이 끝나면 코드에서 Nominatim 검색이 되고, Phase 4가 끝나면 fallback·병합이
되고, Phase 6이 끝나면 Claude Desktop에서 실제로 쓸 수 있다.

---

## 2. Phase별 상세 계획

### Phase 1 — `packages/provider-sdk` (예상 3~4일)

모든 공급자가 구현할 계약. **이 API가 커뮤니티 생태계의 표면이므로 가장 신중하게.**

```text
packages/provider-sdk/src/
├── provider.ts        # GeoProvider 인터페이스, ProviderHealth
├── types.ts           # ProviderPlace, ProviderResult
├── context.ts         # ProviderContext (fetch·logger·clock 주입)
├── errors.ts          # GeoProviderError (schema의 ProviderErrorCode 사용)
├── define.ts          # defineProvider() 헬퍼
└── index.ts
```

핵심 결정 사항:

- **`ProviderPlace`** = `Place`에서 `id`·`attributions`·`confidence` 제외 +
  `providerPlaceId` 단수 보유. 내부 ID 발급·attribution 주입·신뢰도 계산은
  **core의 책임** — provider는 "자기 데이터의 정규화"만 한다.
- **`ProviderContext`**: `fetch`(타임아웃 AbortSignal + 429/5xx 지수 백오프 재시도 내장),
  `logger`, `now()` (테스트 주입용). provider 코드는 인프라를 직접 만들지 않는다
  → 어댑터 200줄 유지 목표.
- **`GeoProviderError`**: `code: ProviderErrorCode` 필수. HTTP 상태 → 코드 매핑
  유틸(`errorFromHttpStatus(401→AUTH_FAILED, 429→RATE_LIMITED, ...)`)을 제공.
- `defineProvider()`: manifest를 `@geowirehq/schema`로 즉시 검증 +
  capability와 구현 메서드 일치 검사(capability에 "search"가 있는데
  `searchPlaces` 미구현이면 생성 시점 에러).

완료 기준(DoD):
- [ ] 단위 테스트: 재시도/타임아웃/에러 매핑/manifest-capability 일치 검사
- [ ] `defineProvider`로 만든 mock provider가 타입 안전하게 동작
- [ ] JSDoc으로 공개 API 전체 문서화 (이 파일이 곧 provider 작성 가이드의 원천)

### Phase 2 — `packages/provider-testkit` (예상 2~3일)

"testkit 통과 = 머지 가능" 규칙의 구현체.

```text
packages/provider-testkit/src/
├── conformance.ts     # runConformanceTests(provider, opts)
├── fixtures.ts        # 픽스처 로더 + 레코더 (record 모드: 실호출 저장)
├── mock-server.ts     # 401/429/500/타임아웃 시뮬레이션
└── index.ts
```

검증 항목:
1. manifest가 스키마에 유효한가
2. capability ↔ 메서드 구현 일치
3. 픽스처 응답 → 반환된 `ProviderPlace`가 스키마에 유효한가
4. HTTP 오류가 정규화된 `GeoProviderError`로 변환되는가 (mock-server 사용)
5. 타임아웃 시 `TIMEOUT` 에러 + AbortSignal 준수
6. manifest에 `attributionRequired`가 있으면 결과에 반영 가능한 정보가 있는가

DoD:
- [ ] 레퍼런스 mock provider가 전 항목 통과
- [ ] 실패 케이스별 명확한 에러 메시지 (기여자가 스스로 고칠 수 있는 수준)
- [ ] `live: true` 모드 분리 (CI에서는 픽스처만, 로컬에서만 실호출)

### Phase 3 — `packages/providers/nominatim` (예상 2~3일)

키 없이 동작하는 기본 공급자. **Zero-config(P1)의 근간.**

- 엔드포인트: `/search` (search + geocode), `/reverse` (reverseGeocode), `format=jsonv2`
- capabilities: `search`, `geocode`, `reverseGeocode`
- OSM 태그 → 표준 카테고리 매핑: `data/category-map.json` (~50개로 시작,
  커뮤니티 PR 대상 데이터 파일)
- **공용 서버 예절 준수 (평판 리스크)**: 1 req/s 토큰버킷을 provider 내부에서 강제,
  `User-Agent: geowire/<version> (+https://geowire.dev)` 필수,
  `baseUrl` 설정으로 자체 호스팅 Nominatim 전환 가능
- manifest.policy: `maxCacheTtlSeconds: 86400`, `canStorePermanently: true`(ODbL),
  `attributionRequired: "© OpenStreetMap contributors"`

DoD:
- [ ] conformance 통과 (픽스처: 호치민 약국 검색, 한국 주소 지오코딩, 역지오코딩)
- [ ] 실호출 스모크: `Nguyễn Huệ` 같은 유니코드 쿼리 정상 처리
- [ ] rate limit 강제 동작 테스트

### Phase 4 — `packages/core` (예상 8~10일, 최대 작업)

```text
packages/core/src/
├── config/
│   ├── schema.ts      # GeoWireConfig Zod 스키마 (설계 §8.1)
│   ├── load.ts        # yaml 로드 + ${ENV} 치환 + zero-config 기본값
│   └── warnings.ts    # 평문 키 감지 경고 등
├── registry.ts        # provider 등록·활성화·자격증명 필터
├── pipeline/
│   ├── pipeline.ts    # 단계 조립 (validate→normalize→plan→execute→...)
│   ├── normalize-request.ts   # 국가 추론(near→국가), 언어 감지
│   ├── plan.ts        # 호출 계획 (국가 라우팅→capability→자격증명→예산 필터)
│   ├── execute.ts     # 병렬 호출, per-provider 타임아웃, 부분 실패 수집
│   ├── strategies/
│   │   ├── first-success.ts
│   │   └── merge.ts
│   ├── dedup/
│   │   ├── dedup.ts       # geohash 버킷팅 → 쌍별 점수 → 병합
│   │   ├── similarity.ts  # Jaro-Winkler, 이름 정규화(NFKC·법인접미사 제거)
│   │   └── merge-fields.ts # 필드별 공급자 강점 우선순위 병합 + sources[].fields 기록
│   ├── rank.ts        # 거리40/영업시간25/공급자신뢰20/최신성15 (설정 가능)
│   └── policy.ts      # attribution 주입, 캐시 TTL 상한 강제
├── cache/
│   ├── adapter.ts     # CacheAdapter 인터페이스
│   └── memory.ts      # LRU (키 = 정규화된 요청 해시)
├── cost.ts            # manifest.cost 기반 사전 추정 + meta.estimatedCostUSD
├── ids.ts             # gwp_ ID 생성 (provider:placeId 안정 해시)
├── circuit-breaker.ts # 공급자별 연속 실패 시 일시 제외
└── geowire.ts         # createGeoWire() 퍼사드 — SDK embedded 모드의 진입점
```

구현 순서 (내부 마일스톤):
1. config + registry + `createGeoWire()` 골격
2. pipeline + `first-success` → **Nominatim으로 첫 E2E 검색 성공** ⭐
3. `merge` + dedup v1 + rank
4. cache + policy + cost + circuit-breaker
5. meta 블록 완성 (providersUsed/Skipped/Failed, dedup before/after, cache, cost)

DoD:
- [x] fake provider 2개로 통합 테스트: fallback 시나리오(1번 실패→2번 응답),
      merge 시나리오(44→27→8 스타일 dedup 검증), 키 없음 skip 시나리오
- [x] dedup 정확도 스냅샷 테스트 (같은 약국이 Google/OSM 이름 표기만 다른 케이스 10쌍)
- [x] zero-config 경로: 설정 파일 없이 `createGeoWire()` → nominatim 검색 성공 (실제 nominatim provider + 픽스처 fetch로 E2E)
- [x] 모든 응답이 `SearchPlacesResponse` 스키마 파싱 통과 (런타임 자기 검증 테스트)

**추가 구현 메모(설계 반영):**
- near→국가 역추론은 오프라인 국가 경계 데이터 필요 → v0.3 국가 라우팅과 함께(현재 명시 country만 라우팅 반영)
- 혼합 캐시 불변식 구현: 캐시 금지 소스(TTL=null) 기여 시 전체 미캐시, 아니면 최솟값 TTL. 순서 `merge→policy→cache` 고정
- 전부 실패/스킵한 응답은 캐시하지 않음(장애 캐시 방지)
- getPlace(단수 반환)는 Phase 6 MCP `get_place` 착수 시 추가 예정(현재 list 반환 3연산만: search/geocode/reverse)

### Phase 5 — `providers/google` + `providers/internal` (예상 4~5일)

**google** (BYOK):
- Places API (New): Text Search + Place Details, Geocoding API: geocode/reverse
- capabilities: `search`, `geocode`, `reverseGeocode`, `getPlace`, `autocomplete`
- manifest.cost.perCall에 공식 단가 기입 (비용 추적의 첫 실데이터)
- manifest.policy: `maxCacheTtlSeconds: null`(원본 캐시 금지),
  `canStorePermanently: false` (place ID는 예외적으로 저장 가능 — 약관 근거 주석)
- 키 없으면 registry가 `MISSING_CREDENTIALS`로 skip (전체 실패 금지)

**internal** (고객 자체 데이터):
- CSV 로더 (`store_id,name,address,phone,latitude,longitude,opening_hours,...`)
- 인메모리 검색: 이름 부분일치 + Haversine 반경 필터. `priority: 100` 기본
- v0.1은 CSV만. PostgreSQL/PostGIS는 v0.3

DoD:
- [x] 둘 다 conformance 통과
- [x] E2E: internal(CSV) + nominatim + google(키 있으면) 3-공급자 merge 동작
- [x] google 키 미설정 시 meta.providersSkipped에 정확히 기록

**추가 구현 메모(설계 반영):**
- google `autocomplete`은 좌표 없는 예측만 반환해 `ProviderPlace`(location 필수)와 불일치 → v0.1 capability에서 제외(v0.2 예측 모델 별도)
- google 영업시간은 사람이 읽는 `weekdayDescriptions`라 OSM opening_hours로 무손실 변환 불가 → `metadata.googleWeekdayDescriptions`로 보존, `business.openingHours`는 v0.2 파서 도입 후
- google policy: place ID/내부 ID는 약관 예외로 영속 저장 허용(원본 데이터는 저장·캐시 금지) — manifest 주석에 근거 명시
- internal CSV: 컬럼 별칭(store_id/id, lat/latitude, lng/lon 등) 흡수, `source`(경로)/`csv`(텍스트)/`records`(배열) 3가지 입력 지원

### Phase 6 — `packages/mcp` (예상 3~4일)

- 도구 5종: `search_places` `get_place` `geocode_address` `reverse_geocode`
  `list_geo_providers`
- inputSchema는 `@geowirehq/schema` Zod → JSON Schema 변환으로 자동 생성 (수기 금지)
- **도구 설명문 = 제품**: LLM이 올바르게 선택·호출하도록 설명·예시를 신중히 작성,
  프롬프트 회귀 테스트(도구 선택 시나리오 스냅샷)
- 응답: 사람이 읽는 요약 텍스트 + `structuredContent`(스키마 준수 JSON) 병행
- 전송: stdio (`bin: geowire-mcp`, `npx -y @geowirehq/mcp`로 즉시 실행)
- 에러: LLM이 자가 수정 가능한 메시지 ("query is required. Example: ...")

DoD:
- [x] MCP Inspector로 5개 도구 전부 호출 성공 (→ InMemoryTransport client-server E2E로 프로그래매틱 검증 + stdio bin JSON-RPC 스모크)
- [ ] Claude Desktop 실기기 테스트: "호치민 1군 근처 24시간 약국 찾아줘" 성공 **(사용자 수동 검증 필요 — stdio 서버·프로토콜은 검증 완료)**
- [x] 키 없는 환경에서 nominatim-only로 정상 동작 (P1 검증)

**추가 구현 메모(설계 반영):**
- MCP low-level `Server` + `setRequestHandler(ListTools/CallTool)` 사용 — inputSchema를 `z.toJSONSchema`로 직접 생성($schema 제거·default 필드 required 제외 후처리)해 "수기 금지" 요건 충족
- 응답은 사람이 읽는 요약 텍스트 + `structuredContent`(스키마 준수 JSON) 병행. outputSchema는 v0.1 미선언(클라이언트 검증 부담 회피, v0.2 검토)
- bin은 stdout=프로토콜 전송이라 **로그를 stderr로만** 출력. `GOOGLE_MAPS_API_KEY`/`GEOWIRE_INTERNAL_CSV`/`GEOWIRE_CONFIG` 환경변수로 provider opt-in
- 부수 수정: `collectConfigWarnings`의 EMPTY_PROVIDERS 오탐 수정(config.providers가 비어도 registry에 인스턴스 있으면 정상 — zero-config 경로)

### Phase 7 — `apps/server` (REST) (예상 3~4일)

- Fastify: `POST /v1/places/search`, `GET /v1/places/{id}`, `GET /v1/geocode`,
  `GET /v1/reverse-geocode`, `GET /v1/providers`, `GET /v1/health`, `GET /metrics`
- OpenAPI 3.1 자동 생성 (Zod 기반) + `/docs` Swagger UI
- MCP Streamable HTTP를 같은 프로세스에 마운트 (`/mcp`)
- 선택적 인증: `GEOWIRE_API_KEYS` 설정 시 Bearer 검사
- `/metrics`: prom-client — provider별 latency/error/cost 카운터

DoD:
- [x] E2E HTTP 테스트 슈트 (inject 기반, 실서버 불필요) — REST 8종 + metrics + auth + OpenAPI 동기화 + /mcp
- [x] `pnpm --filter server start` → curl로 검색 성공 (health/providers/metrics/docs 실서버 확인, 검색 파이프라인은 fixture E2E로 검증)
- [x] OpenAPI 스키마가 schema 패키지와 자동 동기화됨을 테스트로 보증 (swagger 스펙의 body가 SearchPlacesRequest에서 자동 생성됨을 assert)

**추가 구현 메모(설계 반영):**
- **검증·직렬화는 core Zod가 담당** → fastify validator/serializer를 passthrough로 우회하고 route schema는 OpenAPI 문서 전용(draft-7). 스키마 패키지↔문서 자동 동기화 + 응답 직렬화 누락 위험 제거
- get_place 경로는 provider 참조가 슬래시(`nominatim:node/123`)를 포함할 수 있어 `/v1/places/*` 와일드카드 사용
- `/mcp`는 stateless Streamable HTTP(`reply.hijack()` + `transport.handleRequest`), 요청마다 서버·transport 생성 — REST와 MCP가 한 프로세스/포트 공유
- 환경변수: `PORT`(기본 4980)·`HOST`·`GEOWIRE_API_KEYS`(콤마 구분 Bearer)·`GOOGLE_MAPS_API_KEY`·`GEOWIRE_INTERNAL_CSV`·`GEOWIRE_CONFIG`

### Phase 8 — `packages/cli` (예상 3~4일)

```bash
npx @geowirehq/cli            # zero-config 서버 기동 (= serve의 기본형)
npx @geowirehq/cli init       # 대화형 마법사: provider 선택→키 입력→.env+config 생성→연결 검사
npx @geowirehq/cli test       # 등록된 공급자 연결 검사 ("✓ Google Places connected")
npx @geowirehq/cli search "coffee near Gangnam"   # 터미널 원샷 검색 (데모 킬러 기능)
npx @geowirehq/cli serve --config geowire.config.yaml
```

- `search`는 결과 테이블 + 출처·응답시간 표시 (README GIF 재료)
- `init`이 생성한 `.env`는 자동으로 `.gitignore` 확인·추가

DoD:
- [x] 신규 사용자 시나리오: `geowire serve` 실기동(zero-config) → /v1/health·/v1/providers 응답 확인, `init` 마법사가 .env+config+.gitignore 생성(테스트), 검색 파이프라인은 fixture E2E로 검증
- [x] Windows/macOS/Linux 경로 처리 — `path.join`/`resolve` 사용, Windows 개발 환경에서 빌드·테스트·serve 스모크 통과

**추가 구현 메모(설계 반영):**
- command 함수는 geo·IO 주입형 순수 함수(runSearch/runTest/runServe/runInit) → 외부 호출 없이 fixture로 테스트, cli.ts는 argv 라우팅 + readline만 담당
- bin 실행부는 `bin.ts`로 분리(cli.ts import 시 부작용 없음 → run/헬퍼를 안전하게 export·테스트)
- `serve`는 apps/server의 `buildServer` 재사용(CLI와 서버 동작 일치), 서버 기동은 listen이 프로세스 유지 → exit 안 함
- `init`은 평문 키를 config에 넣지 않고 `${ENV}` 참조 + `.env`(GEOWIRE 변수)로 분리, `.gitignore`에 `.env` 자동 추가

### Phase 9 — 배포·CI·문서·런칭 준비 (예상 5~6일)

**CI/CD** (`.github/workflows/`):
- [x] `ci.yml`: typecheck + test + build (Node 22, ubuntu/windows 매트릭스) — lint는 v0.1에서 typecheck로 갈음(eslint는 v0.2)
- [x] `release.yml`: Changesets 기반 버전 관리 + npm publish (changesets/action)
- [x] provider conformance 별도 job (픽스처 기반, 실호출 없음)
- [x] `.changeset/config.json` + 루트 `changeset`/`version-packages`/`release` 스크립트

**배포물**:
- [x] 멀티스테이지 `Dockerfile` (builder→`pnpm deploy --legacy`→distroless nodejs22 runner, 비루트)
- [x] `docker-compose.yml` (server 단독 + node 기반 healthcheck)
- [x] `docker run` 동작 검증 — `docker build` 성공(이미지 267MB), 컨테이너에서 /v1/health·/v1/providers·/docs 응답 + 실제 Nominatim 검색("Tour Eiffel") E2E 통과. `pnpm deploy --legacy`는 Linux 컨테이너에서 정상(Windows 로컬 심링크 실패는 pnpm 경로 버그로 Docker 무관 확인됨)

**문서·커뮤니티 장치**:
- [x] README 완성: 30초 Quickstart 4종(MCP/CLI/Docker/SDK), 비교표, 도구·엔드포인트·config 표 (히어로 GIF는 사용자 녹화 필요)
- [x] `CONTRIBUTING.md` + "Write a provider in 30 minutes" 가이드
- [x] Issue 템플릿: bug / feature / **New Provider Request** (+ config.yml)
- [x] `examples/`: claude-desktop, cursor, geowire.config.yaml, customer-csv, langchain, vercel-ai-sdk
- [ ] **(사용자)** `good first issue` 15~20개 등록 (GitHub 계정 필요)

**런칭 체크리스트 (전부 외부 계정/수동 작업 — 사용자):**
- [ ] GitHub org 이전 + public 전환, npm publish (`NPM_TOKEN` 시크릿 설정 후 release.yml 자동)
- [ ] 데모 GIF 2종 녹화 (`geowire search` + Claude Desktop)
- [ ] MCP 디렉터리 등록: Smithery, mcp.so, Glama, PulseMCP
- [ ] awesome-mcp-servers PR
- [ ] Show HN 초안 + r/LocalLLaMA + X 스레드
- [ ] 공개 후 첫 72시간 이슈 대응 체제

---

## 3. 주차별 일정 (8주 기준, 1인 개발 가정)

| 주차 | 내용 | 검증 마일스톤 |
|---|---|---|
| W1 | Phase 1 + 2 (provider-sdk, testkit) | mock provider가 testkit 통과 |
| W2 | Phase 3 (nominatim) + core 골격 | 코드에서 Nominatim 검색 성공 ⭐ |
| W3 | Phase 4 (pipeline, first-success, merge) | fallback E2E 통과 |
| W4 | Phase 4 (dedup, rank, cache, policy, meta) | 3-공급자 merge + dedup 데모 |
| W5 | Phase 5 (google, internal CSV) | BYOK + 고객 데이터 우선순위 동작 |
| W6 | Phase 6 (MCP) | Claude Desktop 실사용 성공 ⭐ |
| W7 | Phase 7 + 8 (REST, CLI) | `npx @geowirehq/cli` 5분 시나리오 통과 |
| W8 | Phase 9 (CI, Docker, 문서, 런칭) | **v0.1.0 publish + 런칭** 🚀 |

버퍼: dedup 품질(W4)과 MCP 도구 설명 튜닝(W6)이 지연 위험 최대 —
각각 +2일 버퍼를 W5, W7에 흡수.

---

## 4. 공통 규약 (전 Phase 적용)

- **ESM only, TS strict**, `verbatimModuleSyntax` — 이미 base 설정에 반영됨
- 모든 공개 API에 JSDoc (docs 사이트 자동 추출 대비)
- 로깅: `pino` 인터페이스로 통일, provider에는 context.logger만 노출
- 에러: core 외부로 나가는 에러는 전부 정규화된 코드 보유
- 버전: Changesets, `@geowirehq/*` 패키지 간 workspace 프로토콜
- 테스트 계층: 단위(각 패키지) → conformance(provider) → 통합(fake provider) →
  E2E(HTTP inject / MCP Inspector). **실외부호출은 CI에서 금지** (픽스처만)
- 커밋: Conventional Commits (`feat(core): ...`) — 릴리스 노트 자동화 대비

---

## 5. v0.1 완료 정의 (런칭 게이트)

아래 시나리오가 전부 통과하면 v0.1.0 태그:

1. [x] **Zero-config**: 키 0개로 `geowire serve` → `/v1/places/search` 동작 (server 실기동 + fixture E2E)
2. [~] **MCP**: 서버·5개 도구·stdio/HTTP 전송 검증 완료 — Claude Desktop 실기기 연결만 사용자 수동
3. [x] **BYOK**: `GOOGLE_MAPS_API_KEY` 있으면 merge에 google 소스 등장 + 비용 노출, 없으면 MISSING_CREDENTIALS skip (3-공급자 E2E)
4. [x] **Fallback**: 1순위 실패 → 2순위 자동 전환 + meta.providersFailed 기록 (first-success 테스트)
5. [x] **고객 데이터**: CSV 등록 → 자체 매장(priority 100) 최상위 (3-공급자 E2E)
6. [x] **Dedup**: 동일 장소 2-공급자 → 결과 1건 + sources 2개 (dedup 스냅샷 + merge E2E)
7. [x] **투명성**: 모든 응답 meta에 used/skipped/failed·strategy·dedup·cost 존재 (전 파이프라인 테스트)
8. [x] **Docker**: `docker build` 성공(267MB) → `docker run -p 4980:4980`로 health·providers·docs·실검색 재현 확인

→ 게이트 1·3·4·5·6·7·8 통과, **2(MCP)는 Claude Desktop 실기기 연결만** 사용자 수동 잔여.

---

## 6. 리스크와 대응 (구현 관점)

| 리스크 | 징후 | 대응 |
|---|---|---|
| dedup 품질 미달 | 다른 장소 오병합 / 같은 장소 미병합 | 임계값 보수적(0.75) 시작, 0.6~0.75는 병합 대신 표기. 실측 케이스 스냅샷 축적 |
| Google API (New) 마이그레이션 복잡도 | 문서와 실동작 차이 | Phase 5 첫날 스파이크(반나절)로 실호출 확인 후 본구현 |
| MCP 도구 오선택 (LLM이 잘못 씀) | Claude가 도구를 안 쓰거나 인자 오류 | 설명문에 예시 포함, 에러 메시지를 자가수정 가능하게, 실사용 회귀 시나리오 유지 |
| Nominatim 공용 서버 차단 | 429/차단 | rate limit 코드 강제 + UA 명시. 픽스처 우선 개발로 호출 최소화 |
| 스코프 크리프 | v0.2 기능 유혹 (Redis, Playground...) | §5 런칭 게이트 외 기능은 전부 이슈로만 기록 |
| Windows 개발 ↔ Linux 배포 차이 | 경로·프로세스 이슈 | CI 매트릭스에 ubuntu 포함, Docker로 최종 검증 |

---

## 7. v0.1 이후 즉시 착수 항목 (참고, 설계 §11)

- **v0.2**: Playground 비교 UI, 공개 데모, Python SDK, Mapbox/Foursquare,
  Redis 어댑터, dedup v2
- **v0.3**: 국가별 라우팅, cost-aware 전략, Kakao/Naver/HERE, PostGIS,
  스펙 v1 draft 공개 + RFC 프로세스
