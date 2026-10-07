import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const RUNBOOK_URL = new URL('../docs/runbooks/operator.md', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const CATALOG_URL = new URL('../config/provider-catalog.example.json', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);

function readRunbook() {
  return readFileSync(RUNBOOK_URL, 'utf8');
}

test('operator runbook covers F6.AC3 surfaces (credentials, rate limits, live-test toggles, client setup)', () => {
  const text = readRunbook();

  assert.match(text, /F6\.AC3/, 'runbook should self-identify against the acceptance criterion');

  assert.match(text, /## Provider credentials/i, 'must have a provider credentials section');
  assert.match(text, /## Rate limits/i, 'must have a rate limits section');
  assert.match(text, /## Live-test toggles/i, 'must have a live-test toggles section');
  assert.match(text, /## Client setup/i, 'must have a client setup section');
});

test('operator runbook documents the BYOK env-var contract and the gitignored local config', () => {
  const text = readRunbook();

  assert.match(text, /VESSEL_MCP_PROFILE_<LABEL>__<FIELD>/);
  assert.match(text, /config\/credential-profiles\.local\.json/);
  assert.match(text, /environment value wins/i);
  assert.match(text, /credential_profiles/, 'must reference the read-only MCP tool');
});

test('operator runbook documents live-test gating and default-off semantics', () => {
  const text = readRunbook();

  assert.match(text, /VESSEL_MCP_LIVE_TEST_/);
  assert.match(text, /defaultDisabled/);
  assert.match(text, /Default verification.*not call.*paid or live/i);
  assert.match(text, /skip(ped)?/i, 'must say tests skip when required env vars are missing');
});

test('operator runbook documents both transports and the read-only contract', () => {
  const text = readRunbook();

  // stdio surface
  assert.match(text, /VESSEL_MCP_TRANSPORT=stdio/);
  assert.match(text, /Claude Desktop/);
  assert.match(text, /Claude Code/);
  assert.match(text, /MCP Inspector/);
  // http surface
  assert.match(text, /VESSEL_MCP_TRANSPORT=http/);
  assert.match(text, /VESSEL_MCP_HTTP_HOST/);
  assert.match(text, /VESSEL_MCP_HTTP_PORT/);
  assert.match(text, /VESSEL_MCP_AUTH_TOKEN/);
  assert.match(text, /Authorization: Bearer/);
  assert.match(text, /GET \/health/);
  assert.match(text, /X-Request-Id/);
  // read-only & boundary
  assert.match(text, /read-only/i);
  assert.match(text, /must not modify provider accounts/i);
});

test('operator runbook live-test cheat sheet matches the real provider catalog', () => {
  const runbook = readRunbook();
  const catalog = JSON.parse(readFileSync(CATALOG_URL, 'utf8'));

  // Pick a small, stable set of catalog entries that the runbook names by id.
  // Each assertion is sourced from the catalog so a rename or env-var change
  // breaks this test before it ships.
  const targets = ['marinetraffic', 'aishub', 'aisstream', 'barentswatch'];
  for (const id of targets) {
    const entry = catalog.entries.find((e) => e.id === id);
    assert.ok(entry, `catalog must contain ${id}`);
    assert.equal(entry.liveTest.defaultDisabled, true, `${id} must declare defaultDisabled=true`);
    assert.ok(
      entry.liveTest.enabledFlagEnvVar.startsWith('VESSEL_MCP_LIVE_TEST_'),
      `${id} live-test flag must use the VESSEL_MCP_LIVE_TEST_ prefix`,
    );

    // The runbook must reference this provider id by name.
    assert.match(
      runbook,
      new RegExp(`\\b${id}\\b`),
      `runbook should mention provider id "${id}"`,
    );
    // And document at least one of its required env vars.
    const envVar = entry.auth.envVars[0] ?? entry.liveTest.requiredEnvVars[0];
    if (envVar) {
      assert.ok(
        runbook.includes(envVar),
        `runbook should reference env var ${envVar} for ${id}`,
      );
    }
  }
});

test('operator runbook surfaces the AISHub strict throttle', () => {
  const text = readRunbook();
  assert.match(text, /AISHub/);
  assert.match(text, /one[- ]request[- ]per[- ]minute/i);
});

test('operator runbook references the limiter and provider rate-limit contract', () => {
  const text = readRunbook();
  assert.match(text, /RateLimitPolicy/);
  assert.match(text, /requestsPerInterval/);
  assert.match(text, /intervalMs/);
  assert.match(text, /src\/util\/rate-limit\.ts/);
});

test('operator runbook does not leak credential-shaped strings', () => {
  const text = readRunbook();

  // No JWTs (eyJ... two-segment), AWS keys, GitHub PATs, or sk- secret tokens.
  assert.doesNotMatch(text, /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, 'no JWTs');
  assert.doesNotMatch(text, /\b(AKIA|ASIA)[A-Z0-9]{16}\b/, 'no AWS access key IDs');
  assert.doesNotMatch(text, /\bghp_[A-Za-z0-9]{20,}\b/, 'no GitHub PATs');
  assert.doesNotMatch(text, /\bsk-[A-Za-z0-9]{20,}\b/, 'no sk- secrets');
});

test('README links the operator runbook so MCP operators can find it', () => {
  const readme = readFileSync(README_URL, 'utf8');
  assert.match(readme, /docs\/runbooks\/operator\.md/, 'README must link the operator runbook');
});

test('F6.AC3 status in requirements.yaml is set to implemented for this acceptance criterion', () => {
  const reqs = readFileSync(REQUIREMENTS_URL, 'utf8');
  // Locate the F6 block and within it the AC3 entry.
  const f6Index = reqs.indexOf('id: F6');
  assert.ok(f6Index > 0, 'requirements.yaml must contain feature F6');
  const f7Index = reqs.indexOf('id: F7', f6Index);
  const f6Block = reqs.slice(f6Index, f7Index > 0 ? f7Index : undefined);

  const ac3Index = f6Block.indexOf('id: AC3');
  assert.ok(ac3Index > 0, 'F6 must contain acceptance criterion AC3');
  const ac3Block = f6Block.slice(ac3Index, ac3Index + 400);
  assert.match(ac3Block, /operator runbook/i, 'AC3 description must match the runbook criterion');
  assert.match(ac3Block, /status: implemented/, 'F6.AC3 status must be flipped to implemented');
  assert.match(ac3Block, /verification: docs-review/, 'F6.AC3 verification must remain docs-review');
});
