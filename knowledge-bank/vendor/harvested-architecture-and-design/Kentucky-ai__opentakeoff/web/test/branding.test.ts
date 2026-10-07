// Branding mode: the pure resolver that both render paths (report masthead +
// marked-set cover) and the exports share. load/saveBrandingSelection touch the
// IndexedDB meta KV (browser-only) — exercised in the app, deliberately NOT here.
import { test } from "node:test";
import assert from "node:assert/strict";
import { resolveBranding, OT_NAME, OT_CREDIT } from "../src/lib/branding.js";
import { totalsToCsv } from "../src/lib/totals.js";
import { shapesToCsv } from "../src/lib/shapesExport.js";
import { rfisToCsv } from "../src/lib/rfi.js";

const PROFILES = [
  { id: "a", name: "345 Flooring", address: "1 A St", logo: "data:image/png;base64,AAA" },
  { id: "b", name: "Fin Workspaces", address: "2 B St" },
];

test("default mode → OpenTakeoff, no company, no credit, prefixed cover title", () => {
  const b = resolveBranding({ mode: "default", profileId: "a", profiles: PROFILES });
  assert.equal(b.clear, false);
  assert.equal(b.company, null);
  assert.equal(b.brandName, OT_NAME);
  assert.equal(b.credit, null);
  assert.equal(b.coverTitle, "OpenTakeoff · Marked Set");
});

test("clear-label with a valid profile → that trade name brands the doc", () => {
  const b = resolveBranding({ mode: "clearlabel", profileId: "b", profiles: PROFILES });
  assert.equal(b.clear, true);
  assert.deepEqual(b.company, { name: "Fin Workspaces", address: "2 B St", logo: undefined });
  assert.equal(b.brandName, "Fin Workspaces");
  assert.equal(b.credit, OT_CREDIT);
  assert.equal(b.coverTitle, "Marked Set");
});

test("clear-label carries the logo when the profile has one", () => {
  const b = resolveBranding({ mode: "clearlabel", profileId: "a", profiles: PROFILES });
  assert.equal(b.company?.logo, "data:image/png;base64,AAA");
});

test("clear-label with no profiles falls back to default (nothing to brand as)", () => {
  const b = resolveBranding({ mode: "clearlabel", profileId: "a", profiles: [] });
  assert.equal(b.clear, false);
  assert.equal(b.brandName, OT_NAME);
  assert.equal(b.coverTitle, "OpenTakeoff · Marked Set");
});

test("clear-label with a stale profileId falls back to the first profile", () => {
  const b = resolveBranding({ mode: "clearlabel", profileId: "gone", profiles: PROFILES });
  assert.equal(b.clear, true);
  assert.equal(b.brandName, "345 Flooring");
});

test("clear-label profile without a name → brandName degrades to OpenTakeoff, company kept", () => {
  const b = resolveBranding({ mode: "clearlabel", profileId: "c", profiles: [{ id: "c", logo: "data:x" }] });
  assert.equal(b.clear, true);
  assert.equal(b.brandName, OT_NAME);
  assert.equal(b.company?.logo, "data:x");
});

test("garbage / missing mode → default", () => {
  assert.equal(resolveBranding({}).clear, false);
  assert.equal(resolveBranding({ mode: "nonsense", profiles: PROFILES }).clear, false);
  assert.equal(resolveBranding(undefined).brandName, OT_NAME);
});

// export titles follow the brand name (decision: exports follow the mode) — the
// resolver hands brandName to each CSV, defaulting to OpenTakeoff when unbranded
test("CSV export titles carry the brand name (default OpenTakeoff)", () => {
  assert.match(totalsToCsv([], "Proj"), /^# Proj — OpenTakeoff report/);
  assert.match(totalsToCsv([], "Proj", null, null, null, null, null, "345 Flooring"), /^# Proj — 345 Flooring report/);
  assert.match(shapesToCsv([], "Proj"), /^# Proj — OpenTakeoff shapes/);
  assert.match(shapesToCsv([], "Proj", "345 Flooring"), /^# Proj — 345 Flooring shapes/);
  assert.match(rfisToCsv([], [], "Proj"), /^# Proj — OpenTakeoff RFI log/);
  assert.match(rfisToCsv([], [], "Proj", null, "345 Flooring"), /^# Proj — 345 Flooring RFI log/);
});
