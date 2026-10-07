import {
  createRedactionCounter,
  redactBody,
  redactCookiePairs,
  redactHeaderPairs,
  redactUrl,
  summarizeRedactions,
  type NameValuePair,
  type RedactionReport,
} from './redact.js';

export const FIXTURE_FORMAT_VERSION = 1;

export type ImportFormat = 'har' | 'json' | 'auto';

export interface ImportOptions {
  format?: ImportFormat;
  label?: string;
  source?: string;
  now?: () => string;
}

export interface FixtureEntry {
  method: string;
  url: string;
  queryParams: NameValuePair[];
  request: {
    headers: NameValuePair[];
    cookies: { name: string; value: string }[];
    mimeType?: string;
    body?: string;
  };
  response: {
    status: number;
    statusText?: string;
    headers: NameValuePair[];
    cookies: { name: string; value: string }[];
    mimeType?: string;
    body?: string;
  };
  startedAt?: string;
}

export interface CaptureProvenance {
  siteProfileId: string;
  siteProfileVersion: number;
  recorderDriver: 'mock' | 'playwright';
  liveReplayDisabled: true;
  capturedAt: string;
  notes?: string[];
}

export interface CaptureFixture {
  version: number;
  label: string;
  createdAt: string;
  source: {
    format: 'har' | 'json';
    sourceFile?: string;
    entryCount: number;
  };
  entries: FixtureEntry[];
  redactionReport: RedactionReport;
  notes: string[];
  provenance?: CaptureProvenance;
}

export interface ImportResult {
  fixture: CaptureFixture;
  warnings: string[];
}

const DEFAULT_NOTES = [
  'Sanitized authorized capture fixture. Do not use as live AIS or safety-critical navigation data.',
  'All known sensitive headers, cookies, query parameters, and body fields are replaced with [REDACTED].',
  'Imported through the vessel-capture-import CLI; see docs/runbooks/capture-fixture-import.md.',
];

export function importCapture(rawInput: string, options: ImportOptions = {}): ImportResult {
  const format = resolveFormat(rawInput, options.format ?? 'auto');
  const counter = createRedactionCounter();
  const warnings: string[] = [];

  const parsed = safeParseJson(rawInput);
  if (parsed.error) {
    throw new Error(`capture import failed: input is not valid JSON (${parsed.error})`);
  }

  let entries: FixtureEntry[];
  if (format === 'har') {
    entries = importHarEntries(parsed.value, counter, warnings);
  } else {
    entries = importJsonEntries(parsed.value, counter, warnings);
  }

  const now = options.now ? options.now() : new Date().toISOString();
  const label = sanitizeLabel(options.label) ?? 'capture';

  const fixture: CaptureFixture = {
    version: FIXTURE_FORMAT_VERSION,
    label,
    createdAt: now,
    source: {
      format,
      sourceFile: options.source,
      entryCount: entries.length,
    },
    entries,
    redactionReport: summarizeRedactions(counter),
    notes: DEFAULT_NOTES,
  };

  return { fixture, warnings };
}

function resolveFormat(rawInput: string, requested: ImportFormat): 'har' | 'json' {
  if (requested === 'har' || requested === 'json') return requested;
  // auto-detect: HAR documents have `log.entries`.
  const trimmed = rawInput.trimStart();
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return 'json';
  try {
    const value = JSON.parse(rawInput);
    if (
      value &&
      typeof value === 'object' &&
      'log' in value &&
      typeof (value as Record<string, unknown>).log === 'object'
    ) {
      const log = (value as { log?: { entries?: unknown } }).log;
      if (log && Array.isArray(log.entries)) return 'har';
    }
  } catch {
    // fall through; importers will surface the parse error.
  }
  return 'json';
}

interface ParseResult {
  value: unknown;
  error?: string;
}

function safeParseJson(input: string): ParseResult {
  try {
    return { value: JSON.parse(input) };
  } catch (err) {
    return { value: null, error: err instanceof Error ? err.message : String(err) };
  }
}

function importHarEntries(
  parsed: unknown,
  counter: ReturnType<typeof createRedactionCounter>,
  warnings: string[],
): FixtureEntry[] {
  const log = (parsed as { log?: unknown })?.log;
  if (!log || typeof log !== 'object') {
    throw new Error('capture import failed: HAR file has no "log" object');
  }
  const harEntries = (log as { entries?: unknown }).entries;
  if (!Array.isArray(harEntries)) {
    throw new Error('capture import failed: HAR file has no "log.entries" array');
  }

  const fixtureEntries: FixtureEntry[] = [];
  for (let i = 0; i < harEntries.length; i++) {
    const raw = harEntries[i];
    if (!raw || typeof raw !== 'object') {
      warnings.push(`har entry ${i} skipped: not an object`);
      continue;
    }
    const entry = raw as Record<string, unknown>;
    const request = (entry.request ?? {}) as Record<string, unknown>;
    const response = (entry.response ?? {}) as Record<string, unknown>;

    const method = typeof request.method === 'string' ? request.method.toUpperCase() : 'GET';
    const rawUrl = typeof request.url === 'string' ? request.url : '';
    const { url, queryParams } = redactUrl(rawUrl, counter);

    const requestHeaders = redactHeaderPairs(asNameValueList(request.headers), counter);
    const responseHeaders = redactHeaderPairs(asNameValueList(response.headers), counter);
    const requestCookies = redactCookiePairs(asNameValueList(request.cookies), counter);
    const responseCookies = redactCookiePairs(asNameValueList(response.cookies), counter);

    const requestPostData = (request.postData ?? {}) as Record<string, unknown>;
    const requestMime = typeof requestPostData.mimeType === 'string' ? requestPostData.mimeType : undefined;
    const requestBody = redactBody(
      requestMime,
      typeof requestPostData.text === 'string' ? requestPostData.text : undefined,
      counter,
    );

    const responseContent = (response.content ?? {}) as Record<string, unknown>;
    const responseMime = typeof responseContent.mimeType === 'string' ? responseContent.mimeType : undefined;
    let responseText: string | undefined;
    if (typeof responseContent.text === 'string') {
      const encoding = typeof responseContent.encoding === 'string' ? responseContent.encoding : '';
      if (encoding.toLowerCase() === 'base64') {
        // Drop base64 binary blobs; they cannot be safely scanned for tokens
        // and are usually large media or downloads.
        warnings.push(`har entry ${i} response body is base64-encoded; dropped before redaction`);
        responseText = undefined;
      } else {
        responseText = responseContent.text;
      }
    }
    const responseBody = redactBody(responseMime, responseText, counter);

    fixtureEntries.push({
      method,
      url,
      queryParams,
      startedAt: typeof entry.startedDateTime === 'string' ? entry.startedDateTime : undefined,
      request: {
        headers: requestHeaders,
        cookies: requestCookies,
        mimeType: requestMime,
        body: requestBody.text,
      },
      response: {
        status: typeof response.status === 'number' ? response.status : 0,
        statusText: typeof response.statusText === 'string' ? response.statusText : undefined,
        headers: responseHeaders,
        cookies: responseCookies,
        mimeType: responseMime,
        body: responseBody.text,
      },
    });
  }
  return fixtureEntries;
}

function importJsonEntries(
  parsed: unknown,
  counter: ReturnType<typeof createRedactionCounter>,
  warnings: string[],
): FixtureEntry[] {
  const candidates = extractJsonEntries(parsed);
  if (candidates.length === 0) {
    throw new Error(
      'capture import failed: JSON input must be an array of capture entries, an object with an "entries" array, or a single entry object',
    );
  }

  const out: FixtureEntry[] = [];
  for (let i = 0; i < candidates.length; i++) {
    const raw = candidates[i];
    if (!raw || typeof raw !== 'object') {
      warnings.push(`json entry ${i} skipped: not an object`);
      continue;
    }
    const entry = raw as Record<string, unknown>;
    const request = (entry.request ?? {}) as Record<string, unknown>;
    const response = (entry.response ?? {}) as Record<string, unknown>;

    const method =
      typeof entry.method === 'string'
        ? entry.method.toUpperCase()
        : typeof request.method === 'string'
          ? request.method.toUpperCase()
          : 'GET';
    const rawUrl =
      typeof entry.url === 'string'
        ? entry.url
        : typeof request.url === 'string'
          ? request.url
          : '';
    const { url, queryParams } = redactUrl(rawUrl, counter);

    const requestHeaders = redactHeaderPairs(asNameValueList(request.headers), counter);
    const responseHeaders = redactHeaderPairs(asNameValueList(response.headers), counter);
    const requestCookies = redactCookiePairs(asNameValueList(request.cookies), counter);
    const responseCookies = redactCookiePairs(asNameValueList(response.cookies), counter);

    const requestMime = pickMime(request);
    const requestRawBody = pickBodyText(request);
    const requestBody = redactBody(requestMime, requestRawBody, counter);

    const responseMime = pickMime(response);
    const responseRawBody = pickBodyText(response);
    const responseBody = redactBody(responseMime, responseRawBody, counter);

    out.push({
      method,
      url,
      queryParams,
      startedAt:
        typeof entry.startedAt === 'string'
          ? entry.startedAt
          : typeof entry.startedDateTime === 'string'
            ? entry.startedDateTime
            : undefined,
      request: {
        headers: requestHeaders,
        cookies: requestCookies,
        mimeType: requestMime,
        body: requestBody.text,
      },
      response: {
        status:
          typeof response.status === 'number'
            ? response.status
            : typeof entry.status === 'number'
              ? entry.status
              : 0,
        statusText: typeof response.statusText === 'string' ? response.statusText : undefined,
        headers: responseHeaders,
        cookies: responseCookies,
        mimeType: responseMime,
        body: responseBody.text,
      },
    });
  }
  return out;
}

function extractJsonEntries(parsed: unknown): unknown[] {
  if (Array.isArray(parsed)) return parsed;
  if (parsed && typeof parsed === 'object') {
    const obj = parsed as Record<string, unknown>;
    if (Array.isArray(obj.entries)) return obj.entries;
    if (Array.isArray(obj.requests)) return obj.requests;
    if (Array.isArray(obj.samples)) return obj.samples;
    if (typeof obj.url === 'string' || typeof obj.method === 'string' || obj.request || obj.response) {
      return [obj];
    }
  }
  return [];
}

function asNameValueList(value: unknown): { name: string; value: string }[] {
  if (Array.isArray(value)) {
    const out: { name: string; value: string }[] = [];
    for (const item of value) {
      if (item && typeof item === 'object' && typeof (item as { name?: unknown }).name === 'string') {
        const nv = item as { name: string; value?: unknown };
        out.push({ name: nv.name, value: typeof nv.value === 'string' ? nv.value : String(nv.value ?? '') });
      }
    }
    return out;
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).map(([name, raw]) => ({
      name,
      value: typeof raw === 'string' ? raw : String(raw ?? ''),
    }));
  }
  return [];
}

function pickMime(section: Record<string, unknown>): string | undefined {
  if (typeof section.mimeType === 'string') return section.mimeType;
  if (typeof section.contentType === 'string') return section.contentType;
  const headers = asNameValueList(section.headers);
  for (const header of headers) {
    if (header.name.toLowerCase() === 'content-type') return header.value;
  }
  return undefined;
}

function pickBodyText(section: Record<string, unknown>): string | undefined {
  if (typeof section.body === 'string') return section.body;
  if (typeof section.text === 'string') return section.text;
  if (section.body !== undefined && section.body !== null && typeof section.body === 'object') {
    return JSON.stringify(section.body);
  }
  if (section.json !== undefined && section.json !== null) {
    return JSON.stringify(section.json);
  }
  return undefined;
}

function sanitizeLabel(label: string | undefined): string | undefined {
  if (!label) return undefined;
  const cleaned = label.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return cleaned.length === 0 ? undefined : cleaned;
}

export function fixtureToJson(fixture: CaptureFixture): string {
  return `${JSON.stringify(fixture, null, 2)}\n`;
}
