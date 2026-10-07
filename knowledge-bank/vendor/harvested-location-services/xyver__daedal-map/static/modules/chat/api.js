/**
 * Chat API Communication
 * Handles all HTTP communication with the chat backend.
 * Supports both msgpack and streaming SSE endpoints.
 * Reusable across map app and admin dashboard.
 */

import { postMsgpack } from '../utils/fetch.js';
import { getAccessToken } from '../auth.js';

/**
 * Get the appropriate API URL, respecting API_BASE_URL if set.
 * @param {string} path - API path (e.g., '/chat', '/chat/stream')
 * @returns {string} Full API URL
 */
export function getApiUrl(path) {
  if (typeof API_BASE_URL !== 'undefined' && API_BASE_URL) {
    return `${API_BASE_URL}${path}`;
  }
  return path;
}

/**
 * Send a chat request via msgpack.
 * @param {Object} payload - Full request payload (query, viewport, history, etc.)
 * @returns {Promise<Object>} Parsed response
 */
export async function sendChatRequest(payload, path = '/chat') {
  const url = getApiUrl(path);
  return await postMsgpack(url, payload);
}

/**
 * Send a streaming chat request via SSE.
 * Parses Server-Sent Events and calls onProgress for each stage.
 * @param {Object} payload - Full request payload
 * @param {Function} onProgress - Callback: (stage, message) => void
 * @returns {Promise<Object|null>} Final result object, or null if no result
 */
export async function sendStreamingRequest(payload, onProgress, path = '/chat/stream') {
  const url = getApiUrl(path);
  const token = getAccessToken();

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    let payload = null;
    let message = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const contentType = String(response.headers.get('content-type') || '').toLowerCase();
      if (contentType.includes('application/json') || contentType.includes('text/json')) {
        payload = await response.json();
      } else {
        const text = await response.text();
        if (text) {
          payload = JSON.parse(text);
        }
      }
      if (payload && typeof payload === 'object') {
        message = payload.message || payload.error || message;
      }
    } catch (error) {
      // Fall back to the default HTTP status message.
    }
    const err = new Error(message);
    err.status = response.status;
    if (payload && typeof payload === 'object') {
      err.data = payload;
    }
    throw err;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let result = null;
  let buffer = '';
  let deltaText = '';

  const processSseLine = (line) => {
    if (!line.startsWith('data: ')) return;
    try {
      const data = JSON.parse(line.slice(6));

      if (data.stage === 'complete') {
        result = data.result;
        if (deltaText && result && result.type === 'chat') {
          result.message = deltaText;
          result._streamed = true;
        }
      } else if (data.stage === 'delta') {
        const text = data.text || data.message || '';
        deltaText += text;
        if (onProgress) {
          onProgress(data.stage, text, deltaText, data);
        }
      } else if (data.stage === 'answer_start') {
        if (onProgress) {
          onProgress(data.stage, data.message || '', deltaText, data);
        }
      } else if (onProgress) {
        onProgress(data.stage, data.message, deltaText, data);
      }
    } catch (e) {
      console.warn('Failed to parse SSE data:', line);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Process complete SSE events
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';  // Keep incomplete line in buffer

    for (const line of lines) {
      processSseLine(line);
    }
  }

  const trailingLine = buffer.trim();
  if (trailingLine) {
    processSseLine(trailingLine);
  }

  return result;
}

/**
 * Queue an order for background processing.
 * @param {Array} items - Order items
 * @param {Object} hints - Order hints (summary, etc.)
 * @param {string} sessionId - Current session ID
 * @returns {Promise<Object>} { queue_id, position }
 */
export async function queueOrder(items, hints, sessionId) {
  const url = getApiUrl('/api/orders/queue');
  return await postMsgpack(url, {
    items,
    hints,
    session_id: sessionId
  });
}

/**
 * Check status of queued orders.
 * @param {Array<string>} queueIds - Queue IDs to check
 * @returns {Promise<Object>} Map of queue_id -> status
 */
export async function checkOrderStatus(queueIds, sessionId) {
  const url = getApiUrl('/api/orders/status');
  return await postMsgpack(url, {
    queue_ids: queueIds,
    session_id: sessionId
  });
}

/**
 * Cancel a queued order.
 * @param {string} queueId - Queue ID to cancel
 * @returns {Promise<Object>} Response
 */
export async function cancelOrder(queueId, sessionId) {
  const url = getApiUrl('/api/orders/cancel');
  return await postMsgpack(url, {
    queue_id: queueId,
    session_id: sessionId
  });
}

/**
 * Clear a session on the backend (fire and forget).
 * @param {string} sessionId - Session ID to clear
 */
export async function clearBackendSession(sessionId) {
  try {
    await postMsgpack('/api/session/clear', { sessionId });
  } catch (e) {
    console.log('[Session] Backend clear skipped:', e.message);
  }
}
