'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { renderHtmlReport } = require('./html');

describe('html report formatter', () => {
  test('renders production report sections and escapes dynamic content', () => {
    const html = renderHtmlReport({
      meta: {
        generatedAt: '2026-05-05T10:00:00.000Z',
        baseUrl: 'http://localhost:8000/?x=<script>',
        headless: false,
      },
      overallScore: 82,
      routes: {
        '/alerts': { score: 80, status: 'healthy', rootCause: 'empty_db', apiCallCount: 3 },
      },
      rootCauseSummary: {
        empty_db: { count: 1, affectedRoutes: ['/alerts'] },
      },
      endpointDiagnostics: [
        {
          endpoint: 'GET /alerts/dedup',
          rootCause: 'empty_db',
          label: 'no_data',
          severity: 'low',
          affectedRoutes: ['/alerts'],
          affectedRouteCount: 1,
          status: 200,
          ms: 42,
          emptyReason: 'empty_array',
        },
      ],
      regression: { newFailures: [], newPasses: ['/vulnerabilities'] },
    });

    assert.match(html, /qa-probe QA Report/);
    assert.match(html, /Run Summary/);
    assert.match(html, /Priority Endpoint Diagnostics/);
    assert.match(html, /Route Health/);
    assert.match(html, /No Data Evidence/);
    assert.match(html, /Regression Signal/);
    assert.match(html, /GET \/alerts\/dedup/);
    assert.match(html, /http:\/\/localhost:8000\/\?x=&lt;script&gt;/);
    assert.doesNotMatch(html, /<script>/);
  });
});
