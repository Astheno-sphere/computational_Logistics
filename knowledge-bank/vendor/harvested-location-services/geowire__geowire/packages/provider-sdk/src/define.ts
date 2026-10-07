import { ProviderManifest } from "@geowirehq/schema";
import { CAPABILITY_METHOD, type GeoProvider } from "./provider.js";

/**
 * 공급자를 정의하며 두 가지를 **생성 시점에** 검증한다:
 *  1. `manifest`가 `provider-manifest/v1` 스키마에 유효한가
 *  2. `manifest.capabilities`에 선언한 모든 capability의 구현 메서드가 실제로 존재하는가
 *     (예: capabilities에 "search"가 있는데 `searchPlaces`가 없으면 즉시 throw)
 *
 * 잘못된 공급자가 런타임 검색 도중이 아니라 로딩 시점에 실패하도록 만드는 것이 목적이다.
 * 반환값은 입력 그대로(검증 통과한 GeoProvider)라 `export default defineProvider({...})` 패턴에 쓴다.
 */
export function defineProvider(provider: GeoProvider): GeoProvider {
  const parsed = ProviderManifest.safeParse(provider.manifest);
  if (!parsed.success) {
    throw new Error(
      `Invalid provider manifest: ${formatIssues(parsed.error.issues)}`,
    );
  }

  const missing = parsed.data.capabilities.filter((cap) => {
    const method = CAPABILITY_METHOD[cap];
    return typeof provider[method] !== "function";
  });
  if (missing.length > 0) {
    const details = missing
      .map((cap) => `"${cap}" → ${String(CAPABILITY_METHOD[cap])}()`)
      .join(", ");
    throw new Error(
      `Provider "${parsed.data.id}" declares capabilities it does not implement: ${details}`,
    );
  }

  return provider;
}

function formatIssues(issues: { path: PropertyKey[]; message: string }[]): string {
  return issues
    .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join("; ");
}
