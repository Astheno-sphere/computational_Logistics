import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

test('PRD documents the authorized capture boundary', () => {
  const prd = readFileSync(new URL('../docs/PRD.md', import.meta.url), 'utf8');
  assert.match(prd, /Authorized Capture Workflow/);
  assert.match(prd, /Do not bypass/i);
});

test('package exposes required verification scripts', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.equal(pkg.name, '@tools-mcp/vessel-traffic-mcp');
  assert.ok(pkg.scripts.lint);
  assert.ok(pkg.scripts.test);
  assert.ok(pkg.scripts.build);
});
