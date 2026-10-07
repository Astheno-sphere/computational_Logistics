# Publishing `@pedra-ai/mcp` to npm

The package is published as a **public scoped** package (`@pedra-ai/mcp`).
`publishConfig.access` is already `public`, so a plain `npm publish` works.

## One-time setup

The `pedra-ai` npm org already exists (created for `@pedra-ai/sdk`). You need a
member with publish rights. Because the account has 2FA enabled, publishing from
the CLI requires a **Classic Automation token** (a Publish token still prompts
for an OTP). Create one at
https://www.npmjs.com/settings/<user>/tokens → Generate New Token → Classic →
**Automation**, then either `npm login` or publish with the token:

```bash
echo "//registry.npmjs.org/:_authToken=npm_xxx" > ~/.npmrc   # or use NPM_TOKEN in CI
```

## Publish

```bash
npm install        # deps + dev deps
npm test           # builds + runs the test suite
npm publish        # builds via prepublishOnly, publishes @pedra-ai/mcp@<version>
```

`prepublishOnly` runs `clean` + `build`, so `dist/` is always fresh. Only
`dist/`, `README.md`, and `LICENSE` ship in the tarball (see `.npmignore`);
verify with `npm pack --dry-run`.

## Releasing a new version

A tagged release publishes to **both npm and the official MCP registry**
automatically via `.github/workflows/release.yml`:

```bash
# bump package.json + server.json + package-lock to the new version first, then:
npm version patch   # or minor / major — bumps package.json + git tag
git push --follow-tags
```

The workflow (triggered by the `v*` tag) runs the tests, `npm publish`es with
provenance, then publishes `server.json` to the registry. Update `CHANGELOG.md`
and keep `server.json`'s `version` (and the npm `version`) in lockstep before
tagging — the registry rejects a `server.json` whose npm package version isn't
live on npm yet, which is why npm is published first in the same job.

To publish manually instead, run `npm publish` and then:

```bash
brew install mcp-publisher        # or download from the registry releases
mcp-publisher login github        # browser OAuth; authorizes io.github.pedra-ai/*
mcp-publisher publish             # reads ./server.json
```

## MCP registries

The server is listed in the registries below. The **official registry is the
hub** — mcp.so, Glama, and PulseMCP ingest from it (and from npm), so a registry
publish propagates to them automatically. Smithery and the editor directories
are separate, one-time connections.

| Registry | How it's listed | Maintenance |
|----------|-----------------|-------------|
| Official MCP registry (`registry.modelcontextprotocol.io`) | `server.json` + release workflow | Auto on every tag |
| Smithery (`smithery.ai`) | `smithery.yaml`; connect repo once in the Smithery dashboard | Auto-redeploys on push |
| mcp.so | Ingests from the official registry / npm | Auto |
| Glama (`glama.ai`) | Auto-indexes the public GitHub repo + npm | Auto |
| PulseMCP (`pulsemcp.com`) | Ingests from the official registry / npm | Auto |
| Cursor directory | Submit once at `cursor.com/directory` | Manual |
| Claude / Anthropic directory | Submit once via Anthropic's connector directory form | Manual |

Ownership of the npm package is proven by the `mcpName` field in `package.json`
(`io.github.pedra-ai/pedra-mcp`), which must match `name` in `server.json`.

## CI

`.github/workflows/ci.yml` runs `npm test` on Node 18/20/22 for every push and
PR. `.github/workflows/release.yml` handles publishing — it needs one repo
secret, `NPM_TOKEN` (the npm org's Classic Automation token); the registry
publish needs no secret (it uses the workflow's GitHub OIDC token).
