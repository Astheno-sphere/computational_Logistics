import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const RUNBOOK_URL = new URL('../docs/runbooks/clients.md', import.meta.url);
const RUNBOOK_DIR = dirname(fileURLToPath(RUNBOOK_URL));
const README_URL = new URL('../README.md', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const PACKAGE_URL = new URL('../package.json', import.meta.url);
const CREATE_SERVER_URL = new URL('../src/server/create-server.ts', import.meta.url);

function readRunbook() {
  return readFileSync(RUNBOOK_URL, 'utf8');
}

function extractFencedBlocks(markdown, lang) {
  const fence = new RegExp('```' + lang + '\\n([\\s\\S]*?)```', 'g');
  const blocks = [];
  let match;
  while ((match = fence.exec(markdown)) !== null) {
    blocks.push(match[1]);
  }
  return blocks;
}

function extractRelativeMarkdownLinks(markdown) {
  const linkPattern = /\]\((\.\/[^)\s]+\.md|[A-Za-z0-9_-][^)\s]*\.md)\)/g;
  const targets = new Set();
  let match;
  while ((match = linkPattern.exec(markdown)) !== null) {
    targets.add(match[1]);
  }
  return [...targets];
}

test('client setup runbook self-identifies against F1.AC3', () => {
  const text = readRunbook();
  assert.match(text, /F1\.AC3/, 'runbook should self-identify against the acceptance criterion');
});

test('client setup runbook covers required clients', () => {
  const text = readRunbook();
  assert.match(text, /## Claude Desktop/i);
  assert.match(text, /## Claude Code/i);
  assert.match(text, /## ChatGPT remote MCP/i);
  assert.match(text, /## Gemini CLI and Gemini Code Assist/i);
  assert.match(text, /## Generic MCP Inspector/i);
});

test('client setup runbook documents the stdio transport contract', () => {
  const text = readRunbook();
  assert.match(text, /VESSEL_MCP_TRANSPORT=stdio/);
  assert.match(text, /dist\/index\.js/);
  assert.match(text, /claude_desktop_config\.json/);
  assert.match(text, /\.mcp\.json/, 'Claude Code project-scoped MCP config');
  assert.match(text, /@modelcontextprotocol\/inspector/);
});

test('client setup runbook documents the Streamable HTTP transport contract', () => {
  const text = readRunbook();
  assert.match(text, /VESSEL_MCP_TRANSPORT=http/);
  assert.match(text, /VESSEL_MCP_HTTP_HOST/);
  assert.match(text, /VESSEL_MCP_HTTP_PORT/);
  assert.match(text, /VESSEL_MCP_AUTH_TOKEN/);
  assert.match(text, /Authorization: Bearer/);
  assert.match(text, /GET \/health/);
  assert.match(text, /POST \/mcp/);
  assert.match(text, /X-Request-Id/);
});

test('client setup runbook names the registered read-only tool surface', () => {
  const text = readRunbook();
  assert.match(text, /provider_status/);
  assert.match(text, /data_sources/);
  assert.match(text, /credential_profiles/);
  assert.match(text, /\bsearch\b/);
  assert.match(text, /\bfetch\b/);
  assert.match(text, /readOnlyHint/);
  assert.match(text, /read-only/i);
});

test('client setup runbook keeps the no-secret, no-bypass posture', () => {
  const text = readRunbook();
  assert.match(text, /Never paste secrets into chat/i);
  assert.match(
    text,
    /Default verification.*fixture/i,
    'must state that default verification stays fixture-only',
  );
  // stdout is the MCP stream — no log writes there.
  assert.match(text, /stdout is the MCP protocol stream/i);
});

test('client setup runbook separates local protocol proof from third-party client acceptance', () => {
  const text = readRunbook();

  assert.match(text, /## Verification matrix and claim boundary/i);
  assert.match(text, /test\/mcp-stdio\.test\.js/);
  assert.match(text, /test\/mcp-http\.test\.js/);
  assert.match(text, /test\/client-setup\.test\.js/);
  assert.match(text, /does not claim that\s+an arbitrary user's authenticated/i);
  assert.match(text, /operator-owned,\s*HTTPS-protected `\/mcp` endpoint/i);
});

test('client setup runbook does not leak credential-shaped strings', () => {
  const text = readRunbook();
  assert.doesNotMatch(text, /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, 'no JWTs');
  assert.doesNotMatch(text, /\b(AKIA|ASIA)[A-Z0-9]{16}\b/, 'no AWS access key IDs');
  assert.doesNotMatch(text, /\bghp_[A-Za-z0-9]{20,}\b/, 'no GitHub PATs');
  assert.doesNotMatch(text, /\bsk-[A-Za-z0-9]{20,}\b/, 'no sk- secrets');
});

test('client setup runbook references the package binary target', () => {
  const text = readRunbook();
  const pkg = JSON.parse(readFileSync(PACKAGE_URL, 'utf8'));
  const binaryTarget = pkg.bin['vessel-traffic-mcp'];
  assert.equal(binaryTarget, 'dist/index.js');
  // The runbook should point clients at this same binary path.
  assert.ok(text.includes('dist/index.js'), 'runbook must point at the dist/index.js binary');
});

test('README links the client setup runbook so MCP clients can find it', () => {
  const readme = readFileSync(README_URL, 'utf8');
  assert.match(readme, /docs\/runbooks\/clients\.md/, 'README must link the client setup runbook');
});

test('client setup runbook JSON config snippets are valid mcpServers entries', () => {
  const text = readRunbook();
  const jsonBlocks = extractFencedBlocks(text, 'json');
  assert.ok(jsonBlocks.length >= 2, 'runbook should include at least two JSON config snippets');

  const mcpServerBlocks = jsonBlocks.filter((block) => block.includes('mcpServers'));
  assert.ok(
    mcpServerBlocks.length >= 2,
    'runbook should include Claude Desktop and Claude Code mcpServers JSON snippets',
  );

  for (const block of mcpServerBlocks) {
    const parsed = JSON.parse(block);
    assert.ok(parsed && typeof parsed === 'object', 'JSON snippet must parse to an object');
    assert.ok(parsed.mcpServers, 'snippet must define mcpServers');
    const entry = parsed.mcpServers['vessel-traffic-mcp'];
    assert.ok(entry, 'snippet must register vessel-traffic-mcp under mcpServers');
    assert.equal(entry.command, 'node');
    assert.ok(Array.isArray(entry.args), 'args must be an array');
    assert.ok(
      entry.args.some((a) => typeof a === 'string' && a.endsWith('dist/index.js')),
      'args must point at dist/index.js',
    );
    assert.ok(entry.env, 'env block must exist so VESSEL_MCP_TRANSPORT can be set');
    assert.equal(entry.env.VESSEL_MCP_TRANSPORT, 'stdio');
  }
});

test('client setup runbook references existing runbook files (no broken links)', () => {
  const text = readRunbook();
  const targets = extractRelativeMarkdownLinks(text);
  assert.ok(
    targets.includes('./stdio-fixture-server.md'),
    'must reference stdio-fixture-server.md',
  );
  assert.ok(
    targets.includes('./streamable-http-server.md'),
    'must reference streamable-http-server.md',
  );
  for (const target of targets) {
    const resolved = resolve(RUNBOOK_DIR, target);
    assert.ok(existsSync(resolved), `referenced runbook file must exist: ${target}`);
  }
});

test('client setup runbook documents the MCP Inspector for both transports', () => {
  const text = readRunbook();
  // stdio inspector usage
  assert.match(text, /npx\s+@modelcontextprotocol\/inspector\s+node\s+dist\/index\.js/);
  // streamable-http inspector usage
  assert.match(text, /--transport\s+streamable-http/);
  assert.match(text, /--server-url\s+"http:\/\/127\.0\.0\.1:\d+\/mcp"/);
  assert.match(text, /--header\s+"Authorization: Bearer \$VESSEL_MCP_AUTH_TOKEN"/);
});

test('client setup runbook enumerates the full registered read-only tool surface', () => {
  const text = readRunbook();
  const serverSource = readFileSync(CREATE_SERVER_URL, 'utf8');
  const registerCalls = [...serverSource.matchAll(/server\.registerTool\(\s*'([^']+)'/g)];
  const registeredTools = registerCalls.map((m) => m[1]);
  assert.ok(registeredTools.length >= 3, 'create-server.ts must register at least the F1 tool set');

  for (const tool of registeredTools) {
    assert.match(
      text,
      new RegExp(`\\b${tool}\\b`),
      `runbook must mention registered tool ${tool} so MCP clients see the full surface`,
    );
  }
});

const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('client setup runbook documents the Claude-oriented installation metadata state', () => {
  // PRD §8.1 asks for Claude-oriented installation metadata when a stable
  // Claude MCP/plugin registry path exists, and otherwise keeping documented
  // local/remote MCP setup as the canonical integration. The clients runbook
  // is the F1.AC3 owner and is the natural home for the forward-looking
  // Claude scaffold paralleling the Codex one in `codex.md`.
  const text = readRunbook();
  assert.match(
    text,
    /## Claude plugin manifest \/ installation metadata/i,
    'clients runbook must contain a Claude plugin manifest / installation metadata section',
  );
  // The section must dated-document the manifest readiness state — either
  // a real published manifest or a concrete dated blocker. We accept both
  // forms as long as the state is concrete.
  assert.match(
    text,
    /blocker.*2026|2026.*blocker|when ready|not yet (?:finalized|published)|schema not yet finalized/i,
    'clients runbook must dated-document the Claude manifest readiness state',
  );
  // The forward-looking scaffold must surface the read-only and BYOK
  // contract so a future manifest can be promoted without breaking the
  // security model.
  assert.match(text, /readOnly/i, 'manifest sketch must surface the read-only contract');
  assert.match(text, /VESSEL_MCP_PROFILE_/, 'manifest sketch must surface the BYOK env-var prefix');
});

test('client setup runbook Claude plugin manifest scaffold parses as JSONC and carries the release-checklist invariants', () => {
  const text = readRunbook();
  const jsoncBlocks = extractFencedBlocks(text, 'jsonc');
  assert.ok(
    jsoncBlocks.length >= 1,
    'clients runbook must include at least one jsonc manifest scaffold block',
  );

  // The forward-looking Claude plugin manifest sketch must be structurally
  // valid JSON after stripping `// ...` line comments. Any sketch that drifts
  // out of parseable shape would mislead future agents promoting it into a
  // real manifest.
  const stripLineComments = (block) => block.replace(/^\s*\/\/.*$/gm, '');
  const manifest = jsoncBlocks
    .map((block) => {
      try {
        return JSON.parse(stripLineComments(block));
      } catch {
        return null;
      }
    })
    .find(
      (parsed) =>
        parsed &&
        typeof parsed === 'object' &&
        parsed.name === '@tools-mcp/vessel-traffic-mcp' &&
        parsed.entrypoint,
    );
  assert.ok(
    manifest,
    'clients runbook must include a jsonc sketch that parses with name="@tools-mcp/vessel-traffic-mcp" and an entrypoint',
  );

  // Lock the security/contract invariants that release-checklist.md (F7.AC1)
  // requires before promoting the scaffold into a published manifest.
  assert.equal(manifest.readOnly, true, 'manifest scaffold must declare readOnly: true');
  assert.equal(
    manifest.notForNavigation,
    true,
    'manifest scaffold must declare notForNavigation: true',
  );
  assert.equal(manifest.license, 'MIT', 'manifest scaffold license must be MIT');

  // Entrypoint must match the package.json bin target and the stdio contract.
  assert.equal(manifest.entrypoint.command, 'node');
  assert.ok(
    Array.isArray(manifest.entrypoint.args) &&
      manifest.entrypoint.args.some((a) => typeof a === 'string' && a.endsWith('dist/index.js')),
    'manifest scaffold entrypoint args must point at dist/index.js',
  );
  assert.equal(
    manifest.transport,
    'stdio',
    'manifest scaffold transport must default to stdio (Streamable HTTP wiring is documented separately)',
  );

  // Env block must use the same env-var contract as the Claude Desktop /
  // Claude Code JSON wirings above, and must contain only env-var *names* —
  // no real credential values.
  assert.ok(manifest.env && typeof manifest.env === 'object', 'manifest scaffold must define env block');
  assert.equal(manifest.env.VESSEL_MCP_TRANSPORT, 'stdio');
  for (const [name, value] of Object.entries(manifest.env)) {
    assert.equal(typeof value, 'string', `env.${name} must be a string`);
    for (const { name: shape, re } of CREDENTIAL_PATTERNS) {
      assert.doesNotMatch(value, re, `manifest scaffold env.${name} must not contain a ${shape}-shaped value`);
    }
  }

  // BYOK contract — operators are pointed at env-var prefix + redacted policy,
  // matching the credential-profiles env-var contract.
  assert.ok(manifest.byok && typeof manifest.byok === 'object', 'manifest scaffold must define byok block');
  assert.equal(
    manifest.byok.envVarPrefix,
    'VESSEL_MCP_PROFILE_',
    'manifest scaffold byok.envVarPrefix must match the credential-profiles env-var contract',
  );
  assert.match(
    String(manifest.byok.credentialPolicy ?? ''),
    /redacted/i,
    'manifest scaffold byok.credentialPolicy must mention redaction',
  );

  // Homepage and repository should point at the same GitHub project that
  // package.json declares — protects against the sketch drifting away from
  // the canonical project URL.
  const pkg = JSON.parse(readFileSync(PACKAGE_URL, 'utf8'));
  if (manifest.homepage) {
    assert.match(
      manifest.homepage,
      /^https:\/\/github\.com\/[^/]+\/vessel-traffic-mcp(#[^\s]*)?$/,
      'manifest scaffold homepage must point at the canonical vessel-traffic-mcp GitHub URL',
    );
  }
  if (manifest.repository) {
    assert.match(
      manifest.repository,
      /github\.com\/[^/]+\/vessel-traffic-mcp/,
      'manifest scaffold repository must point at the canonical vessel-traffic-mcp GitHub URL',
    );
  }
  assert.equal(manifest.name, pkg.name, 'manifest scaffold name must match package.json name');
});

test('client setup runbook Claude manifest scaffold mirrors the Codex scaffold invariants', () => {
  // Both scaffolds must share the same security/contract invariants so a
  // future edit to one cannot silently weaken the other. Spot-check that the
  // load-bearing keys appear in both runbooks.
  const clients = readRunbook();
  const codex = readFileSync(new URL('../docs/runbooks/codex.md', import.meta.url), 'utf8');
  for (const phrase of [
    '"readOnly": true',
    '"notForNavigation": true',
    '"license": "MIT"',
    '"envVarPrefix": "VESSEL_MCP_PROFILE_"',
    '"credentialPolicy": "redacted-labels-only"',
    '"VESSEL_MCP_TRANSPORT": "stdio"',
  ]) {
    assert.ok(
      clients.includes(phrase),
      `clients runbook Claude scaffold must include shared invariant phrase: ${phrase}`,
    );
    assert.ok(
      codex.includes(phrase),
      `codex runbook scaffold must include shared invariant phrase: ${phrase}`,
    );
  }
});

test('F1.AC3 status in requirements.yaml is set to implemented for this acceptance criterion', () => {
  const reqs = readFileSync(REQUIREMENTS_URL, 'utf8');
  const f1Index = reqs.indexOf('id: F1');
  assert.ok(f1Index > 0, 'requirements.yaml must contain feature F1');
  const f2Index = reqs.indexOf('id: F2', f1Index);
  const f1Block = reqs.slice(f1Index, f2Index > 0 ? f2Index : undefined);

  const ac3Index = f1Block.indexOf('id: AC3');
  assert.ok(ac3Index > 0, 'F1 must contain acceptance criterion AC3');
  const ac3Block = f1Block.slice(ac3Index, ac3Index + 400);
  assert.match(ac3Block, /client setup documentation/i, 'AC3 description must match the client-setup criterion');
  assert.match(ac3Block, /status: implemented/, 'F1.AC3 status must be flipped to implemented');
  assert.match(ac3Block, /verification: docs-review/, 'F1.AC3 verification must remain docs-review');
});
