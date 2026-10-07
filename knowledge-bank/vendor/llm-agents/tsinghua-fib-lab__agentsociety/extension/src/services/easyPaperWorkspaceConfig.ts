import * as fs from 'fs';
import * as yaml from 'js-yaml';
import type { EasyPaperConfigValues } from '../webview/configPage/types';

const EASY_PAPER_AGENT_NAMES = [
  'paper_parser',
  'template_parser',
  'commander',
  'writer',
  'typesetter',
  'metadata',
  'reviewer',
  'planner',
];

export function readEasyPaperConfig(configPath: string): EasyPaperConfigValues | undefined {
  if (!fs.existsSync(configPath)) {
    return undefined;
  }
  const raw = fs.readFileSync(configPath, 'utf-8');
  const data = yaml.load(raw) as Record<string, unknown> | null;
  if (!data || typeof data !== 'object') {
    return undefined;
  }
  const result: EasyPaperConfigValues = {
    llmModelName: '',
    llmApiKey: '',
    llmBaseUrl: '',
    vlmEnabled: false,
    vlmModel: '',
    vlmApiKey: '',
    vlmBaseUrl: '',
  };
  const agents = Array.isArray(data.agents) ? data.agents : [];
  const firstModel = (agents[0] as { model?: Record<string, string> } | undefined)?.model;
  if (firstModel) {
    result.llmModelName = firstModel.model_name || '';
    result.llmApiKey = firstModel.api_key || '';
    result.llmBaseUrl = firstModel.base_url || '';
  }
  const vlm = data.vlm_service as { model?: string; api_key?: string; base_url?: string } | undefined;
  if (vlm?.model) {
    result.vlmEnabled = true;
    result.vlmModel = vlm.model || '';
    result.vlmApiKey = vlm.api_key || '';
    result.vlmBaseUrl = vlm.base_url || '';
  }
  return result;
}

export function writeEasyPaperConfig(configPath: string, config: EasyPaperConfigValues): void {
  const hasLlm = config.llmModelName?.trim() || config.llmApiKey?.trim() || config.llmBaseUrl?.trim();
  if (!hasLlm) {
    if (fs.existsSync(configPath)) {
      fs.unlinkSync(configPath);
    }
    return;
  }

  const agentBlock = (name: string) => {
    const entry: Record<string, unknown> = {
      name,
      model: {
        model_name: config.llmModelName || '',
        api_key: config.llmApiKey || '',
        base_url: config.llmBaseUrl || '',
      },
    };
    if (name === 'writer') {
      entry.writer_config = {};
    }
    if (name === 'metadata') {
      entry.metadata_config = {};
    }
    return entry;
  };

  const yamlObj: Record<string, unknown> = {
    skills: {},
    tools: {
      table_critic_enabled: true,
      table_rendered_review_enabled: true,
      paper_search: { timeout: 15, search_results_per_round: 12 },
      research_context: {},
      core_ref_analysis: {},
      docling: { enabled: true },
      exemplar: { enabled: true },
    },
    agents: EASY_PAPER_AGENT_NAMES.map(agentBlock),
  };

  yamlObj.agents = [
    ...(yamlObj.agents as unknown[]),
    { name: 'vlm_review', vlm_review_config: { check_layout: true } },
  ];

  if (config.vlmEnabled && (config.vlmModel?.trim() || config.vlmApiKey?.trim())) {
    yamlObj.vlm_service = {
      model: config.vlmModel || '',
      api_key: config.vlmApiKey || '',
      base_url: config.vlmBaseUrl || '',
    };
  }

  const content = yaml.dump(yamlObj, { lineWidth: 120, noRefs: true });
  fs.writeFileSync(configPath, content, 'utf-8');
}
