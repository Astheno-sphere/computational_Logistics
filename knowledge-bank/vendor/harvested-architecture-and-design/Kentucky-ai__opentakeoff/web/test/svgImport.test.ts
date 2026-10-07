// Pure svgToStamp / helpers — no DOM, so this runs straight under node.
// Run with: node --import tsx --test test/svgImport.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  svgToStamp,
  parseTransform,
  applyMatrix,
  primitiveToPath,
} from "../src/lib/svgImport.js";

// Pull every number out of a path string, in order.
function nums(d: string): number[] {
  return (d.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/gi) || []).map(Number);
}
const near = (a: number, b: number, eps = 1e-4) =>
  assert.ok(Math.abs(a - b) <= eps, `expected ${a} ≈ ${b}`);

// A single primitive with no transforms.
function prim(tag: string, attrs: Record<string, string>, transforms: string[] = []) {
  return { tag, attrs, transforms };
}

// ── rect ─────────────────────────────────────────────────────────────────────
test("svgToStamp: sharp rect → one element, vb≈[w,h], default color/fill", () => {
  const s = svgToStamp({ primitives: [prim("rect", { x: "0", y: "0", width: "10", height: "6" })] })!;
  assert.ok(s !== null);
  assert.equal(s.elements.length, 1);
  const el = s.elements[0];
  assert.equal(el.type, "svg");
  assert.ok(typeof el.path === "string" && el.path.length > 0);
  assert.deepEqual(el.at, [0, 0]);
  assert.equal(el.w, 0.08);
  near(el.vb[0], 10);
  near(el.vb[1], 6);
  assert.equal(el.color, "#0e1a2e"); // no stroke, no usable fill
  assert.equal(el.fill, "none");
  assert.equal(s.name, "Imported SVG");
});

test("svgToStamp: rounded rect produces a valid non-empty path", () => {
  const s = svgToStamp({
    primitives: [prim("rect", { x: "0", y: "0", width: "10", height: "10", rx: "2", ry: "2" })],
  })!;
  assert.ok(s !== null);
  assert.equal(s.elements.length, 1);
  assert.ok(s.elements[0].path.length > 0);
  near(s.elements[0].vb[0], 10);
  near(s.elements[0].vb[1], 10);
});

// ── circle / ellipse ─────────────────────────────────────────────────────────
test("svgToStamp: circle → non-empty path, vb≈[2r,2r]", () => {
  const s = svgToStamp({ primitives: [prim("circle", { cx: "5", cy: "5", r: "5" })] })!;
  assert.ok(s !== null);
  assert.ok(s.elements[0].path.length > 0);
  near(s.elements[0].vb[0], 10, 1e-3);
  near(s.elements[0].vb[1], 10, 1e-3);
});

test("svgToStamp: ellipse → vb≈[2rx,2ry]", () => {
  const s = svgToStamp({ primitives: [prim("ellipse", { cx: "0", cy: "0", rx: "8", ry: "3" })] })!;
  assert.ok(s !== null);
  near(s.elements[0].vb[0], 16, 1e-3);
  near(s.elements[0].vb[1], 6, 1e-3);
});

// ── line / polyline / polygon ────────────────────────────────────────────────
test("svgToStamp: line → non-empty path with 2D extent", () => {
  const s = svgToStamp({ primitives: [prim("line", { x1: "0", y1: "0", x2: "10", y2: "4" })] })!;
  assert.ok(s !== null);
  near(s.elements[0].vb[0], 10);
  near(s.elements[0].vb[1], 4);
});

test("svgToStamp: polyline is open (no trailing Z)", () => {
  const s = svgToStamp({ primitives: [prim("polyline", { points: "0,0 10,0 10,5" })] })!;
  assert.ok(s !== null);
  assert.ok(!/Z\s*$/.test(s.elements[0].path.trim()));
});

test("svgToStamp: polygon path ends with Z", () => {
  const s = svgToStamp({ primitives: [prim("polygon", { points: "0,0 10,0 10,5" })] })!;
  assert.ok(s !== null);
  assert.ok(/Z$/.test(s.elements[0].path.trim()));
});

// ── transform composition ────────────────────────────────────────────────────
test("parseTransform: translate then scale composes left→right", () => {
  const M = parseTransform("translate(100,0) scale(2)");
  // x' = 2x + 100, y' = 2y
  assert.deepEqual(M, [2, 0, 0, 2, 100, 0]);
  assert.deepEqual(applyMatrix(M, 0, 0), [100, 0]);
  assert.deepEqual(applyMatrix(M, 5, 5), [110, 10]);
});

test("parseTransform: multi-function string and array fold agree", () => {
  // Folding ["translate(100,0)","scale(2)"] as svgToStamp does == one string.
  let M = [1, 0, 0, 1, 0, 0] as number[];
  for (const t of ["translate(100,0)", "scale(2)"]) {
    const m2 = parseTransform(t);
    // replicate matmul used internally
    const [a1, b1, c1, d1, e1, f1] = M;
    const [a2, b2, c2, d2, e2, f2] = m2;
    M = [
      a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
      a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
      a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1,
    ];
  }
  assert.deepEqual(M, parseTransform("translate(100,0) scale(2)"));
});

test("svgToStamp: transforms land a rect at the expected user-space size", () => {
  // 5×5 rect under translate(100,0) scale(2) → user-space 10×10 (then normalized).
  const s = svgToStamp({
    primitives: [prim("rect", { x: "0", y: "0", width: "5", height: "5" }, ["translate(100,0)", "scale(2)"])],
  })!;
  assert.ok(s !== null);
  near(s.elements[0].vb[0], 10);
  near(s.elements[0].vb[1], 10);
});

test("svgToStamp: rotate(90) bakes — horizontal L becomes a vertical extent", () => {
  const base = svgToStamp({ primitives: [prim("polyline", { points: "0,0 10,0 10,1" })] })!;
  near(base.elements[0].vb[0], 10);
  near(base.elements[0].vb[1], 1);
  const rot = svgToStamp({
    primitives: [prim("polyline", { points: "0,0 10,0 10,1" }, ["rotate(90)"])],
  })!;
  // extents swap: now tall (10) and thin (1)
  near(rot.elements[0].vb[0], 1);
  near(rot.elements[0].vb[1], 10);
});

test("parseTransform: rotate about a center, matrix, skew, unknown→identity", () => {
  // rotate(90, 5, 5): (5,5) fixed, (5,0) -> (10,5)
  const R = parseTransform("rotate(90 5 5)");
  const p = applyMatrix(R, 5, 0);
  near(p[0], 10);
  near(p[1], 5);
  assert.deepEqual(parseTransform("matrix(1,2,3,4,5,6)"), [1, 2, 3, 4, 5, 6]);
  const sk = parseTransform("skewX(45)");
  near(sk[2], 1); // tan(45°) = 1
  assert.deepEqual(parseTransform("bogus(1,2)"), [1, 0, 0, 1, 0, 0]);
  assert.deepEqual(parseTransform(""), [1, 0, 0, 1, 0, 0]);
});

// ── color / fill parsing ─────────────────────────────────────────────────────
test("svgToStamp: stroke attribute becomes color, fill stays none by default", () => {
  const s = svgToStamp({ primitives: [prim("rect", { x: "0", y: "0", width: "4", height: "4", stroke: "#ff0000" })] })!;
  assert.equal(s.elements[0].color, "#ff0000");
  assert.equal(s.elements[0].fill, "none");
});

test("svgToStamp: fill without stroke drives both color and fill", () => {
  const s = svgToStamp({ primitives: [prim("rect", { x: "0", y: "0", width: "4", height: "4", fill: "#00ff00" })] })!;
  assert.equal(s.elements[0].color, "#00ff00");
  assert.equal(s.elements[0].fill, "#00ff00");
});

test("svgToStamp: style= overrides presentation attrs, fill:none respected", () => {
  const s = svgToStamp({
    primitives: [
      prim("rect", { x: "0", y: "0", width: "4", height: "4", stroke: "#111111", fill: "#222222", style: "stroke:#abcdef;fill:none" }),
    ],
  })!;
  assert.equal(s.elements[0].color, "#abcdef");
  assert.equal(s.elements[0].fill, "none");
});

test("svgToStamp: stroke:none with a fill → color falls back to the fill", () => {
  const s = svgToStamp({ primitives: [prim("rect", { x: "0", y: "0", width: "4", height: "4", stroke: "none", fill: "#123456" })] })!;
  assert.equal(s.elements[0].color, "#123456");
  assert.equal(s.elements[0].fill, "#123456");
});

// ── multi-shape ──────────────────────────────────────────────────────────────
test("svgToStamp: multiple shapes share the same vb value (own arrays); union bounds correct", () => {
  const s = svgToStamp({
    primitives: [
      prim("rect", { x: "0", y: "0", width: "4", height: "4" }),
      prim("rect", { x: "10", y: "6", width: "2", height: "4" }),
    ],
    name: "Two",
  })!;
  assert.equal(s.elements.length, 2);
  assert.notStrictEqual(s.elements[0].vb, s.elements[1].vb);  // own arrays (no aliasing footgun)
  assert.deepEqual(s.elements[0].vb, s.elements[1].vb);       // same value
  // union: x∈[0,12], y∈[0,10]
  near(s.elements[0].vb[0], 12);
  near(s.elements[0].vb[1], 10);
  assert.equal(s.name, "Two");
});

// ── degenerate ───────────────────────────────────────────────────────────────
test("svgToStamp: zero shapes → null", () => {
  assert.equal(svgToStamp({ primitives: [] }), null);
  assert.equal(svgToStamp({ primitives: [prim("rect", { width: "bad" })] }), null);
});

test("svgToStamp: a single zero-size rect → null", () => {
  assert.equal(svgToStamp({ primitives: [prim("rect", { x: "3", y: "3", width: "0", height: "0" })] }), null);
});

test("svgToStamp: a one-axis symbol (zero height line) is allowed, vb clamped positive", () => {
  // a horizontal cut-line / divider is legitimate — only a true point → null
  const s = svgToStamp({ primitives: [prim("polyline", { points: "0,5 4,5 9,5" })] });
  assert.ok(s !== null);
  assert.ok(s!.elements[0].vb[0] > 0 && s!.elements[0].vb[1] > 0, "vb clamped positive on the degenerate axis");
});

test("svgToStamp: a true point (zero width AND height) → null", () => {
  assert.equal(svgToStamp({ primitives: [prim("line", { x1: "3", y1: "3", x2: "3", y2: "3" })] }), null);
});

test("svgToStamp: colors normalize to #rrggbb (named / rgb / hsl / short hex)", () => {
  const one = (attrs: any) => svgToStamp({ primitives: [prim("rect", { x: "0", y: "0", width: "10", height: "10", ...attrs })] })!.elements[0];
  assert.equal(one({ fill: "red", stroke: "none" }).fill, "#ff0000");
  assert.equal(one({ fill: "black" }).color, "#000000");
  assert.equal(one({ stroke: "rgb(255, 0, 0)", fill: "none" }).color, "#ff0000");
  assert.equal(one({ stroke: "rgb(100%, 0%, 0%)", fill: "none" }).color, "#ff0000");
  assert.equal(one({ stroke: "hsl(120, 100%, 50%)", fill: "none" }).color, "#00ff00");
  assert.equal(one({ fill: "#f00", stroke: "none" }).fill, "#ff0000");
  assert.equal(one({ fill: "#ff0000ff", stroke: "none" }).fill, "#ff0000");   // alpha dropped
  // an unrecognized color falls back to the default ink (not passed through raw)
  assert.equal(one({ stroke: "chartreusey-nonsense", fill: "none" }).color, "#0e1a2e");
});

test("svgToStamp: vb is a fresh array per element (no shared reference)", () => {
  const s = svgToStamp({ primitives: [
    prim("rect", { x: "0", y: "0", width: "10", height: "10" }),
    prim("rect", { x: "0", y: "0", width: "10", height: "10" }),
  ] });
  assert.ok(s!.elements.length === 2);
  assert.notEqual(s!.elements[0].vb, s!.elements[1].vb, "each element owns its vb array");
  assert.deepEqual(s!.elements[0].vb, s!.elements[1].vb);
});

test("svgToStamp: non-array primitives → null", () => {
  // @ts-expect-error — tolerant, not thrown
  assert.equal(svgToStamp({ primitives: null }), null);
  assert.equal(svgToStamp({}), null);
});

// ── caps ─────────────────────────────────────────────────────────────────────
test("svgToStamp: more than 400 primitives → at most 400 elements", () => {
  const many = [];
  for (let i = 0; i < 500; i++) many.push(prim("rect", { x: String(i), y: "0", width: "1", height: "1" }));
  const s = svgToStamp({ primitives: many })!;
  assert.ok(s !== null);
  assert.equal(s.elements.length, 400);
});

// ── primitiveToPath edge cases ───────────────────────────────────────────────
test("primitiveToPath: missing required attrs → ''", () => {
  assert.equal(primitiveToPath("circle", { cx: "0", cy: "0" }), "");
  assert.equal(primitiveToPath("line", { x1: "0", y1: "0" }), "");
  assert.equal(primitiveToPath("polygon", { points: "1,2" }), "");
  assert.equal(primitiveToPath("unknown", {}), "");
  assert.equal(primitiveToPath("path", { d: "M0 0 L1 1" }), "M0 0 L1 1");
});
