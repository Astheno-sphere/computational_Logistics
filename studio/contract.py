"""The trajectory contract: the one table between simulation and rendering.

Solvers and simulators write it, renderers only read it. Nothing is drawn until `validate` passes, and
no number is narrated unless `compare_to_paper` has checked it against the paper's reported value.

Trajectory rows (one per agent per timestamp, pandas DataFrame):
    agent_id  str     vessel / helicopter / crew id
    t         float   seconds from scenario start
    lon, lat  float   WGS84 degrees
    alt_m     float   metres above sea level (0 for vessels; optional column)
    state     str     one of STATES
    load      float   units on board (optional column)
Agents table (one row per agent):
    agent_id, cls (psv | ferry | helicopter | crew_boat | worker | ...), vmax_mps, capacity, domain ("sea" | "air" | "land")
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

STATES = ("sail", "fly", "drive", "walk", "load", "unload", "wait", "idle", "dp", "charge")
MOVING = {"sail", "fly", "drive", "walk"}
REQUIRED = ("agent_id", "t", "lon", "lat", "state")
EARTH_R = 6_371_008.8


def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


@dataclass
class Report:
    violations: list = field(default_factory=list)  # (check, agent_id, detail)

    @property
    def ok(self):
        return not self.violations

    def add(self, check, agent, detail):
        self.violations.append((check, agent, detail))

    def __str__(self):
        if self.ok:
            return "contract: OK"
        lines = [f"contract: {len(self.violations)} violation(s)"]
        lines += [f"  [{c}] {a}: {d}" for c, a, d in self.violations[:50]]
        return "\n".join(lines)


def validate(traj: pd.DataFrame, agents: pd.DataFrame, land=None, speed_tol=0.05, still_m=25.0) -> Report:
    """Check a trajectory against physics and bookkeeping. `land` is an optional shapely geometry in
    lon/lat; sea agents' moving legs must not cross it (air agents are exempt)."""
    r = Report()
    miss = [c for c in REQUIRED if c not in traj.columns]
    if miss:
        r.add("schema", "*", f"missing columns {miss}")
        return r
    if traj[list(REQUIRED)].isna().any().any():
        r.add("schema", "*", "NaN in required columns")
    bad_state = sorted(set(traj["state"]) - set(STATES))
    if bad_state:
        r.add("schema", "*", f"unknown states {bad_state}")
    unknown = sorted(set(traj["agent_id"]) - set(agents["agent_id"]))
    if unknown:
        r.add("schema", "*", f"agents not in agents table {unknown}")
    spec = agents.set_index("agent_id")
    for aid, g in traj.groupby("agent_id", sort=False):
        if aid not in spec.index:
            continue
        a = spec.loc[aid]
        g = g.reset_index(drop=True)
        dt = np.diff(g["t"].to_numpy())
        if (dt < 0).any():
            r.add("time", aid, f"time goes backwards at row {int(np.argmax(dt < 0)) + 1}")
            continue
        d = haversine_m(g["lon"].to_numpy()[:-1], g["lat"].to_numpy()[:-1],
                        g["lon"].to_numpy()[1:], g["lat"].to_numpy()[1:])
        jump = (dt == 0) & (d > still_m)
        if jump.any():
            r.add("teleport", aid, f"{int(jump.sum())} position jump(s) with zero elapsed time")
        with np.errstate(divide="ignore", invalid="ignore"):
            v = np.where(dt > 0, d / dt, 0.0)
        over = v > a["vmax_mps"] * (1 + speed_tol)
        if over.any():
            i = int(np.argmax(v))
            r.add("speed", aid, f"{over.sum()} leg(s) above vmax {a['vmax_mps']:.1f} m/s; worst {v[i]:.1f} m/s at t={g['t'][i]:.0f}")
        # a stationary state must not move: the state of the leg is the state at its start
        still = ~g["state"].iloc[:-1].isin(MOVING).to_numpy() & (d > still_m)
        if still.any():
            i = int(np.argmax(still))
            r.add("state", aid, f"moves {d[i]:.0f} m while '{g['state'][i]}' at t={g['t'][i]:.0f}")
        if "load" in g and "capacity" in a and pd.notna(a.get("capacity")):
            lo, hi = g["load"].min(), g["load"].max()
            if lo < -1e-9 or hi > a["capacity"] + 1e-9:
                r.add("capacity", aid, f"load range [{lo}, {hi}] outside [0, {a['capacity']}]")
        if land is not None and a.get("domain", "sea") == "sea":
            _check_land(r, aid, g, land)
    return r


def _check_land(r, aid, g, land):
    from shapely.geometry import LineString
    from shapely.prepared import prep

    pl = prep(land)
    xy = g[["lon", "lat"]].to_numpy()
    moving = g["state"].isin(MOVING).to_numpy()
    hits = 0
    first = None
    for i in range(len(xy) - 1):
        if not moving[i] or (xy[i] == xy[i + 1]).all():
            continue
        seg = LineString([xy[i], xy[i + 1]])
        # ports sit on the shore: only a leg whose interior enters land is a crossing
        if pl.intersects(seg) and land.intersection(seg).length > 1e-4 * max(seg.length, 1e-9) + 2e-4:
            hits += 1
            first = first if first is not None else float(g["t"][i])
    if hits:
        r.add("land", aid, f"{hits} sea leg(s) cross land; first at t={first:.0f}")


def kpis(traj: pd.DataFrame) -> dict:
    """Measured values every narration must come from."""
    out = {"agents": {}}
    tot_d = 0.0
    for aid, g in traj.groupby("agent_id", sort=False):
        g = g.reset_index(drop=True)
        d = haversine_m(g["lon"].to_numpy()[:-1], g["lat"].to_numpy()[:-1], g["lon"].to_numpy()[1:], g["lat"].to_numpy()[1:])
        dt = np.diff(g["t"].to_numpy())
        by_state = pd.Series(dt, index=g["state"].iloc[:-1]).groupby(level=0).sum().to_dict()
        out["agents"][aid] = {"distance_km": float(d.sum() / 1000), "time_s": float(g["t"].iloc[-1] - g["t"].iloc[0]),
                              "time_by_state_s": {k: float(v) for k, v in by_state.items()}}
        tot_d += d.sum()
    out["distance_km"] = float(tot_d / 1000)
    out["makespan_s"] = float(traj["t"].max() - traj["t"].min())
    waits = sum(a["time_by_state_s"].get("wait", 0.0) for a in out["agents"].values())
    out["wait_s"] = float(waits)
    return out


def compare_to_paper(measured: dict, reported: dict) -> pd.DataFrame:
    """reported: {kpi_name: {"value": x, "rel_tol": 0.02}} as written in scenario.yaml `reported:`.
    A reproduction passes only if every reported KPI is within tolerance."""
    rows = []
    for k, spec in reported.items():
        m = measured.get(k)
        val, tol = float(spec["value"]), float(spec.get("rel_tol", 0.02))
        if m is None:
            rows.append((k, val, None, None, tol, False))
            continue
        rel = abs(m - val) / abs(val) if val else abs(m)
        rows.append((k, val, float(m), rel, tol, rel <= tol))
    return pd.DataFrame(rows, columns=["kpi", "paper", "ours", "rel_gap", "rel_tol", "pass"])
