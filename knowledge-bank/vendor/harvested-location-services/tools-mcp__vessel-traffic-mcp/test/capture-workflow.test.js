import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, rmSync, readFileSync, statSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

import { createMockRecorderDriver } from '../dist/capture/recorder.js';
import {
  loadSiteProfile,
  validateSiteProfile,
  assertOriginAllowed,
  assertActionAllowed,
  detectSessionLoss,
  isOriginAllowed,
  findForbiddenAction,
  SiteProfileError,
  SITE_PROFILE_FORMAT_VERSION,
} from '../dist/capture/site-profile.js';
import {
  recordedExchangesToHar,
  writeHarBackup,
  assertHarOutputPath,
  HarPathError,
  defaultRawDir,
  HAR_VERSION,
} from '../dist/capture/har-writer.js';
import {
  runCaptureWorkflow,
  gateRunner,
  WorkflowAbortedError,
  WorkflowGateError,
} from '../dist/capture/workflow.js';
import { compareTrafficIR } from '../dist/capture/replay-validator.js';
import { buildTrafficIR } from '../dist/capture/traffic-ir.js';
import { runRunnerCli, parseScriptFile } from '../dist/capture/runner-cli.js';

const SECRET_BEARER =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmNWEtYWMyLWNyZWQtRG9Ob3RMZWFrIn0.SiGn4tUre-DoNotLeak-F5A-AC2';
const SECRET_API_KEY = 'F5A-AC2-API-KEY-DO-NOT-LEAK-87654321';
const SECRET_COOKIE_VAL = 'sid=F5A-AC2-COOKIE-DO-NOT-LEAK';
const SECRET_BODY_TOKEN = 'F5A-AC2-BODY-TOKEN-DO-NOT-LEAK';

const ALL_SECRETS = [SECRET_BEARER, SECRET_API_KEY, SECRET_COOKIE_VAL, SECRET_BODY_TOKEN];

function assertNoSecrets(payload, secrets = ALL_SECRETS, label = 'payload') {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  for (const secret of secrets) {
    assert.ok(!text.includes(secret), `${label} must not contain raw secret "${secret}"`);
  }
}

function buildAllowedProfile(overrides = {}) {
  return {
    version: SITE_PROFILE_FORMAT_VERSION,
    id: 'maritime-test.example',
    displayName: 'Maritime Test Site',
    termsReviewStatus: 'allowed',
    baseUrl: 'https://api.maritime.example.test/',
    allowedOrigins: ['https://api.maritime.example.test'],
    forbiddenActions: [
      { pattern: '/account/delete', description: 'destructive account delete endpoint' },
      { pattern: '/auth/logout', description: 'session logout endpoint' },
    ],
    sessionLossIndicators: [
      { kind: 'url-redirect', pattern: '/cm/lgn', description: 'forced login redirect' },
      { kind: 'status-code', pattern: '401', description: 'auth required' },
    ],
    pacing: { minStepIntervalMs: 250, maxStepsPerRun: 50, maxConcurrent: 1 },
    notes: ['safe synthetic profile for deterministic tests'],
    ...overrides,
  };
}

function buildScriptedExchanges() {
  return [
    {
      step: { kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels?api_key=keyplaceholder&mmsi=123456789' },
      exchanges: [
        {
          method: 'GET',
          url: `https://api.maritime.example.test/v1/vessels?api_key=${SECRET_API_KEY}&mmsi=123456789`,
          startedAt: '2026-05-15T11:00:00.000Z',
          request: {
            headers: [
              { name: 'Authorization', value: `Bearer ${SECRET_BEARER}` },
              { name: 'Cookie', value: SECRET_COOKIE_VAL },
              { name: 'X-Api-Key', value: SECRET_API_KEY },
              { name: 'Accept', value: 'application/json' },
            ],
            cookies: [{ name: 'session', value: SECRET_COOKIE_VAL }],
            mimeType: undefined,
            body: undefined,
          },
          response: {
            status: 200,
            statusText: 'OK',
            headers: [
              { name: 'Content-Type', value: 'application/json' },
              { name: 'Set-Cookie', value: `auth=${SECRET_COOKIE_VAL}; Path=/` },
            ],
            cookies: [{ name: 'auth', value: SECRET_COOKIE_VAL }],
            mimeType: 'application/json',
            body: JSON.stringify({
              ok: true,
              refresh_token: SECRET_BEARER,
              positions: [{ mmsi: '123456789', lat: 35.1, lon: 129.0 }],
            }),
          },
        },
      ],
    },
    {
      step: { kind: 'goto', url: 'https://api.maritime.example.test/v1/positions/123456789' },
      exchanges: [
        {
          method: 'POST',
          url: 'https://api.maritime.example.test/v1/positions/123456789',
          startedAt: '2026-05-15T11:00:01.000Z',
          request: {
            headers: [
              { name: 'Content-Type', value: 'application/json' },
              { name: 'X-Api-Key', value: SECRET_API_KEY },
            ],
            cookies: [],
            mimeType: 'application/json',
            body: JSON.stringify({ token: SECRET_BODY_TOKEN, mmsi: '123456789' }),
          },
          response: {
            status: 200,
            statusText: 'OK',
            headers: [{ name: 'Content-Type', value: 'application/json' }],
            cookies: [],
            mimeType: 'application/json',
            body: JSON.stringify({ ok: true, lat: 35.1, lon: 129.0 }),
          },
        },
      ],
    },
  ];
}

function makeTmpWorkspace() {
  const dir = mkdtempSync(join(tmpdir(), 'f5a-ac2-'));
  return dir;
}

const COUNTER = (() => {
  let n = 0;
  return () => `2026-05-15T12:00:0${n++}.000Z`;
})();

test('site-profile validates required fields', () => {
  const ok = buildAllowedProfile();
  assert.deepEqual(validateSiteProfile(ok), []);

  const bad = buildAllowedProfile({ allowedOrigins: [] });
  const errs = validateSiteProfile(bad);
  assert.ok(errs.find((e) => e.code === 'allowedOrigins'));

  assert.throws(
    () => loadSiteProfile(JSON.stringify({ ...ok, version: 99 })),
    SiteProfileError,
  );
});

test('site-profile assertOriginAllowed and assertActionAllowed enforce safe origins and forbidden actions', () => {
  const profile = buildAllowedProfile();
  assert.doesNotThrow(() => assertOriginAllowed(profile, 'https://api.maritime.example.test/v1/vessels'));
  assert.throws(
    () => assertOriginAllowed(profile, 'https://attacker.example/v1/vessels'),
    SiteProfileError,
  );
  assert.equal(isOriginAllowed(profile, 'https://api.maritime.example.test/x'), true);
  assert.equal(isOriginAllowed(profile, 'https://other.example/x'), false);

  assert.doesNotThrow(() => assertActionAllowed(profile, 'https://api.maritime.example.test/v1/vessels'));
  assert.throws(
    () => assertActionAllowed(profile, 'https://api.maritime.example.test/auth/logout'),
    SiteProfileError,
  );
  assert.ok(findForbiddenAction(profile, 'https://api.maritime.example.test/account/delete'));
});

test('site-profile detectSessionLoss flags redirect/status/header/body indicators', () => {
  const profile = buildAllowedProfile({
    sessionLossIndicators: [
      { kind: 'url-redirect', pattern: '/cm/lgn', description: 'login redirect' },
      { kind: 'status-code', pattern: '401', description: 'auth required' },
      { kind: 'response-header', pattern: 'WWW-Authenticate', description: 'auth challenge' },
      { kind: 'response-body', pattern: 'session_expired', description: 'session expired' },
    ],
  });
  assert.ok(
    detectSessionLoss(profile, {
      url: 'https://api.maritime.example.test/cm/lgn?return=/x',
      response: { status: 200, headers: [], body: '' },
    }),
  );
  assert.ok(
    detectSessionLoss(profile, {
      url: 'https://api.maritime.example.test/v1/vessels',
      response: { status: 401, headers: [], body: '' },
    }),
  );
  assert.ok(
    detectSessionLoss(profile, {
      url: 'https://api.maritime.example.test/v1/vessels',
      response: { status: 200, headers: [{ name: 'WWW-Authenticate', value: 'Bearer' }], body: '' },
    }),
  );
  assert.ok(
    detectSessionLoss(profile, {
      url: 'https://api.maritime.example.test/v1/vessels',
      response: { status: 200, headers: [], body: '{"error":"session_expired"}' },
    }),
  );
  assert.equal(
    detectSessionLoss(profile, {
      url: 'https://api.maritime.example.test/v1/vessels',
      response: { status: 200, headers: [], body: '{"ok":true}' },
    }),
    null,
  );
});

test('har-writer assertHarOutputPath enforces captures/raw boundary', () => {
  const tmp = makeTmpWorkspace();
  try {
    const safeRaw = resolve(tmp, 'captures', 'raw');
    const safeOut = resolve(safeRaw, 'demo.har');
    assert.doesNotThrow(() => assertHarOutputPath({ rawDirAbsolute: safeRaw, outFile: safeOut }));

    // Out file outside raw dir.
    const escapeOut = resolve(tmp, 'captures', 'demo.har');
    assert.throws(
      () => assertHarOutputPath({ rawDirAbsolute: safeRaw, outFile: escapeOut }),
      HarPathError,
    );

    // Raw dir not under captures/raw segment.
    const wrongRaw = resolve(tmp, 'captures', 'public');
    assert.throws(
      () => assertHarOutputPath({ rawDirAbsolute: wrongRaw, outFile: resolve(wrongRaw, 'demo.har') }),
      HarPathError,
    );

    // Relative paths refused.
    assert.throws(
      () => assertHarOutputPath({ rawDirAbsolute: 'captures/raw', outFile: 'captures/raw/x.har' }),
      HarPathError,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('har-writer recordedExchangesToHar produces valid HAR shape', () => {
  const exchanges = buildScriptedExchanges().flatMap((s) => s.exchanges);
  const har = recordedExchangesToHar(exchanges, { now: COUNTER });
  assert.equal(har.log.version, HAR_VERSION);
  assert.equal(har.log.entries.length, 2);
  for (const entry of har.log.entries) {
    assert.ok(typeof entry.startedDateTime === 'string');
    assert.ok(Array.isArray(entry.request.headers));
    assert.ok(Array.isArray(entry.response.headers));
  }
});

test('gateRunner blocks live driver without env+authorization', () => {
  // Mock driver always allowed when site is "allowed" or "needs-terms-review".
  assert.doesNotThrow(() =>
    gateRunner({
      driverName: 'mock',
      liveEnvEnabled: false,
      authorized: false,
      termsReviewStatus: 'allowed',
    }),
  );
  // Mock driver still blocked when site is "blocked".
  assert.throws(
    () =>
      gateRunner({
        driverName: 'mock',
        liveEnvEnabled: true,
        authorized: true,
        termsReviewStatus: 'blocked',
      }),
    WorkflowGateError,
  );
  // Live driver requires VESSEL_CAPTURE_LIVE=1.
  assert.throws(
    () =>
      gateRunner({
        driverName: 'playwright',
        liveEnvEnabled: false,
        authorized: true,
        termsReviewStatus: 'allowed',
      }),
    WorkflowGateError,
  );
  // Live driver requires --i-am-authorized.
  assert.throws(
    () =>
      gateRunner({
        driverName: 'playwright',
        liveEnvEnabled: true,
        authorized: false,
        termsReviewStatus: 'allowed',
      }),
    WorkflowGateError,
  );
  // Live driver requires termsReviewStatus=allowed.
  assert.throws(
    () =>
      gateRunner({
        driverName: 'playwright',
        liveEnvEnabled: true,
        authorized: true,
        termsReviewStatus: 'needs-terms-review',
      }),
    WorkflowGateError,
  );
  // Fully authorized live path passes.
  assert.doesNotThrow(() =>
    gateRunner({
      driverName: 'playwright',
      liveEnvEnabled: true,
      authorized: true,
      termsReviewStatus: 'allowed',
    }),
  );
});

test('runCaptureWorkflow happy path: HAR backup, sanitized fixture, IR, replay validation', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const script = buildScriptedExchanges();
    const driver = createMockRecorderDriver({ steps: script });
    const stamp = '2026-05-15T13:00:00.000Z';
    const result = await runCaptureWorkflow({
      profile,
      driver,
      steps: script.map((s) => s.step),
      cwd: tmp,
      label: 'Marine Sample Run!',
      authorized: false,
      liveEnvEnabled: false,
      validateReplay: true,
      now: () => stamp,
    });

    // Sanitized fixture defaults to *.private.json (gitignored).
    assert.match(result.fixturePath, /captures\/marine-sample-run\.private\.json$/);
    assert.match(result.irPath, /captures\/marine-sample-run\.ir\.private\.json$/);
    assert.match(result.harPath, /captures\/raw\/marine-sample-run\.har$/);

    // HAR backup file exists (the operator may need it for debugging) but
    // lives under captures/raw/ which is gitignored.
    const harStat = statSync(result.harPath);
    assert.ok(harStat.size > 0);
    const harContents = readFileSync(result.harPath, 'utf8');
    // The HAR backup is the *raw* dump and intentionally still contains the
    // original session secrets — that is why captures/raw is gitignored.
    assert.ok(harContents.includes(SECRET_BEARER), 'HAR backup must preserve raw exchange so operator can re-replay');

    // Sanitized fixture must NOT contain raw secrets.
    const fixtureContents = readFileSync(result.fixturePath, 'utf8');
    assertNoSecrets(fixtureContents, ALL_SECRETS, 'sanitized fixture');
    assert.ok(fixtureContents.includes('[REDACTED]'));

    // Sanitized fixture provenance is stamped with liveReplayDisabled=true.
    const fixture = JSON.parse(fixtureContents);
    assert.equal(fixture.provenance.liveReplayDisabled, true);
    assert.equal(fixture.provenance.recorderDriver, 'mock');
    assert.equal(fixture.provenance.siteProfileId, profile.id);
    assert.equal(fixture.provenance.capturedAt, stamp);

    // IR must not contain raw secrets either.
    const irContents = readFileSync(result.irPath, 'utf8');
    assertNoSecrets(irContents, ALL_SECRETS, 'IR file');

    // Replay validation: re-running the IR build against the same fixture is
    // identical (deterministic).
    assert.ok(result.validation);
    assert.equal(result.validation.identical, true);
    assert.deepEqual(result.validation.addedEndpointIds, []);
    assert.deepEqual(result.validation.removedEndpointIds, []);
    assert.deepEqual(result.validation.changedEndpoints, []);
    assert.equal(result.validation.baselineEndpoints, result.ir.endpoints.length);

    // IR endpoint shape has known status codes & MIME types and flagged credential headers.
    const ids = result.ir.endpoints.map((e) => e.id).sort();
    assert.deepEqual(ids, [
      'GET https://api.maritime.example.test/v1/vessels',
      'POST https://api.maritime.example.test/v1/positions/:mmsi',
    ]);
    for (const endpoint of result.ir.endpoints) {
      // Cookie + Authorization + X-Api-Key should be flagged so they cannot
      // be silently re-replayed.
      const flagged = endpoint.redactedHeaderNames.map((n) => n.toLowerCase());
      if (endpoint.id.startsWith('GET')) {
        assert.ok(flagged.includes('authorization'));
        assert.ok(flagged.includes('cookie'));
        assert.ok(flagged.includes('x-api-key'));
      }
    }
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow refuses steps that target disallowed origins', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const driver = createMockRecorderDriver({ steps: [] });
    await assert.rejects(
      runCaptureWorkflow({
        profile,
        driver,
        steps: [{ kind: 'goto', url: 'https://attacker.example/v1/x' }],
        cwd: tmp,
        label: 'bad-origin',
        authorized: false,
        liveEnvEnabled: false,
      }),
      SiteProfileError,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow refuses forbidden destructive actions', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const driver = createMockRecorderDriver({ steps: [] });
    await assert.rejects(
      runCaptureWorkflow({
        profile,
        driver,
        steps: [{ kind: 'goto', url: 'https://api.maritime.example.test/auth/logout' }],
        cwd: tmp,
        label: 'forbidden-step',
        authorized: false,
        liveEnvEnabled: false,
      }),
      SiteProfileError,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow aborts when a session-loss indicator triggers', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const sessionLossExchange = {
      method: 'GET',
      url: 'https://api.maritime.example.test/cm/lgn?return=/x',
      startedAt: '2026-05-15T11:01:00.000Z',
      request: { headers: [], cookies: [], body: undefined, mimeType: undefined },
      response: {
        status: 302,
        statusText: 'Found',
        headers: [{ name: 'Content-Type', value: 'text/html' }],
        cookies: [],
        mimeType: 'text/html',
        body: '<html>login</html>',
      },
    };
    const driver = createMockRecorderDriver({
      steps: [
        {
          step: { kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels' },
          exchanges: [sessionLossExchange],
        },
      ],
    });
    await assert.rejects(
      runCaptureWorkflow({
        profile,
        driver,
        steps: [{ kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels' }],
        cwd: tmp,
        label: 'session-loss',
        authorized: false,
        liveEnvEnabled: false,
      }),
      WorkflowAbortedError,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow refuses sites with termsReviewStatus="blocked"', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile({ termsReviewStatus: 'blocked' });
    const driver = createMockRecorderDriver({ steps: [] });
    await assert.rejects(
      runCaptureWorkflow({
        profile,
        driver,
        steps: [{ kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels' }],
        cwd: tmp,
        label: 'blocked',
        authorized: false,
        liveEnvEnabled: false,
      }),
      WorkflowGateError,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow drops exchanges with origins outside the profile', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const offProfile = {
      method: 'GET',
      url: 'https://cdn.attacker.example/track.gif',
      startedAt: '2026-05-15T11:02:00.000Z',
      request: { headers: [], cookies: [], body: undefined, mimeType: undefined },
      response: {
        status: 200,
        statusText: 'OK',
        headers: [{ name: 'Content-Type', value: 'image/gif' }],
        cookies: [],
        mimeType: 'image/gif',
        body: undefined,
      },
    };
    const onProfile = {
      method: 'GET',
      url: 'https://api.maritime.example.test/v1/vessels?mmsi=123456789',
      startedAt: '2026-05-15T11:02:01.000Z',
      request: { headers: [], cookies: [], body: undefined, mimeType: undefined },
      response: {
        status: 200,
        statusText: 'OK',
        headers: [{ name: 'Content-Type', value: 'application/json' }],
        cookies: [],
        mimeType: 'application/json',
        body: JSON.stringify({ ok: true }),
      },
    };
    const driver = createMockRecorderDriver({
      steps: [
        {
          step: { kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels' },
          exchanges: [offProfile, onProfile],
        },
      ],
    });
    const result = await runCaptureWorkflow({
      profile,
      driver,
      steps: [{ kind: 'goto', url: 'https://api.maritime.example.test/v1/vessels' }],
      cwd: tmp,
      label: 'origin-filter',
      authorized: false,
      liveEnvEnabled: false,
      now: () => '2026-05-15T13:01:00.000Z',
    });
    assert.equal(result.recordedExchangeCount, 1);
    assert.ok(result.warnings.some((w) => w.includes('origin not allowed')));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCaptureWorkflow promote=true drops .private suffix', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const script = buildScriptedExchanges();
    const driver = createMockRecorderDriver({ steps: script });
    const result = await runCaptureWorkflow({
      profile,
      driver,
      steps: script.map((s) => s.step),
      cwd: tmp,
      label: 'promote-run',
      authorized: false,
      liveEnvEnabled: false,
      promote: true,
      now: () => '2026-05-15T13:02:00.000Z',
    });
    assert.match(result.fixturePath, /captures\/promote-run\.fixture\.json$/);
    assert.match(result.irPath, /captures\/promote-run\.ir\.json$/);
    // Sanitized still — provenance.liveReplayDisabled remains true even when promoted.
    const fixture = JSON.parse(readFileSync(result.fixturePath, 'utf8'));
    assert.equal(fixture.provenance.liveReplayDisabled, true);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('compareTrafficIR detects added/removed/changed endpoints', () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const script = buildScriptedExchanges();
    const driver = createMockRecorderDriver({ steps: script });
    return runCaptureWorkflow({
      profile,
      driver,
      steps: script.map((s) => s.step),
      cwd: tmp,
      label: 'baseline',
      authorized: false,
      liveEnvEnabled: false,
      now: () => '2026-05-15T13:03:00.000Z',
    }).then((baseline) => {
      // Build a candidate IR by removing one endpoint to simulate API drift.
      const candidate = {
        ...baseline.ir,
        endpoints: baseline.ir.endpoints.filter((e) => e.method !== 'POST'),
      };
      const report = compareTrafficIR(baseline.ir, candidate);
      assert.equal(report.identical, false);
      assert.ok(report.removedEndpointIds.includes('POST https://api.maritime.example.test/v1/positions/:mmsi'));
      assert.equal(report.addedEndpointIds.length, 0);

      // And vice-versa.
      const reverse = compareTrafficIR(candidate, baseline.ir);
      assert.equal(reverse.identical, false);
      assert.ok(reverse.addedEndpointIds.includes('POST https://api.maritime.example.test/v1/positions/:mmsi'));
    });
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('compareTrafficIR catches schema/status drift', () => {
  // Build two minimal fixtures that share the same endpoint id but differ in
  // status codes; ensure compareTrafficIR flags the change.
  const baseEndpoint = {
    id: 'GET https://api.example.test/v1/x',
    method: 'GET',
    origin: 'https://api.example.test',
    pathTemplate: '/v1/x',
    sampleCount: 1,
    samplePaths: ['/v1/x'],
    queryKeys: [],
    requestHeaderNames: [],
    redactedHeaderNames: [],
    requestCookieCount: 0,
    requestBodyMimeTypes: [],
    requestBodySchema: null,
    statuses: [
      { status: 200, count: 1, mimeTypes: ['application/json'], schema: { kind: 'object', properties: {} } },
    ],
  };
  const candEndpoint = {
    ...baseEndpoint,
    statuses: [
      { status: 500, count: 1, mimeTypes: ['application/json'], schema: { kind: 'object', properties: {} } },
    ],
  };
  const baseline = {
    version: 1,
    generatedAt: '2026-05-15T13:04:00.000Z',
    source: { fixtureVersion: 1, fixtureLabel: 'a', fixtureCreatedAt: 'x', entryCount: 1 },
    endpoints: [baseEndpoint],
    warnings: [],
    notes: [],
  };
  const candidate = { ...baseline, endpoints: [candEndpoint] };
  const report = compareTrafficIR(baseline, candidate);
  assert.equal(report.identical, false);
  assert.equal(report.changedEndpoints.length, 1);
  assert.ok(report.changedEndpoints[0].changes.some((c) => c.includes('status/schema')));
});

test('runner-cli mock driver runs end-to-end against site profile and script files', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const script = { steps: buildScriptedExchanges() };
    const profilePath = join(tmp, 'site-profile.json');
    const scriptPath = join(tmp, 'script.json');
    writeFileSync(profilePath, JSON.stringify(profile));
    writeFileSync(scriptPath, JSON.stringify(script));

    const stdout = [];
    const stderr = [];
    const exitCode = await runRunnerCli({
      argv: [
        '--site-profile',
        profilePath,
        '--script',
        scriptPath,
        '--driver',
        'mock',
        '--label',
        'cli-mock-run',
        '--out-dir',
        tmp,
        '--validate-replay',
      ],
      cwd: tmp,
      env: {},
      stdout: (t) => stdout.push(t),
      stderr: (t) => stderr.push(t),
      readFile: (p) => readFileSync(p, 'utf8'),
      writeFile: (p, c) => writeFileSync(p, c),
      ensureDir: (p) => mkdirSync(p, { recursive: true }),
      exists: (p) => {
        try {
          statSync(p);
          return true;
        } catch {
          return false;
        }
      },
      now: () => '2026-05-15T13:05:00.000Z',
    });
    assert.equal(exitCode, 0, `expected exit 0, got ${exitCode}; stderr=${stderr.join('')}`);
    assert.ok(stdout.join('').includes('replay-identical=true'));
    assert.ok(stdout.join('').includes('cli-mock-run.private.json'));

    // Verify the sanitized fixture was actually written and is sanitized.
    const fixture = JSON.parse(
      readFileSync(join(tmp, 'fixtures', 'captures', 'cli-mock-run.private.json'), 'utf8'),
    );
    assert.equal(fixture.provenance.liveReplayDisabled, true);
    assertNoSecrets(JSON.stringify(fixture), ALL_SECRETS, 'cli-emitted fixture');
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runner-cli refuses --driver playwright without env+authorization gates', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const profilePath = join(tmp, 'site-profile.json');
    writeFileSync(profilePath, JSON.stringify(profile));

    const stderr = [];
    const exitCode = await runRunnerCli({
      argv: [
        '--site-profile',
        profilePath,
        '--driver',
        'playwright',
        '--label',
        'live-attempt',
        '--out-dir',
        tmp,
      ],
      cwd: tmp,
      env: {}, // VESSEL_CAPTURE_LIVE not set
      stdout: () => {},
      stderr: (t) => stderr.push(t),
      readFile: (p) => readFileSync(p, 'utf8'),
      writeFile: (p, c) => writeFileSync(p, c),
      ensureDir: (p) => mkdirSync(p, { recursive: true }),
      exists: (p) => {
        try {
          statSync(p);
          return true;
        } catch {
          return false;
        }
      },
      now: () => '2026-05-15T13:06:00.000Z',
    });
    assert.notEqual(exitCode, 0);
    const text = stderr.join('');
    // Either: playwright module is missing (loader stub), or gates rejected the
    // call. Both are acceptable — the important thing is autodev/CI cannot
    // accidentally make a live capture.
    assert.ok(
      text.includes('playwright is not installed') ||
        text.includes('VESSEL_CAPTURE_LIVE') ||
        text.includes('--i-am-authorized') ||
        text.includes('live playwright driver'),
      `expected gate error, got: ${text}`,
    );
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('runner-cli refuses unknown arguments and missing --label', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const profilePath = join(tmp, 'site-profile.json');
    writeFileSync(profilePath, JSON.stringify(profile));
    const stderr = [];
    const exit1 = await runRunnerCli({
      argv: ['--site-profile', profilePath, '--driver', 'mock', '--script', 'noscript', '--bogus'],
      cwd: tmp,
      env: {},
      stdout: () => {},
      stderr: (t) => stderr.push(t),
      readFile: (p) => readFileSync(p, 'utf8'),
      writeFile: () => {},
      ensureDir: () => {},
      exists: () => false,
      now: () => '2026-05-15T13:07:00.000Z',
    });
    assert.equal(exit1, 2);
    assert.ok(stderr.join('').includes('unknown argument'));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('parseScriptFile rejects malformed scripts', () => {
  assert.throws(() => parseScriptFile('{ broken'), /script JSON is invalid/);
  assert.throws(() => parseScriptFile('[]'), /must be a JSON object/);
  assert.throws(() => parseScriptFile(JSON.stringify({ steps: [{ exchanges: [] }] })), /requires \{ step, exchanges/);
});

test('defaultRawDir always lives under captures/raw segment', () => {
  const tmp = makeTmpWorkspace();
  try {
    const dir = defaultRawDir(tmp);
    assert.ok(dir.includes('captures/raw') || dir.includes('captures\\raw'));
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});

test('buildTrafficIR built from workflow output round-trips identically', async () => {
  const tmp = makeTmpWorkspace();
  try {
    const profile = buildAllowedProfile();
    const script = buildScriptedExchanges();
    const driver = createMockRecorderDriver({ steps: script });
    const result = await runCaptureWorkflow({
      profile,
      driver,
      steps: script.map((s) => s.step),
      cwd: tmp,
      label: 'roundtrip',
      authorized: false,
      liveEnvEnabled: false,
      now: () => '2026-05-15T13:08:00.000Z',
    });
    // Reload sanitized fixture from disk and rebuild IR.
    const fixture = JSON.parse(readFileSync(result.fixturePath, 'utf8'));
    const reloadedIr = buildTrafficIR(fixture, { now: () => '2026-05-15T13:08:00.000Z' });
    const diff = compareTrafficIR(result.ir, reloadedIr);
    assert.equal(diff.identical, true, `diff was: ${JSON.stringify(diff)}`);
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
});
