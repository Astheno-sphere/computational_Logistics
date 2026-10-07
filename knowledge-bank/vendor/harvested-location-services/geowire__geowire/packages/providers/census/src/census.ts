import {
  defineProvider,
  errorFromHttpStatus,
  GeoProviderError,
  type GeoProvider,
  type ProviderContext,
  type ProviderDemographics,
} from "@geowirehq/provider-sdk";
import type { DemographicsRequest } from "@geowirehq/schema";
import { CENSUS_MANIFEST } from "./manifest.js";

const DEFAULT_GEOCODER_BASE = "https://geocoding.geo.census.gov";
const DEFAULT_ACS_BASE = "https://api.census.gov";
const DEFAULT_YEAR = 2022; // 최신 ACS 5년 추정치(안정). 옵션으로 변경 가능

/** ACS 변수 코드 → 의미 (FieldMask 대신 명시) */
const VARS = {
  population: "B01003_001E",
  medianAge: "B01002_001E",
  medianIncome: "B19013_001E",
  households: "B11001_001E",
  avgHouseholdSize: "B25010_001E",
} as const;

export interface CensusOptions {
  /** Census API 키(무료). 없으면 demographics가 MISSING_CREDENTIALS (BYOK) */
  apiKey?: string;
  /** ACS 연도(5년 추정치). 기본 2022 */
  year?: number;
  geocoderBaseUrl?: string;
  acsBaseUrl?: string;
}

interface Tract {
  STATE?: string;
  COUNTY?: string;
  TRACT?: string;
  NAME?: string;
  BASENAME?: string;
  AREALAND?: number; // 육지 면적(제곱미터)
}

/** ACS의 결측 센티넬(대형 음수 등)을 걸러 숫자만 반환 */
function num(v: string | undefined): number | undefined {
  if (v == null) return undefined;
  const n = Number(v);
  if (!Number.isFinite(n) || n <= -666666666 || n < 0) return undefined;
  return n;
}

/**
 * US Census 공급자 — 좌표가 속한 census tract의 인구통계(ACS 5년).
 * 1) Census Geocoder(무키)로 좌표 → tract 지리코드
 * 2) ACS API(키)로 인구·중위연령·중위소득·가구·평균가구원 조회
 * 미국 밖이면 tract가 없어 null을 반환한다.
 */
export function createCensusProvider(options: CensusOptions = {}): GeoProvider {
  const geocoderBase = (options.geocoderBaseUrl ?? DEFAULT_GEOCODER_BASE).replace(/\/+$/, "");
  const acsBase = (options.acsBaseUrl ?? DEFAULT_ACS_BASE).replace(/\/+$/, "");
  const year = options.year ?? DEFAULT_YEAR;

  function requireKey(): string {
    if (!options.apiKey) {
      throw new GeoProviderError("MISSING_CREDENTIALS", "Census API 키가 설정되지 않았습니다(무료 발급)", {
        provider: "census",
      });
    }
    return options.apiKey;
  }

  async function getJson(url: string, ctx: ProviderContext): Promise<unknown> {
    const res = await ctx.fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "census" });
    return res.json();
  }

  return defineProvider({
    manifest: CENSUS_MANIFEST,

    async demographics(req: DemographicsRequest, ctx): Promise<ProviderDemographics | null> {
      const apiKey = requireKey();
      const { latitude, longitude } = req.location;

      // 1) 좌표 → census tract (Geocoder, 무키)
      const geoUrl =
        `${geocoderBase}/geocoder/geographies/coordinates` +
        `?x=${longitude}&y=${latitude}&benchmark=Public_AR_Current&vintage=Current_Current&format=json`;
      const geo = (await getJson(geoUrl, ctx)) as {
        result?: { geographies?: { "Census Tracts"?: Tract[] } };
      };
      const tract = geo.result?.geographies?.["Census Tracts"]?.[0];
      if (!tract?.STATE || !tract.COUNTY || !tract.TRACT) return null; // 미국 밖

      // 2) tract → ACS 인구통계 (키 필요)
      const get = Object.values(VARS).join(",");
      const acsUrl =
        `${acsBase}/data/${year}/acs/acs5?get=NAME,${get}` +
        `&for=tract:${tract.TRACT}&in=state:${tract.STATE}&in=county:${tract.COUNTY}&key=${apiKey}`;
      const acs = (await getJson(acsUrl, ctx)) as string[][];
      if (!Array.isArray(acs) || acs.length < 2) return null;
      const header = acs[0]!;
      const row = acs[1]!;
      const val = (code: string): string | undefined => {
        const i = header.indexOf(code);
        return i >= 0 ? row[i] : undefined;
      };

      const profile: ProviderDemographics = {
        areaName: (val("NAME") ?? tract.NAME ?? "Census Tract").replace(/;\s*/g, ", "),
        areaLevel: "tract",
        source: "census",
      };
      const pop = num(val(VARS.population));
      if (pop != null) profile.population = Math.round(pop);
      const age = num(val(VARS.medianAge));
      if (age != null) profile.medianAgeYears = age;
      const income = num(val(VARS.medianIncome));
      if (income != null) profile.medianHouseholdIncome = { amount: income, currency: "USD" };
      const hh = num(val(VARS.households));
      if (hh != null) profile.households = Math.round(hh);
      const size = num(val(VARS.avgHouseholdSize));
      if (size != null) profile.avgHouseholdSize = size;
      // 인구밀도: AREALAND(m²) → km²
      if (pop != null && typeof tract.AREALAND === "number" && tract.AREALAND > 0) {
        profile.populationDensityPerSqKm = Math.round((pop / (tract.AREALAND / 1_000_000)) * 10) / 10;
      }
      return profile;
    },
  });
}
