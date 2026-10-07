/**
 * Frontend auth manager for token-aware runtime behavior.
 *
 * Hosted deployments can delegate login/account UX to an external site.
 * Self-host/local deployments can stay fully local and use /settings instead.
 */

import { readAccountContextCache, writeAccountContextCache } from './shared/account-context-cache.js';

const AUTH_EVENT = 'countymap-auth-changed';
const AUTH_BOOT_EVENT = 'countymap-auth-boot-settled';
const LOGGED_IN_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;
const GUEST_MAX_AGE_MS = 24 * 60 * 60 * 1000;
const LEGACY_SHARED_COOKIE_DOMAIN = '.daedalmap.com';
const LEGACY_SHARED_ACCESS_COOKIE = 'dm_access_token';
const LEGACY_SHARED_REFRESH_COOKIE = 'dm_refresh_token';

let authClient = null;
let authConfig = null;
let currentSession = null;
let currentProfile = null;
let initialized = false;
let _lastAuthUserId = null;
let initPromise = null;
let authBootPending = false;
let authBootSettled = false;
let authBootWaiters = [];
let runtimeSessionRefreshPromise = null;
let localWrapperSyncPromise = null;

function isLocalLikeHost(hostname) {
  const value = String(hostname || '').trim().toLowerCase();
  return value === 'localhost' || value === '127.0.0.1' || value === '0.0.0.0';
}

function currentCatalogLane() {
  if (document.body.classList.contains('chat-mode-ops')) return 'ops';
  if (document.body.classList.contains('chat-mode-research')) return 'research';
  return 'explore';
}

function localWipPreferenceKey(lane = currentCatalogLane()) {
  return `useWipCatalog:${lane}`;
}

const LOCAL_CLOUD_DATA_PREFERENCE_KEY = 'useCloudRuntime';

function currentRuntimeMode() {
  return String(authConfig?.runtime_mode || (isLocalLikeHost(window.location.hostname) ? 'local' : 'cloud'))
    .trim().toLowerCase() === 'cloud' ? 'cloud' : 'local';
}

function accountCanUseWipCatalog() {
  return Boolean(currentProfile?.is_admin || currentProfile?.plan_id === 'master');
}

function selectedCatalogSurface(lane = currentCatalogLane()) {
  return window.localStorage.getItem(localWipPreferenceKey(lane)) === '1' ? 'wip' : 'published';
}

function isLocalWrapperEnabled() {
  return Boolean(authConfig?.local_wrapper_enabled);
}

async function syncLocalWrapperAuthState() {
  if (!isLocalLikeHost(window.location.hostname) || !isLocalWrapperEnabled()) {
    return;
  }
  if (localWrapperSyncPromise) {
    return await localWrapperSyncPromise;
  }
  localWrapperSyncPromise = (async () => {
    try {
      const payload = {
        authenticated: isAuthenticated(),
        mode: isAuthenticated() ? 'hosted_account' : 'guest',
        user_id: currentSession?.user?.id || null,
        email: currentSession?.user?.email || null,
        plan_id: currentProfile?.plan_id || (isAuthenticated() ? 'free' : null),
        account_url: getAccountUrl(),
        balance_micro_usd: currentProfile?.balance_micro_usd ?? null,
      };
      await fetch('/api/local-wrapper/auth-state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      console.warn('[Auth] Local wrapper auth-state sync failed:', error?.message || error);
    } finally {
      localWrapperSyncPromise = null;
    }
  })();
  return await localWrapperSyncPromise;
}

async function restoreCatalogSurfacePreference() {
  // The UI preference lives in browser storage, whereas the local Python
  // process starts with the published catalog. Restore it before app startup
  // reaches OverlaySelector, rather than waiting for the next checkbox click.
  if (!isLocalLikeHost(window.location.hostname) || !isAuthenticated()) return;
  const lane = currentCatalogLane();
  const useWip = selectedCatalogSurface(lane) === 'wip' && accountCanUseWipCatalog();
  if (!accountCanUseWipCatalog()) {
    window.localStorage.setItem(localWipPreferenceKey(lane), '0');
  }
  try {
    const response = await fetch('/api/local/catalog-surface', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_wip: useWip, lane })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (error) {
    console.warn('Could not restore local catalog surface', error);
  }
}

async function restoreLocalDataPlanePreference() {
  if (!isLocalLikeHost(window.location.hostname) || !isLocalWrapperEnabled()) return;
  const mode = window.localStorage.getItem(LOCAL_CLOUD_DATA_PREFERENCE_KEY) === '1' ? 'cloud' : 'local';
  try {
    const response = await fetch('/api/local/data-plane', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    authConfig.runtime_mode = mode;
  } catch (error) {
    console.warn('Could not restore local data-plane preference', error);
  }
}

async function applyLocalDataPlane(mode) {
  const normalized = mode === 'cloud' ? 'cloud' : 'local';
  const activeOverlays = window.OverlaySelector?.getActiveOverlays?.() || [];
  const response = await fetch('/api/local/data-plane', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: normalized })
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  authConfig.runtime_mode = normalized;
  window.localStorage.setItem(LOCAL_CLOUD_DATA_PREFERENCE_KEY, normalized === 'cloud' ? '1' : '0');
  window.dispatchEvent(new CustomEvent('local-data-plane-changed', {
    detail: { dataPlaneMode: normalized }
  }));
  await window.OverlaySelector?.init?.({ restoreState: true });
  for (const overlayId of activeOverlays) {
    await window.OverlayController?.reloadOverlay?.(overlayId);
  }
}

async function applyCatalogSurface(catalogSurface, lane = currentCatalogLane()) {
  const useWip = catalogSurface === 'wip';
  if (useWip && !accountCanUseWipCatalog()) {
    throw new Error('WIP catalog access requires a master or admin account');
  }
  const response = await fetch('/api/local/catalog-surface', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_wip: useWip, lane })
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  window.localStorage.setItem(localWipPreferenceKey(lane), useWip ? '1' : '0');
  window.dispatchEvent(new CustomEvent('local-catalog-surface-changed', {
    detail: { catalogSurface: useWip ? 'wip' : 'published', lane }
  }));
  await window.OverlaySelector?.init?.({ restoreState: true });
}

function getLocalLinkedSiteBase() {
  if (!isLocalLikeHost(window.location.hostname)) return '';
  return `${window.location.protocol}//${window.location.hostname}:8080`;
}

function getSiteBase() {
  const configured = String(authConfig?.site_url || '').trim().replace(/\/$/, '');
  const localLinked = getLocalLinkedSiteBase();
  if (localLinked) return localLinked;
  if (configured) return configured;
  return window.location.origin;
}

function getAccountUrl() {
  const configured = String(currentProfile?.account_url || authConfig?.account_url || '/settings').trim() || '/settings';
  const localLinked = getLocalLinkedSiteBase();
  if (localLinked) return `${localLinked}/account`;
  if (configured) return configured;
  return '/settings';
}

async function fetchProfile({ forceRefresh = false } = {}) {
  try {
    const token = currentSession?.access_token;
    const userId = currentSession?.user?.id || '';
    if (!token) {
      currentProfile = null;
      return;
    }
    if (userId && !forceRefresh) {
      const cached = await readAccountContextCache(userId);
      if (cached && Object.prototype.hasOwnProperty.call(cached, 'ops_feeds')) {
        currentProfile = cached;
        return;
      }
    }
    const resp = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!resp.ok) {
      currentProfile = null;
      return;
    }
    const buf = await resp.arrayBuffer();
    const mp = window.MessagePack || {};
    currentProfile = mp.decode ? mp.decode(new Uint8Array(buf)) : null;
    if (currentProfile?.user_id) {
      await writeAccountContextCache({
        ...currentProfile,
        savedAt: Date.now()
      });
    }
  } catch (_error) {
    currentProfile = null;
  }
}

function readHashSessionTokens() {
  const raw = String(window.location.hash || '').replace(/^#/, '');
  if (!raw || !raw.includes('access_token=')) return null;
  const params = new URLSearchParams(raw);
  const accessToken = params.get('access_token');
  const refreshToken = params.get('refresh_token');
  if (!accessToken || !refreshToken) return null;
  return {
    access_token: accessToken,
    refresh_token: refreshToken
  };
}

function readHashHandoffCode() {
  const raw = String(window.location.hash || '').replace(/^#/, '');
  if (!raw || !raw.includes('handoff_code=')) return null;
  const params = new URLSearchParams(raw);
  const code = params.get('handoff_code');
  return code ? String(code).trim() : null;
}

function readWindowNameHandoffCode() {
  const raw = String(window.name || '').trim();
  if (!raw.startsWith('dm_handoff:')) return null;
  const code = raw.slice('dm_handoff:'.length).trim();
  return code || null;
}

function clearWindowNameHandoffCode() {
  const raw = String(window.name || '').trim();
  if (raw.startsWith('dm_handoff:')) {
    window.name = '';
  }
}

function readHashLogoutSignal() {
  const raw = String(window.location.hash || '').replace(/^#/, '');
  if (!raw || !raw.includes('logout=')) return null;
  const params = new URLSearchParams(raw);
  if (params.get('logout') !== '1') return null;
  return {
    returnTo: params.get('return_to') || ''
  };
}

function clearLegacySharedCookie(name) {
  document.cookie = `${name}=; domain=${LEGACY_SHARED_COOKIE_DOMAIN}; path=/; max-age=0; samesite=lax; secure`;
}

function clearLegacySharedCookies() {
  clearLegacySharedCookie(LEGACY_SHARED_ACCESS_COOKIE);
  clearLegacySharedCookie(LEGACY_SHARED_REFRESH_COOKIE);
}

async function importHashSession(client) {
  const tokens = readHashSessionTokens();
  if (!tokens) return null;
  try {
    const { data, error } = await client.auth.setSession(tokens);
    if (error) {
      console.warn('[Auth] Session handoff failed:', error.message);
      return null;
    }
    return data?.session || null;
  } finally {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
}

async function exchangeHandoffCodeSession(client, code) {
  if (!code) return null;
  try {
    const response = await fetch(`${getSiteBase()}/api/auth/handoff/exchange`, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    const accessToken = payload?.access_token;
    const refreshToken = payload?.refresh_token;
    if (!accessToken || !refreshToken) {
      throw new Error('Incomplete handoff payload');
    }
    const { data, error } = await client.auth.setSession({
      access_token: accessToken,
      refresh_token: refreshToken
    });
    if (error) {
      throw error;
    }
    return data?.session || null;
  } catch (error) {
    console.warn('[Auth] Handoff exchange failed:', error?.message || error);
    return null;
  }
}

function openSiteWithHiddenHandoff(targetUrl, handoffCode, targetBlank = false) {
  if (!handoffCode || !targetUrl) return false;
  const handoffName = `dm_handoff:${handoffCode}`;
  if (targetBlank) {
    const popup = window.open('', '_blank');
    if (!popup) return false;
    try {
      popup.name = handoffName;
      popup.opener = null;
      popup.location.replace(targetUrl);
      return true;
    } catch (_) {
      try {
        popup.close();
      } catch (_) {}
      return false;
    }
  }
  window.name = handoffName;
  window.location.href = targetUrl;
  return true;
}

async function createSecureSiteHandoff(targetUrl) {
  const siteBase = getSiteBase();
  const accessToken = currentSession?.access_token;
  const refreshToken = currentSession?.refresh_token;
  if (!siteBase || !accessToken || !refreshToken) return null;

  try {
    const response = await fetch(`${siteBase}/api/auth/handoff/create`, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`
      },
      body: JSON.stringify({
        return_to: targetUrl,
        refresh_token: refreshToken
      })
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload?.handoff_code || !payload?.return_to) {
      throw new Error(payload?.error || `HTTP ${response.status}`);
    }
    return {
      handoffCode: payload.handoff_code,
      returnTo: payload.return_to
    };
  } catch (error) {
    console.warn('[Auth] Secure site handoff failed:', error?.message || error);
    return null;
  }
}

async function navigateToHostedAccount(targetUrl, options = {}) {
  const destination = String(targetUrl || '').trim();
  if (!destination) return false;
  try {
    const dest = new URL(destination, window.location.origin);
    if (dest.origin === window.location.origin) {
      if (options.targetBlank) {
        window.open(dest.toString(), '_blank', 'noopener');
      } else {
        window.location.href = dest.toString();
      }
      return true;
    }
    const handoff = await createSecureSiteHandoff(dest.toString());
    if (handoff && openSiteWithHiddenHandoff(handoff.returnTo, handoff.handoffCode, options.targetBlank === true)) {
      return true;
    }
    if (options.targetBlank) {
      window.open(dest.toString(), '_blank', 'noopener');
    } else {
      window.location.href = dest.toString();
    }
    return true;
  } catch (_) {
    if (options.targetBlank) {
      window.open(destination, '_blank', 'noopener');
    } else {
      window.location.href = destination;
    }
    return true;
  }
}

async function importHandoffCodeSession(client) {
  const code = readWindowNameHandoffCode() || readHashHandoffCode();
  if (!code) return null;
  try {
    return await exchangeHandoffCodeSession(client, code);
  } finally {
    clearWindowNameHandoffCode();
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }
}

async function trySilentSiteSessionImport(client) {
  const siteBase = getSiteBase();
  if (!siteBase || siteBase.replace(/\/$/, '') === window.location.origin.replace(/\/$/, '')) {
    return null;
  }

  return await new Promise((resolve) => {
    const iframe = document.createElement('iframe');
    const bridgeUrl = `${siteBase.replace(/\/$/, '')}/auth/bridge.html`;
    const timeoutMs = 3500;
    let settled = false;
    let readyPosted = false;

    function cleanup(session = null) {
      if (settled) return;
      settled = true;
      window.removeEventListener('message', onMessage);
      window.clearTimeout(timer);
      try {
        iframe.remove();
      } catch (_) {}
      resolve(session);
    }

    async function requestHandoff() {
      if (readyPosted || !iframe.contentWindow) return;
      readyPosted = true;
      iframe.contentWindow.postMessage({
        type: 'dm-request-auth-handoff',
        returnTo: window.location.origin + window.location.pathname + window.location.search
      }, siteBase.replace(/\/$/, ''));
    }

    async function onMessage(event) {
      const expectedOrigin = siteBase.replace(/\/$/, '');
      if (event.origin.replace(/\/$/, '') !== expectedOrigin) return;
      const data = event.data || {};
      if (data?.type === 'dm-auth-bridge-ready') {
        await requestHandoff();
        return;
      }
      if (data?.type !== 'dm-auth-handoff-result') return;
      if (!data?.ok || !data?.handoffCode) {
        cleanup(null);
        return;
      }
      const session = await exchangeHandoffCodeSession(client, String(data.handoffCode || '').trim());
      cleanup(session);
    }

    const timer = window.setTimeout(() => cleanup(null), timeoutMs);
    window.addEventListener('message', onMessage);
    iframe.hidden = true;
    iframe.setAttribute('aria-hidden', 'true');
    iframe.src = bridgeUrl;
    iframe.addEventListener('load', () => {
      requestHandoff().catch(() => cleanup(null));
    }, { once: true });
    document.body.appendChild(iframe);
  });
}

async function consumeLogoutSignal(client) {
  const signal = readHashLogoutSignal();
  if (!signal) return false;
  try {
    await client.auth.signOut();
  } catch (error) {
    console.warn('[Auth] Logout bridge failed:', error?.message || error);
  } finally {
    currentSession = null;
    currentProfile = null;
    _lastAuthUserId = null;
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  }

  const returnTo = String(signal.returnTo || '').trim();
  if (returnTo) {
    try {
      const dest = new URL(returnTo, window.location.origin);
      const allowedOrigins = new Set([window.location.origin, getSiteBase()]);
      if (allowedOrigins.has(dest.origin)) {
        window.location.replace(dest.toString());
        return true;
      }
    } catch (_) {
      // Fall through to default signed-out state.
    }
  }
  return false;
}

function emitAuthChanged() {
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, {
    detail: {
      isAuthenticated: isAuthenticated(),
      user: getCurrentUser()
    }
  }));
}

function flushAuthBootWaiters() {
  const waiters = authBootWaiters.slice();
  authBootWaiters = [];
  for (const resolve of waiters) {
    try {
      resolve(currentSession);
    } catch (_) {
      // Ignore waiter resolution errors.
    }
  }
}

function markAuthBootPending() {
  authBootPending = true;
  authBootSettled = false;
}

function markAuthBootSettled() {
  authBootPending = false;
  authBootSettled = true;
  flushAuthBootWaiters();
  window.dispatchEvent(new CustomEvent(AUTH_BOOT_EVENT, {
    detail: {
      isAuthenticated: isAuthenticated(),
      user: getCurrentUser()
    }
  }));
}

async function loadConfig() {
  const response = await fetch('/api/auth/config');
  if (!response.ok) {
    throw new Error(`Failed to load auth config: ${response.status}`);
  }
  return response.json();
}

function getBrowserSupabase() {
  if (!window.supabase?.createClient) {
    throw new Error('Supabase browser client not loaded');
  }
  return window.supabase;
}

function updateDom() {
  const btn = document.getElementById('authBtn');
  const status = document.getElementById('authStatusText');
  if (!btn || !status) return;

  if (!authConfig?.enabled) {
    btn.textContent = 'Local Setup';
    btn.disabled = false;
    btn.classList.remove('logged-in');
    status.innerHTML = 'Local mode: no hosted account required. Set your LLM key and local data path in <a href="/settings">settings</a>.';
    return;
  }

  if (isAuthenticated()) {
    const email = getCurrentUser()?.email || 'Signed in';
    const accountUrl = getAccountUrl();
    btn.textContent = 'Account';
    btn.disabled = false;
    btn.classList.add('logged-in');
    const currentLane = currentCatalogLane();
    const runtimeMode = currentRuntimeMode();
    const catalogSurface = selectedCatalogSurface(currentLane);
    const canUseWip = accountCanUseWipCatalog();
    const surfaceControl = `<div style="margin-top:6px">`
      + (isLocalWrapperEnabled()
        ? `<label style="display:block;margin-top:4px"><input type="checkbox" data-cloud-runtime-toggle${runtimeMode === 'cloud' ? ' checked' : ''}> Use cloud data</label>`
        : '')
      + (isLocalWrapperEnabled() && canUseWip
        ? `<label style="display:block;margin-top:4px"><input type="checkbox" data-wip-catalog-toggle${catalogSurface === 'wip' ? ' checked' : ''}> Use WIP catalog</label>`
        : '')
      + `</div>`;
    const accountLabel = isLocalLikeHost(window.location.hostname)
      ? 'Open account settings (hosted sign-in may be required)'
      : 'Open account settings';
    status.innerHTML = `Signed in${isLocalLikeHost(window.location.hostname) ? ' locally' : ''} as ${email}. <a href="${accountUrl}" target="_blank" rel="noopener" data-secure-account-link="1">${accountLabel}</a>${surfaceControl}`;
    const accountLink = status.querySelector('[data-secure-account-link]');
    if (accountLink) {
      accountLink.addEventListener('click', async (event) => {
        event.preventDefault();
        await navigateToHostedAccount(accountUrl, { targetBlank: true });
      });
    }
    const cloudToggle = status.querySelector('[data-cloud-runtime-toggle]');
    const wipToggle = status.querySelector('[data-wip-catalog-toggle]');
    if (cloudToggle) {
      cloudToggle.addEventListener('change', async () => {
        const nextRuntime = cloudToggle.checked ? 'cloud' : 'local';
        cloudToggle.disabled = true;
        if (wipToggle) wipToggle.disabled = true;
        try {
          await applyLocalDataPlane(nextRuntime);
          updateDom();
        } catch (error) {
          console.warn('Could not switch local data plane', error);
          cloudToggle.checked = !cloudToggle.checked;
        } finally {
          cloudToggle.disabled = false;
          if (wipToggle) wipToggle.disabled = false;
        }
      });
    }
    if (wipToggle) {
      wipToggle.addEventListener('change', async () => {
        const nextSurface = wipToggle.checked ? 'wip' : 'published';
        wipToggle.disabled = true;
        if (cloudToggle) cloudToggle.disabled = true;
        try {
          await applyCatalogSurface(nextSurface, currentLane);
          updateDom();
        } catch (error) {
          console.warn('Could not switch catalog surface', error);
          wipToggle.checked = !wipToggle.checked;
        } finally {
          wipToggle.disabled = false;
          if (cloudToggle) cloudToggle.disabled = false;
        }
      });
    }
  } else {
    btn.textContent = 'Sign In';
    btn.disabled = false;
    btn.classList.remove('logged-in');
    status.innerHTML = `Guest mode: local-only workspace and cache. <a href="${getSiteBase()}/login" target="_blank" rel="noopener">Create account</a>`;
  }
}

async function handleAuthClick() {
  if (!authConfig?.enabled) {
    window.location.href = '/settings';
    return;
  }
  if (isAuthenticated()) {
    await navigateToHostedAccount(getAccountUrl(), { targetBlank: true });
    return;
  }
  const targetUrl = `${getSiteBase()}/account?return=${encodeURIComponent(window.location.href)}`;
  window.open(targetUrl, '_blank', 'noopener');
}

export const AuthManager = {
  async init() {
    if (initialized) {
      updateDom();
      return;
    }
    if (initPromise) {
      return initPromise;
    }

    initPromise = (async () => {
      markAuthBootPending();
      try {
        authConfig = await loadConfig();
        if (authConfig.enabled) {
          const supabase = getBrowserSupabase();
          authClient = supabase.createClient(authConfig.supabase_url, authConfig.supabase_anon_key, {
            auth: {
              persistSession: true,
              autoRefreshToken: true,
              storageKey: 'countymap-auth',
              storage: window.localStorage
            }
          });
          const logoutRedirected = await consumeLogoutSignal(authClient);
          if (logoutRedirected) {
            return;
          }
          const handoffSession = await importHandoffCodeSession(authClient) || await importHashSession(authClient);
          const { data, error } = await authClient.auth.getSession();
          if (!error) {
            currentSession = handoffSession || data.session || await trySilentSiteSessionImport(authClient);
            _lastAuthUserId = currentSession?.user?.id ?? null;
            clearLegacySharedCookies();
            await fetchProfile();
            await syncLocalWrapperAuthState();
            await restoreLocalDataPlanePreference();
            await restoreCatalogSurfacePreference();
            updateDom();
          }
          authClient.auth.onAuthStateChange(async (_event, session) => {
            const newUserId = session?.user?.id ?? null;
            const userChanged = newUserId !== _lastAuthUserId;
            _lastAuthUserId = newUserId;
            currentSession = session;
            clearLegacySharedCookies();
            await fetchProfile();
            await syncLocalWrapperAuthState();
            await restoreLocalDataPlanePreference();
            await restoreCatalogSurfacePreference();
            updateDom();
            if (userChanged && (_event === 'SIGNED_IN' || _event === 'SIGNED_OUT')) {
              emitAuthChanged();
            }
          });
        }
      } catch (error) {
        console.warn('[Auth] Disabled:', error.message);
        authConfig = { enabled: false, supabase_url: '', supabase_anon_key: '', local_wrapper_enabled: false };
      }

      const btn = document.getElementById('authBtn');
      if (btn) {
        btn.addEventListener('click', handleAuthClick);
      }

      initialized = true;
      await syncLocalWrapperAuthState();
      await restoreLocalDataPlanePreference();
      await restoreCatalogSurfacePreference();
      updateDom();
      markAuthBootSettled();
      emitAuthChanged();
    })();

    try {
      await initPromise;
    } finally {
      if (authBootPending) {
        markAuthBootSettled();
      }
    }
  }
};

export function onAuthChanged(callback) {
  window.addEventListener(AUTH_EVENT, callback);
}

export function isAuthenticated() {
  return Boolean(currentSession?.user);
}

export function isAuthBootPending() {
  return authBootPending;
}

export async function waitForAuthBoot(timeoutMs = 2500) {
  if (authBootSettled || !authBootPending) {
    return currentSession;
  }
  return await new Promise((resolve) => {
    let timer = null;
    const done = (session) => {
      if (timer != null) {
        window.clearTimeout(timer);
      }
      resolve(session);
    };
    authBootWaiters.push(done);
    if (timeoutMs > 0) {
      timer = window.setTimeout(() => {
        const index = authBootWaiters.indexOf(done);
        if (index >= 0) {
          authBootWaiters.splice(index, 1);
        }
        resolve(currentSession);
      }, timeoutMs);
    }
  });
}

export function getCurrentUser() {
  return currentSession?.user || null;
}

export function getAccessToken() {
  return currentSession?.access_token || null;
}

export async function refreshRuntimeSession({ forceSessionRefresh = false, forceProfileRefresh = false } = {}) {
  if (!authClient || !authConfig?.enabled) {
    return null;
  }
  if (runtimeSessionRefreshPromise) {
    return await runtimeSessionRefreshPromise;
  }
  runtimeSessionRefreshPromise = (async () => {
    try {
      const current = await authClient.auth.getSession();
      const currentError = current?.error;
      if (currentError) {
        throw currentError;
      }
      let session = current?.data?.session || null;
      if (forceSessionRefresh && session?.refresh_token) {
        const refreshed = await authClient.auth.refreshSession();
        const refreshError = refreshed?.error;
        if (refreshError) {
          throw refreshError;
        }
        session = refreshed?.data?.session || session;
      }
      currentSession = session;
      _lastAuthUserId = currentSession?.user?.id ?? null;
      clearLegacySharedCookies();
      await fetchProfile({ forceRefresh: forceProfileRefresh });
      updateDom();
      return currentSession;
    } catch (error) {
      console.warn('[Auth] Runtime session refresh failed:', error?.message || error);
      return null;
    } finally {
      runtimeSessionRefreshPromise = null;
    }
  })();
  return await runtimeSessionRefreshPromise;
}

export async function ensureRuntimeAccessToken() {
  if (currentSession?.access_token) {
    return currentSession.access_token;
  }
  const session = await refreshRuntimeSession();
  return session?.access_token || null;
}

export function getStorageNamespace() {
  const user = getCurrentUser();
  return user?.id ? `user:${user.id}` : 'guest';
}

export function getSessionMaxAgeMs() {
  return isAuthenticated() ? LOGGED_IN_MAX_AGE_MS : GUEST_MAX_AGE_MS;
}

export function getCurrentProfile() {
  return currentProfile;
}

export function getSupabaseClient() {
  return authClient;
}

export function getSiteBaseUrl() {
  return getSiteBase();
}
