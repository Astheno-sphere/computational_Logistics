import type { RegisteredProvider } from "../../registry.js";
import type { ProviderInvocation } from "../types.js";

type Invoke = (rp: RegisteredProvider) => Promise<ProviderInvocation>;

/**
 * merge 전략의 실행부 (설계 §7.2): 모든 대상 공급자를 **병렬 호출**한다.
 * 부분 실패를 허용하며(invoke가 절대 reject하지 않음), 결과 합치기·중복 제거는
 * 파이프라인 후단(dedup, §7.3 — M3)에서 수행한다.
 */
export async function mergeAll(
  providers: readonly RegisteredProvider[],
  invoke: Invoke,
): Promise<ProviderInvocation[]> {
  return Promise.all(providers.map((rp) => invoke(rp)));
}
