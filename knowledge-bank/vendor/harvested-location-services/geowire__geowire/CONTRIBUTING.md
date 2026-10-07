# Contributing to GeoWire

Thanks for helping build GeoWire! The highest-leverage contribution is a **new
provider** — that's what makes GeoWire more useful for everyone.

## Development setup

```bash
# Node 22+ and pnpm 10+
corepack enable
pnpm install
pnpm build       # turbo build (respects package dependency order)
pnpm test        # all unit + conformance + integration tests
pnpm typecheck
```

Monorepo layout:

```
packages/
  schema/            # Zod schemas — the single source of truth
  provider-sdk/      # GeoProvider contract (what every provider implements)
  provider-testkit/  # conformance harness ("testkit passes = mergeable")
  core/              # pipeline, routing, dedup, policy, cache
  providers/*        # nominatim, google, internal, ...
  mcp/               # MCP server (5 tools)
  cli/               # `geowire` CLI
apps/
  server/            # Fastify REST + OpenAPI + /metrics + /mcp
```

Conventions: ESM only, TypeScript strict, `verbatimModuleSyntax`. All public
APIs get JSDoc. Errors leaving core carry a normalized `ProviderErrorCode`.
Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat(core): ...`) so release notes automate.

### Changesets

Every user-facing change needs a changeset:

```bash
pnpm changeset      # pick bumped packages + write a summary
```

---

## Write a provider in 30 minutes

A provider is a thin adapter: **normalize one API's data into `ProviderPlace`**.
Everything else — internal IDs, attribution, dedup, ranking, caching, cost — is
core's job. Adapters stay ~200 lines.

### 1. Scaffold

```
packages/providers/<name>/
  package.json      # name: @geowirehq/provider-<name>, deps: @geowirehq/schema, @geowirehq/provider-sdk
  tsconfig.json     # extends ../../../tsconfig.base.json
  src/
    manifest.ts     # capabilities, auth, cost, policy
    parse.ts        # raw API response → ProviderPlace
    <name>.ts       # createXProvider() using defineProvider()
    index.ts
  test/
    conformance.test.ts
```

### 2. Declare a manifest

```ts
import type { ProviderManifest } from "@geowirehq/schema";

export const MY_MANIFEST: ProviderManifest = {
  id: "myprovider",
  name: "My Provider",
  capabilities: ["search", "geocode"],
  authType: "apiKey",              // "apiKey" | "oauth" | "none"
  cost: { currency: "USD", perCall: { search: 0.005 } },
  policy: {
    maxCacheTtlSeconds: 86_400,    // null = caching forbidden
    canStorePermanently: true,
    attributionRequired: "© My Provider",
  },
};
```

### 3. Implement with `defineProvider()`

`defineProvider` validates the manifest and checks that declared capabilities
match implemented methods at construction time.

```ts
import { defineProvider, errorFromHttpStatus, GeoProviderError } from "@geowirehq/provider-sdk";
import { MY_MANIFEST } from "./manifest.js";
import { parseResults } from "./parse.js";

export function createMyProvider(opts: { apiKey?: string } = {}) {
  return defineProvider({
    manifest: MY_MANIFEST,
    async searchPlaces(req, ctx) {
      if (!opts.apiKey) throw new GeoProviderError("MISSING_CREDENTIALS", "...", { provider: "myprovider" });
      const res = await ctx.fetch(`https://api.example.com/search?q=${encodeURIComponent(req.query)}`);
      if (!res.ok) throw errorFromHttpStatus(res.status, { provider: "myprovider" });
      return parseResults(await res.json());   // ProviderPlace[]
    },
  });
}
```

Rules:
- **Never build infrastructure.** Use `ctx.fetch` (retries + timeout built in),
  `ctx.logger`, `ctx.now`. No raw `fetch`, no `setTimeout` for retries.
- **Throw `GeoProviderError`** with a normalized code — never leak raw errors.
- Return `ProviderPlace[]` (no internal `id`, no `attributions` — core adds those).

### 4. Pass the testkit

```ts
import { runConformanceTests } from "@geowirehq/provider-testkit";
import { createMyProvider } from "../src/index.js";

runConformanceTests(createMyProvider({ apiKey: "test" }), {
  fixtures: {
    search: { request: { query: "coffee", limit: 5 }, responseBody: MY_FIXTURE, minResults: 1 },
  },
});
```

The testkit checks 6 axes: manifest validity, capability↔method match, fixture →
valid `ProviderPlace`, HTTP errors → normalized `GeoProviderError`, timeout →
`TIMEOUT`, attribution present when declared. **Testkit passes = mergeable.**

For a real, minimal reference read `packages/providers/nominatim` (no API key,
so you can run it live). For CSV/in-memory providers, see `providers/internal`
and set `usesHttp: false` in the testkit.

### 5. Add a changeset and open a PR

Include a fixture (recorded real response) so CI runs conformance without live
calls. Map the provider's categories to GeoWire's standard categories in a
`category-map.ts` (community-editable data file).

## Reporting bugs / requesting providers

Use the issue templates: **Bug report**, **Feature request**, and
**New provider request**.
