import { redactForLog } from './redact.js';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export const sensitiveKeyPatterns: readonly RegExp[] = [
  /^authorization$/i,
  /^proxy-authorization$/i,
  /^cookie$/i,
  /^set-cookie$/i,
  /api[_-]?key/i,
  /^x-api-key$/i,
  /access[_-]?token/i,
  /refresh[_-]?token/i,
  /id[_-]?token/i,
  /^bearer([_-]?token)?$/i,
  /^token$/i,
  /^auth[_-]?token$/i,
  /password/i,
  /^pass(wd)?$/i,
  /^secret$/i,
  /client[_-]?secret/i,
  /session[_-]?id/i,
  /^session$/i,
  /subscription[_-]?key/i,
  /credential/i,
];

const REDACTED = '[REDACTED]';
const MAX_DEPTH = 12;

export function isSensitiveKey(key: string): boolean {
  return sensitiveKeyPatterns.some((pattern) => pattern.test(key));
}

export function redactStructured(value: unknown): unknown {
  return redactValue(value, 0);
}

function redactValue(value: unknown, depth: number): unknown {
  if (depth > MAX_DEPTH) {
    return '[TRUNCATED]';
  }
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof value === 'string') {
    return redactForLog(value);
  }
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item, depth + 1));
  }
  if (typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (isSensitiveKey(key)) {
        out[key] = REDACTED;
      } else {
        out[key] = redactValue(child, depth + 1);
      }
    }
    return out;
  }
  return undefined;
}

export interface JsonLogEntry {
  ts: string;
  level: LogLevel;
  event: string;
  [field: string]: unknown;
}

export type JsonLogSink = (line: string, entry: JsonLogEntry) => void;

export interface JsonLogger {
  log(level: LogLevel, event: string, fields?: Record<string, unknown>): void;
  debug(event: string, fields?: Record<string, unknown>): void;
  info(event: string, fields?: Record<string, unknown>): void;
  warn(event: string, fields?: Record<string, unknown>): void;
  error(event: string, fields?: Record<string, unknown>): void;
  withBase(extraBase: Record<string, unknown>): JsonLogger;
}

export interface CreateJsonLoggerOptions {
  sink?: JsonLogSink;
  baseFields?: Record<string, unknown>;
  redact?: boolean;
  now?: () => Date;
}

export function defaultStderrSink(line: string): void {
  process.stderr.write(`${line}\n`);
}

export function createJsonLogger(options: CreateJsonLoggerOptions = {}): JsonLogger {
  const sink = options.sink ?? defaultStderrSink;
  const baseFields = options.baseFields ?? {};
  const shouldRedact = options.redact !== false;
  const now = options.now ?? (() => new Date());

  function emit(level: LogLevel, event: string, fields?: Record<string, unknown>): void {
    const merged: Record<string, unknown> = {
      ts: now().toISOString(),
      level,
      event,
      ...baseFields,
      ...(fields ?? {}),
    };
    const safe = shouldRedact
      ? (redactStructured(merged) as Record<string, unknown>)
      : merged;
    const entry = safe as JsonLogEntry;
    let line: string;
    try {
      line = JSON.stringify(entry);
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      const fallback: JsonLogEntry = {
        ts: now().toISOString(),
        level: 'error',
        event: 'logger_serialize_failed',
        reason: redactForLog(reason),
      };
      line = JSON.stringify(fallback);
      sink(line, fallback);
      return;
    }
    sink(line, entry);
  }

  return {
    log: emit,
    debug(event, fields) {
      emit('debug', event, fields);
    },
    info(event, fields) {
      emit('info', event, fields);
    },
    warn(event, fields) {
      emit('warn', event, fields);
    },
    error(event, fields) {
      emit('error', event, fields);
    },
    withBase(extraBase) {
      return createJsonLogger({
        sink,
        baseFields: { ...baseFields, ...extraBase },
        redact: shouldRedact,
        now,
      });
    },
  };
}
