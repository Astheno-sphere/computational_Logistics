from catalog_coverage_shared import (
    coverage_contract,
    coverage_matches_country,
    normalize_geographic_levels,
    normalize_scope,
    normalize_time_range,
    resolve_pack_coverage_match,
    source_coverage_window,
    temporal_intersects,
)


def test_scope_vocabulary_is_canonical() -> None:
    assert normalize_scope("usa") == "USA"
    assert normalize_scope("USA") == "USA"
    assert normalize_scope("Worldwide") == "global"
    assert normalize_scope("ocean") == "marine"


def test_global_with_regional_exclusions_does_not_claim_worldwide() -> None:
    contract = coverage_contract({
        "scope": "global",
        "geographic_coverage": {"type": "regional", "common_missing": ["CAN"]},
    })
    assert contract["assertion"] == "regional_countries_not_declared"
    assert coverage_matches_country(contract, "CAN") is False
    assert coverage_matches_country(contract, "USA") is None


def test_explicit_country_and_empty_level_meanings() -> None:
    contract = coverage_contract({
        "scope": "usa",
        "data_type": "events",
        "geographic_levels": ["admin_2"],
    })
    assert contract["countries"] == ["USA"]
    assert contract["geographic_levels"] == [2]
    assert coverage_matches_country(contract, "USA") is True
    assert coverage_matches_country(contract, "CAN") is False
    assert normalize_geographic_levels({"scope": "marine"})["empty_meaning"] == "marine_non_administrative"
    assert normalize_geographic_levels({"data_type": "raster"})["empty_meaning"] == "raster_or_grid_non_administrative"
    assert normalize_geographic_levels({"data_type": "events"})["empty_meaning"] == "not_declared"


def test_time_range_and_intersection_are_deterministic() -> None:
    requested = normalize_time_range({"start": "2020", "end": "2022"})
    assert requested == {"start": "2020", "end": "2022"}
    assert temporal_intersects("2019", "2021", requested) is True
    assert temporal_intersects("2010", "2019", requested) is False
    assert temporal_intersects(None, None, requested) is None


def test_bare_year_is_a_whole_year_span() -> None:
    # end=1950 keeps a source whose first record is 1950-01-03.
    assert temporal_intersects("1950-01-03T11:00:00", "2025-10-25", {"start": "1900", "end": "1950"}) is True
    # A source ending in the year 2024 overlaps a request starting mid-2024.
    assert temporal_intersects(2024, 2024, {"start": "2024-06-01", "end": None}) is True
    assert temporal_intersects(2024, 2024, {"start": "2025", "end": None}) is False
    # Two full timestamps still compare exactly.
    assert temporal_intersects("2024-01-01", "2024-03-01", {"start": "2024-06-01", "end": None}) is False


def test_pack_match_requires_one_source_window_to_cover_place_and_time() -> None:
    usa_early = source_coverage_window({"source_id": "a", "scope": "USA", "temporal_coverage": {"start": 1900, "end": 1950}})
    global_late = source_coverage_window({
        "source_id": "b", "scope": "global",
        "geographic_coverage": {"type": "global"}, "temporal_coverage": {"start": 2000, "end": 2020},
    })
    pack = {"coverage_windows": [usa_early, global_late]}
    assert resolve_pack_coverage_match(pack, "FRA", {"start": "2010", "end": None}) == (True, True)
    assert resolve_pack_coverage_match(pack, "FRA", {"start": "1910", "end": "1920"}) == (False, False)
    assert resolve_pack_coverage_match(pack, None, {"start": "1910", "end": "1920"}) == (True, True)
    undated = {"coverage_windows": [source_coverage_window({"source_id": "c", "scope": "USA"})]}
    assert resolve_pack_coverage_match(undated, None, {"start": "2010", "end": None}) == (None, None)
