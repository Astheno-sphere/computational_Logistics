'use strict';

/**
 * @typedef {Object} AdapterSpec
 * @property {Object} routes          - Map of "METHOD /path" → { summary, tags, requiresAuth, parameters, responseSchema }
 * @property {Object} featureFlags    - Map of path prefix → { included, enabled, message }
 * @property {string} specUrl         - The URL the spec was fetched from
 * @property {string} framework       - The detected or configured framework name
 * @property {boolean} headless       - true when spec was not available
 */

/**
 * Every adapter must export an object implementing:
 *
 * fetchSpec(config, http) → Promise<AdapterSpec>
 *   config: validated config object
 *   http: pre-configured axios instance (baseURL set, HTTPS errors handled)
 *
 * isAuthRequired(path, spec) → boolean
 *   Returns true if the given path requires authentication per the spec.
 *
 * buildAuthRequest(config) → Object (axios request config)
 *   Returns the axios config needed to perform login.
 *
 * extractToken(loginResponse, config) → Object (headers)
 *   Takes the login response and returns the headers to add to probe requests.
 */

module.exports = {};
