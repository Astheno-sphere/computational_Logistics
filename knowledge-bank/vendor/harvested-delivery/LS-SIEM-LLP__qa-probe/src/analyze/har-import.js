'use strict';

// HAR import — derive the frontend→backend call map from a captured .har file.
// For frontends too dynamic to parse statically (GraphQL/tRPC, generated SDK
// clients, custom service layers), record real traffic once (DevTools → Save HAR,
// or your existing Playwright/Cypress run) and qa-probe discovers the endpoints
// from it. Produces the same shape the CDP runtime tracer feeds buildGraph:
// Map<routePath, [{ method, path, rawPath, source }]>.

const fs = require('fs');

function pathname(url) {
  try { return new URL(url).pathname; } catch { return String(url || '').split('?')[0]; }
}

const STATIC_RE = /\.(js|mjs|cjs|css|png|jpe?g|gif|svg|webp|avif|woff2?|ttf|eot|ico|map|html?|txt)$/i;

/** Heuristic: is this HAR entry an API request worth probing (not a static asset)? */
function isApiRequest(entry, config) {
  const req = (entry && entry.request) || {};
  const p = pathname(req.url);
  if (!p || STATIC_RE.test(p)) return false;
  const rtype = String(entry._resourceType || '').toLowerCase();
  if (rtype === 'xhr' || rtype === 'fetch') return true;
  const respCT = (((entry.response || {}).content) || {}).mimeType || '';
  if (/json|graphql/i.test(respCT)) return true;
  const prefix = config && config.frontendApiPrefix;
  const prefixes = Array.isArray(prefix) ? prefix : (prefix ? [prefix] : []);
  return prefixes.some(pre => pre && p.startsWith(pre));
}

function harToRuntimeCalls(harFile, config) {
  const map = new Map();
  if (!harFile || !fs.existsSync(harFile)) return map;
  let har;
  try { har = JSON.parse(fs.readFileSync(harFile, 'utf8')); } catch { return map; }
  const entries = (har.log && har.log.entries) || [];

  const seen = new Set();
  const calls = [];
  for (const entry of entries) {
    if (!isApiRequest(entry, config)) continue;
    const req = entry.request || {};
    const method = String(req.method || 'GET').toUpperCase();
    const p = pathname(req.url);
    if (!p) continue;
    const key = `${method} ${p}`;
    if (seen.has(key)) continue;
    seen.add(key);
    calls.push({ method, path: p, rawPath: req.url, source: 'har' });
  }
  if (calls.length) map.set('__unmatched__', calls);
  return map;
}

module.exports = { harToRuntimeCalls, isApiRequest, pathname };
