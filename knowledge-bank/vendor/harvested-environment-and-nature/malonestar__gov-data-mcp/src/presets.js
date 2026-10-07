/**
 * Vertical presets — the same package, the same catalog, a smaller front door.
 *
 * WHY THIS EXISTS. Agents pick tools badly past about twenty, and the full
 * server already exposes fifteen. A Phase I ESA consultant's agent does not
 * need to weigh a liquor-license feed against a Superfund screen; a sales
 * agent building a CRE lead list does not need wetlands. A preset restricts the
 * WHOLE surface — the named tools AND what search/describe/run can reach — to
 * one buyer's shelf, and announces itself to the client under its own server
 * name and description, so a connector directory can list three products that
 * are, underneath, one npm package with one catalog and one release train.
 *
 * WHY NOT THREE NPM PACKAGES. A first `npm publish` cannot be automated from
 * CI (Trusted Publishing needs the package to already exist), each package
 * would carry its own copy of the catalog to drift, and the Official MCP
 * Registry entry stays singular. One package, one gate, `--preset <name>`.
 *
 * Pure. No I/O. `resolvePreset` and `parseCliArgs` are what index.js calls.
 *
 * Every slug listed here is asserted to exist in the bundled catalog by
 * test/presets.test.js, and the preset count is derived into the README by
 * tools/gen-readme-coverage.cjs — never typed.
 */

export const PRESET_ENV = 'GOV_DATA_MCP_PRESET';

export const PRESETS = {
  'phase1-esa': {
    serverName: 'gov-data-mcp-phase1-esa',
    title: 'Phase I ESA — Environmental Due Diligence',
    description: 'US government environmental records for Phase I Environmental Site Assessments and property due diligence: '
      + 'EPA Superfund / RCRA / UST / brownfield records at ASTM E1527-21 search distances, state tank and spill registries, '
      + 'historic land use from FRS SIC/NAICS, USGS historical topographic map coverage, NWI wetlands, Clean Water Act §404 '
      + 'surface water, RCRA corrective-action cleanups, orphaned wells, FEMA hazard risk and NFIP flood-loss history, plus a '
      + 'twenty-layer go / caution / no-go site verdict. Every tool reads the official source directly and reports what it '
      + 'could not check as null, never as clear.',
    tools: [
      'site-due-diligence-bundle',
      'epa-contaminated-site-screener',
      'historic-land-use-sic-contaminant-screener',
      'state-tank-spill-registry-screener',
      'usgs-historical-topo-records-review',
      'epa-rcra-corrective-action-cleanup-monitor',
      'orphaned-well-proximity-screener',
      'fws-wetlands-proximity-screener',
      'nhd-surface-water-404-screener',
      'fema-nri-county-risk-profile',
      'nfip-flood-loss-risk-screener',
    ],
  },
  'cre-leads': {
    serverName: 'gov-data-mcp-cre-leads',
    title: 'CRE & Local Business Leads — Who Just Changed State',
    description: 'Lead-generation feeds built from official state and county registers: new and pending liquor licenses, '
      + 'verified new business openings from Secretary of State and tax rosters, WARN layoff notices, newly licensed real '
      + 'estate agents, licensed childcare providers with contacts, parcel owner of record, absentee-owner lists, '
      + 'distressed-property signal stacks, NYC deed transfers and landlord registries, city business licenses and '
      + 'professional license verification. Delta modes return only what changed since the last run, so a scheduled agent '
      + 'pays for new leads, not the same roster twice.',
    tools: [
      'liquor-license-new-openings-tracker',
      'sos-registry-monitor',
      'warn-layoff-aggregator',
      'realtor-license-roster-delta',
      'childcare-provider-leads',
      'parcel-owner-lookup',
      'absentee-owner-lead-list-builder',
      'distressed-property-signal-stacker',
      'acris-deed-transfer-intel',
      'nyc-landlord-registry-lead-list',
      'city-business-license-leads',
      'license-verifier',
    ],
  },
  'compliance': {
    serverName: 'gov-data-mcp-compliance',
    title: 'KYB, Sanctions & Financial Compliance Screening',
    description: 'Know-your-business and compliance screening from primary US government registers: company existence '
      + 'across Secretary of State registries, the Trade.gov Consolidated Screening List (OFAC SDN, BIS, State) as a delta, '
      + 'the DHS UFLPA Entity List, state Medicaid and HHS-OIG exclusion lists, professional license verification, GLEIF '
      + 'LEI ownership graphs, FDIC / NCUA institution health, FDIC structure changes, SEC investment-adviser registrations, '
      + 'PCAOB auditor engagements and SEC Regulation CF / A+ offering lifecycles. A screen that could not reach its source '
      + 'fails loudly rather than returning a clean sheet.',
    tools: [
      'kyb-company-verifier',
      'consolidated-screening-list-delta',
      'uflpa-entity-list-monitor',
      'medicaid-exclusion-screener',
      'license-verifier',
      'gleif-ownership-graph',
      'fdic-ncua-health-rollup',
      'fdic-structure-change-delta-monitor',
      'ria-registration-delta-monitor',
      'pcaob-auditor-engagement-monitor',
      'reg-cf-lifecycle-monitor',
      'reg-a-plus-lifecycle-monitor',
    ],
  },
};

export const PRESET_NAMES = Object.keys(PRESETS);

/** Agents choose badly past ~20 tools; a preset plus its three meta tools must stay under this. */
export const MAX_PRESET_TOOLS = 15;

/**
 * Resolve a preset name to its definition, or an explicit error. Never guesses:
 * "phase1" does not become "phase1-esa", because a server that silently started
 * with the wrong shelf would be the quiet failure this project exists to avoid.
 */
export function resolvePreset(name) {
  if (name === undefined || name === null || String(name).trim() === '') return { ok: true, preset: null, name: null };
  const key = String(name).trim();
  const preset = PRESETS[key];
  if (!preset) {
    return {
      ok: false,
      error: `Unknown preset "${key}". Known presets: ${PRESET_NAMES.join(', ')}. `
        + `Pass --preset <name> or set ${PRESET_ENV}; omit both for the full catalog.`,
    };
  }
  return { ok: true, preset, name: key };
}

/**
 * Parse the CLI + environment into { presetName, listPresets }. The flag wins
 * over the environment variable, and an empty value is an error rather than
 * "no preset" — `--preset` with nothing after it is a typo, not a choice.
 */
export function parseCliArgs(argv, env) {
  const args = Array.isArray(argv) ? argv : [];
  const out = { presetName: null, listPresets: false, errors: [] };
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === '--list-presets') { out.listPresets = true; continue; }
    if (a === '--preset') {
      const v = args[i + 1];
      if (v === undefined || v.startsWith('--')) { out.errors.push('--preset requires a value'); continue; }
      out.presetName = v; i++; continue;
    }
    if (a.startsWith('--preset=')) {
      const v = a.slice('--preset='.length);
      if (!v) { out.errors.push('--preset requires a value'); continue; }
      out.presetName = v; continue;
    }
  }
  if (out.presetName === null && env && typeof env[PRESET_ENV] === 'string' && env[PRESET_ENV].trim() !== '') {
    out.presetName = env[PRESET_ENV].trim();
  }
  return out;
}

/** One line per preset, for --list-presets and for the README generator. */
export function describePresets() {
  return PRESET_NAMES.map(n => ({
    name: n,
    serverName: PRESETS[n].serverName,
    title: PRESETS[n].title,
    toolCount: PRESETS[n].tools.length,
    tools: [...PRESETS[n].tools],
  }));
}
