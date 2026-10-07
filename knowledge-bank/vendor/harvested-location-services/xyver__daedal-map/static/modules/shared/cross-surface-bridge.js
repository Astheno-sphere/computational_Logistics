import { getSiteBaseUrl } from '../auth.js';

let bridgeFramePromise = null;
let bridgeUnavailableUntilMs = 0;
const BRIDGE_INIT_TIMEOUT_MS = 1200;
const BRIDGE_REQUEST_TIMEOUT_MS = 1200;
const BRIDGE_FAILURE_COOLDOWN_MS = 30000;

export function getBridgeOrigin() {
  const siteBase = String(getSiteBaseUrl?.() || '').trim().replace(/\/$/, '');
  if (!siteBase) return '';
  if (siteBase === window.location.origin.replace(/\/$/, '')) return '';
  return siteBase;
}

export function canUseBridge() {
  return Boolean(getBridgeOrigin()) && Date.now() >= bridgeUnavailableUntilMs;
}

export async function getBridgeFrame() {
  if (!canUseBridge()) return null;
  if (bridgeFramePromise) return bridgeFramePromise;

  bridgeFramePromise = new Promise((resolve, reject) => {
    const bridgeOrigin = getBridgeOrigin();
    const iframe = document.createElement('iframe');
    const timeoutMs = BRIDGE_INIT_TIMEOUT_MS;
    let settled = false;

    function cleanup() {
      window.removeEventListener('message', onReady);
      window.clearTimeout(timer);
    }

    function onReady(event) {
      if (event.origin.replace(/\/$/, '') !== bridgeOrigin) return;
      if (event.data?.type !== 'dm-auth-bridge-ready') return;
      if (settled) return;
      settled = true;
      cleanup();
      resolve({ iframe, origin: bridgeOrigin });
    }

    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanup();
      try {
        iframe.remove();
      } catch (_) {}
      reject(new Error('Shared storage bridge timed out'));
    }, timeoutMs);

    window.addEventListener('message', onReady);
    iframe.hidden = true;
    iframe.setAttribute('aria-hidden', 'true');
    iframe.src = bridgeOrigin + '/auth/bridge.html';
    document.body.appendChild(iframe);
  }).catch((error) => {
    bridgeFramePromise = null;
    bridgeUnavailableUntilMs = Date.now() + BRIDGE_FAILURE_COOLDOWN_MS;
    throw error;
  });

  return bridgeFramePromise;
}

export async function postBridgeMessage(type, payload = {}) {
  const bridge = await getBridgeFrame();
  if (!bridge?.iframe?.contentWindow) {
    throw new Error('Shared storage bridge unavailable');
  }

  return await new Promise((resolve, reject) => {
    const requestId = `bridge_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    const timeoutMs = BRIDGE_REQUEST_TIMEOUT_MS;

    function cleanup() {
      window.removeEventListener('message', onMessage);
      window.clearTimeout(timer);
    }

    function onMessage(event) {
      if (event.origin.replace(/\/$/, '') !== bridge.origin) return;
      const data = event.data || {};
      if (data.type !== 'dm-bridge-response' || data.requestId !== requestId) return;
      cleanup();
      if (data.ok === false) {
        reject(new Error(data.error || 'Bridge request failed'));
        return;
      }
      resolve(data);
    }

    const timer = window.setTimeout(() => {
      cleanup();
      bridgeUnavailableUntilMs = Date.now() + BRIDGE_FAILURE_COOLDOWN_MS;
      reject(new Error('Shared storage bridge request timed out'));
    }, timeoutMs);

    window.addEventListener('message', onMessage);
    bridge.iframe.contentWindow.postMessage({ type, requestId, ...payload }, bridge.origin);
  });
}
