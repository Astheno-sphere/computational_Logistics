#!/usr/bin/env node
/**
 * FilmMap MCP server — a remote Model Context Protocol endpoint over the
 * filming-location atlas (https://thefilmmap.com/mcp).
 *
 * Zero dependencies by design (the pattern is shared with the sister atlases):
 * it implements the MCP Streamable HTTP transport (stateless mode) directly —
 * JSON-RPC over POST — so the VPS needs nothing but Node ≥ 18 and the
 * atlas-compact.json the site already deploys under /data/. Read-only; no
 * sessions, no auth, CORS open (facts from Wikidata, CC0).
 *
 * Spec: modelcontextprotocol.io — protocol revisions 2025-03-26 / 2025-06-18.
 *   POST /mcp  JSON-RPC request  → application/json response
 *   POST /mcp  notification      → 202 empty
 *   GET/DELETE /mcp              → 405 (no server-initiated streams)
 *
 * ⚠ THE ONE RULE THIS FILE EXISTS TO PROTECT. A film or a series is placed by
 * where it was **filmed** (Wikidata P915). A video game is filmed nowhere, and
 * neither is an anime or a manga, so all three are placed by where they are
 * **set** (P840). An
 * assistant that reads one of those pins
 * as a filming location publishes a false claim, and it will only know the
 * difference if we tell it — so every record this server returns carries an
 * explicit `relation` field, every tool description says it, and the
 * `initialize` instructions say it first. Do not "simplify" that away.
 *
 * Two transports over the same dispatch (handleRpc), pick one:
 *   HTTP (default) — the hosted endpoint the VPS runs.
 *   stdio (--stdio) — newline-delimited JSON-RPC on stdin/stdout, for clients
 *     that spawn the server locally. Logs go to stderr there: anything on
 *     stdout that is not an MCP message corrupts the stream.
 *
 * Run:  ATLAS_JSON=/var/www/screenatlas/data/atlas-compact.json PORT=8896 node server.mjs
 *       ATLAS_JSON=./atlas-compact.json node server.mjs --stdio
 */
import { createServer } from 'node:http'
import { readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const PORT = Number(process.env.PORT || 8896)
const HOST = process.env.HOST || '127.0.0.1'
// Data file: env override, else the VPS path, else the built copy in dist/ so
// `node mcp/server.mjs` works straight out of a clone after a build.
const DATA_CANDIDATES = [
  process.env.ATLAS_JSON,
  '/var/www/screenatlas/data/atlas-compact.json',
  fileURLToPath(new URL('../dist/data/atlas-compact.json', import.meta.url)),
].filter(Boolean)
const exists = (p) => {
  try {
    statSync(p)
    return true
  } catch {
    return false
  }
}
const DATA = DATA_CANDIDATES.find(exists) ?? DATA_CANDIDATES[0]
const SITE_URL = 'https://thefilmmap.com'
const PROTOCOLS = new Set(['2025-06-18', '2025-03-26', '2024-11-05'])
const LATEST = '2025-06-18'
// 1.1.0 (2026-08-21): place records carry the photograph's author and licence
// when atlas-compact.json ships `photoCredits` (scripts/fetch-photo-credits.mjs).
// Keep equal to "version" in mcp/server.json — the registry keys on it.
const VERSION = '1.1.0'
const STDIO = process.argv.includes('--stdio')

// On stdio, stdout carries the protocol — every log line must go to stderr.
const log = (...a) => (STDIO ? console.error(...a) : console.log(...a))

/* ── Mirrors of src/data/locationsCore.ts — keep in sync ────────────────────
 * Duplicated rather than imported because this file runs on the VPS with no
 * build step and no TypeScript. Every value below is a copy; if one changes
 * there, change it here. The same trade the sibling atlases make.
 */
const CATEGORIES = {
  studio: { label: 'Studios & sets', slug: 'studios' },
  castle: { label: 'Castles & palaces', slug: 'castles' },
  landmark: { label: 'Landmarks & buildings', slug: 'landmarks' },
  street: { label: 'Streets & squares', slug: 'streets' },
  nature: { label: 'Landscapes & nature', slug: 'landscapes' },
  city: { label: 'Towns & cities', slug: 'towns' },
  region: { label: 'Countries & regions', slug: 'regions' },
  // Mirrors CATEGORY_META in src/data/locationsCore.ts and was missing until
  // 2026-08-30, which cost two things: `by_category` in get_statistics is built
  // from these keys, so 31 locations were absent from a breakdown that is meant
  // to account for all of them, and search_locations rejected `fiction` as an
  // unknown category while the atlas ships 31 of them and a /fictional/ hub.
  fiction: { label: 'Fictional places', slug: 'fictional' },
}
const CATEGORY_KEYS = Object.keys(CATEGORIES)
const CATEGORY_BY_ANY = new Map()
for (const [key, m] of Object.entries(CATEGORIES)) {
  CATEGORY_BY_ANY.set(key, key)
  CATEGORY_BY_ANY.set(m.slug, key)
}
const MEDIUM_LABEL = { film: 'film', tv: 'series', game: 'video game', anime: 'anime', manga: 'manga' }
/**
 * Fame bands, read from the data file rather than restated here.
 *
 * They used to be three literals in this line, copied from locationsCore, and
 * they were a rank cut: `rank <= 100 ? 'iconic' : …`. Two things were wrong with
 * that. The copy went stale the moment the site's bands changed, so this server
 * would have answered `iconic` for places the site called `renowned`; and a rank
 * cut moves under you every time the atlas grows, which is why the site stopped
 * using one on 2026-08-08. The band is now a language count on the best
 * production at the place, and the thresholds ride along in atlas-compact.json.
 *
 * ⚠ The fallback below is NOT the old rank shape, and must never be "restored"
 * to it. It is today's star thresholds, repeated here only for the window
 * between installing this file and shipping a data file that carries the field.
 * The old cuts were 100 / 400 / 1,200 and they were RANKS; feeding a rank
 * boundary to `tierOf`, which now receives a language count, would band every
 * location in the atlas wrong and quietly.
 */
const FALLBACK_TIERS = { iconic: 85, renowned: 60, notable: 38, deepcut: 0 }
let tierCuts = FALLBACK_TIERS
const tierOf = (star) =>
  star >= tierCuts.iconic ? 'iconic' : star >= tierCuts.renowned ? 'renowned' : star >= tierCuts.notable ? 'notable' : 'deepcut'
const starOf = (loc) => {
  let best = 0
  for (const t of loc.titles) if ((t.sitelinks ?? 0) > best) best = t.sitelinks ?? 0
  for (const t of loc.wikiTitles) if ((t.sitelinks ?? 0) > best) best = t.sitelinks ?? 0
  return best
}
const COUNTRY_DISPLAY = {
  "People's Republic of China": 'China',
  'Kingdom of the Netherlands': 'Netherlands',
  'Republic of Ireland': 'Ireland',
}
const CHAR_MAP = { ı: 'i', ø: 'o', đ: 'd', ß: 'ss', æ: 'ae', œ: 'oe', ł: 'l', þ: 'th', ð: 'd', ŋ: 'n' }
const slugify = (v) =>
  String(v)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[ıøđßæœłþðŋ]/g, (ch) => CHAR_MAP[ch] ?? ch)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
const COMMONS = 'https://commons.wikimedia.org/wiki/Special:FilePath/'
const ENWIKI = 'https://en.wikipedia.org/wiki/'
// Two columns store '' for "derive it from the name"; on wiki, null additionally
// means "there is no article", which is why they cannot share a sentinel.
const thickSlug = (stored, name) => stored || slugify(name)
const thickWiki = (stored, name) => (stored === null ? null : `${ENWIKI}${stored || name.replace(/ /g, '_')}`)
/**
 * Where a Wikipedia-evidence claim came from, and the link that backs it.
 *
 * ⚠ A hand copy of `wikiEvidence*` in src/data/locationsCore.ts, because this
 * server is deliberately dependency-free — it reads the published JSON and
 * imports nothing from the app. Keep the two in step; the grammar is documented
 * once, there. `#en:` / `#ja:` lead a setting category; the wiki prefix is part
 * of the test because a section heading really can begin with a bare `#`.
 */
const wikiCat = (section) =>
  /^#(en|ja):/.test(section ?? '')
    ? { wiki: section.slice(1, 3), name: section.slice(4) === '*' ? null : section.slice(4) }
    : null
const wikiEvidencePhrase = (t) => {
  const cat = wikiCat(t.wikiSection)
  if (cat) {
    const where = cat.wiki === 'ja' ? 'Japanese Wikipedia' : 'Wikipedia'
    return cat.name ? `${where}'s "${cat.name}" category` : `${where}'s setting categories`
  }
  return t.wikiSection ? `its article's "${t.wikiSection.replace(/_/g, ' ')}" section` : 'its article'
}
const wikiEvidenceHref = (t) => {
  const cat = wikiCat(t.wikiSection)
  if (cat) {
    if (!cat.name) return cat.wiki === 'en' ? t.wiki : null
    const base = cat.wiki === 'en' ? 'https://en.wikipedia.org' : 'https://ja.wikipedia.org'
    return `${base}/wiki/${encodeURIComponent(`Category:${cat.name}`.replace(/ /g, '_'))}`
  }
  if (!t.wiki || !t.wikiSection) return t.wiki
  // `#`, `%` and `?` cannot travel raw inside a fragment — the hand copy of
  // fragmentOf() in src/data/locationsCore.ts; keep the two in step.
  return `${t.wiki}#${t.wikiSection.replace(/%/g, '%25').replace(/#/g, '%23').replace(/\?/g, '%3F')}`
}

/** A game, an anime or a manga is SET here; everything else was FILMED here. The
 *  single test, and it is the one thing in this file that must never drift: all
 *  three are drawn or rendered, so none was filmed anywhere. */
const isGame = (t) => t.kind === 'game' || t.kind === 'anime' || t.kind === 'manga'

/** The URL segment for a production, which is per MEDIUM rather than per claim:
 *  /game/, /anime/, /manga/ and /film/ are four different namespaces. */
const pageSegment = (t) =>
  t.kind === 'game' ? 'game' : t.kind === 'anime' ? 'anime' : t.kind === 'manga' ? 'manga' : 'film'
/**
 * The claim each place record makes. A third value since 2026-08-03: an anime
 * Wikidata places nowhere, whose places are its adapted source's. An agent that
 * quotes one of these must say so, which is why the value spells it out rather
 * than hiding behind a separate boolean.
 */
const relationOf = (t) => (t.originWork ? 'set in, per its source work' : isGame(t) ? 'set in' : 'filmed at')

/**
 * The first sentence of a set-in record's note, per medium.
 *
 * ⚠ It was `This is a ${kind === 'anime' ? 'an anime, which is drawn' : 'video
 * game'}`, which read "This is a an anime" on every anime the endpoint has ever
 * returned, and called a manga a video game the day manga shipped. An article
 * and a clause do not survive being interpolated into one frame; each medium
 * gets its own sentence.
 */
const setInIntro = (t) =>
  t.kind === 'game'
    ? 'This is a video game, which is rendered rather than filmed.'
    : t.kind === 'anime'
      ? 'This is an anime, which is drawn.'
      : 'This is a manga, which is drawn.'

/** The caveat that has to travel with a source-work record, wherever it lands. */
const sourceNote = (t) =>
  t.originWork
    ? `Wikidata records no setting for "${t.name}". Every place listed for it is where its source, ` +
      `"${t.originWork}", is recorded as set. That is a statement about the source, not about this ` +
      `production, and an adaptation is free to move its story. Say "per its source work" when you quote one.`
    : null

/* ── Dataset (reload when the deployed file changes; stat at most 1/min) ──── */
let locations = []
let titles = []
let descriptions = { locations: {}, titles: {} }
/** Commons file name (as stored in the `img` column) → { by, lic, url }.
 *  Absent from data files built before 2026-08-21; every lookup tolerates that. */
let photoCredits = {}
let countryCount = 0
let loadedMtime = 0
let lastStat = 0

function loadData() {
  const raw = JSON.parse(readFileSync(DATA, 'utf8'))
  const idx = (cols) => Object.fromEntries(cols.map((n, i) => [n, i]))

  const lc = idx(raw.locations.columns)
  locations = raw.locations.rows.map((r, i) => {
    const name = r[lc.name]
    const rawCountry = r[lc.country] ?? null
    const img = r[lc.img]
    // Row order is the pre-drop fame order; `ranks` is recomputed after the
    // drawn-prose drop and shipped alongside, so it is the one to trust when
    // present. Falling back to the row index keeps an older data file working.
    const rank = raw.ranks?.[i] ?? i + 1
    return {
      qid: r[lc.id],
      name,
      category: r[lc.cat],
      lon: r[lc.lon],
      lat: r[lc.lat],
      country: rawCountry ? COUNTRY_DISPLAY[rawCountry] ?? rawCountry : null,
      iso: r[lc.iso] ?? null,
      // 500, not 640: Special:FilePath snaps the width UP to a size it keeps,
      // and 640 lands on 960 — three times the bytes for the same picture. The
      // ladder is 250, 330, 500, 960, 1280 (measured 2026-08-18). See the note
      // on commonsThumb in src/data/locationsCore.ts.
      img: img ? `${COMMONS}${img}?width=500` : null,
      // The stored file name, kept verbatim because it is the key into
      // `photoCredits` — rebuilding it from the URL would mean un-encoding
      // what the pipeline encoded, and the two would drift on the first odd
      // character.
      imgKey: img ?? null,
      wiki: thickWiki(r[lc.wiki], name),
      slug: thickSlug(r[lc.slug], name),
      titleIdx: r[lc.t],
      titles: [],
      // The Wikipedia-evidence column — absent from pre-2026-08-02 files.
      wikiTitleIdx: lc.wt !== undefined ? r[lc.wt] : [],
      wikiTitles: [],
      /**
       * ⚠ The invented place, and the real one whose coordinates it borrows.
       *
       * This server was returning Los Santos at 34.05, -118.24 with nothing
       * saying those are Los Angeles's coordinates and that Los Santos does not
       * exist — a two-hop claim presented as one hop, which the site's own rule
       * forbids and every other surface obeys. It went unnoticed while eleven
       * pins used the route; the 2026-08-03 fix took it to 29 and brought the
       * whole Grand Theft Auto series with it, so an assistant asking this
       * server where GTA V is set got a straight answer of "Los Angeles" with
       * no invented city in sight.
       */
      via: lc.via !== undefined ? (r[lc.via] ?? null) : null,
      titleCount: r[lc.n],
      rank,
      // Set below, once the titles are attached — the band is a fact about them.
      tier: 'deepcut',
    }
  })

  const tc = idx(raw.titles.columns)
  // The series side table `sx` indexes into — absent in older files.
  const seriesTable = (raw.titles.series?.rows ?? []).map((r) => {
    const sc = idx(raw.titles.series.columns)
    return { name: r[sc.name], slug: r[sc.slug], members: r[sc.n] ?? 0 }
  })
  titles = raw.titles.rows.map((r) => {
    const name = r[tc.name]
    return {
      qid: r[tc.id],
      name,
      year: r[tc.year] ?? null,
      endYear: r[tc.end] ?? null,
      kind: r[tc.kind],
      wiki: thickWiki(r[tc.wiki], name),
      slug: thickSlug(r[tc.slug], name),
      sitelinks: r[tc.sl],
      locationIdx: r[tc.l],
      locations: [],
      regions: (r[tc.r] ?? []).map((n) => COUNTRY_DISPLAY[n] ?? n),
      wikiLocationIdx: tc.wl !== undefined ? r[tc.wl] : [],
      wikiLocations: [],
      // The source-work route. Null on all but a handful of anime; when it is
      // set, EVERY entry in `locations` came from that work. See relationOf.
      originWork: tc.os !== undefined ? (r[tc.os] ?? null) : null,
      originWiki:
        tc.os === undefined || r[tc.os] === null
          ? null
          : (tc.ow === undefined ? null : r[tc.ow]) || String(r[tc.os]).replace(/ /g, '_'),
      // '*' means the links came from several sections, so there is no single
      // anchor — null, and never a guess of "Filming". See Title.wikiSection.
      wikiSection:
        tc.ws === undefined || r[tc.ws] === null || r[tc.ws] === '*'
          ? null
          : r[tc.ws] || 'Filming',
      series: tc.sx === undefined ? [] : (r[tc.sx] ?? []).map((i) => seriesTable[i]).filter(Boolean),
    }
  })

  tierCuts = raw.fameTiers
    ? {
        iconic: raw.fameTiers.iconic.minStar,
        renowned: raw.fameTiers.renowned.minStar,
        notable: raw.fameTiers.notable.minStar,
        deepcut: raw.fameTiers.deepcut.minStar,
      }
    : FALLBACK_TIERS
  for (const loc of locations) {
    loc.titles = loc.titleIdx.map((i) => titles[i]).filter(Boolean)
    loc.wikiTitles = loc.wikiTitleIdx.map((i) => titles[i]).filter(Boolean)
    loc.tier = tierOf(starOf(loc))
  }
  for (const t of titles) {
    t.locations = t.locationIdx.map((i) => locations[i]).filter(Boolean)
    t.wikiLocations = t.wikiLocationIdx.map((i) => locations[i]).filter(Boolean)
  }

  descriptions = raw.descriptions ?? { locations: {}, titles: {} }
  photoCredits = raw.photoCredits ?? {}
  // Counted from the decoded rows, never from the file's own `countries` field.
  // That field counts RAW country names; `loc.country` above has already been
  // through COUNTRY_DISPLAY, which folds `Kingdom of the Netherlands` into
  // `Netherlands`. Preferring the field made this server answer 162 where the
  // site answers 161, for the same one country under two Wikidata labels.
  countryCount = new Set(locations.map((l) => l.country).filter(Boolean)).size
  log(
    `filmmap-mcp: loaded ${locations.length} locations and ${titles.length} productions from ${DATA}`,
  )
}
function freshData() {
  const now = Date.now()
  if (now - lastStat < 60_000) return
  lastStat = now
  try {
    const m = statSync(DATA).mtimeMs
    if (m !== loadedMtime) {
      loadedMtime = m
      loadData()
    }
  } catch (e) {
    console.error('filmmap-mcp: stat/reload failed:', e.message)
  }
}
loadedMtime = statSync(DATA).mtimeMs
loadData()

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function norm(s) {
  return String(s ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
}
function matchesCountry(loc, want) {
  if (!want) return true
  const w = norm(want)
  return norm(loc.country) === w || norm(loc.iso) === w || norm(loc.country).includes(w)
}
function categoryOf(arg) {
  if (!arg) return null
  return CATEGORY_BY_ANY.get(String(arg).toLowerCase().trim()) ?? undefined // undefined = unknown
}
function clampInt(v, def, max) {
  const n = Number.isFinite(Number(v)) ? Math.floor(Number(v)) : def
  return Math.max(1, Math.min(max, n))
}
function yearLabel(t) {
  if (!t.year) return null
  if (t.kind !== 'tv') return String(t.year)
  return t.endYear ? `${t.year}–${t.endYear}` : `${t.year}–`
}
/** A place, as it appears inside a production's answer and in lists. */
function placeBrief(loc) {
  return {
    name: loc.name,
    slug: loc.slug,
    category: loc.category,
    category_label: CATEGORIES[loc.category]?.label ?? loc.category,
    /**
     * How much of a place this pin actually is. `region` is the one an
     * assistant must never round up to a location: it is a whole country or
     * state standing in for itself, it only ever carries video-game settings,
     * and its coordinate is a centroid rather than somewhere anything happened.
     */
    precision:
      loc.category === 'city'
        ? 'town level'
        : loc.category === 'region'
          ? 'whole country or region, centroid only'
          : loc.via
            ? 'invented place, on borrowed coordinates'
            : 'exact site',
    country: loc.country,
    latitude: loc.lat,
    longitude: loc.lon,
    /* The invented place and what it stands on. See the `via` note at the
     * decode: without these two fields the coordinates below read as this
     * place's own, and they are not. */
    ...(loc.via
      ? {
          fictional: true,
          stands_on: loc.via,
          fictional_note:
            `"${loc.name}" does not exist. Wikidata records it as based on, or inside, ${loc.via}, ` +
            `and the coordinates here are ${loc.via}'s. Say that it is a fictional place standing on ` +
            `${loc.via}; never report it as somewhere a visitor can go, and never report ${loc.via} as ` +
            `the recorded setting, because that is not what the statement says.`,
        }
      : {}),
    productions: loc.titleCount,
    fame_rank: loc.rank,
    fame_tier: loc.tier,
    page: `${SITE_URL}/locations/${loc.slug}/`,
  }
}
function placeFull(loc) {
  const credit = loc.imgKey ? photoCredits[loc.imgKey] : null
  return {
    ...placeBrief(loc),
    description: descriptions.locations[loc.qid] ?? null,
    image: loc.img,
    /* Who took the photograph and under which licence, from Wikimedia Commons.
     * Most of these licences make naming the author a condition of reuse, so
     * anything that reprints `image` should reprint these two beside it. Null
     * when Commons records none, or when the data file predates the field. */
    image_by: credit?.by ?? null,
    image_licence: credit?.lic ?? null,
    image_licence_url: credit?.url ?? null,
    image_page: loc.imgKey ? `https://commons.wikimedia.org/wiki/File:${loc.imgKey}` : null,
    wikipedia: loc.wiki,
    wikidata: `https://www.wikidata.org/wiki/${loc.qid}`,
    map: `${SITE_URL}/#loc=${loc.slug}`,
  }
}
/** A production, as it appears inside a place's answer and in lists. */
function titleBrief(t) {
  return {
    name: t.name,
    slug: t.slug,
    kind: t.kind,
    kind_label: MEDIUM_LABEL[t.kind] ?? t.kind,
    relation: relationOf(t),
    year: yearLabel(t),
    located_places: t.locations.length,
    ...(t.series.length ? { series: t.series.map((s) => s.name) } : {}),
    page: `${SITE_URL}/${pageSegment(t)}/${t.slug}/`,
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
/** Resolve a production from a slug (preferred) or an exact/near name. */
function findTitle(arg) {
  const want = norm(arg)
  const asSlug = want.replace(/\s+/g, '-')
  return (
    titles.find((t) => t.slug === asSlug) ||
    titles.find((t) => norm(t.name) === want) ||
    // Slugs carry a Q-id when a name has a namesake ("arthur-q627438"), so an
    // exact slug lookup misses on the plain name. Fall back to the most widely
    // covered namesake rather than to nothing.
    titles.filter((t) => t.slug.startsWith(`${asSlug}-q`)).sort((a, b) => b.sitelinks - a.sitelinks)[0] ||
    null
  )
}
function findLocation(arg) {
  const want = norm(arg)
  const asSlug = want.replace(/\s+/g, '-')
  return (
    locations.find((l) => l.slug === asSlug) ||
    locations.find((l) => norm(l.name) === want) ||
    locations.filter((l) => l.slug.startsWith(`${asSlug}-q`)).sort((a, b) => a.rank - b.rank)[0] ||
    null
  )
}
const CATEGORY_ENUM_DESC =
  'Kind of place — key or slug: ' + CATEGORY_KEYS.map((k) => `${k} (${CATEGORIES[k].label})`).join(', ')
/** How many pins are whole jurisdictions rather than filming locations. */
const regionCount = () => locations.reduce((n, l) => n + (l.category === 'region' ? 1 : 0), 0)

/* ── Tools ────────────────────────────────────────────────────────────────── */
const TOOLS = [
  {
    name: 'where_was_it_filmed',
    title: 'Where a film, series or game was filmed',
    // {{FILMS}} / {{LOCATIONS}} are substituted from the loaded dataset on every
    // tools/list rather than baked in, because a baked number goes stale on the
    // next data refresh and every client that connects is then told a wrong
    // figure. The sibling atlas learned this the expensive way.
    description:
      'The main tool. Give a film or television title and get every place Wikidata records it as filmed at, with coordinates, plus the countries it records too coarsely to place. Covers {{FILMS}} productions across {{LOCATIONS}} places. ' +
      'Two things to carry into any answer you write. First, video games AND anime are in here as well, and neither is filmed anywhere: their places are where they are SET (Wikidata P840, not P915), and every record says which through its `relation` field — never call one of those a filming location. ' +
      'Second, the gaps are real information: when `countries_only` is populated, Wikidata knows the production shot in those countries but not where, and the honest answer says so rather than guessing a street. This atlas never records which scene was shot where, so do not infer it.',
    inputSchema: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Title, or its slug, e.g. "Skyfall", "game-of-thrones", "The Third Man"',
        },
        limit: { type: 'integer', minimum: 1, maximum: 200, description: 'Max places (default 50)' },
      },
      required: ['title'],
    },
    run(args) {
      if (!args.title) return { error: 'title must be a non-empty string' }
      const t = findTitle(args.title)
      if (!t) return { error: `No production matches "${args.title}". Try search_productions first.` }
      const limit = clampInt(args.limit, 50, 200)
      return {
        name: t.name,
        kind: t.kind,
        kind_label: MEDIUM_LABEL[t.kind] ?? t.kind,
        relation: relationOf(t),
        note: t.originWork
          ? sourceNote(t)
          : isGame(t)
            ? `${setInIntro(t)} It was filmed nowhere; the places below are where it is SET${
                t.locations.length ? ', from Wikidata narrative location (P840)' : ''
              }.`
            : 'The places below are Wikidata filming location (P915) statements. Which scene was shot where is not recorded and must not be inferred.',
        ...(t.originWork
          ? {
              source_work: t.originWork,
              ...(t.originWiki ? { source_work_wikipedia: `https://en.wikipedia.org/wiki/${t.originWiki}` } : {}),
            }
          : {}),
        year: yearLabel(t),
        description: descriptions.titles[t.qid] ?? null,
        ...(t.series.length
          ? {
              series: t.series.map((s) => ({
                name: s.name,
                ...(s.members >= 2 ? { page: `${SITE_URL}/series/${s.slug}/` } : {}),
              })),
            }
          : {}),
        located_places: t.locations.length,
        places: t.locations.slice(0, limit).map(placeBrief),
        wiki_places: t.wikiLocations.slice(0, limit).map(placeBrief),
        wiki_places_note: t.wikiLocations.length
          ? `These ${t.wikiLocations.length} places come from Wikipedia — ${wikiEvidencePhrase(t)} — NOT from Wikidata statements: weaker evidence, listed apart. ${isGame(t) ? `They are where the ${MEDIUM_LABEL[t.kind]} is SET, not where anything was filmed. ` : ''}Source: ${wikiEvidenceHref(t) ?? 'the article'}. Say "per Wikipedia" when you quote one.`
          : undefined,
        countries_only: t.regions,
        countries_only_note: t.regions.length
          ? 'Wikidata records the production in these places at a resolution too coarse to put on a map. They are not pinned, and nothing finer is known.'
          : undefined,
        wikipedia: t.wiki,
        wikidata: `https://www.wikidata.org/wiki/${t.qid}`,
        page: `${SITE_URL}/${pageSegment(t)}/${t.slug}/`,
        map: `${SITE_URL}/#title=${t.slug}`,
      }
    },
  },
  {
    name: 'search_productions',
    title: 'Search films, series and games by name',
    description:
      'Find productions by name (accent- and case-insensitive substring match), best match first then by how widely Wikipedia covers them. Filter by kind: film, tv, game or anime. Use it when you are unsure of a title before calling where_was_it_filmed. Games and anime are placed by where they are SET, never where they were filmed; the `relation` field on every result says which.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Title or part of one, e.g. "bond", "star wars"' },
        // `manga` belongs here: 366 of them ship, and leaving it out made a
        // medium the atlas publishes an invalid input to this tool.
        kind: { type: 'string', enum: ['film', 'tv', 'game', 'anime', 'manga'], description: 'Restrict to one medium (optional)' },
        limit: { type: 'integer', minimum: 1, maximum: 50, description: 'Max results (default 10)' },
      },
      required: ['query'],
    },
    run(args) {
      const q = norm(args.query)
      if (!q) return { error: 'query must be a non-empty string' }
      const kind = args.kind ? String(args.kind).toLowerCase() : null
      if (kind && !['film', 'tv', 'game', 'anime'].includes(kind))
        return { error: `Unknown kind "${args.kind}". Valid: film, tv, game, anime` }
      const limit = clampInt(args.limit, 10, 50)
      const scored = []
      for (const t of titles) {
        if (kind && t.kind !== kind) continue
        const n = norm(t.name)
        let score = -1
        if (n === q) score = 3
        else if (n.startsWith(q)) score = 2
        else if (n.includes(q)) score = 1
        if (score < 0) continue
        scored.push([score, t])
      }
      scored.sort((a, b) => b[0] - a[0] || b[1].sitelinks - a[1].sitelinks)
      return { total_matches: scored.length, results: scored.slice(0, limit).map((s) => titleBrief(s[1])) }
    },
  },
  {
    name: 'what_was_filmed_here',
    title: 'What was filmed at a place',
    description:
      'The inverse question, and the one this atlas is unusual for answering: give a place and get everything recorded as shot there, most widely covered first. Accepts a slug (preferred, e.g. "skellig-michael") or a name. Each result carries `relation`, because a video game or an anime attached to a place was SET there and not filmed there.',
    inputSchema: {
      type: 'object',
      properties: {
        place: { type: 'string', description: 'Place slug (preferred) or name, e.g. "durham-cathedral"' },
        limit: { type: 'integer', minimum: 1, maximum: 200, description: 'Max productions (default 50)' },
      },
      required: ['place'],
    },
    run(args) {
      if (!args.place) return { error: 'place must be a non-empty string' }
      const loc = findLocation(args.place)
      if (!loc) return { error: `No place matches "${args.place}". Try search_locations first.` }
      const limit = clampInt(args.limit, 50, 200)
      const shown = loc.titles.slice(0, limit)
      return {
        ...placeFull(loc),
        /** titleCount is the true number; loc.titles is capped in the wire
         * format for the busiest places, so say when the list is short of it. */
        productions_listed: shown.length,
        productions_total: loc.titleCount,
        truncated: loc.titleCount > shown.length || undefined,
        filmed_here: shown.map(titleBrief),
        filmed_here_per_wikipedia: loc.wikiTitles.length
          ? loc.wikiTitles.slice(0, limit).map(titleBrief)
          : undefined,
        wikipedia_evidence_note: loc.wikiTitles.length
          ? 'The productions in filmed_here_per_wikipedia are placed here only by their own English Wikipedia article, not by a Wikidata statement — weaker evidence, kept apart. A game or an anime among them is SET here, not filmed here; check its "relation" field. Say "per Wikipedia" when you quote one.'
          : undefined,
        /* Third stream, third note. It rides on the same list rather than a
         * separate one, so the warning has to name the rows it applies to. */
        source_work_note: shown.some((t) => t.originWork)
          ? `Some rows have relation "set in, per its source work": ${shown
              .filter((t) => t.originWork)
              .map((t) => `"${t.name}" via "${t.originWork}"`)
              .join(', ')}. Wikidata records no setting for those productions; the place comes from the work each one adapts, and an adaptation is free to move its story. Say "per its source work" when you quote one.`
          : undefined,
      }
    },
  },
  {
    name: 'search_locations',
    title: 'Search filming locations by name',
    description:
      'Find filming locations by name, optionally filtered by country (name or 2-letter ISO code) and by kind of place. Results are ordered by fame rank, which is driven by the most widely covered production shot there rather than by the place itself.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Place name or part of one, e.g. "skellig", "petra"' },
        country: { type: 'string', description: 'Country name or ISO code (optional)' },
        category: { type: 'string', description: CATEGORY_ENUM_DESC + ' (optional)' },
        limit: { type: 'integer', minimum: 1, maximum: 50, description: 'Max results (default 10)' },
      },
      required: ['query'],
    },
    run(args) {
      const q = norm(args.query)
      if (!q) return { error: 'query must be a non-empty string' }
      const cat = categoryOf(args.category)
      if (cat === undefined) return { error: `Unknown category "${args.category}". Valid: ${CATEGORY_KEYS.join(', ')}` }
      const limit = clampInt(args.limit, 10, 50)
      const scored = []
      for (const loc of locations) {
        if (!matchesCountry(loc, args.country)) continue
        if (cat && loc.category !== cat) continue
        const n = norm(loc.name)
        let score = -1
        if (n === q) score = 3
        else if (n.startsWith(q)) score = 2
        else if (n.includes(q)) score = 1
        if (score < 0) continue
        scored.push([score, loc])
      }
      scored.sort((a, b) => b[0] - a[0] || a[1].rank - b[1].rank)
      return { total_matches: scored.length, results: scored.slice(0, limit).map((s) => placeBrief(s[1])) }
    },
  },
  {
    name: 'locations_near',
    title: 'Filming locations near a point',
    description:
      'List filming locations within a radius of a WGS84 coordinate, most famous first, each with distance_km — the direct answer to "what was filmed near me?" and to set-jetting itineraries. Radius defaults to 50 km (max 500). Geocode the place yourself, then call this with its latitude and longitude.',
    inputSchema: {
      type: 'object',
      properties: {
        latitude: { type: 'number', minimum: -90, maximum: 90 },
        longitude: { type: 'number', minimum: -180, maximum: 180 },
        radius_km: { type: 'number', minimum: 1, maximum: 500, description: 'Search radius in km (default 50)' },
        category: { type: 'string', description: CATEGORY_ENUM_DESC + ' (optional)' },
        limit: { type: 'integer', minimum: 1, maximum: 50, description: 'Max results (default 15)' },
      },
      required: ['latitude', 'longitude'],
    },
    run(args) {
      const lat = Number(args.latitude)
      const lon = Number(args.longitude)
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return { error: 'latitude/longitude must be numbers' }
      const cat = categoryOf(args.category)
      if (cat === undefined) return { error: `Unknown category "${args.category}". Valid: ${CATEGORY_KEYS.join(', ')}` }
      const radius = Math.max(1, Math.min(500, Number(args.radius_km) || 50))
      const limit = clampInt(args.limit, 15, 50)
      const hits = []
      for (const loc of locations) {
        if (cat && loc.category !== cat) continue
        // Cheap prefilter: 1° lat ≈ 111 km — skip the haversine for the far away.
        if (Math.abs(loc.lat - lat) * 111 > radius) continue
        const d = haversineKm(lat, lon, loc.lat, loc.lon)
        if (d <= radius) hits.push([d, loc])
      }
      hits.sort((a, b) => a[1].rank - b[1].rank)
      return {
        total_within_radius: hits.length,
        results: hits.slice(0, limit).map(([d, loc]) => ({
          distance_km: Math.round(d * 10) / 10,
          ...placeBrief(loc),
          top_productions: loc.titles.slice(0, 5).map((t) => t.name),
        })),
      }
    },
  },
  {
    name: 'top_locations',
    title: 'The most filmed places',
    description:
      'The atlas ranked, worldwide or inside one country or one kind of place. Order is fame rank, which comes from the most widely covered production shot there — so rank 1 is the place the most famous production used, not the place with the most credits. Sort by `productions` instead to get the busiest places (Los Angeles, New York, Vancouver). Answers "most famous filming locations in <country>".',
    inputSchema: {
      type: 'object',
      properties: {
        country: { type: 'string', description: 'Country name or ISO code (optional — omit for worldwide)' },
        category: { type: 'string', description: CATEGORY_ENUM_DESC + ' (optional)' },
        sort: { type: 'string', enum: ['fame', 'productions'], description: 'Ranking (default fame)' },
        limit: { type: 'integer', minimum: 1, maximum: 100, description: 'How many (default 10)' },
      },
    },
    run(args) {
      const cat = categoryOf(args.category)
      if (cat === undefined) return { error: `Unknown category "${args.category}". Valid: ${CATEGORY_KEYS.join(', ')}` }
      const limit = clampInt(args.limit, 10, 100)
      const pool = locations.filter((loc) => matchesCountry(loc, args.country) && (!cat || loc.category === cat))
      const sorted =
        args.sort === 'productions' ? [...pool].sort((a, b) => b.titleCount - a.titleCount || a.rank - b.rank) : pool
      return {
        total_matching: pool.length,
        sorted_by: args.sort === 'productions' ? 'productions' : 'fame',
        results: sorted.slice(0, limit).map((loc) => ({
          ...placeBrief(loc),
          top_productions: loc.titles.slice(0, 5).map((t) => t.name),
        })),
      }
    },
  },
  {
    name: 'list_countries',
    title: 'Countries with location counts',
    description:
      'Every country in the atlas with how many filming locations it holds, most first — answers "which country has the most filming locations". Countries with a browsable page carry its URL. Coverage reflects what Wikidata records, which is uneven and skewed to Europe and North America, so read these as records and not as an inventory of world film production.',
    inputSchema: { type: 'object', properties: {} },
    run() {
      const byCountry = new Map()
      for (const loc of locations) {
        if (!loc.country) continue
        const e = byCountry.get(loc.country) || { iso: loc.iso, count: 0 }
        e.count++
        if (!e.iso && loc.iso) e.iso = loc.iso
        byCountry.set(loc.country, e)
      }
      const rows = [...byCountry.entries()]
        .map(([country, e]) => ({
          country,
          iso: e.iso,
          locations: e.count,
          // The page threshold in guide.ts (COUNTRY_PAGE_MIN_LOCATIONS).
          ...(e.count >= 8 ? { page: `${SITE_URL}/places/${slugify(country)}/` } : {}),
        }))
        .sort((a, b) => b.locations - a.locations)
      return { total_countries: rows.length, index: `${SITE_URL}/places/`, results: rows }
    },
  },
  {
    name: 'get_statistics',
    title: 'Atlas statistics',
    description:
      'Headline figures computed live from the atlas: totals by medium and by kind of place, the top countries, the busiest and most famous locations, and — the number worth quoting — how many productions Wikidata records only at country level and therefore cannot place. The source for any aggregate claim about this dataset.',
    inputSchema: { type: 'object', properties: {} },
    run() {
      const byKind = { film: 0, tv: 0, game: 0, anime: 0, manga: 0 }
      const byCategory = {}
      const byCountry = new Map()
      let countryOnly = 0
      for (const t of titles) {
        byKind[t.kind] = (byKind[t.kind] || 0) + 1
        if (!t.locations.length && t.regions.length) countryOnly++
      }
      for (const loc of locations) {
        byCategory[loc.category] = (byCategory[loc.category] || 0) + 1
        if (loc.country) {
          const e = byCountry.get(loc.country) || { iso: loc.iso, count: 0 }
          e.count++
          if (!e.iso && loc.iso) e.iso = loc.iso
          byCountry.set(loc.country, e)
        }
      }
      const busiest = [...locations].sort((a, b) => b.titleCount - a.titleCount).slice(0, 5)
      const brief = (loc) => ({ name: loc.name, country: loc.country, productions: loc.titleCount, page: `${SITE_URL}/locations/${loc.slug}/` })
      return {
        locations: locations.length,
        productions: titles.length,
        // ⚠ EVERY MEDIUM, or this breakdown does not sum to `productions`
        // above. It listed film, tv and game only, so 407 anime and 366 manga
        // were counted in the loop and then dropped from the answer: 773
        // productions missing from "the source for any aggregate claim about
        // this dataset", with nothing saying so.
        by_medium: {
          film: byKind.film,
          tv: byKind.tv,
          game: byKind.game,
          anime: byKind.anime || 0,
          manga: byKind.manga || 0,
          note: 'Films and series are placed by filming location (P915). Games, anime and manga are placed by narrative location (P840) or by a Wikipedia setting category — where they are set, not filmed. These five sum to the productions total.',
        },
        by_category: Object.fromEntries(
          CATEGORY_KEYS.map((k) => [k, { label: CATEGORIES[k].label, locations: byCategory[k] || 0 }]),
        ),
        countries: byCountry.size,
        countries_declared: countryCount,
        top_countries: [...byCountry.entries()]
          .map(([country, e]) => ({ country, iso: e.iso, locations: e.count }))
          .sort((a, b) => b.locations - a.locations)
          .slice(0, 10),
        recorded_at_country_level_only: countryOnly,
        recorded_at_country_level_note:
          'Productions Wikidata places only by country, with nothing finer. They are listed on the site as text and never pinned. Gladiator is Malta and Morocco and nothing more; Casablanca resolves to California.',
        busiest_locations: busiest.map(brief),
        most_famous_location: brief(locations[0]),
        open_data: `${SITE_URL}/data/`,
        browse: `${SITE_URL}/locations/`,
      }
    },
  },
]
const TOOL_BY_NAME = new Map(TOOLS.map((t) => [t.name, t]))

/* ── JSON-RPC dispatch ────────────────────────────────────────────────────── */
function handleRpc(msg) {
  const { method, params, id } = msg
  if (method === 'initialize') {
    const asked = params?.protocolVersion
    return {
      protocolVersion: PROTOCOLS.has(asked) ? asked : LATEST,
      capabilities: { tools: {} },
      serverInfo: { name: 'filmmap', title: 'FilmMap — where films and TV were actually shot', version: VERSION },
      instructions:
        // Counted, not asserted. Saying "2,623 real filming locations" would be
        // wrong by exactly the 121 region pins, which are the one thing on this
        // map that is not a filming location.
        `Read-only tools over FilmMap: ${(locations.length - regionCount()).toLocaleString('en-US')} real filming locations, plus ` +
        `${regionCount()} whole countries or regions that carry nothing but video-game settings, for ` +
        `${titles.length.toLocaleString('en-US')} films, series and games across ${countryCount} countries. The backbone is ` +
        `"filming location" (P915) statements on Wikidata joined to each place's coordinates and Wikipedia article; some ` +
        `records additionally carry places named in the production's own English Wikipedia article, ALWAYS in fields ` +
        `prefixed wiki_ and never merged with the statements — quote those as "per Wikipedia". Nothing is scraped from ` +
        `listicles and nothing is generated. ` +
        `TWO RULES WHEN YOU QUOTE THIS DATA. (1) Video games are placed by where they are SET (P840), because a game is ` +
        `filmed nowhere — every record carries a "relation" field saying "filmed at" or "set in", and calling a game's ` +
        `place a filming location is a false claim. (2) This atlas records that a production filmed at a place and stops ` +
        `there: which scene was shot where is NOT in the data, so never assign one. Gaps are reported honestly rather ` +
        `than filled — where Wikidata knows only a country, the answer says so. ` +
        `Use where_was_it_filmed for the main question, what_was_filmed_here for the inverse, locations_near for ` +
        `"what was filmed near me", search_productions / search_locations for lookups, top_locations and list_countries ` +
        `for coverage, and get_statistics for aggregate claims. Every result links its page on ${SITE_URL}.`,
    }
  }
  if (method === 'ping') return {}
  if (method === 'tools/list') {
    freshData()
    return {
      tools: TOOLS.map(({ name, title, description, inputSchema }) => ({
        name,
        title,
        description: description
          .replace('{{FILMS}}', titles.length.toLocaleString('en-US'))
          .replace('{{LOCATIONS}}', locations.length.toLocaleString('en-US')),
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

/* ── HTTP transport (stateless streamable-http) ───────────────────────────── */
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, DELETE, OPTIONS',
  'Access-Control-Allow-Headers':
    'Content-Type, Accept, Authorization, Mcp-Protocol-Version, Mcp-Session-Id, Last-Event-ID',
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
    return send(
      res,
      405,
      { jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed — POST JSON-RPC to this endpoint' }, id: null },
      { Allow: 'POST, OPTIONS' },
    )

  let body = ''
  let overflow = false
  req.on('data', (chunk) => {
    body += chunk
    if (body.length > 65536) {
      overflow = true
      req.destroy()
    }
  })
  req.on('end', () => {
    if (overflow) return
    let msg
    try {
      msg = JSON.parse(body)
    } catch {
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32700, message: 'Parse error' }, id: null })
    }
    if (Array.isArray(msg))
      return send(res, 400, {
        jsonrpc: '2.0',
        error: { code: -32600, message: 'Batching is not supported (protocol 2025-06-18)' },
        id: null,
      })
    if (!msg || msg.jsonrpc !== '2.0')
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

    const hasId = msg.id !== undefined && msg.id !== null
    const isNotification = typeof msg.method === 'string' && !hasId
    const isResponse = msg.method === undefined && (msg.result !== undefined || msg.error !== undefined)
    if (isNotification || isResponse) return send(res, 202, undefined)
    if (typeof msg.method !== 'string' || !hasId)
      return send(res, 400, { jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

    const t0 = Date.now()
    const result = handleRpc(msg)
    const took = Date.now() - t0
    log(`filmmap-mcp: ${msg.method}${msg.params?.name ? ' ' + msg.params.name : ''} (${took}ms)`)
    if (result && result.__rpcError) return send(res, 200, { jsonrpc: '2.0', error: result.__rpcError, id: msg.id })
    return send(res, 200, { jsonrpc: '2.0', result, id: msg.id })
  })
})
// ---- stdio transport (newline-delimited JSON-RPC on stdin/stdout) -----------
// Clients that spawn the server locally speak this instead of HTTP. Glama's
// build harness runs `mcp-proxy -- node server.mjs --stdio`, so without this the
// server cannot be containerised, scored or released there at all — it was
// HTTP-only until 2026-08-30, and that, not the listing, was the real blocker.
// Same dispatch and the same id rule as the POST branch above: a notification
// (no id, or a null one) draws no reply.
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
    return writeStdio({
      jsonrpc: '2.0',
      error: { code: -32600, message: 'Batching is not supported (protocol 2025-06-18)' },
      id: null,
    })
  if (!msg || msg.jsonrpc !== '2.0')
    return writeStdio({ jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

  const hasId = msg.id !== undefined && msg.id !== null
  const isNotification = typeof msg.method === 'string' && !hasId
  const isResponse = msg.method === undefined && (msg.result !== undefined || msg.error !== undefined)
  if (isNotification || isResponse) return
  if (typeof msg.method !== 'string' || !hasId)
    return writeStdio({ jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: null })

  const t0 = Date.now()
  const result = handleRpc(msg)
  log(`filmmap-mcp: ${msg.method}${msg.params?.name ? ' ' + msg.params.name : ''} (${Date.now() - t0}ms)`)
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
  log(`filmmap-mcp: serving stdio (${locations.length} locations)`)
}

if (STDIO) serveStdio()
else server.listen(PORT, HOST, () => log(`filmmap-mcp: listening on http://${HOST}:${PORT}/mcp`))
