'use strict';

const fs = require('fs');
const { anonymizeHarBody } = require('./har-anonymizer');

function loadHarEntries(harFile) {
  if (!harFile || !fs.existsSync(harFile)) return [];
  const har = JSON.parse(fs.readFileSync(harFile, 'utf8'));
  return (har.log && har.log.entries) || [];
}

function findHarBody(endpoint, routeKey, config = {}) {
  const replay = ((config || {}).probe || {}).harReplay || {};
  if (!replay.enabled) return null;
  const entries = loadHarEntries(replay.harFile);
  const match = entries.find(entry => matchesEndpoint(entry, endpoint, routeKey));
  if (!match || !match.request || !match.request.postData) return null;
  const raw = match.request.postData.text || '';
  const parsed = parseBody(raw);
  return replay.anonymize === false ? parsed : anonymizeHarBody(parsed);
}

function matchesEndpoint(entry, endpoint, routeKey) {
  const req = entry.request || {};
  const method = String(req.method || '').toUpperCase();
  if (method !== String(endpoint.method || '').toUpperCase()) return false;
  const path = pathFromUrl(req.url);
  const endpointPath = endpoint.path || '';
  const routePath = routeKey ? routeKey.split(' ').slice(1).join(' ') : endpointPath;
  return path === endpointPath || pathMatchesPattern(path, routePath);
}

function pathFromUrl(url) {
  try { return new URL(url).pathname; } catch { return String(url || '').split('?')[0]; }
}

function pathMatchesPattern(actual, pattern) {
  const regex = new RegExp('^' + String(pattern).replace(/\{[^}]+\}/g, '[^/]+').replace(/\//g, '\\/') + '$');
  return regex.test(actual);
}

function parseBody(text) {
  try { return JSON.parse(text); } catch { return text; }
}

module.exports = { loadHarEntries, findHarBody, matchesEndpoint, pathMatchesPattern };
