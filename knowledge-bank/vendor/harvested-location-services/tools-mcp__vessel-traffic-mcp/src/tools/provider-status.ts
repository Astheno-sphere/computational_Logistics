import type { ProviderRegistry } from '../providers/registry.js';

export async function getProviderStatus(registry: ProviderRegistry): Promise<Record<string, unknown>> {
  const providers = registry.providers();
  const statuses = await Promise.all(providers.map((provider) => provider.status()));

  return {
    providers: statuses,
    summary: {
      total: statuses.length,
      available: statuses.filter((status) => status.status === 'available').length,
      degraded: statuses.filter((status) => status.status === 'degraded').length,
      unavailable: statuses.filter((status) => status.status === 'unavailable').length,
    },
  };
}
