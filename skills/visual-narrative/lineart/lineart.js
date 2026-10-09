/* lineart.js: drawing primitives for line-art plates (visual-narrative grammar v2).
 *
 * Thin cream strokes on a dark ground, one accent, stippled vegetation, line people and vehicles,
 * isometric layers and node-wire diagrams. Every primitive draws into an SVG group and returns it,
 * so plates stay plain SVG that prints, screenshots and embeds without a library.
 *
 *   const L = LineArt(svgElement, {cream:"#EFE3CC", accent:"#D9734E", ground:"#2f1519"});
 *   L.house(g, 100, 400, 120, 90); L.tree(g, 260, 400, 90, 7); L.person(g, 320, 400, 34, 2);
 */
/* Three plate families, one grammar. oxblood: tool and method plates; charcoal: urban-theory plates
 * (near-black ground, cream line, vermilion accent); sage: step-by-step "how to" plates (mono code, sage accent). */
const LINEART_THEMES = {
  oxblood:  { ground: "#2f1519", cream: "#EFE3CC", dim: "#A8958A", accent: "#D9734E", title: "Roboto", weight: 900 },
  charcoal: { ground: "#151413", cream: "#E9E1D0", dim: "#8E877D", accent: "#D2412B", title: "Inter", weight: 800 },
  sage:     { ground: "#161512", cream: "#EDE6D6", dim: "#8E877D", accent: "#8FA07E", title: "Inter", weight: 800 },
};
function LineArt(svg, opt) {
  const C = Object.assign({ cream: "#EFE3CC", dim: "#A8958A", accent: "#D9734E", ground: "#2f1519", sw: 1 }, opt || {});
  const NS = "http://www.w3.org/2000/svg";
  const el = (p, tag, a, txt) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); if (txt !== undefined) e.textContent = txt; p.appendChild(e); return e; };
  const line = (p, d, o) => el(p, "path", Object.assign({ d, fill: "none", stroke: C.cream, "stroke-width": C.sw, "stroke-linecap": "round", "stroke-linejoin": "round" }, o || {}));
  const rng = seed => { let s = (seed * 9301 + 49297) % 233280 || 1; return () => (s = (s * 16807) % 2147483647) / 2147483647; };
  const text = (p, x, y, s, o) => el(p, "text", Object.assign({ x, y, fill: C.cream, "font-size": 16, "font-family": "Roboto,Inter,sans-serif", stroke: C.ground, "stroke-width": 4, "paint-order": "stroke" }, o || {}), s);

  return {
    C, el, line, text, rng,
    /** isometric projection: plan (u,v) at height z, origin (cx,cy) */
    iso: (u, v, z, cx, cy, s = 1) => [cx + (u - v) * 0.866 * s, cy + (u + v) * 0.5 * s - z],
    /** standing or walking person, feet at (x,y), height h; pose 0..3 */
    person(p, x, y, h, pose = 0, o = {}) {
      const g = el(p, "g", {}), k = h / 34, st = { stroke: o.color || C.cream, "stroke-width": C.sw };
      el(g, "circle", Object.assign({ cx: x, cy: y - 30 * k, r: 3.3 * k, fill: o.fill || C.ground }, st));
      line(g, `M${x} ${y - 26.5 * k} L${x} ${y - 13 * k}`, st);
      const sw = [0, 4, -3, 6][pose % 4] * k;
      line(g, `M${x} ${y - 13 * k} L${x - 3 * k - sw / 2} ${y} M${x} ${y - 13 * k} L${x + 3 * k + sw / 2} ${y}`, st);
      line(g, `M${x} ${y - 24 * k} L${x - 4 * k + sw / 3} ${y - 15 * k} M${x} ${y - 24 * k} L${x + 4 * k - sw / 3} ${y - 15 * k}`, st);
      return g;
    },
    /** tree in elevation: trunk lines and a stippled canopy, base at (x,y), height h */
    tree(p, x, y, h, seed = 1, o = {}) {
      const g = el(p, "g", {}), r = rng(seed), cw = h * 0.42, ch = h * 0.55, cy = y - h + ch * 0.55;
      line(g, `M${x} ${y} L${x} ${cy + ch * 0.2} M${x} ${cy + ch * 0.45} L${x - cw * 0.35} ${cy} M${x} ${cy + ch * 0.35} L${x + cw * 0.3} ${cy - ch * 0.1}`, { "stroke-width": 1.1 });
      const n = o.density || Math.round(h * 9);
      for (let i = 0; i < n; i++) {
        const a = r() * Math.PI * 2, d = Math.sqrt(r());
        const px = x + Math.cos(a) * d * cw, py = cy + Math.sin(a) * d * ch * 0.55;
        el(g, "circle", { cx: px.toFixed(1), cy: py.toFixed(1), r: (0.55 + r() * 0.6).toFixed(2), fill: C.cream, "fill-opacity": (0.35 + 0.6 * (1 - d) * r() + 0.1).toFixed(2) });
      }
      return g;
    },
    /** stippled tree in plan (seen from above), centre (x,y), radius r */
    treePlan(p, x, y, rad, seed = 1) {
      const g = el(p, "g", {}), r = rng(seed);
      for (let i = 0; i < rad * rad * 0.9; i++) { const a = r() * Math.PI * 2, d = Math.sqrt(r()) * rad; el(g, "circle", { cx: (x + Math.cos(a) * d).toFixed(1), cy: (y + Math.sin(a) * d * 0.62).toFixed(1), r: 0.7, fill: C.cream, "fill-opacity": (0.4 + 0.6 * r()).toFixed(2) }); }
      return g;
    },
    /** car in side elevation; lit = filled (e.g. electric); width w */
    car(p, x, y, w = 38, lit = false, o = {}) {
      const g = el(p, "g", { transform: `translate(${x},${y - 17 * w / 38}) scale(${w / 38})` }), col = o.color || C.cream;
      el(g, "path", { d: "M1 13 L1 9 Q2 7 5 6.5 L10 2.5 Q11.5 1.5 14 1.5 L23 1.5 Q25 1.5 27 3 L31 6.5 L36 7.5 Q38 8 38 10.5 L38 13 Z", fill: lit ? col : "none", stroke: col, "stroke-width": C.sw * 38 / w, "stroke-opacity": lit ? 1 : 0.7, "stroke-linejoin": "round" });
      [9.5, 29].forEach(cx => el(g, "circle", { cx, cy: 13.5, r: 3.2, fill: C.ground, stroke: col, "stroke-width": C.sw * 38 / w }));
      return g;
    },
    /** gabled house in elevation, base-left at (x,y) */
    house(p, x, y, w, h, o = {}) {
      const g = el(p, "g", {}), rh = o.roof ?? h * 0.45;
      el(g, "path", { d: `M${x} ${y} L${x} ${y - h} L${x + w / 2} ${y - h - rh} L${x + w} ${y - h} L${x + w} ${y} Z`, fill: o.fill || C.ground, stroke: "none" });
      line(g, `M${x} ${y} L${x} ${y - h} L${x + w / 2} ${y - h - rh} L${x + w} ${y - h} L${x + w} ${y} M${x - 6} ${y - h + 4} L${x + w / 2} ${y - h - rh - 2} L${x + w + 6} ${y - h + 4}`);
      el(g, "rect", { x: x + w * 0.16, y: y - h * 0.72, width: w * 0.24, height: h * 0.26, fill: "none", stroke: C.cream, "stroke-width": C.sw });
      el(g, "rect", { x: x + w * 0.58, y: y - h * 0.62, width: w * 0.2, height: h * 0.62, fill: "none", stroke: C.cream, "stroke-width": C.sw });
      return g;
    },
    /** horizontal hatching (sky band) */
    hatch(p, x, y, w, h, step = 4) { const g = el(p, "g", {}); for (let yy = y; yy <= y + h; yy += step) line(g, `M${x} ${yy} L${x + w} ${yy}`, { stroke: C.cream, "stroke-opacity": 0.22, "stroke-width": 0.6 }); return g; },
    /** bezier wire between two ports */
    wire(p, x1, y1, x2, y2, o = {}) { const m = (x1 + x2) / 2; return line(p, `M${x1} ${y1} C${m} ${y1} ${m} ${y2} ${x2} ${y2}`, o); },
    /** node component box with a vertical name tab and port labels */
    component(p, x, y, w, h, name, inLabels = [], outLabels = []) {
      const g = el(p, "g", {});
      el(g, "rect", { x, y, width: w, height: h, rx: 7, fill: "#e8dcc4" });
      el(g, "rect", { x: x + w / 2 - 15, y: y + 10, width: 30, height: h - 20, rx: 5, fill: C.ground });
      text(g, x + w / 2 + 5, y + h / 2, name, { "text-anchor": "middle", transform: `rotate(-90 ${x + w / 2 + 5} ${y + h / 2})`, "font-size": 13, stroke: "none" });
      inLabels.forEach((l, i) => text(g, x + 12, y + 26 + i * 26, l, { fill: C.ground, stroke: "none", "font-size": 13 }));
      outLabels.forEach((l, i) => text(g, x + w - 12, y + 26 + i * 26, l, { fill: C.ground, stroke: "none", "font-size": 13, "text-anchor": "end" }));
      return g;
    },
    /** alternating scale bar with tick labels */
    scalebar(p, x, y, w, labels = []) {
      const g = el(p, "g", {}), n = 6;
      for (let i = 0; i < n; i++) el(g, "rect", { x: x + i * w / n, y: y + (i % 2 ? 0 : 5), width: w / n, height: 5, fill: C.cream });
      el(g, "rect", { x, y, width: w, height: 10, fill: "none", stroke: C.cream, "stroke-width": 0.8 });
      labels.forEach(([f, s]) => text(g, x + f * w, y + 26, s, { "text-anchor": "middle", "font-size": 12, fill: C.dim }));
      return g;
    },
    /** soft catchment blob around (x,y), radius r, n rings */
    catchment(p, x, y, rad, n = 3, seed = 1) {
      const g = el(p, "g", {}), r = rng(seed);
      for (let k = n; k >= 1; k--) { const rr = rad * k / n, pts = []; for (let a = 0; a < 24; a++) { const ang = a / 24 * Math.PI * 2, j = 1 + (r() - 0.5) * 0.18; pts.push([x + Math.cos(ang) * rr * j, y + Math.sin(ang) * rr * j]); }
        el(g, "path", { d: "M" + pts.map(q => q.map(v => v.toFixed(1)).join(" ")).join(" L") + " Z", fill: C.cream, "fill-opacity": 0.07 + 0.05 * (n - k), stroke: C.cream, "stroke-opacity": 0.5, "stroke-width": 0.8 }); }
      el(g, "circle", { cx: x, cy: y, r: 6, fill: C.accent, stroke: C.ground, "stroke-width": 2 });
      return g;
    },
  };
}
if (typeof module !== "undefined") module.exports = { LineArt, LINEART_THEMES };
