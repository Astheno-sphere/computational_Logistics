"""Read MIKE+ res1d results. Imports mikeio1d ONLY (+ pure contracts). No license.

stdin payload: {action: list|summary|read|compare|flooding, res1d, ...}
"""
import json
import sys


def _skip(df, skip_hours):
    """Drop the first ``skip_hours`` of a result frame (warm-up window)."""
    if skip_hours:
        import pandas as pd
        cutoff = df.index[0] + pd.Timedelta(hours=float(skip_hours))
        df = df.loc[df.index >= cutoff]
    return df


def _compare(payload):
    """Baseline (A) vs scenario (B): one element's series, or every element's peak."""
    import mikeio1d
    from mikeplus_mcp.contracts import compare as cmp, schema

    skip_hours = payload.get("skip_hours") or 0
    df_a = _skip(mikeio1d.open(payload["res1d_a"]).read(), skip_hours)
    df_b = _skip(mikeio1d.open(payload["res1d_b"]).read(), skip_hours)
    quantity = payload["quantity"]
    element = payload.get("element")
    result = {"ok": True, "res1d_a": payload["res1d_a"], "res1d_b": payload["res1d_b"],
              "quantity": quantity, "skip_hours": skip_hours}
    if element:
        ca = schema.match_columns(df_a.columns, quantity, element)
        cb = schema.match_columns(df_b.columns, quantity, element)
        missing = [tag for tag, cols in (("A", ca), ("B", cb)) if not cols]
        if missing:
            raise ValueError(f"no series for {quantity}:{element} in result {' and '.join(missing)}")
        result.update({
            "element_id": element,
            "column_a": str(ca[0]),
            "column_b": str(cb[0]),
            "comparison": cmp.compare_series(
                df_a[ca[0]], df_b[cb[0]], quantity,
                label_a=payload.get("label_a") or "baseline",
                label_b=payload.get("label_b") or "scenario"),
        })
    else:
        result["by_element"] = cmp.compare_frames(
            df_a, df_b, quantity, top_n=int(payload.get("top_n") or 10))
    return result


def _flooding(res, df, top_n, include_outlets=False):
    """Peak water level vs ground level for every node in ``res``.

    Outlets are skipped by default: their level is the boundary condition, so
    'above ground' there is not flooding.
    """
    from mikeplus_mcp.contracts import schema

    names = set(res.nodes.names)
    rows = []
    n_outlets_skipped = 0
    for c in df.columns:
        meta = schema.parse_column(c)
        if meta["quantity"] != "WaterLevel" or meta["chainage"] is not None:
            continue
        nid = meta["element_id"]
        if nid not in names:
            continue
        s = df[c]
        pk = float(s.max())
        if pk != pk:  # NaN
            continue
        nd = res.nodes[nid]
        if not include_outlets and "Outlet" in str(nd.type):
            n_outlets_skipped += 1
            continue
        gl = nd.ground_level
        cl = nd.critical_level
        gl = None if gl is None else float(gl)
        cl = None if cl is None else float(cl)
        rows.append({
            "node": nid,
            "type": str(nd.type),
            "peak_wl": round(pk, 4),
            "peak_time": str(s.idxmax()),
            "ground_level": None if gl is None else round(gl, 4),
            "critical_level": None if cl is None else round(cl, 4),
            "freeboard_m": None if gl is None else round(gl - pk, 4),
            "above_critical_m": None if cl is None else round(pk - cl, 4),
        })
    with_gl = [r for r in rows if r["freeboard_m"] is not None]
    flooded = sorted((r for r in with_gl if r["freeboard_m"] < -1e-6), key=lambda r: r["freeboard_m"])
    dry = sorted((r for r in with_gl if r["freeboard_m"] >= -1e-6), key=lambda r: r["freeboard_m"])
    by_type = {}
    for r in flooded:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    return {
        "n_nodes": len(rows),
        "n_outlets_skipped": n_outlets_skipped,
        "n_with_ground_level": len(with_gl),
        "n_flooded": len(flooded),
        "n_above_critical": sum(1 for r in rows if r["above_critical_m"] is not None and r["above_critical_m"] > 1e-6),
        "flooded_by_type": by_type,
        "flooded": flooded[:top_n],
        "closest_to_flooding": dry[:5],
    }


def _ids(coll, n=25):
    """Best-effort (count, sample-ids) for a mikeio1d collection; never raises."""
    count = None
    try:
        count = int(len(coll))
    except Exception:
        pass
    sample = []
    try:
        names = getattr(coll, "names", None)
        if names is not None:
            sample = [str(x) for x in list(names)[:n]]
        else:
            for i, item in enumerate(coll):
                if i >= n:
                    break
                sample.append(str(getattr(item, "id", getattr(item, "name", item))))
    except Exception:
        sample = []
    return {"count": count, "sample": sample}


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeio1d
        from mikeplus_mcp.contracts import schema
        from mikeplus_mcp.contracts.units import unit_for

        action = payload.get("action", "list")
        # 'compare' opens two files itself; every other action works on one res1d
        res = mikeio1d.open(payload["res1d"]) if action != "compare" else None

        if action == "compare":
            result = _compare(payload)

        elif action == "flooding":
            df = _skip(res.read(), payload.get("skip_hours") or 0)
            result = {"ok": True, "res1d": payload["res1d"],
                      "skip_hours": payload.get("skip_hours") or 0,
                      **_flooding(res, df, int(payload.get("top_n") or 20),
                                  include_outlets=bool(payload.get("include_outlets")))}

        elif action == "list":
            ti = res.time_index
            result = {
                "ok": True,
                "res1d": payload["res1d"],
                "quantities": list(res.quantities),
                "nodes": _ids(res.nodes),
                "reaches": _ids(res.reaches),
                "structures": _ids(res.structures),
                "catchments": _ids(res.catchments),
                "time": {
                    "start": str(res.start_time),
                    "end": str(res.end_time),
                    "n_steps": int(len(ti)),
                },
            }

        elif action == "summary":
            skip_hours = payload.get("skip_hours") or 0
            df = _skip(res.read(), skip_hours)
            result = {
                "ok": True,
                "res1d": payload["res1d"],
                "skip_hours": skip_hours,
                "summary": schema.summarize(df, payload.get("quantities")),
            }

        elif action == "read":
            quantity = payload["quantity"]
            element = payload["element"]
            df = res.read()
            cols = schema.match_columns(df.columns, quantity, element)
            if not cols:
                raise ValueError(f"no series for quantity={quantity!r} element={element!r}")
            col = cols[0]
            full = df[col]
            # peak computed on the FULL series so downsampling can never hide it
            pv = full.max()
            has_peak = pv == pv  # False only when NaN
            max_pts = int(payload.get("max_points", 5000))
            step = max(1, len(full) // max_pts)
            s = full.iloc[::step]
            if step > 1 and has_peak:
                # stride decimation skips extrema — splice the true peak back in
                t_peak = full.idxmax()
                if t_peak not in s.index:
                    s = full.reindex(s.index.union([t_peak]))
            meta = schema.parse_column(col)
            result = {
                "ok": True,
                "res1d": payload["res1d"],
                "column": str(col),
                "quantity": quantity,
                "element_id": meta["element_id"],
                "chainage": meta["chainage"],
                "unit": unit_for(quantity),
                "n_points": int(len(s)),
                "downsampled": bool(step > 1),
                "peak_value": float(pv) if has_peak else None,
                "peak_time": str(full.idxmax()) if has_peak else None,
                "times": [str(t) for t in s.index],
                "values": [float(v) for v in s.values],
            }
        else:
            raise ValueError(f"unknown action: {action!r}")
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
