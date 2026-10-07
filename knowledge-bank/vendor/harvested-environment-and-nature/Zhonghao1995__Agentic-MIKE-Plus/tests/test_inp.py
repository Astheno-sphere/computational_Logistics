"""SWMM .inp helpers for the MIKE+ importer (pure)."""
from mikeplus_mcp.contracts import inp

INP = """[TITLE]
demo
[JUNCTIONS]
;;Name Elev MaxD InitD SurD Apond
J1  100 10 0 0 0
J2  95  10 0 0 0
[OUTFALLS]
;;Name Elev Type StageData Gated RouteTo
O1  90  FREE
O2  90  FREE  NO
O3  88  FIXED  1.1
O4  88  FIXED  1.1  YES
[CONDUITS]
C1 J1 J2 500 0.013 0 0 0 0
C2 J2 O1 500 0.013 0 0 0 0
[SUBCATCHMENTS]
S1 RG1 J1 1 25 100 1 0
S2 RG1 J2 1 25 100 1 0
[RAINGAGES]
RG1 INTENSITY 0:05 1.0 TIMESERIES TS1
[TIMESERIES]
TS1 01/01/2020 00:00 0
TS1 01/01/2020 00:05 10
"""


def test_outfalls_missing_gated_detects_free_and_stage_types():
    assert inp.outfalls_missing_gated(INP) == ["O1", "O3"]


def test_patch_appends_no_only_where_missing():
    fixed, patched = inp.patch_outfalls_gated(INP)
    assert patched == ["O1", "O3"]
    lines = {l.split()[0]: l.split() for l in fixed.splitlines() if l.startswith("O")}
    assert lines["O1"] == ["O1", "90", "FREE", "NO"]
    assert lines["O3"] == ["O3", "88", "FIXED", "1.1", "NO"]
    assert lines["O2"] == ["O2", "90", "FREE", "NO"]          # untouched
    assert lines["O4"] == ["O4", "88", "FIXED", "1.1", "YES"]  # untouched
    assert inp.outfalls_missing_gated(fixed) == []
    # idempotent
    assert inp.patch_outfalls_gated(fixed) == (fixed, [])


def test_scan_counts_rows_and_distinct_timeseries():
    scan = inp.scan_inp(INP)
    c = scan["counts"]
    assert c["JUNCTIONS"] == 2 and c["OUTFALLS"] == 4 and c["CONDUITS"] == 2
    assert c["SUBCATCHMENTS"] == 2 and c["RAINGAGES"] == 1 and c["TIMESERIES"] == 1
    assert scan["outfalls_missing_gated"] == ["O1", "O3"]


def test_failure_hints_name_gated_rows_and_demo_limit():
    hints = inp.import_failure_hints(inp.scan_inp(INP))
    assert len(hints) == 1 and "Gated" in hints[0] and "O1, O3" in hints[0]

    # 12 more subcatchments (inserted before [RAINGAGES] so they stay in [SUBCATCHMENTS])
    big = INP.replace("[RAINGAGES]", "".join(f"X{i} RG1 J1 1 25 100 1 0\n" for i in range(12)) + "[RAINGAGES]")
    hints = inp.import_failure_hints(inp.scan_inp(big))
    assert any("demo-mode limit" in h for h in hints)
