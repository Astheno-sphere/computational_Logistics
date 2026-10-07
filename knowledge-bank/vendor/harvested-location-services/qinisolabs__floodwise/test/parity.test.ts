import assert from "node:assert/strict";
import {
  floodRiskByPostcode,
  validatePostcode,
  normalizePostcode,
  formatPostcode,
  isWellFormedPostcode,
  datasetKind,
  datasetSize,
} from "../src/index.js";
import { handleRpc } from "../src/core.js";

let pass = 0;
let fail = 0;
function check(name: string, fn: () => void) {
  try {
    fn();
    pass++;
  } catch (err) {
    fail++;
    console.error(`✗ ${name}\n    ${(err as Error).message}`);
  }
}

/* ---------- postcode normalise / format / validate (dataset-independent) ---------- */
check("normalize strips spaces + uppercases", () => assert.equal(normalizePostcode("sw1a 1aa"), "SW1A1AA"));
check("format inserts the single space", () => assert.equal(formatPostcode("sw1a1aa"), "SW1A 1AA"));
check("format short outcode (M1 1AE)", () => assert.equal(formatPostcode("m11ae"), "M1 1AE"));
check("well-formed: SW1A 1AA", () => assert.equal(isWellFormedPostcode("SW1A 1AA"), true));
check("well-formed: GIR 0AA special", () => assert.equal(isWellFormedPostcode("GIR 0AA"), true));
check("malformed: bad final letters (CIKMOV)", () => assert.equal(isWellFormedPostcode("SW1A 1CV"), false));
check("malformed: gibberish", () => assert.equal(isWellFormedPostcode("NOTAPOSTCODE"), false));

check("validate_postcode splits outcode/incode", () => {
  const r = validatePostcode("ec1a1bb");
  assert.equal(r.valid, true);
  assert.equal(r.postcode, "EC1A 1BB");
  assert.equal(r.outcode, "EC1A");
  assert.equal(r.incode, "1BB");
});
check("validate_postcode rejects malformed", () => assert.equal(validatePostcode("XYZ").valid, false));

/* ---------- lookup behaviour that holds on ANY dataset ---------- */
check("dataset is loaded", () => assert.ok(datasetSize > 0));
check("malformed postcode → error, not found", () => {
  const r = floodRiskByPostcode("banana");
  assert.equal(r.wellFormed, false);
  assert.equal(r.found, false);
  assert.equal(r.errors.length, 1);
});
check("well-formed but guaranteed-absent → found:false, no guess", () => {
  const r = floodRiskByPostcode("ZZ9 9ZZ"); // non-geographic, never in EA data nor the sample
  assert.equal(r.wellFormed, true);
  assert.equal(r.found, false);
  assert.equal(r.headlineRisk, null);
  assert.ok(r.note && r.note.length > 0);
});
check("result always carries OGL attribution + England coverage", () => {
  const r = floodRiskByPostcode("ZZ9 9ZZ");
  assert.match(r.attribution, /Open Government Licence/);
  assert.equal(r.coverage, "England");
});

/* ---------- sample-specific value checks (only when the starter sample is loaded) ---------- */
if (datasetKind === "sample") {
  check("[sample] High band derived from a high count", () => {
    const r = floodRiskByPostcode("ZZ1 1AA");
    assert.equal(r.found, true);
    assert.equal(r.headlineRisk, "High");
    assert.deepEqual(r.addressesAtRisk, { high: 3, medium: 1, low: 0 });
    assert.equal(r.groundwater, "Possible");
    assert.equal(r.dataset, "sample");
  });
  check("[sample] Medium when no high but med>0", () => assert.equal(floodRiskByPostcode("ZZ1 1AB").headlineRisk, "Medium"));
  check("[sample] Low when only low>0", () => assert.equal(floodRiskByPostcode("ZZ1 1AD").headlineRisk, "Low"));
  check("[sample] Very Low when all bands zero", () => assert.equal(floodRiskByPostcode("ZZ1 1AE").headlineRisk, "Very Low"));
  check("[sample] accepts unspaced + lowercase", () => assert.equal(floodRiskByPostcode("zz22aa").headlineRisk, "High"));
}

/* ---------- real-data sanity (only when the official EA dataset is loaded) ---------- */
if (datasetKind === "ea-official") {
  check("[ea] full England dataset loaded (>1M postcodes)", () => assert.ok(datasetSize > 1_000_000));
  check("[ea] a real England postcode resolves to a band", () => {
    const r = floodRiskByPostcode("AL1 1AJ");
    assert.equal(r.found, true);
    assert.equal(r.dataset, "ea-official");
    assert.ok(["High", "Medium", "Low", "Very Low"].includes(r.headlineRisk as string));
  });
  check("[ea] a Scottish postcode is honestly not found", () => {
    const r = floodRiskByPostcode("EH1 1AA");
    assert.equal(r.wellFormed, true);
    assert.equal(r.found, false);
  });
}

/* ---------- JSON-RPC core (dataset-independent) ---------- */
function rpc(method: string, params?: unknown, id: number | string = 1) {
  return handleRpc({ jsonrpc: "2.0", id, method, params }) as any;
}
check("initialize returns floodwise serverInfo", () => {
  const r = rpc("initialize", { protocolVersion: "2025-06-18" });
  assert.equal(r.result.serverInfo.name, "floodwise");
  assert.ok(r.result.capabilities.tools);
});
check("tools/list returns both tools with schemas", () => {
  const r = rpc("tools/list");
  const names = r.result.tools.map((t: any) => t.name).sort();
  assert.deepEqual(names, ["flood_risk_by_postcode", "validate_postcode"]);
  for (const t of r.result.tools) {
    assert.equal(t.inputSchema.type, "object");
    assert.ok(Array.isArray(t.inputSchema.required));
  }
});
check("tools/call flood_risk_by_postcode returns structured payload", () => {
  const r = rpc("tools/call", { name: "flood_risk_by_postcode", arguments: { postcode: "ZZ9 9ZZ" } });
  const p = JSON.parse(r.result.content[0].text);
  assert.equal(p.coverage, "England");
  assert.equal(p.found, false);
});
check("tools/call validate_postcode", () => {
  const r = rpc("tools/call", { name: "validate_postcode", arguments: { postcode: "sw1a1aa" } });
  assert.equal(JSON.parse(r.result.content[0].text).postcode, "SW1A 1AA");
});
check("unknown tool → JSON-RPC error", () => {
  const r = rpc("tools/call", { name: "nope", arguments: {} });
  assert.ok(r.error);
});
check("notifications/initialized → no response body", () => {
  assert.equal(handleRpc({ jsonrpc: "2.0", method: "notifications/initialized" }), null);
});

console.log(`\n${pass} passed, ${fail} failed  (dataset: ${datasetKind}, ${datasetSize} postcodes)`);
if (fail > 0) process.exit(1);
