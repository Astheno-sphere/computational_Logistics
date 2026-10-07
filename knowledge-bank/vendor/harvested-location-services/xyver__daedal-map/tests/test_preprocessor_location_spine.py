from __future__ import annotations

import json
import unittest
from functools import lru_cache
from pathlib import Path

import pandas as pd
import pytest

from mapmover.explore.preprocessor_runtime import (
    detect_location_candidates,
    extract_country_from_query,
    extract_query_constraints,
)
from mapmover.runtime.geography_reference import translate_geometry_id_to_local_id
from mapmover.runtime.loc_id_resolution import resolve_admin_text_to_loc_id


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "county-map-data"
GEOMETRY_ROOT = DATA_ROOT / "geometry"
ISO_CODES_PATH = REPO_ROOT / "county-map" / "mapmover" / "reference" / "iso_codes.json"

SAMPLE_COUNTRIES = ["USA", "CAN", "MEX", "BRA", "FRA", "DEU", "IND", "JPN", "AUS", "ZAF"]
SAMPLE_LEVELS = (1, 2)
SAMPLES_PER_LEVEL = 10


@lru_cache(maxsize=1)
def _iso3_to_name() -> dict[str, str]:
    payload = json.loads(ISO_CODES_PATH.read_text(encoding="utf-8"))
    return {
        str(key).strip().upper(): str(value).strip()
        for key, value in (payload.get("iso3_to_name") or {}).items()
        if str(key).strip() and str(value).strip()
    }


def _pick_evenly_spaced_rows(df: pd.DataFrame, count: int) -> pd.DataFrame:
    if df.empty:
        return df
    if len(df) <= count:
        return df.reset_index(drop=True)
    max_index = len(df) - 1
    chosen = sorted({round(i * max_index / (count - 1)) for i in range(count)})
    return df.iloc[chosen].reset_index(drop=True)


def _load_country_level_samples(iso3: str, admin_level: int, per_level: int) -> list[dict]:
    parquet_path = GEOMETRY_ROOT / f"{iso3}.parquet"
    if not parquet_path.exists():
        return []

    df = pd.read_parquet(parquet_path, columns=["loc_id", "name", "admin_level"])
    if df.empty:
        return []

    level_df = df[df["admin_level"] == admin_level].copy()
    if level_df.empty:
        return []

    level_df["name"] = level_df["name"].astype(str).str.strip()
    level_df = level_df[level_df["name"] != ""]
    level_df = level_df[~level_df["name"].str.contains(r"\?", regex=True, na=False)]
    level_df["name_key"] = level_df["name"].str.lower()
    counts = level_df["name_key"].value_counts()
    level_df = level_df[level_df["name_key"].map(counts) == 1]

    all_names_df = df.copy()
    all_names_df["name"] = all_names_df["name"].astype(str).str.strip()
    all_names_df = all_names_df[all_names_df["name"] != ""]
    all_names_df["name_key"] = all_names_df["name"].str.lower()
    cross_level_counts = all_names_df["name_key"].value_counts()
    level_df = level_df[level_df["name_key"].map(cross_level_counts) == 1]

    level_df = level_df.sort_values(["name_key", "loc_id"]).reset_index(drop=True)
    level_df = _pick_evenly_spaced_rows(level_df, per_level)

    samples = []
    for row in level_df.itertuples(index=False):
        samples.append(
            {
                "iso3": iso3,
                "country_name": _iso3_to_name().get(iso3, iso3),
                "admin_level": int(row.admin_level),
                "name": str(row.name).strip(),
                "expected_loc_id": translate_geometry_id_to_local_id(str(row.loc_id).strip()),
            }
        )
    return samples


@lru_cache(maxsize=1)
def _generated_location_samples() -> list[dict]:
    samples: list[dict] = []
    for iso3 in SAMPLE_COUNTRIES:
        for admin_level in SAMPLE_LEVELS:
            samples.extend(_load_country_level_samples(iso3, admin_level, SAMPLES_PER_LEVEL))
    return samples


class PreprocessorLocationSpineTests(unittest.TestCase):
    @pytest.mark.spine_gap(
        "2 of 4 subcases fail: 'normandie france' expects pre-v2 G-ID FRA-G141265; 'harris county usa' needs suffix handling plus GA/TX disambiguation (counties stored bare as 'Harris')."
    )
    def test_curated_shared_location_cases(self):
        cases = [
            {
                "query": "show me the fires in ontario canada bigger than 200km2",
                "expected_loc_id": "CAN-ON",
            },
            {
                "query": "show me data in california usa",
                "expected_loc_id": "USA-CA",
            },
            {
                "query": "show me population in normandie france",
                "expected_loc_id": "FRA-G141265",
            },
            {
                "query": "show me the counties in harris county usa",
                "expected_loc_id": "USA-TX-201",
            },
        ]

        for case in cases:
            with self.subTest(query=case["query"]):
                constraints = extract_query_constraints(case["query"])
                self.assertEqual(constraints["region_loc_id"], case["expected_loc_id"])

                extracted = extract_country_from_query(case["query"])
                self.assertEqual(extracted.get("loc_id"), case["expected_loc_id"])

                candidates = detect_location_candidates(case["query"])
                self.assertEqual((candidates.get("best") or {}).get("loc_id"), case["expected_loc_id"])

    def test_lowercase_bare_iso3_words_are_not_locations(self):
        cases = [
            ("can you show me volcanoes", "CAN"),
            ("show me co2 per capita", "PER"),
            ("volcanic eruptions 10 years ago", "AGO"),
            ("Are there tsunami events in the Mediterranean in this data?", "ARE"),
        ]

        for query, iso3 in cases:
            with self.subTest(query=query):
                extracted = extract_country_from_query(query)
                self.assertIsNone(extracted.get("match"))

                candidates = detect_location_candidates(query)
                self.assertIsNone(candidates.get("best"))
                ignored = candidates.get("ignored_locations") or []
                self.assertTrue(
                    any(item.get("iso3") == iso3 for item in ignored),
                    f"expected ignored lowercase ISO3 evidence for {iso3}",
                )

    def test_uppercase_iso3_and_human_aliases_still_resolve(self):
        cases = [
            ("show me volcanoes in CAN", "CAN"),
            ("show me volcanoes in the uae", "ARE"),
            ("show me volcanoes in Canada", "CAN"),
        ]

        for query, expected_loc_id in cases:
            with self.subTest(query=query):
                extracted = extract_country_from_query(query)
                self.assertEqual(extracted.get("loc_id"), expected_loc_id)

                candidates = detect_location_candidates(query)
                self.assertEqual((candidates.get("best") or {}).get("loc_id"), expected_loc_id)

    def test_zip_resolution_still_returns_deepest_stack(self):
        resolved = resolve_admin_text_to_loc_id("90210", country_hint="USA")
        self.assertEqual(resolved.get("match_type"), "postal_code")
        self.assertTrue(str(resolved.get("deepest_resolved_loc_id") or "").startswith("USA-CA-"))
        self.assertEqual(resolved.get("deepest_resolved_admin_level"), "admin_2")

    @pytest.mark.spine_gap(
        "1 of 196 subcases fails: AUS 'Other Territories' admin_1 has no local alias, so AUS-OT and its G-ID are disconnected in the AUS crosswalk."
    )
    def test_geometry_backed_query_location_samples(self):
        samples = _generated_location_samples()
        self.assertGreaterEqual(len(samples), 150, "expected broad deterministic location coverage")

        for sample in samples:
            query = f"show me data in {sample['name']}, {sample['country_name']}"
            with self.subTest(
                iso3=sample["iso3"],
                admin_level=sample["admin_level"],
                name=sample["name"],
            ):
                direct = resolve_admin_text_to_loc_id(sample["name"], country_hint=sample["iso3"])
                self.assertEqual(
                    str(direct.get("deepest_resolved_loc_id") or ""),
                    sample["expected_loc_id"],
                )

                constraints = extract_query_constraints(query)
                self.assertEqual(constraints["region_loc_id"], sample["expected_loc_id"])

                extracted = extract_country_from_query(query)
                self.assertEqual(extracted.get("loc_id"), sample["expected_loc_id"])

                candidates = detect_location_candidates(query)
                self.assertEqual((candidates.get("best") or {}).get("loc_id"), sample["expected_loc_id"])


if __name__ == "__main__":
    unittest.main()
