import { describe, it, expect } from "vitest";
import { ProviderManifest, type Capability } from "@geowirehq/schema";
import type { ProviderErrorCode } from "@geowirehq/schema";
import {
  GeoProviderError,
  ProviderPlace,
  CAPABILITY_METHOD,
  type GeoProvider,
  type ProviderContext,
} from "@geowirehq/provider-sdk";
import { jsonFetch, statusFetch, hangingFetch, createTestContext } from "./mock-server.js";

/** capability 하나에 대한 성공 시나리오 픽스처 */
export interface CapabilityFixture {
  /** 공급자 메서드에 넘길 요청 */
  request: unknown;
  /** HTTP 공급자의 fetch가 받을 mock 응답 바디 */
  responseBody?: unknown;
  responseInit?: ResponseInit;
  /** 최소 기대 결과 수 (기본 1) */
  minResults?: number;
}

export interface ConformanceOptions {
  /** capability별 성공 픽스처 */
  fixtures?: Partial<Record<Capability, CapabilityFixture>>;
  /** HTTP를 쓰지 않는 공급자(CSV 등)면 false — HTTP 오류/타임아웃 체크를 건너뛴다 */
  usesHttp?: boolean;
  /** 성공 시나리오의 attempt 타임아웃(ms). 기본 1000 */
  timeoutMs?: number;
}

export interface ConformanceCheck {
  name: string;
  passed: boolean;
  /** 실패 시 사람이 읽는 사유 (기여자가 스스로 고칠 수 있는 수준) */
  detail?: string;
}

type ProviderMethod = (req: unknown, ctx: ProviderContext) => Promise<unknown>;

function getMethod(provider: GeoProvider, cap: Capability): ProviderMethod | undefined {
  const fn = (provider as unknown as Record<string, unknown>)[CAPABILITY_METHOD[cap]];
  return typeof fn === "function" ? (fn as ProviderMethod).bind(provider) : undefined;
}

function formatIssues(issues: readonly { path: PropertyKey[]; message: string }[]): string {
  return issues
    .map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join("; ");
}

/**
 * 공급자를 6개 축으로 검증하고 구조화된 결과를 돌려준다 (vitest 비의존, 순수 함수).
 *  1. manifest 스키마 유효성
 *  2. 선언 capability ↔ 메서드 구현 일치
 *  3. 픽스처 응답 → 반환 ProviderPlace가 스키마 유효 + 최소 개수
 *  4. HTTP 오류(500/401) → 정규화된 GeoProviderError
 *  5. 타임아웃 → GeoProviderError(TIMEOUT)
 *  6. attributionRequired 선언 시 비어있지 않은 문자열
 */
export async function runConformanceChecks(
  provider: GeoProvider,
  options: ConformanceOptions = {},
): Promise<ConformanceCheck[]> {
  const checks: ConformanceCheck[] = [];
  const usesHttp = options.usesHttp ?? true;
  const timeoutMs = options.timeoutMs ?? 1000;
  const fixtures = options.fixtures ?? {};

  // 1. manifest 유효성
  const manifest = ProviderManifest.safeParse(provider.manifest);
  checks.push({
    name: "manifest is schema-valid",
    passed: manifest.success,
    detail: manifest.success ? undefined : formatIssues(manifest.error.issues),
  });

  // 2. capability ↔ 메서드
  const caps: Capability[] = manifest.success
    ? manifest.data.capabilities
    : (provider.manifest.capabilities ?? []);
  const missing = caps.filter((cap) => getMethod(provider, cap) === undefined);
  checks.push({
    name: "declared capabilities are implemented",
    passed: missing.length === 0,
    detail: missing.length ? `missing methods for: ${missing.join(", ")}` : undefined,
  });

  // 3. 픽스처 → 유효한 ProviderPlace
  for (const cap of Object.keys(fixtures) as Capability[]) {
    const fx = fixtures[cap];
    if (!fx) continue;
    const name = `fixture:${cap} returns valid ProviderPlace(s)`;
    const method = getMethod(provider, cap);
    if (!method) {
      checks.push({ name, passed: false, detail: "method not implemented" });
      continue;
    }
    try {
      const ctx = createTestContext(jsonFetch(fx.responseBody ?? {}, fx.responseInit), {
        timeoutMs,
      });
      const out = await method(fx.request, ctx);
      const list = Array.isArray(out) ? out : out == null ? [] : [out];
      const min = fx.minResults ?? 1;
      let passed = list.length >= min;
      let detail = passed ? undefined : `expected >= ${min} result(s), got ${list.length}`;
      if (passed) {
        for (const place of list) {
          const parsed = ProviderPlace.safeParse(place);
          if (!parsed.success) {
            passed = false;
            detail = `invalid ProviderPlace: ${formatIssues(parsed.error.issues)}`;
            break;
          }
        }
      }
      checks.push({ name, passed, detail });
    } catch (err) {
      checks.push({ name, passed: false, detail: `threw: ${describeError(err)}` });
    }
  }

  // 4·5. HTTP 오류/타임아웃 정규화 (HTTP 공급자 + 픽스처가 하나 이상 있을 때)
  const firstCap = (Object.keys(fixtures) as Capability[])[0];
  const firstFx = firstCap ? fixtures[firstCap] : undefined;
  if (usesHttp && firstCap && firstFx) {
    const method = getMethod(provider, firstCap);
    if (method) {
      checks.push(
        await expectGeoError("HTTP 500 → GeoProviderError", () =>
          method(firstFx.request, createTestContext(statusFetch(500), { timeoutMs, retries: 0 })),
        ),
      );
      checks.push(
        await expectGeoError(
          "HTTP 401 → GeoProviderError(AUTH_FAILED)",
          () =>
            method(
              firstFx.request,
              createTestContext(statusFetch(401), { timeoutMs, retries: 0 }),
            ),
          "AUTH_FAILED",
        ),
      );
      checks.push(
        await expectGeoError(
          "timeout → GeoProviderError(TIMEOUT)",
          () =>
            method(
              firstFx.request,
              createTestContext(hangingFetch(), { timeoutMs: 20, retries: 0 }),
            ),
          "TIMEOUT",
        ),
      );
    }
  }

  // 6. attribution
  const attribution = provider.manifest.policy?.attributionRequired;
  if (attribution !== undefined) {
    checks.push({
      name: "attributionRequired is a non-empty string when declared",
      passed: typeof attribution === "string" && attribution.trim().length > 0,
      detail:
        typeof attribution === "string" && attribution.trim().length > 0
          ? undefined
          : "attributionRequired declared but empty",
    });
  }

  return checks;
}

async function expectGeoError(
  name: string,
  fn: () => Promise<unknown>,
  expectedCode?: ProviderErrorCode,
): Promise<ConformanceCheck> {
  try {
    await fn();
    return { name, passed: false, detail: "expected GeoProviderError, but the call resolved" };
  } catch (err) {
    if (!(err instanceof GeoProviderError)) {
      return { name, passed: false, detail: `threw ${describeError(err)}, not GeoProviderError` };
    }
    if (expectedCode && err.code !== expectedCode) {
      return { name, passed: false, detail: `expected code ${expectedCode}, got ${err.code}` };
    }
    return { name, passed: true };
  }
}

function describeError(err: unknown): string {
  if (err instanceof Error) return `${err.name}: ${err.message}`;
  return String(err);
}

/**
 * vitest 바인딩 — 공급자 패키지의 테스트 파일에서 호출한다.
 * `runConformanceTests(myProvider, { fixtures: {...} })` 한 줄이면 전 항목이 테스트로 등록된다.
 * 실패 시 각 체크의 이름과 사유를 열거한 메시지를 출력한다.
 */
export function runConformanceTests(
  provider: GeoProvider,
  options: ConformanceOptions = {},
): void {
  describe(`conformance: ${provider.manifest?.id ?? "unknown"}`, () => {
    it("passes all provider conformance checks", async () => {
      const results = await runConformanceChecks(provider, options);
      const failures = results.filter((r) => !r.passed);
      const message = failures.map((f) => `  ✗ ${f.name}: ${f.detail ?? ""}`).join("\n");
      expect(failures, `\n${message}`).toHaveLength(0);
    });
  });
}
