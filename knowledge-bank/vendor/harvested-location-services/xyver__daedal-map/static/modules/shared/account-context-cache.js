import { readSharedCache, writeSharedCache, removeSharedCache } from './shared-cache.js';

export const ACCOUNT_CONTEXT_CACHE_PREFIX = 'daedalmap-account-context-v1:';
export const ACCOUNT_CONTEXT_TTL_MS = 5 * 60 * 1000;

function normalizeAccountContext(value) {
  if (!value || typeof value !== 'object') return null;
  const userId = String(value.user_id || '').trim();
  if (!userId) return null;
  const normalizeLaneOverlayMap = (candidate) => {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return undefined;
    const lanes = ['explore', 'research', 'ops'];
    const out = {};
    for (const lane of lanes) {
      if (Array.isArray(candidate[lane])) {
        out[lane] = candidate[lane].map(item => String(item || '').trim()).filter(Boolean);
      }
    }
    return Object.keys(out).length ? out : undefined;
  };
  return {
    authenticated: value.authenticated !== false,
    user_id: userId,
    email: String(value.email || '').trim(),
    plan_id: String(value.plan_id || 'free').trim() || 'free',
    is_admin: value.is_admin === true,
    enabled_shells: Array.isArray(value.enabled_shells) ? value.enabled_shells : undefined,
    ops_feeds: Array.isArray(value.ops_feeds) ? value.ops_feeds.map(item => String(item || '').trim()).filter(Boolean) : undefined,
    default_shown_by_lane: normalizeLaneOverlayMap(value.default_shown_by_lane),
    default_enabled_by_lane: normalizeLaneOverlayMap(value.default_enabled_by_lane),
    max_packs: Number.isFinite(Number(value.max_packs)) ? Number(value.max_packs) : undefined,
    org_id: value.org_id || null,
    account_url: String(value.account_url || '').trim() || undefined,
    balance_micro_usd: Number.isFinite(Number(value.balance_micro_usd)) ? Number(value.balance_micro_usd) : undefined,
    saved_corpora_count: Number.isFinite(Number(value.saved_corpora_count)) ? Number(value.saved_corpora_count) : undefined,
    savedAt: Number.isFinite(Number(value.savedAt)) ? Number(value.savedAt) : Date.now()
  };
}

export function getAccountContextCacheKey(userId) {
  return ACCOUNT_CONTEXT_CACHE_PREFIX + String(userId || '').trim();
}

export async function readAccountContextCache(userId) {
  const key = getAccountContextCacheKey(userId);
  const entry = await readSharedCache(key);
  return normalizeAccountContext(entry?.value ?? entry);
}

export async function writeAccountContextCache(context) {
  const value = normalizeAccountContext(context);
  if (!value) return null;
  await writeSharedCache(getAccountContextCacheKey(value.user_id), value, ACCOUNT_CONTEXT_TTL_MS);
  return value;
}

export async function removeAccountContextCache(userId) {
  await removeSharedCache(getAccountContextCacheKey(userId));
}
