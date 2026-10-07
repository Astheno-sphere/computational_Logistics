# Bamwor MCP — Distribution Plan

## Phase 1: npm Publication

### Pre-publish checklist
- [ ] npm account created (or use existing)
- [ ] `npm login` completed
- [ ] Verify package name available: `npm view bamwor-mcp-server`
- [ ] Run `npm pack --dry-run` to verify package contents
- [ ] Test local install: `npm pack && npm install -g bamwor-mcp-server-0.1.0.tgz`
- [ ] Test with Claude Desktop locally
- [ ] Verify shebang in `dist/index.js`: `#!/usr/bin/env node`

### Publish command
```bash
cd mcp/
npm run build
npm pack --dry-run  # verify contents first
npm publish --access public
```

### Post-publish verification
```bash
npx bamwor-mcp-server  # should start and print to stderr
npm view bamwor-mcp-server  # verify listing
```

---

## Phase 2: MCP Directories & Registries

### Priority 1 — Official/semi-official
1. **modelcontextprotocol.io** — Official MCP server list
   - Submit via: https://github.com/modelcontextprotocol/servers
   - PR to add bamwor-world-data to community servers

2. **Smithery.ai** — MCP server registry
   - Register at smithery.ai
   - Tag: geography, world-data, countries, cities

3. **Glama.ai MCP directory**
   - Submit server listing

### Priority 2 — Awesome lists
4. **awesome-mcp-servers** (GitHub)
   - https://github.com/punkpeye/awesome-mcp-servers
   - Category: "Knowledge & Data" or "Geography"

5. **awesome-mcp** (GitHub)
   - https://github.com/wong2/awesome-mcp-servers

### Priority 3 — Package visibility
6. npm keywords already set for discoverability
7. GitHub repo with proper README, topics, description

---

## Phase 3: HuggingFace

### Pre-publish checklist
- [ ] HuggingFace account created
- [ ] Organization "bamwor" claimed
- [ ] CSV files generated from production DB
- [ ] Parquet files generated
- [ ] README cards reviewed

### Datasets to publish
1. `bamwor/world-countries` — 261 records, ~500KB
2. `bamwor/world-cities` — ~4,500 records (pop >= 100K), ~2MB

### Publication
```bash
# Using huggingface-cli
pip install huggingface-hub
huggingface-cli login
huggingface-cli upload bamwor/world-countries ./data/countries/
huggingface-cli upload bamwor/world-cities ./data/cities/
```

---

## Phase 4: Kaggle

### Pre-publish checklist
- [ ] Kaggle account configured
- [ ] Dataset metadata JSON prepared
- [ ] Demo notebook tested locally

### Datasets
1. "World Countries Dataset 2026" — same data as HuggingFace
2. "World Cities Database 2026" — same data as HuggingFace

### Notebook
- "Exploring World Urbanization" — visualization notebook using both datasets

---

## Phase 5: Community Announcement

### Where to announce (ordered by priority)
1. **GitHub** — Release notes on bamwor-mcp-server repo
2. **r/ClaudeAI** — Post about MCP server for geographic data
3. **r/MachineLearning** — If datasets get traction on HF/Kaggle
4. **Hacker News** — Show HN post (only if we have a compelling demo)
5. **X/Twitter** — Thread from @bamwor account
6. **Dev.to** — Tutorial: "Giving your AI agent access to world geographic data"

### Announcement message template
```
Bamwor MCP Server — world geographic data for AI agents.

Give Claude, Cursor, or any MCP-compatible AI access to:
- 261 countries with 20+ statistics each
- 13.4M cities with coordinates, population, timezone
- Multilingual support (EN/ES/PT/IT)

One command: npx bamwor-mcp-server

Free API key: bamwor.com/developers/quickstart
```

---

## Phase 6: Metrics to Track

### Week 1-2
- npm weekly downloads
- GitHub stars
- API key registrations (track source=mcp)
- HuggingFace dataset downloads
- Kaggle dataset downloads & notebook views

### Month 1
- Total npm installs
- API requests from MCP User-Agent
- Free → Pro conversion rate
- HuggingFace/Kaggle engagement

### Signals to watch
- GitHub issues (bugs, feature requests)
- npm download trend (flat vs growing)
- Which tools get used most (API logs)
- Rate limit hits (demand signal)

---

## Risks of Launching Too Early

1. **API stability** — If the API has breaking changes, MCP users get broken experience
2. **Rate limits too tight** — If free tier (30/min) isn't enough for normal MCP usage
3. **Missing tools** — Users may expect more tools (regions, rankings, nearby cities)
4. **npm name squatting** — Low risk, name is specific enough
5. **Support burden** — GitHub issues need response time

### Mitigations
- Version 0.1.0 signals "early but functional"
- README is clear about free tier limits
- FAQ covers common questions
- API has been stable for months
- Start with minimal announcement, scale up based on reception

---

## Recommended Launch Order

1. **Day 1**: npm publish + GitHub repo public
2. **Day 2**: Deploy /developers/mcp page on bamwor.com
3. **Day 3**: Submit to MCP directories (modelcontextprotocol, Smithery)
4. **Day 5**: Publish HuggingFace datasets
5. **Day 7**: Publish Kaggle datasets + notebook
6. **Day 10**: Community announcements (Reddit, X)
7. **Day 14**: Review metrics, decide on v0.2.0 features
