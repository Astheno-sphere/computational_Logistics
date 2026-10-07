import { readFileSync } from 'node:fs';

import {
  captureEligibilityValues,
  credentialModeValues,
  providerAccessClassValues,
  providerCapabilityValues,
  providerTierValues,
  type CaptureEligibility,
  type CredentialMode,
  type ProviderAccessClass,
  type ProviderCapability,
  type ProviderTier,
} from './types.js';

export const catalogImplementationStatusValues = [
  'fixture',
  'not_started',
  'planned',
  'in_progress',
  'implemented',
  'capture_only',
  'discovery_only',
] as const;

export type CatalogImplementationStatus = (typeof catalogImplementationStatusValues)[number];

export const catalogCostModelValues = [
  'fixture',
  'free',
  'open-data',
  'community',
  'trial',
  'freemium',
  'credit-based',
  'subscription',
  'enterprise',
] as const;

export type CatalogCostModel = (typeof catalogCostModelValues)[number];

export const catalogPriorityValues = ['P0', 'P1', 'P2', 'P3'] as const;

export type CatalogPriority = (typeof catalogPriorityValues)[number];

export interface CatalogAuth {
  readonly mode: CredentialMode;
  readonly required: boolean;
  readonly profileFields: readonly string[];
  readonly envVars: readonly string[];
  readonly notes?: string;
}

export interface CatalogCost {
  readonly model: CatalogCostModel;
  readonly quotaNote?: string;
}

export interface CatalogSources {
  readonly apiDocsUrl?: string;
  readonly landingUrl?: string;
  readonly signupUrl?: string;
  readonly termsUrl?: string;
  readonly referenceUrl?: string;
}

export interface CatalogLiveTest {
  readonly enabledFlagEnvVar: string;
  readonly requiredEnvVars: readonly string[];
  readonly defaultDisabled: true;
  readonly notes?: string;
}

export interface ProviderCatalogEntry {
  readonly id: string;
  readonly displayName: string;
  readonly accessClass: ProviderAccessClass;
  readonly tier: ProviderTier;
  readonly priority: CatalogPriority;
  readonly coverage: string;
  readonly capabilities: readonly ProviderCapability[];
  readonly auth: CatalogAuth;
  readonly cost: CatalogCost;
  readonly sources: CatalogSources;
  readonly implementationStatus: CatalogImplementationStatus;
  readonly liveTest: CatalogLiveTest;
  readonly captureEligibility: CaptureEligibility;
  readonly notes?: string;
}

export interface ProviderCatalog {
  readonly version: number;
  readonly generatedAt: string;
  readonly sourceDoc: string;
  readonly entries: readonly ProviderCatalogEntry[];
}

const ACCESS_CLASSES = new Set<string>(providerAccessClassValues);
const TIERS = new Set<string>(providerTierValues);
const CAPABILITIES = new Set<string>(providerCapabilityValues);
const CREDENTIAL_MODES = new Set<string>(credentialModeValues);
const CAPTURE_ELIGIBILITY = new Set<string>(captureEligibilityValues);
const IMPL_STATUSES = new Set<string>(catalogImplementationStatusValues);
const COST_MODELS = new Set<string>(catalogCostModelValues);
const PRIORITIES = new Set<string>(catalogPriorityValues);

const URL_FIELDS: readonly (keyof CatalogSources)[] = [
  'apiDocsUrl',
  'landingUrl',
  'signupUrl',
  'termsUrl',
  'referenceUrl',
];

const ID_PATTERN = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/;
const ENV_VAR_PATTERN = /^[A-Z][A-Z0-9_]*$/;
const URL_PATTERN = /^https:\/\/[^\s]+$/;

function fail(path: string, message: string): never {
  throw new Error(`provider catalog ${path}: ${message}`);
}

function ensureString(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    fail(path, 'must be a non-empty string');
  }
  return value;
}

function ensureStringArray(value: unknown, path: string): string[] {
  if (!Array.isArray(value)) fail(path, 'must be an array');
  return value.map((item, index) => {
    if (typeof item !== 'string' || item.length === 0) {
      fail(`${path}[${index}]`, 'must be a non-empty string');
    }
    return item;
  });
}

function ensureUrl(value: unknown, path: string): string {
  const str = ensureString(value, path);
  if (!URL_PATTERN.test(str)) {
    fail(path, `must be an https URL (got "${str}")`);
  }
  return str;
}

function ensureEnvVarName(value: unknown, path: string): string {
  const str = ensureString(value, path);
  // UPPER_SNAKE_CASE only — by construction this excludes lowercase, base64
  // padding, and other characters typical of raw credential values, so the
  // pattern check doubles as cheap secret-hygiene gate on env var slots.
  if (!ENV_VAR_PATTERN.test(str)) {
    fail(path, `must be an UPPER_SNAKE_CASE env var name (got "${str}")`);
  }
  return str;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function parseEntry(raw: unknown, basePath: string): ProviderCatalogEntry {
  if (!isPlainObject(raw)) fail(basePath, 'entry must be an object');

  const id = ensureString(raw.id, `${basePath}.id`);
  if (!ID_PATTERN.test(id)) {
    fail(`${basePath}.id`, `must match ${ID_PATTERN.source} (got "${id}")`);
  }
  const displayName = ensureString(raw.displayName, `${basePath}.displayName`);

  const accessClass = ensureString(raw.accessClass, `${basePath}.accessClass`);
  if (!ACCESS_CLASSES.has(accessClass)) {
    fail(`${basePath}.accessClass`, `unknown access class "${accessClass}"`);
  }
  const tier = ensureString(raw.tier, `${basePath}.tier`);
  if (!TIERS.has(tier)) {
    fail(`${basePath}.tier`, `unknown tier "${tier}"`);
  }
  const priority = ensureString(raw.priority, `${basePath}.priority`);
  if (!PRIORITIES.has(priority)) {
    fail(`${basePath}.priority`, `unknown priority "${priority}"`);
  }

  const coverage = ensureString(raw.coverage, `${basePath}.coverage`);

  const capabilities = ensureStringArray(raw.capabilities, `${basePath}.capabilities`);
  if (capabilities.length === 0) {
    fail(`${basePath}.capabilities`, 'must declare at least one capability');
  }
  for (const cap of capabilities) {
    if (!CAPABILITIES.has(cap)) fail(`${basePath}.capabilities`, `unknown capability "${cap}"`);
  }

  const authRaw = raw.auth;
  if (!isPlainObject(authRaw)) fail(`${basePath}.auth`, 'must be an object');
  const authMode = ensureString(authRaw.mode, `${basePath}.auth.mode`);
  if (!CREDENTIAL_MODES.has(authMode)) {
    fail(`${basePath}.auth.mode`, `unknown auth mode "${authMode}"`);
  }
  if (typeof authRaw.required !== 'boolean') {
    fail(`${basePath}.auth.required`, 'must be a boolean');
  }
  const profileFields = ensureStringArray(authRaw.profileFields ?? [], `${basePath}.auth.profileFields`);
  const envVars = (authRaw.envVars === undefined ? [] : ensureStringArray(authRaw.envVars, `${basePath}.auth.envVars`)).map(
    (name, idx) => ensureEnvVarName(name, `${basePath}.auth.envVars[${idx}]`),
  );
  if (authRaw.required === true && authMode === 'none') {
    fail(`${basePath}.auth`, 'required=true is incompatible with auth.mode "none"');
  }
  if (authRaw.required === true && envVars.length === 0 && profileFields.length === 0) {
    fail(`${basePath}.auth`, 'required=true must declare profileFields or envVars');
  }
  const authNotes = authRaw.notes === undefined ? undefined : ensureString(authRaw.notes, `${basePath}.auth.notes`);

  const costRaw = raw.cost;
  if (!isPlainObject(costRaw)) fail(`${basePath}.cost`, 'must be an object');
  const costModel = ensureString(costRaw.model, `${basePath}.cost.model`);
  if (!COST_MODELS.has(costModel)) {
    fail(`${basePath}.cost.model`, `unknown cost model "${costModel}"`);
  }
  const quotaNote = costRaw.quotaNote === undefined ? undefined : ensureString(costRaw.quotaNote, `${basePath}.cost.quotaNote`);

  const sourcesRaw = raw.sources;
  if (!isPlainObject(sourcesRaw)) fail(`${basePath}.sources`, 'must be an object');
  const sources: Record<string, string> = {};
  let urlCount = 0;
  for (const field of URL_FIELDS) {
    const value = sourcesRaw[field];
    if (value === undefined) continue;
    sources[field] = ensureUrl(value, `${basePath}.sources.${field}`);
    urlCount += 1;
  }
  if (urlCount === 0) {
    fail(`${basePath}.sources`, 'must include at least one URL (landingUrl, apiDocsUrl, signupUrl, termsUrl, or referenceUrl)');
  }

  const implementationStatus = ensureString(raw.implementationStatus, `${basePath}.implementationStatus`);
  if (!IMPL_STATUSES.has(implementationStatus)) {
    fail(`${basePath}.implementationStatus`, `unknown implementation status "${implementationStatus}"`);
  }

  const liveTestRaw = raw.liveTest;
  if (!isPlainObject(liveTestRaw)) fail(`${basePath}.liveTest`, 'must be an object');
  const enabledFlag = ensureEnvVarName(liveTestRaw.enabledFlagEnvVar, `${basePath}.liveTest.enabledFlagEnvVar`);
  if (!enabledFlag.startsWith('VESSEL_MCP_LIVE_TEST_')) {
    fail(
      `${basePath}.liveTest.enabledFlagEnvVar`,
      `must start with VESSEL_MCP_LIVE_TEST_ (got "${enabledFlag}")`,
    );
  }
  const requiredEnvVars = ensureStringArray(
    liveTestRaw.requiredEnvVars ?? [],
    `${basePath}.liveTest.requiredEnvVars`,
  ).map((name, idx) => ensureEnvVarName(name, `${basePath}.liveTest.requiredEnvVars[${idx}]`));
  if (liveTestRaw.defaultDisabled !== true) {
    fail(`${basePath}.liveTest.defaultDisabled`, 'live tests must declare defaultDisabled=true');
  }
  const liveTestNotes =
    liveTestRaw.notes === undefined ? undefined : ensureString(liveTestRaw.notes, `${basePath}.liveTest.notes`);

  const captureEligibility = ensureString(raw.captureEligibility, `${basePath}.captureEligibility`);
  if (!CAPTURE_ELIGIBILITY.has(captureEligibility)) {
    fail(`${basePath}.captureEligibility`, `unknown capture eligibility "${captureEligibility}"`);
  }

  const notes = raw.notes === undefined ? undefined : ensureString(raw.notes, `${basePath}.notes`);

  return Object.freeze({
    id,
    displayName,
    accessClass: accessClass as ProviderAccessClass,
    tier: tier as ProviderTier,
    priority: priority as CatalogPriority,
    coverage,
    capabilities: Object.freeze(capabilities as ProviderCapability[]) as readonly ProviderCapability[],
    auth: Object.freeze({
      mode: authMode as CredentialMode,
      required: authRaw.required,
      profileFields: Object.freeze(profileFields) as readonly string[],
      envVars: Object.freeze(envVars) as readonly string[],
      notes: authNotes,
    }),
    cost: Object.freeze({ model: costModel as CatalogCostModel, quotaNote }),
    sources: Object.freeze(sources) as CatalogSources,
    implementationStatus: implementationStatus as CatalogImplementationStatus,
    liveTest: Object.freeze({
      enabledFlagEnvVar: enabledFlag,
      requiredEnvVars: Object.freeze(requiredEnvVars) as readonly string[],
      defaultDisabled: true as const,
      notes: liveTestNotes,
    }),
    captureEligibility: captureEligibility as CaptureEligibility,
    notes,
  });
}

export interface ParseProviderCatalogOptions {
  readonly path?: string;
}

export function parseProviderCatalog(rawText: string, options: ParseProviderCatalogOptions = {}): ProviderCatalog {
  const path = options.path ?? '<inline>';

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawText);
  } catch (error) {
    const reason = error instanceof Error ? error.message : 'unknown JSON error';
    fail(path, `is not valid JSON: ${reason}`);
  }

  if (!isPlainObject(parsed)) {
    fail(path, 'must be a JSON object');
  }
  if (parsed.version !== 1) {
    fail(`${path}.version`, 'must be 1');
  }
  const generatedAt = ensureString(parsed.generatedAt, `${path}.generatedAt`);
  if (Number.isNaN(Date.parse(generatedAt))) {
    fail(`${path}.generatedAt`, 'must be an ISO-8601 timestamp');
  }
  const sourceDoc = ensureString(parsed.sourceDoc, `${path}.sourceDoc`);

  if (!Array.isArray(parsed.entries)) {
    fail(`${path}.entries`, 'must be an array');
  }
  if (parsed.entries.length === 0) {
    fail(`${path}.entries`, 'must declare at least one provider');
  }

  const entries: ProviderCatalogEntry[] = [];
  const seenIds = new Set<string>();
  for (let i = 0; i < parsed.entries.length; i += 1) {
    const entry = parseEntry(parsed.entries[i], `${path}.entries[${i}]`);
    if (seenIds.has(entry.id)) {
      fail(`${path}.entries[${i}].id`, `duplicate provider id "${entry.id}"`);
    }
    seenIds.add(entry.id);
    entries.push(entry);
  }

  return Object.freeze({
    version: 1,
    generatedAt,
    sourceDoc,
    entries: Object.freeze(entries) as readonly ProviderCatalogEntry[],
  });
}

export function loadProviderCatalog(path: string): ProviderCatalog {
  const text = readFileSync(path, 'utf8');
  return parseProviderCatalog(text, { path });
}

export function findCatalogEntry(catalog: ProviderCatalog, id: string): ProviderCatalogEntry | undefined {
  return catalog.entries.find((entry) => entry.id === id);
}

export function catalogEntriesByCapability(
  catalog: ProviderCatalog,
  capability: ProviderCapability,
): readonly ProviderCatalogEntry[] {
  return catalog.entries.filter((entry) => entry.capabilities.includes(capability));
}

export const discoveryGateValues = ['adapter', 'capture'] as const;

export type DiscoveryGate = (typeof discoveryGateValues)[number];

export const discoveryIssueCodeValues = [
  'unknown_provider',
  'missing_source_urls',
  'missing_implementation_status',
  'discovery_only_blocks_adapter',
  'capture_only_blocks_adapter',
  'missing_auth_mode',
  'missing_auth_credentials',
  'byok_profile_missing_fields',
  'missing_documented_terms',
  'capture_blocked_by_terms',
  'capture_eligibility_unknown',
] as const;

export type DiscoveryIssueCode = (typeof discoveryIssueCodeValues)[number];

export interface DiscoveryValidationIssue {
  readonly path: string;
  readonly code: DiscoveryIssueCode;
  readonly message: string;
}

export interface DiscoveryValidationResult {
  readonly providerId: string;
  readonly gate: DiscoveryGate;
  readonly ok: boolean;
  readonly issues: readonly DiscoveryValidationIssue[];
}

function countSourceUrls(entry: ProviderCatalogEntry): number {
  let count = 0;
  for (const field of URL_FIELDS) {
    if (typeof entry.sources[field] === 'string' && entry.sources[field]!.length > 0) {
      count += 1;
    }
  }
  return count;
}

function collectIssues(entry: ProviderCatalogEntry, gate: DiscoveryGate): DiscoveryValidationIssue[] {
  const issues: DiscoveryValidationIssue[] = [];

  if (countSourceUrls(entry) === 0) {
    issues.push({
      path: 'sources',
      code: 'missing_source_urls',
      message: `${entry.id}: at least one source URL (apiDocsUrl, landingUrl, signupUrl, termsUrl, or referenceUrl) must be documented before starting ${gate} work`,
    });
  }

  if (!IMPL_STATUSES.has(entry.implementationStatus)) {
    issues.push({
      path: 'implementationStatus',
      code: 'missing_implementation_status',
      message: `${entry.id}: implementationStatus is not declared in the catalog`,
    });
  }

  if (!CREDENTIAL_MODES.has(entry.auth.mode)) {
    issues.push({
      path: 'auth.mode',
      code: 'missing_auth_mode',
      message: `${entry.id}: auth.mode is not declared`,
    });
  }

  if (entry.auth.required && entry.auth.profileFields.length === 0 && entry.auth.envVars.length === 0) {
    issues.push({
      path: 'auth',
      code: 'missing_auth_credentials',
      message: `${entry.id}: auth.required=true but no profileFields or envVars are documented`,
    });
  }

  if (entry.auth.mode === 'byok-profile' && entry.auth.required && entry.auth.profileFields.length === 0) {
    issues.push({
      path: 'auth.profileFields',
      code: 'byok_profile_missing_fields',
      message: `${entry.id}: byok-profile mode requires at least one auth.profileFields entry so the credential profile loader can find the key`,
    });
  }

  const termsDocumented =
    typeof entry.sources.termsUrl === 'string' || entry.captureEligibility !== 'unknown';
  if (!termsDocumented) {
    issues.push({
      path: 'sources.termsUrl',
      code: 'missing_documented_terms',
      message: `${entry.id}: terms are undocumented — declare sources.termsUrl or set captureEligibility to a non-"unknown" value`,
    });
  }

  if (gate === 'adapter') {
    if (entry.implementationStatus === 'discovery_only') {
      issues.push({
        path: 'implementationStatus',
        code: 'discovery_only_blocks_adapter',
        message: `${entry.id}: implementationStatus="discovery_only" means this provider is catalog-only; adapter work is not authorized until status is updated`,
      });
    }
    if (entry.implementationStatus === 'capture_only') {
      issues.push({
        path: 'implementationStatus',
        code: 'capture_only_blocks_adapter',
        message: `${entry.id}: implementationStatus="capture_only" means only sanitized capture is authorized; do not start adapter implementation`,
      });
    }
  }

  if (gate === 'capture') {
    if (entry.captureEligibility === 'blocked') {
      issues.push({
        path: 'captureEligibility',
        code: 'capture_blocked_by_terms',
        message: `${entry.id}: captureEligibility="blocked" — terms forbid web UI capture for this provider`,
      });
    }
    if (entry.captureEligibility === 'unknown') {
      issues.push({
        path: 'captureEligibility',
        code: 'capture_eligibility_unknown',
        message: `${entry.id}: captureEligibility is "unknown"; review the provider terms and set an explicit value before starting capture`,
      });
    }
  }

  return issues;
}

export function validateProviderForDiscovery(
  entry: ProviderCatalogEntry,
  gate: DiscoveryGate,
): DiscoveryValidationResult {
  const issues = collectIssues(entry, gate);
  return Object.freeze({
    providerId: entry.id,
    gate,
    ok: issues.length === 0,
    issues: Object.freeze(issues) as readonly DiscoveryValidationIssue[],
  });
}

export function validateProviderForDiscoveryInCatalog(
  catalog: ProviderCatalog,
  providerId: string,
  gate: DiscoveryGate,
): DiscoveryValidationResult {
  const entry = findCatalogEntry(catalog, providerId);
  if (!entry) {
    return Object.freeze({
      providerId,
      gate,
      ok: false,
      issues: Object.freeze([
        {
          path: 'catalog',
          code: 'unknown_provider' as const,
          message: `provider "${providerId}" is not declared in the catalog; add a catalog entry with terms, auth, source URLs, and implementation status before starting ${gate} work`,
        },
      ]) as readonly DiscoveryValidationIssue[],
    });
  }
  return validateProviderForDiscovery(entry, gate);
}

export class ProviderDiscoveryValidationError extends Error {
  readonly providerId: string;
  readonly gate: DiscoveryGate;
  readonly issues: readonly DiscoveryValidationIssue[];

  constructor(result: DiscoveryValidationResult) {
    const summary = result.issues.map((issue) => `[${issue.code}] ${issue.message}`).join('; ');
    super(
      `provider "${result.providerId}" is not ready for ${result.gate} work: ${summary || 'no specific issue recorded'}`,
    );
    this.name = 'ProviderDiscoveryValidationError';
    this.providerId = result.providerId;
    this.gate = result.gate;
    this.issues = result.issues;
  }
}

export function assertProviderReadyForDiscovery(
  catalog: ProviderCatalog,
  providerId: string,
  gate: DiscoveryGate,
): ProviderCatalogEntry {
  const result = validateProviderForDiscoveryInCatalog(catalog, providerId, gate);
  if (!result.ok) {
    throw new ProviderDiscoveryValidationError(result);
  }
  const entry = findCatalogEntry(catalog, providerId);
  if (!entry) {
    throw new ProviderDiscoveryValidationError(result);
  }
  return entry;
}
