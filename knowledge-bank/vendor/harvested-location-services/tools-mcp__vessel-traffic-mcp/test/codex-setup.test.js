import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const CODEX_URL = new URL('../docs/runbooks/codex.md', import.meta.url);
const CODEX_DIR = dirname(fileURLToPath(CODEX_URL));
const CLIENTS_URL = new URL('../docs/runbooks/clients.md', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const DISCOVERABILITY_URL = new URL('../docs/discoverability.md', import.meta.url);
const CHECKLIST_URL = new URL('../docs/runbooks/release-checklist.md', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const PACKAGE_URL = new URL('../package.json', import.meta.url);
const CREATE_SERVER_URL = new URL('../src/server/create-server.ts', import.meta.url);

function read(url) {
  return readFileSync(url, 'utf8');
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
  const linkPattern = /\]\((\.{1,2}\/[^)\s]+\.md)\)/g;
  const targets = new Set();
  let match;
  while ((match = linkPattern.exec(markdown)) !== null) {
    targets.add(match[1]);
  }
  return [...targets];
}

const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('codex runbook exists and self-identifies against F7.AC3', () => {
  const text = read(CODEX_URL);
  assert.match(text, /^# /m, 'codex runbook must have a top-level heading');
  assert.match(text, /F7\.AC3/, 'codex runbook must self-identify against the acceptance criterion');
});

test('codex runbook covers the Codex CLI TOML wiring', () => {
  const text = read(CODEX_URL);
  assert.match(text, /## Codex CLI/i, 'codex runbook must include a Codex CLI section');
  assert.match(
    text,
    /~\/\.codex\/config\.toml/,
    'codex runbook must reference the ~/.codex/config.toml file',
  );
  assert.match(
    text,
    /\[mcp_servers\.vessel-traffic-mcp\]/,
    'codex runbook must include the mcp_servers TOML table for vessel-traffic-mcp',
  );
  assert.match(text, /VESSEL_MCP_TRANSPORT\s*=\s*"stdio"/);
});

test('codex runbook documents the stdio transport contract', () => {
  const text = read(CODEX_URL);
  assert.match(text, /VESSEL_MCP_TRANSPORT/);
  assert.match(text, /dist\/index\.js/);
  assert.match(text, /Node\.js 22/);
});

test('codex runbook documents the Streamable HTTP transport contract', () => {
  const text = read(CODEX_URL);
  assert.match(text, /VESSEL_MCP_TRANSPORT=http/);
  assert.match(text, /VESSEL_MCP_HTTP_HOST/);
  assert.match(text, /VESSEL_MCP_HTTP_PORT/);
  assert.match(text, /VESSEL_MCP_AUTH_TOKEN/);
  assert.match(text, /Authorization: Bearer/);
  assert.match(text, /GET \/health/);
  assert.match(text, /POST \/mcp/);
  assert.match(text, /X-Request-Id/);
});

test('codex runbook documents the plugin manifest / marketplace state', () => {
  const text = read(CODEX_URL);
  assert.match(
    text,
    /## Codex plugin manifest \/ marketplace metadata/i,
    'codex runbook must contain a plugin manifest / marketplace section',
  );
  // Either a real published manifest or a dated blocker. We accept both
  // forms as long as the state is concrete.
  assert.match(
    text,
    /blocker.*2026|2026.*blocker|when ready|not yet (?:finalized|published)/i,
    'codex runbook must dated-document the manifest readiness state',
  );
  // The forward-looking scaffold must surface the read-only and BYOK contract
  // so a future manifest can be promoted without breaking the security model.
  assert.match(text, /readOnly/i, 'manifest sketch must surface the read-only contract');
  assert.match(text, /VESSEL_MCP_PROFILE_/, 'manifest sketch must surface the BYOK env-var prefix');
});

test('codex runbook keeps the no-secret, no-bypass posture', () => {
  const text = read(CODEX_URL);
  assert.match(text, /Never paste secrets into chat/i);
  assert.match(
    text,
    /Default verification[\s\S]{0,80}?fixture/i,
    'codex runbook must state that default verification stays fixture-only',
  );
  assert.match(text, /stdout is the MCP protocol stream/i);
});

test('codex runbook names the registered read-only tool surface', () => {
  const text = read(CODEX_URL);
  const serverSource = read(CREATE_SERVER_URL);
  const registerCalls = [...serverSource.matchAll(/server\.registerTool\(\s*'([^']+)'/g)];
  const registeredTools = registerCalls.map((m) => m[1]);
  assert.ok(
    registeredTools.length >= 3,
    'create-server.ts must register at least the F1 tool set',
  );
  for (const tool of registeredTools) {
    assert.match(
      text,
      new RegExp(`\\b${tool}\\b`),
      `codex runbook must mention registered tool ${tool}`,
    );
  }
  assert.match(text, /read-only/i);
  assert.match(text, /readOnlyHint/);
});

test('codex runbook does not leak credential-shaped strings', () => {
  const text = read(CODEX_URL);
  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(text, re, `codex runbook must not contain a ${name}-shaped string`);
  }
  assert.doesNotMatch(
    text,
    /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
    'codex runbook must not contain a real Authorization: Bearer header',
  );
});

test('codex runbook references the package binary target', () => {
  const text = read(CODEX_URL);
  const pkg = JSON.parse(read(PACKAGE_URL));
  const binaryTarget = pkg.bin['vessel-traffic-mcp'];
  assert.equal(binaryTarget, 'dist/index.js');
  assert.ok(
    text.includes('dist/index.js'),
    'codex runbook must point at the dist/index.js binary',
  );
});

test('codex runbook TOML snippets parse as valid TOML-shaped mcp_servers entries', () => {
  const text = read(CODEX_URL);
  const tomlBlocks = extractFencedBlocks(text, 'toml');
  assert.ok(
    tomlBlocks.length >= 1,
    'codex runbook should include at least one TOML config snippet',
  );

  // At least one TOML block must declare the full Codex MCP server entry:
  // the [mcp_servers.vessel-traffic-mcp] table, the command/args pointing
  // at the built binary, and the VESSEL_MCP_TRANSPORT="stdio" env line.
  const fullEntry = tomlBlocks.find(
    (block) =>
      /\[mcp_servers\.vessel-traffic-mcp\]/.test(block) &&
      /command\s*=\s*"node"/.test(block) &&
      /args\s*=\s*\[[^\]]*dist\/index\.js[^\]]*\]/.test(block) &&
      /VESSEL_MCP_TRANSPORT\s*=\s*"stdio"/.test(block),
  );
  assert.ok(
    fullEntry,
    'codex runbook must include a TOML block with the [mcp_servers.vessel-traffic-mcp] table, command="node", args containing dist/index.js, and VESSEL_MCP_TRANSPORT="stdio"',
  );

  // Stdio TOML blocks that mention the vessel-traffic-mcp server (including
  // any standalone env-table example) must set VESSEL_MCP_TRANSPORT="stdio"
  // and must not declare a different command than "node". URL-only remote
  // MCP blocks are allowed because current Codex can register remote servers
  // directly with a `url` field.
  const wired = tomlBlocks.filter((b) => b.includes('mcp_servers.vessel-traffic-mcp'));
  assert.ok(
    wired.some((block) => /url\s*=\s*"https:\/\/<your-public-host>\/mcp"/.test(block)),
    'codex runbook must include a URL-based remote MCP TOML block',
  );
  for (const block of wired) {
    if (/url\s*=/.test(block) && !/command\s*=/.test(block)) {
      assert.doesNotMatch(block, /VESSEL_MCP_AUTH_TOKEN|Authorization:\s*Bearer/i);
      continue;
    }
    assert.match(
      block,
      /VESSEL_MCP_TRANSPORT\s*=\s*"stdio"/,
      'every vessel-traffic-mcp TOML block must set VESSEL_MCP_TRANSPORT="stdio"',
    );
    const otherCommand = /command\s*=\s*"(?!node")[^"]+"/.exec(block);
    assert.ok(
      otherCommand === null,
      `vessel-traffic-mcp TOML blocks must use command = "node"; saw ${otherCommand?.[0]}`,
    );
  }
});

test('codex runbook plugin manifest scaffold parses as JSONC and carries the release-checklist invariants', () => {
  const text = read(CODEX_URL);
  const jsoncBlocks = extractFencedBlocks(text, 'jsonc');
  assert.ok(
    jsoncBlocks.length >= 1,
    'codex runbook must include at least one jsonc manifest scaffold block',
  );

  // The forward-looking Codex plugin manifest sketch must be structurally
  // valid JSON after stripping `// ...` line comments. Any sketch that drifts
  // out of parseable shape would mislead future agents promoting the
  // scaffold into a real manifest.
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
    'codex runbook must include a jsonc sketch that parses with name="@tools-mcp/vessel-traffic-mcp" and an entrypoint',
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

  // Env block must use the same env-var contract as the TOML/JSON wirings,
  // and must contain only env-var *names* — no real credential values.
  assert.ok(manifest.env && typeof manifest.env === 'object', 'manifest scaffold must define env block');
  assert.equal(manifest.env.VESSEL_MCP_TRANSPORT, 'stdio');
  for (const [name, value] of Object.entries(manifest.env)) {
    assert.equal(typeof value, 'string', `env.${name} must be a string`);
    // Sentinel values only. No JWTs, AWS keys, GitHub PATs, or sk- secrets.
    for (const { name: shape, re } of CREDENTIAL_PATTERNS) {
      assert.doesNotMatch(value, re, `manifest scaffold env.${name} must not contain a ${shape}-shaped value`);
    }
  }

  // BYOK contract — operators are pointed at env-var prefix + redacted policy.
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
  const pkg = JSON.parse(read(PACKAGE_URL));
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

test('codex runbook surfaces every F7.AC3 client name', () => {
  // F7.AC3 explicitly enumerates five client surfaces. The codex runbook is
  // the F7.AC3 owner and must reference each one — either as its own section
  // (Codex) or as a cross-link delegating to F1.AC3 (the other four). This
  // guards against a future edit silently dropping one of the contracted
  // surfaces from the AC3 coverage map.
  const text = read(CODEX_URL);
  for (const surface of [
    'Claude Desktop',
    'Claude Code',
    'ChatGPT remote MCP',
    'MCP Inspector',
    'Codex',
  ]) {
    assert.ok(
      text.includes(surface),
      `codex runbook must reference F7.AC3 client surface "${surface}"`,
    );
  }
});

test('codex runbook documents the MCP Inspector for both transports', () => {
  const text = read(CODEX_URL);
  // Inspector against stdio — must invoke the built binary directly.
  assert.match(
    text,
    /npx\s+@modelcontextprotocol\/inspector\s+node\s+dist\/index\.js/,
    'codex runbook must include an MCP Inspector stdio command',
  );
  // Inspector against Streamable HTTP — must use --transport streamable-http
  // and pass the bearer token via --header so operators inherit the same
  // bearer-auth contract documented for the HTTP transport.
  assert.match(
    text,
    /--transport\s+streamable-http/,
    'codex runbook must include an MCP Inspector streamable-http command',
  );
  assert.match(
    text,
    /--server-url\s+"http:\/\/127\.0\.0\.1:\d+\/mcp"/,
    'codex runbook MCP Inspector HTTP form must point at 127.0.0.1:<port>/mcp',
  );
  assert.match(
    text,
    /--header\s+"Authorization: Bearer \$VESSEL_MCP_AUTH_TOKEN"/,
    'codex runbook MCP Inspector HTTP form must pass the bearer token via --header',
  );
});

test('codex runbook references existing runbook files (no broken links)', () => {
  const text = read(CODEX_URL);
  const targets = extractRelativeMarkdownLinks(text);
  assert.ok(
    targets.includes('./clients.md'),
    'codex runbook must cross-link clients.md (F1.AC3) to avoid documentation drift',
  );
  assert.ok(
    targets.includes('./stdio-fixture-server.md'),
    'codex runbook must reference stdio-fixture-server.md',
  );
  assert.ok(
    targets.includes('./streamable-http-server.md'),
    'codex runbook must reference streamable-http-server.md',
  );
  assert.ok(
    targets.includes('./deployment-https.md'),
    'codex runbook must reference deployment-https.md',
  );
  for (const target of targets) {
    const resolved = resolve(CODEX_DIR, target);
    assert.ok(existsSync(resolved), `referenced runbook file must exist: ${target}`);
  }
});

test('codex runbook stays consistent with the F1.AC3 clients runbook', () => {
  const codex = read(CODEX_URL);
  const clients = read(CLIENTS_URL);
  // The two docs share the same read-only / BYOK / stdout contract. If one
  // doc adopts a new rule, the other should too. Spot-check the load-bearing
  // language so a future edit to one runbook cannot silently drift the other.
  for (const phrase of [
    'Never paste secrets into chat',
    'stdout is the MCP protocol stream',
    'VESSEL_MCP_TRANSPORT=http',
    'X-Request-Id',
  ]) {
    assert.ok(
      codex.includes(phrase),
      `codex runbook must include shared contract phrase: "${phrase}"`,
    );
    assert.ok(
      clients.includes(phrase),
      `clients runbook must include shared contract phrase: "${phrase}"`,
    );
  }
});

test('README links the codex runbook so Codex operators can find it', () => {
  const readme = read(README_URL);
  assert.match(
    readme,
    /docs\/runbooks\/codex\.md/,
    'README must link the Codex setup runbook',
  );
});

test('discoverability doc cross-links the codex runbook', () => {
  const text = read(DISCOVERABILITY_URL);
  assert.match(
    text,
    /docs\/runbooks\/codex\.md|runbooks\/codex\.md|\.\/runbooks\/codex\.md/,
    'discoverability doc must link the codex runbook',
  );
});

test('release checklist verifies the codex runbook is current', () => {
  const text = read(CHECKLIST_URL);
  assert.match(
    text,
    /codex\.md|Codex setup|F7\.AC3/i,
    'release checklist must remind operators to verify the Codex setup/distribution docs',
  );
});

test('F7.AC3 status in requirements.yaml is set to implemented', () => {
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  const f7Block = reqs.slice(f7Index);

  const ac3Index = f7Block.indexOf('id: AC3');
  assert.ok(ac3Index > 0, 'F7 must contain acceptance criterion AC3');
  const ac3Block = f7Block.slice(ac3Index, ac3Index + 500);

  assert.match(
    ac3Block,
    /Claude Desktop[\s\S]*?ChatGPT remote MCP[\s\S]*?Codex/i,
    'F7.AC3 description must match the client + codex setup criterion',
  );
  assert.match(ac3Block, /status: implemented/, 'F7.AC3 status must be flipped to implemented');
  assert.match(ac3Block, /verification: docs-review/, 'F7.AC3 verification must remain docs-review');
});

test('F7 parent feature is implemented after PRD completion', () => {
  // F7.AC1, F7.AC2, and F7.AC3 are now implemented, so the parent feature is
  // promoted during the PRD completion pass.
  const reqs = read(REQUIREMENTS_URL);
  const f7Index = reqs.indexOf('id: F7');
  assert.ok(f7Index > 0, 'requirements.yaml must contain feature F7');
  const f7Header = reqs.slice(f7Index, f7Index + 400);
  assert.match(
    f7Header,
    /title: Open source release and plugin discoverability[\s\S]*?status: implemented/,
    'F7 parent feature must be implemented after all child criteria are done',
  );
});
