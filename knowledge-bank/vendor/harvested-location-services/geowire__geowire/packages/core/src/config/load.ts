import { readFileSync } from "node:fs";
import { parse as parseYaml } from "yaml";
import { GeoWireConfig, defaultConfig } from "./schema.js";

/** `${ENV_VAR}` 참조를 치환할 때 값이 없으면 어떻게 할지 */
export interface EnvSubstitution {
  /** 환경 변수 소스. 기본 process.env */
  env?: Record<string, string | undefined>;
  /** 참조된 변수가 없을 때 던질지. 기본 false(빈 문자열로 치환 → 자격증명 없음으로 이어짐) */
  strict?: boolean;
}

const ENV_REF = /\$\{([A-Z0-9_]+)\}/g;

/**
 * 원본 문자열(YAML 텍스트) 안의 `${VAR}`를 환경 변수로 치환한다.
 * **YAML 파싱 전에** 적용한다 — flow-map(`{ apiKey: ${VAR} }`) 안에서는 `${`가 유효한
 * plain scalar가 아니므로, 파싱 후 값 레벨 치환으로는 이런 설정을 읽을 수 없다(설계 §8.1).
 */
export function substituteEnvInString(source: string, opts: EnvSubstitution = {}): string {
  const env = opts.env ?? process.env;
  return source.replace(ENV_REF, (_match, name: string) => {
    const resolved = env[name];
    if (resolved == null) {
      if (opts.strict) throw new Error(`환경 변수 ${name}가 설정되지 않았습니다`);
      return "";
    }
    return resolved;
  });
}

/**
 * 문자열 값 안의 `${VAR}`를 환경 변수로 치환한다 (설계 §8.1 `apiKey: ${GOOGLE_MAPS_API_KEY}`).
 * 객체·배열을 재귀 순회한다 — 이미 파싱된 객체(JSON config 등)에 쓴다.
 * YAML 텍스트에는 `substituteEnvInString`을 쓴다(flow-map 호환).
 */
export function substituteEnv(value: unknown, opts: EnvSubstitution = {}): unknown {
  const env = opts.env ?? process.env;
  if (typeof value === "string") {
    return value.replace(ENV_REF, (_match, name: string) => {
      const resolved = env[name];
      if (resolved == null) {
        if (opts.strict) throw new Error(`환경 변수 ${name}가 설정되지 않았습니다`);
        return "";
      }
      return resolved;
    });
  }
  if (Array.isArray(value)) return value.map((v) => substituteEnv(v, opts));
  if (value != null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) out[k] = substituteEnv(v, opts);
    return out;
  }
  return value;
}

/**
 * YAML 문자열을 파싱하고 `${ENV}` 치환 후 GeoWireConfig로 검증한다.
 * 빈 문자열·`null` 문서도 zero-config 기본값으로 파싱된다.
 */
export function parseConfig(source: string, opts: EnvSubstitution = {}): GeoWireConfig {
  const substituted = substituteEnvInString(source, opts);
  const raw = parseYaml(substituted) ?? {};
  return GeoWireConfig.parse(raw);
}

/**
 * 설정 파일을 읽어 config를 만든다. 파일이 없으면 zero-config 기본값을 반환한다(P1).
 * `required: true`면 파일 부재를 에러로 던진다.
 */
export function loadConfig(
  path: string | undefined,
  opts: EnvSubstitution & { required?: boolean } = {},
): GeoWireConfig {
  if (!path) return defaultConfig();
  let source: string;
  try {
    source = readFileSync(path, "utf8");
  } catch (err) {
    if (opts.required) {
      throw new Error(`설정 파일을 읽을 수 없습니다: ${path}`, { cause: err });
    }
    return defaultConfig();
  }
  return parseConfig(source, opts);
}

/**
 * 이미 객체 형태인 인라인 config를 정규화한다 (createGeoWire에 객체를 직접 넘긴 경우).
 * `${ENV}` 치환은 적용하지 않는다 — 코드에서 넘긴 값은 이미 해석된 것으로 본다.
 */
export function normalizeConfig(config: unknown): GeoWireConfig {
  return GeoWireConfig.parse(config ?? {});
}
