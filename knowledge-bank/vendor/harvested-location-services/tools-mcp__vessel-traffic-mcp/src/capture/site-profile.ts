export const SITE_PROFILE_FORMAT_VERSION = 1;

export type CaptureEligibility = 'allowed' | 'needs-terms-review' | 'blocked';

export type SessionLossKind = 'url-redirect' | 'status-code' | 'response-header' | 'response-body';

export interface SessionLossIndicator {
  kind: SessionLossKind;
  pattern: string;
  description: string;
}

export interface ForbiddenAction {
  pattern: string;
  description: string;
}

export interface PacingPolicy {
  minStepIntervalMs: number;
  maxStepsPerRun: number;
  maxConcurrent: number;
}

export interface SiteProfile {
  version: number;
  id: string;
  displayName: string;
  termsReviewStatus: CaptureEligibility;
  baseUrl: string;
  allowedOrigins: string[];
  forbiddenActions: ForbiddenAction[];
  sessionLossIndicators: SessionLossIndicator[];
  pacing: PacingPolicy;
  notes: string[];
}

export interface SiteProfileValidationError {
  code: string;
  message: string;
}

export class SiteProfileError extends Error {
  constructor(message: string, public readonly errors: SiteProfileValidationError[] = []) {
    super(message);
    this.name = 'SiteProfileError';
  }
}

const SESSION_LOSS_KINDS: ReadonlySet<SessionLossKind> = new Set([
  'url-redirect',
  'status-code',
  'response-header',
  'response-body',
]);

export function validateSiteProfile(profile: SiteProfile): SiteProfileValidationError[] {
  const errors: SiteProfileValidationError[] = [];
  if (profile.version !== SITE_PROFILE_FORMAT_VERSION) {
    errors.push({
      code: 'version',
      message: `unsupported site-profile version ${String(profile.version)}; expected ${SITE_PROFILE_FORMAT_VERSION}`,
    });
  }
  if (typeof profile.id !== 'string' || profile.id.trim().length === 0) {
    errors.push({ code: 'id', message: 'site profile id is required' });
  }
  if (typeof profile.displayName !== 'string' || profile.displayName.trim().length === 0) {
    errors.push({ code: 'displayName', message: 'site profile displayName is required' });
  }
  if (
    profile.termsReviewStatus !== 'allowed' &&
    profile.termsReviewStatus !== 'needs-terms-review' &&
    profile.termsReviewStatus !== 'blocked'
  ) {
    errors.push({
      code: 'termsReviewStatus',
      message: 'termsReviewStatus must be allowed | needs-terms-review | blocked',
    });
  }
  if (!Array.isArray(profile.allowedOrigins) || profile.allowedOrigins.length === 0) {
    errors.push({ code: 'allowedOrigins', message: 'at least one allowed origin must be defined' });
  } else {
    for (const origin of profile.allowedOrigins) {
      try {
        const u = new URL(origin);
        if (`${u.protocol}//${u.host}` !== origin) {
          errors.push({
            code: 'allowedOrigins',
            message: `allowedOrigins entry "${origin}" must be canonical (scheme://host[:port])`,
          });
        }
      } catch {
        errors.push({ code: 'allowedOrigins', message: `allowedOrigins entry "${origin}" is not a valid URL` });
      }
    }
  }
  if (!Array.isArray(profile.forbiddenActions)) {
    errors.push({ code: 'forbiddenActions', message: 'forbiddenActions must be an array' });
  }
  if (!Array.isArray(profile.sessionLossIndicators)) {
    errors.push({ code: 'sessionLossIndicators', message: 'sessionLossIndicators must be an array' });
  } else {
    for (const indicator of profile.sessionLossIndicators) {
      if (!SESSION_LOSS_KINDS.has(indicator?.kind)) {
        errors.push({
          code: 'sessionLossIndicators',
          message: `sessionLossIndicators kind must be one of ${[...SESSION_LOSS_KINDS].join('|')}`,
        });
      }
      if (typeof indicator?.pattern !== 'string' || indicator.pattern.length === 0) {
        errors.push({
          code: 'sessionLossIndicators',
          message: 'sessionLossIndicators.pattern is required',
        });
      }
    }
  }
  if (!profile.pacing || typeof profile.pacing !== 'object') {
    errors.push({ code: 'pacing', message: 'pacing policy is required' });
  } else {
    if (!Number.isFinite(profile.pacing.minStepIntervalMs) || profile.pacing.minStepIntervalMs < 0) {
      errors.push({ code: 'pacing', message: 'pacing.minStepIntervalMs must be a non-negative number' });
    }
    if (!Number.isInteger(profile.pacing.maxStepsPerRun) || profile.pacing.maxStepsPerRun <= 0) {
      errors.push({ code: 'pacing', message: 'pacing.maxStepsPerRun must be a positive integer' });
    }
    if (!Number.isInteger(profile.pacing.maxConcurrent) || profile.pacing.maxConcurrent <= 0) {
      errors.push({ code: 'pacing', message: 'pacing.maxConcurrent must be a positive integer' });
    }
  }
  return errors;
}

export function loadSiteProfile(raw: string): SiteProfile {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new SiteProfileError(
      `site profile JSON is invalid: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (!parsed || typeof parsed !== 'object') {
    throw new SiteProfileError('site profile must be a JSON object');
  }
  const profile = parsed as SiteProfile;
  const errors = validateSiteProfile(profile);
  if (errors.length > 0) {
    throw new SiteProfileError(
      `site profile is invalid: ${errors.map((e) => `${e.code}: ${e.message}`).join('; ')}`,
      errors,
    );
  }
  return profile;
}

export function originOf(url: string): string | null {
  try {
    const u = new URL(url);
    return `${u.protocol}//${u.host}`;
  } catch {
    return null;
  }
}

export function isOriginAllowed(profile: SiteProfile, url: string): boolean {
  const origin = originOf(url);
  if (origin === null) return false;
  return profile.allowedOrigins.includes(origin);
}

export function assertOriginAllowed(profile: SiteProfile, url: string): void {
  if (!isOriginAllowed(profile, url)) {
    const origin = originOf(url) ?? '<unparsable>';
    throw new SiteProfileError(
      `capture-workflow: origin "${origin}" is not in allowedOrigins for profile "${profile.id}"`,
    );
  }
}

export function findForbiddenAction(profile: SiteProfile, url: string): ForbiddenAction | null {
  for (const action of profile.forbiddenActions ?? []) {
    if (typeof action.pattern === 'string' && action.pattern.length > 0 && url.includes(action.pattern)) {
      return action;
    }
  }
  return null;
}

export function assertActionAllowed(profile: SiteProfile, url: string): void {
  const blocked = findForbiddenAction(profile, url);
  if (blocked) {
    throw new SiteProfileError(
      `capture-workflow: step "${url}" matches forbidden action "${blocked.pattern}" (${blocked.description})`,
    );
  }
}

export interface SessionLossSignal {
  indicator: SessionLossIndicator;
  source: string;
}

export interface RecordedExchangeLike {
  url: string;
  response: {
    status: number;
    headers?: { name: string; value: string }[];
    body?: string;
  };
}

export function detectSessionLoss(
  profile: SiteProfile,
  exchange: RecordedExchangeLike,
): SessionLossSignal | null {
  for (const indicator of profile.sessionLossIndicators ?? []) {
    switch (indicator.kind) {
      case 'url-redirect':
        if (exchange.url.includes(indicator.pattern)) {
          return { indicator, source: `url:${exchange.url}` };
        }
        break;
      case 'status-code':
        if (String(exchange.response.status) === indicator.pattern) {
          return { indicator, source: `status:${exchange.response.status}` };
        }
        break;
      case 'response-header':
        for (const h of exchange.response.headers ?? []) {
          const nameMatch = h.name.toLowerCase() === indicator.pattern.toLowerCase();
          if (nameMatch || `${h.name}: ${h.value}`.includes(indicator.pattern)) {
            return { indicator, source: `header:${h.name}` };
          }
        }
        break;
      case 'response-body':
        if (typeof exchange.response.body === 'string' && exchange.response.body.includes(indicator.pattern)) {
          return { indicator, source: 'body' };
        }
        break;
    }
  }
  return null;
}
