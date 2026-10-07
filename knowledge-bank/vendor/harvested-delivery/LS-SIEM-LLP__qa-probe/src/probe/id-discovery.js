'use strict';

// ID chaining: instead of probing detail routes with a guessed id (`/cases/1`,
// which usually 404s on an unseeded DB), probe the collection first, harvest a
// REAL id from its response, and use that for the detail route. Pure read.

const ID_FIELDS = ['id', 'uuid', '_id', 'slug', 'key'];

function rawPathOf(routeKey) {
  if (typeof routeKey !== 'string') return null;
  const i = routeKey.indexOf(' ');
  return i === -1 ? routeKey : routeKey.slice(i + 1);
}

function hasPathParam(routeKey) {
  const raw = rawPathOf(routeKey);
  return !!raw && /\{[^}]+\}/.test(raw);
}

/** Split endpoints into those with `{param}` routes and those without. */
function partitionByParams(endpoints) {
  const withParams = [];
  const withoutParams = [];
  for (const ep of endpoints || []) {
    (hasPathParam(ep.routeKey) ? withParams : withoutParams).push(ep);
  }
  return { withParams, withoutParams };
}

/**
 * Map collection raw path ("/cases") → first item's scalar fields, harvested from
 * the param-less GET results that were already probed.
 */
function harvestCollectionItems(results) {
  const byPath = new Map();
  for (const [key, r] of Object.entries(results || {})) {
    if (!r || !r.firstItem) continue;
    const [method, path] = key.split(' ');
    if (method !== 'GET' || !path) continue;
    byPath.set(path, r.firstItem);
  }
  return byPath;
}

function idFromItem(item, paramName) {
  if (!item || typeof item !== 'object') return null;
  for (const field of [paramName, ...ID_FIELDS]) {
    const v = item[field];
    if (v !== undefined && v !== null && typeof v !== 'object') return String(v);
  }
  return null;
}

/**
 * For each `{param}` in a route, the collection is the path up to that param
 * segment ("/cases/{case_id}" → "/cases"). Returns a { param: value } map of the
 * real ids we could discover.
 */
function discoverFills(routeKey, collectionItems) {
  const raw = rawPathOf(routeKey);
  if (!raw) return {};
  const fills = {};
  const re = /\{([^}]+)\}/g;
  let m;
  while ((m = re.exec(raw)) !== null) {
    const param = m[1];
    const idx = raw.indexOf(`/{${param}}`);
    if (idx <= 0) continue;
    const collection = raw.slice(0, idx);
    const item = collectionItems.get(collection);
    if (!item) continue;
    const value = idFromItem(item, param);
    if (value != null) fills[param] = value;
  }
  return fills;
}

function refillPath(routeKey, fills, config) {
  const raw = rawPathOf(routeKey);
  const defaults = (config.probe && config.probe.pathParamValues) || {};
  return raw.replace(/\{([^}]+)\}/g, (_, name) => fills[name] || defaults[name] || defaults.id || '1');
}

/**
 * Rewrite each detail endpoint's path with discovered ids (mutates path in place).
 * Returns the number of endpoints that got at least one real id.
 */
function applyDiscoveredIds(withParamsEndpoints, collectionItems, config) {
  let applied = 0;
  for (const ep of withParamsEndpoints || []) {
    if (!ep.routeKey) continue;
    const fills = discoverFills(ep.routeKey, collectionItems);
    if (Object.keys(fills).length === 0) continue;
    ep.path = refillPath(ep.routeKey, fills, config);
    ep.discoveredIds = fills;
    applied++;
  }
  return applied;
}

module.exports = {
  partitionByParams,
  harvestCollectionItems,
  discoverFills,
  applyDiscoveredIds,
  idFromItem,
  rawPathOf,
  hasPathParam,
};
