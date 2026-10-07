// Build the FULL data/flood-postcodes.json from the official Environment Agency
// "Flood risk: postcode search tool data" release (England, Open Government Licence).
//
// Download `Postcodes_Risk_Assessment_All.csv` from the Defra Data Services Platform
// / data.gov.uk ("Flood risk: postcode search tool data"). Its columns are:
//
//     Postcode,HIGH_CNT,MED_CNT,LOW_CNT,GWTR_RISK
//
// where HIGH/MED/LOW_CNT are the number of addresses in the postcode whose
// surrounding area is at high (>=3.3%/yr), medium (1-3.3%) or low (0.1-1%) long-term
// risk of flooding from rivers, the sea OR surface water (the highest of those), and
// GWTR_RISK is "Possible" or "Unlikely" for groundwater. Very-low addresses are not
// counted. England only.
//
// Usage:
//   node scripts/build-data.mjs /path/to/Postcodes_Risk_Assessment_All.csv 2025-Q4
//
// Then run `npm run build` (which runs gen-data) to regenerate src/data.generated.ts.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const [, , file, version] = process.argv;
if (!file) {
  console.error("Usage: node scripts/build-data.mjs <Postcodes_Risk_Assessment_All.csv> [version]");
  process.exit(1);
}

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const text = readFileSync(file, "utf8");
const lines = text.split(/\r?\n/);

// Locate the header and the column order (be tolerant of column reordering).
const headerIdx = lines.findIndex((l) => /postcode/i.test(l) && /HIGH_CNT/i.test(l));
if (headerIdx === -1) {
  console.error("Could not find a header row with Postcode + HIGH_CNT — is this the right CSV?");
  process.exit(1);
}
const header = lines[headerIdx].split(",").map((h) => h.trim().toUpperCase());
const col = (name) => header.indexOf(name);
const iPc = col("POSTCODE");
const iHigh = col("HIGH_CNT");
const iMed = col("MED_CNT");
const iLow = col("LOW_CNT");
const iGw = col("GWTR_RISK");
if ([iPc, iHigh, iMed, iLow, iGw].some((i) => i === -1)) {
  console.error("Missing one of the expected columns: Postcode, HIGH_CNT, MED_CNT, LOW_CNT, GWTR_RISK.");
  process.exit(1);
}

const postcodes = {};
let n = 0;
for (let i = headerIdx + 1; i < lines.length; i++) {
  const raw = lines[i];
  if (!raw || !raw.trim()) continue;
  const cells = raw.split(",");
  const key = (cells[iPc] ?? "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!key) continue;
  const gwRaw = (cells[iGw] ?? "").trim().toLowerCase();
  postcodes[key] = {
    high: Number(cells[iHigh]) || 0,
    med: Number(cells[iMed]) || 0,
    low: Number(cells[iLow]) || 0,
    gw: gwRaw.startsWith("poss") ? "Possible" : "Unlikely",
  };
  n++;
}
if (n === 0) {
  console.error("No postcode rows parsed.");
  process.exit(1);
}

const out = {
  _comment:
    "England postcode -> long-term flood-risk address counts (high/med/low) + groundwater. Keys are uppercase, no spaces. Generated from the Environment Agency 'Flood risk: postcode search tool data' (Open Government Licence) by scripts/build-data.mjs. Risk is for the AREA around an address, not the address itself; England only.",
  version: version || "unknown",
  kind: "ea-official",
  postcodes,
};
writeFileSync(join(root, "data/flood-postcodes.json"), JSON.stringify(out, null, 0));
console.error(`wrote data/flood-postcodes.json — ${n} postcodes (version ${out.version}). Now run: npm run build`);
