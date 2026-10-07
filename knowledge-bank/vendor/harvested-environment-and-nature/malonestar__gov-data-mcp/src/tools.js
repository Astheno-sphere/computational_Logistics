/**
 * Pure tool-surface logic. No I/O, no SDK imports — everything here is directly
 * testable offline, and src/index.js is wiring only.
 */

/**
 * Actors promoted to first-class MCP tools. The catalog holds well over a
 * hundred actors; handing an agent that many tool definitions degrades tool
 * selection and blows up the context of every request. These are the
 * highest-signal ones (revenue-proven plus the flagships); every other actor
 * stays reachable through search/describe/run.
 *
 * No count is written down in this file on purpose — the catalog is the only
 * source of truth for how many there are, and prose counts here rotted from
 * 95 to 109 to 114 to 116 without a single test going red.
 */
export const FEATURED = [
  'site-due-diligence-bundle',
  'epa-contaminated-site-screener',
  'faa-drone-airspace-checker',
  'hifld-grid-proximity-screener',
  'interconnection-queue-tracker',
  'fdic-ncua-health-rollup',
  'fema-nri-county-risk-profile',
  'fws-wetlands-proximity-screener',
  'nhd-surface-water-404-screener',
  'epa-drinking-water-quality-screener',
  'parcel-owner-lookup',
  'license-verifier',
];

/**
 * Meta tools are hyphen-case for one reason: so that EVERY tool this server
 * exposes follows a single rule, and for catalog tools the rule is stronger
 * still — the tool name IS the Apify slug, which is also the value you pass to
 * describe/run and the tail of the Store URL. The old snake_case meta names
 * split the surface arbitrarily in two, which an independent review scored 2/5,
 * and the alternative (snake_case everywhere) would have made 12 tool names
 * differ from the slug they resolve to, trading one inconsistency for another.
 *
 * Renamed in v1.1.0. The pre-1.1 names are recognised in resolveCall and
 * answered with an explicit rename notice rather than silently aliased — a
 * caller with a hardcoded name deserves to be told, not quietly patched.
 */
export const META_TOOLS = {
  SEARCH: 'search-gov-data-tools',
  DESCRIBE: 'describe-gov-data-tool',
  RUN: 'run-gov-data-tool',
};

export const RENAMED_IN_1_1 = {
  search_gov_data_tools: 'search-gov-data-tools',
  describe_gov_data_tool: 'describe-gov-data-tool',
  run_gov_data_tool: 'run-gov-data-tool',
};

/** MCP tool names must match ^[a-zA-Z0-9_-]{1,64}$. Slugs already do. */
export function toolNameFor(slug) {
  return slug;
}

/**
 * Build the tool index. With no options this is the full catalog fronted by
 * FEATURED — byte-identical to every release before presets existed.
 *
 * With a preset, the WHOLE index is restricted: `actors` (what search,
 * describe and run can reach) is filtered to the preset's tools, and
 * `featured` becomes the preset's own list. A preset tool that is not in the
 * catalog is a hard error, not a warning — a scoped server advertising a tool
 * that does not exist is precisely the defect a stderr line would hide.
 */
export function indexCatalog(catalog, options = {}) {
  const all = catalog.actors || [];
  const preset = options.preset || null;
  const presetName = options.presetName || null;
  if (preset) {
    const missing = preset.tools.filter(s => !all.some(a => a.slug === s));
    if (missing.length) {
      throw new Error(`preset "${presetName}" names tools that are not in the bundled catalog: ${missing.join(', ')}. `
        + 'Regenerate the catalog or fix the preset before starting a server that would advertise them.');
    }
  }
  const allSlugs = new Set(all.map(a => a.slug));
  const featured = preset ? [...preset.tools] : [...FEATURED];
  const keep = preset ? new Set(preset.tools) : null;
  const actors = keep ? all.filter(a => keep.has(a.slug)) : all;
  const bySlug = new Map(actors.map(a => [a.slug, a]));
  const missingFeatured = featured.filter(s => !bySlug.has(s));
  const scopeNote = preset
    ? ` This server is scoped to the "${presetName}" preset (${actors.length} of ${all.length} catalog tools); start gov-data-mcp without --preset for the full catalog.`
    : '';
  return { actors, bySlug, missingFeatured, featured, presetName, scopeNote, catalogTotal: all.length, allSlugs };
}

function truncate(s, n) {
  if (!s) return '';
  return s.length <= n ? s : s.slice(0, n - 1).trimEnd() + '…';
}

/**
 * MCP tool annotations — the machine-readable half of "what does this do to the
 * world before I call it".
 *
 * WHY `readOnlyHint: false` ON THE DATA TOOLS, despite them only ever reading:
 * they never write to any government system, but every call starts a metered
 * run on the caller's own Apify account and costs them money. `readOnlyHint`
 * means "does not modify its environment", and an agent that reads `true`
 * reasonably concludes the call is free to make speculatively — which is the
 * one wrong conclusion that costs the caller real money. Billing is a side
 * effect. We declare it rather than hide it behind a comfortable `true`, and
 * `destructiveHint: false` carries the other half of the truth: nothing is
 * destroyed, no external state is altered, and a call is always safe to make
 * once you accept its cost.
 *
 * `idempotentHint: false` because these read live sources — the same input
 * tomorrow can legitimately return different rows, and a caller must not cache
 * a flood or sanctions answer as if it were fixed.
 */
export const ANNOTATIONS = {
  /** Reads the bundled catalog. No network, no run, no charge. */
  CATALOG_LOCAL: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  /** Starts a billed Apify run against a live government source. */
  BILLED_LIVE_READ: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
};

/** Format a price so an agent can compare tools without doing arithmetic. */
export function priceLine(pricing) {
  if (!pricing) return 'Price unavailable for this tool — check its Store page before calling.';
  const per1k = pricing.usdPer1000;
  const cheapest = pricing.tierDiscountsUsdPerUnit
    ? Math.min(...Object.values(pricing.tierDiscountsUsdPerUnit))
    : pricing.usdPerUnit;
  const discount = cheapest < pricing.usdPerUnit
    ? ` Lower on paid Apify plans, down to $${(cheapest * 1000).toFixed(2)} per 1,000.`
    : '';
  return `$${pricing.usdPerUnit} per ${pricing.unit} ($${per1k} per 1,000).${discount}`;
}

export function costNote(pricing) {
  return 'COST AND SIDE EFFECTS: read-only with respect to the government source — it never writes to any external system — '
    + `but each call starts a metered run on YOUR Apify account, billed ${priceLine(pricing)} `
    + 'Nothing is charged when a run fails.';
}

/** The generic, price-free wording used by the run tool, which can run anything. */
export const COST_NOTE =
  'COST AND SIDE EFFECTS: read-only with respect to the government source — it never writes to any external system — '
  + 'but each call starts a metered run on YOUR Apify account, billed per result row at the rate this tool reports. '
  + 'Call describe-gov-data-tool first to see the exact price before running anything. '
  + 'Nothing is charged when a run fails.';

/**
 * Routing notes for tools whose scope genuinely overlaps.
 *
 * Four of the featured tools answer adjacent questions about the same
 * coordinate, and an agent handed all four with no guidance picks by keyword
 * overlap rather than by which regulatory question is actually being asked.
 * These sentences say, in each tool's own description, when it is the wrong
 * choice — which is the part a bare capability blurb never tells you.
 */
export const ROUTING = {
  'site-due-diligence-bundle':
    'CHOOSE THIS when you want one combined go / caution / no-go verdict for a coordinate across many unrelated layers. '
    + 'It is NOT an ASTM records review: its contamination layer reads RCRA and TRI through ECHO only and omits coordinate-less Superfund records. '
    + 'For a contamination-first question use epa-contaminated-site-screener.',
  'epa-contaminated-site-screener':
    'CHOOSE THIS for the ASTM E1527-21 Phase I records search at regulation distances around one or more properties. '
    + 'For a single combined verdict across twenty unrelated layers use site-due-diligence-bundle; for drinking-water quality use epa-drinking-water-quality-screener.',
  'fws-wetlands-proximity-screener':
    'CHOOSE THIS for National Wetlands Inventory polygons and their decode columns within a radius. '
    + 'It does NOT answer Clean Water Act §404 jurisdiction — for surface-water features and relative permanence use nhd-surface-water-404-screener. The two are usually needed together.',
  'nhd-surface-water-404-screener':
    'CHOOSE THIS for Clean Water Act §404 surface-water screening — streams, waterbodies and their relative permanence. '
    + 'For mapped wetland polygons use fws-wetlands-proximity-screener.',
  'epa-drinking-water-quality-screener':
    'CHOOSE THIS for public water-system quality: SDWA violations, lead 90th-percentile results and PFAS occurrence. '
    + 'It is NOT a property contamination screen — for soil and groundwater records at a site use epa-contaminated-site-screener.',
};

/**
 * A routing note is only shown when every tool it points at is reachable on
 * THIS server. Under a preset, a note that sends the agent to a tool outside
 * the preset would be a dead end dressed as advice, so the note is dropped
 * rather than edited — a half-note that names a missing tool is worse than none.
 */
export function routingNoteFor(index, slug) {
  const note = ROUTING[slug];
  if (!note) return '';
  // Only tokens that are catalog slugs count as references; hyphenated prose is not a tool.
  const isSlug = (r) => index.allSlugs ? index.allSlugs.has(r) : index.bySlug.has(r);
  const referenced = (note.match(/[a-z0-9]+(?:-[a-z0-9]+){2,}/g) || []).filter(r => r !== slug && isSlug(r));
  return referenced.every(r => index.bySlug.has(r)) ? ` ${note}` : '';
}

export function featuredToolDefinitions(index) {
  const featured = index.featured || FEATURED;
  return featured.filter(s => index.bySlug.has(s)).map(slug => {
    const a = index.bySlug.get(slug);
    const routing = routingNoteFor(index, slug);
    return {
      name: toolNameFor(slug),
      description: `${a.title}. ${truncate(a.description, 400)}${routing} Reads live from the official government source. ${costNote(a.pricing)} Store page: ${a.storeUrl}`,
      inputSchema: a.inputSchema,
      annotations: { title: a.title, ...ANNOTATIONS.BILLED_LIVE_READ },
    };
  });
}

export function metaToolDefinitions(index) {
  const n = index.actors.length;
  return [
    {
      name: META_TOOLS.SEARCH,
      description: `Search the full catalog of ${n} US government data tools by keyword, agency, or topic (e.g. "wetlands", "FDIC", "flood", "drone airspace", "business licenses"). Returns matching tool names with descriptions. Use this first when the task is not covered by one of the dedicated tools above.${index.scopeNote || ''} FREE: reads a catalog bundled with this server — no network call, no run, nothing charged.`,
      annotations: { title: 'Search the government data catalog', ...ANNOTATIONS.CATALOG_LOCAL },
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Keywords to match against tool name, title, description and category.' },
          limit: { type: 'integer', description: 'Maximum number of results to return. Default 10.', minimum: 1, maximum: 50 },
        },
        required: ['query'],
      },
    },
    {
      name: META_TOOLS.DESCRIBE,
      description: `Return the full input schema and documentation for any one of the ${n} tools in the catalog. Call this before ${META_TOOLS.RUN} so the input is correctly shaped. FREE: reads a catalog bundled with this server — no network call, no run, nothing charged.`,
      annotations: { title: 'Describe one government data tool', ...ANNOTATIONS.CATALOG_LOCAL },
      inputSchema: {
        type: 'object',
        properties: {
          tool: { type: 'string', description: 'The tool name, e.g. "noaa-slr-inundation-threshold-screener".' },
        },
        required: ['tool'],
      },
    },
    {
      name: META_TOOLS.RUN,
      description: `Run any one of the ${n} catalog tools with the given input and return its rows. Call ${META_TOOLS.DESCRIBE} first to shape the input. `
        + `${COST_NOTE} A run that FAILS returns an error and no rows rather than an empty result, so a zero-row answer here always means the source was reached and genuinely matched nothing.`,
      annotations: { title: 'Run any government data tool', ...ANNOTATIONS.BILLED_LIVE_READ },
      inputSchema: {
        type: 'object',
        properties: {
          tool: { type: 'string', description: 'The tool name to run, e.g. "usgs-seismic-design-screener".' },
          input: { type: 'object', description: `Input object matching the schema returned by ${META_TOOLS.DESCRIBE}.` },
          maxItems: { type: 'integer', description: 'Maximum rows to return. Default 200.', minimum: 1, maximum: 1000 },
        },
        required: ['tool', 'input'],
      },
    },
  ];
}

export function listTools(index) {
  return [...featuredToolDefinitions(index), ...metaToolDefinitions(index)];
}

export function searchCatalog(index, query, limit = 10) {
  const terms = String(query || '').toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [];
  const scored = index.actors.map(a => {
    const hay = `${a.slug} ${a.title} ${a.description} ${(a.categories || []).join(' ')}`.toLowerCase();
    let score = 0;
    for (const t of terms) {
      if (a.slug.toLowerCase().includes(t)) score += 5;
      else if (a.title.toLowerCase().includes(t)) score += 3;
      else if (hay.includes(t)) score += 1;
    }
    return { actor: a, score };
  }).filter(x => x.score > 0);
  scored.sort((a, b) => b.score - a.score || a.actor.slug.localeCompare(b.actor.slug));
  return scored.slice(0, limit).map(x => ({
    tool: toolNameFor(x.actor.slug),
    title: x.actor.title,
    description: truncate(x.actor.description, 300),
    categories: x.actor.categories,
    // Price rides along on every search hit so an agent can weigh cost while
    // choosing, rather than discovering it only after it has already called.
    usdPer1000Results: x.actor.pricing ? x.actor.pricing.usdPer1000 : null,
    storeUrl: x.actor.storeUrl,
  }));
}

export function describeTool(index, name) {
  const actor = index.bySlug.get(name);
  if (!actor) {
    const near = searchCatalog(index, String(name || '').replace(/[-_]/g, ' '), 5).map(r => r.tool);
    return {
      ok: false,
      error: `No tool named "${name}" in this catalog.${near.length ? ` Closest matches: ${near.join(', ')}.` : ''} Use ${META_TOOLS.SEARCH} to find one. This is a lookup miss, not a statement about the underlying data.${index.scopeNote || ''}`,
    };
  }
  return {
    ok: true,
    tool: toolNameFor(actor.slug),
    title: actor.title,
    description: actor.description,
    categories: actor.categories,
    pricing: actor.pricing
      ? { ...actor.pricing, summary: priceLine(actor.pricing) }
      : null,
    storeUrl: actor.storeUrl,
    inputSchema: actor.inputSchema,
  };
}

/** Resolve a tool call to { slug, input } or an error, for both featured and meta RUN calls. */
export function resolveCall(index, toolName, args) {
  if (index.bySlug.has(toolName)) return { ok: true, slug: toolName, input: args || {}, maxItems: undefined };
  if (toolName === META_TOOLS.RUN) {
    const slug = args && args.tool;
    if (!slug) return { ok: false, error: `${META_TOOLS.RUN} requires a "tool" argument naming which catalog tool to run.` };
    if (!index.bySlug.has(slug)) {
      const near = searchCatalog(index, String(slug).replace(/[-_]/g, ' '), 5).map(r => r.tool);
      return { ok: false, error: `No tool named "${slug}" in this catalog.${near.length ? ` Closest matches: ${near.join(', ')}.` : ''}${index.scopeNote || ''}` };
    }
    return { ok: true, slug, input: (args && args.input) || {}, maxItems: args && args.maxItems };
  }
  // A caller with a hardcoded pre-1.1 name gets told what happened rather than
  // silently aliased, so the hardcode gets fixed instead of quietly persisting.
  if (RENAMED_IN_1_1[toolName]) {
    return { ok: false, error: `"${toolName}" was renamed to "${RENAMED_IN_1_1[toolName]}" in gov-data-mcp v1.1.0, so that every tool on this server uses one naming convention. Call "${RENAMED_IN_1_1[toolName]}" instead — the arguments are unchanged.` };
  }
  return { ok: false, error: `Unknown tool "${toolName}". Call ${META_TOOLS.SEARCH} to list what this server offers.` };
}

/** Shape a run result into MCP text content. Never collapses a failure into an empty answer. */
export function formatRunResult(slug, result) {
  const header = {
    tool: slug,
    run_status: result.status,
    run_id: result.runId,
    rows_returned: result.itemCount,
    apify_run_url: result.runId ? `https://console.apify.com/actors/runs/${result.runId}` : null,
  };
  if (result.statusMessage) header.note = result.statusMessage;
  const failed = result.status !== 'SUCCEEDED';
  return {
    isError: failed,
    text: JSON.stringify(failed ? header : { ...header, rows: result.items }, null, 2),
  };
}
