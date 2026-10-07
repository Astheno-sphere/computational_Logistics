import { createHash } from "node:crypto";
import { PLACE_ID_PREFIX } from "@geowirehq/schema";

/** 해시에서 취할 base64url 문자 수 (충돌 여유 충분, ID 길이 절제) */
const HASH_LENGTH = 20;

/**
 * `provider:providerPlaceId`를 안정적인 내부 ID(`gwp_...`)로 변환한다.
 * 같은 입력은 항상 같은 ID를 낸다 — 병합 후에도, 재요청에도 유지된다(설계 §5 "안정적").
 * base64url 출력은 `Place.id` 정규식(`^gwp_[A-Za-z0-9_-]+$`)을 만족한다.
 */
export function makePlaceId(provider: string, providerPlaceId: string): string {
  const digest = createHash("sha256")
    .update(`${provider}:${providerPlaceId}`)
    .digest("base64url")
    .slice(0, HASH_LENGTH);
  return `${PLACE_ID_PREFIX}${digest}`;
}

/** `provider:providerPlaceId` 참조 문자열. get_place가 내부 ID 대신 받을 수 있는 형태 */
export interface ProviderRef {
  provider: string;
  providerPlaceId: string;
}

/**
 * get_place 입력을 해석한다. `gwp_...`이면 내부 ID(역해시 불가 → ref 없음),
 * `provider:id`이면 ProviderRef로 분해한다.
 */
export function parsePlaceRef(
  id: string,
): { kind: "internal"; id: string } | { kind: "ref"; ref: ProviderRef } {
  if (id.startsWith(PLACE_ID_PREFIX)) return { kind: "internal", id };
  const idx = id.indexOf(":");
  if (idx > 0) {
    return {
      kind: "ref",
      ref: { provider: id.slice(0, idx), providerPlaceId: id.slice(idx + 1) },
    };
  }
  // 접두사도 콜론도 없으면 내부 ID로 취급 (관대한 해석)
  return { kind: "internal", id };
}
