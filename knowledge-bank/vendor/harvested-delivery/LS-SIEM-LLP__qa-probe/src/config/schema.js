'use strict';

const { z } = require('zod');

const AuthSchema = z.object({
  type: z.enum(['bearer', 'cookie', 'api-key', 'none']).default('bearer'),
  loginUrl: z.string().default('/auth/login'),
  credentials: z.object({
    username: z.string(),
    password: z.string(),
  }).optional(),
  apiKey: z.string().optional(),
  apiKeyHeader: z.string().default('X-API-Key'),
  tokenPath: z.string().default('access_token'),
  cookieName: z.string().default('session'),
});

const SseSchema = z.object({
  enabled: z.boolean().default(true),
  firstEventTimeoutMs: z.number().default(5000),
  paths: z.array(z.string()).default([]),
});

const WsSchema = z.object({
  enabled: z.boolean().default(true),
  firstFrameTimeoutMs: z.number().default(5000),
  paths: z.array(z.string()).default([]),
});

const VisualProbeSchema = z.object({
  enabled: z.boolean().default(false),
  viewportWidth: z.number().default(1280),
  viewportHeight: z.number().default(720),
  densityThreshold: z.number().default(0.10),
  navigationTimeoutMs: z.number().default(30000),
});

const OtelSchema = z.object({
  enabled: z.boolean().default(false),
  backend: z.enum(['jaeger', 'tempo', 'honeycomb']).default('jaeger'),
  baseUrl: z.string().default('http://localhost:16686'),
  apiKey: z.string().optional(),
});

const PersonaSchema = z.object({
  name: z.string(),
  auth: z.record(z.any()).default({}),
});

const SecuritySchema = z.object({
  idor: z.boolean().default(false),
  pii: z.boolean().default(false),
  authBypass: z.boolean().default(false),
});

const HarReplaySchema = z.object({
  enabled: z.boolean().default(false),
  harFile: z.string().default('./traffic.har'),
  anonymize: z.boolean().default(true),
});

// Top-level security checks (auth-bypass / privilege-escalation / PII). Distinct
// from the legacy probe.security booleans.
const SecurityChecksSchema = z.object({
  enabled: z.boolean().default(false),
  authBypass: z.boolean().default(true),
  pii: z.boolean().default(true),
  piiAllow: z.array(z.string()).default([]),
  personas: z.array(PersonaSchema).default([]),
  policies: z.record(z.record(z.number())).default({}),
});

// Read-only response assertions, keyed by "METHOD path".
const AssertionRuleSchema = z.object({
  field: z.string().optional(),
  present: z.boolean().optional(),
  type: z.string().optional(),
  in: z.array(z.any()).optional(),
  pattern: z.string().optional(),
  gte: z.number().optional(),
  lte: z.number().optional(),
  gt: z.number().optional(),
  lt: z.number().optional(),
  nonEmpty: z.boolean().optional(),
  minItems: z.number().optional(),
  maxItems: z.number().optional(),
}).passthrough();
const AssertionsSchema = z.record(z.array(AssertionRuleSchema));

// Write-flow (CRUD-chain) testing — opt-in, mutating.
const WriteFlowStepSchema = z.object({
  method: z.string().optional(),
  path: z.string(),
  body: z.any().optional(),
}).passthrough();
const WriteFlowSchema = z.object({
  name: z.string().optional(),
  idField: z.string().optional(),
  create: WriteFlowStepSchema.optional(),
  read: WriteFlowStepSchema.optional(),
  update: WriteFlowStepSchema.optional(),
  delete: WriteFlowStepSchema.optional(),
}).passthrough();
const WriteFlowsSchema = z.object({
  enabled: z.boolean().default(false),
  flows: z.array(WriteFlowSchema).default([]),
});

// HAR import as an analyze-time discovery source (distinct from probe.harReplay,
// which only supplies request bodies).
const HarImportSchema = z.object({
  enabled: z.boolean().default(false),
  harFile: z.string().optional(),
});

const SchemathesisSchema = z.object({
  enabled: z.boolean().default(false),
  command: z.string().default('schemathesis'),
  timeoutMs: z.number().default(300000),
  hypothesisExamples: z.number().default(50),
});

const GraphqlSchema = z.object({
  endpoint: z.string().default('/graphql'),
  authToken: z.string().optional(),
});

const TrpcSchema = z.object({
  routerFile: z.string().default('./server/routers/index.ts'),
  endpoint: z.string().default('/api/trpc'),
});

const AnalyzeRuntimeSchema = z.object({
  enabled: z.boolean().default(false),
  browser: z.enum(['chromium', 'firefox', 'webkit']).default('chromium'),
  baseUrl: z.string().url().optional(),
  viewport: z.object({
    width: z.number().default(1280),
    height: z.number().default(720),
  }).default({}),
  navigationTimeoutMs: z.number().default(30000),
  captureWindowMs: z.number().default(5000),
});

const LlmRepairSchema = z.object({
  enabled: z.boolean().default(false),
  provider: z.enum(['disabled', 'openai', 'anthropic', 'ollama']).default('disabled'),
  endpoint: z.string().optional(),
  apiKey: z.string().optional(),
  model: z.string().optional(),
  maxFileBytes: z.number().default(50000),
  maxLineDelta: z.number().default(5),
  maxCharDelta: z.number().default(200),
});

const AnalyzeSchema = z.object({
  runtime: AnalyzeRuntimeSchema.default({}),
  llmRepair: LlmRepairSchema.default({}),
  har: HarImportSchema.default({}),
});

const ProbeSchema = z.object({
  concurrency: z.number().default(5),
  delayMs: z.number().default(50),
  timeoutMs: z.number().default(10000),
  hardTimeoutMs: z.number().optional(),
  maxProbeMs: z.number().optional(),
  maxResponseBytes: z.number().optional(),
  idDiscovery: z.boolean().default(true),
  ignoreHTTPSErrors: z.boolean().default(false),
  skipPaths: z.array(z.string()).default(['^/auth/', '^/health/', '^/openapi', '^/docs']),
  expectedEmptyPaths: z.array(z.string()).default([]),
  generatedSamplePaths: z.array(z.string()).default([]),
  safePosts: z.array(z.string()).default([]),
  postBodyMode: z.enum(['empty', 'minimal', 'realistic', 'example', 'har']).default('minimal'),
  postBodyOverrides: z.record(z.enum(['empty', 'minimal', 'realistic', 'example', 'har'])).default({}),
  pathParamValues: z.record(z.string()).default({ id: '1' }),
  sse: SseSchema.default({}),
  ws: WsSchema.default({}),
  visual: VisualProbeSchema.default({}),
  otel: OtelSchema.default({}),
  personas: z.array(PersonaSchema).default([]),
  security: SecuritySchema.default({}),
  harReplay: HarReplaySchema.default({}),
  schemathesis: SchemathesisSchema.default({}),
});

const ScoringSchema = z.object({
  missingRoute: z.number().default(-50),
  emptyResponse: z.number().default(-20),
  authError: z.number().default(-30),
  serverError: z.number().default(-40),
  slowResponse: z.number().default(-10),
  disabledFeature: z.number().default(-15),
  schemaMismatch: z.number().default(-25),
  streamDead: z.number().default(-35),
  securityIssue: z.number().default(-50),
  assertionFailed: z.number().default(-30),
  preconditionGate: z.number().default(-30),
  unknown: z.number().default(-10),
});

const OutputSchema = z.object({
  dir: z.string().default('.qaprobe'),
  keepHistory: z.number().default(10),
  formats: z.array(z.enum(['json', 'markdown', 'ai-context', 'html'])).default(['json', 'markdown', 'ai-context', 'html']),
});

const ReportCoverageSchema = z.object({
  enabled: z.boolean().default(true),
  ignoreEndpointGlobs: z.array(z.string()).default([]),
});

const ReportSchema = z.object({
  coverage: ReportCoverageSchema.default({}),
  baselineRuns: z.number().default(20),
});

const ConfigSchema = z.object({
  // Target
  baseUrl: z.string().url('baseUrl must be a valid URL'),
  frontendApiPrefix: z.union([z.string(), z.array(z.string())]).default('/api'),
  framework: z.enum(['fastapi', 'express', 'nextjs', 'generic', 'graphql', 'trpc']).default('fastapi'),
  openApiUrl: z.string().default('/openapi.json'),
  openApiFile: z.string().nullable().default(null),
  featureStatusUrl: z.string().nullable().default('/health/features'),
  graphql: GraphqlSchema.default({}),
  trpc: TrpcSchema.default({}),

  // Frontend source
  frontendSrc: z.string().default('./frontend/src'),
  routerFile: z.string().default('./frontend/src/App.tsx'),
  apiClientFile: z.string().nullable().default(null),

  // Auth
  auth: AuthSchema.default({}),

  // Probe behavior
  analyze: AnalyzeSchema.default({}),
  probe: ProbeSchema.default({}),

  // Scoring
  scoring: ScoringSchema.default({}),

  // Output
  output: OutputSchema.default({}),

  // Report add-ons
  report: ReportSchema.default({}),

  // Security checks (auth-bypass / privilege-escalation / PII) — opt-in.
  security: SecurityChecksSchema.default({}),

  // Read-only response assertions, keyed by "METHOD path".
  assertions: AssertionsSchema.optional(),

  // Write-flow (CRUD-chain) testing — opt-in, mutating.
  writeFlows: WriteFlowsSchema.default({}),

  // Optional: relocate the feedback store (default <output.dir>/feedback.json).
  feedbackFile: z.string().optional(),

  // Optional: shell command to seed the database. Shown in empty_db fix hints.
  // Example: 'docker exec api python scripts/seed.py'
  //          'npm run db:seed'
  //          'make seed'
  seedCommand: z.string().optional(),

  // Optional: map path prefixes to custom HAS_* flag names for feature_flag_disabled hints.
  // Auto-derived as HAS_SOME_FEATURE from /some-feature when not specified.
  // Example: { '/credential-scanner': 'HAS_DEFAULT_CRED_SCANNER' }
  featureFlagMap: z.record(z.string()).default({}),
});

module.exports = { ConfigSchema };
