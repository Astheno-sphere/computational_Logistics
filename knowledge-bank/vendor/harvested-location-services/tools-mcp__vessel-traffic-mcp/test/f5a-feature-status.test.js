import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

import {
  CAPTURE_QUEUE_FORMAT_VERSION,
  CAPTURE_SITES_FORMAT_VERSION,
  crossReferenceCaptureQueue,
  loadCaptureQueueFromDisk,
  loadCaptureSitesFromDisk,
} from '../dist/capture/capture-queue.js';
import { createMockRecorderDriver } from '../dist/capture/recorder.js';
import { gateRunner, runCaptureWorkflow, WorkflowGateError } from '../dist/capture/workflow.js';
import { parseProviderCatalog } from '../dist/providers/catalog.js';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const RUNBOOK_URL = new URL('../docs/runbooks/capture-execution.md', import.meta.url);
const HARNESS_URL = new URL('../docs/maritime-capture-harness.md', import.meta.url);
const SITES_PATH = new URL('../config/capture-sites.example.json', import.meta.url).pathname;
const QUEUE_PATH = new URL('../config/capture-queue.example.json', import.meta.url).pathname;
const CATALOG_PATH = new URL('../config/provider-catalog.example.json', import.meta.url).pathname;

function readRequirements() {
  return readFileSync(REQUIREMENTS_URL, 'utf8');
}

function featureBlock(reqs, featureId, nextFeatureId) {
  const start = reqs.indexOf(`id: ${featureId}`);
  assert.ok(start > 0, `requirements.yaml must contain feature ${featureId}`);
  const end = nextFeatureId ? reqs.indexOf(`id: ${nextFeatureId}`, start) : -1;
  return reqs.slice(start, end > 0 ? end : undefined);
}

function featureHeaderStatus(block) {
  const acIndex = block.indexOf('acceptance_criteria:');
  const header = acIndex > 0 ? block.slice(0, acIndex) : block;
  const match = header.match(/^\s{4}status:\s*(\S+)/m);
  assert.ok(match, 'feature block must contain a header-level status field');
  return match[1];
}

test('F5A feature-level status is flipped to implemented (all three ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f5a = featureBlock(reqs, 'F5A', 'F6');

  assert.equal(
    featureHeaderStatus(f5a),
    'implemented',
    'F5A feature status must be promoted to implemented because AC1, AC2, AC3 are all implemented and covered',
  );

  const acStatusValues = [...f5a.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 3, 'F5A must enumerate at least three acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F5A acceptance criterion must remain implemented');
  }
});

test('F5A acceptance criteria descriptions still match the F5A.AC1/AC2/AC3 PRD contract', () => {
  const reqs = readRequirements();
  const f5a = featureBlock(reqs, 'F5A', 'F6');

  // AC1 — maritime site-profile examples + capture queue metadata for flagship web-only providers.
  assert.match(f5a, /id: AC1[\s\S]{0,600}?safe maritime site-profile examples/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?capture queue metadata/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?MarineTraffic/);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?VesselFinder/);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?MyShipTracking/);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?FleetMon/);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?allowed origins/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?forbidden actions/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?session-loss indicators/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?pacing/i);
  assert.match(f5a, /id: AC1[\s\S]{0,600}?terms-review status/i);

  // AC2 — operator-only capture workflow reusing the api-capture patterns.
  assert.match(f5a, /id: AC2[\s\S]{0,600}?operator-only capture workflow/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?api-capture patterns/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?Playwright browser control/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?XHR\/fetch hooks/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?HAR backup/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?replay validation/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?traffic IR/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?schema summaries/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?redaction/i);
  assert.match(f5a, /id: AC2[\s\S]{0,600}?disabled-by-default sanitized fixtures/i);

  // AC3 — runbook for authorized maritime captures, raw artifact location, sanitized promotion, and CI exclusion.
  assert.match(f5a, /id: AC3[\s\S]{0,600}?runbook for performing authorized maritime captures/i);
  assert.match(f5a, /id: AC3[\s\S]{0,600}?raw private artifacts/i);
  assert.match(f5a, /id: AC3[\s\S]{0,600}?sanitized fixtures are promoted/i);
  assert.match(f5a, /id: AC3[\s\S]{0,600}?default autodev\/CI must never call live paid providers/i);
  assert.match(f5a, /id: AC3[\s\S]{0,600}?capture private sessions/i);
});

test('PRD completion keeps remaining parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1, F2, F3, F3B, F4A, F5 are implemented (asserted by their own feature-status tests) and excluded.
  // F5A is the promotion under test and excluded here.
  // F6 is implemented (asserted by f6-feature-status.test.js) and excluded here.
  // F2B, F4, and F7 are now promoted by the PRD completion pass; keep this
  // guard to prevent stale status rollbacks.
  const guards = [
    ['F2B', 'F3'],
    ['F4', 'F4A'],
    ['F7', null],
  ];

  for (const [id, next] of guards) {
    const block = featureBlock(reqs, id, next);
    assert.equal(
      featureHeaderStatus(block),
      'implemented',
      `${id} parent feature status must remain implemented after PRD completion`,
    );
  }
});

test('F5A verification commands stay aligned with package.json scripts (AC1–AC2 npm test, AC3 docs-review)', () => {
  const reqs = readRequirements();
  const f5a = featureBlock(reqs, 'F5A', 'F6');

  // AC1 — capture-sites and capture-queue parsers / cross-reference exercised by capture-sites-queue.test.js → npm test.
  assert.match(f5a, /id: AC1[\s\S]{0,600}?verification: npm test/);
  // AC2 — operator capture workflow exercised by capture-workflow.test.js → npm test.
  assert.match(f5a, /id: AC2[\s\S]{0,600}?verification: npm test/);
  // AC3 — capture-execution runbook owned by docs-review (per requirements.yaml).
  assert.match(f5a, /id: AC3[\s\S]{0,600}?verification: docs-review/);
});

test('F5A implementation modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must keep its compiled module
  // surface available, since the rest of the suite (capture-sites-queue,
  // capture-workflow, capture-execution-runbook) depends on these exports.
  const captureQueue = await import('../dist/capture/capture-queue.js');
  const siteProfile = await import('../dist/capture/site-profile.js');
  const recorder = await import('../dist/capture/recorder.js');
  const harWriter = await import('../dist/capture/har-writer.js');
  const workflow = await import('../dist/capture/workflow.js');
  const replayValidator = await import('../dist/capture/replay-validator.js');
  const runnerCli = await import('../dist/capture/runner-cli.js');

  // AC1 — capture-sites + capture-queue + cross-reference.
  assert.equal(typeof captureQueue.parseCaptureSites, 'function');
  assert.equal(typeof captureQueue.parseCaptureQueue, 'function');
  assert.equal(typeof captureQueue.loadCaptureSitesFromDisk, 'function');
  assert.equal(typeof captureQueue.loadCaptureQueueFromDisk, 'function');
  assert.equal(typeof captureQueue.crossReferenceCaptureQueue, 'function');
  assert.equal(captureQueue.CAPTURE_SITES_FORMAT_VERSION, 1);
  assert.equal(captureQueue.CAPTURE_QUEUE_FORMAT_VERSION, 1);

  // AC2 — operator capture workflow surface.
  assert.equal(typeof siteProfile.loadSiteProfile, 'function');
  assert.equal(typeof siteProfile.validateSiteProfile, 'function');
  assert.equal(typeof siteProfile.assertOriginAllowed, 'function');
  assert.equal(typeof siteProfile.assertActionAllowed, 'function');
  assert.equal(typeof siteProfile.detectSessionLoss, 'function');
  assert.equal(typeof recorder.createMockRecorderDriver, 'function');
  assert.equal(typeof harWriter.assertHarOutputPath, 'function');
  assert.equal(typeof harWriter.recordedExchangesToHar, 'function');
  assert.equal(typeof workflow.runCaptureWorkflow, 'function');
  assert.equal(typeof workflow.gateRunner, 'function');
  assert.equal(typeof workflow.WorkflowGateError, 'function');
  assert.equal(typeof workflow.WorkflowAbortedError, 'function');
  assert.equal(typeof replayValidator.compareTrafficIR, 'function');
  assert.equal(typeof runnerCli.runRunnerCli, 'function');
});

test('F5A.AC1 the committed capture-sites/queue examples parse end-to-end and cross-reference the catalog', () => {
  // End-to-end invariant for AC1: the committed example files must round-trip
  // through the production parsers, expose every required flagship maritime
  // provider, and cross-reference cleanly against the provider catalog.
  const sites = loadCaptureSitesFromDisk(SITES_PATH);
  const queue = loadCaptureQueueFromDisk(QUEUE_PATH);
  const catalog = parseProviderCatalog(readFileSync(CATALOG_PATH, 'utf8'));

  assert.equal(sites.version, CAPTURE_SITES_FORMAT_VERSION);
  assert.equal(queue.version, CAPTURE_QUEUE_FORMAT_VERSION);
  assert.ok(sites.profiles.length >= 8, `expected ≥8 site profiles, got ${sites.profiles.length}`);
  assert.ok(queue.entries.length >= 4, `expected ≥4 queue entries, got ${queue.entries.length}`);

  const flagshipProviders = ['marinetraffic', 'vesselfinder', 'myshiptracking', 'fleetmon'];
  const profileProviderIds = new Set(sites.profiles.map((p) => p.providerId));
  const queueProviderIds = new Set(queue.entries.map((e) => e.providerId));
  for (const id of flagshipProviders) {
    assert.ok(profileProviderIds.has(id), `capture-sites must include the ${id} profile`);
    assert.ok(queueProviderIds.has(id), `capture-queue must include the ${id} entry`);
  }

  // Every committed entry defaults to needs-terms-review (no live capture allowed by default).
  for (const profile of sites.profiles) {
    assert.equal(profile.termsReviewStatus, 'needs-terms-review');
    assert.equal(profile.pacing.maxConcurrent, 1);
  }
  for (const entry of queue.entries) {
    assert.equal(entry.status, 'pending-terms-review');
    assert.equal(entry.captureAuthorizedAt, null);
    assert.equal(entry.authorizedBy, null);
  }

  const issues = crossReferenceCaptureQueue(sites, queue, { catalog });
  assert.deepEqual(issues, [], `cross-reference issues: ${JSON.stringify(issues, null, 2)}`);
});

test('F5A.AC2 gateRunner enforces the triple-gate live driver contract for every committed site profile', () => {
  // End-to-end invariant for AC2: the operator-only workflow must refuse a
  // live driver while a committed profile is needs-terms-review, even when
  // VESSEL_CAPTURE_LIVE=1 and --i-am-authorized are set. This is the
  // structural enforcement behind "disabled by default" and "default autodev
  // / CI must never call live paid providers".
  const sites = loadCaptureSitesFromDisk(SITES_PATH);
  for (const profile of sites.profiles) {
    assert.throws(
      () =>
        gateRunner({
          driverName: 'playwright',
          liveEnvEnabled: true,
          authorized: true,
          termsReviewStatus: profile.termsReviewStatus,
        }),
      WorkflowGateError,
      `${profile.id}: live driver must be refused while termsReviewStatus="${profile.termsReviewStatus}"`,
    );
    // Mock driver must still be usable for replay/test paths (fixture promotion etc.).
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

test('F5A.AC3 capture-execution runbook is present, self-identifies, and reports the promoted parent status', () => {
  // The runbook is owned by F5A.AC3 (docs-review). After the promotion, the
  // sibling design doc must report the new parent status, but the operator
  // runbook itself only needs to exist as the authoritative source of the
  // workflow. Detailed contract assertions live in capture-execution-runbook.test.js.
  const stat = statSync(RUNBOOK_URL.pathname);
  assert.ok(stat.isFile(), 'F5A.AC3 runbook must be a regular file');
  assert.ok(stat.size > 3000, `F5A.AC3 runbook should be substantive (>3KB), got ${stat.size} bytes`);
  const text = readFileSync(RUNBOOK_URL, 'utf8');
  assert.match(text, /F5A\.AC3/, 'runbook must self-identify against the acceptance criterion');

  // The design doc must agree with requirements.yaml after the promotion.
  const harness = readFileSync(HARNESS_URL, 'utf8');
  assert.match(
    harness,
    /Parent feature `?F5A`?[\s\S]{0,160}?implemented/i,
    'design doc must explicitly state that parent feature F5A is now implemented',
  );
});

test('F5A.AC2 end-to-end integration: committed flagship profiles run through runCaptureWorkflow with a mock driver and emit a sanitized fixture', async () => {
  // This integration check bridges AC1 (committed config) and AC2 (workflow).
  // The capture-workflow tests use synthetic profiles to validate the workflow
  // surface, and the capture-sites-queue tests use the committed profiles to
  // validate parsing/gating. Neither runs the *committed* profile through the
  // *full* mock workflow, which is what an operator would do as their first
  // step before requesting authorization. This test plugs that gap by exercising
  // the committed marinetraffic.web profile end-to-end and verifying the
  // sanitized fixture produced is .private-suffixed, sanitized, and stamped
  // with liveReplayDisabled=true.
  const sites = loadCaptureSitesFromDisk(SITES_PATH);
  const flagshipIds = ['marinetraffic.web', 'vesselfinder.web', 'myshiptracking.web', 'fleetmon.web'];
  const flagshipProfiles = sites.profiles.filter((p) => flagshipIds.includes(p.id));
  assert.equal(
    flagshipProfiles.length,
    flagshipIds.length,
    `expected committed flagship profiles ${flagshipIds.join(',')}, got ${flagshipProfiles.map((p) => p.id).join(',')}`,
  );

  // A token shaped like a session secret. None of these may appear in the
  // sanitized fixture written by runCaptureWorkflow.
  const FAKE_BEARER = 'F5A-AC2-INTEGRATION-BEARER-DO-NOT-LEAK';
  const FAKE_COOKIE = 'sid=F5A-AC2-INTEGRATION-COOKIE-DO-NOT-LEAK';

  for (const profile of flagshipProfiles) {
    const tmp = mkdtempSync(join(tmpdir(), 'f5a-ac2-integration-'));
    try {
      // Build a safe synthetic exchange that targets the profile's first
      // allowedOrigin and avoids every forbiddenActions pattern. The mock
      // driver replays this exchange so the workflow can write the fixture.
      const origin = profile.allowedOrigins[0];
      const safePath = '/en/ais/index/ports/range/?ais_lang=en';
      // Sanity: the path must not collide with the profile's forbidden patterns.
      for (const forbidden of profile.forbiddenActions) {
        assert.ok(
          !safePath.toLowerCase().includes(forbidden.pattern.toLowerCase()),
          `${profile.id}: test path "${safePath}" must not contain forbidden pattern "${forbidden.pattern}"`,
        );
      }
      const targetUrl = `${origin}${safePath}`;
      const exchange = {
        method: 'GET',
        url: targetUrl,
        startedAt: '2026-05-15T14:00:00.000Z',
        request: {
          headers: [
            { name: 'Authorization', value: `Bearer ${FAKE_BEARER}` },
            { name: 'Cookie', value: FAKE_COOKIE },
            { name: 'Accept', value: 'text/html' },
          ],
          cookies: [{ name: 'sid', value: FAKE_COOKIE }],
          mimeType: undefined,
          body: undefined,
        },
        response: {
          status: 200,
          statusText: 'OK',
          headers: [{ name: 'Content-Type', value: 'text/html' }],
          cookies: [],
          mimeType: 'text/html',
          body: '<html><body>ports listing</body></html>',
        },
      };
      const driver = createMockRecorderDriver({
        steps: [{ step: { kind: 'goto', url: targetUrl }, exchanges: [exchange] }],
      });

      const result = await runCaptureWorkflow({
        profile,
        driver,
        steps: [{ kind: 'goto', url: targetUrl }],
        cwd: tmp,
        label: `integration-${profile.id}`,
        // Mock driver path: no env or authorization required, and the
        // committed profile's "needs-terms-review" status must still be
        // allowed for the mock driver (the live driver is the one gated by
        // the F5A.AC2 triple-gate test above).
        authorized: false,
        liveEnvEnabled: false,
        validateReplay: true,
        now: () => '2026-05-15T14:00:01.000Z',
      });

      // The sanitized fixture must default to .private.json (gitignored) and
      // must be stamped with liveReplayDisabled=true even though we used a
      // mock driver — this is the F5A "disabled by default" invariant.
      assert.match(result.fixturePath, /\.private\.json$/);
      assert.match(result.irPath, /\.ir\.private\.json$/);
      const fixtureText = readFileSync(result.fixturePath, 'utf8');
      assert.ok(
        !fixtureText.includes(FAKE_BEARER),
        `${profile.id}: sanitized fixture must not include raw bearer token`,
      );
      assert.ok(
        !fixtureText.includes(FAKE_COOKIE),
        `${profile.id}: sanitized fixture must not include raw cookie value`,
      );
      const fixture = JSON.parse(fixtureText);
      assert.equal(fixture.provenance.liveReplayDisabled, true);
      assert.equal(fixture.provenance.siteProfileId, profile.id);
      assert.equal(fixture.provenance.recorderDriver, 'mock');

      // Replay validation must be deterministic so default verification
      // cannot regress to a flaky state.
      assert.ok(result.validation, 'validateReplay=true must produce a validation report');
      assert.equal(result.validation.identical, true);

      // The IR must record the credential-bearing headers as redacted, so a
      // downstream reader cannot silently re-replay them.
      assert.equal(result.ir.endpoints.length, 1);
      const flagged = result.ir.endpoints[0].redactedHeaderNames.map((n) => n.toLowerCase());
      assert.ok(
        flagged.includes('authorization'),
        `${profile.id}: IR must flag Authorization header as redacted`,
      );
      assert.ok(
        flagged.includes('cookie'),
        `${profile.id}: IR must flag Cookie header as redacted`,
      );
    } finally {
      rmSync(tmp, { recursive: true, force: true });
    }
  }
});

test('F5A flaky-test control: default test environment never enables the live capture gate', () => {
  // Flaky-test control for AC2 + AC3: default verification (npm test) must
  // never have VESSEL_CAPTURE_LIVE=1 set, otherwise a future regression that
  // passes --i-am-authorized as a positional default could escape the gate.
  // The runner-cli tests already inject env={} explicitly; this test guards
  // the surrounding process so a CI runner with an accidentally exported flag
  // would fail loudly here instead of triggering a live capture.
  const envFlag = process.env.VESSEL_CAPTURE_LIVE;
  assert.ok(
    envFlag === undefined || envFlag === '' || envFlag === '0',
    `VESSEL_CAPTURE_LIVE must not be truthy during default verification; got "${envFlag}". ` +
      `If you set this intentionally for an authorized live capture, do not run npm test from that shell.`,
  );

  // gateRunner must continue to refuse the live driver under the default env
  // even with the strongest possible operator confirmation, so long as a
  // committed profile is still pending terms review.
  const sites = loadCaptureSitesFromDisk(SITES_PATH);
  const samples = sites.profiles.slice(0, 2);
  for (const profile of samples) {
    assert.throws(
      () =>
        gateRunner({
          driverName: 'playwright',
          liveEnvEnabled: false,
          authorized: true,
          termsReviewStatus: profile.termsReviewStatus,
        }),
      WorkflowGateError,
      `${profile.id}: live driver must remain refused while VESSEL_CAPTURE_LIVE is unset`,
    );
  }
});
