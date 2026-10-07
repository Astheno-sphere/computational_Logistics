export type ModelPrice = {
  inputPerMillion: number;
  outputPerMillion: number;
  cacheReadPerMillion?: number;
  cacheCreationPerMillion?: number;
};

export type ModelPricingMap = Record<string, ModelPrice>;

const BUILTIN_PRICING: ModelPricingMap = {
  'claude-sonnet-4-6': { inputPerMillion: 3, outputPerMillion: 15, cacheReadPerMillion: 0.6, cacheCreationPerMillion: 3 },
  'claude-sonnet-4-5': { inputPerMillion: 3, outputPerMillion: 15, cacheReadPerMillion: 0.3, cacheCreationPerMillion: 3.75 },
  'claude-sonnet-4': { inputPerMillion: 3, outputPerMillion: 15, cacheReadPerMillion: 0.3, cacheCreationPerMillion: 3.75 },
  'claude-haiku-4-5': { inputPerMillion: 1, outputPerMillion: 5, cacheReadPerMillion: 0.2, cacheCreationPerMillion: 1 },
  'claude-opus-4-6': { inputPerMillion: 5, outputPerMillion: 25, cacheReadPerMillion: 1, cacheCreationPerMillion: 5 },
  'claude-opus-4-5': { inputPerMillion: 5, outputPerMillion: 25, cacheReadPerMillion: 0.5, cacheCreationPerMillion: 6.25 },
  'claude-opus-4': { inputPerMillion: 15, outputPerMillion: 75, cacheReadPerMillion: 1.5, cacheCreationPerMillion: 18.75 },
  'claude-3-7-sonnet': { inputPerMillion: 3, outputPerMillion: 15, cacheReadPerMillion: 0.3, cacheCreationPerMillion: 3.75 },
  'claude-3-5-sonnet': { inputPerMillion: 3, outputPerMillion: 15, cacheReadPerMillion: 0.3, cacheCreationPerMillion: 3.75 },
  'claude-3-5-haiku': { inputPerMillion: 0.8, outputPerMillion: 4, cacheReadPerMillion: 0.08, cacheCreationPerMillion: 1 },
  'claude-3-opus': { inputPerMillion: 15, outputPerMillion: 75, cacheReadPerMillion: 1.5, cacheCreationPerMillion: 18.75 },
  'claude-3-haiku': { inputPerMillion: 0.25, outputPerMillion: 1.25, cacheReadPerMillion: 0.03, cacheCreationPerMillion: 0.3 },
  'gpt-5.5': { inputPerMillion: 5, outputPerMillion: 30, cacheReadPerMillion: 0.5 },
  'gpt-5.5-pro': { inputPerMillion: 30, outputPerMillion: 45, cacheReadPerMillion: 3 },
  'gpt-5.5-codex': { inputPerMillion: 3.5, outputPerMillion: 28, cacheReadPerMillion: 0.35 },
  'gpt-5.4': { inputPerMillion: 1.75, outputPerMillion: 14, cacheReadPerMillion: 0.175 },
  'gpt-5-codex': { inputPerMillion: 1.25, outputPerMillion: 10, cacheReadPerMillion: 0.125 },
  'gpt-5': { inputPerMillion: 1.25, outputPerMillion: 10, cacheReadPerMillion: 0.125 },
  'gpt-4o': { inputPerMillion: 2.5, outputPerMillion: 10, cacheReadPerMillion: 1.25 },
  'gpt-4o-mini': { inputPerMillion: 0.15, outputPerMillion: 0.6, cacheReadPerMillion: 0.075 },
  'gpt-4.1': { inputPerMillion: 2, outputPerMillion: 8, cacheReadPerMillion: 0.5 },
  'gpt-4.1-mini': { inputPerMillion: 0.4, outputPerMillion: 1.6, cacheReadPerMillion: 0.1 },
  'gpt-4.1-nano': { inputPerMillion: 0.1, outputPerMillion: 0.4, cacheReadPerMillion: 0.025 },
  'o3': { inputPerMillion: 2, outputPerMillion: 8, cacheReadPerMillion: 0.5 },
  'o3-mini': { inputPerMillion: 1.1, outputPerMillion: 4.4, cacheReadPerMillion: 0.55 },
  'o4-mini': { inputPerMillion: 1.1, outputPerMillion: 4.4, cacheReadPerMillion: 0.275 },
  'deepseek-chat': { inputPerMillion: 0.28, outputPerMillion: 0.42, cacheReadPerMillion: 0.028 },
  'deepseek-v4-pro': { inputPerMillion: 0.55, outputPerMillion: 2.19, cacheReadPerMillion: 0.14 },
  'deepseek-r2': { inputPerMillion: 0.55, outputPerMillion: 2.19, cacheReadPerMillion: 0.14 },
  'deepseek-reasoner': { inputPerMillion: 0.55, outputPerMillion: 2.19, cacheReadPerMillion: 0.14 },
  'gemini-2.5-pro': { inputPerMillion: 1.25, outputPerMillion: 10, cacheReadPerMillion: 0.31 },
  'gemini-2.5-flash': { inputPerMillion: 0.15, outputPerMillion: 0.6, cacheReadPerMillion: 0.04 },
  'gemini-2.0-flash': { inputPerMillion: 0.1, outputPerMillion: 0.4, cacheReadPerMillion: 0.025 },
  'glm-5.2': { inputPerMillion: 0.14, outputPerMillion: 0.56 },
  'glm-5.1': { inputPerMillion: 0.14, outputPerMillion: 0.56 },
  'qwen-plus': { inputPerMillion: 0.57, outputPerMillion: 2.28 },
  'qwen-turbo': { inputPerMillion: 0.11, outputPerMillion: 0.44 },
  'MiniMax-M3': { inputPerMillion: 0.30, outputPerMillion: 1.20 },
  'kimi-k2.7-code': { inputPerMillion: 0.55, outputPerMillion: 2.19 },
  'kimi-for-coding': { inputPerMillion: 0.55, outputPerMillion: 2.19 },
  'step-3.7-flash': { inputPerMillion: 0.57, outputPerMillion: 2.28 },
  'Pro/deepseek-ai/DeepSeek-V4': { inputPerMillion: 0.28, outputPerMillion: 0.42 },
};

function normalizeModelId(modelId: string): string {
  let id = modelId.trim();
  const lastSlash = id.lastIndexOf('/');
  if (lastSlash >= 0) {
    id = id.slice(lastSlash + 1);
  }
  const colonIdx = id.indexOf(':');
  if (colonIdx >= 0) {
    id = id.slice(0, colonIdx);
  }
  id = id.replace(/@/g, '-');
  return id
    .toLowerCase()
    .replace(/\[1m\]$/, '')
    .replace(/-(?:19|20)\d{2}-\d{2}-\d{2}$/, '')
    .replace(/-(?:19|20)\d{6}$/, '');
}

export function getModelPrice(modelId: string, customPricing?: ModelPricingMap): ModelPrice | null {
  const normalized = normalizeModelId(modelId);
  if (customPricing) {
    for (const [key, price] of Object.entries(customPricing)) {
      if (normalizeModelId(key) === normalized) {
        return price;
      }
    }
  }
  for (const [key, price] of Object.entries(BUILTIN_PRICING)) {
    if (normalizeModelId(key) === normalized) {
      return price;
    }
  }
  if (BUILTIN_PRICING[normalized]) {
    return BUILTIN_PRICING[normalized];
  }
  if (normalized.includes('claude') && normalized.includes('opus')) {
    return BUILTIN_PRICING['claude-opus-4-6'];
  }
  if (normalized.includes('claude') && normalized.includes('sonnet')) {
    return BUILTIN_PRICING['claude-sonnet-4-6'];
  }
  if (normalized.includes('claude') && normalized.includes('haiku')) {
    return BUILTIN_PRICING['claude-haiku-4-5'];
  }
  if (normalized.includes('codex') || normalized.includes('gpt-5.5')) {
    return BUILTIN_PRICING['gpt-5.5-codex'] ?? BUILTIN_PRICING['gpt-5.5'];
  }
  if (normalized.includes('gpt-5.4')) {
    return BUILTIN_PRICING['gpt-5.4'];
  }
  if (normalized.includes('gpt-5')) {
    return BUILTIN_PRICING['gpt-5'];
  }
  if (normalized.startsWith('o4-mini') || normalized.startsWith('o3-mini')) {
    return BUILTIN_PRICING[normalized.startsWith('o4') ? 'o4-mini' : 'o3-mini'];
  }
  if (normalized.startsWith('o3')) {
    return BUILTIN_PRICING['o3'];
  }
  if (normalized.startsWith('gpt-4.1')) {
    return BUILTIN_PRICING[normalized.includes('mini') ? 'gpt-4.1-mini' : 'gpt-4.1'];
  }
  if (normalized.startsWith('gpt-4o')) {
    return BUILTIN_PRICING[normalized.includes('mini') ? 'gpt-4o-mini' : 'gpt-4o'];
  }
  return null;
}

export function calculateCost(
  modelId: string,
  inputTokens: number,
  outputTokens: number,
  cacheReadTokens: number,
  cacheCreationTokens: number,
  customPricing?: ModelPricingMap,
  options?: { app?: 'claude' | 'codex' }
): { total: number; input: number; output: number; cacheRead: number; cacheCreation: number } | null {
  const price = getModelPrice(modelId, customPricing);
  if (!price) {
    return null;
  }
  const billableInputTokens = options?.app === 'codex'
    ? Math.max(0, inputTokens - cacheReadTokens)
    : inputTokens;
  const input = (billableInputTokens / 1_000_000) * price.inputPerMillion;
  const output = (outputTokens / 1_000_000) * price.outputPerMillion;
  const cacheRead = cacheReadTokens > 0 && price.cacheReadPerMillion
    ? (cacheReadTokens / 1_000_000) * price.cacheReadPerMillion
    : 0;
  const cacheCreation = cacheCreationTokens > 0 && price.cacheCreationPerMillion
    ? (cacheCreationTokens / 1_000_000) * price.cacheCreationPerMillion
    : 0;
  const total = input + output + cacheRead + cacheCreation;
  return { total, input, output, cacheRead, cacheCreation };
}

export function formatCost(cost: number): string {
  if (cost < 0.01) {
    return '<$0.01';
  }
  return `$${cost.toFixed(2)}`;
}

export function getBuiltinPricing(): ModelPricingMap {
  return { ...BUILTIN_PRICING };
}