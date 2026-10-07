"""Activate an existing MIKE+ scenario. Imports mikeplus ONLY (needs a license).

stdin payload: {sqlite, scenario}

The activation is verified by RE-OPENING the database: mike_run / mike_set_values
run in fresh processes, so an activation that is not persisted is useless
(demo/unlicensed mode can silently drop writes).

Why no "create": a scenario created through mikeplus either shares its parent's
alternatives (so a table edit "in the scenario" also changes Base) or, if given
its own child alternatives, mikeplus 2026's table.update() silently writes
nothing into them (verified). What-if variants therefore go through MODEL COPIES
(see the mike-compare skill); this tool selects scenarios that already exist.
"""
import json
import sys


def _scenario_names(db):
    out, todo = [], [db.scenarios.base]
    while todo:
        s = todo.pop(0)
        out.append(str(s.name))
        todo.extend(list(s.children or []))
    return out


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeplus as mp

        sqlite = payload["sqlite"]
        wanted = payload["scenario"]
        with mp.open(sqlite) as db:
            before = str(db.active_scenario.name)
            sc = db.scenarios.by_name(wanted) or db.scenarios.find_by_id(wanted)
            if sc is None:
                raise ValueError(f"scenario {wanted!r} not found; scenarios: {_scenario_names(db)}")
            target = str(sc.name)
            sc.activate()
            in_session = str(db.active_scenario.name)
            names = _scenario_names(db)
            own = [str(a.group.name) for a in sc.alternatives if not getattr(a, "is_base", False)]
            shared = [str(a.group.name) for a in sc.alternatives if getattr(a, "is_base", False)]
        if in_session != target:
            raise RuntimeError(f"activate() had no effect: active scenario is still {in_session!r}")

        with mp.open(sqlite) as db2:   # persistence check in a fresh connection
            after = str(db2.active_scenario.name)
        if after != target:
            raise RuntimeError(
                f"activation did not persist: wanted {target!r}, database reopens with {after!r} "
                "(MIKE+ may be in demo/unlicensed mode, or the GUI holds the model)")

        result = {
            "ok": True, "sqlite": sqlite, "previous_active": before, "active_scenario": after,
            "scenarios": names,
            "own_alternatives_in": own,
            "shares_base_alternatives_in": shared,
            "note": ("mike_run now runs this scenario. Table edits (mike_set_values) under it: in "
                     "groups listed in shares_base_alternatives_in they ALSO change Base; in groups "
                     "listed in own_alternatives_in mikeplus cannot write (the edit is refused). "
                     "For what-if edits use a model copy instead."),
        }
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
