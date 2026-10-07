import type { LatLng } from "@geowirehq/schema";

export interface ParsedArgs {
  /** 위치 인자 (플래그가 아닌 것) */
  _: string[];
  flags: Record<string, string | boolean>;
}

/** `--key value`·`--flag`·위치 인자를 파싱한다 (경량, 의존성 없음) */
export function parseFlags(argv: readonly string[]): ParsedArgs {
  const _: string[] = [];
  const flags: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]!;
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      _.push(arg);
    }
  }
  return { _, flags };
}

/** "lat,lon" → LatLng. 형식 오류면 undefined */
export function parseNear(value: string): LatLng | undefined {
  const parts = value.split(",").map((s) => Number(s.trim()));
  if (parts.length !== 2 || parts.some((n) => !Number.isFinite(n))) return undefined;
  return { latitude: parts[0]!, longitude: parts[1]! };
}

/** 플래그 값을 정수로 (없거나 비수치면 undefined) */
export function flagInt(value: string | boolean | undefined): number | undefined {
  if (typeof value !== "string") return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : undefined;
}
