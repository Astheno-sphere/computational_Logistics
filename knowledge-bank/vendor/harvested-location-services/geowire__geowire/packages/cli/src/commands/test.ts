import type { GeoWire } from "@geowirehq/core";
import type { IO } from "../io.js";

/**
 * 등록된 공급자 연결 검사 (설계 §9 `geowire test`).
 * 각 활성 공급자를 개별 호출해 도달성/자격증명을 확인한다.
 * 반환값은 프로세스 종료 코드(모두 정상 0, 하나라도 문제 1).
 */
export async function runTest(geo: GeoWire, io: IO): Promise<number> {
  const providers = geo.listProviders().filter((p) => p.enabled);
  if (providers.length === 0) {
    io.err("등록된 활성 공급자가 없습니다.");
    return 1;
  }

  let ok = true;
  for (const info of providers) {
    try {
      const res = await geo.searchPlaces({
        query: "coffee",
        limit: 1,
        options: { providers: [info.id], strategy: "merge" },
      });
      if (res.meta.providersUsed.some((u) => u.provider === info.id)) {
        io.out(`✓ ${info.name} connected`);
      } else {
        const skipped = res.meta.providersSkipped.find((s) => s.provider === info.id);
        const failed = res.meta.providersFailed.find((s) => s.provider === info.id);
        const reason = skipped?.reason ?? failed?.reason ?? "no response";
        io.out(`✗ ${info.name}: ${reason}`);
        ok = false;
      }
    } catch (err) {
      io.out(`✗ ${info.name}: ${err instanceof Error ? err.message : String(err)}`);
      ok = false;
    }
  }
  return ok ? 0 : 1;
}
