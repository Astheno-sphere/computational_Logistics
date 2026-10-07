#!/usr/bin/env python3
"""Visual storytelling exports for the transport ABM: one ensemble, three views.

  1. SimWrapper dashboard: CSVs + dashboard-*.yaml (pathway bands per package, robustness, mode shares,
     the futures table). Open the folder in SimWrapper (simwrapper.app or `simwrapper here`).
  2. kepler.gl agent-flow map: every agent's commute as an arc, coloured by mode, for 2025 and 2050,
     in one self-contained HTML page (kepler.gl 3.2 from unpkg).
  3. Grasshopper pathway explorer: CO2 trajectories as a data tree {future}, consumed by the Hops
     endpoint /cl/pathways and grasshopper/pathway_explorer.py.

Geography is illustrative: agents get homes and workplaces around Molde and Kristiansund town centres
consistent with their zone and commute distance; it is not a land-use model.

    python story.py --out docs/story --futures 30 --agents 600
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "abm-transport", "scripts"))
import abm  # noqa: E402

STUDY = os.path.join(ROOT, "docs", "results", "transplan_study.json")
CENTRES = {"Molde": (62.7375, 7.1591), "Kristiansund": (63.1104, 7.7279)}   # town centres (lat, lon)
LAND_BEARINGS = {"Molde": (240.0, 460.0), "Kristiansund": (0.0, 360.0)}     # Molde: the fjord lies south
MODES = ["car", "bus", "bike"]


# ---------------------------------------------------------------- ensemble -------------------------
def futures(n=30, seed=0):
    """Latin-hypercube futures over the ABM's deep uncertainties."""
    from scipy.stats import qmc
    names = list(abm.UNCERTAINTIES)
    lo = np.array([abm.UNCERTAINTIES[k][0] for k in names])
    hi = np.array([abm.UNCERTAINTIES[k][1] for k in names])
    pts = qmc.scale(qmc.LatinHypercube(d=len(names), seed=seed).random(n), lo, hi)
    return [dict(zip(names, map(float, row))) for row in pts]


def packages(study=STUDY, top=3):
    """No policy plus the most robust packages from the study, with their lever settings."""
    out = {"no_policy": abm.defaults(abm.LEVERS)}
    if os.path.exists(study):
        for p in json.load(open(study))["top_packages"][:top]:
            out[p["policy"]] = {k: float(p[k]) for k in abm.LEVERS}
    return out


def run_pathways(pkgs, futs, n_agents=600, beta=None, target=0.2, seed=0):
    """One ABM run per package x future. Long table: package, future, year, indicators, success."""
    beta = beta or _study_beta()
    rows = []
    for pname, lev in pkgs.items():
        for fi, unc in enumerate(futs):
            r = abm.run(lev, unc, beta=beta, n=n_agents, seed=seed)
            s = r["series"]
            co2_rel = np.array(s["co2_t"]) / s["co2_t"][0]
            ok = bool(co2_rel[-1] <= target)
            for t, y in enumerate(r["years"]):
                rows.append({"package": pname, "future": fi, "year": y, "co2_rel": round(float(co2_rel[t]), 4),
                             "car_share": round(s["car_share"][t], 4), "bus_share": round(s["bus_share"][t], 4),
                             "bike_share": round(s["bike_share"][t], 4),
                             "ev_fleet_share": round(s["ev_fleet_share"][t], 4), "meets_target": ok})
    return pd.DataFrame(rows)


def _study_beta():
    if os.path.exists(STUDY):
        return json.load(open(STUDY))["dcm"]["beta"]
    return None


# ---------------------------------------------------------------- 1. SimWrapper ---------------------
def simwrapper(df, futs, outdir, target=0.2):
    os.makedirs(outdir, exist_ok=True)
    g = df.groupby(["package", "year"])["co2_rel"]
    band = pd.DataFrame({"median": g.median(), "p10": g.quantile(0.1), "p90": g.quantile(0.9)}).round(4)
    band.reset_index().to_csv(os.path.join(outdir, "co2_by_package.csv"), index=False)
    last = df[df.year == df.year.max()]
    rob = last.groupby("package").agg(share_meeting_target=("meets_target", "mean"),
                                      median_co2_2050=("co2_rel", "median"),
                                      median_car_share_2050=("car_share", "median"),
                                      median_ev_fleet_2050=("ev_fleet_share", "median")).round(3)
    rob = rob.sort_values("share_meeting_target", ascending=False)
    rob.reset_index().to_csv(os.path.join(outdir, "robustness.csv"), index=False)
    best = rob.index[0]
    modes = df[df.package == best].groupby("year")[["car_share", "bus_share", "bike_share"]].median().round(4)
    modes.columns = ["car", "bus", "bike"]
    modes.reset_index().to_csv(os.path.join(outdir, "mode_shares_best.csv"), index=False)
    ft = pd.DataFrame(futs).round(3)
    ft.insert(0, "future", range(len(futs)))
    for p in rob.index:
        ft["meets_" + p] = last[last.package == p].sort_values("future")["meets_target"].to_numpy()
    ft.to_csv(os.path.join(outdir, "futures.csv"), index=False)

    note = ("Synthetic data, illustrative parameters. %d futures x %d packages; target: 2050 commute CO2 "
            "at or below %d%% of 2025." % (len(futs), df.package.nunique(), round(target * 100)))
    dash1 = {
        "header": {"tab": "Pathways", "title": "Asthenosphere: CO2 pathways to 2050",
                   "description": note},
        "layout": {
            "row1": [{"type": "line", "title": "Median CO2 relative to 2025, by policy package",
                      "description": "Each line is the median over all futures; 0.2 is the target",
                      "dataset": "co2_by_package.csv", "x": "year", "columns": ["median"],
                      "groupBy": "package", "xAxisTitle": "Year", "yAxisTitle": "CO2 / CO2 in 2025"}],
            "row2": [{"type": "bar", "title": "Share of futures meeting the 2050 target",
                      "dataset": "robustness.csv", "x": "package", "columns": ["share_meeting_target"],
                      "xAxisTitle": "Package", "yAxisTitle": "Share of futures"},
                     {"type": "area", "title": "Mode shares under %s (median future)" % best,
                      "dataset": "mode_shares_best.csv", "x": "year", "columns": ["car", "bus", "bike"],
                      "xAxisTitle": "Year", "yAxisTitle": "Share of commutes"}],
            "row3": [{"type": "line", "title": "Uncertainty band for %s (10th to 90th percentile)" % best,
                      "dataset": "co2_by_package.csv", "x": "year", "columns": ["p10", "median", "p90"],
                      "filters": {"package": best}, "xAxisTitle": "Year", "yAxisTitle": "CO2 / CO2 in 2025"}],
        },
    }
    dash2 = {
        "header": {"tab": "Futures", "title": "The futures behind the pathways",
                   "description": "Each row is one future (deep uncertainties) and whether each package "
                                  "meets the target in it."},
        "layout": {"row1": [{"type": "table", "title": "Robustness summary", "dataset": "robustness.csv"}],
                   "row2": [{"type": "table", "title": "Futures", "dataset": "futures.csv"}]},
    }
    import yaml
    for name, d in (("dashboard-1-pathways.yaml", dash1), ("dashboard-2-futures.yaml", dash2)):
        with open(os.path.join(outdir, name), "w") as fh:
            yaml.safe_dump(d, fh, sort_keys=False, allow_unicode=True)
    return {"best_package": best, "robustness": rob.reset_index().to_dict("records")}


# ---------------------------------------------------------------- 2. kepler.gl ----------------------
def _offset(lat, lon, km, bearing_deg):
    b = math.radians(bearing_deg)
    return (lat + km / 111.0 * math.cos(b), lon + km / (111.0 * math.cos(math.radians(lat))) * math.sin(b))


def agent_flows(levers, uncertainties, years=(2025, 2050), n_agents=600, beta=None, seed=0):
    """Per-agent commute arcs (home -> work) with the mode each agent takes in each year."""
    r = abm.run(levers, uncertainties, beta=beta or _study_beta(), n=n_agents, seed=seed, trace_years=years)
    tr = r["trace"]
    rng = np.random.default_rng(seed + 101)
    rows = []
    for i, (zone, dist) in enumerate(zip(tr["zone"], tr["dist_km"])):
        if zone == "Between":                       # lives along the corridor, works in the nearer town
            t = rng.uniform(0.25, 0.75)
            town = "Molde" if t < 0.5 else "Kristiansund"
            a, b = CENTRES["Molde"], CENTRES["Kristiansund"]
            home = (a[0] + t * (b[0] - a[0]) + rng.normal(0, 0.02), a[1] + t * (b[1] - a[1]) + rng.normal(0, 0.04))
        else:
            town = zone
            lo, hi = LAND_BEARINGS[town]
            home = _offset(*CENTRES[town], min(dist, 18.0), rng.uniform(lo, hi) % 360)
        work = _offset(*CENTRES[town], abs(rng.normal(0, 0.6)), rng.uniform(0, 360))
        for y in years:
            yt = tr["years"][y]
            rows.append({"agent": i, "year": y, "zone": zone, "mode": MODES[yt["mode"][i]],
                         "ev": bool(yt["ev"][i]), "dist_km": dist,
                         "home_lat": round(home[0], 5), "home_lng": round(home[1], 5),
                         "work_lat": round(work[0], 5), "work_lng": round(work[1], 5)})
    return pd.DataFrame(rows)


MODE_COLOURS = {"car": [217, 95, 2], "bus": [27, 158, 119], "bike": [117, 112, 179]}


def kepler_config(year=2050):
    """kepler.gl map config: arcs coloured by mode, homes as points, a year filter."""
    colors = ["#d95f02", "#1b9e77", "#7570b3"]       # car, bus, bike (ordinal, sorted: bike, bus, car)
    ordinal = {"name": "mode", "type": "ordinal", "category": "Custom",
               "colors": [colors[2], colors[1], colors[0]]}
    return {"version": "v1", "config": {
        "visState": {
            "filters": [{"dataId": ["flows"], "id": "year_filter", "name": ["year"], "type": "range",
                         "value": [year, year]}],
            "layers": [
                {"id": "commutes", "type": "arc", "config": {
                    "dataId": "flows", "label": "Commutes by mode", "isVisible": True,
                    "columns": {"lat0": "home_lat", "lng0": "home_lng", "lat1": "work_lat", "lng1": "work_lng"},
                    "visConfig": {"opacity": 0.55, "thickness": 1.2, "colorRange": ordinal,
                                  "targetColorRange": ordinal}},
                 "visualChannels": {"colorField": {"name": "mode", "type": "string"}, "colorScale": "ordinal",
                                    "sourceColorField": {"name": "mode", "type": "string"},
                                    "sourceColorScale": "ordinal"}},
                {"id": "homes", "type": "point", "config": {
                    "dataId": "flows", "label": "Homes (EV owners highlighted)", "isVisible": True,
                    "columns": {"lat": "home_lat", "lng": "home_lng"},
                    "visConfig": {"radius": 3, "opacity": 0.8,
                                  "colorRange": {"name": "ev", "type": "ordinal", "category": "Custom",
                                                 "colors": ["#9aa6b2", "#00a3e0"]}}},
                 "visualChannels": {"colorField": {"name": "ev", "type": "boolean"}, "colorScale": "ordinal"}},
            ],
            "interactionConfig": {"tooltip": {"enabled": True, "fieldsToShow": {
                "flows": [{"name": n, "format": None} for n in ("zone", "mode", "ev", "dist_km", "year")]}}},
        },
        "mapState": {"latitude": 62.93, "longitude": 7.45, "zoom": 8.6, "pitch": 40, "bearing": 0,
                     "dragRotate": True},
        "mapStyle": {"styleType": "dark-matter"},
    }}


KEPLER_VERSION = "3.2.6"
CDN = {
    "react": "https://unpkg.com/react@18.3.1/umd/react.production.min.js",
    "react-dom": "https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js",
    "redux": "https://unpkg.com/redux@4.2.1/dist/redux.min.js",
    "react-redux": "https://unpkg.com/react-redux@8.1.3/dist/react-redux.min.js",
    "styled-components": "https://unpkg.com/styled-components@6.1.19/dist/styled-components.min.js",
    "kepler.gl": "https://unpkg.com/kepler.gl@%s/umd/keplergl.min.js" % KEPLER_VERSION,
    "kepler.css": "https://unpkg.com/kepler.gl@%s/umd/keplergl.min.css" % KEPLER_VERSION,
    "maplibre.css": "https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css",
}

KEPLER_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asthenosphere Agent Flows</title>
<link rel="stylesheet" href="{maplibre_css}">
<link rel="stylesheet" href="{kepler_css}">
<style>
  html, body {{ margin: 0; height: 100%; background: #0f1418; overflow: hidden;
               font: 13px/1.45 "Helvetica Neue", Arial, sans-serif; }}
  #app {{ position: absolute; inset: 0; }}
  #note {{ position: absolute; right: 12px; bottom: 28px; z-index: 10; max-width: 340px; padding: 10px 12px;
          background: rgba(15, 20, 24, .88); color: #d7e2e8; border: 1px solid #2c3a43; border-radius: 4px; }}
  #note b {{ color: #fff; }} #note a {{ color: #7fd0d6; }}
  .sw {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 4px 0 8px; }}
</style>
</head>
<body>
<div id="app"></div>
<div id="note"><b>Agent commutes, {title_years}</b><br>
Each arc is one simulated commuter (home to work), coloured by mode:
<span class="sw" style="background:#d95f02"></span>car<span class="sw" style="background:#1b9e77"></span>bus<span class="sw" style="background:#7570b3"></span>bike.
Package {package}, median future. Move the year filter (left panel) between 2025 and 2050.
Synthetic agents and illustrative geography. <a href="../../index.html">Back to the atlas</a></div>
<script src="{react}"></script>
<script src="{react_dom}"></script>
<script src="{redux}"></script>
<script src="{react_redux}"></script>
<script src="{styled}"></script>
<script src="{kepler}"></script>
<script>
const DATA = {data};
const CONFIG = {config};
const reducers = Redux.combineReducers({{ keplerGl: KeplerGl.keplerGlReducer.initialState({{
  uiState: {{ readOnly: false, currentModal: null }} }}) }});
const store = Redux.createStore(reducers, {{}}, Redux.applyMiddleware(...KeplerGl.enhanceReduxMiddleware([])));
window.keplerStore = store;
function App() {{
  const [size, setSize] = React.useState({{ width: window.innerWidth, height: window.innerHeight }});
  React.useEffect(() => {{ loadData(); }}, []);   // after the map instance has mounted
  React.useEffect(() => {{
    const f = () => setSize({{ width: window.innerWidth, height: window.innerHeight }});
    window.addEventListener('resize', f); return () => window.removeEventListener('resize', f);
  }}, []);
  return React.createElement(KeplerGl.KeplerGl, {{ id: 'map', mapboxApiAccessToken: '', width: size.width, height: size.height }});
}}
ReactDOM.createRoot(document.getElementById('app')).render(
  React.createElement(ReactRedux.Provider, {{ store }}, React.createElement(App)));
function loadData() {{
  const fields = DATA.fields.map(f => ({{ name: f.name, type: f.type }}));
  store.dispatch(KeplerGl.addDataToMap({{
    datasets: [{{ info: {{ id: 'flows', label: 'Agent commutes' }}, data: {{ fields, rows: DATA.rows }} }}],
    options: {{ centerMap: false, readOnly: false }},
    config: CONFIG
  }}));
}}
</script>
</body>
</html>
"""


def kepler_html(flows, out_html, package="best", year=2050):
    os.makedirs(os.path.dirname(out_html), exist_ok=True)
    types = {"agent": "integer", "year": "integer", "zone": "string", "mode": "string", "ev": "boolean",
             "dist_km": "real", "home_lat": "real", "home_lng": "real", "work_lat": "real", "work_lng": "real"}
    cols = list(types)
    data = {"fields": [{"name": c, "type": types[c]} for c in cols],
            "rows": flows[cols].astype(object).values.tolist()}
    years = sorted(flows.year.unique())
    html = KEPLER_HTML.format(
        maplibre_css=CDN["maplibre.css"], kepler_css=CDN["kepler.css"], react=CDN["react"],
        react_dom=CDN["react-dom"], redux=CDN["redux"], react_redux=CDN["react-redux"],
        styled=CDN["styled-components"], kepler=CDN["kepler.gl"], package=package,
        title_years=" and ".join(map(str, years)),
        data=json.dumps(data, separators=(",", ":")), config=json.dumps(kepler_config(year)))
    with open(out_html, "w") as fh:
        fh.write(html)
    flows.to_csv(os.path.splitext(out_html)[0] + ".csv", index=False)
    with open(os.path.splitext(out_html)[0] + ".config.json", "w") as fh:
        json.dump(kepler_config(year), fh, indent=1)
    return out_html


# ---------------------------------------------------------------- 3. Grasshopper --------------------
def pathway_tree(df, package):
    """Data tree for Grasshopper: {future} -> CO2 relative to 2025 per year, plus success flags."""
    d = df[df.package == package].sort_values(["future", "year"])
    years = sorted(d.year.unique())
    tree = {"{%d}" % f: g["co2_rel"].tolist() for f, g in d.groupby("future")}
    success = [bool(g["meets_target"].iloc[0]) for _, g in d.groupby("future")]
    return {"package": package, "years": [int(y) for y in years], "tree": tree, "success": success}


def pathway_polylines(years, branches, success, index=0, sx=10.0, sy=100.0, target=0.2):
    """Plain-Python version of grasshopper/pathway_explorer.py: polyline vertices (x = years from start
    times sx, y = CO2 relative to 2025 times sy) split by success, plus the focused future."""
    y0 = years[0]
    line = lambda vals: [((y - y0) * sx, v * sy, 0.0) for y, v in zip(years, vals)]  # noqa: E731
    i = max(0, min(int(index), len(branches) - 1))
    return {"ok": [line(b) for b, s in zip(branches, success) if s],
            "fail": [line(b) for b, s in zip(branches, success) if not s],
            "focus": line(branches[i]),
            "target_line": [(0.0, target * sy, 0.0), ((years[-1] - y0) * sx, target * sy, 0.0)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "story"))
    ap.add_argument("--futures", type=int, default=30)
    ap.add_argument("--agents", type=int, default=600)
    ap.add_argument("--target", type=float, default=0.2)
    a = ap.parse_args(argv)
    pk, ft = packages(), futures(a.futures)
    df = run_pathways(pk, ft, a.agents, target=a.target)
    sw = simwrapper(df, ft, os.path.join(a.out, "simwrapper"), a.target)
    best = sw["best_package"]
    df.to_csv(os.path.join(a.out, "pathways.csv"), index=False)
    with open(os.path.join(a.out, "pathway_tree_%s.json" % best), "w") as fh:
        json.dump(pathway_tree(df, best), fh)
    # median future for the best package: the future whose 2050 CO2 is closest to the package median
    last = df[(df.package == best) & (df.year == df.year.max())]
    fmed = int(last.iloc[(last.co2_rel - last.co2_rel.median()).abs().argsort().iloc[0]]["future"])
    flows = agent_flows(pk[best], ft[fmed], n_agents=a.agents)
    kepler_html(flows, os.path.join(a.out, "kepler", "agent-flows.html"), package=best)
    print(json.dumps({"best_package": best, "median_future": fmed, "runs": int(df.groupby(["package", "future"]).ngroups),
                      "robustness": sw["robustness"]}, indent=1))


if __name__ == "__main__":
    main()
