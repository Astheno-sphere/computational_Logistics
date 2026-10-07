'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { generateBody } = require('./body-generator');
const { anonymizeHarBody } = require('./har-anonymizer');
const { pathMatchesPattern } = require('./har-replay');

test('HAR body strategy returns anonymized captured POST body', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-har-'));
  const harFile = path.join(root, 'traffic.har');
  fs.writeFileSync(harFile, JSON.stringify({
    log: {
      entries: [{
        request: {
          method: 'POST',
          url: 'http://localhost/api/cases',
          postData: { mimeType: 'application/json', text: JSON.stringify({ email: 'real@example.com', age: 42 }) },
        },
      }],
    },
  }), 'utf8');

  const body = generateBody(
    { method: 'POST', path: '/api/cases', routeKey: 'POST /api/cases' },
    { type: 'object', required: ['email'], properties: { email: { type: 'string' } } },
    'har',
    { probe: { harReplay: { enabled: true, harFile, anonymize: true } } },
  );

  assert.deepEqual(body, { email: 'user@example.test', age: 42 });
});

test('HAR replay falls back to minimal when no match exists', () => {
  const body = generateBody(
    { method: 'POST', path: '/api/missing', routeKey: 'POST /api/missing' },
    { type: 'object', required: ['email'], properties: { email: { type: 'string' } } },
    'har',
    { probe: { harReplay: { enabled: true, harFile: 'missing.har', anonymize: true } } },
  );
  assert.deepEqual(body, { email: '' });
});

test('HAR anonymizer replaces PII deterministically', () => {
  const result = anonymizeHarBody({ ssn: '123-45-6789', phone: '212-555-1212' });
  assert.equal(result.ssn, '000-00-0000');
  assert.equal(result.phone, '555-010-0000');
});

test('HAR matcher handles OpenAPI path parameters', () => {
  assert.equal(pathMatchesPattern('/users/123', '/users/{id}'), true);
});
