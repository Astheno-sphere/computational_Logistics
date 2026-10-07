/**
 * MessagePack fetch utilities
 * All API calls should use these instead of raw fetch()
 *
 * MessagePack library loaded via CDN, available as window.MessagePack
 */

import { getAccessToken } from '../auth.js';

// Get MessagePack from global scope (loaded via CDN)
const msgpack = window.MessagePack || {};
let activeRequestCount = 0;
let loadingIndicatorTimer = null;
const activeLoadingLabels = [];
const activeAbortControllers = new Set();

function buildAuthHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function getGlobalLoadingIndicator() {
  return document.getElementById('loadingIndicator');
}

function getGlobalLoadingText() {
  return document.querySelector('#loadingIndicator .map-loading-text');
}

function getGlobalLoadingCancelButton() {
  return document.getElementById('cancelLoadingButton');
}

function inferLoadingLabel(url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();

  if (url.includes('/geometry/index')) {
    const levelMatch = url.match(/admin_level=(\d+)/);
    const level = levelMatch ? Number(levelMatch[1]) : null;
    if (level === 0) return 'Loading countries...';
    if (level === 1) return 'Loading states...';
    if (level === 2) return 'Loading counties...';
    if (level === 3) return 'Loading local areas...';
    return 'Loading map index...';
  }
  if (url.includes('/geometry/selection') || url.includes('/geometry/display-features')) {
    return 'Loading map shapes...';
  }
  if (url.includes('/geometry/countries')) return 'Loading countries...';
  if (url.includes('/geometry/viewport')) return 'Loading map view...';
  if (url.includes('/api/earthquakes/')) return 'Loading earthquakes...';
  if (url.includes('/api/storms/')) return 'Loading storms...';
  if (url.includes('/api/eruptions/') || url.includes('/api/volcanoes/')) return 'Loading volcanoes...';
  if (url.includes('/api/wildfires/')) return 'Loading wildfires...';
  if (url.includes('/api/tornadoes/')) return 'Loading tornadoes...';
  if (url.includes('/api/tsunamis/')) return 'Loading tsunamis...';
  if (url.includes('/api/floods/')) return 'Loading floods...';
  if (url.includes('/api/weather/') || url.includes('/api/climate/')) return 'Loading climate data...';
  if (url.includes('/api/catalog/')) return 'Loading catalog...';
  if (url.includes('/reference/admin-levels')) return 'Loading admin level names...';
  if (url.includes('/reference/')) return 'Loading helper data...';
  if (url.includes('/chat')) return 'Thinking...';
  if (method === 'POST') return 'Sending request...';
  return 'Loading data...';
}

function syncGlobalLoadingIndicator() {
  const indicator = getGlobalLoadingIndicator();
  const text = getGlobalLoadingText();
  const cancelButton = getGlobalLoadingCancelButton();
  if (!indicator) return;
  if (text) {
    text.textContent = activeLoadingLabels.length > 0
      ? activeLoadingLabels[activeLoadingLabels.length - 1]
      : 'Loading data...';
  }
  if (cancelButton) {
    cancelButton.disabled = activeRequestCount <= 0;
  }
  if (activeRequestCount > 0) {
    if (loadingIndicatorTimer == null) {
      loadingIndicatorTimer = window.setTimeout(() => {
        if (activeRequestCount > 0) {
          indicator.classList.add('visible');
          indicator.setAttribute('aria-hidden', 'false');
        }
        loadingIndicatorTimer = null;
      }, 150);
    }
  } else {
    if (loadingIndicatorTimer != null) {
      window.clearTimeout(loadingIndicatorTimer);
      loadingIndicatorTimer = null;
    }
    indicator.classList.remove('visible');
    indicator.setAttribute('aria-hidden', 'true');
  }
}

export function cancelActiveRequests() {
  for (const controller of [...activeAbortControllers]) {
    try {
      controller.abort();
    } catch (error) {
      console.warn('Could not abort active request', error);
    }
  }
}

export function logExecutedOrder(order) {
  void order;
}

/**
 * Fetch data from API endpoint with MessagePack decoding.
 * @param {string} url - API endpoint
 * @param {object} options - fetch options (optional)
 * @returns {Promise<any>} Decoded response data
 */
export async function fetchMsgpack(url, options = {}) {
  // Some small, non-blocking helpers are deliberately fetched in the
  // background. They must remain abortable/authenticated, but should not make
  // the map-wide loading scrim imply that visible map data is still loading.
  const { silent = false, ...requestOptions } = options;
  const loadingLabel = inferLoadingLabel(url, options);
  const requestController = new AbortController();
  activeAbortControllers.add(requestController);
  if (requestOptions.signal) {
    if (requestOptions.signal.aborted) {
      requestController.abort();
    } else {
      requestOptions.signal.addEventListener('abort', () => requestController.abort(), { once: true });
    }
  }
  if (!silent) {
    activeRequestCount += 1;
    activeLoadingLabels.push(loadingLabel);
    syncGlobalLoadingIndicator();
  }

  try {
    const response = await fetch(url, {
      ...requestOptions,
      signal: requestController.signal,
      headers: {
        'Accept': 'application/msgpack',
        ...buildAuthHeaders(),
        ...requestOptions.headers,
      }
    });

    if (!response.ok) {
      let errorMsg = 'Request failed';
      let errorPayload = null;
      try {
        const buffer = await response.arrayBuffer();
        const decoded = msgpack.decode(new Uint8Array(buffer));
        errorPayload = decoded;
        errorMsg = decoded.message || decoded.error || errorMsg;
      } catch (e) {
        errorMsg = response.statusText;
      }
      const error = new Error(errorMsg);
      error.status = response.status;
      if (errorPayload && typeof errorPayload === 'object') {
        error.data = errorPayload;
      }
      throw error;
    }

    const buffer = await response.arrayBuffer();
    return msgpack.decode(new Uint8Array(buffer));
  } finally {
    activeAbortControllers.delete(requestController);
    if (!silent) {
      activeRequestCount = Math.max(0, activeRequestCount - 1);
      const labelIndex = activeLoadingLabels.lastIndexOf(loadingLabel);
      if (labelIndex >= 0) {
        activeLoadingLabels.splice(labelIndex, 1);
      }
      syncGlobalLoadingIndicator();
    }
  }
}

/**
 * POST data to API endpoint with MessagePack encoding/decoding.
 * @param {string} url - API endpoint
 * @param {object} data - Data to send
 * @param {object} options - Additional fetch options
 * @returns {Promise<any>} Decoded response data
 */
export async function postMsgpack(url, data, options = {}) {
  return fetchMsgpack(url, {
    ...options,
    method: 'POST',
    headers: {
      'Content-Type': 'application/msgpack',
      ...buildAuthHeaders(),
      ...options.headers,
    },
    body: msgpack.encode(data)
  });
}

/**
 * GET request with query params and MessagePack response.
 * @param {string} url - Base URL
 * @param {object} params - Query parameters
 * @returns {Promise<any>} Decoded response data
 */
export async function getMsgpack(url, params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const fullUrl = queryString ? `${url}?${queryString}` : url;
  return fetchMsgpack(fullUrl);
}
