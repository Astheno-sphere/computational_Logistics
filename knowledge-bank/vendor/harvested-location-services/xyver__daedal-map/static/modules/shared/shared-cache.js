import { canUseBridge, postBridgeMessage } from './cross-surface-bridge.js';

const SHARED_CACHE_PREFIX = 'daedalmap-shared-cache:';

function storageKeyForCache(key) {
  return SHARED_CACHE_PREFIX + String(key || '').trim();
}

export function readLocalSharedCache(key) {
  try {
    const raw = window.localStorage.getItem(storageKeyForCache(key));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    if (Number.isFinite(parsed.expiresAt) && Date.now() > parsed.expiresAt) {
      window.localStorage.removeItem(storageKeyForCache(key));
      return null;
    }
    return parsed;
  } catch (_) {
    return null;
  }
}

export function writeLocalSharedCache(key, value, ttlMs) {
  const payload = {
    savedAt: Date.now(),
    expiresAt: Number.isFinite(Number(ttlMs)) && Number(ttlMs) > 0 ? Date.now() + Number(ttlMs) : null,
    value
  };
  window.localStorage.setItem(storageKeyForCache(key), JSON.stringify(payload));
  return payload;
}

export function removeLocalSharedCache(key) {
  try {
    window.localStorage.removeItem(storageKeyForCache(key));
  } catch (_) {}
}

export async function readSharedCache(key) {
  if (canUseBridge()) {
    const response = await postBridgeMessage('dm-shared-cache-get', { key });
    return response.entry || null;
  }
  return readLocalSharedCache(key);
}

export async function writeSharedCache(key, value, ttlMs) {
  if (canUseBridge()) {
    const response = await postBridgeMessage('dm-shared-cache-set', { key, value, ttlMs });
    return response.entry || null;
  }
  return writeLocalSharedCache(key, value, ttlMs);
}

export async function removeSharedCache(key) {
  if (canUseBridge()) {
    await postBridgeMessage('dm-shared-cache-remove', { key });
    return;
  }
  removeLocalSharedCache(key);
}

export { SHARED_CACHE_PREFIX };
