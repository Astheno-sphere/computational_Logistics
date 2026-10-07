#!/usr/bin/env node
/**
 * Castlemap MCP server — a remote Model Context Protocol endpoint over the
 * castle dataset (https://thecastlemap.com/mcp).
 *
 * Zero dependencies by design: it implements the MCP Streamable HTTP
 * transport (stateless mode) directly — JSON-RPC over POST — so the VPS
 * needs nothing but Node ≥ 18 and the castles.geojson the site already
 * deploys. Read-only; no sessions, no auth, CORS open (public data, CC0).
 *
 * Spec: modelcontextprotocol.io — protocol revisions 2025-03-26 / 2025-06-18.
 *   POST /mcp  JSON-RPC request  → application/json response
 *   POST /mcp  notification      → 202 empty
 *   GET/DELETE /mcp              → 405 (no server-initiated streams)
 *
 * Two transports over the same dispatch (handleRpc), pick one:
 *   HTTP (default) — the hosted endpoint the VPS runs.
 *   stdio (--stdio) — newline-delimited JSON-RPC on stdin/stdout, for clients
 *     that spawn the server locally. Logs go to stderr there: anything on
 *     stdout that is not an MCP message corrupts the stream.
 *
 * Run:  CASTLES_GEOJSON=/var/www/castlemap/castles.geojson PORT=8891 node server.mjs
 *       CASTLES_GEOJSON=./castles.geojson node server.mjs --stdio
 */
import { createServer } from 'node:http'
import { readFileSync, statSync } from 'node:fs'

const PORT = Number(process.env.PORT || 8891)
const HOST = process.env.HOST || '127.0.0.1'
const DATA = process.env.CASTLES_GEOJSON || '/var/www/castlemap/castles.geojson'
const SITE_URL = 'https://thecastlemap.com'
const PROTOCOLS = new Set(['2025-06-18', '2025-03-26', '2024-11-05'])
const LATEST = '2025-06-18'
const VERSION = '1.1.0'
const STDIO = process.argv.includes('--stdio')

// On stdio, stdout carries the protocol — every log line must go to stderr.
const log = (...a) => (STDIO ? console.error(...a) : console.log(...a))

// ---- Dataset (reload when the deployed file changes; stat at most 1/min) ---
let castles = []
let loadedMtime = 0
let lastStat = 0
// Facts the tool descriptions quote. Derived on every load, because a hand-written
// one goes stale silently and an MCP client reads a description as ground truth:
// search_castles advertised "2,400 castles" against a dataset of 5,793, the
// instructions said 131 countries against 138, and top_castles named the Palace
// of Versailles as rank 1 after the Chinese intake had put the Great Wall above it.
let countryCount = 0
let topFamous = null
let topCountry = null
function loadData() {
  const gj = JSON.parse(readFileSync(DATA, 'utf8'))
  castles = gj.features.map((f) => {
    const p = f.properties
    const url = p.url || ''
    return {
      slug: url.replace(/\/$/, '').split('/').pop() || null,
      name: p.name,
      category: p.category,
      country: p.country,
      iso: p.iso,
      year: p.year,
      century: p.century,
      lat: f.geometry.coordinates[1],
      lon: f.geometry.coordinates[0],
      fame_rank: p.fame_rank,
      wikipedia: p.wikipedia,
      image: p.image,
      // Commons photos are CC-licensed: most licences legally require reusers
      // to name the photographer. The geojson has carried these since
      // 2026-08-08; serving the photo URL without them made attribution
      // impossible even for a client that wanted to comply.
      image_by: p.image_by,
      image_licence: p.image_licence,
      sitelinks: p.sitelinks,
      pageviews: p.pageviews,
      url,
    }
  })
  const counts = new Map()
  for (const c of castles) if (c.country) counts.set(c.country, (counts.get(c.country) ?? 0) + 1)
  countryCount = counts.size
  topCountry = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null
  topFamous = castles.find((c) => c.fame_rank === 1) ?? null
  log(`castlemap-mcp: loaded ${castles.length} castles from ${DATA}`)
}
function freshData() {
  const now = Date.now()
  if (now - lastStat < 60_000) return
  lastStat = now
  try {
    const m = statSync(DATA).mtimeMs
    if (m !== loadedMtime) {
      // Load FIRST, record the mtime only on success. The other order marked a
      // failed reload (a deploy caught mid-write) as done, and the server then
      // served the previous dataset forever — the mtime never changed again,
      // so nothing ever retried. Now a failed load leaves loadedMtime alone
      // and the next minute's stat tries again.
      loadData()
      loadedMtime = m
    }
  } catch (e) {
    console.error('castlemap-mcp: stat/reload failed:', e.message)
  }
}
loadedMtime = statSync(DATA).mtimeMs
loadData()

// ---- Tool helpers -----------------------------------------------------------
const CATEGORIES = ['castle', 'fortress', 'palace', 'ruin']
function norm(s) {
  return String(s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}
function matchesCountry(c, want) {
  if (!want) return true
  const w = norm(want)
  if (norm(c.country) === w || norm(c.iso) === w) return true
  // Partial names match only at a WORD START. A bare substring test made the
  // ISO codes the schemas invite poisonous: "US" matched aUStria and rUSsia,
  // "Oman" matched rOMANia — top_castles({country:"Oman"}) answered ten
  // Romanian landmarks before the first Omani one. Word-anchored, "korea"
  // still finds South Korea, "czech" still finds Czechia, and "oman" can no
  // longer hide inside another country's name.
  const rx = new RegExp(`(?:^|\\s)${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)
  return rx.test(norm(c.country))
}
function briefOf(c) {
  return {
    name: c.name,
    slug: c.slug,
    category: c.category,
    country: c.country,
    century: c.century,
    year: c.year,
    latitude: c.lat,
    longitude: c.lon,
    fame_rank: c.fame_rank,
    page: c.url,
    wikipedia: c.wikipedia,
  }
}
function fullOf(c) {
  // wikipedia_pageviews_60d: the enrichment stores a 60-DAY sum across the
  // landmark's largest language editions (since 2026-08-05). The field was
  // named _365d and described as annual for four days — AI clients republish
  // field names as facts, so the name must say exactly what the number is.
  return {
    ...briefOf(c),
    image: c.image,
    image_by: c.image_by,
    image_licence: c.image_licence,
    wikidata_sitelinks: c.sitelinks,
    wikipedia_pageviews_60d: c.pageviews,
  }
}
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}
function clampInt(v, def, max) {
  const n = Number.isFinite(Number(v)) ? Math.floor(Number(v)) : def
  return Math.max(1, Math.min(max, n))
}

// ---- Tools ------------------------------------------------------------------
const TOOLS = [
  {
    name: 'search_castles',
    title: 'Search castles by name',
    describe: () =>
      `Search the atlas’s ${castles.length.toLocaleString('en-US')} castles, fortresses, palaces and ruins by name (accent- and case-insensitive substring match). Optionally filter by country (name or ISO code) and category. Results come best-match-first, then by fame; each has coordinates, founding century, fame rank and links to its atlas page and Wikipedia. If nothing matches, retry with a shorter fragment of the name.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Name or part of a name, e.g. "neuschwanstein" or "himeji"' },
        country: { type: 'string', description: 'Country name or 2-letter ISO code (optional)' },
        category: { type: 'string', enum: CATEGORIES, description: 'Landmark type (optional)' },
        limit: { type: 'integer', minimum: 1, maximum: 50, description: 'Max results (default 10)' },
      },
      required: ['query'],
    },
    run(args) {
      const q = norm(args.query)
      if (!q) return { error: 'query must be a non-empty string' }
      const limit = clampInt(args.limit, 10, 50)
      const scored = []
      for (const c of castles) {
        if (!matchesCountry(c, args.country)) continue
        if (args.category && c.category !== args.category) continue
        const n = norm(c.name)
        let score = -1
        if (n === q) score = 3
        else if (n.startsWith(q)) score = 2
        else if (n.includes(q)) score = 1
        if (score < 0) continue
        scored.push([score, c.fame_rank ?? 99999, c])
      }
      scored.sort((a, b) => b[0] - a[0] || a[1] - b[1])
      return { total_matches: scored.length, results: scored.slice(0, limit).map((s) => briefOf(s[2])) }
    },
  },
  {
    name: 'get_castle',
    title: 'Get one castle in full',
    description:
      'Fetch one landmark’s full record by slug (preferred, e.g. "palace-of-versailles") or exact name: coordinates, founding year and century, worldwide fame rank, photo URL with photographer credit and licence, Wikipedia link and its readership signals (Wikidata sitelinks, Wikipedia pageviews over the last 60 days summed across its largest language editions). Unsure of the slug? Call search_castles first.',
    inputSchema: {
      type: 'object',
      properties: {
        castle: { type: 'string', description: 'Slug (preferred, e.g. "himeji-castle") or exact name' },
      },
      required: ['castle'],
    },
    run(args) {
      const want = norm(args.castle).replace(/\s+/g, '-')
      let hit = castles.find((c) => c.slug === want)
      if (!hit) {
        const wantName = norm(args.castle)
        hit = castles.find((c) => norm(c.name) === wantName)
      }
      if (!hit) return { error: `No castle matches "${args.castle}". Try search_castles first.` }
      return fullOf(hit)
    },
  },
  {
    name: 'castles_near',
    title: 'Find castles near a point',
    description:
      'List landmarks within a radius of a WGS84 coordinate, nearest first, each with distance_km. Radius defaults to 100 km (max 2,000). For "castles near <place>", geocode the place yourself, then call this with its latitude/longitude.',
    inputSchema: {
      type: 'object',
      properties: {
        latitude: { type: 'number', minimum: -90, maximum: 90 },
        longitude: { type: 'number', minimum: -180, maximum: 180 },
        radius_km: { type: 'number', minimum: 1, maximum: 2000, description: 'Search radius in km (default 100)' },
        category: { type: 'string', enum: CATEGORIES },
        limit: { type: 'integer', minimum: 1, maximum: 50, description: 'Max results (default 10)' },
      },
      required: ['latitude', 'longitude'],
    },
    run(args) {
      const lat = Number(args.latitude)
      const lon = Number(args.longitude)
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { error: 'latitude/longitude must be numbers' }
      const radius = Math.max(1, Math.min(2000, Number(args.radius_km) || 100))
      const limit = clampInt(args.limit, 10, 50)
      const hits = []
      for (const c of castles) {
        if (args.category && c.category !== args.category) continue
        const d = haversineKm(lat, lon, c.lat, c.lon)
        if (d <= radius) hits.push([d, c])
      }
      hits.sort((a, b) => a[0] - b[0])
      return {
        total_within_radius: hits.length,
        results: hits.slice(0, limit).map(([d, c]) => ({ distance_km: Math.round(d * 10) / 10, ...briefOf(c) })),
      }
    },
  },
  {
    name: 'top_castles',
    title: 'Most famous castles',
    describe: () =>
      `The most famous landmarks worldwide or in one country, ordered by Castlemap fame rank — a blend of Wikipedia coverage and readership; rank 1 is the most famous${topFamous ? ` (${topFamous.name})` : ''}. The direct answer to "most famous castles in <country>"; filter by country and/or category.`,
    inputSchema: {
      type: 'object',
      properties: {
        country: { type: 'string', description: 'Country name or ISO code (optional — omit for worldwide)' },
        category: { type: 'string', enum: CATEGORIES },
        limit: { type: 'integer', minimum: 1, maximum: 100, description: 'How many (default 10)' },
      },
    },
    run(args) {
      const limit = clampInt(args.limit, 10, 100)
      const pool = castles
        .filter((c) => c.fame_rank != null)
        .filter((c) => matchesCountry(c, args.country))
        .filter((c) => !args.category || c.category === args.category)
        .sort((a, b) => a.fame_rank - b.fame_rank)
      return { results: pool.slice(0, limit).map(briefOf) }
    },
  },
  {
    name: 'list_countries',
    title: 'Countries with castle counts',
    describe: () =>
      `Every country in the atlas with its landmark count, most first — answers "which country has the most castles"${topCountry ? ` (${topCountry} leads)` : ''}. Returns country name and ISO code per row; country pages are browsable from the countries_index URL.`,
    inputSchema: { type: 'object', properties: {} },
    run() {
      // Group by country NAME — a record with a missing ISO must not split
      // its country into two rows.
      const byCountry = new Map()
      for (const c of castles) {
        const e = byCountry.get(c.country) || { iso: c.iso, count: 0 }
        e.count++
        if (!e.iso && c.iso) e.iso = c.iso
        byCountry.set(c.country, e)
      }
      const rows = [...byCountry.entries()]
        .map(([country, e]) => ({ country, iso: e.iso, castles: e.count }))
        .sort((a, b) => b.castles - a.castles)
      return { total_countries: rows.length, countries_index: `${SITE_URL}/countries/`, results: rows }
    },
  },
  {
    name: 'get_statistics',
    title: 'Atlas statistics',
    description:
      'Headline statistics computed live from the atlas: totals by type, top countries, busiest founding century, oldest landmarks, geographic extremes and the most famous entry. The source for claims like "which country has the most castles" or "when were castles built"; the full write-up lives at thecastlemap.com/statistics/.',
    inputSchema: { type: 'object', properties: {} },
    run() {
      const byCat = {}
      for (const cat of CATEGORIES) byCat[cat] = 0
      const byCountry = new Map()
      const byCentury = new Map()
      const dated = []
      let north = null
      let south = null
      let famous = null
      for (const c of castles) {
        byCat[c.category] = (byCat[c.category] || 0) + 1
        const e = byCountry.get(c.country) || { iso: c.iso, count: 0 }
        e.count++
        if (!e.iso && c.iso) e.iso = c.iso
        byCountry.set(c.country, e)
        if (typeof c.year === 'number') {
          dated.push(c)
          if (c.century) byCentury.set(c.century, (byCentury.get(c.century) || 0) + 1)
        }
        if (!north || c.lat > north.lat) north = c
        if (!south || c.lat < south.lat) south = c
        if (c.fame_rank === 1) famous = c
      }
      dated.sort((a, b) => a.year - b.year)
      const topCountries = [...byCountry.entries()]
        .map(([country, e]) => ({ country, iso: e.iso, landmarks: e.count }))
        .sort((a, b) => b.landmarks - a.landmarks)
        .slice(0, 10)
      const busiest = [...byCentury.entries()].sort((a, b) => b[1] - a[1])[0]
      const brief = (c) => c && { name: c.name, country: c.country, page: c.url }
      return {
        landmarks: castles.length,
        by_type: byCat,
        countries: byCountry.size,
        top_countries: topCountries,
        dated_entries: dated.length,
        busiest_founding_century: busiest ? { century: busiest[0], entries: busiest[1] } : null,
        median_founding_year: dated.length ? dated[Math.floor(dated.length / 2)].year : null,
        oldest: dated.slice(0, 3).map((c) => ({ ...brief(c), founded: c.year })),
        northernmost: north && { ...brief(north), latitude: north.lat },
        southernmost: south && { ...brief(south), latitude: south.lat },
        most_famous: brief(famous),
        full_statistics: `${SITE_URL}/statistics/`,
      }
    },
  },
  {
    name: 'random_castle',
    title: 'A random castle',
    description:
      'One random landmark with its full record, optionally limited to a country — for discovery, quizzes and "castle of the day" features.',
    inputSchema: {
      type: 'object',
      properties: { country: { type: 'string', description: 'Country name or ISO code (optional)' } },
    },
    run(args) {
      const pool = castles.filter((c) => matchesCountry(c, args.country))
      if (!pool.length) return { error: `No castles found for "${args.country}"` }
      return fullOf(pool[Math.floor(Math.random() * pool.length)])
    },
  },
]
const TOOL_BY_NAME = new Map(TOOLS.map((t) => [t.name, t]))

// ---- JSON-RPC dispatch ------------------------------------------------------
function handleRpc(msg) {
  const { method, params, id } = msg
  // initialize and tools/list quote live counts, so they need the same freshness
  // check tools/call has always had — otherwise a redeploy leaves every client
  // that connected before it holding numbers from the previous dataset.
  if (method === 'initialize' || method === 'tools/list') freshData()
  if (method === 'initialize') {
    const asked = params?.protocolVersion
    return {
      protocolVersion: PROTOCOLS.has(asked) ? asked : LATEST,
      capabilities: { tools: {} },
      serverInfo: { name: 'castlemap', title: 'Castlemap — the world’s great castles', version: VERSION },
      instructions:
        `Read-only tools over the Castlemap atlas: ${castles.length.toLocaleString('en-US')} curated castles, fortresses, palaces and ruins ` +
        `across ${countryCount} countries (facts from Wikidata, CC0). Every result links its page on ${SITE_URL}. ` +
        `Use search_castles / get_castle for lookups, castles_near for geography (geocode the place first), ` +
        `top_castles for fame, get_statistics for aggregate claims (counts by country/century, oldest, extremes), ` +
        `list_countries for coverage and random_castle for discovery.`,
    }
  }
  if (method === 'ping') return {}
  if (method === 'tools/list') {
    return {
      tools: TOOLS.map(({ name, title, description, describe, inputSchema }) => ({
        name,
        title,
        // A tool that quotes a live count builds its description per call.
        description: describe ? describe() : description,
        inputSchema,
      })),
    }
  }
  if (method === 'tools/call') {
    const tool = TOOL_BY_NAME.get(params?.name)
    if (!tool) return { __rpcError: { code: -32602, message: `Unknown tool: ${params?.name}` } }
    freshData()
    let out
    try {
      out = tool.run(params?.arguments ?? {})
    } catch (e) {
      return { content: [{ type: 'text', text: `Tool failed: ${e.message}` }], isError: true }
    }
    const isError = Boolean(out && typeof out === 'object' && 'error' in out)
    return { content: [{ type: 'text', text: JSON.stringify(out, null, 1) }], isError }
  }
  return { __rpcError: { code: -32601, message: `Method not found: ${method}` } }
}

// ---- HTTP transport (stateless streamable-http) -----------------------------
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, Authorization, Mcp-Protocol-Version, Mcp-Session-Id, Last-Event-ID',
  'Access-Control-Expose-Headers': 'Mcp-Protocol-Version, Mcp-Session-Id',
  'Access-Control-Max-Age': '86400',
}
function send(res, status, body, extra = {}) {
  const headers = { ...CORS, ...extra }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  res.writeHead(status, headers)
  res.end(body === undefined ? undefined : JSON.stringify(body))
}

const server = createServer((req, res) => {
  const url = (req.url || '').split('?')[0]
  if (url !== '/mcp' && url !== '/') return send(res, 404, { error: 'not found — MCP endpoint is /mcp' })
  if (req.method === 'OPTIONS') return send(res, 204, undefined)
  if (req.method !== 'POST')
    return send(res, 405, { jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed — POST JSON-RPC to this endpoint' }, id: null }, { Allow: 'POST, OPTIONS' })

  // Collect raw Buffers and decode ONCE at the end: `body += chunk` coerces
  // each chunk to a string separately, and a multi-byte UTF-8 character split
  // across a chunk boundary decodes as U+FFFD garbage — a parse error for the
  // client on any request whose non-ASCII castle name straddles 64 KiB reads.
  const chunks = []
  let size = 0
  let overflow = false
  req.on('data', (chunk) => {
    size += chunk.length
    if (size > 65536) {
      overflow = true
      req.destroy()
      return
    }
    chunks.push(chunk)
  })
  req.on('end', () => {
    if (overflow) return
    let msg
    try {
      msg = JSON.parse(Buffer.concat(chunks).toString('utf8'))
    } catch {
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32700, message: 'Parse error' }, id: null })
    }
    if (Array.isArray(msg))
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32600, message: 'Batching is not supported (protocol 2025-06-18)' }, id: null })
    if (!msg || msg.jsonrpc !== '2.0')
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

    // Requests carry an id + method; notifications have a method but NO id
    // MEMBER; responses have result/error but no method. Per the streamable-
    // http transport, notifications and responses get 202 with no body.
    // A notification is the ABSENCE of the id member, not a null id: JSON-RPC
    // 2.0 discourages `id: null` on requests but it is still a request, and
    // answering it 202 left the client waiting on a response that never came.
    const hasId = 'id' in msg
    const isNotification = typeof msg.method === 'string' && !hasId
    const isResponse = msg.method === undefined && (msg.result !== undefined || msg.error !== undefined)
    if (isNotification || isResponse) return send(res, 202, undefined)
    if (typeof msg.method !== 'string' || !hasId)
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

    const t0 = Date.now()
    const result = handleRpc(msg)
    const took = Date.now() - t0
    log(`castlemap-mcp: ${msg.method}${msg.params?.name ? ' ' + msg.params.name : ''} (${took}ms)`)
    if (result && result.__rpcError) return send(res, 200, { jsonrpc: '2.0', error: result.__rpcError, id: msg.id })
    return send(res, 200, { jsonrpc: '2.0', result, id: msg.id })
  })
})
// ---- stdio transport (newline-delimited JSON-RPC on stdin/stdout) -----------
// Clients that spawn the server locally speak this instead of HTTP. Same
// dispatch, same semantics: notifications and responses draw no reply at all
// (the stdio equivalent of the 202 above).
function writeStdio(msg) {
  process.stdout.write(JSON.stringify(msg) + '\n')
}
function handleStdioLine(line) {
  let msg
  try {
    msg = JSON.parse(line)
  } catch {
    return writeStdio({ jsonrpc: '2.0', error: { code: -32700, message: 'Parse error' }, id: null })
  }
  if (Array.isArray(msg))
    return writeStdio({ jsonrpc: '2.0', error: { code: -32600, message: 'Batching is not supported (protocol 2025-06-18)' }, id: null })
  if (!msg || msg.jsonrpc !== '2.0')
    return writeStdio({ jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

  // Same id semantics as the HTTP transport: a notification is the absent id
  // MEMBER; `id: null` is a (discouraged) request and gets a response.
  const hasId = 'id' in msg
  const isNotification = typeof msg.method === 'string' && !hasId
  const isResponse = msg.method === undefined && (msg.result !== undefined || msg.error !== undefined)
  if (isNotification || isResponse) return
  if (typeof msg.method !== 'string' || !hasId)
    return writeStdio({ jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

  const t0 = Date.now()
  const result = handleRpc(msg)
  log(`castlemap-mcp: ${msg.method}${msg.params?.name ? ' ' + msg.params.name : ''} (${Date.now() - t0}ms)`)
  if (result && result.__rpcError) return writeStdio({ jsonrpc: '2.0', error: result.__rpcError, id: msg.id })
  writeStdio({ jsonrpc: '2.0', result, id: msg.id })
}
function serveStdio() {
  let buf = ''
  process.stdin.setEncoding('utf8')
  process.stdin.on('data', (chunk) => {
    buf += chunk
    let nl
    while ((nl = buf.indexOf('\n')) !== -1) {
      const line = buf.slice(0, nl).trim()
      buf = buf.slice(nl + 1)
      if (line) handleStdioLine(line)
    }
  })
  process.stdin.on('end', () => process.exit(0))
  log(`castlemap-mcp: serving stdio (${castles.length} castles)`)
}

if (STDIO) serveStdio()
else server.listen(PORT, HOST, () => log(`castlemap-mcp: listening on http://${HOST}:${PORT}/mcp`))
