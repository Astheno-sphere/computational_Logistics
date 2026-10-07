import { createFixtureProvider } from './fixture.js';
import type { ProviderCapability, VesselDataProvider } from './types.js';

export interface ProviderRegistry {
  providers(): VesselDataProvider[];
  byId(id: string): VesselDataProvider | undefined;
  byCapability(capability: ProviderCapability): VesselDataProvider[];
}

export function createProviderRegistry(
  providers: VesselDataProvider[] = [createFixtureProvider()],
): ProviderRegistry {
  const ids = new Set<string>();
  for (const provider of providers) {
    if (ids.has(provider.id)) {
      throw new Error(`duplicate provider id "${provider.id}" in registry`);
    }
    ids.add(provider.id);
  }

  return {
    providers() {
      return [...providers];
    },
    byId(id) {
      return providers.find((provider) => provider.id === id);
    },
    byCapability(capability) {
      return providers.filter((provider) => provider.capabilities().includes(capability));
    },
  };
}
