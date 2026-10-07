import { canUseBridge, postBridgeMessage } from './cross-surface-bridge.js';
import { readSharedCache, writeSharedCache } from './shared-cache.js';

export const RESEARCH_PACK_CATALOG_CACHE_KEY = 'daedalmap-research-pack-catalog-v3';
export const RESEARCH_PACK_CATALOG_TTL_MS = 15 * 60 * 1000;
export const RESEARCH_PACK_CATALOG_API = '/api/account/research-corpora/packs';

function hasUsableResearchPackSources(packs) {
  return Array.isArray(packs) && packs.every((pack) => {
    if (!Array.isArray(pack?.sources)) return false;
    const expectedCount = Number(pack?.source_count || 0);
    if (expectedCount <= 0) return true;
    return pack.sources.length > 0;
  });
}

function normalizeResearchPackCatalog(entry) {
  const value = entry?.value ?? entry;
  const savedAt = Number(entry?.savedAt ?? value?.savedAt ?? 0);
  const expiresAt = Number(entry?.expiresAt ?? 0);
  if (!Array.isArray(value?.packs) || !Number.isFinite(savedAt)) return null;
  if ((expiresAt && Date.now() > expiresAt) || (!expiresAt && (Date.now() - savedAt) > RESEARCH_PACK_CATALOG_TTL_MS)) {
    return null;
  }
  if (!hasUsableResearchPackSources(value.packs)) return null;
  return value;
}

export async function readResearchPackCatalogCache() {
  const entry = await readSharedCache(RESEARCH_PACK_CATALOG_CACHE_KEY);
  return normalizeResearchPackCatalog(entry);
}

export async function writeResearchPackCatalogCache(packs) {
  const value = {
    savedAt: Date.now(),
    packs: Array.isArray(packs) ? packs : []
  };
  await writeSharedCache(RESEARCH_PACK_CATALOG_CACHE_KEY, value, RESEARCH_PACK_CATALOG_TTL_MS);
  return value;
}

export async function loadResearchPackCatalog({
  forceRefresh = false,
  endpoint = RESEARCH_PACK_CATALOG_API,
  fetchImpl = fetch
} = {}) {
  if (!forceRefresh) {
    const cached = await readResearchPackCatalogCache();
    if (cached?.packs?.length) {
      return {
        packs: cached.packs,
        cached: true,
        source: 'shared-cache'
      };
    }
  }

  if (canUseBridge()) {
    const response = await postBridgeMessage('dm-research-pack-catalog-get', { forceRefresh });
    const payload = normalizeResearchPackCatalog(response?.payload || null);
    if (!payload) {
      throw new Error(response?.error || 'Research pack catalog bridge request failed');
    }
    return {
      packs: payload.packs,
      cached: response?.source === 'shared-cache',
      source: response?.source || 'bridge'
    };
  }

  const response = await fetchImpl(endpoint, {
    headers: { Accept: 'application/json' }
  });
  if (!response.ok) {
    throw new Error(`Research pack catalog request failed: HTTP ${response.status}`);
  }
  const payload = await response.json();
  const packs = Array.isArray(payload?.packs) ? payload.packs : [];
  await writeResearchPackCatalogCache(packs);
  return {
    packs,
    cached: false,
    source: 'network'
  };
}

export async function getResearchPackCatalogMap(options = {}) {
  const result = await loadResearchPackCatalog(options);
  return new Map((result.packs || []).map((pack) => [String(pack?.pack_id || '').trim(), pack]).filter(([key]) => Boolean(key)));
}
