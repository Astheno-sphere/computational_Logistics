'use strict';

const http = require('http');
const https = require('https');
const { URL } = require('url');

/**
 * Verify that an SSE endpoint:
 *   1. Connects successfully (HTTP 200 with text/event-stream content-type)
 *   2. Delivers at least one event within firstEventTimeoutMs
 *
 * Returns: { type: 'sse', connected, firstEventMs, status, error }
 */
async function checkSSE(url, headers, config) {
  const { sse } = config.probe;
  const timeout = (sse && sse.firstEventTimeoutMs) || 5000;
  const ignoreHTTPS = config.probe.ignoreHTTPSErrors || false;

  return new Promise((resolve) => {
    const start = Date.now();
    let settled = false;

    function done(result) {
      if (settled) return;
      settled = true;
      try { req.destroy(); } catch {}
      clearTimeout(timer);
      resolve(result);
    }

    const parsed = new URL(url);
    const isHttps = parsed.protocol === 'https:';
    const lib = isHttps ? https : http;

    const reqOptions = {
      hostname: parsed.hostname,
      port: parsed.port || (isHttps ? 443 : 80),
      path: parsed.pathname + parsed.search,
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        'Cache-Control': 'no-cache',
        ...headers,
      },
      rejectUnauthorized: !ignoreHTTPS,
    };

    const timer = setTimeout(() => {
      done({
        type: 'sse',
        connected: false,
        firstEventMs: null,
        status: 'timeout',
        error: `No first event within ${timeout}ms`,
      });
    }, timeout + 2000);

    const req = lib.request(reqOptions, (res) => {
      if (res.statusCode !== 200) {
        done({
          type: 'sse',
          connected: false,
          firstEventMs: null,
          status: 'error',
          error: `HTTP ${res.statusCode}`,
        });
        return;
      }

      const contentType = res.headers['content-type'] || '';
      if (!contentType.includes('text/event-stream') && !contentType.includes('text/plain')) {
        done({
          type: 'sse',
          connected: true,
          firstEventMs: null,
          status: 'wrong_content_type',
          error: `Expected text/event-stream, got ${contentType}`,
        });
        return;
      }

      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        if (chunk && chunk.trim()) {
          const ms = Date.now() - start;
          done({ type: 'sse', connected: true, firstEventMs: ms, status: 'alive', error: null });
        }
      });

      // Set a separate timeout for first event
      setTimeout(() => {
        done({
          type: 'sse',
          connected: true,
          firstEventMs: null,
          status: 'no_events',
          error: `Connected but no events within ${timeout}ms`,
        });
      }, timeout);
    });

    req.on('error', (err) => {
      done({ type: 'sse', connected: false, firstEventMs: null, status: 'error', error: err.message });
    });

    req.end();
  });
}

module.exports = { checkSSE };
