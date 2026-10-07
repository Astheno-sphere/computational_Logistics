import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';

const DESIGN_DOC_PATH = new URL('../docs/maritime-capture-harness.md', import.meta.url).pathname;

const REQUIRED_COMPONENT_HEADINGS = [
  'Site profiles',
  'Playwright capture',
  'HAR backup',
  'Redaction worker',
  'Traffic IR',
  'Replay validation',
  'Supervisor pacing',
];

const REQUIRED_MODULE_CITATIONS = [
  'src/capture/site-profile.ts',
  'src/capture/recorder.ts',
  'src/capture/har-writer.ts',
  'src/capture/redact.ts',
  'src/capture/traffic-ir.ts',
  'src/capture/replay-validator.ts',
  'src/capture/workflow.ts',
];

const REQUIRED_REFERENCE_DOCS = [
  '<api-capture-checkout>/README.md',
  '<api-capture-checkout>/ARCHITECTURE.md',
  '<api-capture-checkout>/docs/LOCAL_AGENT_HARNESS.md',
];

const REQUIRED_RUNBOOK_LINKS = [
  'docs/runbooks/capture-fixture-import.md',
  'docs/runbooks/capture-traffic-ir.md',
  'docs/runbooks/capture-fixture-replay.md',
];

const REQUIRED_SAFETY_PHRASES = [
  'VESSEL_CAPTURE_LIVE',
  '--i-am-authorized',
  'termsReviewStatus',
  'captures/raw',
  'liveReplayDisabled',
];

function readDoc() {
  return readFileSync(DESIGN_DOC_PATH, 'utf8');
}

test('docs/maritime-capture-harness.md exists and is non-trivial', () => {
  const stat = statSync(DESIGN_DOC_PATH);
  assert.ok(stat.isFile(), 'maritime-capture-harness.md must be a regular file');
  assert.ok(
    stat.size > 4000,
    `expected the design doc to be a substantive synthesis (>4KB), got ${stat.size} bytes`,
  );
});

test('design doc covers every F5.AC4 component heading', () => {
  const text = readDoc();
  for (const heading of REQUIRED_COMPONENT_HEADINGS) {
    assert.ok(
      text.includes(heading),
      `design doc must discuss component "${heading}" (F5.AC4 enumerated requirement)`,
    );
  }
});

test('design doc cites the implementing module for each component', () => {
  const text = readDoc();
  for (const modulePath of REQUIRED_MODULE_CITATIONS) {
    assert.ok(
      text.includes(modulePath),
      `design doc must cite ${modulePath} so reviewers can audit the implementation`,
    );
  }
});

test('design doc references the api-capture source architecture (read-only)', () => {
  const text = readDoc();
  for (const ref of REQUIRED_REFERENCE_DOCS) {
    assert.ok(text.includes(ref), `design doc must cite reference doc ${ref}`);
  }
});

test('design doc links every existing capture runbook', () => {
  const text = readDoc();
  for (const link of REQUIRED_RUNBOOK_LINKS) {
    assert.ok(text.includes(link), `design doc must link runbook ${link}`);
  }
});

test('design doc documents the live-capture gating invariants', () => {
  const text = readDoc();
  for (const phrase of REQUIRED_SAFETY_PHRASES) {
    assert.ok(
      text.includes(phrase),
      `design doc must mention safety invariant "${phrase}" so the gating posture is auditable`,
    );
  }
});

test('design doc tracks the F5 and F5A parent feature statuses (both implemented after F5A.FOLLOWUP)', () => {
  const text = readDoc();
  assert.ok(
    text.includes('F5.AC4'),
    'design doc must reference F5.AC4 so the acceptance criterion mapping is explicit',
  );
  // After F5.FOLLOWUP, F5 is promoted to implemented. After F5A.FOLLOWUP,
  // F5A is also promoted; the design doc must report both parent statuses
  // so a reader knows the whole capture program is now shipped.
  assert.ok(
    /Parent feature `?F5`?[\s\S]{0,80}?implemented/i.test(text),
    'design doc must explicitly state that parent feature F5 is now implemented',
  );
  assert.ok(
    /Parent feature `?F5A`?[\s\S]{0,160}?implemented/i.test(text),
    'design doc must explicitly state that parent feature F5A is now implemented',
  );
});

test('design doc does not duplicate the authoritative redaction header list', () => {
  const text = readDoc();
  // The runbook at docs/runbooks/capture-fixture-import.md enumerates the
  // sensitive header list verbatim. The design doc must defer to
  // src/capture/redact.ts rather than copying it, so the two cannot drift.
  // We assert two redaction-list-shaped names are NOT both copied here.
  const hasFullHeaderListCopy =
    text.includes('X-Mt-Api-Key') && text.includes('X-Vesselfinder-Key');
  assert.equal(
    hasFullHeaderListCopy,
    false,
    'design doc must defer to src/capture/redact.ts for the redaction header list, not copy it',
  );
});
