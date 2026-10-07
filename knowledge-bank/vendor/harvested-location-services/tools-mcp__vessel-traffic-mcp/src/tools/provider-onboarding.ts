import { fileURLToPath } from 'node:url';

import { z } from 'zod/v4';

import type { CredentialStore } from '../config/credentials.js';
import { loadProviderCatalog, type ProviderCatalogEntry } from '../providers/catalog.js';
import { providerCapabilityValues, type ProviderCapability } from '../providers/types.js';

const DEFAULT_CATALOG_PATH = fileURLToPath(new URL('../../config/provider-catalog.example.json', import.meta.url));

export const providerOnboardingInputSchema = z
  .object({
    provider: z.string().min(1).optional(),
    capability: z.enum(providerCapabilityValues).optional(),
    implementedOnly: z.boolean().optional(),
  })
  .strict();

export type ProviderOnboardingInput = z.infer<typeof providerOnboardingInputSchema>;

interface Deps {
  credentialStore: CredentialStore;
  catalogPath?: string;
}

const ENV_PROFILE_PREFIX = 'VESSEL_MCP_PROFILE_';
const ENV_LABEL_FIELD_SEPARATOR = '__';

function normalizeLabel(rawLabel: string): string {
  return rawLabel.trim().toLowerCase().replace(/_/g, '-');
}

function labelFromEnvVar(envVar: string): string | undefined {
  if (!envVar.startsWith(ENV_PROFILE_PREFIX)) return undefined;
  const remainder = envVar.slice(ENV_PROFILE_PREFIX.length);
  const separatorIndex = remainder.indexOf(ENV_LABEL_FIELD_SEPARATOR);
  if (separatorIndex <= 0) return undefined;
  return normalizeLabel(remainder.slice(0, separatorIndex));
}

function defaultProfileLabel(entry: ProviderCatalogEntry): string {
  for (const envVar of entry.auth.envVars) {
    const label = labelFromEnvVar(envVar);
    if (label) return label;
  }
  return normalizeLabel(entry.id);
}

function profileStatus(entry: ProviderCatalogEntry, credentialStore: CredentialStore) {
  if (!entry.auth.required) {
    return {
      label: undefined,
      configured: true,
      missingFields: [] as string[],
    };
  }
  const label = defaultProfileLabel(entry);
  const profile = credentialStore.get(label);
  const fieldsPresent = new Set<string>(profile?.fieldsPresent ?? []);
  const missingFields = entry.auth.profileFields.filter((field) => !fieldsPresent.has(field));
  return {
    label,
    configured: profile?.status === 'configured' && missingFields.length === 0,
    missingFields,
  };
}

function firstSourceUrl(entry: ProviderCatalogEntry): string | undefined {
  return (
    entry.sources.signupUrl ??
    entry.sources.apiDocsUrl ??
    entry.sources.landingUrl ??
    entry.sources.referenceUrl ??
    entry.sources.termsUrl
  );
}

function nextStepsFor(entry: ProviderCatalogEntry, status: ReturnType<typeof profileStatus>): string[] {
  const steps: string[] = [];
  const sourceUrl = firstSourceUrl(entry);

  if (entry.auth.required) {
    if (sourceUrl) {
      steps.push(`Open ${sourceUrl} and sign up or request access with your own account.`);
    }
    steps.push(`Create local credential profile "${status.label}" with fields: ${entry.auth.profileFields.join(', ')}.`);
    if (entry.auth.envVars.length > 0) {
      steps.push(`Set environment variable(s): ${entry.auth.envVars.join(', ')}.`);
    }
    steps.push(`Run provider_onboarding again, then provider_status, to confirm the profile is configured.`);
  } else {
    steps.push('No credential is required. Enable the provider through the documented runtime flag if it is opt-in.');
    steps.push('Run provider_status or a read-only vessel/schedule tool and verify source.provider plus source.landingUrl.');
  }

  if (entry.implementationStatus !== 'implemented') {
    steps.push(`Adapter is ${entry.implementationStatus}; implement and test the provider before advertising runtime support.`);
  }

  return steps;
}

export async function providerOnboarding(
  deps: Deps,
  input: ProviderOnboardingInput = {},
): Promise<Record<string, unknown>> {
  const catalog = loadProviderCatalog(deps.catalogPath ?? DEFAULT_CATALOG_PATH);
  const providerFilter = input.provider?.toLowerCase();
  const entries = catalog.entries.filter((entry) => {
    if (providerFilter && entry.id !== providerFilter) return false;
    if (input.capability && !entry.capabilities.includes(input.capability as ProviderCapability)) return false;
    if (input.implementedOnly && entry.implementationStatus !== 'implemented') return false;
    return true;
  });

  const providers = entries.map((entry) => {
    const status = profileStatus(entry, deps.credentialStore);
    return {
      id: entry.id,
      displayName: entry.displayName,
      implementationStatus: entry.implementationStatus,
      accessClass: entry.accessClass,
      tier: entry.tier,
      priority: entry.priority,
      coverage: entry.coverage,
      capabilities: entry.capabilities,
      auth: {
        required: entry.auth.required,
        mode: entry.auth.mode,
        profileFields: entry.auth.profileFields,
        envVars: entry.auth.envVars,
        defaultProfileLabel: status.label,
        configured: status.configured,
        missingFields: status.missingFields,
        notes: entry.auth.notes,
      },
      cost: entry.cost,
      sources: entry.sources,
      liveTest: entry.liveTest,
      captureEligibility: entry.captureEligibility,
      canAutoCreateAccount: false as const,
      canAutoIssueCredential: false as const,
      onboardingMode: 'manual_signup_then_local_profile' as const,
      nextSteps: nextStepsFor(entry, status),
      notes: entry.notes,
    };
  });

  return {
    providers,
    summary: {
      total: providers.length,
      configured: providers.filter((entry) => entry.auth.configured).length,
      missingCredentials: providers.filter((entry) => entry.auth.required && !entry.auth.configured).length,
      implemented: providers.filter((entry) => entry.implementationStatus === 'implemented').length,
      manualSignupRequired: providers.filter((entry) => entry.auth.required).length,
    },
    filters: {
      provider: input.provider,
      capability: input.capability,
      implementedOnly: input.implementedOnly,
    },
    safety: {
      readOnly: true as const,
      autoSignup: false as const,
      autoCredentialIssuance: false as const,
      note:
        'This MCP cannot create provider accounts, accept terms, solve CAPTCHA, complete email verification, set payment details, or issue API keys. Operators must sign up manually and supply their own local credentials.',
    },
  };
}
