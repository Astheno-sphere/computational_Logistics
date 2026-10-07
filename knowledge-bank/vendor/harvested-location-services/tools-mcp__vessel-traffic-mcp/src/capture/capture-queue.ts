import { readFileSync } from 'node:fs';

import type { ProviderCatalog } from '../providers/catalog.js';
import {
  SITE_PROFILE_FORMAT_VERSION,
  validateSiteProfile,
  type SiteProfile,
} from './site-profile.js';

export const CAPTURE_SITES_FORMAT_VERSION = 1;
export const CAPTURE_QUEUE_FORMAT_VERSION = 1;

export const captureQueueStatusValues = [
  'pending-terms-review',
  'authorized',
  'paused',
  'blocked',
] as const;

export type CaptureQueueStatus = (typeof captureQueueStatusValues)[number];

export interface CaptureSiteProfile extends SiteProfile {
  /** Catalog providerId this profile belongs to. */
  readonly providerId: string;
}

export interface CaptureSitesFile {
  readonly version: number;
  readonly generatedAt: string;
  readonly sourceDoc: string;
  readonly notes: readonly string[];
  readonly profiles: readonly CaptureSiteProfile[];
}

export interface CaptureQueueEntry {
  readonly providerId: string;
  readonly siteProfileId: string;
  readonly status: CaptureQueueStatus;
  readonly priority: 'P0' | 'P1' | 'P2' | 'P3';
  readonly rationale: string;
  readonly captureAuthorizedAt: string | null;
  readonly authorizedBy: string | null;
}

export interface CaptureQueueFile {
  readonly version: number;
  readonly generatedAt: string;
  readonly sourceDoc: string;
  readonly notes: readonly string[];
  readonly entries: readonly CaptureQueueEntry[];
}

export class CaptureQueueError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CaptureQueueError';
  }
}

const STATUS_SET = new Set<string>(captureQueueStatusValues);
const PRIORITY_SET = new Set<string>(['P0', 'P1', 'P2', 'P3']);
const ID_PATTERN = /^[a-z0-9][a-z0-9.\-]*[a-z0-9]$/;

function fail(path: string, message: string): never {
  throw new CaptureQueueError(`${path}: ${message}`);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function ensureString(value: unknown, path: string): string {
  if (typeof value !== 'string' || value.length === 0) {
    fail(path, 'must be a non-empty string');
  }
  return value;
}

function ensureStringArray(value: unknown, path: string): string[] {
  if (!Array.isArray(value)) fail(path, 'must be an array');
  return value.map((item, idx) => {
    if (typeof item !== 'string' || item.length === 0) {
      fail(`${path}[${idx}]`, 'must be a non-empty string');
    }
    return item;
  });
}

export function parseCaptureSites(raw: string, path = 'capture-sites'): CaptureSitesFile {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new CaptureQueueError(
      `${path}: invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (!isPlainObject(parsed)) fail(path, 'must be a JSON object');
  const version = parsed.version;
  if (version !== CAPTURE_SITES_FORMAT_VERSION) {
    fail(
      `${path}.version`,
      `unsupported capture-sites version ${String(version)}; expected ${CAPTURE_SITES_FORMAT_VERSION}`,
    );
  }
  const generatedAt = ensureString(parsed.generatedAt, `${path}.generatedAt`);
  const sourceDoc = ensureString(parsed.sourceDoc, `${path}.sourceDoc`);
  const notes = parsed.notes === undefined ? [] : ensureStringArray(parsed.notes, `${path}.notes`);
  const profilesRaw = parsed.profiles;
  if (!Array.isArray(profilesRaw) || profilesRaw.length === 0) {
    fail(`${path}.profiles`, 'must be a non-empty array');
  }

  const seenIds = new Set<string>();
  const profiles: CaptureSiteProfile[] = [];
  for (let i = 0; i < profilesRaw.length; i += 1) {
    const basePath = `${path}.profiles[${i}]`;
    const profile = profilesRaw[i];
    if (!isPlainObject(profile)) fail(basePath, 'must be an object');
    const id = ensureString(profile.id, `${basePath}.id`);
    if (!ID_PATTERN.test(id)) fail(`${basePath}.id`, `must match ${ID_PATTERN.source} (got "${id}")`);
    if (seenIds.has(id)) fail(`${basePath}.id`, `duplicate site profile id "${id}"`);
    seenIds.add(id);
    const providerId = ensureString(profile.providerId, `${basePath}.providerId`);
    if (!ID_PATTERN.test(providerId)) {
      fail(`${basePath}.providerId`, `must match ${ID_PATTERN.source} (got "${providerId}")`);
    }
    const siteProfile = profile as unknown as SiteProfile;
    const errors = validateSiteProfile(siteProfile);
    if (errors.length > 0) {
      fail(basePath, `site profile invalid: ${errors.map((e) => `${e.code}: ${e.message}`).join('; ')}`);
    }
    if (siteProfile.version !== SITE_PROFILE_FORMAT_VERSION) {
      fail(`${basePath}.version`, `unsupported site profile version ${siteProfile.version}`);
    }
    if (siteProfile.termsReviewStatus === 'allowed') {
      fail(
        `${basePath}.termsReviewStatus`,
        'committed example profiles must NOT default to "allowed"; use "needs-terms-review" or "blocked"',
      );
    }
    if (siteProfile.pacing.minStepIntervalMs < 1000) {
      fail(
        `${basePath}.pacing.minStepIntervalMs`,
        `committed example profiles must throttle to >=1000ms between steps (got ${siteProfile.pacing.minStepIntervalMs})`,
      );
    }
    if (siteProfile.pacing.maxConcurrent !== 1) {
      fail(
        `${basePath}.pacing.maxConcurrent`,
        `committed example profiles must use maxConcurrent=1 (got ${siteProfile.pacing.maxConcurrent})`,
      );
    }
    if (!siteProfile.forbiddenActions || siteProfile.forbiddenActions.length === 0) {
      fail(`${basePath}.forbiddenActions`, 'must declare at least one forbidden destructive/auth action');
    }
    if (!siteProfile.sessionLossIndicators || siteProfile.sessionLossIndicators.length === 0) {
      fail(`${basePath}.sessionLossIndicators`, 'must declare at least one session-loss indicator');
    }
    profiles.push(
      Object.freeze({ ...siteProfile, providerId }) as CaptureSiteProfile,
    );
  }

  return Object.freeze({
    version,
    generatedAt,
    sourceDoc,
    notes: Object.freeze(notes) as readonly string[],
    profiles: Object.freeze(profiles) as readonly CaptureSiteProfile[],
  });
}

export function parseCaptureQueue(raw: string, path = 'capture-queue'): CaptureQueueFile {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new CaptureQueueError(
      `${path}: invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (!isPlainObject(parsed)) fail(path, 'must be a JSON object');
  const version = parsed.version;
  if (version !== CAPTURE_QUEUE_FORMAT_VERSION) {
    fail(
      `${path}.version`,
      `unsupported capture-queue version ${String(version)}; expected ${CAPTURE_QUEUE_FORMAT_VERSION}`,
    );
  }
  const generatedAt = ensureString(parsed.generatedAt, `${path}.generatedAt`);
  const sourceDoc = ensureString(parsed.sourceDoc, `${path}.sourceDoc`);
  const notes = parsed.notes === undefined ? [] : ensureStringArray(parsed.notes, `${path}.notes`);
  const entriesRaw = parsed.entries;
  if (!Array.isArray(entriesRaw) || entriesRaw.length === 0) {
    fail(`${path}.entries`, 'must be a non-empty array');
  }

  const seen = new Set<string>();
  const entries: CaptureQueueEntry[] = [];
  for (let i = 0; i < entriesRaw.length; i += 1) {
    const basePath = `${path}.entries[${i}]`;
    const entry = entriesRaw[i];
    if (!isPlainObject(entry)) fail(basePath, 'must be an object');

    const providerId = ensureString(entry.providerId, `${basePath}.providerId`);
    const siteProfileId = ensureString(entry.siteProfileId, `${basePath}.siteProfileId`);
    const key = `${providerId}::${siteProfileId}`;
    if (seen.has(key)) fail(basePath, `duplicate provider/site pairing "${key}"`);
    seen.add(key);

    const status = ensureString(entry.status, `${basePath}.status`);
    if (!STATUS_SET.has(status)) {
      fail(`${basePath}.status`, `unknown queue status "${status}"`);
    }
    const priority = ensureString(entry.priority, `${basePath}.priority`);
    if (!PRIORITY_SET.has(priority)) {
      fail(`${basePath}.priority`, `unknown priority "${priority}"`);
    }
    const rationale = ensureString(entry.rationale, `${basePath}.rationale`);

    let captureAuthorizedAt: string | null = null;
    if (entry.captureAuthorizedAt === null || entry.captureAuthorizedAt === undefined) {
      captureAuthorizedAt = null;
    } else if (typeof entry.captureAuthorizedAt === 'string') {
      // Loose ISO-8601 check (matches Date.parse-able values).
      if (Number.isNaN(Date.parse(entry.captureAuthorizedAt))) {
        fail(`${basePath}.captureAuthorizedAt`, 'must be null or an ISO timestamp');
      }
      captureAuthorizedAt = entry.captureAuthorizedAt;
    } else {
      fail(`${basePath}.captureAuthorizedAt`, 'must be null or an ISO timestamp string');
    }

    let authorizedBy: string | null = null;
    if (entry.authorizedBy === null || entry.authorizedBy === undefined) {
      authorizedBy = null;
    } else if (typeof entry.authorizedBy === 'string' && entry.authorizedBy.length > 0) {
      authorizedBy = entry.authorizedBy;
    } else {
      fail(`${basePath}.authorizedBy`, 'must be null or a non-empty string');
    }

    if (status === 'authorized') {
      if (captureAuthorizedAt === null || authorizedBy === null) {
        fail(
          basePath,
          'status="authorized" requires captureAuthorizedAt and authorizedBy to be populated',
        );
      }
    } else if (status !== 'blocked') {
      if (captureAuthorizedAt !== null || authorizedBy !== null) {
        fail(
          basePath,
          `status="${status}" must have captureAuthorizedAt and authorizedBy = null (use status="authorized" only after operator sign-off)`,
        );
      }
    }

    entries.push(
      Object.freeze({
        providerId,
        siteProfileId,
        status: status as CaptureQueueStatus,
        priority: priority as CaptureQueueEntry['priority'],
        rationale,
        captureAuthorizedAt,
        authorizedBy,
      }),
    );
  }

  return Object.freeze({
    version,
    generatedAt,
    sourceDoc,
    notes: Object.freeze(notes) as readonly string[],
    entries: Object.freeze(entries) as readonly CaptureQueueEntry[],
  });
}

export interface CrossReferenceOptions {
  /** When provided, every queue providerId must appear in the catalog. */
  readonly catalog?: ProviderCatalog;
  /** When true, every catalog entry with captureEligibility != "allowed" must have a queue entry. */
  readonly requireCoverage?: boolean;
}

export interface CrossReferenceIssue {
  readonly code:
    | 'unknown-site'
    | 'site-provider-mismatch'
    | 'unknown-provider'
    | 'capture-disallowed'
    | 'missing-queue-entry';
  readonly message: string;
}

export function crossReferenceCaptureQueue(
  sites: CaptureSitesFile,
  queue: CaptureQueueFile,
  options: CrossReferenceOptions = {},
): CrossReferenceIssue[] {
  const issues: CrossReferenceIssue[] = [];
  const sitesById = new Map<string, CaptureSiteProfile>();
  for (const profile of sites.profiles) sitesById.set(profile.id, profile);

  const catalogById = new Map<string, ProviderCatalog['entries'][number]>();
  if (options.catalog) {
    for (const entry of options.catalog.entries) catalogById.set(entry.id, entry);
  }

  for (const entry of queue.entries) {
    const site = sitesById.get(entry.siteProfileId);
    if (!site) {
      issues.push({
        code: 'unknown-site',
        message: `queue entry providerId=${entry.providerId} references unknown siteProfileId "${entry.siteProfileId}"`,
      });
      continue;
    }
    if (site.providerId !== entry.providerId) {
      issues.push({
        code: 'site-provider-mismatch',
        message: `queue entry providerId=${entry.providerId} does not match site profile providerId=${site.providerId} (site=${site.id})`,
      });
    }
    if (options.catalog) {
      const catalogEntry = catalogById.get(entry.providerId);
      if (!catalogEntry) {
        issues.push({
          code: 'unknown-provider',
          message: `queue entry providerId="${entry.providerId}" is not present in the provider catalog`,
        });
      } else if (
        entry.status !== 'blocked' &&
        catalogEntry.captureEligibility === 'blocked'
      ) {
        issues.push({
          code: 'capture-disallowed',
          message: `provider "${entry.providerId}" has catalog captureEligibility="blocked" but queue status="${entry.status}"`,
        });
      }
    }
  }

  if (options.catalog && options.requireCoverage) {
    const queueProviderIds = new Set(queue.entries.map((e) => e.providerId));
    for (const catalogEntry of options.catalog.entries) {
      if (catalogEntry.captureEligibility === 'needs-terms-review' && !queueProviderIds.has(catalogEntry.id)) {
        issues.push({
          code: 'missing-queue-entry',
          message: `catalog provider "${catalogEntry.id}" has captureEligibility="needs-terms-review" but is missing from the capture queue`,
        });
      }
    }
  }

  return issues;
}

export function loadCaptureSitesFromDisk(path: string): CaptureSitesFile {
  return parseCaptureSites(readFileSync(path, 'utf8'), path);
}

export function loadCaptureQueueFromDisk(path: string): CaptureQueueFile {
  return parseCaptureQueue(readFileSync(path, 'utf8'), path);
}
