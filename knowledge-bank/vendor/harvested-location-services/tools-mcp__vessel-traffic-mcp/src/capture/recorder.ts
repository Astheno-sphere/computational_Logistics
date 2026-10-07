import type { SiteProfile } from './site-profile.js';

export interface NamedValue {
  name: string;
  value: string;
}

export interface RecordedExchange {
  method: string;
  url: string;
  startedAt: string;
  request: {
    headers: NamedValue[];
    cookies: { name: string; value: string }[];
    body?: string;
    mimeType?: string;
  };
  response: {
    status: number;
    statusText?: string;
    headers: NamedValue[];
    cookies: { name: string; value: string }[];
    body?: string;
    mimeType?: string;
  };
}

export type WorkflowStep =
  | { kind: 'goto'; url: string }
  | { kind: 'wait'; ms: number }
  | { kind: 'note'; description: string };

export interface RecorderOpenOptions {
  /**
   * Optional override for the system clock used to stamp recorded exchanges
   * that do not already carry a startedAt timestamp.
   */
  now?: () => string;
}

export interface RecorderSession {
  readonly driverName: 'mock' | 'playwright';
  runStep(step: WorkflowStep, index: number): Promise<RecordedExchange[]>;
  close(): Promise<void>;
}

export interface RecorderDriver {
  readonly name: 'mock' | 'playwright';
  open(profile: SiteProfile, options?: RecorderOpenOptions): Promise<RecorderSession>;
}

export interface MockScriptStep {
  step: WorkflowStep;
  exchanges: RecordedExchange[];
}

export interface MockScript {
  steps: MockScriptStep[];
}

/**
 * Deterministic recorder used by tests and `--driver mock`. The driver does
 * not open any browser; it simply replays a pre-built script of recorded
 * XHR/fetch exchanges, one batch per workflow step. Tests can use this to
 * exercise the full capture → HAR → sanitize → IR → replay pipeline without
 * touching the network or installing Playwright.
 */
export function createMockRecorderDriver(script: MockScript): RecorderDriver {
  const steps = [...script.steps];
  return {
    name: 'mock',
    async open(_profile, _options) {
      let index = 0;
      let closed = false;
      return {
        driverName: 'mock',
        async runStep(step, stepIndex) {
          if (closed) {
            throw new Error('mock recorder: session already closed');
          }
          if (stepIndex !== index) {
            throw new Error(
              `mock recorder: step index out of order (expected ${index}, got ${stepIndex})`,
            );
          }
          const scripted = steps[index];
          index += 1;
          if (!scripted) {
            return [];
          }
          if (
            scripted.step.kind !== step.kind ||
            (scripted.step.kind === 'goto' && step.kind === 'goto' && scripted.step.url !== step.url) ||
            (scripted.step.kind === 'note' && step.kind === 'note' && scripted.step.description !== step.description)
          ) {
            throw new Error(
              `mock recorder: scripted step ${index - 1} does not match workflow step ${describeStep(step)}`,
            );
          }
          return scripted.exchanges.map(cloneExchange);
        },
        async close() {
          closed = true;
        },
      };
    },
  };
}

function describeStep(step: WorkflowStep): string {
  switch (step.kind) {
    case 'goto':
      return `goto ${step.url}`;
    case 'wait':
      return `wait ${step.ms}ms`;
    case 'note':
      return `note ${step.description}`;
  }
}

function cloneExchange(exchange: RecordedExchange): RecordedExchange {
  return JSON.parse(JSON.stringify(exchange)) as RecordedExchange;
}

/**
 * Stub factory for a Playwright-backed recorder. Playwright is intentionally
 * not a package.json dependency — it must be installed by the operator
 * out-of-band before the live driver can run. This function performs a
 * dynamic import so `npm install` and `npm test` stay lightweight; tests
 * never exercise this path.
 */
export async function createPlaywrightRecorderDriver(): Promise<RecorderDriver> {
  // Playwright is intentionally NOT a package.json dependency to keep
  // `npm install` and `npm test` lightweight; the live driver is an
  // operator-only path. The dynamic specifier below uses a runtime-built
  // string so that TypeScript does not try to resolve the module at
  // compile time.
  const moduleName = ['play', 'wright'].join('');
  let chromium: { launch: (opts?: unknown) => Promise<unknown> } | undefined;
  try {
    const mod = (await import(moduleName)) as { chromium?: typeof chromium };
    chromium = mod.chromium;
  } catch (err) {
    throw new Error(
      `capture-workflow: playwright is not installed. Install it locally with "npm install --no-save playwright" before running --driver playwright. (${err instanceof Error ? err.message : String(err)})`,
    );
  }
  if (!chromium) {
    throw new Error('capture-workflow: imported playwright module exposes no chromium driver');
  }
  // The live Playwright driver is intentionally a stub in this build.
  // F5A.AC2 deliberately keeps the live runner an operator-only path that is
  // never exercised by autodev/CI; the actual page hooking implementation is
  // provided by an external operator script that drives this driver via the
  // exported RecorderDriver interface.
  throw new Error(
    'capture-workflow: live playwright driver requires an operator-provided implementation; only the mock driver is supported in this build.',
  );
}
