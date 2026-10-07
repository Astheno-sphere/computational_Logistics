from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from mapmover import foundation_helpers


class FoundationGeometryCloudTests(unittest.TestCase):
    def setUp(self) -> None:
        foundation_helpers._GLOBAL_COUNTRIES_CACHE = None
        foundation_helpers._GLOBAL_COUNTRY_DISPLAY_CACHE = None

    def tearDown(self) -> None:
        foundation_helpers._GLOBAL_COUNTRIES_CACHE = None
        foundation_helpers._GLOBAL_COUNTRY_DISPLAY_CACHE = None
        foundation_helpers._COUNTRY_CROSSWALK_CACHE.clear()

    def test_country_crosswalk_reads_canonical_country_geometry_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            path = root / "USA" / "crosswalk.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"sub_admin_levels": {"admin_3": {"folder": "tract"}}}),
                encoding="utf-8",
            )
            with mock.patch.object(
                foundation_helpers, "COUNTRY_GEOMETRY_DIR", root
            ), mock.patch.object(
                foundation_helpers, "prefer_local_geometry_reads", return_value=True
            ):
                payload = foundation_helpers.load_country_crosswalk("USA")

        self.assertEqual(payload["sub_admin_levels"]["admin_3"]["folder"], "tract")

    def test_cloud_display_frame_is_self_contained(self) -> None:
        supplemental = pd.DataFrame([{
            "loc_id": "MNP",
            "name": "Northern Mariana Islands",
            "source_system": "test",
            "geometry": '{"type":"Polygon","coordinates":[[[145,19],[146,19],[146,20],[145,20],[145,19]]]}',
        }])
        parquet = io.BytesIO()
        supplemental.to_parquet(parquet, index=False)
        display = pd.DataFrame([
            {
                "loc_id": "USA",
                "name": "United States",
                "geometry": "{}",
                "bbox_min_lon": -125.0,
                "bbox_min_lat": 24.0,
                "bbox_max_lon": -66.0,
                "bbox_max_lat": 49.0,
            },
            {
                "loc_id": "MNP",
                "name": "Northern Mariana Islands (display)",
                "geometry": "{}",
                "bbox_min_lon": 145.0,
                "bbox_min_lat": 14.0,
                "bbox_max_lon": 146.0,
                "bbox_max_lat": 21.0,
            },
        ])
        display_parquet = io.BytesIO()
        display.to_parquet(display_parquet, index=False)

        def artifact_bytes(path: str, **_kwargs):
            if path == "geometry/global/display/admin_0.parquet":
                return display_parquet.getvalue()
            raise AssertionError(path)

        with tempfile.TemporaryDirectory() as temp_name, mock.patch.object(
            foundation_helpers, "GEOMETRY_DIR", Path(temp_name) / "not-installed"
        ), mock.patch.object(
            foundation_helpers, "is_cloud_mode", return_value=True
        ), mock.patch.object(
            foundation_helpers, "read_artifact_bytes", side_effect=artifact_bytes
        ), mock.patch.object(
            foundation_helpers,
            "read_artifact_json",
            return_value={
                "license_review_status": "approved",
                "usable_for_derivation": True,
                "overlap_override_loc_ids": ["MNP"],
            },
        ), mock.patch.object(foundation_helpers, "_reference_country_codes", return_value={"USA", "MNP"}):
            frame = foundation_helpers.load_global_country_display_frame()

        self.assertEqual({"USA", "MNP"}, set(frame["loc_id"]))
        self.assertEqual(1, int((frame["loc_id"] == "MNP").sum()))
        mnp = frame.loc[frame["loc_id"] == "MNP"].iloc[0]
        self.assertEqual("Northern Mariana Islands (display)", mnp["name"])
        self.assertEqual(145.0, mnp["bbox_min_lon"])
        self.assertEqual(146.0, mnp["bbox_max_lon"])

    def test_cloud_exact_frame_uses_contained_global_namespace(self) -> None:
        exact = pd.DataFrame([{
            "loc_id": "USA",
            "name": "United States",
            "geometry": "{}",
        }])
        exact_parquet = io.BytesIO()
        exact.to_parquet(exact_parquet, index=False)
        requested: list[str] = []

        def artifact_bytes(path: str, **_kwargs):
            requested.append(path)
            if path == "geometry/global/exact/admin_0.parquet":
                return exact_parquet.getvalue()
            raise AssertionError(path)

        with tempfile.TemporaryDirectory() as temp_name, mock.patch.object(
            foundation_helpers, "GEOMETRY_DIR", Path(temp_name) / "not-installed"
        ), mock.patch.object(
            foundation_helpers, "is_cloud_mode", return_value=True
        ), mock.patch.object(
            foundation_helpers, "read_artifact_bytes", side_effect=artifact_bytes
        ):
            frame = foundation_helpers.load_global_countries_frame()

        self.assertEqual(["USA"], frame["loc_id"].tolist())
        self.assertEqual(["geometry/global/exact/admin_0.parquet"], requested)

    def test_local_display_frame_prefers_display_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "admin0").mkdir()
            pd.DataFrame([{"loc_id": "DSP", "name": "Display"}]).to_parquet(
                root / "admin0" / "display.parquet",
                index=False,
            )
            with mock.patch.object(foundation_helpers, "GEOMETRY_DIR", root):
                frame = foundation_helpers.load_global_country_display_frame()

        self.assertEqual(["DSP"], frame["loc_id"].tolist())

    def test_missing_display_frame_does_not_fall_back_to_exact_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "admin0").mkdir()
            pd.DataFrame([{"loc_id": "EXACT", "name": "Exact"}]).to_parquet(
                root / "admin0" / "full.parquet", index=False,
            )
            with mock.patch.object(
                foundation_helpers, "GEOMETRY_DIR", root
            ), mock.patch.object(
                foundation_helpers, "is_cloud_mode", return_value=False
            ), mock.patch.object(
                foundation_helpers, "load_global_countries_frame",
                side_effect=AssertionError("display loader must fail closed"),
            ):
                frame = foundation_helpers.load_global_country_display_frame()

        self.assertIsNone(frame)

    def test_exact_global_frame_does_not_use_display_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "admin0").mkdir()
            pd.DataFrame([{"loc_id": "DSP", "name": "Display"}]).to_parquet(
                root / "admin0" / "display.parquet",
                index=False,
            )
            pd.DataFrame([{"loc_id": "EXACT", "name": "Exact"}]).to_parquet(
                root / "admin0" / "full.parquet", index=False,
            )
            with mock.patch.object(foundation_helpers, "GEOMETRY_DIR", root):
                frame = foundation_helpers.load_global_countries_frame()

        self.assertEqual(["EXACT"], frame["loc_id"].tolist())

    def test_exact_global_frame_prefers_admin0_full_parquet(self) -> None:
        from shapely.geometry import Point

        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "admin0").mkdir()
            pd.DataFrame([{
                "candidate_id": "FULL~primary",
                "loc_id": "FULL",
                "name": "Full",
                "source_kind": "global_full",
                "geometry_wkb": Point(0, 0).buffer(1).wkb,
            }]).to_parquet(root / "admin0" / "full.parquet", index=False)
            with mock.patch.object(foundation_helpers, "GEOMETRY_DIR", root):
                frame = foundation_helpers.load_global_countries_frame()

        self.assertEqual(["FULL"], frame["loc_id"].tolist())
        self.assertIn("geometry", frame.columns)


if __name__ == "__main__":
    unittest.main()
