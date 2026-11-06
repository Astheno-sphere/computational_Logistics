"""Build a renderer scene (JSON) from a *validated* trajectory. The renderer never sees anything else."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from studio.contract import Report


def polygons(geom):
    """shapely (Multi)Polygon in lon/lat -> deck.gl PolygonLayer rings [[outer], [hole], ...]."""
    if geom is None or geom.is_empty:
        return []
    parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    return [[[list(c) for c in p.exterior.coords]] + [[list(c) for c in h.coords] for h in p.interiors] for p in parts]


def build_scene(traj: pd.DataFrame, agents: pd.DataFrame, report: Report, *, camera: dict, overlay: dict,
                land=None, lanes=None, sites=None, accent=(), kpi_track=None, seconds=20, trail_s=None) -> dict:
    """camera: deck.gl view state {longitude, latitude, zoom, pitch, bearing}.
    overlay: {kicker, title, legend: [[hex, label]], source, watermark}. accent: agent ids drawn in the accent.
    kpi_track: [[label, [[t, display_value], ...]], ...] values shown over time (from studio.contract.kpis only)."""
    if not report.ok:
        raise ValueError(f"refusing to build a scene from an invalid trajectory\n{report}")
    cls = agents.set_index("agent_id")["cls"].to_dict()
    out = []
    for aid, g in traj.groupby("agent_id", sort=False):
        alt = g["alt_m"] if "alt_m" in g else 0.0
        out.append({"id": str(aid), "cls": cls[aid], "accent": aid in accent,
                    "path": [[float(x), float(y), float(z)] for x, y, z in zip(g["lon"], g["lat"], alt if hasattr(alt, "__iter__") else [alt] * len(g))],
                    "ts": [float(t) for t in g["t"]], "states": list(g["state"])})
    t0, t1 = float(traj["t"].min()), float(traj["t"].max())
    return {"t0": t0, "t1": t1, "seconds": seconds, "trail_s": trail_s or (t1 - t0) / 6,
            "camera": camera, "overlay": {**overlay, "kpi_track": kpi_track or []},
            "world": {"land": polygons(land), "lanes": lanes or [], "sites": sites or []},
            "agents": out}


def write(scene: dict, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(scene, separators=(",", ":")))
    return path
