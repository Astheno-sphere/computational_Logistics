'use strict';

const fs = require('fs');

// Common locations to look for an OpenAPI/Swagger spec if the configured URL
// (or default) isn't served there — so fewer apps fall into headless mode.
const FALLBACK_SPEC_PATHS = [
  '/openapi.json', '/swagger.json', '/v3/api-docs', '/api-docs',
  '/swagger/v1/swagger.json', '/openapi.yaml',
];

function looksLikeSpec(data) {
  return !!(data && typeof data === 'object' && (data.openapi || data.swagger || data.paths));
}

/**
 * Load an OpenAPI spec from a local file (config.openApiFile) or by trying the
 * configured URL plus a list of common fallback paths. Returns { spec, source }
 * or throws if none yield a spec.
 */
async function loadSpec(config, http) {
  if (config.openApiFile) {
    const spec = JSON.parse(fs.readFileSync(config.openApiFile, 'utf8'));
    return { spec, source: config.openApiFile };
  }
  const candidates = [];
  if (config.openApiUrl) candidates.push(config.openApiUrl);
  for (const p of FALLBACK_SPEC_PATHS) if (!candidates.includes(p)) candidates.push(p);

  let lastErr = null;
  for (const url of candidates) {
    try {
      const res = await http.get(url);
      if (looksLikeSpec(res && res.data)) return { spec: res.data, source: url };
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error('no OpenAPI spec found at any known path');
}

/**
 * FastAPI adapter.
 * Fetches OpenAPI spec from /openapi.json (with fallback discovery + local-file
 * support) and optional feature flags from /health/features. Falls back to
 * headless mode only if no spec is found anywhere.
 */

function normalizeOpenApiRoutes(openapi) {
  const routes = {};

  for (const [rawPath, methods] of Object.entries(openapi.paths || {})) {
    for (const [method, op] of Object.entries(methods)) {
      if (['get', 'post', 'put', 'patch', 'delete'].includes(method)) {
        const key = `${method.toUpperCase()} ${rawPath}`;

        // Extract security requirement — FastAPI uses securitySchemes
        const requiresAuth = !!(
          (op.security && op.security.length > 0) ||
          (openapi.security && openapi.security.length > 0)
        );

        // Extract first response schema
        let responseSchema = null;
        const okResponse = (op.responses || {})['200'];
        if (okResponse) {
          const content = okResponse.content || {};
          const jsonContent = content['application/json'];
          if (jsonContent && jsonContent.schema) {
            responseSchema = resolveSchema(jsonContent.schema, openapi);
          }
        }

        let requestBody = null;
        if (op.requestBody) {
          requestBody = resolveRequestBody(op.requestBody, openapi);
        }

        // Collect path parameters
        const parameters = (op.parameters || []).filter(p => p.in === 'path').map(p => p.name);

        routes[key] = {
          summary: op.summary || '',
          tags: op.tags || [],
          requiresAuth,
          parameters,
          requestBody,
          responseSchema,
          deprecated: !!op.deprecated,
        };
      }
    }
  }

  return routes;
}

function resolveRequestBody(requestBody, openapi) {
  const content = requestBody.content || {};
  const jsonContent = content['application/json'];
  if (!jsonContent || !jsonContent.schema) return requestBody;
  return {
    ...requestBody,
    content: {
      ...content,
      'application/json': {
        ...jsonContent,
        schema: resolveSchema(jsonContent.schema, openapi),
      },
    },
  };
}

function resolveSchema(schema, openapi, depth = 0) {
  if (depth > 5) return schema; // prevent infinite recursion
  if (!schema) return null;

  if (schema.$ref) {
    const refPath = schema.$ref.replace('#/', '').split('/');
    let resolved = openapi;
    for (const segment of refPath) {
      resolved = resolved[segment];
      if (!resolved) return null;
    }
    return resolveSchema(resolved, openapi, depth + 1);
  }

  if (schema.allOf) {
    return resolveSchema(schema.allOf[0], openapi, depth + 1);
  }

  if (schema.type === 'array' && schema.items) {
    return {
      type: 'array',
      items: resolveSchema(schema.items, openapi, depth + 1),
    };
  }

  return schema;
}

function parseFeatureFlags(featuresData) {
  if (!featuresData || typeof featuresData !== 'object') return {};

  const flags = {};

  // Expected shape: { "count": N, "routers": { "/prefix": { "included", "enabled", "message" } } }
  // Generic fallback: { "features": { ... } } or the object itself
  const source = featuresData.routers || featuresData.features || featuresData;

  // Skip top-level scalar fields (count, etc.)
  for (const [prefix, info] of Object.entries(source)) {
    if (typeof info !== 'object' || info === null) continue;
    const normPrefix = prefix.startsWith('/') ? prefix : `/${prefix}`;
    flags[normPrefix] = {
      included: info.included !== false,
      enabled: info.enabled !== false,
      message: info.message || null,
    };
  }

  return flags;
}

async function fetchSpec(config, http) {
  let openapi = null;
  let featureFlags = {};
  let headless = false;

  // Try to fetch OpenAPI spec — local file, configured URL, then common fallbacks.
  try {
    const { spec, source } = await loadSpec(config, http);
    openapi = spec;
    const configured = config.openApiFile || config.openApiUrl || '/openapi.json';
    if (source !== configured) {
      process.stderr.write(`[qa-probe] OpenAPI spec found at ${source} (not ${configured}).\n`);
    }
  } catch (err) {
    headless = true;
    process.stderr.write(
      `[qa-probe] No OpenAPI spec found (tried ${config.openApiFile || config.openApiUrl || '/openapi.json'} + common fallbacks): ${err.message}\n` +
      `[qa-probe] Falling back to headless mode — HTTP status probing only.\n`
    );
  }

  // Try to fetch feature flags (FastAPI-specific, optional)
  if (!headless && config.featureStatusUrl) {
    try {
      const res = await http.get(config.featureStatusUrl);
      featureFlags = parseFeatureFlags(res.data);
    } catch {
      // /health/features is optional — not all FastAPI apps expose it
    }
  }

  return {
    routes: openapi ? normalizeOpenApiRoutes(openapi) : {},
    featureFlags,
    specUrl: config.openApiUrl,
    framework: 'fastapi',
    headless,
    rawSpec: openapi,
  };
}

function isAuthRequired(path, spec) {
  // Check if any route matching this path requires auth
  for (const [key, route] of Object.entries(spec.routes || {})) {
    const routePath = key.split(' ')[1];
    if (routePath === path || pathMatches(routePath, path)) {
      return !!route.requiresAuth;
    }
  }
  // Default: assume auth required
  return true;
}

function pathMatches(pattern, actual) {
  // Convert /items/{id} to regex /items/[^/]+
  const regex = new RegExp(
    '^' + pattern.replace(/\{[^}]+\}/g, '[^/]+').replace(/\//g, '\\/') + '$'
  );
  return regex.test(actual);
}

function buildAuthRequest(config) {
  const { auth } = config;
  if (auth.type === 'bearer') {
    return {
      method: 'POST',
      url: auth.loginUrl,
      data: auth.credentials,
    };
  }
  if (auth.type === 'api-key') {
    return null; // no login needed
  }
  return null;
}

function extractToken(loginResponse, config) {
  const { auth } = config;
  if (auth.type === 'bearer') {
    const token = loginResponse.data[auth.tokenPath];

    if (token) {
      return { Authorization: `Bearer ${token}` };
    }

    // Fallback: cookie-mode login (some apps return the JWT in a Set-Cookie header)
    const setCookies = loginResponse.headers && loginResponse.headers['set-cookie'];
    if (setCookies) {
      const cookies = Array.isArray(setCookies) ? setCookies : [setCookies];
      // Find the access token cookie — try common names
      const ACCESS_COOKIE_NAMES = ['access_token', 'jwt', 'auth_token', 'token', 'session'];
      for (const cookieStr of cookies) {
        const [nameVal] = cookieStr.split(';');
        const [name, val] = nameVal.split('=');
        if (ACCESS_COOKIE_NAMES.includes(name.trim())) {
          // Use as Bearer token (it's a JWT) and also send as Cookie for compatibility
          return {
            Authorization: `Bearer ${val.trim()}`,
            Cookie: `${name.trim()}=${val.trim()}`,
          };
        }
      }

      // If no named match, build full cookie string and send it
      const cookieHeader = cookies
        .map(c => c.split(';')[0].trim())
        .join('; ');
      return { Cookie: cookieHeader };
    }

    throw new Error(
      `Login succeeded but "${auth.tokenPath}" not found in response and no access cookie set. ` +
      `Response keys: ${Object.keys(loginResponse.data || {}).join(', ')}`
    );
  }
  if (auth.type === 'api-key') {
    return { [auth.apiKeyHeader]: auth.apiKey };
  }
  return {};
}

module.exports = { fetchSpec, isAuthRequired, buildAuthRequest, extractToken, normalizeOpenApiRoutes, loadSpec, looksLikeSpec };
