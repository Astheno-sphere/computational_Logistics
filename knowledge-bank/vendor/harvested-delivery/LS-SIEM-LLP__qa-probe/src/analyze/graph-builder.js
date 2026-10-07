'use strict';

/**
 * Build the dependency graph: frontend routes → backend routes → blast radius.
 *
 * Input:
 *   frontendRoutes: Map<routePath, { component, authGuard, requiredScopes }>
 *   apiCalls: { byFile: Map<file, calls[]>, allCalls: calls[] }
 *   runtimeCalls: Map<routePath, calls[]>
 *   backendSpec: { routes, featureFlags, headless }
 *   config: validated config
 *
 * Output: graph.json structure
 */

const path = require('path');

function buildGraph({ frontendRoutes, apiCalls, runtimeCalls = null, runtimeDomSnapshots = null, backendSpec, config, warnings = [] }) {
  const { routes: backendRoutes, featureFlags, headless } = backendSpec;

  // --- 1. Build a map of "which files belong to which frontend route" ---
  // We use a heuristic: component name from route → find matching file in src
  // For each frontend route, collect all api calls made by files under that route's subtree.
  //
  // Simple strategy: group api calls by the frontend route they appear closest to.
  // We look at the file path and match it to the route path.

  const routeApiCallMap = buildRouteToApiCallMap(frontendRoutes, apiCalls, config);
  mergeRuntimeCalls(routeApiCallMap, runtimeCalls, frontendRoutes);

  // --- 2. For each api call, find the matching backend route ---
  const prefix = config.frontendApiPrefix || '/api';

  // --- 3. Build blast radius: which frontend routes call each backend route ---
  const blastRadius = {};

  for (const [routePath, { component, authGuard, requiredScopes, apiCallsList }] of Object.entries(routeApiCallMap)) {
    for (const call of apiCallsList) {
      const backendPath = stripFrontendPrefix(call.path, prefix);
      const matchKey = matchBackendRoute(`${call.method} ${backendPath}`, backendRoutes);

      if (matchKey) {
        if (!blastRadius[matchKey]) {
          blastRadius[matchKey] = { calledByRoutes: [], calledByCount: 0 };
        }
        if (!blastRadius[matchKey].calledByRoutes.includes(routePath)) {
          blastRadius[matchKey].calledByRoutes.push(routePath);
          blastRadius[matchKey].calledByCount++;
        }
      }
    }
  }

  // --- 4. Assemble final graph.json shape ---
  const frontendRoutesOut = {};
  for (const [routePath, data] of Object.entries(routeApiCallMap)) {
    const apiCallsAnnotated = data.apiCallsList.map(call => {
      const backendPath = stripFrontendPrefix(call.path, prefix);
      const matchKey = matchBackendRoute(`${call.method} ${backendPath}`, backendRoutes);
      return {
        method: call.method,
        path: call.path,
        backendPath,
        matchedBackendRoute: matchKey || null,
        callSite: call.callSite,
        rawPath: call.rawPath,
        source: call.source || 'ast',
      };
    });

    frontendRoutesOut[routePath] = {
      component: data.component || null,
      authGuard: data.authGuard || 'Route',
      requiredScopes: data.requiredScopes || [],
      staleParse: !!data.staleParse,
      apiCalls: apiCallsAnnotated,
    };
  }

  // --- 5. Identify feature-flag-disabled routes ---
  const featureFlagMap = { ...(featureFlags || {}) };
  for (const [routePath] of Object.entries(frontendRoutesOut)) {
    const flag = findFeatureFlag(routePath, featureFlags);
    if (flag) {
      featureFlagMap[routePath] = flag;
    }
  }

  return {
    meta: {
      generatedAt: new Date().toISOString(),
      baseUrl: config.baseUrl,
      headless,
      frontendApiPrefix: prefix,
      runtimeTracing: !!runtimeCalls,
    },
    backendRoutes,
    featureFlags: featureFlagMap,
    frontendRoutes: frontendRoutesOut,
    blastRadius,
    warnings,
    runtimeDomSnapshots: runtimeDomSnapshots || undefined,
  };
}

function mergeRuntimeCalls(routeApiCallMap, runtimeCalls, frontendRoutes) {
  if (!runtimeCalls) return;

  for (const [routePath, calls] of runtimeCalls.entries()) {
    if (!routeApiCallMap[routePath]) {
      const routeInfo = frontendRoutes.get(routePath) || {};
      routeApiCallMap[routePath] = {
        component: routeInfo.component || null,
        authGuard: routeInfo.authGuard || 'Route',
        requiredScopes: routeInfo.requiredScopes || [],
        staleParse: !!routeInfo.staleParse,
        apiCallsList: [],
      };
    }

    for (const call of calls || []) {
      const existing = routeApiCallMap[routePath].apiCallsList.find(item =>
        item.method === call.method && item.path === call.path
      );
      if (existing) {
        existing.source = existing.source === 'runtime' ? 'runtime' : 'both';
      } else {
        routeApiCallMap[routePath].apiCallsList.push({ ...call, source: 'runtime' });
      }
    }
  }
}

/**
 * Strip the frontend API prefix from a path.
 * Supports both a single string prefix and an array of prefixes.
 */
function stripFrontendPrefix(p, prefix) {
  const prefixes = Array.isArray(prefix) ? prefix : [prefix];
  for (const pfx of prefixes) {
    if (p.startsWith(pfx)) return p.slice(pfx.length) || '/';
  }
  return p;
}

/**
 * For each frontend route, collect the API calls made by files associated with it.
 * Strategy: we look at the component name for a route and try to find matching files.
 * Also includes all API calls where we cannot identify a parent route.
 */
function buildRouteToApiCallMap(frontendRoutes, apiCalls, config) {
  const result = {};
  const srcDir = path.resolve(process.cwd(), config.frontendSrc);

  // Index all calls by file
  const callsByFile = apiCalls.byFile;

  // Build component name → route path index
  const componentToRoute = new Map();
  for (const [routePath, info] of frontendRoutes.entries()) {
    if (info.component) {
      componentToRoute.set(info.component.toLowerCase(), routePath);
    }
    // Always register by route path directly
    if (!result[routePath]) {
      result[routePath] = {
        component: info.component,
        authGuard: info.authGuard,
          requiredScopes: info.requiredScopes,
          staleParse: !!info.staleParse,
          apiCallsList: [],
      };
    }
  }

  // Associate API calls with routes based on file path heuristic
  const usedCalls = new Set();

  for (const [file, calls] of callsByFile.entries()) {
    const relFile = path.relative(srcDir, file).replace(/\\/g, '/').toLowerCase();
    const matchedRoute = findRouteForFile(relFile, frontendRoutes, componentToRoute);

    if (matchedRoute) {
      if (!result[matchedRoute]) {
        const info = frontendRoutes.get(matchedRoute) || {};
        result[matchedRoute] = {
          component: info.component || null,
          authGuard: info.authGuard || 'Route',
          requiredScopes: info.requiredScopes || [],
          staleParse: !!info.staleParse,
          apiCallsList: [],
        };
      }
      for (const call of calls) {
        const key = `${file}:${call.method}:${call.path}`;
        if (!usedCalls.has(key)) {
          usedCalls.add(key);
          result[matchedRoute].apiCallsList.push(call);
        }
      }
    }
  }

  // Any remaining unmatched calls go to a synthetic "__unmatched__" bucket
  for (const [file, calls] of callsByFile.entries()) {
    for (const call of calls) {
      const key = `${file}:${call.method}:${call.path}`;
      if (!usedCalls.has(key)) {
        usedCalls.add(key);
        if (!result['__unmatched__']) {
          result['__unmatched__'] = { component: null, authGuard: null, requiredScopes: [], apiCallsList: [] };
        }
        result['__unmatched__'].apiCallsList.push({ ...call, source: call.source || 'ast' });
      }
    }
  }

  return result;
}

/**
 * Heuristic: given a relative file path like "components/Alerts/index.tsx",
 * return the most likely frontend route it belongs to.
 */
function findRouteForFile(relFile, frontendRoutes, componentToRoute) {
  // 1. Try to match by component name (filename without extension)
  const baseName = relFile.split('/').pop().replace(/\.(j|t)sx?$/, '').toLowerCase();
  if (componentToRoute.has(baseName)) {
    return componentToRoute.get(baseName);
  }

  // 2. Try to match directory name against route paths
  const parts = relFile.split('/');
  for (let i = parts.length - 1; i >= 0; i--) {
    const segment = parts[i].replace(/\.(j|t)sx?$/, '').toLowerCase();
    // Check if any route path ends with this segment
    for (const routePath of frontendRoutes.keys()) {
      const routeSegments = routePath.split('/').filter(Boolean);
      const lastSegment = routeSegments[routeSegments.length - 1];
      if (lastSegment && lastSegment.toLowerCase() === segment) {
        return routePath;
      }
    }
  }

  return null;
}

/**
 * Find the backend route key that matches a given "METHOD /path" string.
 * Handles path params: /items/{id} matches /items/1 etc.
 */
function matchBackendRoute(callKey, backendRoutes) {
  // Exact match first
  if (backendRoutes[callKey]) return callKey;

  const [callMethod, callPath] = callKey.split(' ');

  // Try with trailing slash variants
  const alt = callKey.endsWith('/') ? callKey.slice(0, -1) : `${callKey}/`;
  if (backendRoutes[alt]) return alt;

  // Try pattern matching (backend has {param} style)
  for (const routeKey of Object.keys(backendRoutes)) {
    const [routeMethod, routePath] = routeKey.split(' ');
    if (routeMethod !== callMethod) continue;

    if (pathMatchesPattern(callPath, routePath)) return routeKey;
  }

  // Try case-insensitive
  for (const routeKey of Object.keys(backendRoutes)) {
    if (routeKey.toLowerCase() === callKey.toLowerCase()) return routeKey;
  }

  return null;
}

function pathMatchesPattern(actual, pattern) {
  // Convert /items/{id}/detail to regex
  const regex = new RegExp(
    '^' +
    pattern
      .replace(/\{[^}]+\}/g, '[^/]+')
      .replace(/\//g, '\\/')
    + '$'
  );
  return regex.test(actual);
}

/**
 * Find if a frontend route is gated by a feature flag.
 */
function findFeatureFlag(routePath, featureFlags) {
  // Direct match
  if (featureFlags[routePath]) return featureFlags[routePath];

  // Prefix match: /billing/invoices → featureFlags["/billing"]
  for (const [prefix, flag] of Object.entries(featureFlags)) {
    if (routePath === prefix || routePath.startsWith(prefix + '/')) {
      return flag;
    }
  }
  return null;
}

module.exports = { buildGraph, mergeRuntimeCalls };
