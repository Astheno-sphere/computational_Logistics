import type { CredentialStore } from '../config/credentials.js';

export async function getCredentialProfiles(store: CredentialStore): Promise<Record<string, unknown>> {
  const summaries = store.list();
  const profiles = summaries.map((entry) => ({
    label: entry.label,
    provider: entry.provider,
    source: entry.source,
    fieldsPresent: [...entry.fieldsPresent],
    status: entry.status,
  }));

  return {
    profiles,
    summary: {
      total: profiles.length,
      configured: profiles.filter((p) => p.status === 'configured').length,
      incomplete: profiles.filter((p) => p.status === 'incomplete').length,
      fromEnv: profiles.filter((p) => p.source === 'env').length,
      fromLocalConfig: profiles.filter((p) => p.source === 'local-config').length,
    },
    notes: [
      'Profile values are redacted; only labels, provider hints, declared fields, and status are exposed.',
      'Env vars matching VESSEL_MCP_PROFILE_<LABEL>__<FIELD> override local config on label collision.',
      'BYOK keys belong in env or gitignored config; never commit raw credentials.',
    ],
  };
}
