// Motion plate: one idea at two scales on one clock (spec: skills/visual-narrative/reference/motion-plate-spec.md).
// Self-contained: canvas 2D, data inline, no libraries, no network. Layout numbers are the spec's 720x900 grid.
(() => {
  const M = /*MOTION*/null, cv = document.getElementById("mp");
  if (!M || !cv) return;
  const W = 720, H = 900, X0 = 34, X1 = 685, NY = M.years.length - 1;
  const cs = getComputedStyle(cv), tok = (n, d) => cs.getPropertyValue(n).trim() || d;
  const C = {bg: tok("--panel", "#1E1915"), paper: tok("--cream", "#ECE3D2"), body: tok("--body", "#D3CABA"), dim: tok("--dim", "#948B7E"),
    amber: tok("--amber", "#D4A530"), good: tok("--sage", "#9DB886"), bad: tok("--red", "#D2412B"), teal: tok("--teal", "#7CBAC4"), rule: "rgba(236,227,210,.25)"};
  C.note = C.dim;
  const SANS = tok("--sans", "Inter, system-ui, sans-serif"), MONO = tok("--mono", '"Roboto Mono", ui-monospace, monospace');
  // one scale for the whole plate, in the page's own semantics: sage meets the target, amber is today
  const STOPS = [[0, C.good], [.5, C.paper], [1, C.amber]];
  const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const ramp = v => {
    v = Math.min(1, Math.max(0, v));
    for (let i = 1; i < STOPS.length; i++) if (v <= STOPS[i][0]) {
      const [a, ca] = STOPS[i - 1], [b, cb] = STOPS[i], k = (v - a) / (b - a), A = rgb(ca), B = rgb(cb);
      return `rgb(${A.map((x, j) => Math.round(x + (B[j] - x) * k)).join(",")})`;
    }
  };
  const heat = co2 => co2 / 1.0;                        // share of 2025 emissions -> ramp position (1 = today)
  const MODE_COL = [C.amber, C.good, C.paper, C.teal], MODE_NAME = ["PETROL CAR", "ELECTRIC CAR", "BUS", "BIKE"];
  const ACTS = [["no_policy", "NO POLICY"], [M.best, "PACKAGE " + M.best]];
  const DUR = [10, 1.2, 10, 3.5], TOTAL = DUR.reduce((a, b) => a + b);
    const paths = M.towns.map(t => new Path2D(t.path));
  const byTown = [[], []]; M.home.forEach(([t, j], i) => byTown[t].push([i, j]));
  const median = a => { const s = [...a].sort((x, y) => x - y); return s[s.length >> 1]; };
  const at = (name, i) => M.fans[name].map(f => f[i]);
  const finalHit = name => M.fans[name].filter(f => f[NY] <= M.target).length;
  const nF = M.fans.no_policy.length, hit0 = finalHit("no_policy"), hit1 = finalHit(M.best);
  let ctx, S = 1, f = NY, act = 1, paused = false, last = 0, clock = 0;

  const txt = (s, x, y, o = {}) => {
    ctx.font = `${o.w || 400} ${o.s || 12}px ${o.f || SANS}`; ctx.fillStyle = o.c || C.paper;
    ctx.textAlign = o.a || "left"; ctx.letterSpacing = (o.t || 0) + "px"; ctx.fillText(s, x, y);
  };
  const width = (s, o) => { ctx.font = `${o.w || 400} ${o.s}px ${o.f || SANS}`; ctx.letterSpacing = (o.t || 0) + "px"; return ctx.measureText(s).width; };
  const wrap = (s, maxw, o) => {
    const out = []; let cur = "";
    for (const w of s.split(" ")) { const n = cur ? cur + " " + w : w; if (width(n, o) > maxw && cur) { out.push(cur); cur = w; } else cur = n; }
    return out.concat(cur);
  };

  function fan(name, x0, x1, y0, y1) {
    const px = i => x0 + (x1 - x0) * i / NY, py = v => y1 - (y1 - y0) * Math.min(v, 1.1) / 1.1;
    ctx.strokeStyle = C.rule; ctx.lineWidth = 1; ctx.setLineDash([]);
    [0, .5, 1].forEach(v => { ctx.beginPath(); ctx.moveTo(x0, py(v)); ctx.lineTo(x1, py(v)); ctx.globalAlpha = .35; ctx.stroke(); ctx.globalAlpha = 1;
      txt(Math.round(v * 100) + "%", x0 - 8, py(v) + 3.5, {s: 9.5, c: C.dim, a: "right"}); });
    [2025, 2030, 2035, 2040, 2045, 2050].forEach(y => txt(y, px(y - 2025), y1 + 17, {s: 9.5, c: C.dim, a: "center"}));
    const end = Math.floor(f), done = f >= NY - .001, held = done && (act === 1);
    M.fans[name].forEach(line => {
      const ok = line[NY] <= M.target;
      ctx.lineWidth = held && ok ? 1.5 : 1; ctx.globalAlpha = held ? (ok ? .95 : .3) : .55;
      for (let i = 0; i < end; i++) { ctx.strokeStyle = held ? (ok ? C.good : C.bad) : ramp(heat(line[i + 1])); ctx.beginPath(); ctx.moveTo(px(i), py(line[i])); ctx.lineTo(px(i + 1), py(line[i + 1])); ctx.stroke(); }
      if (f < NY && end < NY) { const fr = f - end, v = line[end] + (line[end + 1] - line[end]) * fr; ctx.strokeStyle = ramp(heat(v)); ctx.beginPath(); ctx.moveTo(px(end), py(line[end])); ctx.lineTo(px(f), py(v)); ctx.stroke(); }
    });
    ctx.globalAlpha = 1; ctx.strokeStyle = C.good; ctx.setLineDash([5, 4]); ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(x0, py(M.target)); ctx.lineTo(x1, py(M.target)); ctx.stroke(); ctx.setLineDash([]);
    txt("TARGET 20%", x1, py(M.target) - 6, {s: 9.5, w: 500, f: MONO, t: 1.2, c: C.good, a: "right"});
  }

  function draw() {
    const i = Math.min(NY, Math.floor(f)), name = ACTS[act][0];
    ctx.setTransform(S, 0, 0, S, 0, 0); ctx.fillStyle = C.bg; ctx.fillRect(0, 0, W, H);
    // Hero A: the 60 futures
    fan(name, X0 + 36, X1 - 8, 76, 270);
    ctx.fillStyle = "rgba(20,8,10,.45)"; ctx.fillRect(X0, 20, 136, 48);
    txt(String(M.years[i]), X0 + 12, 43, {s: 20, w: 800, f: SANS, t: -.3});
    txt(ACTS[act][1], X0 + 12, 59, {s: 9.5, w: 700, f: MONO, t: 1.4, c: act ? C.good : C.dim});
    txt("COMMUTING CO₂, SHARE OF 2025", X1, 34, {s: 9.5, w: 500, f: MONO, t: 1.4, a: "right"});
    for (let x = 0; x < 132; x++) { ctx.fillStyle = ramp(x / 131); ctx.fillRect(X1 - 132 + x, 41, 1, 4); }
    txt("0", X1 - 132, 58, {s: 9, c: C.dim}); txt("100%", X1, 58, {s: 9, c: C.dim, a: "right"});
    const hits = M.fans[name].filter(l => l[i] <= M.target).length;
    txt(`${hits} OF ${nF} FUTURES AT TARGET`, X1, 94, {s: 11, w: 700, f: MONO, t: 1.2, c: hits ? C.good : C.dim, a: "right"});
    // value labels, coloured by the same ramp
    const lab = [["TARGET", M.target], ["NO POLICY", median(at("no_policy", i))], ["PACKAGE " + M.best, median(at(M.best, i))]];
    const o = {s: 13.5, w: 700, f: MONO, t: .8};
    let widths = lab.map(([a, v]) => width(`${a} ${Math.round(v * 100)}%`, o)), gap = 28, x = (X0 + X1) / 2 - (widths.reduce((a, b) => a + b) + gap * 2) / 2;
    lab.forEach(([a, v], k) => { const lw = width(a + " ", o); txt(a + " ", x, 319, {...o, c: C.paper}); txt(Math.round(v * 100) + "%", x + lw, 319, {...o, c: ramp(heat(v))}); x += widths[k] + gap; });
    // Hero B: the same quantity as agents on the real networks
    const cw = 320, shares = [0, 0, 0, 0];
    M.towns.forEach((t, k) => {
      const x0 = k ? X1 - cw : X0, s = Math.min(cw / t.w, 262 / t.h), ox = x0 + (cw - t.w * s) / 2, oy = 352 + (262 - t.h * s) / 2;
      txt(t.name.toUpperCase() + ", SIMULATED", x0, 351, {s: 9.5, w: 600, f: MONO, t: 1.2});
      ctx.save(); ctx.translate(ox, oy); ctx.scale(s, s); ctx.strokeStyle = "rgba(232,223,208,.3)"; ctx.lineWidth = .9 / s; ctx.lineJoin = "round"; ctx.stroke(paths[k]); ctx.restore();
      byTown[k].forEach(([a, j]) => { const c = +M.states[name][a][i]; shares[c]++; ctx.fillStyle = MODE_COL[c]; const [px, py] = t.pts[j]; ctx.fillRect(ox + px * s - 1.5, oy + py * s - 1.5, 3, 3); });
      if (k === 0) { const L = 2e6 / t.span_m * s; ctx.strokeStyle = C.dim; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, 633); ctx.lineTo(x0, 637); ctx.lineTo(x0 + L, 637); ctx.lineTo(x0 + L, 633); ctx.stroke(); txt("2 km", x0 + L + 6, 637, {s: 9, c: C.dim}); }
    });
    let lx = X1; for (let c = 3; c >= 0; c--) {
      const s = `${MODE_NAME[c]} ${Math.round(shares[c] / M.n * 100)}%`, w = width(s, {w: 600, s: 9, f: MONO, t: .6});
      txt(s, lx, 637, {s: 9, w: 600, f: MONO, t: .6, c: C.body, a: "right"}); ctx.fillStyle = MODE_COL[c]; ctx.fillRect(lx - w - 12, 629, 7, 7); lx -= w + 26;
    }
    // text block
    ctx.fillStyle = C.rule; ctx.fillRect(X0, 666, X1 - X0, 1.2);
    txt(`PACKAGE ${M.best} AGAINST NO POLICY: COMMUTING EMISSIONS, 2025 TO 2050`, X0, 691, {s: 12.5, w: 500, f: MONO, t: 1.5, c: C.amber});
    const parts = [[`${hit1} OF ${nF}`, C.good], [" FUTURES REACH THE TARGET", C.paper]], full = parts.map(p => p[0]).join("");
    let hs = 36; while (hs > 20 && width(full, {f: SANS, w: 800, s: hs, t: -.4}) > X1 - X0) hs--;
    let hx = X0; parts.forEach(([t, c]) => { txt(t, hx, 727, {s: hs, w: 800, f: SANS, t: -.4, c}); hx += width(t, {f: SANS, w: 800, s: hs, t: -.4}); });
    wrap(`Without policy, ${hit0} of the same ${nF} futures get there. Each dot is a commuter on the real road network, coloured by how they travel in that year.`, X1 - X0, {w: 300, s: 17.5, f: SANS})
      .forEach((l, k) => txt(l, X0, 756 + k * 21, {s: 17.5, w: 300, c: C.body}));
    wrap("Synthetic behaviour and illustrative parameters until the A1 survey. One median future per package; the fan shows all 60. 1,000 agents sit on junctions of the OpenStreetMap networks; congestion is zonal.", X1 - X0, {w: 400, s: 10.5, f: SANS})
      .slice(0, 3).forEach((l, k) => txt(l, X0, 800 + k * 13, {s: 10.5, c: C.note}));
    txt("ARSHAD AKHTAR ABBASIA · PHD PROPOSAL, MOLDE", X0, 883, {s: 10, w: 600, f: MONO, t: 1, c: C.dim});
    txt("© OpenStreetMap contributors (ODbL)", X1, 883, {s: 10, c: C.note, a: "right"});
    // progress hairline
    ctx.fillStyle = C.amber; ctx.fillRect(0, H - 2, W * (clock / TOTAL), 2);
  }

  function size() {
    const d = window.devicePixelRatio || 1, w = cv.clientWidth; S = w * d / W;
    cv.width = Math.round(w * d); cv.height = Math.round(w * d * H / W); ctx = cv.getContext("2d"); draw();
  }
  function frame(now) {
    const dt = Math.min(.1, (now - last) / 1000); last = now;
    if (!paused) {
      clock = (clock + dt) % TOTAL; let t = clock, k = 0; while (t > DUR[k]) t -= DUR[k++];
      act = k >> 1; f = k % 2 ? NY : NY * t / DUR[k];
    }
    draw(); requestAnimationFrame(frame);
  }
  const still = /mp=(\d)-([\d.]+)/.exec(location.hash);   // #mp=1-1 freezes act 1 at the end: stable stills
  if (still) { act = +still[1]; f = NY * +still[2]; paused = true; }
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  cv.addEventListener("click", () => { paused = !paused; });
  cv.addEventListener("keydown", e => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); paused = !paused; } });
  new ResizeObserver(size).observe(cv); size();
  const go = () => { size(); if (!calm || still) requestAnimationFrame(t => { last = t; frame(t); }); };
  (document.fonts && document.fonts.load ? Promise.race([document.fonts.load("800 36px Inter"), new Promise(r => setTimeout(r, 1200))]) : Promise.resolve()).then(go);
})();
