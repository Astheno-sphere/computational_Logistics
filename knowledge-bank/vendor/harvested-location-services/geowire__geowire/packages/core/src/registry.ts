import type { GeoProvider } from "@geowirehq/provider-sdk";
import type { Capability } from "@geowirehq/schema";
import { CAPABILITY_METHOD } from "@geowirehq/provider-sdk";
import type { GeoWireConfig, ProviderConfig } from "./config/schema.js";

/** 등록된 공급자 + 해석된 설정 (registry가 관리하는 단위) */
export interface RegisteredProvider {
  readonly id: string;
  readonly provider: GeoProvider;
  readonly enabled: boolean;
  /** 라우팅·랭킹 우선순위 (높을수록 우선). config.priority ?? 0 */
  readonly priority: number;
  readonly config: ProviderConfig;
}

/**
 * 주입된 provider 인스턴스들을 manifest.id로 등록·관리한다.
 * config에서 `enabled`·`priority`를 해석하지만 자격증명 유무는 판단하지 않는다 —
 * 자격증명은 provider 인스턴스에 캡슐화되어 있고, 없을 때의 skip은 실행 시점
 * `MISSING_CREDENTIALS`로 처리된다(설계 §7.1 Execute 단계).
 */
export class ProviderRegistry {
  private readonly byId = new Map<string, RegisteredProvider>();

  constructor(providers: readonly GeoProvider[], config: GeoWireConfig) {
    for (const provider of providers) {
      const id = provider.manifest.id;
      if (this.byId.has(id)) {
        throw new Error(`중복된 공급자 id '${id}' — 각 provider는 고유한 manifest.id를 가져야 합니다`);
      }
      // config에 명시 항목이 없으면 기본 활성(zero-config: nominatim은 설정 없이도 켜진다)
      const pc = config.providers[id];
      this.byId.set(id, {
        id,
        provider,
        enabled: pc?.enabled ?? true,
        priority: pc?.priority ?? 0,
        config: pc ?? { enabled: true },
      });
    }
  }

  get(id: string): RegisteredProvider | undefined {
    return this.byId.get(id);
  }

  has(id: string): boolean {
    return this.byId.has(id);
  }

  /** 등록된 모든 provider id 집합 (config 경고의 오타 감지용) */
  ids(): Set<string> {
    return new Set(this.byId.keys());
  }

  /** 등록된 전부 (비활성 포함) */
  all(): RegisteredProvider[] {
    return [...this.byId.values()];
  }

  /** 활성 provider만, priority 내림차순 → id 오름차순(안정 정렬) */
  active(): RegisteredProvider[] {
    return this.all()
      .filter((r) => r.enabled)
      .sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  }

  /** 주어진 capability를 manifest에 선언하고 해당 메서드를 실제 구현한 활성 provider */
  supporting(capability: Capability): RegisteredProvider[] {
    const method = CAPABILITY_METHOD[capability];
    return this.active().filter(
      (r) =>
        r.provider.manifest.capabilities.includes(capability) &&
        typeof r.provider[method] === "function",
    );
  }
}
