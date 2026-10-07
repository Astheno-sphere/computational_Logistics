'use strict';

module.exports = {
  name: 'qa_probe_probe_endpoint',
  description: 'Live-probe a single endpoint right now and return its status. Ask: "Is GET /alerts returning data right now?"',
  inputSchema: {
    type: 'object',
    properties: {
      method: { type: 'string', description: 'HTTP method (GET, POST, etc.)' },
      path: { type: 'string', description: 'Backend path (e.g. /alerts)' },
    },
    required: ['path'],
  },
  async execute({ method = 'GET', path: endpointPath } = {}, { config, graph }) {
    if (!config) return { error: 'No config available.' };

    const { createHttpClient } = require('../../analyze/backend-fetcher');
    const { authenticate } = require('../../probe/authenticator');
    const { probeEndpoint } = require('../../probe/endpoint-runner');
    const { classifyEndpoint } = require('../../report/root-cause');

    const http = createHttpClient(config);
    const headers = await authenticate(config, http);

    const endpoint = { path: endpointPath, method: method.toUpperCase(), routeKey: `${method.toUpperCase()} ${endpointPath}`, type: 'http' };
    const result = await probeEndpoint(endpoint, headers, http, graph || {}, config);

    const cause = classifyEndpoint(`${method.toUpperCase()} ${endpointPath}`, result, graph || {}, config);

    return {
      endpoint: `${method.toUpperCase()} ${endpointPath}`,
      status: result.status,
      ms: result.ms,
      empty: result.empty,
      itemCount: result.itemCount,
      schemaErrors: result.schemaErrors,
      rootCause: cause.rootCause,
      fixHint: cause.fixHint,
    };
  },
};
