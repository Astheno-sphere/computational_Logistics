"""Import a SWMM / EPANET .inp into a NEW MIKE+ database. Imports mikeplus ONLY (needs a license).

stdin payload: {inp, out_sqlite, kind?: 'swmm'|'epanet', overwrite?: bool, srid?: int, projection?: str}

For SWMM the worker (verified on MIKE+ 2026):
* writes a patched COPY of the .inp next to out_sqlite when [OUTFALLS] rows lack the
  Gated column (MIKE+ rejects them; EPA SWMM defaults to NO) and imports that copy;
* sets the model type to SWMM (m_ModelSetting.ModelNo=2) after the import, so
  mike_model_info shows CS_SWMM and mike_run runs the imported setup;
* on failure explains the likely cause (gated-less outfalls / demo-mode size limit).
"""
import json
import os
import sys


def _count(db, table):
    try:
        return int(len(getattr(db.tables, table).get_muids()))
    except Exception:
        return None


def main() -> None:
    payload = json.load(sys.stdin)
    out = payload["__out"]
    try:
        import mikeplus as mp
        from mikeplus_mcp.contracts import inp as inp_utils

        inp = payload["inp"]
        out_sqlite = payload["out_sqlite"]
        kind = (payload.get("kind") or "swmm").lower()
        if kind not in ("swmm", "epanet"):
            raise ValueError("kind must be 'swmm' or 'epanet'")
        if not os.path.isfile(inp):
            raise FileNotFoundError(f"input file not found: {inp}")
        if os.path.exists(out_sqlite):
            if not payload.get("overwrite"):
                raise FileExistsError(f"{out_sqlite} exists; pass overwrite=true to replace it")
            os.remove(out_sqlite)
            side = os.path.splitext(out_sqlite)[0] + ".mupp"   # companion project file
            if os.path.exists(side):
                os.remove(side)
        os.makedirs(os.path.dirname(os.path.abspath(out_sqlite)), exist_ok=True)

        scan, patched, inp_used = None, [], inp
        if kind == "swmm":
            text = open(inp, encoding="utf-8", errors="replace").read()
            scan = inp_utils.scan_inp(text)
            fixed, patched = inp_utils.patch_outfalls_gated(text)
            if patched:
                inp_used = os.path.join(os.path.dirname(os.path.abspath(out_sqlite)),
                                        os.path.splitext(os.path.basename(inp))[0] + ".mikeplus.inp")
                with open(inp_used, "w", encoding="ascii", errors="replace") as fh:
                    fh.write(fixed)

        kwargs = {}
        if payload.get("srid") is not None:
            kwargs["srid"] = int(payload["srid"])
        if payload.get("projection"):
            kwargs["projection_string"] = payload["projection"]
        try:
            with mp.create(out_sqlite, **kwargs) as db:
                if kind == "swmm":
                    db.import_from_swmm(inp_used)
                    # the importer fills the mss_* (SWMM) tables but leaves the model type
                    # at MIKE 1D; switch it so the model opens/runs as a SWMM model
                    db.tables.m_ModelSetting.update({"ModelNo": 2}).by_muid(["MuModel"]).execute()
                else:
                    db.import_from_epanet(inp_used)
        except Exception as exc:
            hints = inp_utils.import_failure_hints(scan) if scan else []
            msg = f"{type(exc).__name__}: {str(exc).strip()}"
            if hints:
                msg += " | likely cause(s): " + " ; ".join(hints)
            raise RuntimeError(msg) from None

        # report from a fresh connection so we describe what is really on disk
        with mp.open(out_sqlite) as db:
            proj = "mss_Project" if kind == "swmm" else "mw_Project"
            try:
                sims = [str(x) for x in list(getattr(db.tables, proj).to_dataframe().index)]
            except Exception:
                sims = []
            counts = {
                "nodes": _count(db, "mss_Node"), "links": _count(db, "mss_Link"),
                "catchments": _count(db, "msm_Catchment"),
                "wd_junctions": _count(db, "mw_Junction"), "wd_pipes": _count(db, "mw_Pipe"),
            }
            result = {
                "ok": True, "kind": kind, "inp": inp, "inp_used": inp_used,
                "patched_outfalls_gated": patched, "sqlite": out_sqlite,
                "active_model": str(db.active_model),
                "active_simulation": str(db.active_simulation),
                "unit_system": str(db.unit_system),
                "simulations": sims,
                "counts": {k: v for k, v in counts.items() if v},
                "inp_scan": scan["counts"] if scan else None,
            }
        if not result["counts"]:
            raise RuntimeError("import produced an empty model (no nodes/links/junctions/pipes) — "
                               "check the .inp and that MIKE+ is licensed")
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    sys.exit(0 if result.get("ok") else 1)


main()
