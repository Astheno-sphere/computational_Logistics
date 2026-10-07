// Pure SVG path utilities — no DOM, so this runs straight under node.
// Run with: node --import tsx --test test/svgpath.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { transformPath, arcToBeziers, pathBounds, svgPlacedBox } from "../src/lib/svgpath.js";

// ── svgPlacedBox ─────────────────────────────────────────────────────────────
// Regression: a one-axis symbol (vertical/horizontal divider) whose degenerate
// viewBox axis is clamped to ~epsilon must NOT explode. Scale is uniform off the
// LONGER extent, so the longest side == wFrac*sheetW and the thin side stays tiny.
test("svgPlacedBox: a wide symbol sizes off width", () => {
  const { s, bw, bh } = svgPlacedBox([100, 40], 0.08, 1000);
  assert.equal(s, (0.08 * 1000) / 100);   // longest extent is width (100)
  assert.equal(bw, 80);
  assert.equal(bh, 32);
});
test("svgPlacedBox: a tall symbol sizes off height (no distortion)", () => {
  const { s, bw, bh } = svgPlacedBox([40, 100], 0.08, 1000);
  assert.equal(s, (0.08 * 1000) / 100);   // longest extent is height (100)
  assert.equal(bh, 80);
  assert.equal(bw, 32);
});
test("svgPlacedBox: a vertical divider (near-zero width) does NOT explode", () => {
  // this is the bug the width-derived scale caused: vw≈1e-6 → sx≈8e7 → ~1e9 px
  const { s, bw, bh } = svgPlacedBox([1e-6, 9], 0.08, 1224);
  assert.ok(s > 0 && Number.isFinite(s));
  assert.ok(bh <= 0.08 * 1224 + 1e-6, "height is the placed longest side (~98px), not 1e9");
  assert.ok(bw < 1e-3, "the near-zero width stays near-zero");
});
test("svgPlacedBox: guards — bad vb / zero width / non-finite → s=0", () => {
  assert.equal(svgPlacedBox(null as any, 0.08, 1000).s, 0);
  assert.equal(svgPlacedBox([0, 0], 0.08, 1000).s, 0);
  assert.equal(svgPlacedBox([10, 10], 0.08, Infinity).s, 0);
});
test("svgPlacedBox: wFrac defaults to 0.08 when missing/invalid", () => {
  assert.equal(svgPlacedBox([100, 50], 0 as any, 1000).s, (0.08 * 1000) / 100);
});

// Pull every number out of a path string, in order.
function nums(d: string): number[] {
  return (d.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
}
// Command letters, in order.
function cmds(d: string): string[] {
  return (d.match(/[A-Za-z]/g) || []);
}
const near = (a: number, b: number, eps = 1e-6) =>
  assert.ok(Math.abs(a - b) <= eps, `expected ${a} ≈ ${b}`);

// ── transformPath ───────────────────────────────────────────────────────────
test("transformPath: identity fn returns an equivalent path", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  const out = transformPath("M0 0 L10 0 L10 10 Z", id);
  assert.deepEqual(cmds(out), ["M", "L", "L", "Z"]);
  assert.deepEqual(nums(out), [0, 0, 10, 0, 10, 10]);
});

test("transformPath: translate+scale on a known square", () => {
  // (x,y) -> (2x+5, 3y+7)
  const fn = (x: number, y: number): [number, number] => [2 * x + 5, 3 * y + 7];
  const out = transformPath("M0 0 L10 0 L10 10 Z", fn);
  assert.deepEqual(cmds(out), ["M", "L", "L", "Z"]);
  assert.deepEqual(nums(out), [5, 7, 25, 7, 25, 37]);
});

test("transformPath: relative m/l/c resolve to absolute coords", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  // m 10 10 (=> M10 10), l 5 0 (=> L15 10), c 0 5 5 5 5 0 (=> C15 15 20 15 20 10)
  const out = transformPath("m10 10 l5 0 c0 5 5 5 5 0", id);
  assert.deepEqual(cmds(out), ["M", "L", "C"]);
  assert.deepEqual(nums(out), [10, 10, 15, 10, 15, 15, 20, 15, 20, 10]);
});

test("transformPath: H/h and V/v expand to L", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  const out = transformPath("M0 0 H10 V10 h-5 v-5", id);
  assert.deepEqual(cmds(out), ["M", "L", "L", "L", "L"]);
  // H10 -> (10,0); V10 -> (10,10); h-5 -> (5,10); v-5 -> (5,5)
  assert.deepEqual(nums(out), [0, 0, 10, 0, 10, 10, 5, 10, 5, 5]);
});

test("transformPath: S reflects the previous cubic control point", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  // C0 10 10 10 10 0  then  S 20 10 20 0
  // prev C2 = (10,10), current = (10,0) → reflected c1 = (10,-10)
  const out = transformPath("M0 0 C0 10 10 10 10 0 S20 10 20 0", id);
  assert.deepEqual(cmds(out), ["M", "C", "C"]);
  const n = nums(out);
  // second cubic: c1=(10,-10) c2=(20,10) end=(20,0)
  assert.deepEqual(n.slice(8), [10, -10, 20, 10, 20, 0]);
});

test("transformPath: S with no preceding cubic uses the current point", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  // No prior C/S: reflected control = current point (5,5)
  const out = transformPath("M5 5 S20 10 20 0", id);
  const n = nums(out);
  assert.deepEqual(n.slice(2), [5, 5, 20, 10, 20, 0]);
});

test("transformPath: T reflects the previous quadratic control point", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  // Q0 10 10 0  then  T20 0
  // prev Qctrl=(0,10), current=(10,0) → reflected = (20,-10)
  const out = transformPath("M0 0 Q0 10 10 0 T20 0", id);
  assert.deepEqual(cmds(out), ["M", "Q", "Q"]);
  const n = nums(out);
  assert.deepEqual(n.slice(6), [20, -10, 20, 0]);
});

test("transformPath: multiple subpaths each keep their own Z + start", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  const out = transformPath("M0 0 L10 0 Z M20 20 L30 20 Z", id);
  assert.deepEqual(cmds(out), ["M", "L", "Z", "M", "L", "Z"]);
});

test("transformPath: Z returns to the correct subpath start", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  // After the first Z the current point must be (0,0), so the relative
  // m 5 5 that follows lands at (5,5) — not relative to (10,0).
  const out = transformPath("M0 0 L10 0 Z m5 5 l1 0", id);
  const n = nums(out);
  // M0 0 L10 0 Z M5 5 L6 5
  assert.deepEqual(n, [0, 0, 10, 0, 5, 5, 6, 5]);
});

test("transformPath: malformed input never throws; non-finite fn drops the segment", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  assert.doesNotThrow(() => transformPath("M0 0 L L blah 10 10 xyz", id));
  assert.doesNotThrow(() => transformPath("garbage 1 2 3 !!!", id));
  // A fn that blows up the second vertex must drop that L, keep the rest.
  const boom = (x: number, y: number): [number, number] => (x === 10 ? [Infinity, y] : [x, y]);
  const out = transformPath("M0 0 L10 0 L0 20", boom);
  assert.deepEqual(cmds(out), ["M", "L"]);
  assert.deepEqual(nums(out), [0, 0, 0, 20]);
});

test("transformPath: empty / blank input → ''", () => {
  const id = (x: number, y: number): [number, number] => [x, y];
  assert.equal(transformPath("", id), "");
  assert.equal(transformPath("   \n\t ", id), "");
  // @ts-expect-error — non-string is tolerated, not thrown
  assert.equal(transformPath(null, id), "");
});

// ── arcToBeziers ────────────────────────────────────────────────────────────
test("arcToBeziers: quarter circle — endpoints match, midpoint ~r from center", () => {
  // Unit-ish circle radius 10 centered at origin: from (10,0) to (0,10),
  // small arc, sweep=1 (CCW in SVG's y-down? here just check geometry).
  const r = 10;
  const segs = arcToBeziers(r, 0, r, r, 0, 0, 1, 0, r);
  assert.ok(segs.length >= 1);
  const last = segs[segs.length - 1];
  near(last[4], 0); // end x
  near(last[5], r); // end y
  // Center is (0,0); the join point between endpoints should sit ~r away.
  const mid = segs[0]; // its endpoint is the arc midpoint for a 1-seg 90° arc
  near(Math.hypot(mid[4], mid[5]), r, 1e-3);
});

test("arcToBeziers: ellipse rx≠ry endpoints match", () => {
  const segs = arcToBeziers(30, 0, 30, 15, 0, 0, 1, 0, 15);
  assert.ok(segs.length >= 1);
  const last = segs[segs.length - 1];
  near(last[4], 0);
  near(last[5], 15);
});

test("arcToBeziers: rotated arc endpoints still match x1,y1", () => {
  const segs = arcToBeziers(5, 5, 20, 10, 37, 1, 0, 40, 30);
  assert.ok(segs.length >= 1);
  const last = segs[segs.length - 1];
  near(last[4], 40, 1e-6);
  near(last[5], 30, 1e-6);
});

test("arcToBeziers: rx==0 → []", () => {
  assert.deepEqual(arcToBeziers(0, 0, 0, 10, 0, 0, 1, 10, 10), []);
  assert.deepEqual(arcToBeziers(0, 0, 10, 0, 0, 0, 1, 10, 10), []);
  // start == end is degenerate too
  assert.deepEqual(arcToBeziers(5, 5, 10, 10, 0, 0, 1, 5, 5), []);
});

test("arcToBeziers: F.6.6 radius correction — endpoints farther than 2*rx", () => {
  // Endpoints 100 apart but rx=ry=10: radii get scaled up; result non-empty,
  // endpoints still match.
  const segs = arcToBeziers(0, 0, 10, 10, 0, 0, 1, 100, 0);
  assert.ok(segs.length >= 1, "corrected arc is non-empty");
  const last = segs[segs.length - 1];
  near(last[4], 100, 1e-6);
  near(last[5], 0, 1e-6);
  for (const s of segs) for (const v of s) assert.ok(Number.isFinite(v), "no NaN controls");
});

test("arcToBeziers: ~270° arc splits into ≥3 cubics", () => {
  // From (10,0) to (0,10) the LONG way (largeArc=1) is ~270°.
  const segs = arcToBeziers(10, 0, 10, 10, 0, 1, 1, 0, 10);
  assert.ok(segs.length >= 3, `expected ≥3 segments, got ${segs.length}`);
});

// ── pathBounds ──────────────────────────────────────────────────────────────
test("pathBounds: a line returns sane bounds", () => {
  assert.deepEqual(pathBounds("M0 0 L10 20"), [0, 0, 10, 20]);
});

test("pathBounds: a cubic includes control points (hull superset)", () => {
  // control hull spans x∈[0,30], y∈[0,40]
  const b = pathBounds("M0 0 C10 40 30 -5 30 10")!;
  assert.ok(b !== null);
  assert.equal(b[0], 0);
  assert.equal(b[1], -5);
  assert.equal(b[2], 30);
  assert.equal(b[3], 40);
});

test("pathBounds: an Infinity coord is skipped, not poisoning bounds", () => {
  const b = pathBounds("M0 0 L1e999 5 L10 10")!;
  assert.ok(b !== null);
  assert.deepEqual(b, [0, 0, 10, 10]);
});

test("pathBounds: empty → null", () => {
  assert.equal(pathBounds(""), null);
  assert.equal(pathBounds("   "), null);
});
