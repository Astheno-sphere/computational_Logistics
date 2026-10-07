import { readFileSync, statSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';

export const ENV_PROFILE_PREFIX = 'VESSEL_MCP_PROFILE_';
export const ENV_LABEL_FIELD_SEPARATOR = '__';
export const DEFAULT_LOCAL_CONFIG_PATH = 'config/credential-profiles.local.json';

export const credentialProfileFieldValues = [
  'api_key',
  'username',
  'password',
  'bearer_token',
  'client_id',
  'client_secret',
  'subscription_key',
] as const;

export type CredentialProfileField = (typeof credentialProfileFieldValues)[number];

const ALLOWED_FIELDS: ReadonlySet<string> = new Set(credentialProfileFieldValues);
const META_FIELD_PROVIDER = 'provider';

export type CredentialProfileSource = 'env' | 'local-config' | 'one-time';

export type CredentialProfileStatus = 'configured' | 'incomplete';

export interface CredentialProfileSummary {
  readonly label: string;
  readonly provider?: string;
  readonly source: CredentialProfileSource;
  readonly fieldsPresent: readonly CredentialProfileField[];
  readonly status: CredentialProfileStatus;
}

export interface CredentialStore {
  list(): readonly CredentialProfileSummary[];
  get(label: string): CredentialProfileSummary | undefined;
  resolveSecret(label: string, field: CredentialProfileField): string | undefined;
}

export const ONE_TIME_CREDENTIAL_ENV_GATE = 'VESSEL_MCP_ONE_TIME_CREDENTIALS';

export interface OneTimeCredentialInput {
  readonly providerId: string;
  readonly label: string;
  readonly fields: Partial<Record<CredentialProfileField, string>>;
}

export interface OneTimeCredentialGate {
  readonly enabled: boolean;
  readonly reason?: 'env_not_set' | 'env_value_invalid';
}

const ONE_TIME_GATE_TRUE = /^(1|true|on|enabled|yes)$/i;

export function readOneTimeCredentialGate(env: NodeJS.ProcessEnv = process.env): OneTimeCredentialGate {
  const raw = env[ONE_TIME_CREDENTIAL_ENV_GATE];
  if (raw === undefined || raw === '') {
    return { enabled: false, reason: 'env_not_set' };
  }
  if (ONE_TIME_GATE_TRUE.test(raw.trim())) {
    return { enabled: true };
  }
  return { enabled: false, reason: 'env_value_invalid' };
}

export interface LoadCredentialProfilesOptions {
  env?: NodeJS.ProcessEnv;
  cwd?: string;
  localConfigPath?: string;
  readFile?: (path: string) => string | undefined;
}

interface InternalProfile {
  label: string;
  provider?: string;
  source: CredentialProfileSource;
  fields: Map<CredentialProfileField, string>;
}

function defaultReadFile(path: string): string | undefined {
  try {
    if (!statSync(path).isFile()) {
      return undefined;
    }
  } catch {
    return undefined;
  }
  return readFileSync(path, 'utf8');
}

function normalizeLabel(rawLabel: string): string {
  return rawLabel.trim().toLowerCase().replace(/_/g, '-');
}

function isAllowedField(field: string): field is CredentialProfileField {
  return ALLOWED_FIELDS.has(field);
}

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function parseEnvProfiles(env: NodeJS.ProcessEnv): Map<string, InternalProfile> {
  const profiles = new Map<string, InternalProfile>();

  for (const [rawKey, rawValue] of Object.entries(env)) {
    if (!rawKey.startsWith(ENV_PROFILE_PREFIX)) continue;
    if (!nonEmpty(rawValue)) continue;

    const remainder = rawKey.slice(ENV_PROFILE_PREFIX.length);
    const separatorIndex = remainder.indexOf(ENV_LABEL_FIELD_SEPARATOR);
    if (separatorIndex <= 0 || separatorIndex >= remainder.length - ENV_LABEL_FIELD_SEPARATOR.length) {
      continue;
    }
    const rawLabel = remainder.slice(0, separatorIndex);
    const rawField = remainder.slice(separatorIndex + ENV_LABEL_FIELD_SEPARATOR.length).toLowerCase();
    const label = normalizeLabel(rawLabel);
    if (!label) continue;

    const profile = profiles.get(label) ?? {
      label,
      source: 'env' as CredentialProfileSource,
      fields: new Map<CredentialProfileField, string>(),
    };

    if (rawField === META_FIELD_PROVIDER) {
      profile.provider = rawValue.trim();
    } else if (isAllowedField(rawField)) {
      profile.fields.set(rawField, rawValue);
    }
    profiles.set(label, profile);
  }

  return profiles;
}

function parseLocalConfig(rawText: string, sourcePath: string): Map<string, InternalProfile> {
  const profiles = new Map<string, InternalProfile>();
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch (error) {
    const reason = error instanceof Error ? error.message : 'unknown JSON error';
    throw new Error(`credential profile config ${sourcePath} is not valid JSON: ${reason}`);
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`credential profile config ${sourcePath} must be a JSON object`);
  }
  const entries = (parsed as { profiles?: unknown }).profiles;
  if (entries === undefined) return profiles;
  if (!Array.isArray(entries)) {
    throw new Error(`credential profile config ${sourcePath} field "profiles" must be an array`);
  }

  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') continue;
    const record = entry as Record<string, unknown>;
    const rawLabel = record.label;
    if (!nonEmpty(rawLabel)) continue;
    const label = normalizeLabel(rawLabel);
    if (!label) continue;

    const profile: InternalProfile = {
      label,
      source: 'local-config',
      fields: new Map<CredentialProfileField, string>(),
    };

    if (nonEmpty(record.provider)) {
      profile.provider = record.provider.trim();
    }

    const rawFields = record.fields;
    if (rawFields && typeof rawFields === 'object' && !Array.isArray(rawFields)) {
      for (const [rawField, rawValue] of Object.entries(rawFields as Record<string, unknown>)) {
        const field = rawField.toLowerCase();
        if (!isAllowedField(field)) continue;
        if (!nonEmpty(rawValue)) continue;
        profile.fields.set(field, rawValue);
      }
    }

    profiles.set(label, profile);
  }

  return profiles;
}

function freezeSummary(profile: InternalProfile): CredentialProfileSummary {
  const fieldsPresent = credentialProfileFieldValues.filter((field) => profile.fields.has(field));
  const status: CredentialProfileStatus = fieldsPresent.length > 0 ? 'configured' : 'incomplete';
  return Object.freeze({
    label: profile.label,
    provider: profile.provider,
    source: profile.source,
    fieldsPresent: Object.freeze(fieldsPresent.slice()) as readonly CredentialProfileField[],
    status,
  });
}

export function loadCredentialProfiles(options: LoadCredentialProfilesOptions = {}): CredentialStore {
  const env = options.env ?? process.env;
  const cwd = options.cwd ?? process.cwd();
  const localConfigPath = resolvePath(cwd, options.localConfigPath ?? DEFAULT_LOCAL_CONFIG_PATH);
  const readFile = options.readFile ?? defaultReadFile;

  const fromLocal = (() => {
    const text = readFile(localConfigPath);
    if (text === undefined) return new Map<string, InternalProfile>();
    return parseLocalConfig(text, localConfigPath);
  })();

  const fromEnv = parseEnvProfiles(env);

  // env wins on label collision (architect contract).
  const merged = new Map<string, InternalProfile>();
  for (const [label, profile] of fromLocal) {
    merged.set(label, profile);
  }
  for (const [label, profile] of fromEnv) {
    merged.set(label, profile);
  }

  const orderedLabels = [...merged.keys()].sort();
  const summaries: CredentialProfileSummary[] = orderedLabels.map((label) =>
    freezeSummary(merged.get(label) as InternalProfile),
  );

  return {
    list() {
      return summaries;
    },
    get(label) {
      const normalized = normalizeLabel(label);
      return summaries.find((entry) => entry.label === normalized);
    },
    resolveSecret(label, field) {
      const normalized = normalizeLabel(label);
      const profile = merged.get(normalized);
      if (!profile) return undefined;
      if (!isAllowedField(field)) return undefined;
      return profile.fields.get(field);
    },
  };
}

export function emptyCredentialStore(): CredentialStore {
  return {
    list() {
      return [];
    },
    get() {
      return undefined;
    },
    resolveSecret() {
      return undefined;
    },
  };
}

function normalizeOneTimeFields(
  fields: Partial<Record<CredentialProfileField, string>>,
): Map<CredentialProfileField, string> {
  const accepted = new Map<CredentialProfileField, string>();
  for (const field of credentialProfileFieldValues) {
    const raw = fields[field];
    if (typeof raw !== 'string') continue;
    if (raw.trim().length === 0) continue;
    accepted.set(field, raw);
  }
  return accepted;
}

export function createOneTimeCredentialOverlay(
  base: CredentialStore,
  overlay: OneTimeCredentialInput,
): CredentialStore {
  const overlayLabel = normalizeLabel(overlay.label);
  const acceptedFields = normalizeOneTimeFields(overlay.fields);
  const fieldsPresent = credentialProfileFieldValues.filter((field) => acceptedFields.has(field));
  const summary: CredentialProfileSummary = Object.freeze({
    label: overlayLabel,
    provider: overlay.providerId,
    source: 'one-time',
    fieldsPresent: Object.freeze(fieldsPresent.slice()) as readonly CredentialProfileField[],
    status: acceptedFields.size > 0 ? 'configured' : 'incomplete',
  });

  return {
    list() {
      // The one-time overlay is intentionally absent from the public list so
      // it never appears in the credential_profiles MCP tool payload.
      return base.list();
    },
    get(label) {
      const normalized = normalizeLabel(label);
      if (normalized === overlayLabel) {
        return summary;
      }
      return base.get(label);
    },
    resolveSecret(label, field) {
      const normalized = normalizeLabel(label);
      if (normalized === overlayLabel) {
        if (!isAllowedField(field)) return undefined;
        return acceptedFields.get(field);
      }
      return base.resolveSecret(label, field);
    },
  };
}
