'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const {
  normalizePath,
  parseFile,
  parseFrontendSrc,
} = require('./frontend-parser.js');

function tempProject(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-parser-'));
  for (const [name, content] of Object.entries(files)) {
    const filePath = path.join(root, name);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return root;
}

describe('normalizePath', () => {
  test('strips frontend /api prefix and trailing slashes', () => {
    assert.equal(normalizePath('/api/alerts/'), '/alerts');
  });

  test('normalizes template interpolations to params', () => {
    assert.equal(normalizePath('/api/users/${user.id}/alerts'), '/users/{param}/alerts');
  });
});

describe('parseFile', () => {
  test('detects axios-style client method calls', () => {
    const root = tempProject({
      'src/Alerts.jsx': "import api from './api';\napi.get('/api/alerts');\napi.post('/api/logs/search');\n",
    });

    const calls = parseFile(path.join(root, 'src', 'Alerts.jsx'), {
      relBase: root,
    });

    assert.deepEqual(
      calls.map(call => `${call.method} ${call.path}`),
      ['GET /alerts', 'POST /logs/search'],
    );
  });

  test('detects configured hook path arguments', () => {
    const root = tempProject({
      'src/Rules.tsx': "useApiData('/api/rules');\nuseApiQuery(['alerts'], '/api/alerts');\n",
    });

    const calls = parseFile(path.join(root, 'src', 'Rules.tsx'), {
      relBase: root,
    });

    assert.deepEqual(
      calls.map(call => `${call.method} ${call.path}`),
      ['GET /rules', 'GET /alerts'],
    );
  });

  test('detects visible client calls nested inside React Query callbacks', () => {
    const root = tempProject({
      'src/Dynamic.tsx': "useQuery(['alerts'], () => api.get(`/api/alerts/${tenantId}`));\n",
    });

    const calls = parseFile(path.join(root, 'src', 'Dynamic.tsx'), {
      relBase: root,
    });

    assert.deepEqual(calls.map(call => `${call.method} ${call.path}`), ['GET /alerts/{param}']);
  });
});

describe('parseFrontendSrc', () => {
  test('auto-discovers project-specific axios client names', () => {
    const root = tempProject({
      'src/api.ts': "import axios from 'axios';\nexport const siemApi = axios.create({ baseURL: '/api' });\n",
      'src/Dashboard.tsx': "import { siemApi } from './api';\nsiemApi.get('/api/dashboard');\n",
    });

    const result = parseFrontendSrc(path.join(root, 'src'));

    assert.ok(result.clientNames.includes('siemApi'));
    assert.deepEqual(
      result.allCalls.map(call => `${call.method} ${call.path}`),
      ['GET /dashboard'],
    );
  });
});
