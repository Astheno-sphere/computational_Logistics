import {
  inferApiKindFromBaseUrl,
  isOfficialAnthropicBaseUrl,
  isOfficialOpenAiBaseUrl,
  resolveProviderBaseUrl,
  type AiCliApiKind,
} from '../aiCli/officialEndpoints';
import { OFFICIAL_ANTHROPIC_MODELS, OFFICIAL_OPENAI_MODELS } from './officialBuiltinModels';
import { findPresetByUrl, mergeModelOptions } from '../aiCli/providerPresets';
import { requestJson, type JsonResponse } from './httpClient';

export type ClaudeModelOption = {
  id: string;
  label?: string;
};

export type FetchClaudeModelsResult =
  | { ok: true; models: ClaudeModelOption[]; apiKind: AiCliApiKind }
  | { ok: false; error: string; status?: number; detail?: string };

type ModelRow = {
  id?: string;
  name?: string;
  display_name?: string;
};

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

export function buildClaudeModelsUrl(baseUrl: string): string {
  const base = normalizeBaseUrl(baseUrl);
  if (base.endsWith('/v1')) {
    return `${base}/models`;
  }
  return `${base}/v1/models`;
}

export function buildOpenAiModelsUrl(baseUrl: string): string {
  const base = normalizeBaseUrl(baseUrl);
  if (/\/v\d+$/.test(base)) {
    return `${base}/models`;
  }
  if (base.endsWith('/v1')) {
    return `${base}/models`;
  }
  return `${base}/v1/models`;
}

export function parseClaudeModelsResponse(body: unknown): ClaudeModelOption[] {
  if (!body || typeof body !== 'object') {
    return [];
  }
  const record = body as Record<string, unknown>;
  let rows: ModelRow[] = [];
  if (Array.isArray(record.data)) {
    rows = record.data as ModelRow[];
  } else if (Array.isArray(record.models)) {
    rows = record.models as ModelRow[];
  } else if (Array.isArray(body)) {
    rows = body as ModelRow[];
  }
  const seen = new Set<string>();
  const models: ClaudeModelOption[] = [];
  for (const row of rows) {
    const id = (row.id ?? row.name ?? '').trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    const display = (row.display_name ?? '').trim();
    models.push(display && display !== id ? { id, label: display } : { id });
  }
  models.sort((a, b) => {
    const aClaude = /claude/i.test(a.id) ? 0 : 1;
    const bClaude = /claude/i.test(b.id) ? 0 : 1;
    if (aClaude !== bClaude) {
      return aClaude - bClaude;
    }
    return a.id.localeCompare(b.id);
  });
  return models;
}

function authHeaderSets(apiKey: string): Record<string, string>[] {
  const token = apiKey.trim();
  return [
    {
      Authorization: `Bearer ${token}`,
      'anthropic-version': '2023-06-01',
      Accept: 'application/json',
    },
    {
      'x-api-key': token,
      'anthropic-version': '2023-06-01',
      Accept: 'application/json',
    },
    {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  ];
}

async function fetchOnce(
  url: string,
  headers: Record<string, string>
): Promise<JsonResponse<unknown>> {
  return requestJson(url, {
    method: 'GET',
    headers,
    timeoutMs: 12_000,
    fallbackToNodeOnFetchError: true,
  });
}

export async function fetchProviderModels(
  baseUrl: string,
  apiKey: string,
  apiKind?: AiCliApiKind
): Promise<FetchClaudeModelsResult> {
  if (!apiKind) {
    return fetchProviderModelsAuto(baseUrl, apiKey);
  }
  if (apiKind === 'openai') {
    return fetchOpenAiCompatibleModels(baseUrl, apiKey);
  }
  return fetchClaudeCompatibleModels(baseUrl, apiKey);
}

export async function fetchProviderModelsAuto(
  baseUrl: string,
  apiKey: string
): Promise<FetchClaudeModelsResult> {
  const inferred = inferApiKindFromBaseUrl(baseUrl);
  const first = await fetchProviderModels(baseUrl, apiKey, inferred);
  if (first.ok) {
    return first;
  }
  const second = await fetchProviderModels(
    baseUrl,
    apiKey,
    inferred === 'openai' ? 'anthropic' : 'openai'
  );
  if (second.ok) {
    return second;
  }
  return first.error === 'auth_failed' ? first : second;
}

export async function fetchOpenAiCompatibleModels(
  baseUrl: string,
  apiKey: string
): Promise<FetchClaudeModelsResult> {
  const base = normalizeBaseUrl(resolveProviderBaseUrl(baseUrl, 'openai'));
  const key = apiKey.trim();
  if (!key) {
    return { ok: false, error: 'missing_api_key' };
  }
  if (isOfficialOpenAiBaseUrl(base)) {
    return { ok: true, models: [...OFFICIAL_OPENAI_MODELS], apiKind: 'openai' };
  }

  const url = buildOpenAiModelsUrl(base);
  let lastStatus: number | undefined;
  let lastError = 'request_failed';
  let lastDetail: string | undefined;

  for (const headers of [
    { Authorization: `Bearer ${key}`, Accept: 'application/json' },
  ]) {
    try {
      const response = await fetchOnce(url, headers);
      lastStatus = response.status;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          lastError = 'auth_failed';
          continue;
        }
        if (response.status === 404) {
          const preset = findPresetByUrl(base);
          if (preset?.modelHints?.length) {
            return {
              ok: true,
              models: mergeModelOptions(preset.modelHints, base, 'openai'),
              apiKind: 'openai',
            };
          }
          return { ok: true, models: [...OFFICIAL_OPENAI_MODELS], apiKind: 'openai' };
        }
        lastError = 'http_error';
        continue;
      }
      const body = (await response.json()) as unknown;
      const models = parseClaudeModelsResponse(body);
      if (models.length === 0) {
        lastError = 'empty_list';
        continue;
      }
      return {
        ok: true,
        models: mergeModelOptions(models, base, 'openai'),
        apiKind: 'openai',
      };
    } catch (err) {
      if (
        err instanceof Error &&
        (err.name === 'AbortError' || err.message.includes('请求超时'))
      ) {
        return { ok: false, error: 'timeout', status: lastStatus, detail: err.message };
      }
      lastError = 'network_error';
      lastDetail = err instanceof Error ? err.message : String(err);
    }
  }

  return { ok: false, error: lastError, status: lastStatus, detail: lastDetail };
}

export async function fetchClaudeCompatibleModels(
  baseUrl: string,
  apiKey: string
): Promise<FetchClaudeModelsResult> {
  const base = normalizeBaseUrl(resolveProviderBaseUrl(baseUrl, 'anthropic'));
  const key = apiKey.trim();
  if (!key) {
    return { ok: false, error: 'missing_api_key' };
  }

  const url = buildClaudeModelsUrl(base);
  let lastStatus: number | undefined;
  let lastError = 'request_failed';
  let lastDetail: string | undefined;

  for (const headers of authHeaderSets(key)) {
    try {
      const response = await fetchOnce(url, headers);
      lastStatus = response.status;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          lastError = 'auth_failed';
          continue;
        }
        if (response.status === 404) {
          const preset = findPresetByUrl(base);
          if (preset?.modelHints?.length) {
            return {
              ok: true,
              models: mergeModelOptions(preset.modelHints, base, 'anthropic'),
              apiKind: 'anthropic',
            };
          }
          lastError = 'models_not_supported';
          continue;
        }
        lastError = 'http_error';
        continue;
      }
      const body = (await response.json()) as unknown;
      const models = parseClaudeModelsResponse(body);
      if (models.length === 0) {
        lastError = 'empty_list';
        continue;
      }
      return {
        ok: true,
        models: mergeModelOptions(models, base, 'anthropic'),
        apiKind: 'anthropic',
      };
    } catch (err) {
      if (
        err instanceof Error &&
        (err.name === 'AbortError' || err.message.includes('请求超时'))
      ) {
        return { ok: false, error: 'timeout', status: lastStatus, detail: err.message };
      }
      lastError = 'network_error';
      lastDetail = err instanceof Error ? err.message : String(err);
    }
  }

  if (
    (lastError === 'models_not_supported' || lastError === 'http_error' || lastError === 'request_failed') &&
    isOfficialAnthropicBaseUrl(base)
  ) {
    return { ok: true, models: [...OFFICIAL_ANTHROPIC_MODELS], apiKind: 'anthropic' };
  }

  return { ok: false, error: lastError, status: lastStatus, detail: lastDetail };
}

export function suggestClaudeModelByRole(
  models: ClaudeModelOption[],
  role: 'sonnet' | 'opus' | 'fable' | 'haiku'
): string | undefined {
  const pattern =
    role === 'sonnet'
      ? /sonnet/i
      : role === 'opus'
        ? /opus/i
        : role === 'fable'
          ? /fable/i
          : /haiku/i;
  const match = models.find((m) => pattern.test(m.id) || (m.label && pattern.test(m.label)));
  return match?.id;
}

export function suggestClaudeModelMappings(
  models: ClaudeModelOption[]
): Partial<Record<'model' | 'sonnetModel' | 'opusModel' | 'fableModel' | 'haikuModel', string>> {
  const ids = models.map((m) => m.id);
  if (ids.length === 0) {
    return {};
  }
  const sonnet = suggestClaudeModelByRole(models, 'sonnet');
  const opus = suggestClaudeModelByRole(models, 'opus');
  const fable = suggestClaudeModelByRole(models, 'fable');
  const haiku = suggestClaudeModelByRole(models, 'haiku');
  const fallback = sonnet ?? opus ?? ids[0];
  return {
    model: fallback,
    sonnetModel: sonnet ?? fallback,
    opusModel: opus ?? fallback,
    fableModel: fable ?? opus ?? fallback,
    haikuModel: haiku ?? fallback,
  };
}
