'use strict';

const fs = require('fs');
const path = require('path');

// Verdicts a human or AI can record about an endpoint's diagnosis.
// `suppress` verdicts mean "this is fine, stop flagging it"; `confirm` verdicts
// mean "this is a real problem, keep flagging it (and trust it more)".
const SUPPRESS_VERDICTS = new Set(['expected', 'ignore', 'known_gate', 'ok']);
const CONFIRM_VERDICTS = new Set(['bug', 'real_bug', 'confirm']);
const VALID_VERDICTS = new Set([...SUPPRESS_VERDICTS, ...CONFIRM_VERDICTS]);

function effectFor(verdict) {
  return SUPPRESS_VERDICTS.has(verdict) ? 'suppress' : 'confirm';
}

function feedbackPath(config) {
  if (config && config.feedbackFile) return config.feedbackFile;
  const dir = (config && config.output && config.output.dir) || '.qaprobe';
  return path.join(dir, 'feedback.json');
}

function emptyStore() {
  return { version: 1, labels: {} };
}

function loadFeedback(config) {
  const p = feedbackPath(config);
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf8'));
    if (data && typeof data === 'object' && data.labels && typeof data.labels === 'object') {
      return { version: data.version || 1, labels: data.labels };
    }
  } catch {
    /* missing or invalid file → empty store */
  }
  return emptyStore();
}

function saveFeedback(store, config) {
  const p = feedbackPath(config);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(store, null, 2));
  return p;
}

function normalizeVerdict(verdict) {
  const v = String(verdict || '').trim().toLowerCase();
  return VALID_VERDICTS.has(v) ? v : null;
}

/**
 * Record a label for an endpoint and persist it.
 * `signal` is the rootCause the label applies to (the honesty guard): the label
 * is only reapplied while the endpoint still produces that same rootCause, so a
 * "this empty result is expected" label can never hide a later 500.
 * `signal: 'any'` applies regardless of the observed rootCause.
 */
function addLabel(config, { endpoint, verdict, reason, by, signal } = {}) {
  const v = normalizeVerdict(verdict);
  if (!endpoint || typeof endpoint !== 'string') {
    throw new Error('endpoint is required, e.g. "GET /alerts"');
  }
  if (!v) {
    throw new Error(`Invalid verdict "${verdict}". Use one of: ${[...VALID_VERDICTS].join(', ')}`);
  }
  const store = loadFeedback(config);
  const label = {
    verdict: v,
    effect: effectFor(v),
    reason: reason || null,
    by: by || 'unknown',
    at: new Date().toISOString(),
    signal: signal || 'any',
  };
  store.labels[endpoint] = label;
  const savedPath = saveFeedback(store, config);
  return { endpoint, label, path: savedPath };
}

/**
 * Return the label for an endpoint only if it still applies to the current
 * rootCause (or the label is signal-agnostic). Stale labels return null so a
 * changed behavior re-surfaces instead of being silently suppressed.
 */
function applicableLabel(store, endpointKey, currentRootCause) {
  const label = store && store.labels && store.labels[endpointKey];
  if (!label) return null;
  if (label.signal && label.signal !== 'any' && label.signal !== currentRootCause) return null;
  return label;
}

/**
 * Apply persisted feedback onto the classified causes (mutates in place).
 * - suppress → reclassify as `acknowledged` (a non-issue) with provenance
 * - confirm  → keep the diagnosis but mark it confirmed and high-confidence
 * Returns the list of applied records for a transparent report summary.
 */
function applyFeedback(endpointRootCauses, config) {
  const store = loadFeedback(config);
  const applied = [];
  for (const [key, cause] of Object.entries(endpointRootCauses || {})) {
    if (!cause) continue;
    const label = applicableLabel(store, key, cause.rootCause);
    if (!label) continue;

    const priorRootCause = cause.rootCause;
    cause.feedback = { verdict: label.verdict, reason: label.reason, by: label.by, at: label.at };

    if (label.effect === 'suppress') {
      cause.priorRootCause = priorRootCause;
      cause.rootCause = 'acknowledged';
      cause.confidence = 'high';
      cause.acknowledged = true;
      cause.rootCauseDetail =
        `${key} — acknowledged via feedback by ${label.by}` +
        (label.reason ? `: ${label.reason}` : '') +
        ` (was ${priorRootCause}). Auto-revoked if the observed result changes.`;
      cause.fixHint = null;
    } else {
      cause.confirmed = true;
      cause.confidence = 'high';
    }

    applied.push({
      endpoint: key,
      verdict: label.verdict,
      effect: label.effect,
      by: label.by,
      reason: label.reason,
      priorRootCause,
    });
  }
  return applied;
}

module.exports = {
  loadFeedback,
  saveFeedback,
  addLabel,
  applicableLabel,
  applyFeedback,
  feedbackPath,
  normalizeVerdict,
  VALID_VERDICTS,
  SUPPRESS_VERDICTS,
  CONFIRM_VERDICTS,
};
