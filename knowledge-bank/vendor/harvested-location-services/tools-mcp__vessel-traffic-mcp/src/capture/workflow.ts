import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, resolve } from 'node:path';

import {
  fixtureToJson,
  importCapture,
  type CaptureFixture,
  type CaptureProvenance,
} from './import.js';
import {
  recordedExchangesToHar,
  writeHarBackup,
  defaultRawDir,
  type HarLog,
} from './har-writer.js';
import {
  buildTrafficIR,
  trafficIRToJson,
  type TrafficIR,
  type TrafficIROptions,
} from './traffic-ir.js';
import { compareTrafficIR, type ReplayValidationReport } from './replay-validator.js';
import {
  assertActionAllowed,
  assertOriginAllowed,
  detectSessionLoss,
  validateSiteProfile,
  SiteProfileError,
  type SiteProfile,
} from './site-profile.js';
import type {
  RecordedExchange,
  RecorderDriver,
  WorkflowStep,
} from './recorder.js';

export const CAPTURE_WORKFLOW_VERSION = 1;

export class WorkflowGateError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = 'WorkflowGateError';
  }
}

export class WorkflowAbortedError extends Error {
  constructor(public readonly reason: string) {
    super(reason);
    this.name = 'WorkflowAbortedError';
  }
}

export interface CaptureWorkflowOptions {
  profile: SiteProfile;
  driver: RecorderDriver;
  steps: WorkflowStep[];
  label: string;
  /** Workspace cwd. Used to compute default output paths. */
  cwd: string;
  /**
   * `true` when the operator has explicitly authorized this run via
   * `--i-am-authorized`. The mock driver does not require this; live
   * drivers do.
   */
  authorized: boolean;
  /** True when VESSEL_CAPTURE_LIVE=1. Live drivers require this. */
  liveEnvEnabled: boolean;
  /**
   * If true, the workflow re-runs the IR build against the just-written
   * fixture and compares it to the in-memory IR. Used to verify
   * deterministic round-tripping.
   */
  validateReplay?: boolean;
  /**
   * If true, the sanitized fixture is written without the `.private.json`
   * extension so the operator can promote it into the tracked fixture
   * directory. Default: false (always write `*.private.json` first).
   */
  promote?: boolean;
  irOptions?: TrafficIROptions;
  /** Override the system clock for deterministic tests. */
  now?: () => string;
  /** Optional override for the raw HAR directory. Must contain `captures/raw`. */
  rawDirAbsolute?: string;
  /** Optional override for the sanitized fixture/IR directory. */
  fixtureDirAbsolute?: string;
}

export interface CaptureWorkflowResult {
  fixture: CaptureFixture;
  fixturePath: string;
  irPath: string;
  ir: TrafficIR;
  harPath: string;
  har: HarLog;
  recordedExchangeCount: number;
  validation?: ReplayValidationReport;
  warnings: string[];
}

export function gateRunner(options: {
  driverName: 'mock' | 'playwright';
  liveEnvEnabled: boolean;
  authorized: boolean;
  termsReviewStatus: SiteProfile['termsReviewStatus'];
}): void {
  if (options.termsReviewStatus === 'blocked') {
    throw new WorkflowGateError(
      'site-blocked',
      'capture-workflow: site profile termsReviewStatus is "blocked"; refusing to capture',
    );
  }
  if (options.driverName === 'mock') {
    return;
  }
  if (!options.liveEnvEnabled) {
    throw new WorkflowGateError(
      'live-env-disabled',
      'capture-workflow: VESSEL_CAPTURE_LIVE=1 is required for live recorder drivers',
    );
  }
  if (!options.authorized) {
    throw new WorkflowGateError(
      'not-authorized',
      'capture-workflow: --i-am-authorized must be passed for live recorder drivers',
    );
  }
  if (options.termsReviewStatus !== 'allowed') {
    throw new WorkflowGateError(
      'terms-review-pending',
      `capture-workflow: site termsReviewStatus="${options.termsReviewStatus}" — review terms before live capture`,
    );
  }
}

export async function runCaptureWorkflow(options: CaptureWorkflowOptions): Promise<CaptureWorkflowResult> {
  const validationErrors = validateSiteProfile(options.profile);
  if (validationErrors.length > 0) {
    throw new SiteProfileError(
      `capture-workflow: site profile invalid: ${validationErrors
        .map((e) => `${e.code}: ${e.message}`)
        .join('; ')}`,
      validationErrors,
    );
  }

  gateRunner({
    driverName: options.driver.name,
    liveEnvEnabled: options.liveEnvEnabled,
    authorized: options.authorized,
    termsReviewStatus: options.profile.termsReviewStatus,
  });

  if (options.steps.length === 0) {
    throw new WorkflowGateError('no-steps', 'capture-workflow: at least one workflow step is required');
  }
  if (options.steps.length > options.profile.pacing.maxStepsPerRun) {
    throw new WorkflowGateError(
      'pacing',
      `capture-workflow: ${options.steps.length} steps exceeds pacing.maxStepsPerRun=${options.profile.pacing.maxStepsPerRun}`,
    );
  }
  for (const step of options.steps) {
    if (step.kind === 'goto') {
      assertOriginAllowed(options.profile, step.url);
      assertActionAllowed(options.profile, step.url);
    }
  }

  const safeLabel = sanitizeLabel(options.label);
  const cwd = options.cwd;
  if (!isAbsolute(cwd)) {
    throw new WorkflowGateError('cwd', `capture-workflow: cwd must be absolute, got "${cwd}"`);
  }

  const rawDir = options.rawDirAbsolute ?? defaultRawDir(cwd);
  const fixtureDir = options.fixtureDirAbsolute ?? resolve(cwd, 'fixtures', 'captures');
  const harPath = resolve(rawDir, `${safeLabel}.har`);
  const fixturePath = resolve(
    fixtureDir,
    options.promote ? `${safeLabel}.fixture.json` : `${safeLabel}.private.json`,
  );
  const irPath = resolve(
    fixtureDir,
    options.promote ? `${safeLabel}.ir.json` : `${safeLabel}.ir.private.json`,
  );

  const now = options.now ?? (() => new Date().toISOString());
  const session = await options.driver.open(options.profile, { now });
  const warnings: string[] = [];
  const recorded: RecordedExchange[] = [];

  try {
    for (let i = 0; i < options.steps.length; i++) {
      const step = options.steps[i];
      const exchanges = await session.runStep(step, i);
      for (const exchange of exchanges) {
        const lossSignal = detectSessionLoss(options.profile, exchange);
        if (lossSignal) {
          throw new WorkflowAbortedError(
            `session-loss detected via ${lossSignal.indicator.kind}: ${lossSignal.indicator.description} (${lossSignal.source})`,
          );
        }
        const originAllowed = options.profile.allowedOrigins.some((origin) =>
          exchange.url.startsWith(origin),
        );
        if (!originAllowed) {
          warnings.push(
            `exchange dropped: origin not allowed by profile ${options.profile.id}: ${exchange.url}`,
          );
          continue;
        }
        recorded.push(exchange);
      }
    }
  } finally {
    await session.close();
  }

  if (recorded.length === 0) {
    throw new WorkflowAbortedError('no exchanges were recorded; refusing to write empty capture');
  }

  // Build HAR backup (raw, unredacted) and write it under captures/raw.
  const har = recordedExchangesToHar(recorded, { now });
  writeHarBackup(har, { rawDirAbsolute: rawDir, outFile: harPath });

  // Sanitize via the existing AC1 importer using the HAR we just built.
  const importResult = importCapture(JSON.stringify(har), {
    format: 'har',
    label: safeLabel,
    source: 'capture-workflow:in-memory-har',
    now,
  });
  for (const w of importResult.warnings) warnings.push(`importer: ${w}`);

  const provenance: CaptureProvenance = {
    siteProfileId: options.profile.id,
    siteProfileVersion: options.profile.version,
    recorderDriver: options.driver.name,
    liveReplayDisabled: true,
    capturedAt: now(),
    notes: [
      'Sanitized fixture emitted by capture-workflow. Never replayable as a live session.',
      `Site profile termsReviewStatus="${options.profile.termsReviewStatus}".`,
    ],
  };
  const fixture: CaptureFixture = {
    ...importResult.fixture,
    provenance,
    notes: [
      ...importResult.fixture.notes,
      `provenance: site=${options.profile.id} driver=${options.driver.name} liveReplayDisabled=true`,
    ],
  };

  // Build IR from the sanitized fixture.
  const ir = buildTrafficIR(fixture, { ...(options.irOptions ?? {}), now });

  // Defense-in-depth: round-trip the fixture through buildTrafficIR a second
  // time and compare against the first. This proves that, given the same
  // sanitized fixture, the IR is deterministic and replay-validated against
  // itself before we ship it.
  let validation: ReplayValidationReport | undefined;
  if (options.validateReplay) {
    const replayIr = buildTrafficIR(fixture, { ...(options.irOptions ?? {}), now });
    validation = compareTrafficIR(ir, replayIr);
    if (!validation.identical) {
      warnings.push(
        `replay validation: IR is non-deterministic; added=${validation.addedEndpointIds.length} removed=${validation.removedEndpointIds.length} changed=${validation.changedEndpoints.length}`,
      );
    }
  }

  // Persist sanitized artifacts. Both files default to *.private.* (gitignored)
  // unless the operator passes --promote.
  mkdirSync(dirname(fixturePath), { recursive: true });
  writeFileSync(fixturePath, fixtureToJson(fixture), { encoding: 'utf8', mode: 0o600 });
  writeFileSync(irPath, trafficIRToJson(ir), { encoding: 'utf8', mode: 0o600 });

  return {
    fixture,
    fixturePath,
    irPath,
    ir,
    harPath,
    har,
    recordedExchangeCount: recorded.length,
    validation,
    warnings,
  };
}

function sanitizeLabel(label: string): string {
  const cleaned = label.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  if (cleaned.length === 0) {
    throw new WorkflowGateError('label', 'capture-workflow: label must contain a-z0-9_- characters');
  }
  return cleaned;
}
