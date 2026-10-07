'use strict';

const { getAdapter } = require('../analyze/backend-fetcher');

/**
 * Authenticate against the API and return request headers.
 * Supports: bearer token, api-key, cookie, none.
 */
async function authenticate(config, http) {
  const { auth } = config;

  if (auth.type === 'none') return {};

  if (auth.type === 'api-key') {
    return { [auth.apiKeyHeader || 'X-API-Key']: auth.apiKey };
  }

  const adapter = getAdapter(config.framework);
  const authRequest = adapter.buildAuthRequest(config);
  if (!authRequest) return {};

  let loginRes;
  try {
    loginRes = await http.request({
      method: authRequest.method,
      url: authRequest.url,
      data: authRequest.data,
    });
  } catch (err) {
    throw new Error(`Authentication request failed: ${err.message}`);
  }

  if (loginRes.status >= 400) {
    throw new Error(
      `Authentication failed: ${loginRes.status} ${loginRes.statusText}. ` +
      `Check auth.credentials in your config. URL: ${authRequest.url}`
    );
  }

  return adapter.extractToken(loginRes, config);
}

module.exports = { authenticate };
