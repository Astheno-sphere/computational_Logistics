'use strict';

const axios = require('axios');

async function fetchTempoTrace(traceId, otel) {
  const baseUrl = String(otel.baseUrl || '').replace(/\/$/, '');
  const res = await axios.get(`${baseUrl}/api/traces/${traceId}`, {
    headers: otel.apiKey ? { Authorization: `Bearer ${otel.apiKey}` } : {},
    validateStatus: () => true,
  });
  if (res.status >= 400) throw new Error(`Tempo trace fetch failed: ${res.status}`);
  return res.data;
}

module.exports = { fetchTempoTrace };
