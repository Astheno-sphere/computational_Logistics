import type { ProviderRegistry } from '../providers/registry.js';

export async function getDataSources(registry: ProviderRegistry): Promise<Record<string, unknown>> {
  const sources = (await Promise.all(registry.providers().map((provider) => provider.dataSources()))).flat();

  return {
    sources,
    summary: {
      total: sources.length,
      fixtureBacked: sources.filter((source) => source.transport === 'fixture').length,
      liveBacked: sources.filter((source) => source.transport !== 'fixture').length,
    },
  };
}
