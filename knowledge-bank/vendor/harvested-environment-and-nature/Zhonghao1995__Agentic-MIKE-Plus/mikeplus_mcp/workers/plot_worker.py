"""Render MIKE+ result plots in the house style.

Imports mikeio1d / mikeio / matplotlib (NOT mikeplus). No license needed.
Actions: rain_flow | timeseries | network | compare | profile
"""
import json
import sys


def _skip(df, skip_hours):
    if skip_hours:
        import pandas as pd
        cutoff = df.index[0] + pd.Timedelta(hours=float(skip_hours))
        df = df.loc[df.index >= cutoff]
    return df


def _read_rain(path):
    import mikeio
    return mikeio.read(path).to_dataframe().iloc[:, 0]


def _profile(res, payload):
    """Longitudinal profile along an ordered reach chain (given, or found between two nodes)."""
    import numpy as np
    from mikeplus_mcp.contracts import plot_style, schema, topology

    edges = []
    for name in res.reaches.names:
        r = res.reaches[name]
        edges.append((name, str(r.start_node), str(r.end_node)))

    reaches = payload.get("reaches") or []
    from_node, to_node = payload.get("from_node"), payload.get("to_node")
    if reaches:
        path_source = "given"
    elif from_node and to_node:
        reaches = topology.find_path(edges, from_node, to_node)
        if not reaches:
            raise ValueError(f"no reach chain connects {from_node!r} to {to_node!r}")
        path_source = "found"
    else:
        raise ValueError("give 'reaches' (ordered ids) or both 'from_node' and 'to_node'")
    problems = topology.check_chain(edges, reaches)
    if any(p.startswith("unknown reach") for p in problems):
        raise ValueError("; ".join(problems))

    skip_hours = payload.get("skip_hours") or 0
    xs, beds, crowns, grounds, waters, marks = [], [], [], [], [], []
    offset = 0.0
    cur = from_node or str(res.reaches[reaches[0]].start_node)
    peak = {"level": None, "x": None, "reach": None}
    for name in reaches:
        rc = res.reaches[name]
        s_node, e_node = str(rc.start_node), str(rc.end_node)
        reversed_ = (e_node == cur and s_node != cur)   # walk against the reach's own direction
        cur = s_node if reversed_ else e_node
        c0, c1 = float(rc.start_chainage), float(rc.end_chainage)

        def gx(ch):
            return offset + ((c1 - ch) if reversed_ else (ch - c0))

        # water: max over time at every H point of this reach
        wl_ch, wl_max = [], []
        try:
            wdf = _skip(rc.WaterLevel.read(), skip_hours)
            for c in wdf.columns:
                ch = schema.parse_column(c)["chainage"]
                v = float(wdf[c].max())
                if isinstance(ch, float) and v == v:
                    wl_ch.append(ch)
                    wl_max.append(v)
        except Exception:
            pass
        order = np.argsort(wl_ch)
        wl_ch = [wl_ch[i] for i in order]
        wl_max = [wl_max[i] for i in order]

        h = rc.height
        try:
            h = None if h is None else float(h)
        except Exception:
            h = None
        gps = sorted(rc.gridpoints, key=lambda g: float(g.chainage))
        marks.append((offset, e_node if reversed_ else s_node))   # entry node of this reach
        for gp in gps:
            ch = float(gp.chainage)
            bed = gp.bottom_level
            bed = None if bed is None else float(bed)
            xs.append(gx(ch))
            beds.append(np.nan if bed is None else bed)
            crowns.append(np.nan if (bed is None or h is None) else bed + h)
            try:
                grounds.append(float(rc.interpolate_reach_ground_level(ch)))
            except Exception:
                grounds.append(np.nan)
            if wl_ch:
                w = float(np.interp(ch, wl_ch, wl_max))
                waters.append(w)
                if peak["level"] is None or w > peak["level"]:
                    peak = {"level": round(w, 4), "x": round(gx(ch), 2), "reach": name}
            else:
                waters.append(np.nan)
        offset += abs(c1 - c0)
    marks.append((offset, cur))

    if not xs:
        raise ValueError("no grid points found along the requested reaches")
    # sort by global chainage in case a reversed reach put points out of order
    order = np.argsort(xs)
    xs, beds, crowns, grounds, waters = (
        [seq[i] for i in order] for seq in (xs, beds, crowns, grounds, waters))

    plot_style.profile(xs, beds, waters, payload["out_png"], crown=crowns, ground=grounds,
                       node_marks=marks)
    fb = [g - w for g, w in zip(grounds, waters) if g == g and w == w]
    return {
        "ok": True, "png": payload["out_png"],
        "reaches": reaches, "n_reaches": len(reaches), "path_source": path_source,
        "from_node": marks[0][1], "to_node": marks[-1][1],
        "length_m": round(offset, 2), "n_points": len(xs),
        "connectivity_problems": problems,
        "max_water_level": peak["level"], "max_water_level_chainage": peak["x"],
        "max_water_level_reach": peak["reach"],
        "min_freeboard_m": round(min(fb), 4) if fb else None,
        "skip_hours": skip_hours,
    }


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeio1d
        from mikeplus_mcp.contracts import plot_style, schema
        from mikeplus_mcp.contracts.units import unit_for

        action = payload.get("action", "rain_flow")
        res = mikeio1d.open(payload["res1d"])
        out_png = payload["out_png"]

        if action == "profile":
            result = _profile(res, payload)

        elif action == "compare":
            res_b = mikeio1d.open(payload["res1d_b"])
            skip_hours = payload.get("skip_hours") or 0
            quantity = payload.get("quantity", "Discharge")
            element = payload["element"]
            series, labels, cols = [], [], []
            for r, lab in ((res, payload.get("label_a") or "baseline"),
                           (res_b, payload.get("label_b") or "scenario")):
                df = _skip(r.read(), skip_hours)
                c = schema.match_columns(df.columns, quantity, element)
                if not c:
                    raise ValueError(f"no series for {quantity}:{element} in {lab!r} result")
                series.append(df[c[0]])
                labels.append(lab)
                cols.append(str(c[0]))
            rain = _read_rain(payload["rain_dfs0"]) if payload.get("rain_dfs0") else None
            plot_style.overlay(series, labels, out_png,
                               ylabel=f"{quantity} ({unit_for(quantity) or ''})", rain=rain)
            result = {"ok": True, "png": out_png, "series_a": cols[0], "series_b": cols[1],
                      "labels": labels, "with_rain": rain is not None, "skip_hours": skip_hours}

        elif action == "network":
            reach_lines = []
            for name in res.reaches.names:
                try:
                    reach_lines.append(list(res.reaches[name].geometry.to_shapely().coords))
                except Exception:
                    pass
            node_xy = []
            for name in res.nodes.names:
                try:
                    nd = res.nodes[name]
                    node_xy.append((float(nd.xcoord), float(nd.ycoord)))
                except Exception:
                    pass
            plot_style.network_map(reach_lines, node_xy, out_png)
            result = {"ok": True, "png": out_png,
                      "n_reaches": len(reach_lines), "n_nodes": len(node_xy)}
        else:
            df = res.read()

            def series_for(quantity, element):
                cols = schema.match_columns(df.columns, quantity, element)
                if not cols:
                    raise ValueError(f"no series for {quantity}:{element}")
                return df[cols[0]], str(cols[0])

            if action == "rain_flow":
                quantity = payload.get("quantity", "Discharge")
                flow, col = series_for(quantity, payload["element"])
                rain = None
                if payload.get("rain_dfs0"):
                    import mikeio
                    rain = mikeio.read(payload["rain_dfs0"]).to_dataframe().iloc[:, 0]
                plot_style.rain_flow_stacked(
                    flow, out_png, rain=rain,
                    flow_label=quantity, flow_unit=unit_for(quantity) or "",
                )
                result = {"ok": True, "png": out_png, "series": col, "with_rain": rain is not None}

            elif action == "timeseries":
                quantity = payload.get("quantity", "WaterLevel")
                s, col = series_for(quantity, payload["element"])
                plot_style.timeseries(s, out_png, ylabel=f"{quantity} ({unit_for(quantity) or ''})")
                result = {"ok": True, "png": out_png, "series": col}
            else:
                raise ValueError(f"unknown action: {action!r}")
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
