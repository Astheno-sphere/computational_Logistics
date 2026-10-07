'use strict';

/**
 * Root cause classifier.
 * Rules applied in priority order — first match wins.
 *
 * Priority:
 *  1. feature_flag_disabled  — 404 + path prefix in featureFlags with included/enabled: false
 *  2. missing_route          — 404 + NOT in OpenAPI spec + not a disabled flag
 *  3. contract_mismatch      — fuzzy match finds backend route but exact path differs
 *  4. empty_db               — 200 + empty array/body + list endpoint
 *  5. auth_scope_mismatch    — 403
 * 5b. precondition_required  — 428 (terms/license, onboarding, or MFA gate not satisfied)
 *  6. type_mismatch          — 200 + data present + wrong field type
 *  7. missing_required_field — 200 + data present + required field absent
 *  8. field_renamed          — 200 + bidirectional drift indicates rename
 *  9. data_received_not_rendered — HTTP healthy but visual density is low
 * 10. stream_dead            — SSE/WS connected=false OR no first event/frame
 * 11. server_error           — 5xx
 * 12. invalid_sample_params  — 400/422 from generated sample params/query
 * 13. sample_not_found       — 404 on a known templated backend route
 * 14. timeout                — request timed out/aborted
 * 15. slow_app/slow_dependency — 200 + ms > 80% of timeout
 * 16. ok                     — everything else
 */

function classifyEndpoint(endpointKey, probeResult, graph, config) {
  if (!probeResult) return { rootCause: 'not_probed', rootCauseDetail: null, fixHint: null };

  const { status, ms, empty, schemaErrors, type, connected, error, routeKey } = probeResult;

  if (probeResult.securityFinding) {
    const finding = probeResult.securityFinding;
    const hints = {
      privilege_escalation: 'Review authorization checks and object ownership filters for this endpoint.',
      pii_leak: 'Remove or document PII fields, mask sensitive values, or restrict the endpoint to authorized personas.',
      auth_bypass: 'Require authentication middleware for this endpoint and verify anonymous probes return 401/403.',
    };
    return {
      rootCause: finding.rootCause,
      rootCauseDetail: finding.detail || `${endpointKey} -> ${finding.rootCause}`,
      fixHint: hints[finding.rootCause] || null,
      // auth_bypass / privilege_escalation are deterministic (an unauthorized
      // persona reached the route); pii_leak is a regex heuristic.
      confidence: finding.confidence || (finding.rootCause === 'pii_leak' ? 'medium' : 'high'),
    };
  }

  // A declared response invariant was violated on a 2xx response — a logic/contract
  // bug the app actually returned. Deterministic, so high confidence.
  if (probeResult.assertionFailures && probeResult.assertionFailures.length) {
    const fails = probeResult.assertionFailures;
    return {
      rootCause: 'assertion_failed',
      rootCauseDetail: `${endpointKey} → ${fails.length} assertion(s) failed: ${fails.slice(0, 5).join('; ')}`,
      fixHint: 'The endpoint returned 2xx but the response violated a declared invariant. Fix the backend response, or update the assertion if the contract changed intentionally.',
      confidence: 'high',
    };
  }

  if (probeResult.anomaly) {
    return {
      rootCause: 'anomaly_vs_baseline',
      rootCauseDetail: probeResult.anomaly.detail,
      fixHint: probeResult.anomaly.fixHint || 'Compare this endpoint against recent healthy runs before treating it as an application failure.',
      // A statistical deviation, not a confirmed defect — flag it, but don't claim certainty.
      confidence: 'medium',
    };
  }

  if (probeResult.schemathesisFailure) {
    return {
      rootCause: 'validation_edge_case',
      rootCauseDetail: probeResult.schemathesisFailure.check || probeResult.schemathesisFailure.error || 'Schemathesis found an edge-case failure',
      fixHint: probeResult.schemathesisFailure.fixHint || 'Reproduce the Schemathesis payload and tighten request/response validation.',
    };
  }

  if (type === 'visual') {
    const threshold = probeResult.densityThreshold === undefined ? 0.10 : probeResult.densityThreshold;
    if (probeResult.httpScore >= 80 && probeResult.density < threshold) {
      return {
        rootCause: 'data_received_not_rendered',
        rootCauseDetail: `${probeResult.routePath || endpointKey} → HTTP score ${probeResult.httpScore}, visual density ${probeResult.density.toFixed(3)} below ${threshold}`,
        fixHint: 'Check component render: data fetched but not rendered. Common causes: prop name mismatch, missing key prop, error boundary swallow.',
      };
    }
    return { rootCause: 'ok', rootCauseDetail: null, fixHint: null };
  }

  // --- Rule 7: stream_dead (SSE/WS) ---
  if (type === 'sse' || type === 'ws') {
    if (!connected || probeResult.status === 'error' || probeResult.status === 'timeout') {
      return {
        rootCause: 'stream_dead',
        rootCauseDetail: `${type.toUpperCase()} ${endpointKey}: ${error || 'not connected'}`,
        fixHint: 'Check streaming endpoint auth, server-side event emitter, and proxy config (nginx/traefik must allow SSE/WS passthrough).',
      };
    }
    if (probeResult.status === 'no_events' || probeResult.status === 'no_frames') {
      return {
        rootCause: 'stream_dead',
        rootCauseDetail: `${type.toUpperCase()} connected but no events delivered within timeout`,
        fixHint: 'Server is not emitting events. Check that the event loop/background task is running.',
      };
    }
    return { rootCause: 'ok', rootCauseDetail: null, fixHint: null };
  }

  // --- Rule 1: feature_flag_disabled ---
  if (status === 404) {
    const flagInfo = findFeatureFlag(endpointKey, graph);
    if (flagInfo && (!flagInfo.included || !flagInfo.enabled)) {
      const flagName = getFlagName(endpointKey, graph);
      const timingDetail = typeof ms === 'number' ? ` at ${ms}ms` : '';
      return {
        rootCause: 'feature_flag_disabled',
        rootCauseDetail: `${endpointKey} → 404${timingDetail}. Feature disabled: ${flagInfo.message || 'feature flag disabled'}`,
        fixHint: flagName
          ? `Set ${flagName}=true in backend config (.env.prod or environment variables) and restart the API.`
          : 'Enable the corresponding HAS_* flag in backend config and restart the API.',
      };
    }
  }

  // --- Rule 3: contract_mismatch (checked before missing_route) ---
  // A fuzzy match is a better diagnosis than a generic "not found" — it tells the
  // developer exactly which route to align to, rather than leaving them to search.
  if (status === 404) {
    if (routeKey && /\{[^}]+\}/.test(routeKey)) {
      if (matchesProbePath(config, 'generatedSamplePaths', endpointKey, routeKey)) {
        return {
          rootCause: 'sample_unavailable',
          rootCauseDetail: `${endpointKey} -> 404 on sampled route ${routeKey}. This QA profile probes the route shape, but does not require the generated sample record to exist.`,
          fixHint: 'For deeper contract testing, set a real pathParamValues fixture or move this route out of probe.generatedSamplePaths.',
        };
      }
      return {
        rootCause: 'sample_not_found',
        rootCauseDetail: `${endpointKey} -> 404 on known backend route ${routeKey}. The sampled path value probably does not exist.`,
        fixHint: 'Set probe.pathParamValues in qa-probe.config.js to IDs/slugs that exist in your demo or test database, or add non-fixture detail routes to probe.generatedSamplePaths.',
      };
    }

    const fuzzyMatch = findFuzzyBackendMatch(endpointKey, graph);
    if (fuzzyMatch) {
      return {
        rootCause: 'contract_mismatch',
        rootCauseDetail: `${endpointKey} → 404. Similar route exists: ${fuzzyMatch}`,
        fixHint: 'Align the frontend call path to match the backend route. Check trailing slashes, prefix differences, or casing.',
      };
    }
  }

  // --- Rule 2: missing_route ---
  if (status === 404) {
    const inSpec = isInBackendSpec(endpointKey, graph);
    if (!inSpec) {
      return {
        rootCause: 'missing_route',
        rootCauseDetail: `${endpointKey} → 404. Not found in OpenAPI spec.`,
        fixHint: 'Check for typos in the frontend API call path or a missing include_router() in backend/app/main.py.',
      };
    }
  }

  // --- Rule 8: server_error ---
  if (status >= 500) {
    return {
      rootCause: 'server_error',
      rootCauseDetail: `${endpointKey} → ${status}. Backend returned a server error.`,
      fixHint: 'Check backend logs for a traceback (e.g. `docker logs <api-container> --tail 50`).',
    };
  }

  if (status === 400 || status === 422) {
    if (matchesProbePath(config, 'generatedSamplePaths', endpointKey, routeKey)) {
      return {
        rootCause: 'sample_unavailable',
        rootCauseDetail: `${endpointKey} -> ${status}. Generated probe parameters are intentionally smoke-test-only for this endpoint.`,
        fixHint: 'For strict validation, provide route-specific sample params or remove this pattern from probe.generatedSamplePaths.',
      };
    }
    return {
      rootCause: 'invalid_sample_params',
      rootCauseDetail: `${endpointKey} -> ${status}. Generated probe parameters did not satisfy this endpoint's validation rules.`,
      fixHint: 'Tune probe.pathParamValues, provide endpoint-specific fixtures, or add non-fixture detail/query routes to probe.generatedSamplePaths.',
    };
  }

  // --- Rule 5: auth_scope_mismatch ---
  if (status === 403) {
    return {
      rootCause: 'auth_scope_mismatch',
      rootCauseDetail: `${endpointKey} → 403. Test user lacks required scopes.`,
      fixHint: 'Use a user with admin role, or check the required scopes for this endpoint in the backend.',
    };
  }

  if (status === 401) {
    return {
      rootCause: 'auth_scope_mismatch',
      rootCauseDetail: `${endpointKey} → 401. Authentication token rejected or expired.`,
      fixHint: 'Check that auth credentials are correct and the token has not expired.',
    };
  }

  // --- Rule 5b: precondition_required (428) ---
  // The request is well-formed and the user is authenticated, but a one-time
  // gate must be satisfied before the endpoint returns data — e.g. terms/license
  // acceptance, an onboarding wizard, or MFA enrollment. This is a probe-account
  // configuration issue, not a broken route, so it gets its own diagnosis instead
  // of falling through to the generic `unknown` bucket.
  if (status === 428) {
    return {
      rootCause: 'precondition_required',
      rootCauseDetail: `${endpointKey} → 428 Precondition Required. The probe account has not satisfied a required gate (terms/license acceptance, onboarding, or MFA enrollment) before this endpoint will return data.`,
      fixHint: 'Satisfy the gate for the QA service account (accept the current terms/license version, complete onboarding, or configure MFA), or exempt the service account from the gate. Then re-run.',
    };
  }

  if (status === 200) {
    // --- Rule 4: empty_db ---
    if (empty) {
      if (matchesProbePath(config, 'expectedEmptyPaths', endpointKey, routeKey)) {
        return {
          rootCause: 'expected_empty',
          rootCauseDetail: `${endpointKey} -> 200 but ${probeResult.emptyReason || 'empty body'}. Empty is an expected healthy quiet-state for this endpoint.`,
          fixHint: null,
        };
      }
      const seedCmd = config && config.seedCommand;
      const seedHint = seedCmd
        ? `Run: ${seedCmd}`
        : 'Run your project\'s seed or fixture script to populate test data (set seedCommand in qa-probe.config.js to show the exact command here).';
      return {
        rootCause: 'empty_db',
        rootCauseDetail: `${endpointKey} → 200 but ${probeResult.emptyReason || 'empty body'}. No records in database.`,
        fixHint: `Seed the database. ${seedHint}`,
      };
    }

    // --- Rule 6: schema_mismatch ---
    if (schemaErrors && schemaErrors.length > 0) {
      const schemaCause = classifySchemaError(schemaErrors[0]);
      return {
        rootCause: schemaCause.rootCause,
        rootCauseDetail: `${endpointKey} → 200 but response shape differs from spec: ${schemaErrors[0]}`,
        fixHint: schemaCause.fixHint,
      };
    }

    // --- Rule 9: slow_app / slow_dependency ---
    const timeout = (config && config.probe && config.probe.timeoutMs) || 10000;
    if (ms > timeout * 0.8) {
      if (probeResult.otel && probeResult.otel.classification === 'slow_dependency') {
        return {
          rootCause: 'slow_dependency',
          rootCauseDetail: `${endpointKey} -> downstream ${probeResult.otel.slowComponent || 'dependency'} dominated trace time`,
          fixHint: `Investigate downstream operation ${probeResult.otel.slowComponent || 'dependency'} before tuning app code.`,
        };
      }
      if (probeResult.otel && probeResult.otel.classification === 'slow_app') {
        return {
          rootCause: 'slow_app',
          rootCauseDetail: `${endpointKey} -> application self-time dominated trace latency`,
          fixHint: 'Profile handler code, query planning, and serialization inside the application span.',
        };
      }
      return {
        rootCause: 'slow_app',
        rootCauseDetail: `${endpointKey} → 200 but took ${ms}ms (${Math.round((ms / timeout) * 100)}% of timeout)`,
        fixHint: 'No trace correlation was available. Profile app code and dependencies to locate the slow span.',
      };
    }

    return { rootCause: 'ok', rootCauseDetail: null, fixHint: null };
  }

  // Anything else — not probed or unknown
  if (status === null && error && /timeout|deadline|aborted|canceled|cancelled|ECONNRESET|socket hang up/i.test(error)) {
    return {
      rootCause: 'timeout',
      rootCauseDetail: `${endpointKey} -> ${error}`,
      fixHint: 'Check whether the endpoint is long-running, streaming, calling an external model, or should be skipped/tuned for smoke tests.',
    };
  }

  return {
    rootCause: 'unknown',
    rootCauseDetail: `${endpointKey} → status=${status}, error=${error || 'none'}. No classifier rule matched this signal, so this is an UNCLASSIFIED result — not a confirmed pass. Inspect the captured evidence (raw status + response sample) to determine the cause; if the pattern recurs, add a root-cause rule for it.`,
    fixHint: 'Open the endpoint evidence to see what the server actually returned. If this status/shape is expected, add a rule or mark it as expected; if not, treat it as a real failure — do not assume it passed.',
    confidence: 'none',
    unmatched: true,
  };
}

function findFeatureFlag(endpointKey, graph) {
  const path = endpointKey.split(' ').slice(1).join(' ');
  for (const [prefix, flag] of Object.entries(graph.featureFlags || {})) {
    if (path === prefix || path.startsWith(prefix + '/') || path.startsWith(prefix)) {
      return flag;
    }
  }
  return null;
}

function classifySchemaError(error) {
  const message = String(error || '');
  if (/missing required field/i.test(message)) {
    return {
      rootCause: 'missing_required_field',
      fixHint: 'Return the required field from the backend response or update the OpenAPI schema if the contract changed intentionally.',
    };
  }
  if (/type mismatch/i.test(message)) {
    return {
      rootCause: 'type_mismatch',
      fixHint: 'Align the backend field type with OpenAPI, or update the spec and frontend parser for the new type.',
    };
  }
  if (/no expected fields found|renamed/i.test(message)) {
    return {
      rootCause: 'field_renamed',
      fixHint: 'A field appears to have been renamed. Align the frontend read, backend response, and OpenAPI field name.',
    };
  }
  return {
    rootCause: 'schema_mismatch',
    fixHint: 'A field was renamed or removed. Align the frontend component or backend response model.',
  };
}

function matchesProbePath(config, configKey, endpointKey, routeKey) {
  const patterns = config && config.probe && config.probe[configKey];
  if (!Array.isArray(patterns) || patterns.length === 0) return false;

  const endpointPath = pathWithoutMethod(endpointKey).split('?')[0];
  const routePath = routeKey ? pathWithoutMethod(routeKey).split('?')[0] : null;

  return patterns.some(pattern => {
    const rx = new RegExp(pattern);
    return rx.test(endpointPath) || (routePath && rx.test(routePath));
  });
}

function pathWithoutMethod(key) {
  const text = String(key || '');
  const firstSpace = text.indexOf(' ');
  return firstSpace === -1 ? text : text.slice(firstSpace + 1);
}

function getFlagName(endpointKey, graph) {
  // Derive a probable HAS_* flag name from the path prefix using the
  // standard convention: /some-feature → HAS_SOME_FEATURE.
  // Projects can override this by adding a featureFlagMap to their config.
  const path = endpointKey.split(' ').slice(1).join(' ');
  const segment = path.split('/').filter(Boolean)[0];
  if (!segment) return null;

  // Check config-provided override map first (config.featureFlagMap)
  const configMap = (graph && graph.config && graph.config.featureFlagMap) || {};
  const prefix = '/' + segment;
  if (configMap[prefix]) return configMap[prefix];

  // Auto-derive: /some-feature-name → HAS_SOME_FEATURE_NAME
  return 'HAS_' + segment.toUpperCase().replace(/-/g, '_');
}

function isInBackendSpec(endpointKey, graph) {
  return !!(graph.backendRoutes && graph.backendRoutes[endpointKey]);
}

function findFuzzyBackendMatch(endpointKey, graph) {
  if (!graph.backendRoutes) return null;
  const [method, callPath] = endpointKey.split(' ');

  for (const routeKey of Object.keys(graph.backendRoutes)) {
    const [routeMethod, routePath] = routeKey.split(' ');
    if (routeMethod !== method) continue;

    // Check if stripping/adding trailing slash would match
    if (routePath === callPath + '/' || routePath + '/' === callPath) {
      return routeKey;
    }

    // Check if paths are the same ignoring case
    if (routePath.toLowerCase() === callPath.toLowerCase()) {
      return routeKey;
    }

    // Levenshtein-like: are they 1-2 path segments different?
    const callParts = callPath.split('/').filter(Boolean);
    const routeParts = routePath.split('/').filter(Boolean);
    if (Math.abs(callParts.length - routeParts.length) <= 1) {
      const shared = callParts.filter((p, i) => routeParts[i] === p || routeParts[i] === `{${p}}`);
      // Require at least 1 shared segment so fully-unrelated paths don't match.
      // When min segment count is N, allow at most 1 mismatch (N-1 shared required),
      // but never accept 0 shared segments regardless of length delta.
      if (shared.length >= 1 && shared.length >= Math.min(callParts.length, routeParts.length) - 1) {
        return routeKey;
      }
    }
  }

  return null;
}

/**
 * Cluster pass: if 5+ endpoints share the same path prefix and the same root cause,
 * group them under one shared root cause entry.
 */
function clusterRootCauses(endpointResults) {
  const prefixGroups = {};

  for (const [key, data] of Object.entries(endpointResults)) {
    const pathPart = key.split(' ').slice(1).join(' ');
    const prefix = '/' + pathPart.split('/').filter(Boolean)[0];
    if (!prefixGroups[prefix]) prefixGroups[prefix] = [];
    prefixGroups[prefix].push({ key, ...data });
  }

  const clusters = [];
  for (const [prefix, items] of Object.entries(prefixGroups)) {
    if (items.length < 5) continue;
    const causeCounts = {};
    for (const item of items) {
      causeCounts[item.rootCause] = (causeCounts[item.rootCause] || 0) + 1;
    }
    const dominantCause = Object.entries(causeCounts).sort((a, b) => b[1] - a[1])[0];
    if (dominantCause && dominantCause[1] >= 5) {
      clusters.push({
        prefix,
        rootCause: dominantCause[0],
        count: dominantCause[1],
        keys: items.map(i => i.key),
      });
    }
  }

  return clusters;
}

module.exports = { classifyEndpoint, clusterRootCauses, classifySchemaError };
