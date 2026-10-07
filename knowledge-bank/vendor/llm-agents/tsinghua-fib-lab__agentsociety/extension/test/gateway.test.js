/**
 * Gateway / auth smoke tests.
 * Keep only invariants that protect auth routing, role eligibility, and usage accounting.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  inferApiKindFromBaseUrl,
} = require('../out/aiCli/officialEndpoints');
const {
  isFiblabLlmBase,
} = require('../out/services/webConfigGatewayImport');
const {
  pythonHasAgentsociety2,
} = require('../out/services/agentsocietyPythonResolver');
const {
  applyUpstreamAuthHeaders,
  resolveAuthHeaderMode,
} = require('../out/aiCli/upstreamAuthHeaders');
const {
  clampProviderRoleFlags,
  countApiUpstreamsForRole,
  providerEligibleForRoleUpstream,
} = require('../out/aiCli/providerAuth');
const {
  aggregateUsage,
  sanitizeUsageRecords,
} = require('../out/services/gatewayUsageTracker');
const { resolveUpstreamTargetUrl } = require('../out/services/aiCliGatewayUpstream');
const { claudeSettingsBaseUrl } = require('../out/aiCli/officialEndpoints');

test('URL classification only inspects parsed host and path components', () => {
  assert.equal(
    inferApiKindFromBaseUrl('https://evil.example/siliconflow.cn/v1'),
    'anthropic',
  );
  assert.equal(inferApiKindFromBaseUrl('https://api.siliconflow.cn/v1'), 'openai');
  assert.equal(inferApiKindFromBaseUrl('https://llmapi.fiblab.net/v1'), 'openai');
  assert.equal(isFiblabLlmBase('not-a-url-llmapi.fiblab.net'), false);
  assert.equal(isFiblabLlmBase('https://llmapi.fiblab.net/v1'), true);
});

test('Python discovery never evaluates configured paths in a shell', () => {
  assert.equal(pythonHasAgentsociety2('python3; echo pwned'), false);
  assert.equal(pythonHasAgentsociety2('python3 && echo pwned'), false);
});

test('auth header mode: auto inference and explicit override', () => {
  assert.equal(
    resolveAuthHeaderMode({
      upstreamBaseUrl: 'https://api.openai.com/v1',
      requestHeaders: {},
    }),
    'bearer',
  );
  assert.equal(
    resolveAuthHeaderMode({
      upstreamBaseUrl: 'https://api.anthropic.com',
      requestHeaders: {},
    }),
    'both',
  );

  const bearerOnly = {};
  applyUpstreamAuthHeaders(bearerOnly, 'tok', {
    upstreamBaseUrl: 'https://api.anthropic.com',
    mode: 'bearer',
  });
  assert.equal(bearerOnly.authorization, 'Bearer tok');
  assert.equal(bearerOnly['x-api-key'], undefined);

  const both = {};
  applyUpstreamAuthHeaders(both, 'tok', {
    upstreamBaseUrl: 'https://api.openai.com/v1',
    mode: 'both',
  });
  assert.equal(both.authorization, 'Bearer tok');
  assert.equal(both['x-api-key'], 'tok');
});

test('Codex role eligibility excludes Anthropic upstreams', () => {
  const anthropic = {
    baseUrl: 'https://api.anthropic.com',
    apiKey: 'sk-ant',
    apiKind: 'anthropic',
    authMode: 'api',
  };
  const openai = {
    baseUrl: 'https://api.openai.com/v1',
    apiKey: 'sk-openai',
    apiKind: 'openai',
    authMode: 'api',
  };
  assert.equal(providerEligibleForRoleUpstream(anthropic, 'claude'), true);
  assert.equal(providerEligibleForRoleUpstream(anthropic, 'codex'), false);
  assert.equal(providerEligibleForRoleUpstream(openai, 'codex'), true);

  const clamped = clampProviderRoleFlags({
    ...anthropic,
    failoverClaude: true,
    failoverCodex: true,
  });
  assert.equal(clamped.failoverClaude, true);
  assert.equal(clamped.failoverCodex, false);

  assert.equal(countApiUpstreamsForRole([anthropic, openai], 'claude'), 2);
  assert.equal(countApiUpstreamsForRole([anthropic, openai], 'codex'), 1);
});

test('upstream URL joining does not double /v1', () => {
  assert.equal(
    resolveUpstreamTargetUrl('https://api.example.com/v1', '/v1/messages'),
    'https://api.example.com/v1/messages',
  );
  assert.equal(
    claudeSettingsBaseUrl('https://llmapi.fiblab.net/v1'),
    'https://llmapi.fiblab.net',
  );
});

test('usage accounting requires an explicit claude/codex app', () => {
  const base = {
    model: 'gpt-5.5',
    inputTokens: 10,
    outputTokens: 5,
    cacheReadTokens: 0,
    cacheCreationTokens: 0,
    serverToolUseTokens: 0,
    requestId: 'r1',
    upstream: 'https://api.example.com/v1',
    ts: '2026-07-12T04:08:28.000Z',
  };
  const kept = sanitizeUsageRecords([
    { ...base, app: 'claude' },
    { ...base, requestId: 'r2' },
    { ...base, requestId: 'r3', app: 'unknown' },
  ]);
  assert.equal(kept.length, 1);
  assert.equal(kept[0].app, 'claude');

  const agg = aggregateUsage([{ ...base, app: 'codex' }, { ...base, requestId: 'r2' }]);
  assert.equal(agg.totalRequests, 1);
  assert.equal(agg.byApp.codex.requests, 1);
});

test('gateway start keeps authHeaderMode on the primary upstream', async () => {
  const { AiCliGateway } = require('../out/services/aiCliGateway');
  const gateway = new AiCliGateway();
  const status = await gateway.start({
    baseUrl: 'https://api.anthropic.com',
    apiKey: 'sk-test',
    apiKind: 'anthropic',
    authHeaderMode: 'x-api-key',
  });
  assert.equal(status.running, true);
  assert.equal(gateway.upstream.authHeaderMode, 'x-api-key');
  await gateway.stop();
});
