'use strict';

/**
 * Score a frontend route 0–100.
 * Starts at 100 and deducts points for each broken/degraded API call.
 */
function scoreRoute(routePath, routeData, probeResults, rootCauses, config) {
  const weights = config.scoring || {};
  const apiCalls = (routeData && routeData.apiCalls) || [];

  if (apiCalls.length === 0) {
    // No API calls — score is neutral (no data dependency)
    return { score: 100, status: 'healthy', penalties: [] };
  }

  let score = 100;
  const penalties = [];

  for (const call of apiCalls) {
    const probeKey = `${call.method} ${call.backendPath || call.path}`;
    const probe = probeResults[probeKey];
    const cause = rootCauses[probeKey];

    if (!probe) continue; // not probed

    const rootCause = cause && cause.rootCause;

    switch (rootCause) {
      case 'expected_empty':
      case 'sample_unavailable':
        break;
      case 'feature_flag_disabled':
        score += (weights.disabledFeature || -15);
        penalties.push({ probeKey, reason: 'feature_flag_disabled', delta: weights.disabledFeature || -15 });
        break;
      case 'missing_route':
        score += (weights.missingRoute || -50);
        penalties.push({ probeKey, reason: 'missing_route', delta: weights.missingRoute || -50 });
        break;
      case 'contract_mismatch':
        score += (weights.missingRoute || -50);
        penalties.push({ probeKey, reason: 'contract_mismatch', delta: weights.missingRoute || -50 });
        break;
      case 'empty_db':
        score += (weights.emptyResponse || -20);
        penalties.push({ probeKey, reason: 'empty_db', delta: weights.emptyResponse || -20 });
        break;
      case 'auth_scope_mismatch':
        score += (weights.authError || -30);
        penalties.push({ probeKey, reason: 'auth_scope_mismatch', delta: weights.authError || -30 });
        break;
      case 'precondition_required':
        // A 428 gate (terms/onboarding/MFA) blocks the endpoint from returning
        // data just as surely as an auth failure does. Penalize it so a probe
        // account that hasn't cleared the gate cannot inflate the score.
        score += (weights.preconditionGate || -30);
        penalties.push({ probeKey, reason: 'precondition_required', delta: weights.preconditionGate || -30 });
        break;
      case 'schema_mismatch':
      case 'type_mismatch':
      case 'missing_required_field':
      case 'field_renamed':
        score += (weights.schemaMismatch || -25);
        penalties.push({ probeKey, reason: rootCause, delta: weights.schemaMismatch || -25 });
        break;
      case 'assertion_failed':
        // A declared invariant was violated — a real logic/contract bug.
        score += (weights.assertionFailed || -30);
        penalties.push({ probeKey, reason: 'assertion_failed', delta: weights.assertionFailed || -30 });
        break;
      case 'stream_dead':
        score += (weights.streamDead || -35);
        penalties.push({ probeKey, reason: 'stream_dead', delta: weights.streamDead || -35 });
        break;
      case 'server_error':
        score += (weights.serverError || -40);
        penalties.push({ probeKey, reason: 'server_error', delta: weights.serverError || -40 });
        break;
      case 'auth_bypass':
      case 'privilege_escalation':
      case 'pii_leak':
        // Security findings are among the most severe — an unguarded endpoint or a
        // PII leak should dominate the route score.
        score += (weights.securityIssue || -50);
        penalties.push({ probeKey, reason: rootCause, delta: weights.securityIssue || -50 });
        break;
      case 'slow_but_working':
      case 'slow_app':
      case 'slow_dependency':
        score += (weights.slowResponse || -10);
        penalties.push({ probeKey, reason: rootCause, delta: weights.slowResponse || -10 });
        break;
      case 'sample_not_found':
      case 'invalid_sample_params':
      case 'timeout':
        score += (weights.slowResponse || -10);
        penalties.push({ probeKey, reason: rootCause, delta: weights.slowResponse || -10 });
        break;
      case 'unknown':
        // An unclassified non-2xx response is still a real failure. Apply a small
        // penalty so it shows up in the score rather than being silently free,
        // which previously let large clusters of odd status codes (e.g. 428/429)
        // hide behind a perfect-looking number.
        score += (weights.unknown || -10);
        penalties.push({ probeKey, reason: 'unknown', delta: weights.unknown || -10 });
        break;
    }
  }

  score = Math.max(0, Math.min(100, score));

  let status;
  if (score >= 80) status = 'healthy';
  else if (score >= 50) status = 'degraded';
  else status = 'broken';

  // Primary root cause is the worst penalty
  const primaryCause = penalties.length > 0
    ? penalties.sort((a, b) => a.delta - b.delta)[0].reason
    : (score === 100 ? 'ok' : null);

  return { score, status, penalties, primaryCause };
}

/**
 * Compute overall score as weighted average across all routes.
 */
function scoreOverall(routeScores) {
  const scores = Object.values(routeScores).map(r => r.score);
  if (scores.length === 0) return 100;
  return Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length);
}

module.exports = { scoreRoute, scoreOverall };
