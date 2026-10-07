import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import {
  CAPTURE_QUEUE_FORMAT_VERSION,
  CAPTURE_SITES_FORMAT_VERSION,
  CaptureQueueError,
  captureQueueStatusValues,
  crossReferenceCaptureQueue,
  loadCaptureQueueFromDisk,
  loadCaptureSitesFromDisk,
  parseCaptureQueue,
  parseCaptureSites,
} from '../dist/capture/capture-queue.js';
import { gateRunner, WorkflowGateError } from '../dist/capture/workflow.js';
import { parseProviderCatalog } from '../dist/providers/catalog.js';

const SITES_PATH = new URL('../config/capture-sites.example.json', import.meta.url).pathname;
const QUEUE_PATH = new URL('../config/capture-queue.example.json', import.meta.url).pathname;
const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url).pathname;

const SITES_TEXT = readFileSync(SITES_PATH, 'utf8');
const QUEUE_TEXT = readFileSync(QUEUE_PATH, 'utf8');
const CATALOG_TEXT = readFileSync(CATALOG_PATH, 'utf8');

const REQUIRED_PROVIDER_IDS = [
  'marinetraffic',
  'vesselfinder',
  'myshiptracking',
  'fleetmon',
];

const CONTROLLED_ACTION_PATTERNS = ['/login', '/logout', '/account', '/billing'];

const SUSPICIOUS_SECRET_RE =
  /"((?:[A-Za-z0-9+/]{40,}={0,2}|[A-Fa-f0-9]{32,}|sk-[A-Za-z0-9]{16,}|Bearer\s+[A-Za-z0-9._-]{20,})|gho_[A-Za-z0-9]+)"/;

test('capture-sites.example.json parses and declares format version 1', () => {
  const sites = parseCaptureSites(SITES_TEXT, 'config/capture-sites.example.json');
  assert.equal(sites.version, CAPTURE_SITES_FORMAT_VERSION);
  assert.equal(sites.sourceDoc, 'docs/provider-catalog.md');
  assert.ok(sites.profiles.length >= 8, `expected >=8 profiles, got ${sites.profiles.length}`);
});

test('loadCaptureSitesFromDisk reads the committed example', () => {
  const sites = loadCaptureSitesFromDisk(SITES_PATH);
  assert.equal(sites.profiles.length, parseCaptureSites(SITES_TEXT).profiles.length);
});

test('every required maritime provider has a site profile entry', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  const providerIds = new Set(sites.profiles.map((p) => p.providerId));
  for (const required of REQUIRED_PROVIDER_IDS) {
    assert.ok(
      providerIds.has(required),
      `capture-sites must include a profile for catalog providerId "${required}"`,
    );
  }
});

test('every site profile defaults to needs-terms-review and conservative pacing', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  for (const profile of sites.profiles) {
    assert.equal(
      profile.termsReviewStatus,
      'needs-terms-review',
      `${profile.id} committed example must default to needs-terms-review`,
    );
    assert.ok(
      profile.pacing.minStepIntervalMs >= 4000,
      `${profile.id} must throttle to >=4000ms between steps (got ${profile.pacing.minStepIntervalMs})`,
    );
    assert.equal(profile.pacing.maxConcurrent, 1, `${profile.id} must use maxConcurrent=1`);
    assert.ok(
      profile.pacing.maxStepsPerRun > 0 && profile.pacing.maxStepsPerRun <= 25,
      `${profile.id} maxStepsPerRun out of safe range (got ${profile.pacing.maxStepsPerRun})`,
    );
  }
});

test('every site profile declares forbidden destructive/auth actions and session-loss indicators', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  for (const profile of sites.profiles) {
    assert.ok(profile.forbiddenActions.length > 0, `${profile.id} must declare forbiddenActions`);
    assert.ok(
      profile.sessionLossIndicators.length > 0,
      `${profile.id} must declare sessionLossIndicators`,
    );

    const patterns = profile.forbiddenActions.map((a) => a.pattern.toLowerCase());
    const haveAuthGuard = patterns.some(
      (p) =>
        p.includes('login') ||
        p.includes('logout') ||
        p.includes('register') ||
        p.includes('signup'),
    );
    const haveAccountGuard = patterns.some((p) => p.includes('account') || p.includes('billing'));
    assert.ok(
      haveAuthGuard,
      `${profile.id} must block at least one auth-related URL fragment, got ${JSON.stringify(patterns)}`,
    );
    assert.ok(
      haveAccountGuard,
      `${profile.id} must block at least one account/billing fragment, got ${JSON.stringify(patterns)}`,
    );

    const indicatorKinds = new Set(profile.sessionLossIndicators.map((i) => i.kind));
    // Conservative: at least one redirect-type and one status-code-type indicator.
    assert.ok(
      indicatorKinds.has('url-redirect') || indicatorKinds.has('response-body'),
      `${profile.id} must declare a redirect/body session-loss indicator`,
    );
    assert.ok(
      indicatorKinds.has('status-code'),
      `${profile.id} must declare a status-code session-loss indicator`,
    );
  }
});

test('every allowed origin is canonical and uses https', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  for (const profile of sites.profiles) {
    assert.ok(profile.allowedOrigins.length > 0, `${profile.id} has no allowedOrigins`);
    for (const origin of profile.allowedOrigins) {
      const u = new URL(origin);
      assert.equal(u.protocol, 'https:', `${profile.id} origin ${origin} must use https`);
      assert.equal(
        `${u.protocol}//${u.host}`,
        origin,
        `${profile.id} origin ${origin} must be canonical (scheme://host[:port])`,
      );
      // Confidence-check: hostname must look like a real DNS label, not a placeholder.
      assert.ok(/^[a-z0-9.-]+$/i.test(u.hostname), `${profile.id} origin hostname looks unsafe: ${origin}`);
    }
  }
});

test('capture-queue.example.json parses and declares format version 1', () => {
  const queue = parseCaptureQueue(QUEUE_TEXT, 'config/capture-queue.example.json');
  assert.equal(queue.version, CAPTURE_QUEUE_FORMAT_VERSION);
  assert.equal(queue.sourceDoc, 'docs/provider-catalog.md');
  assert.ok(queue.entries.length >= 4, `expected >=4 queue entries, got ${queue.entries.length}`);
});

test('loadCaptureQueueFromDisk reads the committed example', () => {
  const queue = loadCaptureQueueFromDisk(QUEUE_PATH);
  assert.equal(queue.entries.length, parseCaptureQueue(QUEUE_TEXT).entries.length);
});

test('every queue entry uses a known status and defaults to pending-terms-review', () => {
  const queue = parseCaptureQueue(QUEUE_TEXT);
  for (const entry of queue.entries) {
    assert.ok(
      captureQueueStatusValues.includes(entry.status),
      `unknown queue status ${entry.status} for provider ${entry.providerId}`,
    );
    assert.equal(
      entry.status,
      'pending-terms-review',
      `committed example queue must keep ${entry.providerId} pending-terms-review`,
    );
    assert.equal(entry.captureAuthorizedAt, null);
    assert.equal(entry.authorizedBy, null);
  }
});

test('queue entries cross-reference the provider catalog and site profiles', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  const queue = parseCaptureQueue(QUEUE_TEXT);
  const catalog = parseProviderCatalog(CATALOG_TEXT);
  const issues = crossReferenceCaptureQueue(sites, queue, { catalog });
  assert.deepEqual(issues, [], `cross-reference issues: ${JSON.stringify(issues, null, 2)}`);
});

test('every required maritime provider is queued', () => {
  const queue = parseCaptureQueue(QUEUE_TEXT);
  const providerIds = new Set(queue.entries.map((e) => e.providerId));
  for (const required of REQUIRED_PROVIDER_IDS) {
    assert.ok(
      providerIds.has(required),
      `capture-queue must include a queue entry for provider "${required}"`,
    );
  }
});

test('capture-sites file rejects unsupported versions', () => {
  const bumped = JSON.stringify({
    ...JSON.parse(SITES_TEXT),
    version: 99,
  });
  assert.throws(() => parseCaptureSites(bumped), CaptureQueueError);
});

test('capture-sites file rejects profiles defaulting to "allowed"', () => {
  const broken = JSON.parse(SITES_TEXT);
  broken.profiles[0].termsReviewStatus = 'allowed';
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken)),
    /committed example profiles must NOT default to "allowed"/,
  );
});

test('capture-sites file rejects pacing under 1000ms or maxConcurrent>1', () => {
  const broken = JSON.parse(SITES_TEXT);
  broken.profiles[0].pacing.minStepIntervalMs = 100;
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken)),
    /must throttle to >=1000ms/,
  );

  const broken2 = JSON.parse(SITES_TEXT);
  broken2.profiles[0].pacing.maxConcurrent = 4;
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken2)),
    /maxConcurrent=1/,
  );
});

test('capture-sites file rejects profiles missing forbiddenActions or sessionLossIndicators', () => {
  const broken = JSON.parse(SITES_TEXT);
  broken.profiles[0].forbiddenActions = [];
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken)),
    /forbidden destructive/,
  );

  const broken2 = JSON.parse(SITES_TEXT);
  broken2.profiles[0].sessionLossIndicators = [];
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken2)),
    /session-loss indicator/,
  );
});

test('capture-sites file rejects duplicate profile ids', () => {
  const broken = JSON.parse(SITES_TEXT);
  broken.profiles.push(JSON.parse(JSON.stringify(broken.profiles[0])));
  assert.throws(
    () => parseCaptureSites(JSON.stringify(broken)),
    /duplicate site profile id/,
  );
});

test('capture-queue rejects status="authorized" without captureAuthorizedAt + authorizedBy', () => {
  const broken = JSON.parse(QUEUE_TEXT);
  broken.entries[0].status = 'authorized';
  assert.throws(
    () => parseCaptureQueue(JSON.stringify(broken)),
    /authorizedBy to be populated/,
  );
});

test('capture-queue rejects non-blocked status carrying authorization metadata', () => {
  const broken = JSON.parse(QUEUE_TEXT);
  broken.entries[0].captureAuthorizedAt = '2026-05-15T00:00:00.000Z';
  broken.entries[0].authorizedBy = 'operator@example.test';
  assert.throws(
    () => parseCaptureQueue(JSON.stringify(broken)),
    /status="pending-terms-review" must have captureAuthorizedAt/,
  );
});

test('capture-queue rejects unknown status values', () => {
  const broken = JSON.parse(QUEUE_TEXT);
  broken.entries[0].status = 'mystery-status';
  assert.throws(
    () => parseCaptureQueue(JSON.stringify(broken)),
    /unknown queue status/,
  );
});

test('capture-queue rejects duplicate provider/site pairings', () => {
  const broken = JSON.parse(QUEUE_TEXT);
  broken.entries.push(JSON.parse(JSON.stringify(broken.entries[0])));
  assert.throws(
    () => parseCaptureQueue(JSON.stringify(broken)),
    /duplicate provider\/site pairing/,
  );
});

test('crossReferenceCaptureQueue reports unknown sites and mismatched providers', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  const broken = JSON.parse(QUEUE_TEXT);
  broken.entries[0].siteProfileId = 'does-not-exist.web';
  const issues = crossReferenceCaptureQueue(sites, parseCaptureQueue(JSON.stringify(broken)));
  assert.ok(issues.some((i) => i.code === 'unknown-site'));

  const broken2 = JSON.parse(QUEUE_TEXT);
  broken2.entries[0].providerId = 'definitely-not-a-real-provider';
  const issues2 = crossReferenceCaptureQueue(sites, parseCaptureQueue(JSON.stringify(broken2)));
  assert.ok(issues2.some((i) => i.code === 'site-provider-mismatch'));
});

test('crossReferenceCaptureQueue flags providers blocked by the catalog', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  const catalog = parseProviderCatalog(CATALOG_TEXT);
  // Spire is captureEligibility=blocked in the catalog. Forge a queue entry that
  // tries to queue spire-maritime against a real site profile id.
  const targetSiteId = sites.profiles[0].id;
  const queue = parseCaptureQueue(
    JSON.stringify({
      ...JSON.parse(QUEUE_TEXT),
      entries: [
        {
          providerId: 'spire-maritime',
          siteProfileId: targetSiteId,
          status: 'pending-terms-review',
          priority: 'P2',
          rationale: 'forged test entry',
          captureAuthorizedAt: null,
          authorizedBy: null,
        },
      ],
    }),
  );
  const issues = crossReferenceCaptureQueue(sites, queue, { catalog });
  assert.ok(
    issues.some((i) => i.code === 'capture-disallowed' || i.code === 'site-provider-mismatch'),
    `expected catalog-blocked or provider-mismatch issue, got: ${JSON.stringify(issues)}`,
  );
});

test('capture-sites profiles plug into gateRunner with the documented termsReviewStatus', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  for (const profile of sites.profiles) {
    // Live drivers must be rejected because committed profiles default to needs-terms-review.
    assert.throws(
      () =>
        gateRunner({
          driverName: 'playwright',
          liveEnvEnabled: true,
          authorized: true,
          termsReviewStatus: profile.termsReviewStatus,
        }),
      WorkflowGateError,
      `${profile.id}: gateRunner must refuse a live driver while termsReviewStatus="${profile.termsReviewStatus}"`,
    );

    // Mock drivers are still allowed for fixture/replay tests.
    assert.doesNotThrow(() =>
      gateRunner({
        driverName: 'mock',
        liveEnvEnabled: false,
        authorized: false,
        termsReviewStatus: profile.termsReviewStatus,
      }),
    );
  }
});

test('committed example files do not embed obvious raw secrets', () => {
  const forbiddenSubstrings = [
    'BEGIN RSA PRIVATE KEY',
    'BEGIN OPENSSH PRIVATE KEY',
    'aws_access_key_id',
    'aws_secret_access_key',
    '.env',
  ];
  for (const corpus of [SITES_TEXT, QUEUE_TEXT]) {
    for (const needle of forbiddenSubstrings) {
      assert.ok(!corpus.includes(needle), `committed example must not contain ${needle}`);
    }
    for (const line of corpus.split('\n')) {
      assert.ok(
        !SUSPICIOUS_SECRET_RE.test(line),
        `committed example contains suspicious secret-like value: ${line.slice(0, 80)}`,
      );
    }
  }
});

test('controlled action patterns appear in at least the four flagship provider profiles', () => {
  const sites = parseCaptureSites(SITES_TEXT);
  const byProvider = new Map();
  for (const profile of sites.profiles) byProvider.set(profile.providerId, profile);
  for (const providerId of REQUIRED_PROVIDER_IDS) {
    const profile = byProvider.get(providerId);
    assert.ok(profile, `missing site profile for ${providerId}`);
    const patterns = profile.forbiddenActions.map((a) => a.pattern);
    for (const required of CONTROLLED_ACTION_PATTERNS) {
      assert.ok(
        patterns.some((p) => p.includes(required)),
        `${providerId} site profile must block pattern containing "${required}", got ${JSON.stringify(patterns)}`,
      );
    }
  }
});
