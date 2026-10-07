"""Read/modify MIKE+ model parameters in any table. Imports mikeplus ONLY.

stdin payload:
  get: {sqlite, table, columns?, muids?}
  set: {sqlite, table, values{col:val}, muids? | all?}   -- set MUTATES the db
"""
import json
import sys


def _records(df):
    if df is None:
        return None
    safe = df.astype(object).where(df.notna(), None)
    return {str(k): v for k, v in safe.to_dict(orient="index").items()}


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeplus as mp

        sqlite = payload["sqlite"]
        action = payload.get("action", "get")
        table = payload["table"]

        with mp.open(sqlite) as db:
            tbl = getattr(db.tables, table)

            if action == "get":
                cols = payload.get("columns") or []
                q = tbl.select(cols)
                muids = payload.get("muids")
                if muids:
                    q = q.by_muid(muids)
                df = q.to_dataframe()
                result = {
                    "ok": True, "table": table,
                    "n_rows": int(len(df)),
                    "columns": [str(c) for c in df.columns],
                    "rows": _records(df),
                }

            elif action == "set":
                values = payload["values"]
                muids = payload.get("muids")
                cols = list(values.keys())
                if muids:
                    before = _records(tbl.select(cols).by_muid(muids).to_dataframe())
                    tbl.update(values).by_muid(muids).execute()
                    after = _records(tbl.select(cols).by_muid(muids).to_dataframe())
                    # verify the edit persisted — demo/unlicensed mode silently drops edits
                    bad = []
                    for mu in muids:
                        row = (after or {}).get(mu, {})
                        for col, want in values.items():
                            got = row.get(col)
                            same = got == want or (
                                isinstance(want, (int, float)) and isinstance(got, (int, float))
                                and abs(float(got) - float(want)) < 1e-9
                            )
                            if not same:
                                bad.append(f"{mu}.{col}: wanted {want!r}, got {got!r}")
                    if bad:
                        raise RuntimeError(
                            "edit did not persist — MIKE+ may be in demo/unlicensed mode, or the "
                            "value was rejected: " + "; ".join(bad[:6])
                        )
                elif payload.get("all"):
                    tbl.update(values).all().execute()
                    before = after = None
                else:
                    raise ValueError("set requires 'muids' (a list) or all=true")
                result = {
                    "ok": True, "table": table, "values": values,
                    "muids": muids, "before": before, "after": after,
                }
            else:
                raise ValueError(f"unknown action: {action!r}")
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
