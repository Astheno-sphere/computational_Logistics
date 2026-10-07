# Publishing floodwise

Run these on your Mac (npm 2FA passkey + `gh` auth as `kristaffa`). From the repo root: `cd floodwise`.

Each command has a working directory — this is a single-package repo, so everything runs from the repo root **except** nothing special; just don't run it from another project folder.

---

## 0. ⚠️ FIRST: load the real Environment Agency dataset

**The real EA data is already loaded** in this working tree: `data/flood-postcodes.json` (git-ignored
because it's large) holds the full 2025-Q4 set (~1.46M England postcodes), and `npm run build` bakes it
into `dist/`. So for this publish you can skip straight to pre-flight. Just confirm it:
```
npm install
npm run build
npm test
```
`npm test` should report `dataset: ea-official, 1463052 postcodes`. (The committed repo only contains the
small `data/flood-postcodes.sample.json` fallback — the 81 MB real file is never committed.)

**To refresh later** (the EA updates ~quarterly — see the scheduled task), download a new
`Postcodes_Risk_Assessment_All.csv` from <https://www.data.gov.uk/> ("Flood risk: postcode search tool
data", Open Government Licence) and re-run:
```
npm run build-data /path/to/Postcodes_Risk_Assessment_All.csv 2025-Q4
npm run build && npm test
```

> **Size:** handled. The data is bundled as one packed string literal, so `tsc` builds in seconds and the
> npm tarball is ~5 MB (≈24 MB unpacked); it parses into a Map (~1.5 M entries) once at server start. The
> hosted **Worker** still can't bundle the full set (CF limit) — that's the D1 follow-on, see step 5.

---

## 1. Pre-flight (scrub + pack)

```
npm test
node -e "import('./dist/index.js').then(m=>console.log('dataset', m.datasetKind, m.datasetVersion, m.datasetSize, 'postcodes'))"
npm pack --dry-run
grep -rniE "anthropic|claude|/Users/|TODO|FIXME" src scripts data docs README.md
```
The pack should ship only `dist/ README.md LICENSE NOTICE`. The grep should print nothing (scrub for
personal paths/usernames, local home paths, AI attribution — and eyeball for your own name or work email).

---

## 2. Publish to npm

Name is unscoped (`floodwise`). If npm rejects with 403 "too similar", scope it to
`@qinisolabs/floodwise` (update `package.json` name, `server.json` identifier, and the install strings
in README/docs/llms.txt/smithery), then republish.

```
npm whoami
npm publish --access public
```

## 3. GitHub repo + push

The `git config user.email` line MUST print `qinisolabs@gmail.com` before the first commit
(never `--global`; keeps brand vs work/GitLab identities separate).

```
git init
git config user.name "Qiniso"
git config user.email "qinisolabs@gmail.com"
git config user.email
git add .
git commit -m "Initial commit: floodwise"
git branch -M main
gh repo create qinisolabs/floodwise --source=. --remote=origin --push --public --description "England flood-risk by postcode for AI agents — verified Environment Agency data, not guesses."
gh repo edit qinisolabs/floodwise --add-topic mcp,model-context-protocol,agents,llm,flood-risk,postcode,england,environment-agency,insurance,typescript
gh repo edit qinisolabs/floodwise --homepage "https://qinisolabs.github.io/floodwise"
git log --format='%an <%ae>' -1
```

## 4. MCP Registry

```
mcp-publisher login github
mcp-publisher publish
```

## 5. (Deferred) Hosted Worker

The full England dataset exceeds the Cloudflare Worker bundle limit, so **don't deploy a sample-only
Worker as if it were the real endpoint** — it would return `dataset: "sample"`. The hosted edge endpoint
is a follow-on that moves the data into Cloudflare D1/KV. Until then, floodwise is npm/stdio only, and the
README points users to the `npx` install (do not advertise a `workers.dev` URL that isn't live).

## 6. GitHub Pages

```
gh api -X POST repos/qinisolabs/floodwise/pages --input - <<'JSON'
{"source":{"branch":"main","path":"/docs"}}
JSON
```
Live at <https://qinisolabs.github.io/floodwise>.

## 7. Verify live + directories

Add `{ "command": "npx", "args": ["-y", "floodwise"] }` in a client, then `flood_risk_by_postcode` a
known England postcode and a Scottish one (expect "not found"). Track directory submissions in
`SUBMISSIONS.md` (Glama / mcp.so auto-ingest from the registry; the awesome-mcp-servers PR is manual).
