/**
 * Chat Session Manager
 * Handles session ID lifecycle.
 * Persistent browser restore of lane/map UI state is intentionally disabled:
 * authoritative view state now comes from URL intent or account-backed defaults,
 * not hidden browser-saved state.
 * Reusable across map app and admin dashboard.
 */

import { getSessionMaxAgeMs, getStorageNamespace, isAuthenticated } from '../auth.js';

// Storage keys
const SESSION_ID_KEY = 'countymap_session_id';
const SESSION_TIMESTAMP_KEY = 'countymap_session_timestamp';
function namespacedKey(baseKey) {
  return `${baseKey}:${getStorageNamespace()}`;
}

/**
 * Get existing session ID from localStorage or create a new one.
 * Session persists across tab close/refresh for recovery.
 * @returns {string} Session ID
 */
export function getOrCreateSessionId() {
  const sessionKey = namespacedKey(SESSION_ID_KEY);
  const timestampKey = namespacedKey(SESSION_TIMESTAMP_KEY);
  let sessionId = localStorage.getItem(sessionKey);
  const timestamp = localStorage.getItem(timestampKey);

  // Check if session is expired
  const isExpired = timestamp && (Date.now() - parseInt(timestamp, 10)) > getSessionMaxAgeMs();

  if (sessionId && !isExpired) {
    // Update timestamp on reuse
    localStorage.setItem(timestampKey, Date.now().toString());
    console.log('[Session] Restored session:', sessionId);
    return sessionId;
  }

  // Create new session - also clear stale chat storage so old conversation
  // doesn't bleed into the new session on page load.
  clearChatStorage();
  const prefix = isAuthenticated() ? 'authsess_' : 'sess_';
  sessionId = prefix + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
  localStorage.setItem(sessionKey, sessionId);
  localStorage.setItem(timestampKey, Date.now().toString());
  console.log('[Session] Created new session:', sessionId);
  return sessionId;
}

/**
 * Clear the current session ID from localStorage.
 * @returns {string} New session ID (auto-created)
 */
export function resetSessionId() {
  localStorage.removeItem(namespacedKey(SESSION_ID_KEY));
  localStorage.removeItem(namespacedKey(SESSION_TIMESTAMP_KEY));
  return getOrCreateSessionId();
}

/**
 * Browser-persistent chat UI state is intentionally disabled.
 */
export function saveChatState() {
  return;
}

/**
 * Browser-persistent chat UI restore is intentionally disabled.
 */
export function restoreChatState() {
  return null;
}

/**
 * Clear all persisted chat UI state.
 */
export function clearChatStorage() {
  return;
}
