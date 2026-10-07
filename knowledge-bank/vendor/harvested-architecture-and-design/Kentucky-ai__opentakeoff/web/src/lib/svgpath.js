// Pure SVG path utilities — no DOM, no deps, no Date/Math.random. Everything
// here is deterministic given its inputs so stamps can be re-emitted identically
// on canvas and in the exported PDF.
//
// transformPath parses any SVG `d` (absolute + relative M/L/H/V/C/S/Q/T/A/Z),
// applies an affine map POINTWISE to every emitted coordinate (control points
// included — correct for affine maps), and re-emits a normalized path using only
// absolute M/L/C/Q/Z. Arcs are flattened to cubics up front (in user space) so
// the pointwise map lands on ordinary bezier controls.

// ── low-level scanner ───────────────────────────────────────────────────────
// A separator is whitespace or a comma. Numbers follow the SVG number grammar
// (optional sign, digits, fraction, exponent); arc flags are a single 0/1.
function isSep(c) {
  return c === " " || c === "\t" || c === "\n" || c === "\r" || c === "\f" || c === ",";
}
function isDigit(c) {
  return c >= "0" && c <= "9";
}

class Scanner {
  constructor(s) {
    this.s = s;
    this.i = 0;
    this.n = s.length;
  }

  skipSep() {
    while (this.i < this.n && isSep(this.s[this.i])) this.i++;
  }

  eof() {
    this.skipSep();
    return this.i >= this.n;
  }

  // The next non-separator char if it's a command letter, else null.
  peekCmd() {
    this.skipSep();
    if (this.i >= this.n) return null;
    const c = this.s[this.i];
    return (c >= "a" && c <= "z") || (c >= "A" && c <= "Z") ? c : null;
  }

  readCmd() {
    const c = this.peekCmd();
    if (c !== null) this.i++;
    return c;
  }

  // Reads one number; returns NaN (without consuming) if none is present.
  readNumber() {
    this.skipSep();
    const s = this.s;
    const start = this.i;
    let i = this.i;
    if (s[i] === "+" || s[i] === "-") i++;
    let sawDigit = false;
    while (i < this.n && isDigit(s[i])) { i++; sawDigit = true; }
    if (s[i] === ".") {
      i++;
      while (i < this.n && isDigit(s[i])) { i++; sawDigit = true; }
    }
    if (sawDigit && (s[i] === "e" || s[i] === "E")) {
      let j = i + 1;
      if (s[j] === "+" || s[j] === "-") j++;
      if (j < this.n && isDigit(s[j])) {
        j++;
        while (j < this.n && isDigit(s[j])) j++;
        i = j;
      }
    }
    if (!sawDigit) return NaN;
    this.i = i;
    return parseFloat(s.slice(start, i));
  }

  // Arc flag: a single "0" or "1" (they may be packed with no separator).
  readFlag() {
    this.skipSep();
    const c = this.s[this.i];
    if (c === "0") { this.i++; return 0; }
    if (c === "1") { this.i++; return 1; }
    return NaN;
  }
}

// ── normalization ───────────────────────────────────────────────────────────
// Parse `d` into a flat list of absolute primitives:
//   { t: "M"|"L", p: [x, y] }
//   { t: "C", p: [c1x, c1y, c2x, c2y, x, y] }
//   { t: "Q", p: [cx, cy, x, y] }
//   { t: "Z" }
// Malformed number runs are skipped; nothing throws.
function normalize(d) {
  const out = [];
  if (typeof d !== "string") return out;
  const sc = new Scanner(d);

  let cx = 0, cy = 0;       // current point
  let sx = 0, sy = 0;       // subpath start (for Z)
  let prevType = "other";   // "C", "Q" or "other" — for S/T reflection
  let pc2x = 0, pc2y = 0;   // previous cubic 2nd control point
  let pqx = 0, pqy = 0;     // previous quadratic control point

  while (!sc.eof()) {
    const letter = sc.readCmd();
    if (letter === null) {
      // Leading junk with no command — drop a number (or a char) to progress.
      const before = sc.i;
      if (Number.isNaN(sc.readNumber()) && sc.i === before) sc.i++;
      continue;
    }
    const C = letter.toUpperCase();
    const rel = letter !== C; // lowercase letter ⇒ relative

    if (C === "Z") {
      out.push({ t: "Z" });
      cx = sx; cy = sy;
      prevType = "other";
      continue;
    }

    // Read one coordinate pair (absolute), honoring `rel` against cx/cy which
    // stays fixed for the whole group (relative controls share the anchor).
    const pair = () => {
      const x = sc.readNumber();
      const y = sc.readNumber();
      if (Number.isNaN(x) || Number.isNaN(y)) return null;
      return rel ? [cx + x, cy + y] : [x, y];
    };

    let first = true;
    while (!sc.eof() && sc.peekCmd() === null) {
      const before = sc.i;
      const effC = C === "M" && !first ? "L" : C; // extra M groups are L's
      let ok = true;

      switch (effC) {
        case "M": {
          const p = pair();
          if (!p) { ok = false; break; }
          out.push({ t: "M", p });
          cx = p[0]; cy = p[1]; sx = p[0]; sy = p[1];
          prevType = "other";
          break;
        }
        case "L": {
          const p = pair();
          if (!p) { ok = false; break; }
          out.push({ t: "L", p });
          cx = p[0]; cy = p[1];
          prevType = "other";
          break;
        }
        case "H": {
          const x = sc.readNumber();
          if (Number.isNaN(x)) { ok = false; break; }
          const nx = rel ? cx + x : x;
          out.push({ t: "L", p: [nx, cy] });
          cx = nx;
          prevType = "other";
          break;
        }
        case "V": {
          const y = sc.readNumber();
          if (Number.isNaN(y)) { ok = false; break; }
          const ny = rel ? cy + y : y;
          out.push({ t: "L", p: [cx, ny] });
          cy = ny;
          prevType = "other";
          break;
        }
        case "C": {
          const p1 = pair(), p2 = pair(), p3 = pair();
          if (!p1 || !p2 || !p3) { ok = false; break; }
          out.push({ t: "C", p: [p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]] });
          pc2x = p2[0]; pc2y = p2[1];
          cx = p3[0]; cy = p3[1];
          prevType = "C";
          break;
        }
        case "S": {
          const c1 = prevType === "C" ? [2 * cx - pc2x, 2 * cy - pc2y] : [cx, cy];
          const p2 = pair(), p3 = pair();
          if (!p2 || !p3) { ok = false; break; }
          out.push({ t: "C", p: [c1[0], c1[1], p2[0], p2[1], p3[0], p3[1]] });
          pc2x = p2[0]; pc2y = p2[1];
          cx = p3[0]; cy = p3[1];
          prevType = "C";
          break;
        }
        case "Q": {
          const c = pair(), p = pair();
          if (!c || !p) { ok = false; break; }
          out.push({ t: "Q", p: [c[0], c[1], p[0], p[1]] });
          pqx = c[0]; pqy = c[1];
          cx = p[0]; cy = p[1];
          prevType = "Q";
          break;
        }
        case "T": {
          const c = prevType === "Q" ? [2 * cx - pqx, 2 * cy - pqy] : [cx, cy];
          const p = pair();
          if (!p) { ok = false; break; }
          out.push({ t: "Q", p: [c[0], c[1], p[0], p[1]] });
          pqx = c[0]; pqy = c[1];
          cx = p[0]; cy = p[1];
          prevType = "Q";
          break;
        }
        case "A": {
          const rx = sc.readNumber();
          const ry = sc.readNumber();
          const rot = sc.readNumber();
          const laf = sc.readFlag();
          const sf = sc.readFlag();
          const ex = sc.readNumber();
          const ey = sc.readNumber();
          if (
            Number.isNaN(rx) || Number.isNaN(ry) || Number.isNaN(rot) ||
            Number.isNaN(laf) || Number.isNaN(sf) || Number.isNaN(ex) || Number.isNaN(ey)
          ) { ok = false; break; }
          const nex = rel ? cx + ex : ex;
          const ney = rel ? cy + ey : ey;
          const cubics = arcToBeziers(cx, cy, rx, ry, rot, laf, sf, nex, ney);
          if (cubics.length === 0) {
            out.push({ t: "L", p: [nex, ney] });
          } else {
            for (const seg of cubics) {
              out.push({ t: "C", p: [seg[0], seg[1], seg[2], seg[3], seg[4], seg[5]] });
            }
          }
          cx = nex; cy = ney;
          prevType = "other";
          break;
        }
        default:
          ok = false;
      }

      first = false;
      if (!ok) {
        if (sc.i === before) sc.i++; // guarantee forward progress, then resync
        break;
      }
    }
  }

  return out;
}

// ── number formatting ───────────────────────────────────────────────────────
// Round to ~4 decimals and strip trailing zeros; -0 renders as 0.
function fmt(n) {
  let r = Math.round(n * 1e4) / 1e4;
  if (Object.is(r, -0)) r = 0;
  return String(r);
}

/**
 * Parse an SVG path `d`, apply an affine `fn(x, y) => [x2, y2]` to every
 * absolute coordinate (control points included), and re-emit a normalized
 * absolute path using only M/L/C/Q/Z.
 *
 * @param {string} d
 * @param {(x: number, y: number) => [number, number]} fn
 * @returns {string}
 */
export function transformPath(d, fn) {
  const segs = normalize(d);
  const parts = [];

  for (const seg of segs) {
    if (seg.t === "Z") { parts.push("Z"); continue; }

    const src = seg.p;
    const dst = new Array(src.length);
    let bad = false;
    for (let k = 0; k < src.length; k += 2) {
      const r = fn(src[k], src[k + 1]);
      const x = r[0], y = r[1];
      if (!Number.isFinite(x) || !Number.isFinite(y)) { bad = true; break; }
      dst[k] = x; dst[k + 1] = y;
    }
    if (bad) continue; // drop segments that would emit NaN/Infinity

    let s = seg.t;
    for (let k = 0; k < dst.length; k++) s += " " + fmt(dst[k]);
    parts.push(s);
  }

  return parts.join(" ");
}

/**
 * SVG endpoint-arc → array of cubic bezier segments, each
 * `[c1x, c1y, c2x, c2y, ex, ey]`, in the SAME user space as the inputs.
 * Implements W3C SVG F.6.5 (endpoint→center) and F.6.6 (radius correction).
 * Returns `[]` for a degenerate arc (zero/non-finite radius, or start==end);
 * the caller should then emit a straight line to (x1, y1).
 *
 * @returns {number[][]}
 */
export function arcToBeziers(x0, y0, rx, ry, xAxisRotationDeg, largeArcFlag, sweepFlag, x1, y1) {
  if (
    !Number.isFinite(x0) || !Number.isFinite(y0) ||
    !Number.isFinite(x1) || !Number.isFinite(y1) ||
    !Number.isFinite(rx) || !Number.isFinite(ry) || !Number.isFinite(xAxisRotationDeg)
  ) return [];

  rx = Math.abs(rx);
  ry = Math.abs(ry);
  if (rx === 0 || ry === 0) return [];
  if (x0 === x1 && y0 === y1) return [];

  const large = Boolean(largeArcFlag);
  const sweep = Boolean(sweepFlag);

  const phi = (xAxisRotationDeg * Math.PI) / 180;
  const cosP = Math.cos(phi);
  const sinP = Math.sin(phi);

  // F.6.5.1 — (x1', y1') in the rotated frame.
  const dx = (x0 - x1) / 2;
  const dy = (y0 - y1) / 2;
  const x1p = cosP * dx + sinP * dy;
  const y1p = -sinP * dx + cosP * dy;

  // F.6.6 — scale radii up if they can't span the endpoints.
  let rxs = rx * rx;
  let rys = ry * ry;
  const x1ps = x1p * x1p;
  const y1ps = y1p * y1p;
  const lambda = x1ps / rxs + y1ps / rys;
  if (lambda > 1) {
    const s = Math.sqrt(lambda);
    rx *= s; ry *= s;
    rxs = rx * rx; rys = ry * ry;
  }

  // F.6.5.2 — center (cx', cy') in the rotated frame.
  const den = rxs * y1ps + rys * x1ps;
  if (den === 0) return [];
  let num = rxs * rys - rxs * y1ps - rys * x1ps;
  if (num < 0) num = 0;
  const co = (large !== sweep ? 1 : -1) * Math.sqrt(num / den);
  const cxp = co * ((rx * y1p) / ry);
  const cyp = co * ((-ry * x1p) / rx);

  // F.6.5.3 — center in user space.
  const cx = cosP * cxp - sinP * cyp + (x0 + x1) / 2;
  const cy = sinP * cxp + cosP * cyp + (y0 + y1) / 2;

  // F.6.5.5/6 — start angle and sweep.
  const ux = (x1p - cxp) / rx;
  const uy = (y1p - cyp) / ry;
  const vx = (-x1p - cxp) / rx;
  const vy = (-y1p - cyp) / ry;

  const angle = (uxa, uya, vxa, vya) => {
    const dot = uxa * vxa + uya * vya;
    const len = Math.sqrt((uxa * uxa + uya * uya) * (vxa * vxa + vya * vya));
    let a = len === 0 ? 0 : Math.acos(Math.min(1, Math.max(-1, dot / len)));
    if (uxa * vya - uya * vxa < 0) a = -a;
    return a;
  };

  const theta1 = angle(1, 0, ux, uy);
  let dtheta = angle(ux, uy, vx, vy);
  if (!sweep && dtheta > 0) dtheta -= 2 * Math.PI;
  if (sweep && dtheta < 0) dtheta += 2 * Math.PI;

  const nSegs = Math.max(1, Math.ceil(Math.abs(dtheta) / (Math.PI / 2)));
  const delta = dtheta / nSegs;
  const alpha = (4 / 3) * Math.tan(delta / 4);

  const point = (theta) => {
    const ct = Math.cos(theta), st = Math.sin(theta);
    return [
      cosP * rx * ct - sinP * ry * st + cx,
      sinP * rx * ct + cosP * ry * st + cy,
    ];
  };
  const deriv = (theta) => {
    const ct = Math.cos(theta), st = Math.sin(theta);
    const lx = -rx * st, ly = ry * ct; // local ellipse tangent
    return [cosP * lx - sinP * ly, sinP * lx + cosP * ly];
  };

  const result = [];
  let a = theta1;
  let p1 = point(a);
  let d1 = deriv(a);
  for (let k = 0; k < nSegs; k++) {
    const b = a + delta;
    const p2 = point(b);
    const d2 = deriv(b);
    result.push([
      p1[0] + alpha * d1[0], p1[1] + alpha * d1[1],
      p2[0] - alpha * d2[0], p2[1] - alpha * d2[1],
      p2[0], p2[1],
    ]);
    a = b; p1 = p2; d1 = d2;
  }
  return result;
}

/**
 * Bounds over all line endpoints AND bezier control points (a control-hull
 * superset is acceptable). Non-finite coordinates are skipped, so a single
 * Infinity can't poison the result.
 *
 * @param {string} d
 * @returns {[number, number, number, number] | null}
 */
export function pathBounds(d) {
  const segs = normalize(d);
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  let any = false;

  for (const seg of segs) {
    if (seg.t === "Z") continue;
    const p = seg.p;
    for (let k = 0; k < p.length; k += 2) {
      const x = p[k], y = p[k + 1];
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
      any = true;
    }
  }

  return any ? [minX, minY, maxX, maxY] : null;
}

/**
 * Placed size of an `svg` stamp element in a target pixel space. The scale is
 * uniform (never distorts) and derived from the element's **longer** viewBox
 * extent, so `wFrac` (a fraction of `sheetW`) sizes the symbol's longest side —
 * and neither axis can blow up when the other is ~0 (a vertical or horizontal
 * divider whose degenerate viewBox axis was clamped to a tiny epsilon).
 *
 * @param {[number, number]} vb  local viewBox size [vw, vh]
 * @param {number} wFrac         placed longest-side length as a fraction of sheetW (default 0.08)
 * @param {number} sheetW        target width in px (sheet/panel width)
 * @returns {{ s: number, bw: number, bh: number }}  scale + placed box px; s<=0 ⇒ nothing to draw
 */
export function svgPlacedBox(vb, wFrac, sheetW) {
  const vw = Array.isArray(vb) ? Number(vb[0]) : 0;
  const vh = Array.isArray(vb) ? Number(vb[1]) : 0;
  const longest = Math.max(vw, vh);
  const w = Number(wFrac) > 0 ? Number(wFrac) : 0.08;
  const s = longest > 0 && Number.isFinite(longest) && Number.isFinite(sheetW) ? (w * sheetW) / longest : 0;
  return { s, bw: vw * s, bh: vh * s };
}
