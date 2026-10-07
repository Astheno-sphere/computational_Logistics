export type AiCliAuthHeaderMode = 'auto' | 'bearer' | 'x-api-key' | 'both';

export type ResolvedAuthHeaderMode = Exclude<AiCliAuthHeaderMode, 'auto'>;

function isOpenAiHostname(hostname: string): boolean {
  return (
    hostname === 'api.openai.com' ||
    hostname.endsWith('.api.openai.com') ||
    hostname === 'openai.com' ||
    hostname.endsWith('.openai.com')
  );
}

function isAnthropicHostname(hostname: string): boolean {
  return (
    hostname === 'api.anthropic.com' ||
    hostname.endsWith('.api.anthropic.com') ||
    hostname === 'anthropic.com' ||
    hostname.endsWith('.anthropic.com')
  );
}

function hostnameOf(upstreamBaseUrl: string): string {
  try {
    return new URL(upstreamBaseUrl).hostname.toLowerCase();
  } catch {
    return upstreamBaseUrl.toLowerCase();
  }
}

/**
 * Resolve outbound auth header strategy.
 *
 * `auto` preserves historical gateway behavior:
 * - OpenAI hosts → Bearer only
 * - Anthropic hosts, or requests that already carry `anthropic-version` → Bearer + x-api-key
 * - otherwise → Bearer only
 */
export function resolveAuthHeaderMode(params: {
  mode?: AiCliAuthHeaderMode;
  upstreamBaseUrl: string;
  requestHeaders: Record<string, string>;
}): ResolvedAuthHeaderMode {
  if (params.mode && params.mode !== 'auto') {
    return params.mode;
  }
  const host = hostnameOf(params.upstreamBaseUrl);
  if (isOpenAiHostname(host)) {
    return 'bearer';
  }
  if (isAnthropicHostname(host) || params.requestHeaders['anthropic-version'] !== undefined) {
    return 'both';
  }
  return 'bearer';
}

/**
 * Inject authentication headers for the upstream API.
 *
 * When `mode` is omitted or `auto`, behavior matches the previous gateway defaults.
 */
export function applyUpstreamAuthHeaders(
  headers: Record<string, string>,
  apiKey: string,
  options: {
    upstreamBaseUrl: string;
    mode?: AiCliAuthHeaderMode;
  }
): void {
  const token = apiKey.trim();
  delete headers['x-upstream-base'];
  if (!token) {
    return;
  }

  const mode = resolveAuthHeaderMode({
    mode: options.mode,
    upstreamBaseUrl: options.upstreamBaseUrl,
    requestHeaders: headers,
  });
  const host = hostnameOf(options.upstreamBaseUrl);

  if (mode === 'bearer' || mode === 'both') {
    headers.authorization = `Bearer ${token}`;
  } else {
    delete headers.authorization;
  }

  if (mode === 'x-api-key' || mode === 'both') {
    headers['x-api-key'] = token;
    if (
      (isAnthropicHostname(host) || headers['anthropic-version'] !== undefined) &&
      !headers['anthropic-version']
    ) {
      headers['anthropic-version'] = '2023-06-01';
    }
  } else {
    delete headers['x-api-key'];
  }
}
