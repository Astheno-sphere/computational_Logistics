import type { GeoWireConfig } from "./schema.js";

export interface ConfigWarning {
  code: "PLAINTEXT_SECRET" | "UNKNOWN_PROVIDER" | "EMPTY_PROVIDERS";
  provider?: string;
  message: string;
}

/** 값이 평문 비밀처럼 보이는지 — `${ENV}` 참조가 아니고 충분히 긴 영숫자/키 형태 */
function looksLikePlaintextSecret(value: unknown): boolean {
  if (typeof value !== "string") return false;
  if (value.includes("${")) return false; // 아직 치환되지 않은 참조는 경고 대상 아님
  // 대표적 키 패턴: 20자 이상, 공백 없음, 접두사(AIza, sk-, pk. 등) 또는 고엔트로피
  if (/\s/.test(value)) return false;
  if (/^(AIza|sk-|pk\.|Bearer\s)/.test(value)) return true;
  return value.length >= 20 && /^[A-Za-z0-9._-]+$/.test(value);
}

const SECRET_KEYS = new Set(["apikey", "apiKey", "token", "secret", "password"]);

/**
 * 설정에서 흔한 실수를 감지해 경고 목록을 만든다 (설계 §8.1 평문 키 감지).
 * 반환만 하고 던지지 않는다 — 호출자(CLI/server)가 logger로 출력한다.
 *
 * @param knownProviderIds registry에 실제 등록된 provider id 집합 (오타 감지용)
 */
export function collectConfigWarnings(
  config: GeoWireConfig,
  knownProviderIds?: ReadonlySet<string>,
): ConfigWarning[] {
  const warnings: ConfigWarning[] = [];
  const providerEntries = Object.entries(config.providers);

  // config에 활성 항목이 없고 registry에도 등록된 provider가 없을 때만 경고.
  // (zero-config: config.providers가 비어도 nominatim 인스턴스가 주입되면 정상)
  const enabledCount = providerEntries.filter(([, c]) => c.enabled).length;
  const registeredCount = knownProviderIds?.size ?? 0;
  if (enabledCount === 0 && registeredCount === 0) {
    warnings.push({
      code: "EMPTY_PROVIDERS",
      message:
        "활성화된 공급자가 없습니다. 최소 하나의 provider 인스턴스를 등록하세요(zero-config는 nominatim).",
    });
  }

  for (const [id, providerConfig] of providerEntries) {
    if (knownProviderIds && providerConfig.enabled && !knownProviderIds.has(id)) {
      warnings.push({
        code: "UNKNOWN_PROVIDER",
        provider: id,
        message: `설정의 공급자 '${id}'에 해당하는 등록된 provider 인스턴스가 없습니다(오타?).`,
      });
    }
    for (const [key, value] of Object.entries(providerConfig)) {
      if (SECRET_KEYS.has(key) && looksLikePlaintextSecret(value)) {
        warnings.push({
          code: "PLAINTEXT_SECRET",
          provider: id,
          message: `공급자 '${id}'의 '${key}'가 평문으로 보입니다. \${ENV_VAR} 참조 사용을 권장합니다.`,
        });
      }
    }
  }
  return warnings;
}
