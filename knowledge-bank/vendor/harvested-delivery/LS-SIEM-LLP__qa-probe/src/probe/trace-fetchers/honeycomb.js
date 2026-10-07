'use strict';

const axios = require('axios');

async function fetchHoneycombTrace(traceId, otel) {
  const baseUrl = String(otel.baseUrl || '').replace(/\/$/, '');
  const res = await axios.get(`${baseUrl}/1/traces/${traceId}`, {
    headers: otel.apiKey ? { 'X-Honeycomb-Team': otel.apiKey } : {},
    validateStatus: () => true,
  });
  if (res.status >= 400) throw new Error(`Honeycomb trace fetch failed: ${res.status}`);
  return res.data;
}

module.exports = { fetchHoneycombTrace };
