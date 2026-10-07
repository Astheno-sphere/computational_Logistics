import type { Place } from "@geowirehq/schema";
import { haversineMeters } from "../../geo.js";

/** 라틴 법인 접미사 — 단어 경계(\b) 기준으로 제거 ("co"가 "company"를 오탐하지 않도록) */
const LATIN_SUFFIXES = [
  "inc",
  "incorporated",
  "llc",
  "ltd",
  "limited",
  "co",
  "corp",
  "corporation",
  "company",
  "gmbh",
  "srl",
  "sarl",
  "sa",
  "bv",
  "plc",
  "pte",
];

/** CJK 법인 접미사 — 단어 경계가 없으므로(\b는 ASCII 전용) 직접 매칭해 제거 */
const CJK_SUFFIXES = ["주식회사", "유한회사", "有限公司", "有限会社", "株式会社"];

const LATIN_SUFFIX_RE = new RegExp(`\\b(${LATIN_SUFFIXES.join("|")})\\b\\.?`, "giu");
const CJK_SUFFIX_RE = new RegExp(`(${CJK_SUFFIXES.join("|")})`, "gu");

/**
 * 이름을 비교용으로 정규화한다 (설계 §7.3):
 * 유니코드 NFKC → 소문자 → 법인 접미사 제거(라틴·CJK) → 구두점 제거 → 공백 정리.
 */
export function normalizeName(name: string): string {
  return name
    .normalize("NFKC")
    .toLowerCase()
    .replace(LATIN_SUFFIX_RE, " ")
    .replace(CJK_SUFFIX_RE, " ")
    .replace(/[.,''"“”·・\-_/()]+/gu, " ")
    .replace(/\s+/gu, " ")
    .trim();
}

/** Jaro 유사도 (0~1) */
function jaro(a: string, b: string): number {
  if (a === b) return 1;
  if (a.length === 0 || b.length === 0) return 0;
  const matchWindow = Math.max(0, Math.floor(Math.max(a.length, b.length) / 2) - 1);
  const aMatched = new Array<boolean>(a.length).fill(false);
  const bMatched = new Array<boolean>(b.length).fill(false);

  let matches = 0;
  for (let i = 0; i < a.length; i++) {
    const start = Math.max(0, i - matchWindow);
    const end = Math.min(i + matchWindow + 1, b.length);
    for (let j = start; j < end; j++) {
      if (bMatched[j] || a[i] !== b[j]) continue;
      aMatched[i] = true;
      bMatched[j] = true;
      matches++;
      break;
    }
  }
  if (matches === 0) return 0;

  let transpositions = 0;
  let k = 0;
  for (let i = 0; i < a.length; i++) {
    if (!aMatched[i]) continue;
    while (!bMatched[k]) k++;
    if (a[i] !== b[k]) transpositions++;
    k++;
  }
  transpositions /= 2;

  return (matches / a.length + matches / b.length + (matches - transpositions) / matches) / 3;
}

/** Jaro-Winkler 유사도 (0~1). 공통 접두사에 가중(최대 4자, p=0.1) */
export function jaroWinkler(a: string, b: string): number {
  const j = jaro(a, b);
  if (j === 0) return 0;
  let prefix = 0;
  const maxPrefix = Math.min(4, a.length, b.length);
  while (prefix < maxPrefix && a[prefix] === b[prefix]) prefix++;
  return j + prefix * 0.1 * (1 - j);
}

/**
 * 전화번호를 비교용 NSN(national significant number) 근사치로 정규화한다.
 * 숫자만 남긴 뒤 **국제 접두 `00`** 또는 **국내 트렁크 프리픽스 `0`** 한 자리를 벗긴다.
 * 이렇게 하면 국제표기 `+82 2 1234 5678`(→`82212345678`)의 뒷자리가 국내표기
 * `02-1234-5678`(→`0` 제거 `212345678`)와 endsWith로 일치한다(국가코드 테이블 불필요).
 */
export function phoneNsn(phone: string): string {
  let d = phone.replace(/\D/gu, "");
  if (d.startsWith("00")) d = d.slice(2); // 국제전화 접두 00
  else if (d.startsWith("0")) d = d.slice(1); // 국내 트렁크 프리픽스 0
  return d;
}

/** URL에서 호스트명(www. 제거) 추출. 실패 시 원문 소문자 */
function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./u, "").toLowerCase();
  } catch {
    return url.toLowerCase();
  }
}

/** 좌표 거리 → 근접 신호(0~1): 25m 이내 1, 500m 이상 0, 사이는 선형 */
function distanceSignal(a: Place, b: Place): number {
  const d = haversineMeters(a.location, b.location);
  if (d <= 25) return 1;
  if (d >= 500) return 0;
  return 1 - (d - 25) / 475;
}

/** 쌍별 점수 가중치 (설계 §7.3): 좌표 35 / 이름 30 / 주소 20 / 전화 10 / 웹 5 */
export const PAIR_WEIGHTS = {
  location: 35,
  name: 30,
  address: 20,
  phone: 10,
  website: 5,
} as const;

/**
 * 두 Place가 동일 장소일 가능성 점수(0~1).
 * 각 신호에 가중치를 곱하고, **비교 가능한(양쪽에 값이 있는) 신호의 가중치로만 정규화**한다
 * — 주소·전화·웹이 없다고 점수가 부당하게 낮아지지 않도록.
 * 좌표·이름은 항상 존재하므로 최소 신호는 보장된다.
 */
/** 전화번호 일치(양쪽 존재 + NSN 뒤 7자리 이상 일치). 국가코드/선행 0 표기차를 흡수 */
function phoneMatches(a: Place, b: Place): boolean {
  if (!a.contact?.phone || !b.contact?.phone) return false;
  const pa = phoneNsn(a.contact.phone);
  const pb = phoneNsn(b.contact.phone);
  return pa.length >= 7 && pb.length >= 7 && (pa.endsWith(pb) || pb.endsWith(pa));
}

/** 웹사이트 호스트 일치(양쪽 존재) */
function websiteMatches(a: Place, b: Place): boolean {
  if (!a.contact?.website || !b.contact?.website) return false;
  return hostname(a.contact.website) === hostname(b.contact.website);
}

export function pairScore(a: Place, b: Place): number {
  const distance = distanceSignal(a, b);
  const phoneMatch = phoneMatches(a, b);
  const websiteMatch = websiteMatches(a, b);

  // 언어/문자가 다른 상호(예: "Starbucks" vs "스타벅스")는 이름 유사도가 0이라
  // 이름 가중치(30)가 항상 분모에 남아 최대 0.70 → 기본 임계값(0.75)을 못 넘어 병합 불가.
  // 전화/웹은 문자 체계와 무관한 강한 식별자이므로, **근접(≤~262m) + 전화/웹 정확 일치**면
  // 이름 언어와 무관하게 동일 장소로 확정한다. (근접 조건은 프랜차이즈 공용번호 오병합 방지)
  if (distance >= 0.5 && (phoneMatch || websiteMatch)) return 1;

  let weightedSum = 0;
  let activeWeight = 0;

  const add = (weight: number, signal: number): void => {
    weightedSum += weight * signal;
    activeWeight += weight;
  };

  add(PAIR_WEIGHTS.location, distance);
  add(PAIR_WEIGHTS.name, jaroWinkler(normalizeName(a.name), normalizeName(b.name)));

  if (a.address?.formatted && b.address?.formatted) {
    add(
      PAIR_WEIGHTS.address,
      jaroWinkler(a.address.formatted.toLowerCase(), b.address.formatted.toLowerCase()),
    );
  }
  if (a.contact?.phone && b.contact?.phone) {
    add(PAIR_WEIGHTS.phone, phoneMatch ? 1 : 0);
  }
  if (a.contact?.website && b.contact?.website) {
    add(PAIR_WEIGHTS.website, websiteMatch ? 1 : 0);
  }

  return activeWeight === 0 ? 0 : weightedSum / activeWeight;
}
