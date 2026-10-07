import * as https from 'https';
import * as http from 'http';
import { URL } from 'url';
import { isOfficialOpenAiBaseUrl } from '../aiCli/officialEndpoints';
import { readCodexSubscriptionSession } from './codexSettings';

export type ProviderUsagePlan = {
  name: string;
  remaining: string;
  used?: string;
  unit?: string;
};

export type ProviderUsageResult = {
  ok: boolean;
  template?: string;
  summary?: string;
  plans?: ProviderUsagePlan[];
  error?: string;
  unsupported?: boolean;
};

const USAGE_TIMEOUT_MS = 12_000;

function fetchJson(url: string, headers: Record<string, string>): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const transport = parsed.protocol === 'https:' ? https : http;
    const req = transport.request(
      parsed,
      { method: 'GET', headers, timeout: USAGE_TIMEOUT_MS },
      (res) => {
        const chunks: Buffer[] = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => {
          const text = Buffer.concat(chunks).toString('utf-8');
          if ((res.statusCode ?? 0) >= 400) {
            reject(new Error(`http_${res.statusCode}: ${text.slice(0, 200)}`));
            return;
          }
          try {
            resolve(JSON.parse(text));
          } catch {
            reject(new Error('invalid_json'));
          }
        });
      }
    );
    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error('timeout'));
    });
    req.end();
  });
}

function authHeader(apiKey: string): Record<string, string> {
  const token = apiKey.trim();
  if (token.toLowerCase().startsWith('bearer ')) {
    return { Authorization: token };
  }
  return { Authorization: `Bearer ${token}` };
}

function isHostnameOrSuffix(host: string, domain: string): boolean {
  return host === domain || host.endsWith('.' + domain);
}

function detectTemplate(baseUrl: string): string | null {
  let host: string;
  try {
    host = new URL(baseUrl).hostname.toLowerCase();
  } catch {
    host = baseUrl.toLowerCase();
  }
  if (isHostnameOrSuffix(host, 'open.bigmodel.cn') || isHostnameOrSuffix(host, 'bigmodel.cn')) {
    return 'zhipu';
  }
  if (isHostnameOrSuffix(host, 'api.deepseek.com') || isHostnameOrSuffix(host, 'deepseek.com')) {
    return 'deepseek';
  }
  if (isHostnameOrSuffix(host, 'openrouter.ai')) {
    return 'openrouter';
  }
  if (isHostnameOrSuffix(host, 'api.siliconflow.cn') || isHostnameOrSuffix(host, 'siliconflow.cn')) {
    return 'siliconflow';
  }
  return null;
}

async function queryZhipu(apiKey: string): Promise<ProviderUsageResult> {
  const data = (await fetchJson('https://open.bigmodel.cn/api/monitor/usage/quota/limit', {
    ...authHeader(apiKey),
    'Content-Type': 'application/json',
  })) as {
    success?: boolean;
    msg?: string;
    data?: {
      level?: string;
      limits?: Array<{
        type?: string;
        percentage?: number;
        remaining?: number;
        usage?: number;
        currentValue?: number;
        nextResetTime?: number;
      }>;
    };
  };
  if (!data.success || !data.data?.limits) {
    return { ok: false, template: 'zhipu', error: data.msg ?? 'query_failed' };
  }
  const limits = data.data.limits;
  const tokenLimits = limits.filter((l) => l.type === 'TOKENS_LIMIT');
  const plans: ProviderUsagePlan[] = [];
  if (tokenLimits[0]) {
    const p = tokenLimits[0].percentage ?? 0;
    plans.push({
      name: '5小时额度',
      remaining: `${Math.max(0, 100 - p).toFixed(0)}%`,
      used: `${p.toFixed(0)}%`,
      unit: '%',
    });
  }
  if (tokenLimits[1]) {
    const p = tokenLimits[1].percentage ?? 0;
    plans.push({
      name: '每周额度',
      remaining: `${Math.max(0, 100 - p).toFixed(0)}%`,
      used: `${p.toFixed(0)}%`,
      unit: '%',
    });
  }
  const mcp = limits.find((l) => l.type === 'TIME_LIMIT');
  if (mcp) {
    plans.push({
      name: 'MCP 每月',
      remaining: String(mcp.remaining ?? 0),
      used: String(mcp.currentValue ?? 0),
      unit: '次',
    });
  }
  const summary = plans.map((p) => `${p.name} 余${p.remaining}`).join(' · ');
  return { ok: true, template: 'zhipu', plans, summary };
}

async function queryDeepseek(apiKey: string): Promise<ProviderUsageResult> {
  const data = (await fetchJson('https://api.deepseek.com/user/balance', {
    ...authHeader(apiKey),
    Accept: 'application/json',
  })) as {
    is_available?: boolean;
    balance_infos?: Array<{ currency?: string; total_balance?: string }>;
  };
  const infos = data.balance_infos ?? [];
  if (infos.length === 0) {
    return { ok: false, template: 'deepseek', error: 'empty_balance' };
  }
  const parts = infos.map((i) => `${i.total_balance ?? '?'} ${i.currency ?? ''}`.trim());
  return {
    ok: true,
    template: 'deepseek',
    summary: parts.join(' · '),
    plans: infos.map((i, idx) => ({
      name: i.currency ?? `账户${idx + 1}`,
      remaining: i.total_balance ?? '—',
      unit: i.currency,
    })),
  };
}

async function queryOpenRouter(apiKey: string): Promise<ProviderUsageResult> {
  const data = (await fetchJson('https://openrouter.ai/api/v1/auth/key', {
    ...authHeader(apiKey),
    Accept: 'application/json',
  })) as {
    data?: {
      label?: string;
      limit?: number | null;
      usage?: number;
      limit_remaining?: number | null;
      is_free_tier?: boolean;
    };
  };
  const d = data.data;
  if (!d) {
    return { ok: false, template: 'openrouter', error: 'empty_response' };
  }
  const remaining =
    typeof d.limit_remaining === 'number'
      ? `$${d.limit_remaining.toFixed(2)}`
      : typeof d.limit === 'number'
        ? `$${Math.max(0, d.limit - (d.usage ?? 0)).toFixed(2)}`
        : '—';
  const summary =
    typeof d.limit === 'number'
      ? `剩余 ${remaining} / 额度 $${d.limit.toFixed(2)}`
      : `已用 $${(d.usage ?? 0).toFixed(2)}`;
  return {
    ok: true,
    template: 'openrouter',
    summary,
    plans: [{ name: d.label ?? 'API Key', remaining, used: `$${(d.usage ?? 0).toFixed(2)}`, unit: 'USD' }],
  };
}

async function querySiliconFlow(apiKey: string): Promise<ProviderUsageResult> {
  const data = (await fetchJson('https://api.siliconflow.cn/v1/user/info', {
    ...authHeader(apiKey),
    Accept: 'application/json',
  })) as {
    data?: { balance?: string; charge_balance?: string };
  };
  const balance = data.data?.balance ?? data.data?.charge_balance;
  if (balance === undefined || balance === null) {
    return { ok: false, template: 'siliconflow', error: 'empty_balance' };
  }
  return {
    ok: true,
    template: 'siliconflow',
    summary: `余额 ${balance}`,
    plans: [{ name: '账户余额', remaining: String(balance), unit: 'CNY' }],
  };
}

type RateLimitWindowPayload = {
  used_percent?: number;
  limit_window_seconds?: number;
  reset_at?: number;
};

function windowLabel(seconds: number | undefined, fallback: string): string {
  if (seconds === undefined || seconds <= 0) {
    return fallback;
  }
  const minutes = Math.round(seconds / 60);
  if (minutes >= 24 * 60) {
    return `${Math.round(minutes / (24 * 60))} 天窗口`;
  }
  if (minutes >= 60) {
    return `${Math.round(minutes / 60)} 小时窗口`;
  }
  return `${minutes} 分钟窗口`;
}

function formatRateLimitWindow(
  window: RateLimitWindowPayload | null | undefined,
  fallbackName: string
): ProviderUsagePlan | null {
  if (!window || window.used_percent === undefined) {
    return null;
  }
  const used = window.used_percent;
  const remaining = Math.max(0, 100 - used);
  const name = windowLabel(window.limit_window_seconds, fallbackName);
  return {
    name,
    remaining: `${remaining.toFixed(0)}%`,
    used: `${used.toFixed(0)}%`,
    unit: '%',
  };
}

async function queryCodexSubscriptionUsage(): Promise<ProviderUsageResult> {
  const session = readCodexSubscriptionSession();
  if (!session) {
    return { ok: false, template: 'codex_subscription', error: 'codex_not_logged_in' };
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.accessToken}`,
    Accept: 'application/json',
    'User-Agent': 'codex-cli',
  };
  if (session.accountId) {
    headers['ChatGPT-Account-Id'] = session.accountId;
  }
  const data = (await fetchJson('https://chatgpt.com/backend-api/wham/usage', headers)) as {
    rate_limit?: {
      primary_window?: RateLimitWindowPayload | null;
      secondary_window?: RateLimitWindowPayload | null;
    } | null;
    additional_rate_limits?: Array<{
      limit_name?: string | null;
      rate_limit?: {
        primary_window?: RateLimitWindowPayload | null;
        secondary_window?: RateLimitWindowPayload | null;
      } | null;
    }> | null;
  };
  const primary = formatRateLimitWindow(data.rate_limit?.primary_window, '短期额度');
  const secondary = formatRateLimitWindow(data.rate_limit?.secondary_window, '长期额度');
  const plans = [primary, secondary].filter((p): p is ProviderUsagePlan => p !== null);
  if (plans.length === 0) {
    const codexExtra = data.additional_rate_limits?.find((item) => item.limit_name === 'codex');
    const extraPrimary = formatRateLimitWindow(
      codexExtra?.rate_limit?.primary_window,
      'Codex 短期'
    );
    const extraSecondary = formatRateLimitWindow(
      codexExtra?.rate_limit?.secondary_window,
      'Codex 长期'
    );
    if (extraPrimary) {
      plans.push(extraPrimary);
    }
    if (extraSecondary) {
      plans.push(extraSecondary);
    }
  }
  if (plans.length === 0) {
    return { ok: false, template: 'codex_subscription', error: 'empty_quota' };
  }
  const summary = plans.map((p) => `${p.name} 余 ${p.remaining}`).join(' · ');
  return { ok: true, template: 'codex_subscription', plans, summary };
}

export type ProviderUsageQueryOptions = {
  baseUrl: string;
  apiKey?: string;
  authMode?: 'subscription' | 'api';
  apiKind?: 'anthropic' | 'openai';
};

export function supportsProviderUsageQuery(
  baseUrl: string,
  options?: Pick<ProviderUsageQueryOptions, 'authMode' | 'apiKind'>
): boolean {
  if (
    options?.apiKind === 'openai' &&
    options.authMode === 'subscription' &&
    isOfficialOpenAiBaseUrl(baseUrl)
  ) {
    return true;
  }
  return detectTemplate(baseUrl) !== null;
}

export async function queryProviderUsage(
  baseUrl: string,
  apiKey: string,
  options?: Pick<ProviderUsageQueryOptions, 'authMode' | 'apiKind'>
): Promise<ProviderUsageResult> {
  if (
    options?.apiKind === 'openai' &&
    options.authMode === 'subscription' &&
    isOfficialOpenAiBaseUrl(baseUrl)
  ) {
    try {
      return await queryCodexSubscriptionUsage();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, template: 'codex_subscription', error: message };
    }
  }
  const template = detectTemplate(baseUrl);
  if (!template) {
    return { ok: false, unsupported: true, error: 'unsupported_provider' };
  }
  if (!apiKey.trim()) {
    return { ok: false, error: 'missing_api_key' };
  }
  try {
    switch (template) {
      case 'zhipu':
        return await queryZhipu(apiKey);
      case 'deepseek':
        return await queryDeepseek(apiKey);
      case 'openrouter':
        return await queryOpenRouter(apiKey);
      case 'siliconflow':
        return await querySiliconFlow(apiKey);
      default:
        return { ok: false, unsupported: true, error: 'unsupported_provider' };
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, template, error: message };
  }
}
