from __future__ import annotations

from pathlib import Path

import pandas as pd

from mapmover.runtime import geometry_compatibility as compatibility


def test_alias_and_retained_geometry_contract(tmp_path: Path, monkeypatch) -> None:
    aliases_path = tmp_path / "aliases.parquet"
    legacy_path = tmp_path / "legacy_areas.parquet"
    pd.DataFrame([
        {"source_loc_id": "TST-G1OLD-G2SAME", "target_loc_id": "TST-G1NEW-G2SAME"},
    ]).to_parquet(aliases_path, index=False)
    pd.DataFrame([
        {
            "loc_id": "TST-G1OLD-G2LEGACY",
            "name": "Legacy feature",
            "geometry": '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}',
        },
    ]).to_parquet(legacy_path, index=False)
    monkeypatch.setattr(compatibility, "ALIASES_PATH", aliases_path)
    monkeypatch.setattr(compatibility, "LEGACY_AREAS_PATH", legacy_path)
    compatibility.compatibility_aliases.cache_clear()
    compatibility.retained_legacy_loc_ids.cache_clear()

    assert compatibility.translate_compatibility_loc_id("tst-g1old-g2same") == "TST-G1NEW-G2SAME"
    assert compatibility.compatibility_loc_ids() == {
        "TST-G1OLD-G2SAME",
        "TST-G1OLD-G2LEGACY",
    }
    rows = compatibility.load_legacy_geometry_rows(
        ["TST-G1OLD-G2LEGACY"],
        columns=["loc_id", "name"],
    )
    assert rows[["loc_id", "name"]].to_dict("records") == [
        {"loc_id": "TST-G1OLD-G2LEGACY", "name": "Legacy feature"},
    ]

    compatibility.compatibility_aliases.cache_clear()
    compatibility.retained_legacy_loc_ids.cache_clear()
