#!/usr/bin/env node

import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { isAbsolute, resolve } from 'node:path';

import { redactForLog } from '../util/redact.js';
import { loadSiteProfile, SiteProfileError } from './site-profile.js';
import {
  createMockRecorderDriver,
  createPlaywrightRecorderDriver,
  type MockScript,
  type RecorderDriver,
  type WorkflowStep,
} from './recorder.js';
import {
  runCaptureWorkflow,
  WorkflowAbortedError,
  WorkflowGateError,
  type CaptureWorkflowResult,
} from './workflow.js';

interface ParsedRunnerArgs {
  siteProfilePath?: string;
  scriptPath?: string;
  driver: 'mock' | 'playwright';
  label?: string;
  outDir?: string;
  iAmAuthorized: boolean;
  validateReplay: boolean;
  promote: boolean;
  showHelp: boolean;
}

export interface RunnerCliEnvironment {
  argv: readonly string[];
  cwd: string;
  env: Record<string, string | undefined>;
  stdout: (text: string) => void;
  stderr: (text: string) => void;
  readFile: (path: string) => string;
  writeFile: (path: string, contents: string) => void;
  ensureDir: (path: string) => void;
  exists: (path: string) => boolean;
  now: () => string;
}

const HELP_TEXT = `vessel-capture-runner — operator-only authorized maritime capture workflow.

USAGE
  vessel-capture-runner --site-profile <path> --label <name>
                        [--script <path>] [--driver mock|playwright]
                        [--out-dir <dir>] [--i-am-authorized]
                        [--validate-replay] [--promote]

OPTIONS
  --site-profile <path>  Path to a JSON site profile (required).
  --label <name>         Human label used in the fixture and filenames.
  --script <path>        Path to a JSON capture script (required for --driver mock).
                         Each entry is { step: WorkflowStep, exchanges: RecordedExchange[] }.
  --driver mock|playwright  Recorder driver. Default: mock.
  --out-dir <dir>        Workspace directory for outputs. Defaults to cwd.
                         HAR backup goes to <out-dir>/captures/raw/<label>.har.
                         Sanitized fixture goes to <out-dir>/fixtures/captures/<label>.private.json.
  --i-am-authorized      Required for --driver playwright. Confirms the operator
                         has reviewed the site terms and the session is authorized.
  --validate-replay      Round-trip the fixture through the IR builder a second
                         time and verify the IR is deterministic.
  --promote              Drop the .private suffix from output filenames so the
                         operator can review and commit the fixture. Default off.
  --help, -h             Show this message.

GATES
  - --driver playwright requires VESSEL_CAPTURE_LIVE=1 and --i-am-authorized,
    and the site profile termsReviewStatus must equal "allowed".
  - --driver mock is the default and never touches the network. Tests and
    autodev/CI must use the mock driver only.
  - Any site profile with termsReviewStatus="blocked" is refused even with
    --driver mock.
  - The output HAR is path-asserted to live under <out-dir>/captures/raw and
    is never written to a tracked location.

NOTES
  - Sanitized fixtures are stamped with provenance.liveReplayDisabled=true and
    are never replayable as a live session.
  - Raw HAR backups remain on the operator's local disk only; the captures/raw
    directory is gitignored.
`;

class CliError extends Error {}

export function parseRunnerArgs(argv: readonly string[]): ParsedRunnerArgs {
  const args: ParsedRunnerArgs = {
    driver: 'mock',
    iAmAuthorized: false,
    validateReplay: false,
    promote: false,
    showHelp: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    switch (token) {
      case '-h':
      case '--help':
        args.showHelp = true;
        break;
      case '--site-profile':
        args.siteProfilePath = readNext(argv, ++i, token);
        break;
      case '--script':
        args.scriptPath = readNext(argv, ++i, token);
        break;
      case '--driver':
        args.driver = parseDriver(readNext(argv, ++i, token));
        break;
      case '--label':
        args.label = readNext(argv, ++i, token);
        break;
      case '--out-dir':
        args.outDir = readNext(argv, ++i, token);
        break;
      case '--i-am-authorized':
        args.iAmAuthorized = true;
        break;
      case '--validate-replay':
        args.validateReplay = true;
        break;
      case '--promote':
        args.promote = true;
        break;
      default:
        if (token.startsWith('--site-profile=')) args.siteProfilePath = token.slice('--site-profile='.length);
        else if (token.startsWith('--script=')) args.scriptPath = token.slice('--script='.length);
        else if (token.startsWith('--driver=')) args.driver = parseDriver(token.slice('--driver='.length));
        else if (token.startsWith('--label=')) args.label = token.slice('--label='.length);
        else if (token.startsWith('--out-dir=')) args.outDir = token.slice('--out-dir='.length);
        else throw new CliError(`unknown argument "${token}". Use --help for usage.`);
    }
  }
  return args;
}

function readNext(argv: readonly string[], index: number, flag: string): string {
  const value = argv[index];
  if (value === undefined || value.startsWith('--')) {
    throw new CliError(`option "${flag}" requires a value.`);
  }
  return value;
}

function parseDriver(raw: string): 'mock' | 'playwright' {
  const lower = raw.trim().toLowerCase();
  if (lower === 'mock' || lower === 'playwright') return lower;
  throw new CliError(`unsupported --driver "${raw}". Allowed: mock, playwright.`);
}

interface ParsedScript {
  steps: WorkflowStep[];
  script: MockScript;
}

export function parseScriptFile(raw: string): ParsedScript {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new CliError(
      `script JSON is invalid: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (!parsed || typeof parsed !== 'object' || !Array.isArray((parsed as { steps?: unknown }).steps)) {
    throw new CliError('script must be a JSON object with a "steps" array');
  }
  const stepEntries = (parsed as { steps: unknown[] }).steps;
  const script: MockScript = { steps: [] };
  const steps: WorkflowStep[] = [];
  for (let i = 0; i < stepEntries.length; i++) {
    const entry = stepEntries[i];
    if (!entry || typeof entry !== 'object') {
      throw new CliError(`script.steps[${i}] is not an object`);
    }
    const candidate = entry as { step?: WorkflowStep; exchanges?: unknown };
    if (!candidate.step || !Array.isArray(candidate.exchanges)) {
      throw new CliError(`script.steps[${i}] requires { step, exchanges[] }`);
    }
    script.steps.push({
      step: candidate.step,
      exchanges: candidate.exchanges as MockScript['steps'][number]['exchanges'],
    });
    steps.push(candidate.step);
  }
  return { steps, script };
}

export async function runRunnerCli(env: RunnerCliEnvironment): Promise<number> {
  let parsed: ParsedRunnerArgs;
  try {
    parsed = parseRunnerArgs(env.argv);
  } catch (err) {
    env.stderr(`vessel-capture-runner: ${redactForLog(messageOf(err))}\n`);
    env.stderr(HELP_TEXT);
    return 2;
  }
  if (parsed.showHelp) {
    env.stdout(HELP_TEXT);
    return 0;
  }
  if (!parsed.siteProfilePath) {
    env.stderr('vessel-capture-runner: --site-profile <path> is required\n');
    return 2;
  }
  if (!parsed.label) {
    env.stderr('vessel-capture-runner: --label <name> is required\n');
    return 2;
  }
  if (parsed.driver === 'mock' && !parsed.scriptPath) {
    env.stderr('vessel-capture-runner: --script <path> is required when --driver=mock\n');
    return 2;
  }

  const profileAbs = resolveAbsolute(parsed.siteProfilePath, env.cwd);
  if (!env.exists(profileAbs)) {
    env.stderr(`vessel-capture-runner: site profile not found: ${profileAbs}\n`);
    return 2;
  }

  let profile;
  try {
    profile = loadSiteProfile(env.readFile(profileAbs));
  } catch (err) {
    if (err instanceof SiteProfileError) {
      env.stderr(`vessel-capture-runner: ${redactForLog(err.message)}\n`);
      return 2;
    }
    env.stderr(`vessel-capture-runner: failed to load site profile: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  let driver: RecorderDriver;
  let parsedScript: ParsedScript | undefined;
  if (parsed.driver === 'mock') {
    const scriptAbs = resolveAbsolute(parsed.scriptPath as string, env.cwd);
    if (!env.exists(scriptAbs)) {
      env.stderr(`vessel-capture-runner: script not found: ${scriptAbs}\n`);
      return 2;
    }
    try {
      parsedScript = parseScriptFile(env.readFile(scriptAbs));
    } catch (err) {
      env.stderr(`vessel-capture-runner: ${redactForLog(messageOf(err))}\n`);
      return 2;
    }
    driver = createMockRecorderDriver(parsedScript.script);
  } else {
    try {
      driver = await createPlaywrightRecorderDriver();
    } catch (err) {
      env.stderr(`vessel-capture-runner: ${redactForLog(messageOf(err))}\n`);
      return 1;
    }
  }

  const outDir = parsed.outDir ? resolveAbsolute(parsed.outDir, env.cwd) : env.cwd;

  let result: CaptureWorkflowResult;
  try {
    result = await runCaptureWorkflow({
      profile,
      driver,
      steps: parsedScript ? parsedScript.steps : [],
      label: parsed.label,
      cwd: outDir,
      authorized: parsed.iAmAuthorized,
      liveEnvEnabled: env.env.VESSEL_CAPTURE_LIVE === '1',
      validateReplay: parsed.validateReplay,
      promote: parsed.promote,
      now: env.now,
    });
  } catch (err) {
    if (err instanceof WorkflowGateError) {
      env.stderr(`vessel-capture-runner: gate ${err.code}: ${redactForLog(err.message)}\n`);
      return 2;
    }
    if (err instanceof WorkflowAbortedError) {
      env.stderr(`vessel-capture-runner: aborted: ${redactForLog(err.message)}\n`);
      return 3;
    }
    if (err instanceof SiteProfileError) {
      env.stderr(`vessel-capture-runner: ${redactForLog(err.message)}\n`);
      return 2;
    }
    env.stderr(`vessel-capture-runner: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  for (const w of result.warnings) {
    env.stderr(`vessel-capture-runner: warning: ${redactForLog(w)}\n`);
  }
  env.stdout(
    `wrote ${result.recordedExchangeCount} recorded exchange(s); ` +
      `har=${result.harPath}; fixture=${result.fixturePath}; ir=${result.irPath}; ` +
      `endpoints=${result.ir.endpoints.length}` +
      (result.validation ? `; replay-identical=${String(result.validation.identical)}` : '') +
      `\n`,
  );
  return 0;
}

function resolveAbsolute(path: string, cwd: string): string {
  return isAbsolute(path) ? path : resolve(cwd, path);
}

function messageOf(value: unknown): string {
  return value instanceof Error ? value.message : String(value);
}

export function buildDefaultRunnerEnvironment(): RunnerCliEnvironment {
  return {
    argv: process.argv.slice(2),
    cwd: process.cwd(),
    env: process.env as Record<string, string | undefined>,
    stdout: (text) => process.stdout.write(text),
    stderr: (text) => process.stderr.write(text),
    readFile: (path) => readFileSync(path, 'utf8'),
    writeFile: (path, contents) => writeFileSync(path, contents, { encoding: 'utf8', mode: 0o600 }),
    ensureDir: (path) => mkdirSync(path, { recursive: true }),
    exists: (path) => {
      try {
        statSync(path);
        return true;
      } catch {
        return existsSync(path);
      }
    },
    now: () => new Date().toISOString(),
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runRunnerCli(buildDefaultRunnerEnvironment())
    .then((code) => {
      process.exitCode = code;
    })
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : String(err);
      process.stderr.write(`vessel-capture-runner: ${redactForLog(message)}\n`);
      process.exitCode = 1;
    });
}
