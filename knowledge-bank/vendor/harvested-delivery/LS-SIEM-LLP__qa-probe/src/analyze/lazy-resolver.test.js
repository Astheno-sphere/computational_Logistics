'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { parseFrontendSrc } = require('./frontend-parser');
const { extractRoutes } = require('./route-extractor');
const { buildGraph } = require('./graph-builder');

test('React.lazy routes associate API calls inside lazy component files', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-lazy-'));
  const src = path.join(root, 'src');
  fs.mkdirSync(path.join(src, 'pages'), { recursive: true });
  fs.writeFileSync(path.join(src, 'App.tsx'), `
    import React, { lazy } from 'react';
    import { Route } from 'react-router-dom';
    const Dashboard = lazy(() => import('./pages/Dashboard'));
    export function App() {
      return <Route path="/dash" element={<Dashboard />} />;
    }
  `, 'utf8');
  fs.writeFileSync(path.join(src, 'pages', 'Dashboard.tsx'), `
    export default function Dashboard() {
      api.get('/api/dashboard');
      return <div />;
    }
  `, 'utf8');

  const frontendRoutes = extractRoutes(path.join(src, 'App.tsx'), src, { warnings: [] });
  const apiCalls = parseFrontendSrc(src, { warnings: [] });
  const graph = buildGraph({
    frontendRoutes,
    apiCalls,
    backendSpec: { routes: { 'GET /dashboard': { responseSchema: null } }, featureFlags: {}, headless: false },
    config: { frontendSrc: src, frontendApiPrefix: '/api', baseUrl: 'http://localhost' },
  });

  assert.ok(frontendRoutes.has('/dash'));
  assert.deepEqual(
    graph.frontendRoutes['/dash'].apiCalls.map(c => `${c.method} ${c.backendPath}`),
    ['GET /dashboard'],
  );
});

test('buildGraph preserves backend-only feature flags', () => {
  const graph = buildGraph({
    frontendRoutes: new Map(),
    apiCalls: { byFile: new Map(), allCalls: [] },
    backendSpec: {
      routes: { 'GET /scim/v2/Users': { responseSchema: null } },
      featureFlags: {
        '/scim/v2': {
          included: false,
          enabled: false,
          message: 'SCIM is disabled',
        },
      },
      headless: false,
    },
    config: { frontendSrc: '.', frontendApiPrefix: '/api', baseUrl: 'http://localhost' },
  });

  assert.deepEqual(graph.featureFlags['/scim/v2'], {
    included: false,
    enabled: false,
    message: 'SCIM is disabled',
  });
});
