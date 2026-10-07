'use strict';

function remediateContractMismatch({ graph, probeResults, report }) {
  const fixes = [];
  const causes = collectCauses(report);
  for (const [endpointKey, cause] of causes) {
    if (!cause || cause.rootCause !== 'contract_mismatch') continue;
    const match = findTrailingSlashFix(endpointKey, graph, probeResults);
    if (!match) continue;
    fixes.push({
      id: `contract-mismatch:${endpointKey}`,
      title: `Align frontend path for ${endpointKey}`,
      strategy: 'contract_mismatch',
      confidence: 1.0,
      autoApply: true,
      patch: {
        file: match.file,
        before: match.before,
        after: match.after,
      },
      diff: unifiedDiff(match.file, match.before, match.after),
    });
  }
  return fixes;
}

function collectCauses(report) {
  if (report && report.endpointRootCauses) return Object.entries(report.endpointRootCauses);
  const out = [];
  for (const item of (report && report.endpointDiagnostics) || []) {
    out.push([item.endpoint, { rootCause: item.rootCause, fixHint: item.fixHint }]);
  }
  return out;
}

function findTrailingSlashFix(endpointKey, graph) {
  const calls = allCalls(graph);
  const [, endpointPath] = splitEndpointKey(endpointKey);
  const target = endpointPath.endsWith('/') ? endpointPath.slice(0, -1) : `${endpointPath}/`;
  const call = calls.find(item =>
    item.call.backendPath === endpointPath ||
    item.call.backendPath === target ||
    item.call.path === endpointPath ||
    item.call.path === target ||
    item.call.rawPath === endpointPath ||
    item.call.rawPath === target
  );
  if (!call || !call.callSite) return null;
  const file = call.callSite.split(':').slice(0, -1).join(':');
  const before = call.call.rawPath || call.call.path;
  const after = before.endsWith('/') ? before.slice(0, -1) : `${before}/`;
  if (before === after) return null;
  return { file, before, after };
}

function allCalls(graph) {
  const out = [];
  for (const [routePath, routeData] of Object.entries((graph && graph.frontendRoutes) || {})) {
    for (const call of routeData.apiCalls || []) out.push({ routePath, call, callSite: call.callSite });
  }
  return out;
}

function splitEndpointKey(key) {
  const idx = key.indexOf(' ');
  return idx === -1 ? ['', key] : [key.slice(0, idx), key.slice(idx + 1)];
}

function unifiedDiff(file, before, after) {
  return [
    `--- a/${file}`,
    `+++ b/${file}`,
    '@@',
    `-${before}`,
    `+${after}`,
  ].join('\n');
}

module.exports = { remediateContractMismatch, findTrailingSlashFix };
