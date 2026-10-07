import { createGeoWire, loadConfig, type GeoWire } from "@geowirehq/core";
import type { GeoProvider, Logger } from "@geowirehq/provider-sdk";
import { createNominatimProvider } from "@geowirehq/provider-nominatim";
import { createGoogleProvider } from "@geowirehq/provider-google";
import { createInternalProvider } from "@geowirehq/provider-internal";
import { createKakaoProvider } from "@geowirehq/provider-kakao";
import { createNaverProvider } from "@geowirehq/provider-naver";
import { createBaiduProvider } from "@geowirehq/provider-baidu";
import { createFoursquareProvider } from "@geowirehq/provider-foursquare";
import { createOsrmProvider } from "@geowirehq/provider-osrm";
import { createCensusProvider } from "@geowirehq/provider-census";
import { createYelpProvider } from "@geowirehq/provider-yelp";

/**
 * 환경 변수로 GeoWire 인스턴스를 구성한다 (설계 §8.1 Zero-config + BYOK).
 * - nominatim: 항상 활성(키 불필요) — 검색·지오코딩
 * - osrm: 항상 활성(키 불필요) — 길찾기·거리행렬. `OSRM_BASE_URL`로 self-host 지정 가능
 * - google: `GOOGLE_MAPS_API_KEY` 있으면 추가
 * - kakao: `KAKAO_REST_API_KEY` 있으면 추가 (한국)
 * - naver: `NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET` 있으면 추가 (한국)
 * - baidu: `BAIDU_MAP_AK` 있으면 추가 (중국)
 * - foursquare: `FOURSQUARE_API_KEY` 있으면 추가 (글로벌 POI)
 * - yelp: `YELP_API_KEY` 있으면 추가 (미국·서구권 비즈니스·리뷰·평점)
 * - census: `CENSUS_API_KEY`(무료) 있으면 추가 (미국 인구통계)
 * - internal: `GEOWIRE_INTERNAL_CSV`(파일 경로) 있으면 추가
 * - config: `GEOWIRE_CONFIG`(YAML 경로) 있으면 로드, 없으면 zero-config 기본값
 */
export function createGeoFromEnv(logger?: Logger): GeoWire {
  // nominatim(검색)·osrm(길찾기) 둘 다 무키 기본. OSRM_BASE_URL로 self-host 오버라이드.
  const providers: GeoProvider[] = [
    createNominatimProvider(),
    createOsrmProvider({ baseUrl: process.env.OSRM_BASE_URL }),
  ];

  const googleKey = process.env.GOOGLE_MAPS_API_KEY;
  if (googleKey) providers.push(createGoogleProvider({ apiKey: googleKey }));

  const kakaoKey = process.env.KAKAO_REST_API_KEY;
  if (kakaoKey) providers.push(createKakaoProvider({ apiKey: kakaoKey }));

  const naverId = process.env.NAVER_CLIENT_ID;
  const naverSecret = process.env.NAVER_CLIENT_SECRET;
  if (naverId && naverSecret)
    providers.push(createNaverProvider({ clientId: naverId, clientSecret: naverSecret }));

  const baiduKey = process.env.BAIDU_MAP_AK;
  if (baiduKey) providers.push(createBaiduProvider({ apiKey: baiduKey }));

  const fsqKey = process.env.FOURSQUARE_API_KEY;
  if (fsqKey) providers.push(createFoursquareProvider({ apiKey: fsqKey }));

  const yelpKey = process.env.YELP_API_KEY;
  if (yelpKey) providers.push(createYelpProvider({ apiKey: yelpKey }));

  const censusKey = process.env.CENSUS_API_KEY;
  if (censusKey) providers.push(createCensusProvider({ apiKey: censusKey }));

  const internalCsv = process.env.GEOWIRE_INTERNAL_CSV;
  if (internalCsv) providers.push(createInternalProvider({ source: internalCsv }));

  const config = loadConfig(process.env.GEOWIRE_CONFIG);
  return createGeoWire({ providers, config, logger });
}
