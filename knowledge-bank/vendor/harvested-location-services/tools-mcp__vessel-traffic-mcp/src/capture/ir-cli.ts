#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync, statSync, existsSync } from 'node:fs';
import { dirname, basename, extname, isAbsolute, resolve } from 'node:path';

import { redactForLog } from '../util/redact.js';
import { FIXTURE_FORMAT_VERSION, type CaptureFixture } from './import.js';
import {
  buildTrafficIR,
  trafficIRToJson,
  FixtureVersionError,
} from './traffic-ir.js';

interface ParsedCliArgs {
  inPath?: string;
  outPath?: string;
  maxDepth?: number;
  maxBreadth?: number;
  maxUnion?: number;
  maxSamplePaths?: number;
  force: boolean;
  showHelp: boolean;
}

interface CliEnvironment {
  argv: readonly string[];
  cwd: string;
  stdout: (text: string) => void;
  stderr: (text: string) => void;
  readFile: (path: string) => string;
  writeFile: (path: string, contents: string) => void;
  ensureDir: (path: string) => void;
  exists: (path: string) => boolean;
  now: () => string;
}

const HELP_TEXT = `vessel-capture-ir — generate endpoint fingerprints, traffic IR, and schema
summaries from a sanitized capture fixture.

USAGE
  vessel-capture-ir --in <fixture.json> [--out <ir.json>]
                    [--max-depth N] [--max-breadth N] [--max-union N]
                    [--max-sample-paths N] [--force]

OPTIONS
  --in <path>             Path to a sanitized capture fixture produced by
                          vessel-capture-import (required).
  --out <path>            Destination IR path. Defaults to
                          fixtures/captures/<basename>.ir.json
                          relative to the current working directory.
  --max-depth <N>         Max JSON nesting depth retained in schema (default 6).
  --max-breadth <N>       Max object keys retained per level (default 32).
  --max-union <N>         Max union variants retained per array (default 8).
  --max-sample-paths <N>  Max sample redacted path strings retained per
                          endpoint (default 3).
  --force                 Overwrite the output file if it already exists.
  --help, -h              Show this message.

GUARANTEES
  - Input must be a fixture from vessel-capture-import (version ${FIXTURE_FORMAT_VERSION}).
  - Raw HAR/JSON captures are NOT accepted; run vessel-capture-import first.
  - Cookie values are dropped; only the request cookie count is retained.
  - Header and query values are NOT retained; only name sets, with
    credential-bearing names flagged for review.
  - Schema summaries describe shape only, never raw values. Surviving
    [REDACTED] placeholders are flagged with redacted=true so they cannot
    be misinterpreted as data.
  - Output is byte-stable across runs for the same input (sorted keys,
    sorted arrays, deterministic union ordering).
  - A defense-in-depth scan re-checks the IR for JWT/AWS-style tokens
    before the file is written; any hit is surfaced as a warning and
    redacted.
`;

class CliError extends Error {}

function parseArgs(argv: readonly string[]): ParsedCliArgs {
  const args: ParsedCliArgs = { force: false, showHelp: false };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    switch (token) {
      case '-h':
      case '--help':
        args.showHelp = true;
        break;
      case '--in':
      case '--input':
        args.inPath = readNext(argv, ++i, token);
        break;
      case '--out':
      case '--output':
        args.outPath = readNext(argv, ++i, token);
        break;
      case '--max-depth':
        args.maxDepth = parsePositiveInt(readNext(argv, ++i, token), token);
        break;
      case '--max-breadth':
        args.maxBreadth = parsePositiveInt(readNext(argv, ++i, token), token);
        break;
      case '--max-union':
        args.maxUnion = parsePositiveInt(readNext(argv, ++i, token), token);
        break;
      case '--max-sample-paths':
        args.maxSamplePaths = parsePositiveInt(readNext(argv, ++i, token), token);
        break;
      case '--force':
        args.force = true;
        break;
      default:
        if (token.startsWith('--in=')) args.inPath = token.slice(5);
        else if (token.startsWith('--out=')) args.outPath = token.slice(6);
        else if (token.startsWith('--max-depth=')) args.maxDepth = parsePositiveInt(token.slice(12), '--max-depth');
        else if (token.startsWith('--max-breadth=')) args.maxBreadth = parsePositiveInt(token.slice(14), '--max-breadth');
        else if (token.startsWith('--max-union=')) args.maxUnion = parsePositiveInt(token.slice(12), '--max-union');
        else if (token.startsWith('--max-sample-paths=')) args.maxSamplePaths = parsePositiveInt(token.slice(19), '--max-sample-paths');
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

function parsePositiveInt(raw: string, flag: string): number {
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n) || n <= 0) {
    throw new CliError(`option "${flag}" requires a positive integer, got "${raw}".`);
  }
  return n;
}

export function defaultOutputPath(inPath: string, cwd: string): string {
  const stem = basename(inPath, extname(inPath))
    .replace(/\.fixture$/i, '')
    .replace(/[^a-z0-9_-]+/gi, '-')
    .replace(/^-+|-+$/g, '');
  const safe = stem.length === 0 ? 'capture' : stem.toLowerCase();
  return resolve(cwd, 'fixtures', 'captures', `${safe}.ir.json`);
}

function parseFixture(raw: string): CaptureFixture {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new CliError(
      `input is not valid JSON (${err instanceof Error ? err.message : String(err)})`,
    );
  }
  if (!parsed || typeof parsed !== 'object') {
    throw new CliError('input fixture must be a JSON object');
  }
  const obj = parsed as Record<string, unknown>;
  if (typeof obj.version !== 'number' || obj.version !== FIXTURE_FORMAT_VERSION) {
    throw new FixtureVersionError(obj.version);
  }
  if (!Array.isArray(obj.entries)) {
    throw new CliError('input fixture must contain an "entries" array');
  }
  return parsed as CaptureFixture;
}

export async function runIrCli(env: CliEnvironment): Promise<number> {
  let parsed: ParsedCliArgs;
  try {
    parsed = parseArgs(env.argv);
  } catch (err) {
    env.stderr(`vessel-capture-ir: ${redactForLog(messageOf(err))}\n`);
    env.stderr(HELP_TEXT);
    return 2;
  }

  if (parsed.showHelp) {
    env.stdout(HELP_TEXT);
    return 0;
  }

  if (!parsed.inPath) {
    env.stderr('vessel-capture-ir: missing required --in <fixture.json>.\n');
    env.stderr(HELP_TEXT);
    return 2;
  }

  const absoluteIn = isAbsolute(parsed.inPath) ? parsed.inPath : resolve(env.cwd, parsed.inPath);
  if (!env.exists(absoluteIn)) {
    env.stderr(`vessel-capture-ir: input fixture not found: ${absoluteIn}\n`);
    return 2;
  }

  const outAbsolute = parsed.outPath
    ? isAbsolute(parsed.outPath)
      ? parsed.outPath
      : resolve(env.cwd, parsed.outPath)
    : defaultOutputPath(absoluteIn, env.cwd);

  if (env.exists(outAbsolute) && !parsed.force) {
    env.stderr(
      `vessel-capture-ir: refusing to overwrite ${outAbsolute}. Pass --force to replace.\n`,
    );
    return 1;
  }

  let inputContent: string;
  try {
    inputContent = env.readFile(absoluteIn);
  } catch (err) {
    env.stderr(`vessel-capture-ir: failed to read fixture: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  let fixture: CaptureFixture;
  try {
    fixture = parseFixture(inputContent);
  } catch (err) {
    env.stderr(`vessel-capture-ir: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  let ir;
  try {
    ir = buildTrafficIR(fixture, {
      maxDepth: parsed.maxDepth,
      maxBreadth: parsed.maxBreadth,
      maxUnion: parsed.maxUnion,
      maxSamplePaths: parsed.maxSamplePaths,
      now: env.now,
    });
  } catch (err) {
    env.stderr(`vessel-capture-ir: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  try {
    env.ensureDir(dirname(outAbsolute));
    env.writeFile(outAbsolute, trafficIRToJson(ir));
  } catch (err) {
    env.stderr(`vessel-capture-ir: failed to write output: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  for (const warning of ir.warnings) {
    env.stderr(`vessel-capture-ir: warning: ${redactForLog(warning)}\n`);
  }

  const redactedCount = ir.endpoints.reduce((acc, e) => acc + e.redactedHeaderNames.length, 0);
  env.stdout(
    `wrote ${ir.endpoints.length} endpoint(s) (${ir.source.entryCount} entries, ` +
      `${redactedCount} credential-bearing header names flagged) to ${outAbsolute}\n`,
  );
  return 0;
}

function messageOf(value: unknown): string {
  return value instanceof Error ? value.message : String(value);
}

export function buildDefaultIrCliEnvironment(): CliEnvironment {
  return {
    argv: process.argv.slice(2),
    cwd: process.cwd(),
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
  runIrCli(buildDefaultIrCliEnvironment())
    .then((code) => {
      process.exitCode = code;
    })
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : String(err);
      process.stderr.write(`vessel-capture-ir: ${redactForLog(message)}\n`);
      process.exitCode = 1;
    });
}
