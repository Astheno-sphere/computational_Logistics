from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from mapmover.runtime.place_lookup import normalize_place_name, resolve_populated_place


def _write_index(root: Path, rows: list[dict]) -> None:
    target = root / "CAN" / "place_lookup"
    target.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(target / "places.parquet", index=False)


def test_normalize_place_name_removes_case_and_diacritics() -> None:
    assert normalize_place_name(" Montréal ") == "montreal"


def test_place_lookup_prefers_unique_best_subtype() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write_index(root, [
            {"lookup_key": "toronto", "matched_name": "Toronto", "display_name": "Toronto", "loc_id": "CITY", "subtype": "CITY", "subtype_rank": 0, "country_code": "CAN", "region_label": "Ontario", "latitude": 1.0, "longitude": 2.0, "source_system": "authority", "source_release": "2026"},
            {"lookup_key": "toronto", "matched_name": "Toronto", "display_name": "Toronto", "loc_id": "UNP", "subtype": "UNP", "subtype_rank": 6, "country_code": "CAN", "region_label": "Ontario", "latitude": 3.0, "longitude": 4.0, "source_system": "authority", "source_release": "2026"},
        ])
        with patch("mapmover.runtime.place_lookup.COUNTRY_GEOMETRY_DIR", root):
            resolved = resolve_populated_place("Toronto", country_hint="CAN")
        assert resolved["status"] == "matched"
        assert resolved["match"]["loc_id"] == "CITY"


def test_place_lookup_returns_equal_rank_ambiguity() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write_index(root, [
            {"lookup_key": "springfield", "matched_name": "Springfield", "display_name": "Springfield", "loc_id": "ONE", "subtype": "TOWN", "subtype_rank": 3, "country_code": "CAN", "region_label": "A", "latitude": 1.0, "longitude": 2.0, "source_system": "authority", "source_release": "2026"},
            {"lookup_key": "springfield", "matched_name": "Springfield", "display_name": "Springfield", "loc_id": "TWO", "subtype": "TOWN", "subtype_rank": 3, "country_code": "CAN", "region_label": "B", "latitude": 3.0, "longitude": 4.0, "source_system": "authority", "source_release": "2026"},
        ])
        with patch("mapmover.runtime.place_lookup.COUNTRY_GEOMETRY_DIR", root):
            resolved = resolve_populated_place("Springfield", country_hint="CAN")
        assert resolved["status"] == "ambiguous"
        assert len(resolved["candidates"]) == 2
