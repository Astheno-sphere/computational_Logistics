import type { RegisteredProvider } from "../../registry.js";
import type { ProviderInvocation } from "../types.js";

type Invoke = (rp: RegisteredProvider) => Promise<ProviderInvocation>;

/**
 * first-success 전략 (기본값, 설계 §7.2):
 * 우선순위 순서로 하나씩 호출하고, **결과를 하나라도 반환한 첫 공급자에서 정지**한다.
 * 실패나 빈 결과는 다음 공급자로 폴백한다. 시도한 호출만 반환한다(정지 이후는 호출하지 않음)
 * — meta.providersUsed/Failed는 실제 시도분만 반영한다.
 */
export async function firstSuccess(
  providers: readonly RegisteredProvider[],
  invoke: Invoke,
): Promise<ProviderInvocation[]> {
  const attempts: ProviderInvocation[] = [];
  for (const rp of providers) {
    const result = await invoke(rp);
    attempts.push(result);
    if (result.ok && result.places.length > 0) break;
  }
  return attempts;
}
