'use strict';

const WebSocket = require('ws');

/**
 * Verify that a WebSocket endpoint:
 *   1. Upgrades successfully
 *   2. Delivers at least one frame within firstFrameTimeoutMs
 *
 * Returns: { type: 'ws', connected, firstFrameMs, status, error }
 */
async function checkWS(url, headers, config) {
  const { ws } = config.probe;
  const timeout = (ws && ws.firstFrameTimeoutMs) || 5000;
  const ignoreHTTPS = config.probe.ignoreHTTPSErrors || false;

  // Convert http(s) URL to ws(s)
  const wsUrl = url.replace(/^https:\/\//, 'wss://').replace(/^http:\/\//, 'ws://');

  return new Promise((resolve) => {
    const start = Date.now();
    let settled = false;

    function done(result) {
      if (settled) return;
      settled = true;
      try { socket.close(); } catch {}
      clearTimeout(timer);
      resolve(result);
    }

    const timer = setTimeout(() => {
      done({
        type: 'ws',
        connected: false,
        firstFrameMs: null,
        status: 'timeout',
        error: `No first frame within ${timeout}ms`,
      });
    }, timeout + 2000);

    let socket;
    try {
      socket = new WebSocket(wsUrl, {
        headers,
        rejectUnauthorized: !ignoreHTTPS,
        handshakeTimeout: timeout,
      });
    } catch (err) {
      clearTimeout(timer);
      return resolve({ type: 'ws', connected: false, firstFrameMs: null, status: 'error', error: err.message });
    }

    socket.on('open', () => {
      // Connected — now wait for first frame
      setTimeout(() => {
        done({
          type: 'ws',
          connected: true,
          firstFrameMs: null,
          status: 'no_frames',
          error: `Connected but no frames within ${timeout}ms`,
        });
      }, timeout);
    });

    socket.on('message', () => {
      const ms = Date.now() - start;
      done({ type: 'ws', connected: true, firstFrameMs: ms, status: 'alive', error: null });
    });

    socket.on('error', (err) => {
      done({ type: 'ws', connected: false, firstFrameMs: null, status: 'error', error: err.message });
    });

    socket.on('unexpected-response', (req, res) => {
      done({
        type: 'ws',
        connected: false,
        firstFrameMs: null,
        status: 'error',
        error: `Unexpected HTTP ${res.statusCode} during WS upgrade`,
      });
    });
  });
}

module.exports = { checkWS };
