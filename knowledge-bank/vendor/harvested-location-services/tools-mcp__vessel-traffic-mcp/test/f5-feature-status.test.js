import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';

import {
  FIXTURE_FORMAT_VERSION,
  importCapture,
} from '../dist/capture/import.js';
import { REDACTED_PLACEHOLDER } from '../dist/capture/redact.js';
import {
  TRAFFIC_IR_FORMAT_VERSION,
  buildTrafficIR,
} from '../dist/capture/traffic-ir.js';
import { createCaptureFixtureProvider } from '../dist/providers/capture-fixture.js';

const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const HARNESS_URL = new URL('../docs/maritime-capture-harness.md', import.meta.url);
const REFERENCE_ONLY_URL = new URL('../docs/runbooks/api-capture-reference-only.md', import.meta.url);

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

test('F5 feature-level status is flipped to implemented (all five ACs implemented and verified)', () => {
  const reqs = readRequirements();
  const f5 = featureBlock(reqs, 'F5', 'F5A');

  assert.equal(
    featureHeaderStatus(f5),
    'implemented',
    'F5 feature status must be promoted to implemented because AC1–AC5 are all implemented and covered',
  );

  const acStatusValues = [...f5.matchAll(/^\s{8}status:\s*(\S+)/gm)].map((m) => m[1]);
  assert.ok(acStatusValues.length >= 5, 'F5 must enumerate at least five acceptance criteria');
  for (const value of acStatusValues) {
    assert.equal(value, 'implemented', 'every F5 acceptance criterion must remain implemented');
  }
});

test('F5 acceptance criteria descriptions still match the F5.AC1/AC2/AC3/AC4/AC5 PRD contract', () => {
  const reqs = readRequirements();
  const f5 = featureBlock(reqs, 'F5', 'F5A');

  // AC1 — CLI importer that redacts sensitive headers, cookies, tokens, query params, body fields.
  assert.match(f5, /id: AC1[\s\S]{0,500}?CLI importer/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?HAR\/JSON samples/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?redacts/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?sensitive headers/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?cookies/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?tokens/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?query params/i);
  assert.match(f5, /id: AC1[\s\S]{0,500}?body fields/i);

  // AC2 — fingerprints, traffic IR, schema summaries; no credentials or replayable private session data.
  assert.match(f5, /id: AC2[\s\S]{0,500}?endpoint fingerprints/i);
  assert.match(f5, /id: AC2[\s\S]{0,500}?traffic IR/i);
  assert.match(f5, /id: AC2[\s\S]{0,500}?schema summaries/i);
  assert.match(f5, /id: AC2[\s\S]{0,500}?sanitized captures/i);
  assert.match(f5, /id: AC2[\s\S]{0,500}?credentials/i);
  assert.match(f5, /id: AC2[\s\S]{0,500}?replayable private session data/i);

  // AC3 — capture-fixture provider, replay sanitized fixtures, disabled for live use by default.
  assert.match(f5, /id: AC3[\s\S]{0,500}?capture-fixture provider/i);
  assert.match(f5, /id: AC3[\s\S]{0,500}?replay sanitized fixtures/i);
  assert.match(f5, /id: AC3[\s\S]{0,500}?adapter development/i);
  assert.match(f5, /id: AC3[\s\S]{0,500}?disabled for live use by default/i);

  // AC4 — maritime capture harness design based on api-capture patterns.
  assert.match(f5, /id: AC4[\s\S]{0,500}?maritime capture harness design/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?api-capture/);
  assert.match(f5, /id: AC4[\s\S]{0,500}?site profiles/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?Playwright capture/);
  assert.match(f5, /id: AC4[\s\S]{0,500}?HAR backup/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?replay validation/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?traffic IR/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?supervisor pacing/i);
  assert.match(f5, /id: AC4[\s\S]{0,500}?redaction worker/i);

  // AC5 — api-capture reference-only policy.
  assert.match(f5, /id: AC5[\s\S]{0,500}?raw api-capture sessions/i);
  assert.match(f5, /id: AC5[\s\S]{0,500}?\.env files/);
  assert.match(f5, /id: AC5[\s\S]{0,500}?cookies/i);
  assert.match(f5, /id: AC5[\s\S]{0,500}?logs/i);
  assert.match(f5, /id: AC5[\s\S]{0,500}?reference-only/i);
  assert.match(f5, /id: AC5[\s\S]{0,500}?not be imported into this project/i);
});

test('PRD completion keeps remaining parent feature statuses implemented (F2B, F4, F7)', () => {
  const reqs = readRequirements();

  // F1, F2, F3, F3B, F4A are implemented (asserted by their own feature-status tests) and excluded.
  // F5 is the promotion under test and excluded here.
  // F5A is implemented (asserted by f5a-feature-status.test.js) and excluded here.
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

test('F5 verification commands stay aligned with package.json scripts (AC1–AC3 npm test, AC4–AC5 docs-review)', () => {
  const reqs = readRequirements();
  const f5 = featureBlock(reqs, 'F5', 'F5A');

  // AC1 — importer is exercised by capture-import.test.js → npm test.
  assert.match(f5, /id: AC1[\s\S]{0,500}?verification: npm test/);
  // AC2 — IR + fingerprint + schema is exercised by capture-traffic-ir.test.js → npm test.
  assert.match(f5, /id: AC2[\s\S]{0,500}?verification: npm test/);
  // AC3 — capture-fixture provider is exercised by provider-capture-fixture*.test.js → npm test.
  assert.match(f5, /id: AC3[\s\S]{0,500}?verification: npm test/);
  // AC4 — design doc, owned by docs-review.
  assert.match(f5, /id: AC4[\s\S]{0,500}?verification: docs-review/);
  // AC5 — reference-only policy doc, owned by docs-review.
  assert.match(f5, /id: AC5[\s\S]{0,500}?verification: docs-review/);
});

test('F5 implementation modules referenced by the promotion are present and exported', async () => {
  // Deterministic guard: the promoted feature must keep its compiled module
  // surface available, since the rest of the suite (capture-import,
  // capture-traffic-ir, capture-workflow, provider-capture-fixture,
  // provider-capture-fixture-deterministic, api-capture-reference-only,
  // maritime-capture-harness-design) depends on these exports.
  const importMod = await import('../dist/capture/import.js');
  const redactMod = await import('../dist/capture/redact.js');
  const irMod = await import('../dist/capture/traffic-ir.js');
  const fingerprintMod = await import('../dist/capture/fingerprint.js');
  const schemaMod = await import('../dist/capture/schema.js');
  const captureFixtureMod = await import('../dist/providers/capture-fixture.js');

  // AC1 — importer + redaction surface.
  assert.equal(typeof importMod.importCapture, 'function');
  assert.equal(typeof importMod.fixtureToJson, 'function');
  assert.equal(importMod.FIXTURE_FORMAT_VERSION, 1);
  assert.equal(typeof redactMod.redactBody, 'function');
  assert.equal(typeof redactMod.redactHeaderPairs, 'function');
  assert.equal(typeof redactMod.redactUrl, 'function');
  assert.ok(Array.isArray(redactMod.SENSITIVE_HEADER_NAMES));
  assert.ok(Array.isArray(redactMod.SENSITIVE_QUERY_PARAM_NAMES));
  assert.ok(Array.isArray(redactMod.SENSITIVE_BODY_FIELD_NAMES));
  assert.equal(redactMod.REDACTED_PLACEHOLDER, '[REDACTED]');

  // AC2 — traffic IR / fingerprint / schema surface.
  assert.equal(typeof irMod.buildTrafficIR, 'function');
  assert.equal(typeof irMod.trafficIRToJson, 'function');
  assert.equal(irMod.TRAFFIC_IR_FORMAT_VERSION, 1);
  assert.equal(typeof fingerprintMod.buildFingerprints, 'function');
  assert.equal(typeof fingerprintMod.classifySegment, 'function');
  assert.equal(typeof fingerprintMod.breakdownPath, 'function');
  assert.equal(typeof schemaMod.summarizeBody, 'function');

  // AC3 — capture-fixture provider factory and replay guard.
  assert.equal(typeof captureFixtureMod.createCaptureFixtureProvider, 'function');
  assert.equal(typeof captureFixtureMod.CaptureFixtureProvider, 'function');
  assert.equal(typeof captureFixtureMod.CaptureFixtureProviderError, 'function');
  assert.ok(captureFixtureMod.CAPTURE_FIXTURE_ADAPTER_VERSION.startsWith('capture-fixture-'));
});

test('F5 AC1–AC2 end-to-end: HAR import redacts sensitive material and produces a sanitized IR', () => {
  // End-to-end invariant guarding the F5 promotion: import a HAR sample that
  // contains every sensitive class — Authorization header, Cookie header,
  // ?api_key query param, and a body password field — then build the
  // traffic IR. The fixture and IR must never echo the original secret
  // values, while still producing a usable endpoint fingerprint + schema
  // summary. No network, no clocks; deterministic enough for CI.
  const har = {
    log: {
      version: '1.2',
      entries: [
        {
          startedDateTime: '2026-05-15T00:00:00.000Z',
          request: {
            method: 'GET',
            url: 'https://example.invalid/api/v1/vessels?api_key=SECRET-DO-NOT-LEAK&mmsi=477806100',
            headers: [
              { name: 'Authorization', value: 'Bearer eyJleak.payload.signature' },
              { name: 'Cookie', value: 'session=PRIVATE-COOKIE-VALUE' },
              { name: 'Accept', value: 'application/json' },
            ],
            cookies: [{ name: 'session', value: 'PRIVATE-COOKIE-VALUE' }],
            postData: {
              mimeType: 'application/json',
              text: JSON.stringify({ password: 'SUPER-SECRET-PW', mmsi: '477806100' }),
            },
          },
          response: {
            status: 200,
            statusText: 'OK',
            headers: [{ name: 'Content-Type', value: 'application/json' }],
            cookies: [],
            content: {
              mimeType: 'application/json',
              text: JSON.stringify({ ok: true, mmsi: '477806100', lat: 31.2, lon: 121.4 }),
            },
          },
        },
      ],
    },
  };
  const { fixture, warnings } = importCapture(JSON.stringify(har), {
    format: 'har',
    label: 'f5-status-e2e',
    source: 'inline-test',
    now: () => '2026-05-15T00:00:00.000Z',
  });
  assert.equal(fixture.version, FIXTURE_FORMAT_VERSION);
  assert.deepEqual(warnings, []);
  assert.equal(fixture.entries.length, 1);

  const serialized = JSON.stringify(fixture);
  // Hard invariant: NONE of the original secrets may survive the import.
  for (const leak of ['SECRET-DO-NOT-LEAK', 'eyJleak.payload.signature', 'PRIVATE-COOKIE-VALUE', 'SUPER-SECRET-PW']) {
    assert.equal(
      serialized.includes(leak),
      false,
      `imported fixture must not contain the original secret "${leak}"`,
    );
  }
  // The placeholder must be present, proving the redactor actually fired.
  assert.ok(serialized.includes(REDACTED_PLACEHOLDER), 'imported fixture must contain the redaction placeholder');
  assert.ok(fixture.redactionReport.totalRedactions >= 4, 'redaction report must count at least four redactions');

  // Build the traffic IR over the sanitized fixture.
  const ir = buildTrafficIR(fixture, { now: () => '2026-05-15T00:00:01.000Z' });
  assert.equal(ir.version, TRAFFIC_IR_FORMAT_VERSION);
  assert.equal(ir.endpoints.length, 1);
  const endpoint = ir.endpoints[0];
  assert.equal(endpoint.method, 'GET');
  assert.equal(endpoint.origin, 'https://example.invalid');
  assert.ok(endpoint.pathTemplate.startsWith('/api/'), 'path template must be derived');
  assert.ok(
    endpoint.redactedHeaderNames.some((name) => name.toLowerCase() === 'authorization'),
    'Authorization must be reported as a redacted header in the IR',
  );
  assert.ok(
    endpoint.queryKeys.some((q) => q.name === 'api_key' && q.redacted === true),
    'api_key query key must be marked redacted in the IR',
  );
  assert.ok(endpoint.statuses.some((s) => s.status === 200), 'IR must summarize the 200 response');

  // Hard invariant: the IR itself must never echo any secret value.
  const irSerialized = JSON.stringify(ir);
  for (const leak of ['SECRET-DO-NOT-LEAK', 'eyJleak.payload.signature', 'PRIVATE-COOKIE-VALUE', 'SUPER-SECRET-PW']) {
    assert.equal(
      irSerialized.includes(leak),
      false,
      `traffic IR must not contain the original secret "${leak}"`,
    );
  }
});

test('F5.AC3 capture-fixture provider refuses any fixture that is not flagged liveReplayDisabled=true', () => {
  // End-to-end invariant guarding the F5 promotion: the capture-fixture
  // provider must reject fixtures whose provenance does not explicitly
  // declare liveReplayDisabled=true. This is the structural enforcement
  // behind "disabled for live use by default" — a sanitized fixture lacking
  // the disabled flag is treated as suspect and refused at construction
  // time, so a CI run cannot accidentally route live traffic through it.
  const unsafeFixture = {
    version: 1,
    label: 'unsafe-fixture',
    createdAt: '2026-05-15T00:00:00.000Z',
    source: { format: 'json', entryCount: 0 },
    entries: [],
    redactionReport: { totalRedactions: 0, byKind: {} },
    notes: [],
    // Intentionally missing provenance entirely — should be rejected.
  };
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [unsafeFixture] }),
    /missing provenance|liveReplayDisabled/i,
    'capture-fixture provider must reject fixtures with no provenance',
  );

  const wrongFlagFixture = {
    ...unsafeFixture,
    label: 'wrong-flag',
    provenance: {
      siteProfileId: 'example-site',
      siteProfileVersion: 1,
      recorderDriver: 'mock',
      liveReplayDisabled: false, // explicit opt-in to live replay — must be refused.
      capturedAt: '2026-05-15T00:00:00.000Z',
    },
  };
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [wrongFlagFixture] }),
    /liveReplayDisabled/i,
    'capture-fixture provider must reject fixtures with liveReplayDisabled !== true',
  );

  // Empty fixture set must also fail — the provider has no value without
  // sanitized inputs and we never want a silently-empty fallback.
  assert.throws(
    () => createCaptureFixtureProvider({ fixtures: [] }),
    /at least one sanitized fixture/i,
    'capture-fixture provider must require at least one sanitized fixture',
  );
});

test('F5.AC4 maritime capture harness design doc is present and reports the new parent status', () => {
  const stat = statSync(HARNESS_URL.pathname);
  assert.ok(stat.isFile(), 'F5.AC4 design doc must be a regular file');
  assert.ok(stat.size > 3000, `F5.AC4 design doc should be substantive (>3KB), got ${stat.size} bytes`);
  const text = readFileSync(HARNESS_URL, 'utf8');
  // The design doc must reference every AC4 component name from requirements.yaml.
  for (const term of ['site profile', 'Playwright', 'HAR', 'replay', 'traffic IR', 'pacing', 'redaction']) {
    assert.ok(
      new RegExp(term, 'i').test(text),
      `F5.AC4 design doc must mention "${term}" so the AC4 scope is explicit`,
    );
  }
  // After F5.FOLLOWUP the doc owns the F5 parent-status statement.
  assert.match(text, /Parent feature `?F5`?[\s\S]{0,80}?implemented/i);
  // After F5A.FOLLOWUP, F5A is also promoted; the design doc must reflect that.
  assert.match(text, /Parent feature `?F5A`?[\s\S]{0,160}?implemented/i);
});

test('F5.AC5 api-capture reference-only runbook is still the authoritative boundary doc', () => {
  // The F5 promotion cannot remove the reference-only contract; F5.AC5
  // remains the boundary document and the api-capture-reference-only test
  // already covers its content. Here we just verify the file still exists
  // and is large enough to be the documented runbook, so a future refactor
  // that accidentally renames or shrinks it fails this guard alongside
  // its sibling test/api-capture-reference-only.test.js.
  const stat = statSync(REFERENCE_ONLY_URL.pathname);
  assert.ok(stat.isFile(), 'F5.AC5 runbook must remain a regular file');
  assert.ok(stat.size > 3000, `F5.AC5 runbook should remain substantive (>3KB), got ${stat.size} bytes`);
});
