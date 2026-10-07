export type SimLlmPreset = {
  id: string;
  labelKey: string;
  hintKey?: string;
  baseUrl: string;
  defaultModel?: string;
};

export const SIM_LLM_PRESETS: SimLlmPreset[] = [
  {
    id: 'openai',
    labelKey: 'configPage.llm.presetOpenai',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-5.5',
  },
  {
    id: 'fiblab',
    labelKey: 'configPage.llm.presetFiblab',
    hintKey: 'configPage.llm.presetFiblabHint',
    baseUrl: 'https://llmapi.fiblab.net/v1',
  },
  {
    id: 'custom',
    labelKey: 'configPage.llm.presetCustom',
    baseUrl: '',
  },
];

export function matchSimLlmPreset(baseUrl: string | undefined): string {
  const normalized = (baseUrl ?? '').trim().replace(/\/+$/, '');
  if (!normalized) {
    return 'custom';
  }
  const hit = SIM_LLM_PRESETS.find((p) => {
    if (p.id === 'custom') {
      return false;
    }
    const presetBase = p.baseUrl.replace(/\/+$/, '');
    return (
      presetBase === normalized ||
      presetBase === `${normalized}/v1` ||
      `${normalized}/v1` === presetBase
    );
  });
  return hit?.id ?? 'custom';
}
