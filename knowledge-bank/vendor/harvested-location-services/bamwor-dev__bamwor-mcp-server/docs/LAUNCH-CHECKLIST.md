# Bamwor MCP — Launch Checklist

## Before Publishing npm

- [ ] npm account exists and `npm login` works
- [ ] Package name `bamwor-mcp-server` is available (`npm view bamwor-mcp-server`)
- [ ] `npm run build` succeeds cleanly
- [ ] `dist/index.js` starts with `#!/usr/bin/env node`
- [ ] `npm pack --dry-run` shows only: dist/, LICENSE, README.md, package.json
- [ ] No `.env`, no `src/`, no `Dockerfile` in package
- [ ] Version is `0.1.0`
- [ ] Local test: `npm pack && npx ./bamwor-mcp-server-0.1.0.tgz` starts server
- [ ] Test with real Claude Desktop: configure, ask "population of Brazil", verify answer
- [ ] API key error message is clear (401 → helpful message)
- [ ] Rate limit error message is clear (429 → upgrade link)
- [ ] README has correct install instructions and config examples
- [ ] LICENSE file is included
- [ ] GitHub repo `bamwor-mcp-server` is created (can be private initially)

### Publish command
```bash
cd mcp/
npm run build
npm publish --access public
```

---

## Before Deploying /developers/mcp Page

- [ ] Page compiles with `npx tsc --noEmit` (already verified)
- [ ] npm package is published and `npx bamwor-mcp-server` works
- [ ] All 4 language versions render correctly
- [ ] FAQ answers are accurate
- [ ] Comparison table data is accurate
- [ ] CTA links work (quickstart, GitHub)
- [ ] JSON-LD schema validates (test at schema.org validator)
- [ ] MCP nav item appears in developers layout
- [ ] Canonical URLs are correct
- [ ] No broken links

### Deploy
Standard deploy flow: git push → SSH deploy script

---

## Before Publishing HuggingFace

- [ ] HuggingFace account created
- [ ] Organization "bamwor" registered (or personal account)
- [ ] CSV files generated from production database
  - countries: `SELECT name, slug, iso_code, capital, region, population, area_sq_km, latitude, longitude, category FROM countries`
  - cities: `SELECT geoname_id, ascii_name, country_code, population, latitude, longitude, timezone, elevation, feature_code FROM geonames WHERE population >= 100000 AND feature_class = 'P'`
- [ ] Parquet files generated from CSVs
- [ ] README cards match docs/huggingface-readme.md
- [ ] YAML frontmatter metadata is correct
- [ ] CTA links point to live bamwor.com pages
- [ ] License is CC BY 4.0
- [ ] No premium data leakage (only basic fields, no stats, no multilingual)
- [ ] Sample data verified for accuracy

### Data boundary (free vs premium)
**Included free (HuggingFace/Kaggle):**
- Country: name, slug, iso_code, capital, region, population, area_sq_km, lat, lon, category
- City: geoname_id, name, country_code, population, lat, lon, timezone, elevation, feature_code

**NOT included (premium/API only):**
- 20+ country statistics (GDP, HDI, etc.)
- Multilingual names (es, pt, it)
- Country sections (text descriptions)
- Cities below 100K population (13.4M total)
- Administrative region names for cities
- Nearby city search
- URL slugs

---

## Before Publishing Kaggle

- [ ] Kaggle account configured
- [ ] Dataset metadata JSON prepared (dataset-metadata.json)
- [ ] Same CSV files as HuggingFace
- [ ] Demo notebook tested in Kaggle environment
- [ ] Notebook uses only standard libraries (pandas, matplotlib, plotly)
- [ ] CTA links work
- [ ] Tags are appropriate

---

## Before Public Announcement

- [ ] npm package has been live for at least 48 hours without issues
- [ ] /developers/mcp page is deployed and accessible
- [ ] At least one real user has tested (yourself with Claude Desktop)
- [ ] GitHub repo is public with proper README
- [ ] No known bugs in any of the 5 tools
- [ ] API is stable and responding normally
- [ ] Rate limits are adequate for expected initial traffic
- [ ] HuggingFace/Kaggle datasets are published (optional but recommended)
- [ ] Announcement posts drafted for Reddit/X

### Announcement order
1. GitHub release
2. MCP directory submissions
3. Reddit (r/ClaudeAI first)
4. X/Twitter
5. Dev.to article (optional)
