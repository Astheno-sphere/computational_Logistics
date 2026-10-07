import type { ClaudeModelOption } from './claudeCodeModels';

export const OFFICIAL_ANTHROPIC_MODELS: ClaudeModelOption[] = [
  { id: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
  { id: 'claude-opus-4-5', label: 'Claude Opus 4.5' },
  { id: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { id: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
  { id: 'claude-sonnet-4', label: 'Claude Sonnet 4' },
  { id: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { id: 'claude-opus-4', label: 'Claude Opus 4' },
  { id: 'claude-3-7-sonnet', label: 'Claude 3.7 Sonnet' },
  { id: 'claude-3-5-sonnet', label: 'Claude 3.5 Sonnet' },
  { id: 'claude-3-5-haiku', label: 'Claude 3.5 Haiku' },
  { id: 'claude-3-opus', label: 'Claude 3 Opus' },
  { id: 'claude-3-haiku', label: 'Claude 3 Haiku' },
];

export const OFFICIAL_OPENAI_MODELS: ClaudeModelOption[] = [
  { id: 'gpt-5.5', label: 'GPT-5.5' },
  { id: 'gpt-5.5-pro', label: 'GPT-5.5 Pro' },
  { id: 'gpt-5.5-codex', label: 'GPT-5.5 Codex' },
  { id: 'gpt-5.4', label: 'GPT-5.4' },
  { id: 'gpt-5', label: 'GPT-5' },
  { id: 'gpt-5-codex', label: 'GPT-5 Codex' },
  { id: 'gpt-4.1', label: 'GPT-4.1' },
  { id: 'gpt-4.1-mini', label: 'GPT-4.1 mini' },
  { id: 'gpt-4o', label: 'GPT-4o' },
  { id: 'gpt-4o-mini', label: 'GPT-4o mini' },
  { id: 'o4-mini', label: 'o4 mini' },
  { id: 'o3', label: 'o3' },
  { id: 'o3-mini', label: 'o3 mini' },
];