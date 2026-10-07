import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { loadRuntimeConfig } from '../dist/config/runtime.js';

const DOCKERFILE_URL = new URL('../Dockerfile', import.meta.url);
const DOCKERIGNORE_URL = new URL('../.dockerignore', import.meta.url);
const RUNBOOK_URL = new URL('../docs/runbooks/deployment-https.md', import.meta.url);
const HTTP_RUNBOOK_URL = new URL('../docs/runbooks/streamable-http-server.md', import.meta.url);
const README_URL = new URL('../README.md', import.meta.url);
const REQUIREMENTS_URL = new URL('../docs/autodev/requirements.yaml', import.meta.url);
const GITIGNORE_URL = new URL('../.gitignore', import.meta.url);

function read(url) {
  return readFileSync(url, 'utf8');
}

// Credential-shape patterns we reuse from the operator-runbook test so
// the new deployment assets cannot embed real secrets.
const CREDENTIAL_PATTERNS = [
  { name: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/ },
  { name: 'AWS access key ID', re: /\b(AKIA|ASIA)[A-Z0-9]{16}\b/ },
  { name: 'GitHub PAT', re: /\bghp_[A-Za-z0-9]{20,}\b/ },
  { name: 'sk- secret', re: /\bsk-[A-Za-z0-9]{20,}\b/ },
];

test('Dockerfile is a multi-stage build on Node 22 that runs as non-root', () => {
  const text = read(DOCKERFILE_URL);

  // Two named stages: build + runtime.
  assert.match(text, /FROM\s+node:22[^\s]*\s+AS\s+build/i, 'must declare a build stage on node:22');
  assert.match(text, /FROM\s+node:22[^\s]*\s+AS\s+runtime/i, 'must declare a runtime stage on node:22');

  // Reproducible install + TypeScript build.
  assert.match(text, /npm ci/, 'must use npm ci for reproducible installs');
  assert.match(text, /npm run build/, 'must run the project build script');
  assert.match(text, /npm prune --omit=dev/, 'must drop dev deps before the runtime stage');

  // Runs as the unprivileged "node" user.
  assert.match(text, /^USER node\s*$/m, 'runtime stage must drop to the unprivileged node user');

  // HTTP transport defaults and port exposure.
  assert.match(text, /VESSEL_MCP_TRANSPORT=http/);
  assert.match(text, /VESSEL_MCP_HTTP_HOST=0\.0\.0\.0/);
  assert.match(text, /VESSEL_MCP_HTTP_PORT=3000/);
  assert.match(text, /^EXPOSE\s+3000\s*$/m);

  // Healthcheck against the public /health endpoint.
  assert.match(text, /HEALTHCHECK[\s\S]*\/health/);

  // Entrypoint launches the compiled server.
  assert.match(text, /ENTRYPOINT \[\s*"node"[\s\S]*"dist\/index\.js"\s*\]/);
});

test('Dockerfile never copies secret, capture, or local credential surfaces', () => {
  const text = read(DOCKERFILE_URL);

  // Reject COPY directives that bring in any of these paths. The
  // .dockerignore enforces the same boundary, but a literal COPY of
  // these names would still try to pull them in if they existed in
  // the build context, so block them at the Dockerfile level too.
  const forbiddenCopyTargets = [
    /COPY[^\n]*\.env(\s|$|\*)/i,
    /COPY[^\n]*credential-profiles\.local\.json/i,
    /COPY[^\n]*credential-profiles\.[^\s]*\.local\.json/i,
    /COPY[^\n]*captures\/raw/i,
    /COPY[^\n]*captures\/private/i,
    /COPY[^\n]*\.har/i,
  ];
  for (const re of forbiddenCopyTargets) {
    assert.doesNotMatch(text, re, `Dockerfile must not COPY ${re}`);
  }

  // No baked-in secrets, BYOK keys, or bearer tokens.
  assert.doesNotMatch(text, /VESSEL_MCP_AUTH_TOKEN=[^\s\\]+/, 'must not bake a bearer token into the image');
  assert.doesNotMatch(text, /VESSEL_MCP_PROFILE_[A-Z0-9_]+=[^\s\\]+/, 'must not bake BYOK env values into the image');
  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(text, re, `Dockerfile must not embed a ${name}-shaped string`);
  }
});

test('.dockerignore excludes secrets, captures, logs, and local credential overlays', () => {
  const text = read(DOCKERIGNORE_URL);
  const lines = text.split(/\r?\n/);

  const required = [
    '.git',
    'node_modules',
    'dist',
    '.env',
    '.env.*',
    'config/credential-profiles.local.json',
    'config/credential-profiles.*.local.json',
    '*.log',
    '*.har',
    'captures/raw',
    'captures/private',
    'fixtures/captures/raw',
    'fixtures/captures/*.private.json',
    'state',
    'test',
  ];
  for (const rule of required) {
    assert.ok(
      lines.includes(rule),
      `.dockerignore must contain line: ${rule}`,
    );
  }

  // The .env.example template stays available so the image can still
  // reference the documented env-var shape if needed.
  assert.ok(lines.includes('!.env.example'), '.dockerignore must keep .env.example unignored');
});

test('gitignore and dockerignore both block the same secret/capture surfaces', () => {
  const dockerignore = read(DOCKERIGNORE_URL);
  const gitignore = read(GITIGNORE_URL);

  // Each rule below is one the operator runbook tells the operator to
  // verify. Both ignore files must list it so neither `git add` nor
  // `docker build` can stage it.
  const sharedRules = [
    '.env',
    '.env.*',
    '*.log',
    '*.har',
    'config/credential-profiles.local.json',
    'config/credential-profiles.*.local.json',
  ];
  for (const rule of sharedRules) {
    assert.ok(
      gitignore.split(/\r?\n/).includes(rule),
      `.gitignore must contain shared rule: ${rule}`,
    );
    assert.ok(
      dockerignore.split(/\r?\n/).includes(rule),
      `.dockerignore must contain shared rule: ${rule}`,
    );
  }
});

test('deployment-https runbook covers the HTTPS contract, bearer token, and a concrete topology', () => {
  const text = read(RUNBOOK_URL);

  // Self-identifies against F6.AC2.
  assert.match(text, /F6\.AC2/, 'runbook should self-identify against the acceptance criterion');

  // HTTPS is mandatory and TLS terminates outside the container.
  assert.match(text, /HTTPS/, 'must explicitly require HTTPS');
  assert.match(text, /terminat(es|e|ed).*TLS|TLS\s+(is\s+)?terminated/i);
  assert.match(text, /reverse proxy|load balancer|platform edge/i);

  // Bearer token contract.
  assert.match(text, /VESSEL_MCP_AUTH_TOKEN/);
  assert.match(text, /Authorization: Bearer/);
  // /health stays public, /mcp is bearer-gated.
  assert.match(text, /\/health/);
  assert.match(text, /\/mcp/);
  assert.match(text, /\/\.well-known\/mcp\/server-card\.json/);

  // At least one concrete reverse-proxy or managed-platform topology.
  assert.match(
    text,
    /nginx|Caddy|Cloud Run|App Runner|Fly\.io|Render/i,
    'must document at least one HTTPS termination topology',
  );

  // Read-only and no-paid-defaults invariants are restated.
  assert.match(text, /read-only/i);
  assert.match(text, /Default verification[\s\S]{0,120}?not.*(call|use|invoke).*(paid|live)/i);

  // Container hygiene: non-root user and image hardening notes.
  assert.match(text, /\bnode\b[^\n]*user|unprivileged|non-root/i);

  // Default verification is npm run build (the brief's expected
  // verification mode), and docker build is operator-only.
  assert.match(text, /npm run build/);
  assert.match(text, /docker build[\s\S]{0,200}?(operator-only|not\s+(part\s+of\s+)?default CI|not.*in.*CI)/i);
});

test('deployment runbook distinguishes local HTTP capability from a public hosted endpoint', () => {
  const text = read(RUNBOOK_URL);

  assert.match(text, /##\s+Current distribution decision/i);
  assert.match(text, /do not operate a shared public HTTPS\s+`?\/mcp`? endpoint/i);
  assert.match(text, /operator-owned deployment/i);
  assert.match(text, /local stdio is the supported[\s\S]*?installation path for ordinary users/i);
});

test('deployment runbook does not embed credential-shaped strings', () => {
  const text = read(RUNBOOK_URL);
  for (const { name, re } of CREDENTIAL_PATTERNS) {
    assert.doesNotMatch(text, re, `deployment runbook must not contain a ${name}-shaped string`);
  }
  // No literal "Authorization: Bearer <real-looking-token>" with 20+
  // chars of token material. Placeholders such as
  // "Authorization: Bearer <token>" remain allowed.
  assert.doesNotMatch(
    text,
    /Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}/,
    'must not embed a real Authorization: Bearer header',
  );
});

test('README cross-links the deployment-https runbook', () => {
  const text = read(README_URL);
  assert.match(text, /docs\/runbooks\/deployment-https\.md/, 'README must link the deployment-https runbook');
});

test('Streamable HTTP runbook keeps pointing operators at the HTTPS deployment doc', () => {
  // The HTTP runbook already says "terminate TLS at a reverse proxy".
  // Closing F6.AC2 wires that note through to the new deployment doc
  // so operators do not have to grep for it.
  const text = read(HTTP_RUNBOOK_URL);
  assert.match(text, /deployment-https\.md/, 'streamable-http-server runbook must link the deployment-https runbook');
});

test('F6.AC2 status in requirements.yaml is set to implemented with the build verification mode', () => {
  const reqs = read(REQUIREMENTS_URL);

  const f6Index = reqs.indexOf('id: F6');
  assert.ok(f6Index > 0, 'requirements.yaml must contain feature F6');
  const f7Index = reqs.indexOf('id: F7', f6Index);
  const f6Block = reqs.slice(f6Index, f7Index > 0 ? f7Index : undefined);

  const ac2Index = f6Block.indexOf('id: AC2');
  assert.ok(ac2Index > 0, 'F6 must contain acceptance criterion AC2');
  const ac2Block = f6Block.slice(ac2Index, ac2Index + 400);

  assert.match(
    ac2Block,
    /Dockerfile|deployment notes/i,
    'F6.AC2 description must match the deployment criterion',
  );
  assert.match(ac2Block, /status: implemented/, 'F6.AC2 status must be flipped to implemented');
  assert.match(ac2Block, /verification: npm run build/, 'F6.AC2 verification must remain npm run build');
});

test('Dockerfile env defaults parse into a runtime config that boots HTTP on the EXPOSEd port', () => {
  // Drift guard: if someone changes VESSEL_MCP_HTTP_PORT default in
  // runtime.ts (e.g. 3000 -> 8080) without updating the Dockerfile
  // EXPOSE/ENV defaults, the container would bind a different port
  // than the platform health probe and reverse proxy expect.
  const dockerfile = read(DOCKERFILE_URL);

  const envMatch = (re) => {
    const m = dockerfile.match(re);
    assert.ok(m, `Dockerfile must declare ${re}`);
    return m[1];
  };

  const transport = envMatch(/VESSEL_MCP_TRANSPORT=([^\s\\]+)/);
  const host = envMatch(/VESSEL_MCP_HTTP_HOST=([^\s\\]+)/);
  const port = envMatch(/VESSEL_MCP_HTTP_PORT=([^\s\\]+)/);

  const exposeMatch = dockerfile.match(/^EXPOSE\s+(\d+)\s*$/m);
  assert.ok(exposeMatch, 'Dockerfile must EXPOSE a numeric port');
  assert.equal(
    exposeMatch[1],
    port,
    'Dockerfile EXPOSE port must match VESSEL_MCP_HTTP_PORT default so the platform probe and reverse proxy reach the same socket',
  );

  // The HEALTHCHECK script must read VESSEL_MCP_HTTP_PORT (with the
  // same default) so it never drifts from the env value.
  assert.match(
    dockerfile,
    /HEALTHCHECK[\s\S]*?process\.env\.VESSEL_MCP_HTTP_PORT\s*\|\|\s*3000/,
    'HEALTHCHECK must source the port from VESSEL_MCP_HTTP_PORT to avoid drift',
  );

  // Now feed the Dockerfile's documented defaults through the actual
  // runtime parser. It must produce the HTTP transport bound on the
  // EXPOSEd port — the same shape an operator gets when they run the
  // image with no further overrides.
  const config = loadRuntimeConfig({
    VESSEL_MCP_TRANSPORT: transport,
    VESSEL_MCP_HTTP_HOST: host,
    VESSEL_MCP_HTTP_PORT: port,
  });
  assert.equal(config.transport, 'http', 'Dockerfile defaults must select the HTTP transport');
  assert.equal(config.http.host, '0.0.0.0', 'container must bind 0.0.0.0 so the proxy can reach it');
  assert.equal(config.http.port, Number.parseInt(port, 10), 'parsed port must match Dockerfile EXPOSE');
  assert.equal(
    config.http.authToken,
    undefined,
    'image must not bake an auth token; operators inject VESSEL_MCP_AUTH_TOKEN at deploy time',
  );
});

test('deployment-https runbook documents all three named topology options and token rotation', () => {
  const text = read(RUNBOOK_URL);

  // Each named option header must be present; a missing one would
  // mean operators only see partial guidance for some platforms.
  assert.match(text, /###\s+Option A:\s+nginx/i, 'must include Option A: nginx');
  assert.match(text, /###\s+Option B:\s+Caddy/i, 'must include Option B: Caddy');
  assert.match(text, /###\s+Option C:\s+Managed platform/i, 'must include Option C: managed platform');

  // Each topology must show the bearer flowing through to /mcp via
  // a private upstream (not an https upstream — TLS terminates at the
  // proxy, never at the container).
  assert.doesNotMatch(
    text,
    /proxy_pass\s+https:\/\/127\.0\.0\.1/,
    'reverse proxy must not speak HTTPS to the container; TLS terminates at the proxy',
  );
  assert.doesNotMatch(
    text,
    /reverse_proxy\s+https:\/\/127\.0\.0\.1/,
    'Caddy must not speak HTTPS to the container; TLS terminates at the proxy',
  );

  // Token rotation procedure is part of secure deployment.
  assert.match(text, /##\s+Token rotation/i, 'must document token rotation');
  assert.match(text, /openssl rand -hex 32/, 'must show a concrete way to mint a fresh token');
  assert.match(text, /rolling restart|restart/i, 'must tell operators a restart is required');

  // Pre-deploy secret-safety verification list exists.
  assert.match(text, /Secret-safety verification|secret.safety/i);
  assert.match(text, /git status/, 'pre-deploy checklist must include git status hygiene');
});

test('deployment-https runbook keeps /mcp behind a bearer in every documented topology', () => {
  const text = read(RUNBOOK_URL);

  // The whole premise of the criterion is that /mcp stays bearer-gated
  // and TLS terminates outside the container. The runbook must not
  // accidentally include a "skip auth" / "disable bearer" recipe.
  assert.doesNotMatch(text, /disable.*(bearer|auth)/i, 'must not document disabling the bearer');
  assert.doesNotMatch(text, /VESSEL_MCP_AUTH_TOKEN=\s*$/m, 'must not show clearing the auth token');
  assert.doesNotMatch(text, /VESSEL_MCP_AUTH_TOKEN=""/, 'must not show clearing the auth token');

  // /health stays public; the runbook must say so explicitly so
  // operators do not gate the load-balancer probe behind the bearer.
  assert.match(
    text,
    /\/health[\s\S]{0,400}?(public|unauthenticated|no.*bearer|no.*token)/i,
    'must clarify that /health stays public for unauthenticated probes',
  );
});

test('F6 parent feature is flipped to implemented now that AC1, AC2, AC3 are all green', () => {
  // F6.FOLLOWUP closes the last F6 gap: with the observability,
  // deployment-https, and operator runbook tests all green and their
  // acceptance criteria already at status: implemented, the parent
  // feature is promoted by this followup.
  const reqs = read(REQUIREMENTS_URL);
  const f6Index = reqs.indexOf('id: F6');
  assert.ok(f6Index > 0, 'requirements.yaml must contain feature F6');
  const f6Header = reqs.slice(f6Index, f6Index + 400);
  assert.match(
    f6Header,
    /title: Security, observability, and deployment readiness[\s\S]*?status: implemented/,
    'F6 parent feature must be promoted to implemented by F6.FOLLOWUP',
  );
});
