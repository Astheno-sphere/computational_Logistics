import { z } from 'zod/v4';

import { credentialProfileFieldValues } from '../config/credentials.js';
import {
  catalogCostModelValues,
  catalogImplementationStatusValues,
  catalogPriorityValues,
} from '../providers/catalog.js';
import { providerCapabilityValues, providerTransportValues, sourceConfidenceValues } from '../providers/types.js';

const providerCapabilitySchema = z.enum(providerCapabilityValues);
const providerTransportSchema = z.enum(providerTransportValues);
const sourceConfidenceSchema = z.enum(sourceConfidenceValues);

const sourceMetadataSchema = z.object({
  provider: z.string(),
  adapterVersion: z.string(),
  transport: providerTransportSchema,
  coverage: z.string().optional(),
  confidence: sourceConfidenceSchema.optional(),
  termsNote: z.string().optional(),
  landingUrl: z.url().optional(),
});

const providerStatusSchema = z.object({
  id: z.string(),
  name: z.string(),
  authState: z.enum(['not_required', 'configured', 'missing', 'disabled']),
  status: z.enum(['available', 'degraded', 'unavailable']),
  capabilities: z.array(providerCapabilitySchema),
  source: sourceMetadataSchema,
  retrievedAt: z.iso.datetime(),
  quota: z
    .object({
      state: z.enum(['not_applicable', 'unknown', 'available', 'limited', 'exhausted']),
      note: z.string().optional(),
    })
    .optional(),
  caveats: z.array(z.string()),
});

const dataSourceSchema = z.object({
  id: z.string(),
  name: z.string(),
  transport: providerTransportSchema,
  capabilities: z.array(providerCapabilitySchema),
  coverage: z.string(),
  auth: z.object({
    required: z.boolean(),
    mode: z.enum(['none', 'byok-profile', 'one-time']),
  }),
  caveats: z.array(z.string()),
  source: sourceMetadataSchema,
});

export const providerStatusOutputSchema = {
  providers: z.array(providerStatusSchema),
  summary: z.object({
    total: z.number().int().nonnegative(),
    available: z.number().int().nonnegative(),
    degraded: z.number().int().nonnegative(),
    unavailable: z.number().int().nonnegative(),
  }),
};

export const dataSourcesOutputSchema = {
  sources: z.array(dataSourceSchema),
  summary: z.object({
    total: z.number().int().nonnegative(),
    fixtureBacked: z.number().int().nonnegative(),
    liveBacked: z.number().int().nonnegative(),
  }),
};

const credentialProfileFieldSchema = z.enum(credentialProfileFieldValues);

const credentialProfileSummarySchema = z.object({
  label: z.string(),
  provider: z.string().optional(),
  source: z.enum(['env', 'local-config', 'one-time']),
  fieldsPresent: z.array(credentialProfileFieldSchema),
  status: z.enum(['configured', 'incomplete']),
});

export const credentialProfilesOutputSchema = {
  profiles: z.array(credentialProfileSummarySchema),
  summary: z.object({
    total: z.number().int().nonnegative(),
    configured: z.number().int().nonnegative(),
    incomplete: z.number().int().nonnegative(),
    fromEnv: z.number().int().nonnegative(),
    fromLocalConfig: z.number().int().nonnegative(),
  }),
  notes: z.array(z.string()),
};

const providerOnboardingEntrySchema = z.object({
  id: z.string(),
  displayName: z.string(),
  implementationStatus: z.enum(catalogImplementationStatusValues),
  accessClass: z.string(),
  tier: z.string(),
  priority: z.enum(catalogPriorityValues),
  coverage: z.string(),
  capabilities: z.array(providerCapabilitySchema),
  auth: z.object({
    required: z.boolean(),
    mode: z.string(),
    profileFields: z.array(z.string()),
    envVars: z.array(z.string()),
    defaultProfileLabel: z.string().optional(),
    configured: z.boolean(),
    missingFields: z.array(z.string()),
    notes: z.string().optional(),
  }),
  cost: z.object({
    model: z.enum(catalogCostModelValues),
    quotaNote: z.string().optional(),
  }),
  sources: z.object({
    apiDocsUrl: z.url().optional(),
    landingUrl: z.url().optional(),
    signupUrl: z.url().optional(),
    termsUrl: z.url().optional(),
    referenceUrl: z.url().optional(),
  }),
  liveTest: z.object({
    enabledFlagEnvVar: z.string(),
    requiredEnvVars: z.array(z.string()),
    defaultDisabled: z.literal(true),
    notes: z.string().optional(),
  }),
  captureEligibility: z.string(),
  canAutoCreateAccount: z.literal(false),
  canAutoIssueCredential: z.literal(false),
  onboardingMode: z.literal('manual_signup_then_local_profile'),
  nextSteps: z.array(z.string()),
  notes: z.string().optional(),
});

export const providerOnboardingOutputSchema = {
  providers: z.array(providerOnboardingEntrySchema),
  summary: z.object({
    total: z.number().int().nonnegative(),
    configured: z.number().int().nonnegative(),
    missingCredentials: z.number().int().nonnegative(),
    implemented: z.number().int().nonnegative(),
    manualSignupRequired: z.number().int().nonnegative(),
  }),
  filters: z.object({
    provider: z.string().optional(),
    capability: providerCapabilitySchema.optional(),
    implementedOnly: z.boolean().optional(),
  }),
  safety: z.object({
    readOnly: z.literal(true),
    autoSignup: z.literal(false),
    autoCredentialIssuance: z.literal(false),
    note: z.string(),
  }),
};
