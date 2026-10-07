'use strict';

const axios = require('axios');
const https = require('https');

/**
 * Create a pre-configured axios instance for probing.
 */
function createHttpClient(config) {
  const httpsAgent = config.probe.ignoreHTTPSErrors
    ? new https.Agent({ rejectUnauthorized: false })
    : undefined;

  // Cap the buffered response so an endpoint that floods the socket (e.g. an
  // accidental streaming/LLM route) can't be read into memory unbounded. The
  // per-request wall-clock abort in endpoint-runner covers the slow-trickle case;
  // this covers the fast-flood case.
  const maxBytes = (config.probe && config.probe.maxResponseBytes) || 25 * 1024 * 1024;

  return axios.create({
    baseURL: config.baseUrl,
    timeout: config.probe.timeoutMs,
    httpsAgent,
    maxContentLength: maxBytes,
    maxBodyLength: maxBytes,
    validateStatus: () => true, // never throw on HTTP errors — we inspect status ourselves
  });
}

/**
 * Get the right adapter for the configured framework.
 */
function getAdapter(framework) {
  switch (framework) {
    case 'express': return require('./adapters/express');
    case 'graphql': return require('./adapters/graphql');
    case 'nextjs':  return require('./adapters/fastapi'); // next uses same OpenAPI shape
    case 'generic': return require('./adapters/generic');
    case 'trpc':    return require('./adapters/trpc');
    default:        return require('./adapters/fastapi');
  }
}

module.exports = { createHttpClient, getAdapter };
