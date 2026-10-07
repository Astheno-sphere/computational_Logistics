import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import writeFileAtomic from 'write-file-atomic';

export const CODEX_MODEL_CATALOG_FILENAME = 'agentsociety-model-catalog.json';
export const CODEX_DEFAULT_CONTEXT_WINDOW = 272_000;
export const CODEX_ONE_M_CONTEXT_WINDOW = 1_048_576;
export const CODEX_DEFAULT_EFFECTIVE_CONTEXT_PERCENT = 95;
export const CODEX_ONE_M_AUTO_COMPACT_LIMIT = 900_000;

const DEFAULT_BASE_INSTRUCTIONS =
  'You are Codex, a coding agent. Follow the user instructions and use available tools when helpful.';

const DEFAULT_SUPPORTED_REASONING_LEVELS = [
  { effort: 'low', description: 'Fast responses with lighter reasoning' },
  { effort: 'medium', description: 'Balances speed and reasoning depth' },
  { effort: 'high', description: 'Greater reasoning depth for complex problems' },
  { effort: 'xhigh', description: 'Extra reasoning depth for complex problems' },
] as const;

export type CodexCatalogEntry = {
  modelId: string;
  displayName?: string;
  description?: string;
  contextWindow: number;
  effectiveContextPercent?: number;
  baseInstructions?: string;
};

export type CodexCatalogWriteOptions = {
  codexHome?: string;
  entries: CodexCatalogEntry[];
};

function resolveCodexHome(codexHome?: string): string {
  const configured = codexHome?.trim();
  if (configured) {
    return configured;
  }
  const envHome = process.env.CODEX_HOME?.trim();
  return envHome || path.join(os.homedir(), '.codex');
}

export function resolveCodexModelCatalogPath(codexHome?: string): string {
  return path.join(resolveCodexHome(codexHome), CODEX_MODEL_CATALOG_FILENAME);
}

export function buildCodexModelCatalogDocument(entries: CodexCatalogEntry[]): Record<string, unknown> {
  if (entries.length === 0) {
    throw new Error('Codex model catalog requires at least one entry');
  }
  const seenModelIds = new Set<string>();
  const models = entries.map((entry, index) => {
    const modelId = entry.modelId.trim();
    if (!modelId) {
      throw new Error('Codex model catalog modelId must not be empty');
    }
    if (seenModelIds.has(modelId)) {
      throw new Error(`Codex model catalog contains duplicate modelId: ${modelId}`);
    }
    seenModelIds.add(modelId);
    const displayName = entry.displayName?.trim() || modelId;
    const contextWindow = entry.contextWindow > 0 ? entry.contextWindow : CODEX_DEFAULT_CONTEXT_WINDOW;
    const effectiveContextPercent =
      entry.effectiveContextPercent && entry.effectiveContextPercent > 0
        ? entry.effectiveContextPercent
        : CODEX_DEFAULT_EFFECTIVE_CONTEXT_PERCENT;
    return {
      slug: modelId,
      display_name: displayName,
      description: entry.description?.trim() || `${displayName} coding model`,
      default_reasoning_level: 'medium',
      supported_reasoning_levels: DEFAULT_SUPPORTED_REASONING_LEVELS.map((level) => ({ ...level })),
      shell_type: 'shell_command',
      visibility: 'list',
      supported_in_api: true,
      priority: index + 1,
      availability_nux: null,
      upgrade: null,
      base_instructions: entry.baseInstructions?.trim() || DEFAULT_BASE_INSTRUCTIONS,
      support_verbosity: false,
      default_verbosity: null,
      default_reasoning_summary: 'auto',
      apply_patch_tool_type: 'freeform',
      web_search_tool_type: 'text',
      truncation_policy: { mode: 'bytes', limit: 10_000 },
      supports_parallel_tool_calls: true,
      context_window: contextWindow,
      effective_context_window_percent: effectiveContextPercent,
      experimental_supported_tools: [] as string[],
      input_modalities: ['text'],
      supports_reasoning_summaries: false,
    };
  });
  return { models };
}

export function writeCodexModelCatalog(options: CodexCatalogWriteOptions): string {
  const catalogPath = resolveCodexModelCatalogPath(options.codexHome);
  const dir = path.dirname(catalogPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  const payload = buildCodexModelCatalogDocument(options.entries);
  const json = `${JSON.stringify(payload, null, 2)}\n`;
  writeFileAtomic.sync(catalogPath, json, { encoding: 'utf8', mode: 0o600 });
  return catalogPath;
}

export function readCodexModelCatalogDocument(codexHome?: string): Record<string, unknown> | null {
  const catalogPath = resolveCodexModelCatalogPath(codexHome);
  if (!fs.existsSync(catalogPath)) {
    return null;
  }
  try {
    const parsed = JSON.parse(fs.readFileSync(catalogPath, 'utf-8')) as Record<string, unknown>;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

export function inferCodexContextWindow(modelId: string, enable1m?: boolean): number {
  if (enable1m) {
    return CODEX_ONE_M_CONTEXT_WINDOW;
  }
  const lower = modelId.trim().toLowerCase();
  if (
    lower.includes('longcat') ||
    lower.includes('mimo') ||
    lower.includes('qwen3-coder') ||
    lower.includes('deepseek-v4') ||
    lower.includes('doubao') ||
    lower.includes('seed')
  ) {
    return CODEX_ONE_M_CONTEXT_WINDOW;
  }
  return CODEX_DEFAULT_CONTEXT_WINDOW;
}
