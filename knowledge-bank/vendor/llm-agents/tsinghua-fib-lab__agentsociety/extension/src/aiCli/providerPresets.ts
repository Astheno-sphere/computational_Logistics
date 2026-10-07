import type { AiCliApiKind } from './officialEndpoints';
import {
  OFFICIAL_ANTHROPIC_BASE_URL,
  OFFICIAL_OPENAI_BASE_URL,
  isOfficialAnthropicBaseUrl,
  isOfficialOpenAiBaseUrl,
} from './officialEndpoints';

export type ClaudeModelOption = {
  id: string;
  label?: string;
};

/** How Codex should talk to this OpenAI-compatible endpoint. */
export type CodexWireHint = 'openai_responses' | 'openai_chat';

export type AiCliProviderPreset = {
  id: string;
  url: string;
  apiKind: AiCliApiKind;
  official?: boolean;
  /** Coding Plan / Token Plan / Agent Plan style subscription endpoint. */
  planKind?: 'coding' | 'token' | 'agent';
  /** Codex: prefer Chat Completions bridge vs native Responses. */
  codexWire?: CodexWireHint;
  roles: Array<'claude' | 'codex'>;
  modelHints?: ClaudeModelOption[];
};

/**
 * Built-in dropdown presets (aligned with cc-switch cn_official / official set).
 * These do not auto-create cards — they only fill Base URL / hints when selected.
 * Fiblab still comes from Web import. Partner aggregators are intentionally omitted.
 */
export const CLAUDE_PROVIDER_PRESETS: AiCliProviderPreset[] = [
  { id: 'anthropic', url: OFFICIAL_ANTHROPIC_BASE_URL, apiKind: 'anthropic', official: true, roles: ['claude'] },
  {
    id: 'deepseek',
    url: 'https://api.deepseek.com/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [
      { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
      { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    ],
  },
  {
    id: 'volcengine',
    url: 'https://ark.cn-beijing.volces.com/api/coding',
    apiKind: 'anthropic',
    planKind: 'agent',
    roles: ['claude'],
    modelHints: [{ id: 'ark-code-latest', label: 'Ark Code Latest' }],
  },
  {
    id: 'byteplus',
    url: 'https://ark.ap-southeast.bytepluses.com/api/coding',
    apiKind: 'anthropic',
    planKind: 'agent',
    roles: ['claude'],
    modelHints: [{ id: 'ark-code-latest', label: 'Ark Code Latest' }],
  },
  {
    id: 'doubaoSeed',
    url: 'https://ark.cn-beijing.volces.com/api/compatible',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [{ id: 'doubao-seed-2-1-pro-260628', label: 'Doubao Seed 2.1 Pro' }],
  },
  {
    id: 'mimo',
    url: 'https://api.xiaomimimo.com/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [{ id: 'mimo-v2.5-pro', label: 'MiMo V2.5 Pro' }],
  },
  {
    id: 'mimoTokenPlan',
    url: 'https://token-plan-cn.xiaomimimo.com/anthropic',
    apiKind: 'anthropic',
    planKind: 'token',
    roles: ['claude'],
    modelHints: [{ id: 'mimo-v2.5-pro', label: 'MiMo V2.5 Pro' }],
  },
  {
    id: 'longcat',
    url: 'https://api.longcat.chat/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [{ id: 'LongCat-2.0', label: 'LongCat 2.0' }],
  },
  {
    id: 'bigmodel',
    url: 'https://open.bigmodel.cn/api/anthropic',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'glm-5.1', label: 'GLM-5.1' }],
  },
  {
    id: 'zhipuEn',
    url: 'https://api.z.ai/api/anthropic',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'glm-5.1', label: 'GLM-5.1' }],
  },
  {
    id: 'kimi',
    url: 'https://api.kimi.com/coding/',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'kimi-for-coding', label: 'Kimi for Coding' }],
  },
  {
    id: 'moonshot',
    url: 'https://api.moonshot.cn/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [
      { id: 'kimi-k2.7-code', label: 'Kimi K2.7 Code' },
      { id: 'kimi-k3', label: 'Kimi K3' },
    ],
  },
  {
    id: 'minimax',
    url: 'https://api.minimaxi.com/anthropic',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'MiniMax-M2.7', label: 'MiniMax M2.7' }],
  },
  {
    id: 'minimaxEn',
    url: 'https://api.minimax.io/anthropic',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'MiniMax-M2.7', label: 'MiniMax M2.7' }],
  },
  {
    id: 'bailian',
    url: 'https://dashscope.aliyuncs.com/apps/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
  },
  {
    id: 'bailianCoding',
    url: 'https://coding.dashscope.aliyuncs.com/apps/anthropic',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
  },
  {
    id: 'stepfunClaude',
    url: 'https://api.stepfun.com/step_plan',
    apiKind: 'anthropic',
    planKind: 'token',
    roles: ['claude'],
    modelHints: [{ id: 'step-3.5-flash-2603', label: 'Step 3.5 Flash' }],
  },
  {
    id: 'stepfunClaudeEn',
    url: 'https://api.stepfun.ai/step_plan',
    apiKind: 'anthropic',
    planKind: 'token',
    roles: ['claude'],
    modelHints: [{ id: 'step-3.5-flash-2603', label: 'Step 3.5 Flash' }],
  },
  {
    id: 'bailing',
    url: 'https://api.tbox.cn/api/anthropic',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [{ id: 'Ling-2.5-1T', label: 'Ling 2.5 1T' }],
  },
  {
    id: 'qianfan',
    url: 'https://qianfan.baidubce.com/anthropic/coding',
    apiKind: 'anthropic',
    planKind: 'coding',
    roles: ['claude'],
    modelHints: [{ id: 'qianfan-code-latest', label: 'Qianfan Code Latest' }],
  },
  {
    id: 'xaiClaude',
    url: 'https://api.x.ai/v1',
    apiKind: 'anthropic',
    roles: ['claude'],
    modelHints: [{ id: 'grok-4.5', label: 'Grok 4.5' }],
  },
  {
    id: 'openrouter',
    url: 'https://openrouter.ai/api',
    apiKind: 'anthropic',
    roles: ['claude'],
  },
];

export const CODEX_PROVIDER_PRESETS: AiCliProviderPreset[] = [
  { id: 'openai', url: OFFICIAL_OPENAI_BASE_URL, apiKind: 'openai', official: true, roles: ['codex'], codexWire: 'openai_responses' },
  {
    id: 'xaiCodex',
    url: 'https://api.x.ai/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [{ id: 'grok-4.5', label: 'Grok 4.5' }],
  },
  {
    id: 'mimoCodex',
    url: 'https://api.xiaomimimo.com/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [
      { id: 'mimo-v2.5-pro', label: 'MiMo V2.5 Pro' },
      { id: 'mimo-v2.5', label: 'MiMo V2.5' },
    ],
  },
  {
    id: 'mimoTokenPlanCodex',
    url: 'https://token-plan-cn.xiaomimimo.com/v1',
    apiKind: 'openai',
    planKind: 'token',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [
      { id: 'mimo-v2.5-pro', label: 'MiMo V2.5 Pro' },
      { id: 'mimo-v2.5', label: 'MiMo V2.5' },
    ],
  },
  {
    id: 'longcatCodex',
    url: 'https://api.longcat.chat/openai/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [{ id: 'LongCat-2.0', label: 'LongCat 2.0' }],
  },
  {
    id: 'zhipuCodex',
    url: 'https://open.bigmodel.cn/api/coding/paas/v4',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'glm-5.2', label: 'GLM-5.2' }],
  },
  {
    id: 'zhipuCodexEn',
    url: 'https://api.z.ai/api/coding/paas/v4',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'glm-5.2', label: 'GLM-5.2' }],
  },
  {
    id: 'kimiCodex',
    url: 'https://api.kimi.com/coding/v1',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'kimi-for-coding', label: 'Kimi for Coding' }],
  },
  {
    id: 'moonshotCodex',
    url: 'https://api.moonshot.cn/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [
      { id: 'kimi-k2.7-code', label: 'Kimi K2.7 Code' },
      { id: 'kimi-k3', label: 'Kimi K3' },
    ],
  },
  {
    id: 'minimaxOpenAi',
    url: 'https://api.minimaxi.com/v1',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    // MiniMax official /v1/responses — native Responses (cc-switch).
    codexWire: 'openai_responses',
    modelHints: [{ id: 'MiniMax-M3', label: 'MiniMax M3' }],
  },
  {
    id: 'minimaxOpenAiEn',
    url: 'https://api.minimax.io/v1',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [{ id: 'MiniMax-M3', label: 'MiniMax M3' }],
  },
  {
    id: 'deepseekOpenAi',
    url: 'https://api.deepseek.com',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [
      { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
      { id: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    ],
  },
  {
    id: 'volcengineAgentplanCodex',
    url: 'https://ark.cn-beijing.volces.com/api/coding/v3',
    apiKind: 'openai',
    planKind: 'agent',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'ark-code-latest', label: 'Ark Code Latest' }],
  },
  {
    id: 'byteplusCodex',
    url: 'https://ark.ap-southeast.bytepluses.com/api/coding/v3',
    apiKind: 'openai',
    planKind: 'agent',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'ark-code-latest', label: 'Ark Code Latest' }],
  },
  {
    id: 'doubaoSeedCodex',
    url: 'https://ark.cn-beijing.volces.com/api/v3',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [{ id: 'doubao-seed-2-1-pro-260628', label: 'Doubao Seed 2.1 Pro' }],
  },
  {
    id: 'siliconflow',
    url: 'https://api.siliconflow.cn/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_chat',
  },
  {
    id: 'bailianCodex',
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_responses',
    modelHints: [
      { id: 'qwen-plus', label: 'Qwen Plus' },
      { id: 'qwen3-coder-plus', label: 'Qwen3 Coder Plus' },
    ],
  },
  {
    id: 'stepfun',
    url: 'https://api.stepfun.com/step_plan/v1',
    apiKind: 'openai',
    planKind: 'token',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [
      { id: 'step-3.7-flash', label: 'Step 3.7 Flash' },
      { id: 'step-3.5-flash-2603', label: 'Step 3.5 Flash' },
    ],
  },
  {
    id: 'stepfunEn',
    url: 'https://api.stepfun.ai/step_plan/v1',
    apiKind: 'openai',
    planKind: 'token',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [
      { id: 'step-3.7-flash', label: 'Step 3.7 Flash' },
      { id: 'step-3.5-flash-2603', label: 'Step 3.5 Flash' },
    ],
  },
  {
    id: 'qianfanCodex',
    url: 'https://qianfan.baidubce.com/v2/coding',
    apiKind: 'openai',
    planKind: 'coding',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'qianfan-code-latest', label: 'Qianfan Code Latest' }],
  },
  {
    id: 'bailingCodex',
    url: 'https://api.tbox.cn/api/llm/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_chat',
    modelHints: [{ id: 'Ling-2.6-1T', label: 'Ling 2.6 1T' }],
  },
  {
    id: 'openrouterOpenAi',
    url: 'https://openrouter.ai/api/v1',
    apiKind: 'openai',
    roles: ['codex'],
    codexWire: 'openai_chat',
  },
];

export const OPENAI_FALLBACK_MODELS: ClaudeModelOption[] = [
  { id: 'gpt-5.5-codex', label: 'GPT-5.5 Codex' },
  { id: 'gpt-5.5', label: 'GPT-5.5' },
  { id: 'gpt-5.4', label: 'GPT-5.4' },
];

export const ANTHROPIC_FALLBACK_MODELS: ClaudeModelOption[] = [
  { id: 'claude-sonnet-5', label: 'Claude Sonnet 5' },
  { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { id: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
  { id: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
];

const ALL_PRESETS: AiCliProviderPreset[] = [...CLAUDE_PROVIDER_PRESETS, ...CODEX_PROVIDER_PRESETS];

export function getProviderPresetsForRole(role: 'claude' | 'codex'): AiCliProviderPreset[] {
  return role === 'claude' ? CLAUDE_PROVIDER_PRESETS : CODEX_PROVIDER_PRESETS;
}

export function findPresetByUrl(baseUrl: string): AiCliProviderPreset | undefined {
  const normalized = baseUrl.trim().replace(/\/+$/, '');
  return ALL_PRESETS.find((preset) => preset.url.replace(/\/+$/, '') === normalized);
}

export function findPresetById(id: string): AiCliProviderPreset | undefined {
  return ALL_PRESETS.find((preset) => preset.id === id);
}

/** Hosts that natively speak OpenAI Responses (Codex can skip Chat bridge). */
const NATIVE_RESPONSES_HOST_MARKERS = [
  'api.openai.com',
  'api.longcat.chat',
  'api.xiaomimimo.com',
  'token-plan-cn.xiaomimimo.com',
  'token-plan.xiaomimimo.com',
  'dashscope.aliyuncs.com',
  'api.x.ai',
];

export function inferCodexWireFromBaseUrl(baseUrl: string): CodexWireHint {
  const preset = findPresetByUrl(baseUrl);
  if (preset?.codexWire) {
    return preset.codexWire;
  }
  if (isOfficialOpenAiBaseUrl(baseUrl)) {
    return 'openai_responses';
  }
  try {
    const host = new URL(baseUrl.trim()).hostname.toLowerCase();
    if (NATIVE_RESPONSES_HOST_MARKERS.some((marker) => host === marker || host.endsWith(`.${marker}`))) {
      return 'openai_responses';
    }
  } catch {
    /* fall through */
  }
  return 'openai_chat';
}

export function mergeModelOptions(
  fetched: ClaudeModelOption[],
  baseUrl: string,
  apiKind: AiCliApiKind
): ClaudeModelOption[] {
  const preset = findPresetByUrl(baseUrl);
  const hints = preset?.modelHints ?? [];
  const useGenericFallback =
    isOfficialOpenAiBaseUrl(baseUrl) || isOfficialAnthropicBaseUrl(baseUrl);
  const fallback = useGenericFallback
    ? apiKind === 'openai'
      ? OPENAI_FALLBACK_MODELS
      : ANTHROPIC_FALLBACK_MODELS
    : [];
  const seen = new Set<string>();
  const merged: ClaudeModelOption[] = [];
  for (const source of [...fetched, ...hints, ...fallback]) {
    const id = source.id.trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    merged.push(source);
  }
  return merged;
}
