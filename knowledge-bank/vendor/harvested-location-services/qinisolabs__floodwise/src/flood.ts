import { FLOOD_DATA, FLOOD_VERSION, FLOOD_KIND } from "./data.generated.js";

// UK postcode format (applied to the space-stripped, uppercased value). The final
// two letters never use C, I, K, M, O or V. GIR 0AA is the one special case.
const UK_POSTCODE = /^(GIR0AA|[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][ABD-HJLNP-UW-Z]{2})$/;

export type FloodRow = { high: number; med: number; low: number; gw: "Possible" | "Unlikely" };

// Parse the packed "POSTCODE,high,med,low,gwFlag" rows into a Map once, at load.
function parseData(packed: string): Map<string, FloodRow> {
  const m = new Map<string, FloodRow>();
  if (!packed) return m;
  for (const line of packed.split("\n")) {
    if (!line) continue;
    const c = line.split(",");
    m.set(c[0], { high: +c[1], med: +c[2], low: +c[3], gw: c[4] === "1" ? "Possible" : "Unlikely" });
  }
  return m;
}

const FLOOD = parseData(FLOOD_DATA);

export const datasetVersion = FLOOD_VERSION;
export const datasetKind = FLOOD_KIND;
export const datasetSize = FLOOD.size;

const OGL_ATTRIBUTION =
  "Contains public sector information licensed under the Open Government Licence v3.0. © Environment Agency copyright and/or database right.";

/** Normalise any user input to the lookup key: uppercase, no spaces/punctuation. */
export function normalizePostcode(input: string): string {
  return (input ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}

/** Whether a string is a structurally valid UK postcode (format only). */
export function isWellFormedPostcode(input: string): boolean {
  return UK_POSTCODE.test(normalizePostcode(input));
}

/** Canonical display form with the single space before the 3-character incode. */
export function formatPostcode(input: string): string | null {
  const s = normalizePostcode(input);
  if (!UK_POSTCODE.test(s)) return null;
  return `${s.slice(0, s.length - 3)} ${s.slice(s.length - 3)}`;
}

export interface PostcodeResult {
  input: string;
  postcode: string | null; // canonical "SW1A 1AA" form when valid
  valid: boolean;
  outcode: string | null; // outward code, e.g. "SW1A"
  incode: string | null; // inward code, e.g. "1AA"
  errors: string[];
}

/** Validate and split a UK postcode (deterministic format check; no lookup). */
export function validatePostcode(input: string): PostcodeResult {
  const s = normalizePostcode(input);
  const result: PostcodeResult = { input, postcode: null, valid: false, outcode: null, incode: null, errors: [] };
  if (!UK_POSTCODE.test(s)) {
    result.errors.push("Not a well-formed UK postcode (e.g. SW1A 1AA, M1 1AE, GIR 0AA).");
    return result;
  }
  result.valid = true;
  result.incode = s.slice(s.length - 3);
  result.outcode = s.slice(0, s.length - 3);
  result.postcode = `${result.outcode} ${result.incode}`;
  return result;
}

export type RiskBand = "High" | "Medium" | "Low" | "Very Low";

function headlineBand(row: FloodRow): RiskBand {
  if (row.high > 0) return "High";
  if (row.med > 0) return "Medium";
  if (row.low > 0) return "Low";
  return "Very Low";
}

export interface FloodRiskResult {
  input: string;
  postcode: string | null; // canonical form when well-formed
  wellFormed: boolean;
  found: boolean;
  /** Highest long-term flood-risk band among addresses in the postcode's area. */
  headlineRisk: RiskBand | null;
  /** Count of addresses whose surrounding AREA falls in each band (very-low is not counted by the EA). */
  addressesAtRisk: { high: number; medium: number; low: number } | null;
  /** Groundwater flooding indication for the postcode (separate from the bands above). */
  groundwater: "Possible" | "Unlikely" | null;
  riskSources: string;
  coverage: "England";
  basis: string;
  dataset: "sample" | "ea-official";
  datasetVersion: string;
  attribution: string;
  note?: string;
  errors: string[];
}

/**
 * Look up the Environment Agency long-term flood-risk indication for an England
 * postcode. Returns the highest risk band for the area around addresses in the
 * postcode, address counts per band, and the groundwater indication — or an honest
 * "not found" instead of guessing. England only; area-level, not property-level.
 */
export function floodRiskByPostcode(input: string): FloodRiskResult {
  const key = normalizePostcode(input);
  const result: FloodRiskResult = {
    input,
    postcode: null,
    wellFormed: false,
    found: false,
    headlineRisk: null,
    addressesAtRisk: null,
    groundwater: null,
    riskSources: "rivers, sea and surface water (the highest of these); groundwater reported separately",
    coverage: "England",
    basis: "Long-term risk (annual chance) for the AREA around the address — not a property-level assessment, and not a live flood warning.",
    dataset: FLOOD_KIND,
    datasetVersion: FLOOD_VERSION,
    attribution: OGL_ATTRIBUTION,
    errors: [],
  };

  if (!UK_POSTCODE.test(key)) {
    result.errors.push("Not a well-formed UK postcode (e.g. SW1A 1AA). Flood data covers England postcodes only.");
    return result;
  }
  result.wellFormed = true;
  result.postcode = `${key.slice(0, key.length - 3)} ${key.slice(key.length - 3)}`;

  const row = FLOOD.get(key);
  if (row) {
    result.found = true;
    result.headlineRisk = headlineBand(row);
    result.addressesAtRisk = { high: row.high, medium: row.med, low: row.low };
    result.groundwater = row.gw;
    if (FLOOD_KIND === "sample") {
      result.note =
        "Running on the ILLUSTRATIVE starter sample, not the official Environment Agency dataset — load the real data with scripts/build-data.mjs before relying on these values.";
    }
  } else {
    result.note =
      FLOOD_KIND === "sample"
        ? "Well-formed postcode, but this build only has the illustrative starter sample loaded. Load the official Environment Agency dataset via scripts/build-data.mjs."
        : "Well-formed postcode, but not present in the loaded England dataset. It may be a Welsh, Scottish or Northern Irish postcode (out of Environment Agency coverage — see Natural Resources Wales / SEPA / DfI), a newly created or terminated postcode, or a non-residential postcode. Not guessing a risk level.";
  }
  return result;
}
