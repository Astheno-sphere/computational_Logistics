#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync, statSync, existsSync } from 'node:fs';
import { dirname, basename, extname, isAbsolute, resolve, relative } from 'node:path';

import { redactForLog } from '../util/redact.js';
import { fixtureToJson, importCapture, type ImportFormat } from './import.js';

interface ParsedCliArgs {
  inPath?: string;
  outPath?: string;
  format: ImportFormat;
  label?: string;
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

const HELP_TEXT = `vessel-capture-import — sanitize an authorized HAR/JSON capture into a fixture.

USAGE
  vessel-capture-import --in <path> [--out <path>] [--format har|json|auto] [--label <name>] [--force]

OPTIONS
  --in <path>           Path to the source HAR or JSON capture (required).
  --out <path>          Destination fixture path. Defaults to fixtures/captures/<basename>.fixture.json
                        relative to the current working directory.
  --format <fmt>        Source format: "har", "json", or "auto" (default).
  --label <name>        Human label stored in the fixture; also used for the default filename.
                        Sanitized to [a-z0-9_-] characters.
  --force               Overwrite the output file if it already exists.
  --help, -h            Show this message.

NOTES
  - Sensitive headers (Authorization, Cookie, Set-Cookie, X-Api-Key, ...), known credential
    query parameters, JSON body fields (password, token, api_key, ...), and JWT/AWS-style
    token strings are replaced with [REDACTED] before the fixture is written.
  - Multipart and binary bodies are dropped — only the MIME type is retained.
  - This tool does not call any live or paid provider. It only reads the local input file.
  - Raw HAR/.env captures must NEVER be committed; commit only the produced sanitized fixture.
`;

function parseArgs(argv: readonly string[]): ParsedCliArgs {
  const args: ParsedCliArgs = {
    format: 'auto',
    force: false,
    showHelp: false,
  };

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
      case '--format':
        args.format = parseFormat(readNext(argv, ++i, token));
        break;
      case '--label':
        args.label = readNext(argv, ++i, token);
        break;
      case '--force':
        args.force = true;
        break;
      default:
        if (token.startsWith('--in=')) args.inPath = token.slice(5);
        else if (token.startsWith('--out=')) args.outPath = token.slice(6);
        else if (token.startsWith('--format=')) args.format = parseFormat(token.slice(9));
        else if (token.startsWith('--label=')) args.label = token.slice(8);
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

function parseFormat(raw: string): ImportFormat {
  const lower = raw.trim().toLowerCase();
  if (lower === 'har' || lower === 'json' || lower === 'auto') return lower;
  throw new CliError(`unsupported --format "${raw}". Allowed: har, json, auto.`);
}

class CliError extends Error {}

export function defaultOutputPath(inPath: string, label: string | undefined, cwd: string): string {
  const base = label ?? basename(inPath, extname(inPath));
  const safeBase = base.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '') || 'capture';
  return resolve(cwd, 'fixtures', 'captures', `${safeBase}.fixture.json`);
}

export async function runCli(env: CliEnvironment): Promise<number> {
  let parsed: ParsedCliArgs;
  try {
    parsed = parseArgs(env.argv);
  } catch (err) {
    env.stderr(`vessel-capture-import: ${redactForLog(messageOf(err))}\n`);
    env.stderr(HELP_TEXT);
    return 2;
  }

  if (parsed.showHelp) {
    env.stdout(HELP_TEXT);
    return 0;
  }

  if (!parsed.inPath) {
    env.stderr('vessel-capture-import: missing required --in <path>.\n');
    env.stderr(HELP_TEXT);
    return 2;
  }

  const absoluteIn = isAbsolute(parsed.inPath) ? parsed.inPath : resolve(env.cwd, parsed.inPath);
  if (!env.exists(absoluteIn)) {
    env.stderr(`vessel-capture-import: input file not found: ${absoluteIn}\n`);
    return 2;
  }

  const outAbsolute = parsed.outPath
    ? isAbsolute(parsed.outPath)
      ? parsed.outPath
      : resolve(env.cwd, parsed.outPath)
    : defaultOutputPath(absoluteIn, parsed.label, env.cwd);

  if (env.exists(outAbsolute) && !parsed.force) {
    env.stderr(
      `vessel-capture-import: refusing to overwrite ${outAbsolute}. Pass --force to replace.\n`,
    );
    return 1;
  }

  let inputContent: string;
  try {
    inputContent = env.readFile(absoluteIn);
  } catch (err) {
    env.stderr(`vessel-capture-import: failed to read input: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  let result;
  try {
    result = importCapture(inputContent, {
      format: parsed.format,
      label: parsed.label,
      source: relative(env.cwd, absoluteIn),
      now: env.now,
    });
  } catch (err) {
    env.stderr(`vessel-capture-import: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  try {
    env.ensureDir(dirname(outAbsolute));
    env.writeFile(outAbsolute, fixtureToJson(result.fixture));
  } catch (err) {
    env.stderr(`vessel-capture-import: failed to write output: ${redactForLog(messageOf(err))}\n`);
    return 1;
  }

  for (const warning of result.warnings) {
    env.stderr(`vessel-capture-import: warning: ${redactForLog(warning)}\n`);
  }

  const report = result.fixture.redactionReport;
  env.stdout(
    `wrote ${result.fixture.entries.length} sanitized entries to ${outAbsolute} ` +
      `(redactions: ${report.totalRedactions}; headers=${report.redactedHeaders.length}, ` +
      `query=${report.redactedQueryParams.length}, body=${report.redactedBodyFields.length}, ` +
      `value-patterns=${report.redactedValuePatterns.length})\n`,
  );
  return 0;
}

function messageOf(value: unknown): string {
  return value instanceof Error ? value.message : String(value);
}

export function buildDefaultCliEnvironment(): CliEnvironment {
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
  runCli(buildDefaultCliEnvironment())
    .then((code) => {
      process.exitCode = code;
    })
    .catch((err: unknown) => {
      const message = err instanceof Error ? err.message : String(err);
      process.stderr.write(`vessel-capture-import: ${redactForLog(message)}\n`);
      process.exitCode = 1;
    });
}
