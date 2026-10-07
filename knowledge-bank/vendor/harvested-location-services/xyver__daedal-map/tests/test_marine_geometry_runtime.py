import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

import mapmover.runtime.marine_geometry as marine_runtime
from mapmover.runtime.reference_exchange import _geometry_catalog_domains
from mapmover.runtime.marine_geometry import (
    has_marine_geometry,
    is_marine_loc_id,
    load_marine_geometry,
    marine_bank_for_loc_id,
    resolve_marine_geometry_source,
)
from mapmover.runtime.geography_reference import is_named_water_loc_id


class MarineGeometryRuntimeTests(unittest.TestCase):
    def test_jurisdiction_batch_tree_returns_only_exact_point_matches(self):
        from shapely.geometry import Polygon

        jurisdictions = pd.DataFrame([
            {
                "loc_id": "LEFT",
                "geometry_wkb": Polygon([(0, 0), (0, 2), (2, 2), (2, 0)]).wkb,
            },
            {
                "loc_id": "RIGHT",
                "geometry_wkb": Polygon([(3, 0), (3, 2), (5, 2), (5, 0)]).wkb,
            },
        ])

        matches = marine_runtime._exact_jurisdiction_matches(
            [{"lon": 1, "lat": 1}, {"lon": 4, "lat": 1}, {"lon": 10, "lat": 1}],
            jurisdictions,
        )

        self.assertEqual(matches, {0: {"LEFT"}, 1: {"RIGHT"}})

    def test_catalog_domain_projection_exposes_activation_without_component_bloat(self):
        catalog = {"domain_profiles": [{
            "release_unit_id": "MARINE",
            "release_unit_kind": "global_domain",
            "label": "Marine",
            "family_ids": ["water_body", "marine_jurisdiction"],
            "release_status": "published",
            "active_release": {
                "release_id": "marine_geometry_1_0_1",
                "release_version": "1.0.1",
                "publication_status": "published",
                "runtime_artifacts": {
                    "jurisdictions": {"path": "geometry/domains/MARINE/jurisdictions.parquet"},
                    "country_components": {
                        "USA": {"path": "geometry/domains/MARINE/country_components/USA.parquet"},
                        "CAN": {"path": "geometry/domains/MARINE/country_components/CAN.parquet"},
                    },
                    "point_bank": {"path": "geometry/domains/MARINE/point_bank.parquet"},
                },
            },
        }]}

        domains = _geometry_catalog_domains(catalog)

        self.assertEqual(len(domains), 1)
        self.assertEqual(domains[0]["release_unit_id"], "MARINE")
        self.assertEqual(domains[0]["release_id"], "marine_geometry_1_0_1")
        self.assertEqual(domains[0]["country_component_count"], 2)
        self.assertNotIn("country_components", domains[0]["runtime_artifacts"])
        self.assertEqual(
            domains[0]["runtime_artifacts"]["point_bank"]["path"],
            "geometry/domains/MARINE/point_bank.parquet",
        )

    def test_active_domain_uses_catalog_paths_without_runtime_pointer(self):
        with TemporaryDirectory() as tmp:
            data_root = Path(tmp)
            geometry_root = data_root / "geometry"
            release_rel = "geometry/domains/MARINE/releases/geometry/marine_geometry_1_0_1"
            runtime_artifacts = {
                "jurisdictions": {"path": f"{release_rel}/exact/jurisdictions.parquet"},
                "water_bodies": {"path": f"{release_rel}/exact/water_bodies.parquet"},
                "named_water_areas": {"path": f"{release_rel}/exact/named_water_areas.parquet"},
                "bbox_index": {"path": f"{release_rel}/predicate/bbox_index.parquet"},
                "point_bank": {"path": f"{release_rel}/predicate/point_bank.parquet"},
                "country_components": {
                    "USA": {"path": f"{release_rel}/country_components/USA/marine_jurisdictions.parquet"},
                },
            }
            catalog = {"domain_profiles": [{
                "release_unit_id": "MARINE",
                "active_release": {
                    "publication_status": "published",
                    "runtime_artifacts": runtime_artifacts,
                },
            }]}
            with patch.object(marine_runtime, "GEOMETRY_DIR", geometry_root), patch.object(
                marine_runtime, "load_geometry_catalog", return_value=catalog,
            ):
                self.assertEqual(
                    marine_runtime._active_domain_paths()["named_water_areas"],
                    data_root / runtime_artifacts["named_water_areas"]["path"],
                )
                self.assertEqual(
                    marine_runtime._active_domain_paths()["point_bank"],
                    data_root / runtime_artifacts["point_bank"]["path"],
                )
                self.assertEqual(
                    marine_bank_for_loc_id("USA-EEZ-MRGID-8456"),
                    data_root / runtime_artifacts["country_components"]["USA"]["path"],
                )

    def test_active_domain_rejects_legacy_point_shards_without_point_bank(self):
        runtime_artifacts = {
            key: {"path": f"geometry/domains/MARINE/{key}.parquet"}
            for key in ("jurisdictions", "water_bodies", "named_water_areas", "bbox_index")
        }
        runtime_artifacts["point_shards"] = {
            f"{index:02d}": {
                "path": f"geometry/domains/MARINE/point_shards/{index:02d}.parquet",
            }
            for index in range(32)
        }
        catalog = {"catalog_fingerprint": "legacy-shards", "domain_profiles": [{
            "release_unit_id": "MARINE",
            "active_release": {
                "publication_status": "published",
                "runtime_artifacts": runtime_artifacts,
            },
        }]}
        with patch.object(marine_runtime, "load_geometry_catalog", return_value=catalog):
            marine_runtime.clear_marine_geometry_cache()
            self.assertIsNone(marine_runtime._active_domain_paths())

    def test_point_lookup_hydrates_jurisdiction_ids_from_single_point_bank(self):
        domain = {
            "bbox_index": Path("marine/bbox.parquet"),
            "point_bank": Path("marine/point_bank.parquet"),
            "water_bodies": Path("marine/water.parquet"),
            "named_water_areas": Path("marine/named.parquet"),
        }
        bbox = pd.DataFrame([{"loc_id": "EEZ-MRGID-1"}])
        jurisdiction = pd.DataFrame([{
            "loc_id": "EEZ-MRGID-1", "name": "Example", "geometry_wkb": b"shape",
        }])
        with patch.object(marine_runtime, "_active_domain_paths", return_value=domain), patch.object(
            marine_runtime, "read_rows_by_ids", return_value=jurisdiction,
        ) as exact_read, patch.object(
            marine_runtime, "read_bbox_candidates", side_effect=[bbox, pd.DataFrame(), pd.DataFrame()],
        ):
            result = marine_runtime.load_marine_geometry_at_point(-120.0, 30.0)

        self.assertEqual(set(result["loc_id"]), {"EEZ-MRGID-1"})
        exact_read.assert_called_once()
        self.assertEqual(exact_read.call_args.args[0], domain["point_bank"])
        self.assertEqual(exact_read.call_args.args[1], {"EEZ-MRGID-1"})

    def test_classification(self):
        self.assertTrue(is_marine_loc_id("EEZ-USA"))
        self.assertTrue(is_marine_loc_id("EEZ-MRGID-21801"))
        self.assertTrue(is_marine_loc_id("XSG"))
        self.assertTrue(is_marine_loc_id("XLS"))
        self.assertTrue(is_marine_loc_id("IHO1953-123"))
        self.assertTrue(is_marine_loc_id("USA-EEZ-MRGID-8456"))
        self.assertTrue(is_marine_loc_id("XOP-TS-MRGID-48975"))
        self.assertTrue(is_named_water_loc_id("IHO1953-123"))
        self.assertFalse(is_marine_loc_id("USA"))
        self.assertFalse(is_marine_loc_id("USA-CA-037"))
        self.assertFalse(is_marine_loc_id(""))

    def test_bank_routing(self):
        active = {
            "jurisdictions": Path("marine/jurisdictions.parquet"),
            "water_bodies": Path("marine/water_bodies.parquet"),
            "named_water_areas": Path("marine/named_water_areas.parquet"),
            "country_components": {"USA": Path("marine/country_components/USA.parquet")},
        }
        with patch.object(marine_runtime, "_active_domain_paths", return_value=active):
            self.assertIsNone(marine_bank_for_loc_id("EEZ-USA"))
            self.assertEqual(
                marine_bank_for_loc_id("USA-CZ-MRGID-49390"),
                active["country_components"]["USA"],
            )
            self.assertEqual(marine_bank_for_loc_id("XOP-CZ-MRGID-48975"), active["jurisdictions"])
            self.assertEqual(marine_bank_for_loc_id("XOP"), active["water_bodies"])
            self.assertEqual(marine_bank_for_loc_id("XLM"), active["water_bodies"])
            self.assertIsNone(marine_bank_for_loc_id("USA"))

    def test_bank_routing_fails_closed_without_catalog_domain(self):
        with patch.object(marine_runtime, "_active_domain_paths", return_value=None):
            self.assertIsNone(marine_bank_for_loc_id("USA-CZ-MRGID-49390"))
            self.assertIsNone(marine_bank_for_loc_id("XOP"))

    def test_resolve_source(self):
        active = {
            "jurisdictions": Path("marine/jurisdictions.parquet"),
            "water_bodies": Path("marine/water_bodies.parquet"),
            "named_water_areas": Path("marine/named_water_areas.parquet"),
            "country_components": {"USA": Path("marine/country_components/USA.parquet")},
        }
        with patch.object(marine_runtime, "_active_domain_paths", return_value=active), patch.object(
            marine_runtime, "parquet_available", return_value=True,
        ):
            self.assertEqual(
                resolve_marine_geometry_source("USA-CZ-MRGID-49390")["marine_kind"],
                "marine_jurisdiction",
            )
            self.assertEqual(resolve_marine_geometry_source("XSG")["marine_kind"], "water_body")
            self.assertIsNone(resolve_marine_geometry_source("USA")["parquet_file"])

    def test_exact_empty_result_does_not_trigger_full_bank_read(self):
        with patch.object(marine_runtime, "parquet_available", return_value=True), patch.object(
            marine_runtime, "read_rows_by_ids", return_value=marine_runtime.pd.DataFrame(),
        ) as exact_read, patch.object(
            marine_runtime, "select_columns_from_parquet",
            side_effect=AssertionError("exact miss must not become a full-bank scan"),
        ):
            result = marine_runtime._read_bank(Path("marine.parquet"), {"XOP"})
        self.assertTrue(result.empty)
        exact_read.assert_called_once()

    def test_batch_water_candidates_are_not_reopened_for_shape_hydration(self):
        domain = {
            "bbox_index": Path("marine/bbox.parquet"),
            "point_bank": Path("marine/point_bank.parquet"),
            "water_bodies": Path("marine/water.parquet"),
            "named_water_areas": Path("marine/named.parquet"),
        }

        def exact_candidates(path, _points, *, columns):
            if path == domain["water_bodies"]:
                return pd.DataFrame([{
                    "point_position": 0,
                    "loc_id": "XOP",
                    "name": "Pacific Ocean",
                    "geometry": "{}",
                    "centroid_lon": 0.0,
                    "centroid_lat": 0.0,
                    "bbox_min_lon": -180.0,
                    "bbox_min_lat": -90.0,
                    "bbox_max_lon": 180.0,
                    "bbox_max_lat": 90.0,
                }])
            return pd.DataFrame(columns=["point_position", *columns])

        with patch.object(marine_runtime, "_active_domain_paths", return_value=domain), patch.object(
            marine_runtime, "read_bbox_candidates_for_points", return_value=pd.DataFrame(
                columns=["point_position", "loc_id"],
            ),
        ), patch.object(
            marine_runtime, "read_geojson_containment_for_points", side_effect=exact_candidates,
        ), patch.object(
            marine_runtime, "read_rows_by_ids",
            side_effect=AssertionError("water candidate bank must only be scanned once"),
        ):
            frame, candidates_by_point = marine_runtime.load_marine_geometry_for_points([
                {"lon": -120.0, "lat": 30.0},
            ])

        self.assertEqual(set(frame["loc_id"]), {"XOP"})
        self.assertEqual(candidates_by_point, {0: ["XOP"]})

    def test_batch_jurisdictions_are_hydrated_from_single_point_bank(self):
        domain = {
            "bbox_index": Path("marine/bbox.parquet"),
            "point_bank": Path("marine/point_bank.parquet"),
            "water_bodies": Path("marine/water.parquet"),
            "named_water_areas": Path("marine/named.parquet"),
        }
        pairs = pd.DataFrame([{"point_position": 0, "loc_id": "EEZ-MRGID-1"}])
        jurisdiction = pd.DataFrame([{
            "loc_id": "EEZ-MRGID-1", "name": "Example", "geometry_wkb": b"shape",
        }])
        with patch.object(marine_runtime, "_active_domain_paths", return_value=domain), patch.object(
            marine_runtime, "read_bbox_candidates_for_points", return_value=pairs,
        ), patch.object(
            marine_runtime, "read_rows_by_ids", return_value=jurisdiction,
        ) as exact_read, patch.object(
            marine_runtime, "_exact_jurisdiction_matches", return_value={0: {"EEZ-MRGID-1"}},
        ), patch.object(
            marine_runtime, "read_geojson_containment_for_points",
            return_value=pd.DataFrame(columns=["point_position", "loc_id"]),
        ):
            frame, candidates_by_point = marine_runtime.load_marine_geometry_for_points([
                {"lon": -120.0, "lat": 30.0},
            ])

        self.assertEqual(set(frame["loc_id"]), {"EEZ-MRGID-1"})
        self.assertEqual(candidates_by_point, {0: ["EEZ-MRGID-1"]})
        exact_read.assert_called_once()
        self.assertEqual(exact_read.call_args.args[0], domain["point_bank"])
        self.assertEqual(exact_read.call_args.args[1], {"EEZ-MRGID-1"})

    @unittest.skipUnless(has_marine_geometry(), "marine geometry banks not present locally")
    def test_load_geometry_for_loc_ids(self):
        df = load_marine_geometry(["USA-CZ-MRGID-49390", "XSG", "XLG", "XLS", "XLM", "XLH", "XLE", "XLO"])
        ids = set(df["loc_id"])
        self.assertIn("USA-CZ-MRGID-49390", ids)
        self.assertIn("XSG", ids)
        self.assertTrue({"XLG", "XLS", "XLM", "XLH", "XLE", "XLO"}.issubset(ids))
        self.assertTrue((df["geometry"].astype(str).str.len() > 0).all())

    @unittest.skipUnless(has_marine_geometry(), "marine geometry banks not present locally")
    def test_jurisdiction_only_query_skips_water_body_bank(self):
        df = load_marine_geometry(["USA-CZ-MRGID-49390"])
        self.assertEqual(set(df["loc_id"]), {"USA-CZ-MRGID-49390"})


if __name__ == "__main__":
    unittest.main()
