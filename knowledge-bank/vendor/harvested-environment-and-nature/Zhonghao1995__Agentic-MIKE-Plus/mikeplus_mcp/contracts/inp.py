"""EPA SWMM .inp helpers for the MIKE+ importer (pure; no DHI imports).

MIKE+ 2026's SWMM importer is stricter than EPA SWMM in two verified ways:

* an ``[OUTFALLS]`` row without the optional ``Gated`` column (``O1 90 FREE``,
  which SWMM reads as Gated=NO) makes the whole import fail with the opaque
  "Error importing from SWMM file." — ``patch_outfalls_gated`` appends ``NO``;
* without a checked-out license MIKE+ runs in demo mode, and importing more
  than ``DEMO_MAX_CATCHMENTS`` subcatchments fails with the same message —
  ``scan_inp`` counts what the file contains so the error can say why.
"""
from __future__ import annotations

import re

DEMO_MAX_CATCHMENTS = 10          # observed: 10 imports, 11 fails, when unlicensed
_SECTION = re.compile(r"^\s*\[([A-Za-z_]+)\]\s*$")
_COUNTED = ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS", "CONDUITS", "PUMPS",
            "ORIFICES", "WEIRS", "OUTLETS", "SUBCATCHMENTS", "RAINGAGES", "TIMESERIES")


def _rows(text: str):
    """Yield ``(section_upper, raw_line, tokens)`` for every data row."""
    section = None
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            section = m.group(1).upper()
            continue
        s = line.strip()
        if not s or s.startswith(";"):
            continue
        yield section, line, s.split()


def outfalls_missing_gated(text: str) -> list[str]:
    """Names of ``[OUTFALLS]`` rows that omit the Gated column.

    Row = ``Name Elev Type [StageData] [Gated] [RouteTo]``; FREE/NORMAL have no
    stage data, the other types (FIXED/TIDAL/TIMESERIES) carry one value.
    """
    out = []
    for section, _, tok in _rows(text):
        if section != "OUTFALLS" or len(tok) < 3:
            continue
        need = 3 if tok[2].upper() in ("FREE", "NORMAL") else 4
        if len(tok) == need:
            out.append(tok[0])
    return out


def patch_outfalls_gated(text: str) -> tuple[str, list[str]]:
    """Return ``(text, patched_names)`` with ``NO`` appended to gated-less outfall rows."""
    missing = set(outfalls_missing_gated(text))
    if not missing:
        return text, []
    out, patched = [], []
    for line in text.splitlines():
        s = line.strip()
        tok = s.split()
        if tok and not s.startswith(";") and not s.startswith("[") and tok[0] in missing \
                and len(tok) >= 3 and tok[2].upper() in ("FREE", "NORMAL", "FIXED", "TIDAL", "TIMESERIES"):
            line = line.rstrip() + "  NO"
            patched.append(tok[0])
        out.append(line)
    return "\n".join(out) + "\n", patched


def scan_inp(text: str) -> dict:
    """Row counts per section of interest + the gated-less outfalls."""
    counts = {k: 0 for k in _COUNTED}
    ts_names = set()
    for section, _, tok in _rows(text):
        if section in counts:
            counts[section] += 1
        if section == "TIMESERIES":
            ts_names.add(tok[0])
    counts["TIMESERIES"] = len(ts_names)   # rows -> distinct series
    return {"counts": counts, "outfalls_missing_gated": outfalls_missing_gated(text)}


def import_failure_hints(scan: dict) -> list[str]:
    """Plain-language reasons an import may have failed, from a ``scan_inp`` result."""
    hints = []
    if scan["outfalls_missing_gated"]:
        hints.append("[OUTFALLS] rows without the Gated column (MIKE+ requires it): "
                     + ", ".join(scan["outfalls_missing_gated"][:8]))
    n = scan["counts"].get("SUBCATCHMENTS", 0)
    if n > DEMO_MAX_CATCHMENTS:
        hints.append(f"{n} subcatchments > MIKE+ demo-mode limit ({DEMO_MAX_CATCHMENTS}); if no license "
                     "was checked out (GUI holding it / relay lease) the import fails: free the license and retry")
    return hints
