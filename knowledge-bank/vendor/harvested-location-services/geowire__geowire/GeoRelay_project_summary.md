# GeoRelay 프로젝트 기획 및 설계 정리

## 1. 프로젝트 개요

### 1.1 프로젝트 가칭

**GeoRelay**

대안 이름:

- PlaceBridge
- AtlasGateway
- GeoMux
- AnyPlace
- OpenPlaceRouter

### 1.2 핵심 정의

> AI 에이전트와 여러 지도·장소 데이터 공급자 사이에 위치하는 오픈소스 지리정보 검색 게이트웨이

GeoRelay는 Google Maps, OpenStreetMap, Mapbox, HERE, Foursquare, Kakao, Naver, Pelias 및 고객 자체 데이터를 하나의 공통 인터페이스로 연결한다.

### 1.3 해결하려는 문제

AI 서비스에서 장소 검색을 구현하려면 공급자마다 API 규격, 인증 방식, 응답 형식, 가격, 데이터 품질 및 이용약관이 다르다.

기존 방식에서는 개발자가 공급자별로 별도의 연동 코드를 작성해야 한다.

```text
AI 서비스
 ├── Google Places 연동
 ├── Mapbox 연동
 ├── HERE 연동
 ├── Kakao 연동
 └── Naver 연동
```

GeoRelay를 사용하면 다음처럼 단일 인터페이스로 통합할 수 있다.

```text
AI 서비스
    ↓
GeoRelay
    ↓
Google / OSM / Mapbox / HERE / Kakao / Naver / 자체 데이터
```

### 1.4 프로젝트의 핵심 가치

단순한 API 래퍼가 아니라 다음 기능을 제공해야 차별성이 생긴다.

- 통합 장소 스키마
- 공급자 추상화
- 공급자 장애 시 자동 대체
- 국가별 최적 공급자 라우팅
- 비용 기반 라우팅
- 다중 공급자 결과 병합
- 중복 장소 제거
- 데이터 출처 표시
- 자체 호스팅
- MCP 지원
- REST API 및 SDK
- 고객 자체 데이터 검색
- 이용정책 및 저장정책 관리

---

## 2. 목표 사용자와 시장 수요

## 2.1 AI 에이전트 및 챗봇 개발사

가장 직접적인 초기 사용자다.

예시 요청:

- 회사 근처 회식 장소 검색
- 출장지 호텔과 식당 추천
- 고객 주소를 좌표로 변환
- 여러 지점 중 가장 가까운 매장 검색
- 이메일에 포함된 주소 확인
- 특정 장소의 영업시간과 전화번호 조회

AI 에이전트 개발사에는 다음 기능이 중요하다.

- MCP 연결
- 자연어 장소 검색
- 표준 JSON 응답
- 공급자 교체
- 장애 자동 우회
- 비용 제한
- 결과 출처 표시

**수요 강도:** 매우 높음  
**초기 지불 가능성:** 중간  
**오픈소스 사용자 확보 가능성:** 매우 높음

---

## 2.2 여행·출장·일정관리 AI 서비스

여행 서비스는 장소 데이터를 반복적으로 사용한다.

```text
도시 선택
→ 관광지 검색
→ 식당 검색
→ 호텔 검색
→ 거리 계산
→ 영업시간 확인
→ 일정 구성
```

고객 후보:

- 여행 일정 생성 SaaS
- 출장 관리 서비스
- 호텔 및 항공 예약 서비스
- 디지털 노마드 앱
- 지역 관광 앱
- 호텔 컨시어지 챗봇
- 여행사 상담 AI

필요 데이터:

- 위치
- 카테고리
- 거리
- 영업시간
- 평점
- 리뷰
- 전화번호
- 웹사이트
- 가족 친화 여부
- 예약 가능 여부

**수요 강도:** 높음  
**관리형 API 지불 가능성:** 중간~높음

---

## 2.3 배달·물류·현장 서비스

실제 비용을 지불할 가능성이 높은 시장이다.

필요 기능:

- 주소 정제
- 주소를 좌표로 변환
- 잘못된 주소 감지
- 배송지 후보 추천
- 가까운 기사·창고·매장 검색
- 지도 공급자 장애 대체
- 국가별 주소 체계 대응
- 대량 지오코딩

예를 들어 같은 베트남 주소가 다음처럼 다양하게 입력될 수 있다.

```text
12 Nguyen Hue
12 Nguyễn Huệ
12 Nguyen Hue, Q1
12 Nguyễn Huệ, Phường Sài Gòn
```

GeoRelay는 여러 공급자의 결과를 비교하여 다음과 같은 결과를 제공할 수 있다.

```json
{
  "normalizedAddress": "12 Nguyễn Huệ, Ho Chi Minh City, Vietnam",
  "latitude": 10.77,
  "longitude": 106.70,
  "confidence": 0.91,
  "sources": ["google", "nominatim"]
}
```

고객 후보:

- 배달 플랫폼
- 택배 회사
- 퀵서비스
- 방문 설치 및 수리 서비스
- 보험 현장 조사
- 렌터카
- 차량 관제
- B2B 영업 방문 관리

**수요 강도:** 매우 높음  
**지불 가능성:** 매우 높음  
**진입 난이도:** 높음

---

## 2.4 글로벌 SaaS 회사

국가별로 강한 지도 공급자가 다르다.

```text
한국: Kakao, Naver, Google
중국: Amap, Baidu
미국: Google, Mapbox, Foursquare
유럽: Google, HERE, OSM
베트남: Google, OSM, 현지 데이터
```

글로벌 SaaS가 겪는 문제:

- 국가별 데이터 품질 차이
- 가격 차이
- 주소 체계 차이
- 현지어 검색 문제
- 공급자 장애
- 공급자 종속
- 약관 차이

GeoRelay 설정 예시:

```yaml
routing:
  KR:
    - kakao
    - naver
    - google

  US:
    - google
    - foursquare
    - mapbox

  VN:
    - google
    - nominatim
```

고객 후보:

- 글로벌 CRM
- 프랜차이즈 관리 SaaS
- 예약 시스템
- 고객지원 플랫폼
- 부동산 플랫폼
- 해외 커머스
- 다국가 매장 관리 시스템

**수요 강도:** 높음  
**지불 가능성:** 높음

---

## 2.5 프랜차이즈·리테일·상권 분석

주요 수요는 검색보다 POI 데이터 통합에 있다.

활용 예:

- 반경 1km 내 경쟁 매장 수
- 특정 지역 내 업종 분포
- 신규 매장 후보지 분석
- 브랜드별 지점 통합
- 폐업 및 이전 가능성 확인
- 공급자별 매장 정보 비교

필요 기능:

- 대량 검색
- 지역 단위 데이터 수집
- 변경 이력
- 체인점 식별
- 중복 제거
- 카테고리 표준화
- 데이터 품질 점수

주의할 점:

상용 지도 공급자의 데이터를 대량 수집하거나 재판매하는 기능은 공급자 약관과 충돌할 수 있으므로 별도 검토가 필요하다.

**수요 강도:** 중간 이상  
**지불 가능성:** 높음  
**법적·정책적 난이도:** 높음

---

## 2.6 기업 내부 AI 플랫폼

기업은 외부 지도 API를 직접 호출하기보다 자체 게이트웨이를 두려는 수요가 있다.

주요 이유:

- API 키 중앙 관리
- 사용량 통제
- 비용 관리
- 감사 로그
- 위치 검색 기록 보호
- 공급자 허용 목록 관리
- 데이터 보존 정책
- 전용 배포

고객 후보:

- 금융회사
- 보험회사
- 대기업
- 정부기관
- 사내 AI 플랫폼 운영팀
- 보안 요구가 높은 SaaS

**수요 강도:** 중간  
**지불 가능성:** 매우 높음  
**진입 난이도:** 매우 높음

---

## 2.7 로봇·드론·현장 자동화

장기적으로 큰 시장이지만 초기 범위에는 적합하지 않다.

필요 기능:

- 실시간 위치
- 공간 이해
- 이동 가능 영역
- 시설 및 건물 데이터
- 실내 지도
- 장애물 및 도로 상태
- 고정밀 좌표

일반 장소 검색보다 정확도와 실시간성 요구가 훨씬 높다.

**장기 수요:** 매우 높음  
**초기 진입 추천:** 낮음

---

## 2.8 시장 우선순위

| 순위 | 시장 | 사용 수요 | 지불 가능성 | 진입 난이도 |
|---|---|---:|---:|---:|
| 1 | AI 에이전트 개발사 | 매우 높음 | 중간 | 낮음 |
| 2 | 여행·출장 AI | 높음 | 중간~높음 | 중간 |
| 3 | 배달·물류 | 매우 높음 | 매우 높음 | 높음 |
| 4 | 글로벌 SaaS | 높음 | 높음 | 중간 |
| 5 | 프랜차이즈·상권 분석 | 높음 | 높음 | 높음 |
| 6 | 기업 내부 AI | 중간 | 매우 높음 | 매우 높음 |
| 7 | 로봇·드론 | 장기적 높음 | 높음 | 매우 높음 |

---

## 3. 제품 포지셔닝

### 3.1 오픈소스 단계

> Add reliable place search to any AI agent with one MCP server.

한국어 표현:

> 하나의 MCP 서버로 모든 AI 에이전트에 신뢰할 수 있는 장소 검색 기능을 추가한다.

### 3.2 사업화 단계

> 여러 지도 공급자의 비용, 품질, 장애 및 국가별 차이를 관리하는 Geo Search Infrastructure

### 3.3 피해야 할 포지셔닝

다음 정도로만 설명하면 차별성이 약하다.

> 여러 지도 API를 하나로 묶어주는 서비스

기존 라이브러리와 차별화하려면 반드시 다음이 필요하다.

- 공급자 독립성
- 자체 호스팅
- 비용 기반 라우팅
- 다중 공급자 검증
- 데이터 정책 관리
- 기업 보안
- 도메인별 주소 정제
- MCP 지원

---

## 4. 전체 시스템 아키텍처

```text
AI Agent / Application
        ↓
┌──────────────────────────────┐
│ REST API / SDK / MCP Server  │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│         GeoRelay Core        │
│                              │
│ - Provider Router            │
│ - Normalizer                 │
│ - Deduplicator               │
│ - Ranker                     │
│ - Cache                      │
│ - Policy Engine              │
│ - Cost Controller            │
└──────────────────────────────┘
        ↓
┌─────────────────────────────────────────────┐
│ Google / OSM / Mapbox / HERE / Foursquare │
│ Kakao / Naver / Pelias / Customer Data    │
└─────────────────────────────────────────────┘
```

---

## 5. 저장소 구조

대형 모노레포 기준 제안:

```text
apps/
  api/
  mcp-server/
  playground/
  docs/

packages/
  core/
  schema/
  provider-sdk/
  provider-google/
  provider-mapbox/
  provider-nominatim/
  provider-pelias/
  provider-kakao/
  provider-naver/
  sdk-typescript/
  sdk-python/

examples/

specs/

deploy/

tests/
```

### 주요 앱

- `apps/api`: REST API 서버
- `apps/mcp-server`: MCP 서버
- `apps/playground`: 검색 테스트 및 공급자 비교 화면
- `apps/docs`: 문서 사이트

### 주요 패키지

- `core`: 라우팅, 병합, 중복 제거, 정책 처리
- `schema`: 공통 Place 스키마
- `provider-sdk`: 공급자 플러그인 인터페이스
- `provider-*`: 각 지도 공급자 어댑터
- `sdk-typescript`: TypeScript SDK
- `sdk-python`: Python SDK

---

## 6. 공통 Place 스키마

추천 기본 모델:

```ts
interface Place {
  id: string;
  name: string;
  categories: string[];

  location: {
    latitude: number;
    longitude: number;
  };

  address?: {
    formatted?: string;
    country?: string;
    region?: string;
    city?: string;
    district?: string;
    street?: string;
    postalCode?: string;
  };

  contact?: {
    phone?: string;
    website?: string;
  };

  business?: {
    openingHours?: unknown;
    priceLevel?: number;
    rating?: number;
    reviewCount?: number;
  };

  distanceMeters?: number;
  confidence?: number;

  sources: PlaceSource[];

  metadata?: Record<string, unknown>;
}
```

### PlaceSource

단일 공급자 필드보다 배열을 사용하는 것이 중요하다.

```ts
interface PlaceSource {
  provider: string;
  providerPlaceId: string;
  fetchedAt?: string;
  confidence?: number;
}
```

예:

```json
{
  "id": "georelay_place_123",
  "name": "Bornga Korean Restaurant",
  "location": {
    "latitude": 10.78,
    "longitude": 106.69
  },
  "sources": [
    {
      "provider": "google",
      "providerPlaceId": "ChIJxxx"
    },
    {
      "provider": "mapbox",
      "providerPlaceId": "poi.xxx"
    }
  ]
}
```

이 구조를 사용하면 여러 공급자의 정보를 하나의 장소로 병합할 수 있다.

---

## 7. Provider SDK

공급자는 플러그인 방식으로 추가한다.

```ts
interface GeoProvider {
  manifest: ProviderManifest;

  searchPlaces?(request: SearchPlacesRequest): Promise<ProviderResult>;
  autocomplete?(request: AutocompleteRequest): Promise<ProviderResult>;
  geocode?(request: GeocodeRequest): Promise<ProviderResult>;
  reverseGeocode?(request: ReverseGeocodeRequest): Promise<ProviderResult>;
  getPlace?(request: GetPlaceRequest): Promise<ProviderResult>;
  nearbySearch?(request: NearbySearchRequest): Promise<ProviderResult>;
  healthCheck?(): Promise<ProviderHealth>;
}
```

### ProviderManifest

```ts
interface ProviderManifest {
  id: string;
  name: string;
  capabilities: string[];
  authType: "apiKey" | "oauth" | "none";
  coverage?: string[];
  rateLimit?: {
    requestsPerSecond?: number;
  };
}
```

---

## 8. 검색 전략

GeoRelay는 공급자 호출 전략을 선택할 수 있어야 한다.

### 8.1 First Success

우선순위가 높은 공급자를 호출하고 성공하면 종료한다.

```text
Google 성공 → 종료
Google 실패 → OSM 호출
```

### 8.2 Merge

여러 공급자를 동시에 호출하여 결과를 병합한다.

```text
Google + OSM + Mapbox
→ 정규화
→ 중복 제거
→ 통합 결과
```

### 8.3 Fastest

여러 공급자를 동시에 호출하고 가장 빠른 유효 결과를 반환한다.

### 8.4 Weighted

공급자별 신뢰도와 지역별 품질 점수를 반영한다.

### 8.5 Cost-aware

예산, 예상 호출 비용 및 캐시 상태를 고려해 공급자를 선택한다.

이 기능은 GeoRelay의 주요 차별화 요소가 될 수 있다.

---

## 9. 중복 장소 탐지

LLM보다 규칙 기반 점수 계산이 적합하다.

비교 요소:

- 좌표 거리
- 장소명 유사도
- 주소 유사도
- 전화번호
- 웹사이트
- 카테고리
- 체인 브랜드

예시 점수:

```text
좌표 거리       35%
장소명 유사도   30%
주소 유사도     20%
전화번호        10%
웹사이트         5%
```

특정 기준 이상이면 같은 장소로 병합한다.

---

## 10. MCP 도구

MCP 도구는 너무 많이 만들지 않는 것이 좋다.

추천 도구:

- `search_places`
- `get_place`
- `geocode_address`
- `reverse_geocode`
- `list_geo_providers`

예:

```json
{
  "name": "search_places",
  "arguments": {
    "query": "24-hour pharmacy",
    "near": {
      "latitude": 10.78,
      "longitude": 106.69
    }
  }
}
```

---

## 11. 지도정보 확보 방식

GeoRelay는 상용 지도 전체를 긁어서 자체 DB에 복제하는 방식이 아니다.

다음 네 가지 소스를 함께 사용한다.

1. 공식 상용 API 실시간 호출
2. OpenStreetMap 오픈데이터 자체 적재
3. 고객 자체 장소 데이터
4. 정부 및 공공데이터

웹 크롤링은 허가된 범위에서만 보조적으로 사용한다.

---

## 12. 공식 API 실시간 호출

사용자 요청이 들어오면 필요한 공급자 API를 호출한다.

```text
사용자 요청
   ↓
GeoRelay
   ├── Google Places API
   ├── Mapbox Search API
   ├── HERE API
   ├── Foursquare API
   └── Nominatim
```

각 공급자 응답을 공통 스키마로 변환한다.

### 장점

- 최신 장소정보 확보
- 초기 개발이 빠름
- 대형 지도 DB 불필요
- 여러 공급자 비교 가능

### 단점

- API 비용
- 호출 제한
- 외부 장애 영향
- 공급자별 약관
- 저장 제한

---

## 13. OpenStreetMap 자체 구축

오픈소스 프로젝트의 기본 데이터는 OSM이 적합하다.

### 데이터 흐름

```text
OSM 지역 PBF 파일
      ↓
osm2pgsql / imposm
      ↓
PostgreSQL + PostGIS
      ↓
Nominatim 또는 Pelias
      ↓
GeoRelay Provider Adapter
```

처음부터 전 세계 데이터를 운영하지 않고 특정 국가부터 시작할 수 있다.

예:

- 베트남
- 한국
- 미국 일부 지역

### 업데이트

```text
초기:
국가 단위 PBF 전체 적재

이후:
minute / hour / day replication diff 반영
```

### 공용 Nominatim 사용 주의

공용 Nominatim 서버는 테스트나 소량 사용에는 적합하지만 제품의 대량 백엔드로 사용하면 안 된다.

권장:

```text
개발:
공용 Nominatim 제한적 사용

운영:
자체 Nominatim 또는 유료 운영 서비스
```

---

## 14. 고객 자체 데이터

기업 고객에게 가장 가치 있는 데이터일 수 있다.

예시 CSV:

```csv
store_id,name,address,phone,latitude,longitude,opening_hours
001,Arena Karaoke,123 Nguyen...,090...,10.77,106.69,18:00-04:00
```

수집 대상:

- 매장
- 창고
- 대리점
- 배송지
- 영업 대상 업체
- 내부 시설
- 계약 매장

검색 우선순위 예:

```text
1순위: 고객 자체 데이터
2순위: 자체 OSM
3순위: Google·Mapbox 등 외부 API
```

외부 지도에서 얻기 어려운 데이터:

- 실제 영업시간
- 내부 매장 코드
- 담당자
- 배송 가능 여부
- 주차 여부
- 계약 상태
- 출입 방법

---

## 15. 정부 및 공공데이터

활용 가능한 데이터:

- 행정구역 경계
- 도로명 주소
- 지번
- 공공시설
- 병원
- 약국
- 학교
- 대피소
- 버스정류장
- 관광시설
- 주차장

일반적인 형식:

- 공공 API
- CSV
- Excel
- GeoJSON
- Shapefile

각 데이터의 라이선스와 갱신주기를 별도로 확인해야 한다.

---

## 16. 웹 크롤링

웹 크롤링은 핵심 수집 수단으로 추천하지 않는다.

문제:

- robots.txt
- 서비스 이용약관
- 저작권
- 개인정보
- 오래된 정보
- 중복 업체
- 구조 변경
- 차단 가능성

허용 가능한 범위:

- 고객이 소유한 홈페이지
- 공식 업체 홈페이지
- 명확한 공개 라이선스 데이터
- 제휴 및 허가된 사이트

크롤링 정보는 신뢰도를 낮게 설정한다.

```json
{
  "source": "web_crawl",
  "confidence": 0.62,
  "lastVerifiedAt": "2026-07-17"
}
```

---

## 17. 지도 데이터와 장소 데이터의 구분

### 지도 데이터

- 도로
- 건물
- 하천
- 행정구역
- 지도 타일
- 경로 네트워크

### 장소 데이터

- 식당
- 카페
- 호텔
- 병원
- 매장
- 관광지
- 영업시간
- 평점
- 전화번호

GeoRelay 초기 버전은 지도 그림 자체보다 장소 검색과 주소 검색에 집중한다.

### 초기 범위

- 장소 검색
- 주소 검색
- 좌표 검색
- 주변 장소
- 자체 매장 검색

### 후속 범위

- 지도 타일
- 경로 탐색
- 실시간 교통
- 내비게이션
- 실내 지도

---

## 18. 데이터 저장 정책

상용 공급자 데이터를 마음대로 장기 저장하거나 재배포할 수 있다고 가정하면 안 된다.

DB를 두 층으로 분리하는 것이 좋다.

### Permanent Store

장기 저장 대상:

- 내부 Place ID
- Provider Place ID
- 고객 자체 데이터
- OSM 데이터
- 허가된 공공데이터
- 자체 계산 점수
- 사용자 제보 데이터

```json
{
  "internalPlaceId": "place_001",
  "providerReferences": [
    {
      "provider": "google",
      "placeId": "ChIJxxx"
    },
    {
      "provider": "osm",
      "osmType": "node",
      "osmId": "123456"
    }
  ]
}
```

### Temporary Cache

공급자 정책에 따라 임시 저장:

- 검색 결과
- 영업시간
- 평점
- 사진 URL
- 상세정보
- 원본 응답

필요할 때 Provider Place ID를 이용해 최신 정보를 다시 조회한다.

---

## 19. 실제 검색 처리 예시

사용자 요청:

> 현재 위치에서 가까운 24시간 약국을 찾아줘.

### 19.1 요청 정규화

```json
{
  "query": "pharmacy",
  "near": {
    "latitude": 10.78,
    "longitude": 106.69
  },
  "filters": {
    "openNow": true,
    "open24Hours": true
  },
  "country": "VN"
}
```

### 19.2 공급자 선택

```text
베트남 정책

1. 고객 자체 데이터
2. 자체 OSM
3. Google Places
```

### 19.3 병렬 호출

```text
internal: 6건
OSM: 18건
Google: 20건
```

### 19.4 정규화

총 44개 원본 결과를 공통 Place 스키마로 변환한다.

### 19.5 중복 제거

```text
44개 → 27개
```

### 19.6 필터링

```text
27개 → 8개
```

### 19.7 순위 계산

예시:

```text
거리                 40%
영업시간 신뢰도      25%
공급자 신뢰도        20%
정보 최신성          15%
```

### 19.8 최종 응답

```json
{
  "results": [
    {
      "name": "Pharmacity",
      "distanceMeters": 420,
      "isOpenNow": true,
      "open24Hours": true,
      "confidence": 0.93,
      "sources": ["google", "osm"]
    }
  ]
}
```

---

## 20. 추천 기술 스택

```text
PostgreSQL
PostGIS
Redis
OpenSearch 선택
```

### PostgreSQL + PostGIS

저장 대상:

- 장소
- 주소
- 좌표
- 경계
- 고객 데이터
- 공급자 참조
- 데이터 출처

공간 검색 예:

```sql
SELECT *
FROM places
WHERE ST_DWithin(
  location::geography,
  ST_SetSRID(ST_MakePoint(106.69, 10.78), 4326)::geography,
  5000
);
```

### Redis

용도:

- 검색 결과 캐시
- 공급자 응답 캐시
- Rate limit
- 중복 호출 방지
- 임시 세션

### OpenSearch

필요한 경우 추가:

- 다국어 검색
- 오타 검색
- 자동완성
- 대량 POI 검색
- 복합 텍스트 랭킹

초기 MVP는 PostgreSQL 전문검색만으로도 가능하다.

---

## 21. Google Places API 연결 방식

Google Places API는 사용자가 Google Cloud에 가입하고, 결제 계정을 연결하고, API를 활성화하고, API 키를 발급해야 한다.

오픈소스에서는 일반적으로 **BYOK(Bring Your Own Key)** 방식을 사용한다.

### 사용자 책임

- Google Cloud 프로젝트 생성
- 결제 계정 연결
- Places API 활성화
- API 키 발급
- 할당량 및 비용 관리
- API 키 보안

### GeoRelay 책임

- 설정 방법 제공
- 환경변수 템플릿 제공
- 연결 테스트
- 오류 메시지 변환
- 공급자 미설정 시 자동 건너뛰기
- 비용 및 사용량 가시화
- 키 보안 권장사항 제공

---

## 22. Google API 키 설정 예시

환경변수:

```bash
GOOGLE_MAPS_API_KEY=AIzaSy...
```

설정 파일:

```yaml
providers:
  google:
    enabled: true
    apiKey: ${GOOGLE_MAPS_API_KEY}
```

TypeScript:

```ts
const geoRelay = createGeoRelay({
  providers: {
    google: {
      apiKey: process.env.GOOGLE_MAPS_API_KEY
    }
  }
});
```

---

## 23. 설치 마법사

사용자 온보딩을 쉽게 만들어야 한다.

```bash
npx georelay init
```

예시 화면:

```text
Select providers:

[x] OpenStreetMap / Nominatim
[ ] Google Places
[ ] Mapbox
[ ] HERE
```

Google 선택 시:

```text
Google Places requires your own Google Cloud API key.

1. Create a Google Cloud project
2. Enable billing
3. Enable Places API
4. Create an API key
5. Restrict the key to Places API

Paste your API key:
> ************************
```

자동 생성 파일:

```env
GEORELAY_PROVIDERS=nominatim,google
GOOGLE_MAPS_API_KEY=AIzaSy...
```

연결 검사:

```text
✓ Google Places API connected
✓ Test request succeeded
```

---

## 24. 배포 방식별 API 키 처리

### 24.1 사용자가 직접 호스팅

```text
사용자 서버
├── GeoRelay
├── Google API 키
└── Google Places 호출
```

가장 권장되는 오픈소스 방식이다.

- 키가 사용자 서버 밖으로 나가지 않음
- Google 비용을 사용자가 직접 지불
- 사용자가 할당량과 예산 통제
- GeoRelay 운영자가 비용 위험을 부담하지 않음

---

### 24.2 Hosted GeoRelay + 고객 BYOK

```text
고객
  ↓
Hosted GeoRelay
  ↓
고객이 등록한 Google 키
  ↓
Google Places
```

이 경우 키는 암호화해서 저장해야 한다.

권장 기술:

- AWS KMS
- Google Cloud KMS
- HashiCorp Vault
- 클라우드 Secret Manager

DB에는 평문 키를 저장하지 않는다.

```json
{
  "provider": "google",
  "credentialId": "cred_284",
  "maskedKey": "AIza••••••K90",
  "status": "active"
}
```

---

### 24.3 GeoRelay 운영자의 Google 키 사용

```text
모든 고객
   ↓
Hosted GeoRelay
   ↓
GeoRelay 운영자 Google 키
   ↓
Google Places
```

장점:

- 고객이 Google 계정을 만들 필요 없음
- 즉시 체험 가능
- 사용료에 마진을 붙일 수 있음

단점:

- 악용 시 큰 비용 발생
- 고객별 사용량 측정 필요
- 결제 및 선불 잔액 시스템 필요
- 공급자 약관 검토 필요
- 한 고객의 폭주가 전체 시스템에 영향
- 재판매 구조 법률 검토 필요

초기 프로젝트에는 권장하지 않는다.

---

## 25. 추천 과금 구조

### 오픈소스

- 사용자가 직접 호스팅
- 사용자가 각 공급자 키 등록
- 지도 공급자 비용은 사용자 부담

### Hosted Starter

- GeoRelay 관리형 서버
- 고객 BYOK
- GeoRelay 서버 운영비만 과금

### Managed

- 일부 공급자 사용량 포함
- 월 요청량 한도
- 초과 사용료
- 부정 사용 방지 필요

### Enterprise

- 전용 배포
- 고객 전용 Google 프로젝트
- 전용 VPC
- SLA
- 감사 로그
- SSO
- 별도 계약

예시:

| 요금제 | 지도 키 | 지도 비용 |
|---|---|---|
| Open Source | 사용자 키 | 사용자 부담 |
| Free Hosted | OSM 중심 | 서비스 제공자 부담 |
| Starter | 사용자 키 | 사용자 부담 |
| Managed | 운영자 키 또는 혼합 | 요금제 포함 |
| Enterprise | 고객 전용 프로젝트 | 계약에 따라 결정 |

---

## 26. 무료 체험 전략

Google 키를 처음부터 요구하면 설치 이탈률이 높아질 수 있다.

따라서 설치 직후에는 무료 또는 오픈데이터 공급자로 작동해야 한다.

```yaml
providers:
  osm:
    enabled: true

  google:
    enabled: false
```

사용자가 Google 키를 추가하면 검색 품질이 향상된다.

```yaml
providers:
  osm:
    enabled: true

  google:
    enabled: true
    apiKey: ${GOOGLE_MAPS_API_KEY}
```

단계별 경험:

```text
기본:
OSM 검색

Google 키 추가:
OSM + Google 병합

다른 키 추가:
OSM + Google + Foursquare + 기타
```

---

## 27. API 키 보안

GeoRelay는 안전한 기본 설정을 제공해야 한다.

권장사항:

- 공급자별 별도 키 사용
- 개발용과 운영용 키 분리
- API 제한 설정
- 가능하면 서버 IP 제한
- 일일 할당량 설정
- 예산 경고 설정
- `.env`를 Git에 커밋하지 않기
- 설정 파일에 평문 키 저장 경고

`.gitignore`:

```gitignore
.env
.env.local
.env.production
```

시작 시 경고 예:

```text
⚠ GOOGLE_MAPS_API_KEY is defined directly in georelay.config.yaml.
Use an environment variable or secret manager instead.
```

---

## 28. 공급자 키가 없을 때 처리

특정 공급자 키가 없어도 시스템 전체가 실패하면 안 된다.

```text
Google 키 없음
→ Google Provider 비활성화
→ OSM 또는 다른 공급자로 계속 검색
```

응답 예:

```json
{
  "results": [],
  "meta": {
    "providersUsed": ["nominatim"],
    "providersSkipped": [
      {
        "provider": "google",
        "reason": "MISSING_CREDENTIALS"
      }
    ]
  }
}
```

---

## 29. 설정 파일 예시

```yaml
providers:
  internal:
    enabled: true
    priority: 100

  nominatim:
    enabled: true
    baseUrl: https://nominatim.example.com
    priority: 80

  google:
    enabled: true
    apiKey: ${GOOGLE_MAPS_API_KEY}
    priority: 90

  mapbox:
    enabled: false
    accessToken: ${MAPBOX_ACCESS_TOKEN}

routing:
  defaultStrategy: cost-aware

  countries:
    KR:
      providers:
        - kakao
        - naver
        - google

    VN:
      providers:
        - internal
        - google
        - nominatim

cache:
  enabled: true
  providerResponseTtlSeconds: 3600
```

---

## 30. MVP 개발 로드맵

### v0.1

- Google Places Provider
- Nominatim Provider
- 고객 CSV 업로드
- 공통 Place 스키마
- REST API
- MCP Server
- Docker
- 기본 공급자 fallback

### v0.2

- Mapbox
- HERE
- Redis
- Playground
- 공급자 응답시간 비교
- 기본 비용 추적

### v0.3

- 다중 공급자 병합
- 중복 제거
- Python SDK
- 국가별 라우팅
- 자체 PostGIS 검색

### v1.0

- 안정화된 Provider SDK
- Kubernetes 배포
- 관측성
- 감사 로그
- 이용정책 엔진
- 엔터프라이즈 문서
- SLA 지원

---

## 31. 현실적인 첫 MVP

초기에는 OSM 전 세계 데이터를 직접 구축할 필요가 없다.

### 데이터 소스

```text
1. Nominatim API
2. Google Places API
3. 사용자 CSV 또는 PostgreSQL
```

### 컴포넌트

```text
GeoRelay Core
├── Nominatim Adapter
├── Google Adapter
└── Internal PostgreSQL Adapter
```

### 핵심 기능

- 통합 검색
- 공통 응답
- 공급자 미설정 처리
- 공급자 장애 fallback
- 고객 자체 장소 우선
- 검색 출처 표시
- 기본 캐시
- MCP 연결

이 정도만 구현해도 프로젝트의 핵심 가치를 검증할 수 있다.

---

## 32. 오픈소스 배포 전략

README 핵심 문구:

> One place-search interface for every AI and map provider.

한국어:

> 모든 AI와 지도 공급자를 위한 하나의 장소 검색 인터페이스

추천 데모:

```text
사용자 검색
   ↓
GeoRelay
   ↓
Google / OSM / Mapbox / 기타
   ↓
하나의 정규화된 결과
```

Playground에서 보여주면 좋은 정보:

- 공급자별 응답시간
- 공급자별 결과 수
- 병합 결과
- 중복 제거 전후
- 사용 공급자
- 예상 비용
- 신뢰도
- 캐시 적중 여부

---

## 33. 라이선스

추천:

**Apache License 2.0**

이유:

- 상업적 사용 가능
- 기업 도입 친화적
- 특허 조항 포함
- 오픈소스 인프라 프로젝트에 적합

반드시 명시할 사항:

> GeoRelay 코드의 라이선스와 제3자 지도 및 장소 데이터의 이용 라이선스는 서로 별개다.

Google, Mapbox, HERE, Kakao, Naver 등 각 공급자의 데이터 및 API 사용은 해당 공급자의 약관을 따라야 한다.

OSM 데이터를 사용하면 ODbL 및 표시 의무를 검토해야 한다.

---

## 34. 수익화 모델

오픈소스 코드 자체보다 운영 부담 제거에 비용을 받는다.

### Hosted GeoRelay

예시:

- 월 $29
- 월 $99
- 월 $499
- Enterprise 별도 계약

### 유료 기능

- 관리형 호스팅
- 조직별 API 키
- 사용량 대시보드
- SSO
- 감사 로그
- SLA
- 전용 서버
- VPC 배포
- 우선 지원
- 공급자 비용 분석
- 국가별 자동 라우팅
- 데이터 보존 정책
- 주소 품질 분석
- 대량 지오코딩
- 중복 매장 제거
- 체인점 판별

고객은 단순 API 통합보다 다음 가치에 돈을 지불한다.

- 개발시간 단축
- 비용 절감
- 검색 정확도 향상
- 장애 방지
- 공급자 종속 회피
- 보안 및 감사
- 주소 품질 개선

---

## 35. 주요 위험

### 35.1 대형 AI 플랫폼의 지도 기능 내장

대형 AI 및 지도 회사가 직접 MCP, 에이전트 도구 또는 통합 장소 검색 기능을 제공할 수 있다.

따라서 Google 검색을 AI에 연결하는 기능만으로는 부족하다.

### 35.2 공급자 약관

- 데이터 저장 제한
- 캐시 제한
- 표시 의무
- 리뷰 및 사진 재사용 제한
- 대량 수집 제한
- 재판매 제한

### 35.3 비용 폭주

운영자 공용 API 키를 사용할 경우 악성 사용자가 큰 비용을 발생시킬 수 있다.

### 35.4 데이터 품질

공급자별 장소명, 주소, 좌표, 영업시간이 다를 수 있다.

### 35.5 프로젝트 범위 확대

지도 타일, 내비게이션, 실시간 교통까지 포함하면 개발 범위가 급격히 커진다.

초기에는 장소 검색과 지오코딩에 집중해야 한다.

---

## 36. 최종 권장 방향

### 초기 타깃

**AI 에이전트 개발자**

### 초기 제품

**AI용 통합 장소 검색 MCP 및 REST API**

### 초기 데이터

- Nominatim 또는 자체 OSM
- Google Places BYOK
- 고객 CSV/PostgreSQL

### 초기 운영 방식

- 오픈소스 자체 호스팅
- 상용 Provider는 사용자 BYOK
- 키가 없어도 OSM으로 기본 작동
- 공급자 장애 시 자동 fallback

### 장기 사업화

- Hosted GeoRelay
- 물류·배송용 주소 품질 서비스
- 글로벌 SaaS용 국가별 라우팅
- 엔터프라이즈 전용 배포
- 비용·품질·장애 관리 대시보드

---

## 37. 한 문장 요약

> GeoRelay는 AI가 장소를 검색할 때 어떤 지도 공급자를 사용하더라도 동일하고 신뢰할 수 있는 결과를 제공하도록 만드는 오픈소스 지리정보 검색 인프라다.

---

## 38. 핵심 의사결정 요약

1. 프로젝트는 단순 API 래퍼가 아니라 Geo Search Gateway로 포지셔닝한다.
2. 초기 사용자는 AI 에이전트 개발자로 잡는다.
3. 수익성이 높은 후속 시장은 물류, 글로벌 SaaS, 여행 및 기업 AI다.
4. 상용 지도 데이터는 무단 수집하지 않고 공식 API로 실시간 중개한다.
5. OSM, 고객 데이터 및 허가된 공공데이터는 자체 저장한다.
6. Google Places 등 상용 API는 초기에는 BYOK 방식으로 제공한다.
7. 사용자가 키를 등록하지 않아도 OSM 기반으로 작동해야 한다.
8. Google 비용을 운영자가 대신 부담하는 모델은 사용량과 과금 체계를 검증한 뒤 추가한다.
9. 초기 MVP는 Google Places, Nominatim, 고객 CSV/PostgreSQL 세 가지로 충분하다.
10. 장기 차별화 요소는 비용 기반 라우팅, 중복 제거, 공급자 검증, 국가별 최적화, 정책 관리 및 엔터프라이즈 보안이다.
