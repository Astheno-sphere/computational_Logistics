#!/usr/bin/env node
import { createGeoWire, loadConfig } from "@geowirehq/core";
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
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createGeoWireMcpServer } from "./server.js";

/** MCP는 stdout을 프로토콜 전송에 쓰므로 로그는 반드시 stderr로만 낸다 */
const stderrLogger: Logger = {
  debug: () => {},
  info: (message, ...args) => console.error("[geowire:info]", message, ...args),
  warn: (message, ...args) => console.error("[geowire:warn]", message, ...args),
  error: (message, ...args) => console.error("[geowire:error]", message, ...args),
};

async function main(): Promise<void> {
  // Zero-config: nominatim(검색)·osrm(길찾기)은 키 없이 항상 활성. 나머지는 환경 변수로 opt-in.
  const providers: GeoProvider[] = [
    createNominatimProvider(),
    createOsrmProvider({ baseUrl: process.env.OSRM_BASE_URL }),
  ];

  const googleKey = process.env.GOOGLE_MAPS_API_KEY;
  if (googleKey) providers.push(createGoogleProvider({ apiKey: googleKey }));

  const internalCsv = process.env.GEOWIRE_INTERNAL_CSV;
  if (internalCsv) providers.push(createInternalProvider({ source: internalCsv }));

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

  const config = loadConfig(process.env.GEOWIRE_CONFIG);
  const geo = createGeoWire({ providers, config, logger: stderrLogger });

  const server = createGeoWireMcpServer(geo);
  await server.connect(new StdioServerTransport());
  stderrLogger.info(`geowire-mcp ready with ${providers.length} provider(s)`);
}

main().catch((err) => {
  console.error("[geowire:fatal]", err);
  process.exit(1);
});
