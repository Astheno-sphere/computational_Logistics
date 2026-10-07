export const REDACTED_PLACEHOLDER = '[REDACTED]';

export const SENSITIVE_HEADER_NAMES: readonly string[] = [
  'authorization',
  'proxy-authorization',
  'cookie',
  'set-cookie',
  'www-authenticate',
  'authentication',
  'api-key',
  'apikey',
  'x-api-key',
  'x-apikey',
  'x-auth-token',
  'x-access-token',
  'x-amz-security-token',
  'x-csrf-token',
  'x-xsrf-token',
  'x-session-id',
  'x-session-token',
  'x-goog-api-key',
  'x-functions-key',
  'x-mt-api-key',
  'x-vesselfinder-key',
  'session-id',
  'session-token',
];

export const SENSITIVE_QUERY_PARAM_NAMES: readonly string[] = [
  'token',
  'access_token',
  'refresh_token',
  'id_token',
  'bearer',
  'bearer_token',
  'api_key',
  'apikey',
  'app_key',
  'key',
  'subscription_key',
  'client_secret',
  'secret',
  'session',
  'sessionid',
  'session_id',
  'sid',
  'auth',
  'authentication',
  'password',
  'passwd',
  'pwd',
  'mt_key',
  'userkey',
];

export const SENSITIVE_BODY_FIELD_NAMES: readonly string[] = [
  'password',
  'passwd',
  'pwd',
  'token',
  'access_token',
  'refresh_token',
  'id_token',
  'bearer_token',
  'bearertoken',
  'session_token',
  'session_id',
  'sessionid',
  'session',
  'api_key',
  'apikey',
  'app_key',
  'subscription_key',
  'client_secret',
  'secret',
  'authorization',
  'auth',
  'cookie',
  'set_cookie',
  'credit_card',
  'creditcard',
  'cardnumber',
  'card_number',
  'cvv',
  'ssn',
];

const VALUE_PATTERNS: readonly { pattern: RegExp; label: string }[] = [
  { pattern: /\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, label: 'jwt' },
  { pattern: /\bAKIA[0-9A-Z]{16}\b/g, label: 'aws-access-key-id' },
  { pattern: /\bASIA[0-9A-Z]{16}\b/g, label: 'aws-temp-key-id' },
  { pattern: /\bsk-[A-Za-z0-9_-]{16,}\b/g, label: 'sk-token' },
  { pattern: /\bghp_[A-Za-z0-9]{20,}\b/g, label: 'github-token' },
];

export interface RedactionCounter {
  headers: Map<string, number>;
  queryParams: Map<string, number>;
  bodyFields: Map<string, number>;
  valuePatterns: Map<string, number>;
}

export function createRedactionCounter(): RedactionCounter {
  return {
    headers: new Map(),
    queryParams: new Map(),
    bodyFields: new Map(),
    valuePatterns: new Map(),
  };
}

function bumpCounter(map: Map<string, number>, key: string): void {
  map.set(key, (map.get(key) ?? 0) + 1);
}

const sensitiveHeaderSet = new Set(SENSITIVE_HEADER_NAMES.map((name) => name.toLowerCase()));
const sensitiveQueryParamSet = new Set(SENSITIVE_QUERY_PARAM_NAMES.map((name) => name.toLowerCase()));
const sensitiveBodyFieldSet = new Set(SENSITIVE_BODY_FIELD_NAMES.map((name) => name.toLowerCase()));

export function isSensitiveHeader(name: string): boolean {
  return sensitiveHeaderSet.has(name.trim().toLowerCase());
}

export function isSensitiveQueryParam(name: string): boolean {
  return sensitiveQueryParamSet.has(name.trim().toLowerCase());
}

export function isSensitiveBodyField(name: string): boolean {
  return sensitiveBodyFieldSet.has(name.trim().toLowerCase());
}

export function redactValuePatterns(value: string, counter?: RedactionCounter): string {
  let result = value;
  for (const { pattern, label } of VALUE_PATTERNS) {
    result = result.replace(pattern, () => {
      if (counter) bumpCounter(counter.valuePatterns, label);
      return REDACTED_PLACEHOLDER;
    });
  }
  return result;
}

export interface NameValuePair {
  name: string;
  value: string;
}

export function redactHeaderPairs(
  headers: readonly NameValuePair[],
  counter: RedactionCounter,
): NameValuePair[] {
  return headers.map((header) => {
    const trimmedName = typeof header.name === 'string' ? header.name : '';
    const rawValue = typeof header.value === 'string' ? header.value : '';
    if (isSensitiveHeader(trimmedName)) {
      bumpCounter(counter.headers, trimmedName.toLowerCase());
      return { name: trimmedName, value: REDACTED_PLACEHOLDER };
    }
    return { name: trimmedName, value: redactValuePatterns(rawValue, counter) };
  });
}

export function redactCookiePairs(
  cookies: readonly { name: string; value: string }[],
  counter: RedactionCounter,
): { name: string; value: string }[] {
  return cookies.map((cookie) => {
    const name = typeof cookie.name === 'string' ? cookie.name : '';
    bumpCounter(counter.headers, 'cookie');
    return { name, value: REDACTED_PLACEHOLDER };
  });
}

export interface RedactedUrl {
  url: string;
  queryParams: NameValuePair[];
}

export function redactUrl(rawUrl: string, counter: RedactionCounter): RedactedUrl {
  if (typeof rawUrl !== 'string' || rawUrl.length === 0) {
    return { url: '', queryParams: [] };
  }

  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    // Relative URLs or malformed strings: redact value patterns and preserve.
    return {
      url: redactValuePatterns(rawUrl, counter),
      queryParams: [],
    };
  }

  const redactedParams: NameValuePair[] = [];
  const replacementParams = new URLSearchParams();
  for (const [name, value] of parsed.searchParams.entries()) {
    if (isSensitiveQueryParam(name)) {
      bumpCounter(counter.queryParams, name.toLowerCase());
      redactedParams.push({ name, value: REDACTED_PLACEHOLDER });
      replacementParams.append(name, REDACTED_PLACEHOLDER);
    } else {
      const safeValue = redactValuePatterns(value, counter);
      redactedParams.push({ name, value: safeValue });
      replacementParams.append(name, safeValue);
    }
  }
  parsed.search = replacementParams.toString();
  // userinfo (user:password@host) is always sensitive.
  if (parsed.username || parsed.password) {
    if (parsed.password) bumpCounter(counter.queryParams, 'userinfo:password');
    if (parsed.username) bumpCounter(counter.queryParams, 'userinfo:username');
    parsed.username = '';
    parsed.password = '';
  }
  return { url: parsed.toString(), queryParams: redactedParams };
}

export function redactJsonValue(value: unknown, counter: RedactionCounter): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === 'string') {
    return redactValuePatterns(value, counter);
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactJsonValue(item, counter));
  }
  if (typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (isSensitiveBodyField(key)) {
        bumpCounter(counter.bodyFields, key.toLowerCase());
        result[key] = REDACTED_PLACEHOLDER;
      } else {
        result[key] = redactJsonValue(child, counter);
      }
    }
    return result;
  }
  return value;
}

export interface RedactedBody {
  mimeType: string | undefined;
  text: string | undefined;
  parsedJson?: unknown;
  encoding?: 'json' | 'form' | 'text' | 'binary' | 'empty';
}

export function redactBody(
  mimeType: string | undefined,
  rawText: string | undefined,
  counter: RedactionCounter,
): RedactedBody {
  if (rawText === undefined || rawText === null || rawText === '') {
    return { mimeType, text: undefined, encoding: 'empty' };
  }
  const lowerMime = (mimeType ?? '').toLowerCase();

  // JSON
  if (lowerMime.includes('json') || looksLikeJson(rawText)) {
    try {
      const parsed = JSON.parse(rawText);
      const redacted = redactJsonValue(parsed, counter);
      return {
        mimeType,
        text: JSON.stringify(redacted),
        parsedJson: redacted,
        encoding: 'json',
      };
    } catch {
      // fall through to text handling
    }
  }

  // application/x-www-form-urlencoded
  if (lowerMime.includes('x-www-form-urlencoded')) {
    const params = new URLSearchParams(rawText);
    const out = new URLSearchParams();
    for (const [name, value] of params.entries()) {
      if (isSensitiveBodyField(name) || isSensitiveQueryParam(name)) {
        bumpCounter(counter.bodyFields, name.toLowerCase());
        out.append(name, REDACTED_PLACEHOLDER);
      } else {
        out.append(name, redactValuePatterns(value, counter));
      }
    }
    return { mimeType, text: out.toString(), encoding: 'form' };
  }

  // multipart and binary content: drop body, keep mime type only.
  if (lowerMime.startsWith('multipart/') || isLikelyBinaryMime(lowerMime)) {
    bumpCounter(counter.bodyFields, '__binary_or_multipart_dropped');
    return { mimeType, text: undefined, encoding: 'binary' };
  }

  // Plain text or unknown: scrub known token patterns.
  return { mimeType, text: redactValuePatterns(rawText, counter), encoding: 'text' };
}

function looksLikeJson(value: string): boolean {
  const trimmed = value.trim();
  if (trimmed.length === 0) return false;
  const first = trimmed.charAt(0);
  return first === '{' || first === '[';
}

function isLikelyBinaryMime(mime: string): boolean {
  if (mime.length === 0) return false;
  return (
    mime.startsWith('image/') ||
    mime.startsWith('audio/') ||
    mime.startsWith('video/') ||
    mime.startsWith('font/') ||
    mime === 'application/octet-stream' ||
    mime === 'application/pdf' ||
    mime === 'application/zip'
  );
}

export interface RedactionReport {
  totalRedactions: number;
  redactedHeaders: { name: string; count: number }[];
  redactedQueryParams: { name: string; count: number }[];
  redactedBodyFields: { name: string; count: number }[];
  redactedValuePatterns: { name: string; count: number }[];
}

export function summarizeRedactions(counter: RedactionCounter): RedactionReport {
  const sortEntries = (map: Map<string, number>) =>
    [...map.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

  const headers = sortEntries(counter.headers);
  const queryParams = sortEntries(counter.queryParams);
  const bodyFields = sortEntries(counter.bodyFields);
  const valuePatterns = sortEntries(counter.valuePatterns);
  const total =
    headers.reduce((acc, e) => acc + e.count, 0) +
    queryParams.reduce((acc, e) => acc + e.count, 0) +
    bodyFields.reduce((acc, e) => acc + e.count, 0) +
    valuePatterns.reduce((acc, e) => acc + e.count, 0);

  return {
    totalRedactions: total,
    redactedHeaders: headers,
    redactedQueryParams: queryParams,
    redactedBodyFields: bodyFields,
    redactedValuePatterns: valuePatterns,
  };
}
