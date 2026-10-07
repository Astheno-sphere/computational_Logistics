# PROPOSAL: /developers/mcp Page

**Status:** PROPOSAL — NOT APPROVED for integration
**Files affected (pending approval):**
- `web/src/app/[lang]/developers/mcp/page.tsx` (new page)
- `web/src/app/[lang]/developers/layout.tsx` (nav item addition)

**These files exist in the repo as drafts but are NOT approved for deploy.**

---

## Page Structure

### Route
`/[lang]/developers/mcp` — e.g., `/en/developers/mcp`

### SEO Metadata

**Title (per lang):**
- EN: "MCP Server — World Geographic Data for AI Agents"
- ES: "Servidor MCP — Datos Geográficos Mundiales para Agentes de IA"
- PT: "Servidor MCP — Dados Geográficos Mundiais para Agentes de IA"
- IT: "Server MCP — Dati Geografici Mondiali per Agenti IA"

**Description (per lang):**
- EN: "Connect AI agents to 261 countries and 13.4M cities via the Model Context Protocol (MCP). Works with Claude Desktop, Cursor, Windsurf, and any MCP client."
- ES: "Conecta agentes de IA a 261 países y 13.4M ciudades a través del Model Context Protocol (MCP). Compatible con Claude Desktop, Cursor, Windsurf y cualquier cliente MCP."
- PT: "Conecte agentes de IA a 261 países e 13.4M cidades via Model Context Protocol (MCP). Funciona com Claude Desktop, Cursor, Windsurf e qualquer cliente MCP."
- IT: "Collega agenti IA a 261 paesi e 13.4M città tramite il Model Context Protocol (MCP). Funziona con Claude Desktop, Cursor, Windsurf e qualsiasi client MCP."

**Canonical:** `https://bamwor.com/{lang}/developers/mcp`
**Alternates:** All 4 lang versions
**OpenGraph + Twitter Card:** Standard pattern from `@/lib/seo`

---

## JSON-LD Schemas

### 1. BreadcrumbList
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "position": 1, "name": "Home", "item": "https://bamwor.com/{lang}" },
    { "position": 2, "name": "API", "item": "https://bamwor.com/{lang}/developers" },
    { "position": 3, "name": "MCP Server" }
  ]
}
```

### 2. SoftwareApplication
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "bamwor-mcp-server",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Any",
  "description": "{DESCRIPTIONS[lang]}",
  "url": "https://bamwor.com/{lang}/developers/mcp",
  "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
  "author": { "@type": "Organization", "name": "Bamwor", "url": "https://bamwor.com" }
}
```

### 3. FAQPage
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    { "@type": "Question", "name": "Do I need an API key?", "acceptedAnswer": { "@type": "Answer", "text": "..." } },
    // ... 6 questions per language
  ]
}
```

---

## Page Sections (top to bottom)

### 1. Badge + Hero
- Badge: "Model Context Protocol" (green pill)
- H1: "World Geographic Data for AI Agents" (4 langs)
- Subtitle: value proposition with numbers (4 langs)

### 2. Install Command Block
```
npx bamwor-mcp-server
```

### 3. CTAs
- Primary: "Get free API key" → /{lang}/developers/quickstart
- Secondary: "GitHub" → github.com/ismaeldarosa19/bamwor-mcp-server

### 4. Data Highlights Grid (2x2 mobile, 4 cols desktop)
- 261 Countries
- 13.4M Cities
- 20+ Stats/country
- 4 Languages

### 5. "What is MCP?" Explainer Box
Blue info box explaining MCP for developers unfamiliar with the protocol.

### 6. Competitive Comparison Table
| Source | Cities | Countries | MCP | API |
|--------|--------|-----------|-----|-----|
| REST Countries | 0 | 250 | No | Free |
| CountryStateCity | 151K | 250 | No | No |
| API Ninjas | 5M | — | No | Paid |
| **Bamwor** | **13.4M** | **261** | **Yes** | **Free + Paid** |

### 7. Available Tools (5 cards)
Each card: tool name (code badge), description (4 langs), example input.

1. `get_country` — `{ query: "Brazil" }`
2. `search_countries` — `{ query: "south", limit: 10 }`
3. `search_cities` — `{ query: "Springfield", limit: 10 }`
4. `list_cities_by_country` — `{ country: "germany", min_population: 500000 }`
5. `compare_countries` — `{ country_a: "France", country_b: "Germany" }`

### 8. Installation Configs
Claude Desktop `claude_desktop_config.json` and Cursor/Windsurf config blocks.

### 9. Example Prompts Grid (2 cols, 6 items)
Natural language queries users can try with their AI assistant. 4 langs.

### 10. FAQ Accordion (6 items, 4 langs)
1. Do I need an API key?
2. Which AI clients are supported?
3. Is the data real-time?
4. What languages are supported?
5. Is there a rate limit?
6. Is this open source?

### 11. Bottom CTA
"Ready to start?" with link to quickstart.

---

## Navigation Integration (pending approval)

Add MCP Server to the developers layout nav bar:
```typescript
{
  href: '/developers/mcp',
  icon: '🤖',
  label: { en: 'MCP Server', es: 'Servidor MCP', pt: 'Servidor MCP', it: 'Server MCP' },
  color: '#e8f5e9',
  border: '#a5d6a7',
}
```
Position: before "Recover Key" in the nav items array.

---

## Integration Steps (when approved)

1. Review `web/src/app/[lang]/developers/mcp/page.tsx` (already exists as draft)
2. Review nav item change in `web/src/app/[lang]/developers/layout.tsx` (already exists as draft)
3. Run `npx tsc --noEmit` from `web/` — already verified to compile
4. No middleware changes needed (route is under existing `/developers` layout)
5. No nginx changes needed (proxied by existing rules)
6. No next.config.js changes needed
7. Deploy via standard deploy flow

---

## Texts by Language

All texts are embedded in the page component file. Full i18n records for:
- Titles, descriptions, hero subtitles
- What is MCP explainer
- Section headings (Why Bamwor, Tools, Installation, Examples, FAQ)
- Tool descriptions (5 tools x 4 langs)
- Example prompts (6 x 4 langs)
- FAQ Q&A (6 x 4 langs)
- CTA labels

Total: ~120 translated strings across 4 languages.
