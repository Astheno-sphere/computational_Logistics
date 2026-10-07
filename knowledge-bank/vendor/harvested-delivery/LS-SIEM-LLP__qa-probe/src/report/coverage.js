'use strict';

function generateCoverage(graph, probeResults = {}, config = {}) {
  const coverageConfig = (((config || {}).report || {}).coverage) || {};
  const ignoreGlobs = coverageConfig.ignoreEndpointGlobs || [];
  const referenced = buildReferencedEndpointIndex(graph);
  const deadEndpoints = findDeadEndpoints(graph, referenced, ignoreGlobs);
  const deadComponents = findDeadComponents(graph, probeResults);
  const orphanedFields = findOrphanedFields(graph, probeResults, referenced);

  return {
    generatedAt: new Date().toISOString(),
    deadEndpoints,
    deadComponents,
    orphanedFields,
    summary: {
      deadEndpointCount: deadEndpoints.length,
      deadComponentCount: deadComponents.length,
      orphanedFieldEndpointCount: orphanedFields.length,
      orphanedFieldCount: orphanedFields.reduce((sum, item) => sum + item.fields.length, 0),
    },
  };
}

function buildReferencedEndpointIndex(graph) {
  const byEndpoint = new Map();
  const byBackendRoute = new Map();

  for (const [routePath, routeData] of Object.entries((graph && graph.frontendRoutes) || {})) {
    for (const call of routeData.apiCalls || []) {
      const endpointKey = endpointKeyForCall(call);
      const entry = {
        routePath,
        component: routeData.component || null,
        file: fileFromCallSite(call.callSite),
        call,
      };
      addToMapList(byEndpoint, endpointKey, entry);
      if (call.matchedBackendRoute) addToMapList(byBackendRoute, call.matchedBackendRoute, entry);
    }
  }

  return { byEndpoint, byBackendRoute };
}

function findDeadEndpoints(graph, referenced, ignoreGlobs) {
  const out = [];
  for (const [endpointKey, routeInfo] of Object.entries((graph && graph.backendRoutes) || {})) {
    if (matchesAnyGlob(endpointKey, ignoreGlobs)) continue;
    if (referenced.byBackendRoute.has(endpointKey) || referenced.byEndpoint.has(endpointKey)) continue;
    out.push({
      endpoint: endpointKey,
      summary: routeInfo.summary || '',
      tags: routeInfo.tags || [],
      deprecated: !!routeInfo.deprecated,
    });
  }
  return out.sort((a, b) => a.endpoint.localeCompare(b.endpoint));
}

function findDeadComponents(graph, probeResults) {
  const byFile = new Map();

  for (const [, routeData] of Object.entries((graph && graph.frontendRoutes) || {})) {
    for (const call of routeData.apiCalls || []) {
      const file = fileFromCallSite(call.callSite) || routeData.component || '(unknown)';
      const endpointKey = endpointKeyForCall(call);
      addToMapList(byFile, file, {
        endpoint: endpointKey,
        matchedBackendRoute: call.matchedBackendRoute || null,
        status: statusForCall(call, probeResults),
      });
    }
  }

  const out = [];
  for (const [file, calls] of byFile.entries()) {
    if (calls.length === 0) continue;
    const deadCalls = calls.filter(call => !call.matchedBackendRoute || call.status === 404);
    if (deadCalls.length === calls.length) {
      out.push({
        file,
        endpoints: unique(deadCalls.map(call => call.endpoint)).sort(),
        reason: deadCalls.every(call => !call.matchedBackendRoute)
          ? 'not_in_spec'
          : deadCalls.every(call => call.status === 404)
            ? 'always_404'
            : 'not_in_spec_or_404',
      });
    }
  }

  return out.sort((a, b) => a.file.localeCompare(b.file));
}

function findOrphanedFields(graph, probeResults, referenced) {
  const out = [];

  for (const [endpointKey, probe] of Object.entries(probeResults || {})) {
    if (endpointKey.startsWith('__') || endpointKey.startsWith('VISUAL ')) continue;

    const returnedFields = fieldsFromResponseShape(probe && probe.responseShape);
    if (returnedFields.length === 0) continue;

    const readers = [
      ...(referenced.byEndpoint.get(endpointKey) || []),
      ...(probe && probe.routeKey ? referenced.byBackendRoute.get(probe.routeKey) || [] : []),
    ];
    const readFields = unique(readers.flatMap(entry => fieldsReadByCall(entry.call)));
    if (readFields.length === 0) continue;

    const readSet = new Set(readFields);
    const orphaned = returnedFields.filter(field => !readSet.has(field));
    if (orphaned.length > 0) {
      out.push({
        endpoint: endpointKey,
        routeKey: (probe && probe.routeKey) || null,
        fields: orphaned.sort(),
        readFields: readFields.sort(),
      });
    }
  }

  return out.sort((a, b) => a.endpoint.localeCompare(b.endpoint));
}

function endpointKeyForCall(call) {
  return `${call.method} ${call.backendPath || call.path}`;
}

function statusForCall(call, probeResults) {
  const keys = [endpointKeyForCall(call), call.matchedBackendRoute].filter(Boolean);
  for (const key of keys) {
    if (probeResults[key] && probeResults[key].status !== undefined) return probeResults[key].status;
  }
  return null;
}

function fieldsFromResponseShape(shape) {
  if (!shape || !shape.fields || typeof shape.fields !== 'object') return [];
  return Object.keys(shape.fields);
}

function fieldsReadByCall(call) {
  return unique([
    ...(call.readFields || []),
    ...(call.responseFields || []),
    ...(call.frontendFields || []),
  ].filter(Boolean));
}

function fileFromCallSite(callSite) {
  if (!callSite) return null;
  const idx = String(callSite).lastIndexOf(':');
  return idx === -1 ? String(callSite) : String(callSite).slice(0, idx);
}

function addToMapList(map, key, value) {
  if (!key) return;
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(value);
}

function unique(values) {
  return [...new Set(values)];
}

function matchesAnyGlob(value, globs) {
  return (globs || []).some(glob => globToRegExp(glob).test(value));
}

function globToRegExp(glob) {
  const escaped = String(glob)
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*/g, '.*');
  return new RegExp(`^${escaped}$`);
}

module.exports = {
  generateCoverage,
  buildReferencedEndpointIndex,
  findDeadEndpoints,
  findDeadComponents,
  findOrphanedFields,
  fieldsReadByCall,
  globToRegExp,
};
