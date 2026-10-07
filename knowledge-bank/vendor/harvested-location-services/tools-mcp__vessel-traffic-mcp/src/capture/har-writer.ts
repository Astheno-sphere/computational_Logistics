import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, normalize, relative, resolve } from 'node:path';

import type { RecordedExchange } from './recorder.js';

export const HAR_VERSION = '1.2';

export interface HarEntry {
  startedDateTime: string;
  time: number;
  request: {
    method: string;
    url: string;
    httpVersion: string;
    headers: { name: string; value: string }[];
    cookies: { name: string; value: string }[];
    queryString: { name: string; value: string }[];
    headersSize: -1;
    bodySize: number;
    postData?: { mimeType: string; text: string };
  };
  response: {
    status: number;
    statusText: string;
    httpVersion: string;
    headers: { name: string; value: string }[];
    cookies: { name: string; value: string }[];
    content: { size: number; mimeType: string; text?: string };
    redirectURL: string;
    headersSize: -1;
    bodySize: number;
  };
  cache: Record<string, never>;
  timings: { send: number; wait: number; receive: number };
}

export interface HarLog {
  log: {
    version: string;
    creator: { name: string; version: string };
    browser?: { name: string; version: string };
    pages?: unknown[];
    entries: HarEntry[];
  };
}

export function recordedExchangesToHar(
  exchanges: readonly RecordedExchange[],
  meta: { creator?: { name: string; version: string }; now?: () => string } = {},
): HarLog {
  const creator = meta.creator ?? { name: 'vessel-capture-runner', version: '0.1.0' };
  const fallbackNow = meta.now ?? (() => new Date().toISOString());
  const entries: HarEntry[] = exchanges.map((exchange) => {
    const startedDateTime = exchange.startedAt ?? fallbackNow();
    const queryString = parseQuery(exchange.url);
    const requestBody = exchange.request.body;
    const responseBody = exchange.response.body;
    const responseMime = exchange.response.mimeType ?? 'application/octet-stream';
    return {
      startedDateTime,
      time: 0,
      request: {
        method: exchange.method.toUpperCase(),
        url: exchange.url,
        httpVersion: 'HTTP/1.1',
        headers: exchange.request.headers.map((h) => ({ name: h.name, value: h.value })),
        cookies: exchange.request.cookies.map((c) => ({ name: c.name, value: c.value })),
        queryString,
        headersSize: -1,
        bodySize: requestBody ? Buffer.byteLength(requestBody, 'utf8') : 0,
        postData:
          requestBody !== undefined
            ? {
                mimeType: exchange.request.mimeType ?? 'application/octet-stream',
                text: requestBody,
              }
            : undefined,
      },
      response: {
        status: exchange.response.status,
        statusText: exchange.response.statusText ?? '',
        httpVersion: 'HTTP/1.1',
        headers: exchange.response.headers.map((h) => ({ name: h.name, value: h.value })),
        cookies: exchange.response.cookies.map((c) => ({ name: c.name, value: c.value })),
        content: {
          size: responseBody ? Buffer.byteLength(responseBody, 'utf8') : 0,
          mimeType: responseMime,
          text: responseBody,
        },
        redirectURL: '',
        headersSize: -1,
        bodySize: responseBody ? Buffer.byteLength(responseBody, 'utf8') : 0,
      },
      cache: {},
      timings: { send: 0, wait: 0, receive: 0 },
    };
  });
  return {
    log: {
      version: HAR_VERSION,
      creator,
      entries,
    },
  };
}

function parseQuery(rawUrl: string): { name: string; value: string }[] {
  try {
    const u = new URL(rawUrl);
    const out: { name: string; value: string }[] = [];
    for (const [name, value] of u.searchParams.entries()) {
      out.push({ name, value });
    }
    return out;
  } catch {
    return [];
  }
}

export class HarPathError extends Error {}

export interface HarWriteOptions {
  /**
   * Absolute path that the HAR file MUST be written under (typically
   * `<workspace>/captures/raw`). Writes outside this directory are refused
   * because the resulting HAR contains the unredacted recorded session and
   * is gitignored only inside the configured raw directory.
   */
  rawDirAbsolute: string;
  /** Absolute path of the file to write. */
  outFile: string;
}

const RAW_GUARD_PATH_SEGMENT = `${'captures'}/raw`;

/**
 * Asserts that the requested HAR output path is contained within the raw
 * directory and that the raw directory itself sits inside a gitignored
 * `captures/raw` boundary. Defense-in-depth against accidentally writing a
 * raw HAR (which contains the recorded session secrets) into a tracked
 * location.
 */
export function assertHarOutputPath(options: HarWriteOptions): void {
  if (!isAbsolute(options.rawDirAbsolute)) {
    throw new HarPathError(`har-writer: rawDirAbsolute must be absolute, got "${options.rawDirAbsolute}"`);
  }
  if (!isAbsolute(options.outFile)) {
    throw new HarPathError(`har-writer: outFile must be absolute, got "${options.outFile}"`);
  }
  const normalizedRaw = normalize(options.rawDirAbsolute);
  if (!normalizedRaw.replaceAll('\\', '/').includes(RAW_GUARD_PATH_SEGMENT)) {
    throw new HarPathError(
      `har-writer: refusing to use raw directory "${normalizedRaw}" — must contain "${RAW_GUARD_PATH_SEGMENT}" segment to enforce gitignore boundary`,
    );
  }
  const rel = relative(normalizedRaw, normalize(options.outFile));
  if (rel.startsWith('..') || isAbsolute(rel)) {
    throw new HarPathError(
      `har-writer: refusing to write HAR outside raw directory; resolved relative="${rel}"`,
    );
  }
}

export interface HarWriteResult {
  outFile: string;
  bytesWritten: number;
}

export function writeHarBackup(har: HarLog, options: HarWriteOptions): HarWriteResult {
  assertHarOutputPath(options);
  mkdirSync(dirname(options.outFile), { recursive: true });
  const serialized = `${JSON.stringify(har, null, 2)}\n`;
  writeFileSync(options.outFile, serialized, { encoding: 'utf8', mode: 0o600 });
  return { outFile: options.outFile, bytesWritten: Buffer.byteLength(serialized, 'utf8') };
}

export function harToJson(har: HarLog): string {
  return JSON.stringify(har, null, 2);
}

export function defaultRawDir(workspaceCwd: string): string {
  return resolve(workspaceCwd, 'captures', 'raw');
}
