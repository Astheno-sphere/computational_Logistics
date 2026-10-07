'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { extractProcedures, fetchSpec } = require('./trpc');
const { getAdapter } = require('../backend-fetcher');
const { ConfigSchema } = require('../../config/schema');

const ROUTER_SOURCE = `
  import { router, publicProcedure, protectedProcedure } from './trpc';
  export const appRouter = router({
    cases: publicProcedure.query(() => []),
    createCase: publicProcedure.input(caseInput).mutation(({ input }) => input),
    adminUsers: protectedProcedure.query(() => []),
  });
`;

test('tRPC parser extracts query and mutation procedures from a router definition', () => {
  const procedures = extractProcedures(ROUTER_SOURCE);

  assert.deepEqual(procedures, [
    { name: 'cases', type: 'query' },
    { name: 'createCase', type: 'mutation' },
    { name: 'adminUsers', type: 'query' },
  ]);
});

test('tRPC adapter converts router procedures into endpoint entries', async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'qa-probe-trpc-'));
  const routerFile = path.join(dir, 'router.ts');
  fs.writeFileSync(routerFile, ROUTER_SOURCE);

  const spec = await fetchSpec({
    trpc: { routerFile, endpoint: '/api/trpc' },
  });

  assert.deepEqual(Object.keys(spec.routes).sort(), [
    'POST /api/trpc/adminUsers',
    'POST /api/trpc/cases',
    'POST /api/trpc/createCase',
  ]);
  assert.equal(spec.routes['POST /api/trpc/createCase'].trpc.type, 'mutation');
});

test('config and backend fetcher register the trpc framework', () => {
  const config = ConfigSchema.parse({
    baseUrl: 'http://localhost:3000',
    framework: 'trpc',
  });

  assert.equal(config.trpc.endpoint, '/api/trpc');
  assert.equal(getAdapter(config.framework), require('./trpc'));
});
