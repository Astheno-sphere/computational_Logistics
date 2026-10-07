"""Inspect a MIKE+ model database. Imports mikeplus ONLY.

stdin payload: {sqlite, __out}
result: {ok, active_simulation/scenario/model, unit_system, simulations, scenarios, counts}
"""
import json
import sys


def _count(db, table: str):
    try:
        return int(len(getattr(db.tables, table).get_muids()))
    except Exception:
        return None


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeplus as mp

        sqlite = payload["sqlite"]
        with mp.open(sqlite) as db:
            # MIKE 1D models live in msm_* tables, MIKE+ SWMM models in mss_* tables
            active_model = str(db.active_model)
            pre = "mss" if active_model == "CS_SWMM" else "msm"
            try:
                proj = getattr(db.tables, f"{pre}_Project").to_dataframe()
                sims = [str(x) for x in list(proj.index)]
            except Exception:
                sims = []
            try:   # names (not reprs) so they can be passed to mike_set_scenario
                scenarios, todo = [], [db.scenarios.base]
                while todo:
                    s = todo.pop(0)
                    scenarios.append(str(s.name))
                    todo.extend(list(s.children or []))
            except Exception:
                scenarios = []
            try:
                active_scenario = str(db.active_scenario.name)
            except Exception:
                active_scenario = str(db.active_scenario)
            result = {
                "ok": True,
                "sqlite": sqlite,
                "active_simulation": str(db.active_simulation),
                "active_scenario": active_scenario,
                "active_model": active_model,
                "unit_system": str(db.unit_system),
                "simulations": sims,
                "scenarios": scenarios,
                "counts": {
                    "nodes": _count(db, f"{pre}_Node"),
                    "links": _count(db, f"{pre}_Link"),
                    "catchments": _count(db, "msm_Catchment"),
                },
            }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
