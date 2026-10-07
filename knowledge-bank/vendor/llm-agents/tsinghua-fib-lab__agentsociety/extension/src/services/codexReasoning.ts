type JsonObject = Record<string, unknown>;

const VALID_EFFORTS = new Set(['minimal', 'low', 'medium', 'high', 'xhigh']);
const DISABLED_EFFORTS = new Set(['none', 'off', 'disabled']);

function readEffort(reasoning: unknown): string | undefined {
  if (!reasoning || typeof reasoning !== 'object' || Array.isArray(reasoning)) {
    return undefined;
  }
  const effort = (reasoning as JsonObject).effort;
  if (typeof effort !== 'string') {
    return undefined;
  }
  const normalized = effort.trim().toLowerCase();
  if (normalized === 'max') {
    return 'xhigh';
  }
  if (VALID_EFFORTS.has(normalized) || DISABLED_EFFORTS.has(normalized)) {
    return normalized;
  }
  return undefined;
}

function hostname(baseUrl: string): string {
  try {
    return new URL(baseUrl).hostname.toLowerCase();
  } catch {
    return '';
  }
}

function isDomainOrSubdomain(host: string, domain: string): boolean {
  return host === domain || host.endsWith(`.${domain}`);
}

export function mapCodexReasoningToChat(
  reasoning: unknown,
  upstreamBaseUrl: string,
  model: string
): JsonObject {
  const effort = readEffort(reasoning);
  if (!effort) {
    return {};
  }
  const disabled = DISABLED_EFFORTS.has(effort);
  const host = hostname(upstreamBaseUrl);

  if (host === 'openrouter.ai') {
    return { reasoning: { effort: disabled ? 'none' : effort } };
  }
  if (host === 'api.deepseek.com') {
    return disabled
      ? { thinking: { type: 'disabled' } }
      : {
          thinking: { type: 'enabled' },
          reasoning_effort: effort === 'xhigh' ? 'max' : 'high',
        };
  }
  if (
    isDomainOrSubdomain(host, 'bigmodel.cn') ||
    host === 'api.z.ai' ||
    isDomainOrSubdomain(host, 'kimi.com') ||
    isDomainOrSubdomain(host, 'xiaomimimo.com')
  ) {
    return { thinking: { type: disabled ? 'disabled' : 'enabled' } };
  }
  if (
    isDomainOrSubdomain(host, 'dashscope.aliyuncs.com') ||
    isDomainOrSubdomain(host, 'siliconflow.cn')
  ) {
    return { enable_thinking: !disabled };
  }
  if (
    isDomainOrSubdomain(host, 'minimaxi.com') ||
    isDomainOrSubdomain(host, 'minimax.io')
  ) {
    return { reasoning_split: !disabled };
  }
  if (/^(o\d|gpt-[5-9])/i.test(model)) {
    return disabled ? {} : { reasoning_effort: effort };
  }
  return {};
}
