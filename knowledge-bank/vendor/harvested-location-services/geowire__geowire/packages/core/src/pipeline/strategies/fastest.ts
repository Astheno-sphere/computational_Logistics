import type { RegisteredProvider } from "../../registry.js";
import type { ProviderInvocation } from "../types.js";

type Invoke = (rp: RegisteredProvider) => Promise<ProviderInvocation>;

/**
 * fastest 전략 (지연 최적화, 설계 §7.2):
 * 모든 대상 공급자를 **병렬 호출**하고, **결과를 가진 첫 응답(가장 빠른 non-empty 성공)**이
 * 오는 즉시 반환한다. 나머지 in-flight 호출은 기다리지 않고 버린다(그 결과는 무시).
 * 아무도 결과를 못 내면(전부 실패/빈 결과) 완료된 모든 시도를 반환한다.
 *
 * ⚠️ 비용: 유료 공급자도 이미 병렬 dispatch되므로 버려진 결과에도 과금될 수 있다.
 * 단 예산 게이트(applyBudget)가 execute 전에 초과 유료 공급자를 제외하므로 상한은 유지된다.
 * invoke는 절대 reject하지 않는다(에러도 ProviderInvocation으로 정규화).
 */
export async function fastest(
  providers: readonly RegisteredProvider[],
  invoke: Invoke,
): Promise<ProviderInvocation[]> {
  if (providers.length === 0) return [];
  const settled: ProviderInvocation[] = [];
  return new Promise<ProviderInvocation[]>((resolve) => {
    let done = false;
    let remaining = providers.length;
    for (const rp of providers) {
      void invoke(rp).then((inv) => {
        remaining -= 1;
        settled.push(inv);
        if (!done && inv.ok && inv.places.length > 0) {
          done = true;
          resolve([...settled]); // 결과를 가진 첫 응답 → 즉시 반환(나머지는 버림)
        } else if (remaining === 0 && !done) {
          resolve(settled); // 아무도 결과를 못 냄 → 모든 시도 반환
        }
      });
    }
  });
}
