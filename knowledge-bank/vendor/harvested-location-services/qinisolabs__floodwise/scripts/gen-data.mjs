// Generates src/data.generated.ts from the flood-postcode data.
//
// Prefers data/flood-postcodes.json (the real Environment Agency data, produced by
// scripts/build-data.mjs and git-ignored because it is large). Falls back to the
// committed data/flood-postcodes.sample.json so a fresh clone still builds/tests.
//
// The data is emitted as a single packed STRING literal ("POSTCODE,high,med,low,gwFlag"
// rows, newline-separated), not a multi-million-key object literal — a string literal is
// one token, so tsc stays fast even with ~1.5M England postcodes. Parsed into a Map at load.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const full = join(root, "data/flood-postcodes.json");
const sample = join(root, "data/flood-postcodes.sample.json");
const src = existsSync(full) ? full : sample;
const data = JSON.parse(readFileSync(src, "utf8"));
const postcodes = data.postcodes ?? {};

const parts = [];
for (const k of Object.keys(postcodes)) {
  const r = postcodes[k];
  parts.push(`${k},${r.high},${r.med},${r.low},${r.gw === "Possible" ? 1 : 0}`);
}
const packed = parts.join("\n");

const out = `// AUTO-GENERATED from ${existsSync(full) ? "data/flood-postcodes.json" : "data/flood-postcodes.sample.json"} by scripts/gen-data.mjs — do not edit by hand.
// Packed "POSTCODE,high,med,low,gwFlag" rows (newline-separated); parsed into a Map at load.
export const FLOOD_VERSION = ${JSON.stringify(data.version ?? "unknown")};
export const FLOOD_KIND: "sample" | "ea-official" = ${JSON.stringify(data.kind ?? "sample")};
// Typed as string (not the literal) so the emitted .d.ts stays tiny.
export const FLOOD_DATA: string = ${JSON.stringify(packed)};
`;

writeFileSync(join(root, "src/data.generated.ts"), out);
console.error(
  `generated src/data.generated.ts (${parts.length} postcodes, kind ${data.kind}, version ${data.version}, from ${existsSync(full) ? "real data" : "sample"})`
);
