/**
 * Display-only time formatting for Ops.
 *
 * Collector payloads and cursor values remain canonical UTC instants. This is
 * called only for visible labels and popups; it never rewrites frames or
 * iterates map features. Account settings can later call
 * setOpsDisplayTimeZone() after profile hydration.
 */

export const DEFAULT_OPS_DISPLAY_TIME_ZONE = 'America/Los_Angeles';

let accountTimeZone = null;

export function setOpsDisplayTimeZone(timeZone) {
  const candidate = String(timeZone || '').trim();
  if (!candidate) {
    accountTimeZone = null;
    return;
  }
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: candidate }).format();
    accountTimeZone = candidate;
  } catch (_) {
    accountTimeZone = null;
  }
}

export function getOpsDisplayTimeZone() {
  return accountTimeZone || DEFAULT_OPS_DISPLAY_TIME_ZONE;
}

export function formatOpsTime(value, options = {}) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    ...(options.includeYear ? { year: 'numeric' } : {}),
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
    timeZone: getOpsDisplayTimeZone(),
    ...options,
  }).format(date);
}
