// lineStyles — the pure dash-pattern + dark-boost primitive shared by the canvas
// (SVG) and the marked-set PDF. These pin the two contracts that bite: solid must
// return a FALSY value (not [] / "") so no stray dash attribute is drawn, and
// boostForDark must preserve hue while lightening only genuinely dark colors.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  LINE_STYLES, LINE_STYLE_IDS, dashArrayFor, pdfDashFor, boostForDark, luminance,
  clampWeight, snapWeight, WEIGHT_MIN, WEIGHT_MAX,
} from "../src/lib/lineStyles.js";

test("LINE_STYLES exposes the four expected styles", () => {
  assert.deepEqual(LINE_STYLE_IDS, ["solid", "dashed", "dotted", "dashdot"]);
  const styles = LINE_STYLES as Record<string, { label: string }>;
  for (const id of LINE_STYLE_IDS) assert.ok(styles[id].label);
});

test("dashArrayFor: dashed returns a space-joined SVG string at scale 1", () => {
  assert.equal(dashArrayFor("dashed", 1), "6 4");
  assert.equal(dashArrayFor("dashdot", 1), "8 3 1 3");
});

test("dashArrayFor: divides the pattern by the stage scale (screen-relative)", () => {
  assert.equal(dashArrayFor("dashed", 2), "3 2");
  assert.equal(dashArrayFor("dotted", 4), "0.25 0.75");
});

test("dashArrayFor + pdfDashFor: solid and unknown are FALSY (never [] or empty string)", () => {
  for (const style of ["solid", "wobble", undefined]) {
    const svg = dashArrayFor(style as string, 1);
    assert.ok(!svg, `svg dash for ${style} must be falsy, got ${JSON.stringify(svg)}`);
    assert.notDeepEqual(svg, []);
    const pdf = pdfDashFor(style as string);
    assert.ok(!pdf, `pdf dash for ${style} must be falsy, got ${JSON.stringify(pdf)}`);
    // the exact bug guarded: pdf-lib treats [] as truthy
    assert.notDeepEqual(pdf, []);
  }
});

test("pdfDashFor: dashed returns a fresh page-point array (no scale)", () => {
  assert.deepEqual(pdfDashFor("dashed"), [6, 4]);
  // a fresh copy each call — mutating one must not corrupt the source pattern
  const a = pdfDashFor("dashed") as number[];
  a[0] = 99;
  assert.deepEqual(pdfDashFor("dashed"), [6, 4]);
});

test("boostForDark: a dark color is lightened", () => {
  const dark = "#1f2937"; // near-black navy — invisible on the dark canvas
  const out = boostForDark(dark);
  assert.notEqual(out.toLowerCase(), dark.toLowerCase());
  assert.ok(luminance(out) > luminance(dark), "boosted color must be brighter");
});

test("boostForDark: always returns a valid hex, coercing malformed input (never leaks invalid CSS)", () => {
  const isHex = (s: string) => /^#[0-9a-fA-F]{6}$/.test(s);
  assert.equal(boostForDark("garbage"), "#888888", "unparseable → safe grey");
  for (const bad of ["garbage", "not-a-color", "#xyzxyz", "#12", undefined as unknown as string]) {
    assert.ok(isHex(boostForDark(bad)), `boostForDark(${bad}) returns a valid hex`);
  }
});

test("boostForDark: a light color passes through unchanged", () => {
  assert.equal(boostForDark("#ffffff"), "#ffffff");
  assert.equal(boostForDark("#e8e2d4"), "#e8e2d4");
});

test("boostForDark: hue is preserved when lightening a dark color", () => {
  // a dark saturated blue → still blue after the boost
  const [h] = rgbHsl(boostForDark("#101d6b"));
  assert.ok(Math.abs(h - 235) < 12, `expected a blue hue near 235°, got ${h}`);
});

test("clampWeight: absent/garbage → 1 (legacy markups unchanged), else clamped", () => {
  assert.equal(clampWeight(undefined), 1, "absent weight = ×1");
  assert.equal(clampWeight(null), 1);
  assert.equal(clampWeight("nonsense"), 1);
  assert.equal(clampWeight(0), 1, "non-positive falls back to 1");
  assert.equal(clampWeight(-2), 1);
  assert.equal(clampWeight(1.5), 1.5, "in-range passes through");
  assert.equal(clampWeight(0.1), WEIGHT_MIN, "clamped up to the floor");
  assert.equal(clampWeight(99), WEIGHT_MAX, "clamped down to the ceiling");
});

test("snapWeight: an off-step (imported) value maps to the nearest UI step", () => {
  assert.equal(snapWeight(1.7), 1.5, "1.7 → nearest step 1.5");
  assert.equal(snapWeight(0.75), 0.5, "0.75 → 0.5");
  assert.equal(snapWeight(2.4), 2.5);
  assert.equal(snapWeight(2), 2, "an on-step value is unchanged");
  assert.equal(snapWeight(undefined), 1, "absent → 1 (a step)");
});

// local HSL for the hue assertion (kept out of the lib's public surface)
function rgbHsl(hex: string): [number, number, number] {
  const s = hex.replace("#", "");
  const r = parseInt(s.slice(0, 2), 16) / 255, g = parseInt(s.slice(2, 4), 16) / 255, b = parseInt(s.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  const l = (max + min) / 2;
  if (d === 0) return [0, 0, l];
  const sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let hh;
  if (max === r) hh = ((g - b) / d) % 6;
  else if (max === g) hh = (b - r) / d + 2;
  else hh = (r - g) / d + 4;
  hh *= 60;
  if (hh < 0) hh += 360;
  return [hh, sat, l];
}
