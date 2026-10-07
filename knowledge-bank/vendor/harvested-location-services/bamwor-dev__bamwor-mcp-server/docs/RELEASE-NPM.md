# npm Release Procedure — bamwor-mcp-server

**Status:** READY — do NOT execute until explicitly authorized

---

## Prerequisites

1. **npm account** — create at npmjs.com if needed
2. **GitHub repo** — `bamwor-mcp-server` (can be private initially)
   - Update `repository.url` in package.json if repo URL differs
3. **Contact email** — confirm or replace `hello@bamwor.com` in package.json `author` field
4. **Valid API key** — for testing before publish

---

## Pre-publish Validation

Run these in order from `mcp/` directory:

### Step 1: Clean build
```bash
npm run clean
npm ci
npm run build
```

### Step 2: Verify shebang
```bash
head -1 dist/index.js
# MUST output: #!/usr/bin/env node
```

### Step 3: Verify package contents
```bash
npm pack --dry-run
```
Expected output:
- `dist/` files (*.js, *.d.ts, *.js.map, *.d.ts.map)
- `LICENSE`
- `README.md`
- `package.json`
- Total: ~39 files, ~13KB compressed

Must NOT contain:
- `src/` (TypeScript source)
- `.env` or `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `tsconfig.json`
- `docs/`
- `node_modules/`

### Step 4: Local install test
```bash
npm pack
# Creates bamwor-mcp-server-0.1.0.tgz

# Test global install
npm install -g ./bamwor-mcp-server-0.1.0.tgz
bamwor-mcp-server
# Should print "Bamwor MCP Server started" to stderr

# Clean up
npm uninstall -g bamwor-mcp-server
rm bamwor-mcp-server-0.1.0.tgz
```

### Step 5: Test with Claude Desktop
```json
{
  "mcpServers": {
    "bamwor-world-data": {
      "command": "node",
      "args": ["/full/path/to/mcp/dist/index.js"],
      "env": {
        "BAMWOR_API_KEY": "your_real_key"
      }
    }
  }
}
```
Verify all 5 tools respond correctly.

### Step 6: Verify README renders
```bash
# Preview at https://npm.runkit.com/ or check markdown locally
# Ensure: install instructions, tool list, config examples, rate limits
```

---

## Publish

```bash
# Login (first time only)
npm login

# Verify logged in
npm whoami

# Publish
cd mcp/
npm publish --access public
```

The `prepublishOnly` script will automatically run `npm run build` before publishing.

---

## Post-publish Verification

```bash
# Check listing
npm view bamwor-mcp-server

# Test npx
BAMWOR_API_KEY=your_key npx bamwor-mcp-server
# Should start server

# Check npm page
# https://www.npmjs.com/package/bamwor-mcp-server
```

---

## Version Bumping (future releases)

```bash
# Patch: 0.1.0 → 0.1.1 (bug fix)
npm version patch

# Minor: 0.1.0 → 0.2.0 (new tool)
npm version minor

# Then publish
npm publish
```

Remember to also update `version` in `src/server.ts` to match.

---

## Rollback (if needed)

```bash
# Unpublish within 72 hours
npm unpublish bamwor-mcp-server@0.1.0

# Or deprecate (softer)
npm deprecate bamwor-mcp-server@0.1.0 "Known issue — use 0.1.1"
```

---

## Configurable Fields (confirm before publish)

| Field | Current Value | Status |
|-------|---------------|--------|
| `name` | `bamwor-mcp-server` | Confirmed |
| `version` | `0.1.0` | Confirmed |
| `author` | `Bamwor <hello@bamwor.com>` | **PENDING CONFIRMATION** |
| `repository.url` | `https://github.com/ismaeldarosa19/bamwor-mcp-server` | **PENDING — repo not created yet** |
| `bugs.url` | `https://github.com/ismaeldarosa19/bamwor-mcp-server/issues` | **PENDING — repo not created yet** |
| `homepage` | `https://bamwor.com/developers/mcp` | **PENDING — page not deployed yet** |
