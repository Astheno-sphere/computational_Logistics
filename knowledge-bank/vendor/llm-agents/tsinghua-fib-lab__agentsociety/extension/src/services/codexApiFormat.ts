import { isOfficialOpenAiBaseUrl } from '../aiCli/officialEndpoints';
import { inferCodexWireFromBaseUrl } from '../aiCli/providerPresets';
import { normalizeUpstreamBaseUrl } from './aiCliGatewayUpstream';

export type OpenAiApiFormat = 'openai_responses' | 'openai_chat';

export function inferOpenAiApiFormat(baseUrl: string): OpenAiApiFormat {
  if (isOfficialOpenAiBaseUrl(baseUrl)) {
    return 'openai_responses';
  }
  return inferCodexWireFromBaseUrl(baseUrl);
}

export function isCodexResponsesPath(urlPath: string): boolean {
  const path = urlPath.split('?')[0] ?? urlPath;
  return (
    path === '/responses' ||
    path === '/v1/responses' ||
    path === '/responses/compact' ||
    path === '/v1/responses/compact' ||
    path.endsWith('/responses') ||
    path.endsWith('/responses/compact')
  );
}

export function resolveChatCompletionsTargetUrl(upstreamBase: string): string {
  const base = normalizeUpstreamBaseUrl(upstreamBase);
  const suffix = '/chat/completions';
  if (base.endsWith('/v1')) {
    return `${base}${suffix}`;
  }
  if (/\/v\d+$/i.test(base)) {
    return `${base}${suffix}`;
  }
  return `${base}/v1${suffix}`;
}
