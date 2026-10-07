import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      include: ['src/**'],
      // Entry point: only wires config and server to the stdio transport and exits
      // the process; not reachable from unit tests.
      exclude: ['src/index.ts'],
      // Measured 2026-08-18: 94.7 / 79.3 / 93.2 / 96.7 — thresholds sit just
      // below with headroom on functions. Raise them with new tests, never lower.
      thresholds: {
        statements: 92,
        branches: 76,
        functions: 88,
        lines: 94,
      },
    },
  },
});
