import { normalizeUpstreamBaseUrl } from './aiCliGatewayUpstream';

const CODEX_MODEL_BY_HOST: Array<{ pattern: RegExp; model: string }> = [
  { pattern: /open\.bigmodel\.cn/i, model: 'glm-5.2' },
  { pattern: /api\.z\.ai/i, model: 'glm-5.2' },
  { pattern: /api\.kimi\.com/i, model: 'kimi-for-coding' },
  { pattern: /api\.deepseek\.com/i, model: 'deepseek-chat' },
  { pattern: /minimax/i, model: 'MiniMax-M3' },
  { pattern: /xiaomimimo\.com/i, model: 'mimo-v2.5-pro' },
  { pattern: /longcat\.chat/i, model: 'LongCat-2.0-Preview' },
  { pattern: /dashscope\.aliyuncs\.com/i, model: 'qwen-plus' },
  { pattern: /moonshot\.(cn|ai)/i, model: 'kimi-k2.7-code' },
  { pattern: /siliconflow\.cn/i, model: 'Pro/deepseek-ai/DeepSeek-V4' },
  { pattern: /openrouter\.ai/i, model: 'openai/gpt-5.5' },
];

const CODEX_PLACEHOLDER_MODEL = /^gpt-|^o\d|codex/i;

export function inferCodexModelFromBaseUrl(baseUrl: string): string | undefined {
  const host = baseUrl.trim().toLowerCase();
  if (!host) {
    return undefined;
  }
  for (const entry of CODEX_MODEL_BY_HOST) {
    if (entry.pattern.test(host)) {
      return entry.model;
    }
  }
  return undefined;
}

export function isCodexPlaceholderModel(model: string): boolean {
  const id = model.trim();
  return !id || CODEX_PLACEHOLDER_MODEL.test(id);
}

export function resolveCodexChatModel(
  requestModel: unknown,
  upstream: { baseUrl: string; codexModel?: string; codexApiFormat?: 'openai_responses' | 'openai_chat' }
): string {
  const configured = upstream.codexModel?.trim();
  const requested = typeof requestModel === 'string' ? requestModel.trim() : '';
  const inferred = inferCodexModelFromBaseUrl(normalizeUpstreamBaseUrl(upstream.baseUrl));
  if (configured) {
    return isCodexPlaceholderModel(configured) && inferred ? inferred : configured;
  }
  if (upstream.codexApiFormat === 'openai_chat' && isCodexPlaceholderModel(requested)) {
    // Only remap gpt-*/codex placeholders when the host has an explicit vendor default.
    // Do not invent a Zhipu/GLM model for unrelated providers.
    return inferred ?? requested;
  }
  return requested || inferred || '';
}
