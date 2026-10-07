import json
import unittest
from pathlib import Path

from mapmover.runtime.grid_loc_id_resolution import (
    aggregate_grid_to_loc_ids,
    build_centered_grid_cell_rows,
    build_regular_grid_cell_rows,
    build_grid_target_overlaps,
    classify_grid_target_loc_id,
    is_eez_loc_id,
    is_water_body_loc_id,
    normalize_overlap_weights,
    project_loc_id_metrics_to_grid,
    resolve_point_to_grid_cells,
)


class GridLocIdResolutionRuntimeTests(unittest.TestCase):
    def test_build_regular_grid_cell_rows(self):
        rows = build_regular_grid_cell_rows(
            west=0.0,
            south=0.0,
            east=2.0,
            north=1.0,
            width=2,
            height=1,
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["bbox"], [0.0, 0.0, 1.0, 1.0])
        self.assertEqual(rows[1]["bbox"], [1.0, 0.0, 2.0, 1.0])

    def test_rejects_invalid_regular_grid_dimensions_and_bounds(self):
        with self.assertRaisesRegex(ValueError, "positive integers"):
            build_regular_grid_cell_rows(
                west=0.0, south=0.0, east=1.0, north=1.0, width=0, height=1
            )
        with self.assertRaisesRegex(ValueError, "east>west"):
            build_regular_grid_cell_rows(
                west=1.0, south=0.0, east=0.0, north=1.0, width=1, height=1
            )

    def test_build_centered_grid_cell_rows(self):
        rows = build_centered_grid_cell_rows(
            [{"cell_id": "a", "lon": 10.0, "lat": 20.0}],
            cell_width_deg=2.0,
            cell_height_deg=4.0,
        )
        self.assertEqual(rows[0]["bbox"], [9.0, 18.0, 11.0, 22.0])

    def test_centered_grid_rejects_unnormalized_and_wrapping_coordinates(self):
        with self.assertRaisesRegex(ValueError, "normalized EPSG:4326"):
            build_centered_grid_cell_rows(
                [{"cell_id": "zero-to-360", "lon": 359.875, "lat": 0.0}],
                cell_width_deg=0.25,
                cell_height_deg=0.25,
            )
        with self.assertRaisesRegex(ValueError, "antimeridian"):
            build_centered_grid_cell_rows(
                [{"cell_id": "wraps", "lon": 179.9, "lat": 0.0}],
                cell_width_deg=1.0,
                cell_height_deg=1.0,
            )
        with self.assertRaisesRegex(ValueError, "latitude domain"):
            build_centered_grid_cell_rows(
                [{"cell_id": "polar", "lon": 0.0, "lat": 89.9}],
                cell_width_deg=0.25,
                cell_height_deg=1.0,
            )

    def test_registration_changes_cell_footprint(self):
        center = build_centered_grid_cell_rows(
            [{"cell_id": "center", "lon": 10.0, "lat": 20.0}],
            cell_width_deg=2.0,
            cell_height_deg=2.0,
        )[0]
        upper_left = build_centered_grid_cell_rows(
            [{"cell_id": "edge", "lon": 10.0, "lat": 20.0}],
            cell_width_deg=2.0,
            cell_height_deg=2.0,
            registration="upper_left",
        )[0]
        self.assertEqual(center["bbox"], [9.0, 19.0, 11.0, 21.0])
        self.assertEqual(upper_left["bbox"], [10.0, 18.0, 12.0, 20.0])
        self.assertNotEqual(center["bbox"], upper_left["bbox"])

    def test_zero_to_360_and_antimeridian_split_are_explicit(self):
        rows = build_centered_grid_cell_rows(
            [{"cell_id": "wrapped", "lon": 359.875, "lat": 0.0}],
            cell_width_deg=0.5,
            cell_height_deg=0.5,
            longitude_domain="0_360",
            antimeridian_policy="split",
        )
        self.assertEqual(rows[0]["center_lon"], -0.125)
        self.assertEqual(rows[0]["longitude_domain"], "-180_180")

        date_line = build_centered_grid_cell_rows(
            [{"cell_id": "date-line", "lon": 179.875, "lat": 0.0}],
            cell_width_deg=0.5,
            cell_height_deg=0.5,
            antimeridian_policy="split",
        )
        overlaps = build_grid_target_overlaps(
            date_line,
            [
                {"loc_id": "XOP", "bbox": [179.0, -1.0, 180.0, 1.0]},
                {"loc_id": "EEZ-USA", "bbox": [-180.0, -1.0, -179.0, 1.0]},
            ],
            area_method="geodesic",
        )
        self.assertEqual(set(overlaps["loc_id"]), {"XOP", "EEZ-USA"})
        self.assertAlmostEqual(float(overlaps["cell_fraction"].sum()), 1.0, places=6)

    def test_polar_coordinate_rows_require_explicit_clipping(self):
        row = build_centered_grid_cell_rows(
            [{"cell_id": "north-pole", "lon": 0.0, "lat": 90.0}],
            cell_width_deg=0.25,
            cell_height_deg=0.25,
            latitude_boundary_policy="clip",
        )[0]
        self.assertEqual(row["bbox"], [-0.125, 89.875, 0.125, 90.0])

    def test_geodesic_area_is_smaller_near_pole(self):
        overlaps = build_grid_target_overlaps(
            [
                {"cell_id": "equator", "bbox": [0.0, 0.0, 1.0, 1.0]},
                {"cell_id": "polar", "bbox": [0.0, 80.0, 1.0, 81.0]},
            ],
            [
                {"loc_id": "USA", "bbox": [0.0, 0.0, 1.0, 1.0]},
                {"loc_id": "XOP", "bbox": [0.0, 80.0, 1.0, 81.0]},
            ],
            area_method="geodesic",
        ).set_index("cell_id")
        self.assertGreater(
            float(overlaps.loc["equator", "overlap_area"]),
            5.0 * float(overlaps.loc["polar", "overlap_area"]),
        )
        self.assertAlmostEqual(float(overlaps.loc["equator", "cell_fraction"]), 1.0, places=6)

    def test_projected_and_irregular_cells_use_explicit_geometry(self):
        # These coordinates deliberately represent a projected planar space,
        # not degrees.  A triangular/curvilinear source cell is accepted when
        # its actual footprint is supplied instead of pretending it is a bbox.
        cells = [
            {
                "cell_id": "irregular",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [2000, 0], [0, 1000], [0, 0]]],
                },
            }
        ]
        overlaps = build_grid_target_overlaps(
            cells,
            [{"loc_id": "USA", "bbox": [0, 0, 1000, 1000]}],
            area_method="planar",
        )
        self.assertEqual(len(overlaps), 1)
        self.assertAlmostEqual(float(overlaps.iloc[0]["cell_fraction"]), 0.75, places=6)

    def test_point_lookup_exposes_shared_boundary(self):
        cells = build_regular_grid_cell_rows(
            west=0.0, south=0.0, east=2.0, north=1.0, width=2, height=1
        )
        self.assertEqual(
            resolve_point_to_grid_cells(cells, lon=1.0, lat=0.5),
            ["cell_0_0", "cell_0_1"],
        )
        self.assertEqual(
            resolve_point_to_grid_cells(cells, lon=1.0, lat=0.5, boundary_policy="lowest_id"),
            ["cell_0_0"],
        )
        with self.assertRaisesRegex(ValueError, "shared cell boundary"):
            resolve_point_to_grid_cells(cells, lon=1.0, lat=0.5, boundary_policy="error")

    def test_classifies_admin_and_water_body_targets(self):
        self.assertEqual(classify_grid_target_loc_id("USA-VA-059"), "admin_2")
        self.assertEqual(classify_grid_target_loc_id("XOP"), "water_body")
        self.assertTrue(is_water_body_loc_id("XOP"))
        self.assertFalse(is_water_body_loc_id("USA"))

    def test_classifies_eez_marine_targets(self):
        # EEZ is a marine overlay namespace: a valid grid target, distinct from
        # both the admin spine and the X* water bodies.
        self.assertEqual(classify_grid_target_loc_id("EEZ-USA"), "marine_eez")
        self.assertEqual(classify_grid_target_loc_id("EEZ-ASM"), "marine_eez")
        self.assertEqual(classify_grid_target_loc_id("EEZ-MRGID-21801"), "marine_eez")
        self.assertTrue(is_eez_loc_id("EEZ-USA"))
        self.assertTrue(is_eez_loc_id("USA-EEZ-MRGID-8456"))
        self.assertTrue(is_eez_loc_id("XOP-EEZ-MRGID-8456"))
        self.assertFalse(is_eez_loc_id("USA"))
        self.assertFalse(is_eez_loc_id("XOP"))

    def test_classifies_regional_base_targets_through_shared_spine(self):
        self.assertEqual(classify_grid_target_loc_id("DEU-DE2"), "admin_1")
        self.assertEqual(classify_grid_target_loc_id("DEU-DE27"), "admin_2")
        self.assertEqual(classify_grid_target_loc_id("DEU-DE27C"), "admin_3")

    def test_build_grid_target_overlaps_accepts_eez_target(self):
        cell_rows = [{"cell_id": "c1", "bbox": [0.0, 0.0, 1.0, 1.0]}]
        target_rows = [{"loc_id": "EEZ-USA", "bbox": [0.0, 0.0, 1.0, 1.0]}]
        overlaps = build_grid_target_overlaps(cell_rows, target_rows)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(str(overlaps.iloc[0]["target_kind"]), "marine_eez")

    def test_build_grid_target_overlaps_from_bboxes(self):
        cell_rows = [
            {"cell_id": "c1", "bbox": [0.0, 0.0, 1.0, 1.0]},
            {"cell_id": "c2", "bbox": [1.0, 0.0, 2.0, 1.0]},
        ]
        target_rows = [
            {"loc_id": "USA-VA-059", "bbox": [0.0, 0.0, 1.5, 1.0]},
            {"loc_id": "XOP", "bbox": [1.5, 0.0, 2.0, 1.0]},
        ]
        overlaps = build_grid_target_overlaps(cell_rows, target_rows)
        self.assertEqual(len(overlaps), 3)

        fairfax_c1 = overlaps[(overlaps["cell_id"] == "c1") & (overlaps["loc_id"] == "USA-VA-059")].iloc[0]
        self.assertAlmostEqual(float(fairfax_c1["cell_fraction"]), 1.0, places=6)

        fairfax_c2 = overlaps[(overlaps["cell_id"] == "c2") & (overlaps["loc_id"] == "USA-VA-059")].iloc[0]
        pacific_c2 = overlaps[(overlaps["cell_id"] == "c2") & (overlaps["loc_id"] == "XOP")].iloc[0]
        self.assertAlmostEqual(float(fairfax_c2["cell_fraction"]), 0.5, places=6)
        self.assertAlmostEqual(float(pacific_c2["cell_fraction"]), 0.5, places=6)
        self.assertEqual(str(pacific_c2["target_kind"]), "water_body")

    def test_rejects_duplicate_cell_ids_before_overlap(self):
        cells = [
            {"cell_id": "duplicate", "bbox": [0.0, 0.0, 1.0, 1.0]},
            {"cell_id": "duplicate", "bbox": [1.0, 0.0, 2.0, 1.0]},
        ]
        targets = [{"loc_id": "USA-VA-059", "bbox": [0.0, 0.0, 2.0, 1.0]}]
        with self.assertRaisesRegex(ValueError, "Duplicate cell_id"):
            build_grid_target_overlaps(cells, targets)

    def test_aggregate_grid_to_loc_ids_weighted(self):
        cell_rows = [
            {"cell_id": "c1", "timestamp": "2026-06-01", "sst_c": 10.0},
            {"cell_id": "c2", "timestamp": "2026-06-01", "sst_c": 20.0},
        ]
        overlap_rows = [
            {"cell_id": "c1", "loc_id": "USA-VA-059", "cell_fraction": 1.0},
            {"cell_id": "c2", "loc_id": "USA-VA-059", "cell_fraction": 0.5},
            {"cell_id": "c2", "loc_id": "XOP", "cell_fraction": 0.5},
        ]
        out = aggregate_grid_to_loc_ids(
            cell_rows,
            overlap_rows,
            metric_columns=["sst_c"],
            time_columns=["timestamp"],
        )
        fairfax = out[out["loc_id"] == "USA-VA-059"].iloc[0]
        pacific = out[out["loc_id"] == "XOP"].iloc[0]
        self.assertAlmostEqual(float(fairfax["sst_c"]), (10.0 * 1.0 + 20.0 * 0.5) / 1.5, places=6)
        self.assertAlmostEqual(float(pacific["sst_c"]), 20.0, places=6)

    def test_aggregate_grid_to_loc_ids_supports_weighted_stats(self):
        cell_rows = [
            {"cell_id": "c1", "timestamp": "2026-06-01", "sst_c": 10.0},
            {"cell_id": "c2", "timestamp": "2026-06-01", "sst_c": 20.0},
            {"cell_id": "c3", "timestamp": "2026-06-01", "sst_c": 30.0},
        ]
        overlap_rows = [
            {"cell_id": "c1", "loc_id": "XOP", "cell_fraction": 1.0},
            {"cell_id": "c2", "loc_id": "XOP", "cell_fraction": 2.0},
            {"cell_id": "c3", "loc_id": "XOP", "cell_fraction": 1.0},
        ]
        out = aggregate_grid_to_loc_ids(
            cell_rows,
            overlap_rows,
            metric_columns=["sst_c"],
            time_columns=["timestamp"],
            metric_stats={"sst_c": ["min", "max", "p05", "p50", "p95"]},
        )
        pacific = out[out["loc_id"] == "XOP"].iloc[0]
        self.assertAlmostEqual(float(pacific["sst_c"]), 20.0, places=6)
        self.assertAlmostEqual(float(pacific["sst_c__min"]), 10.0, places=6)
        self.assertAlmostEqual(float(pacific["sst_c__max"]), 30.0, places=6)
        self.assertAlmostEqual(float(pacific["sst_c__p05"]), 10.0, places=6)
        self.assertAlmostEqual(float(pacific["sst_c__p50"]), 20.0, places=6)
        self.assertAlmostEqual(float(pacific["sst_c__p95"]), 30.0, places=6)

    def test_aggregate_grid_to_loc_ids_supports_weighted_sum(self):
        cell_rows = [
            {"cell_id": "c1", "timestamp": "2026-06-01", "people": 100.0},
            {"cell_id": "c2", "timestamp": "2026-06-01", "people": 80.0},
        ]
        overlap_rows = [
            {"cell_id": "c1", "loc_id": "USA-VA-059", "cell_fraction": 0.25},
            {"cell_id": "c2", "loc_id": "USA-VA-059", "cell_fraction": 0.50},
        ]
        out = aggregate_grid_to_loc_ids(
            cell_rows,
            overlap_rows,
            metric_columns=["people"],
            time_columns=["timestamp"],
            metric_aggregations={"people": "weighted_sum"},
        )
        fairfax = out[out["loc_id"] == "USA-VA-059"].iloc[0]
        self.assertAlmostEqual(float(fairfax["people"]), 65.0, places=6)

    def test_aggregation_distinguishes_intensive_extensive_and_categorical(self):
        cells = [
            {"cell_id": "c1", "temperature": 10.0, "people": 100.0, "class": "forest"},
            {"cell_id": "c2", "temperature": 20.0, "people": 80.0, "class": "water"},
        ]
        overlaps = [
            {"cell_id": "c1", "loc_id": "USA", "cell_fraction": 1.0},
            {"cell_id": "c2", "loc_id": "USA", "cell_fraction": 0.25},
        ]
        out = aggregate_grid_to_loc_ids(
            cells,
            overlaps,
            metric_columns=["temperature", "people", "class"],
            metric_aggregations={
                "temperature": "area_weighted_mean",
                "people": "weighted_sum",
                "class": "categorical_majority",
            },
        ).iloc[0]
        self.assertAlmostEqual(float(out["temperature"]), 12.0, places=6)
        self.assertAlmostEqual(float(out["people"]), 120.0, places=6)
        self.assertEqual(out["class"], "forest")

    def test_nodata_coverage_is_visible_and_can_propagate(self):
        cells = [
            {"cell_id": "c1", "temperature": 10.0},
            {"cell_id": "c2", "temperature": None},
        ]
        overlaps = [
            {"cell_id": "c1", "loc_id": "USA", "cell_fraction": 0.75},
            {"cell_id": "c2", "loc_id": "USA", "cell_fraction": 0.25},
        ]
        excluded = aggregate_grid_to_loc_ids(
            cells, overlaps, metric_columns=["temperature"]
        ).iloc[0]
        self.assertEqual(float(excluded["temperature"]), 10.0)
        self.assertEqual(float(excluded["temperature__coverage_fraction"]), 0.75)
        propagated = aggregate_grid_to_loc_ids(
            cells, overlaps, metric_columns=["temperature"], nodata_policy="propagate"
        ).iloc[0]
        self.assertIsNone(propagated["temperature"])

    def test_extensive_full_coverage_conserves_source_total(self):
        cells = [
            {"cell_id": "c1", "people": 100.0},
            {"cell_id": "c2", "people": 80.0},
        ]
        overlaps = [
            {"cell_id": "c1", "loc_id": "USA", "cell_fraction": 0.4},
            {"cell_id": "c1", "loc_id": "CAN", "cell_fraction": 0.6},
            {"cell_id": "c2", "loc_id": "USA", "cell_fraction": 1.0},
        ]
        out = aggregate_grid_to_loc_ids(
            cells,
            overlaps,
            metric_columns=["people"],
            metric_aggregations={"people": "weighted_sum"},
        )
        self.assertAlmostEqual(float(out["people"].sum()), 180.0, places=6)

    def test_local_resolution_snapshot_preserves_distinct_lattices(self):
        fixture = Path(__file__).with_name("fixtures") / "raster_grid_resolution_samples.json"
        grids = json.loads(fixture.read_text(encoding="utf-8"))["grids"]
        for grid in grids:
            self.assertEqual(grid["cell_count"], grid["width"] * grid["height"])
        by_id = {grid["grid_id"]: grid for grid in grids}
        alpha = by_id["physical_coastline_v1_alpha_025deg"]
        era5 = by_id["era5_lsm_v1_native_025deg"]
        self.assertEqual(alpha["resolution_deg"], era5["resolution_deg"])
        self.assertNotEqual(alpha["cell_count"], era5["cell_count"])
        self.assertNotEqual(alpha["registration"], era5["registration"])
        ids = [grid["grid_id"] for grid in grids]
        self.assertEqual(len(ids), len(set(ids)))

    def test_installed_local_alpha_headers_match_snapshot_when_available(self):
        workspace = Path(__file__).resolve().parents[2]
        data_root = workspace / "county-map-data" / "geometry" / "masks"
        snapshot_path = Path(__file__).with_name("fixtures") / "raster_grid_resolution_samples.json"
        grids = json.loads(snapshot_path.read_text(encoding="utf-8"))["grids"]
        alpha_grids = [grid for grid in grids if "land_alpha" in grid["artifact"]]
        if not all((data_root.parents[1] / grid["artifact"]).is_file() for grid in alpha_grids):
            self.skipTest("local physical-coastline alpha artifacts are not installed")
        import msgpack

        for expected in alpha_grids:
            path = data_root.parents[1] / expected["artifact"]
            payload = msgpack.unpackb(path.read_bytes(), raw=False)
            with self.subTest(path=path.name):
                self.assertEqual(payload["deg"], expected["resolution_deg"])
                self.assertEqual(payload["width"], expected["width"])
                self.assertEqual(payload["height"], expected["height"])
                self.assertEqual(len(payload["land_alpha"]), expected["cell_count"])
                self.assertEqual(payload["row_order"], expected["row_order"])

    def test_installed_local_era5_headers_match_snapshot_when_available(self):
        workspace = Path(__file__).resolve().parents[2]
        data_root = workspace / "county-map-data"
        snapshot_path = Path(__file__).with_name("fixtures") / "raster_grid_resolution_samples.json"
        grids = json.loads(snapshot_path.read_text(encoding="utf-8"))["grids"]
        era5_grids = [grid for grid in grids if "era5_lsm_v1" in grid["artifact"]]
        if not all((data_root / grid["artifact"]).is_file() for grid in era5_grids):
            self.skipTest("local ERA5 land-mask artifacts are not installed")
        import pyarrow.parquet as pq

        for expected in era5_grids:
            path = data_root / expected["artifact"]
            parquet = pq.ParquetFile(path)
            with self.subTest(path=path.name):
                self.assertEqual(parquet.metadata.num_rows, expected["cell_count"])
                self.assertIn("cell_id", parquet.schema.names)
                self.assertIn("lat", parquet.schema.names)
                self.assertIn("lon", parquet.schema.names)

    def test_normalize_overlap_weights_by_cell(self):
        normalized = normalize_overlap_weights(
            [
                {"cell_id": "c1", "loc_id": "A", "cell_fraction": 0.25},
                {"cell_id": "c1", "loc_id": "B", "cell_fraction": 0.75},
            ],
            group_by="cell",
        )
        self.assertAlmostEqual(float(normalized.iloc[0]["normalized_weight"]), 0.25, places=6)
        self.assertAlmostEqual(float(normalized.iloc[1]["normalized_weight"]), 0.75, places=6)

    def test_rejects_negative_and_nonfinite_overlap_weights(self):
        for invalid in (-0.1, float("inf"), float("nan"), "not-a-number"):
            with self.subTest(invalid=invalid):
                rows = [{"cell_id": "c1", "loc_id": "USA", "cell_fraction": invalid}]
                with self.assertRaisesRegex(ValueError, "cell_fraction"):
                    normalize_overlap_weights(rows)

    def test_aggregation_rejects_negative_overlap_weights(self):
        cells = [{"cell_id": "c1", "value": 10.0}]
        overlaps = [{"cell_id": "c1", "loc_id": "USA", "cell_fraction": -0.5}]
        with self.assertRaisesRegex(ValueError, "cell_fraction"):
            aggregate_grid_to_loc_ids(cells, overlaps, metric_columns=["value"])

    def test_project_loc_id_metrics_to_grid_weighted(self):
        cell_rows = [
            {"cell_id": "c1", "timestamp": "2026-06-01"},
            {"cell_id": "c2", "timestamp": "2026-06-01"},
        ]
        overlap_rows = [
            {"cell_id": "c1", "loc_id": "USA-VA-059", "cell_fraction": 1.0},
            {"cell_id": "c2", "loc_id": "USA-VA-059", "cell_fraction": 0.5},
            {"cell_id": "c2", "loc_id": "XOP", "cell_fraction": 0.5},
        ]
        loc_rows = [
            {"loc_id": "USA-VA-059", "timestamp": "2026-06-01", "risk": 4.0},
            {"loc_id": "XOP", "timestamp": "2026-06-01", "risk": 8.0},
        ]
        projected = project_loc_id_metrics_to_grid(
            cell_rows,
            overlap_rows,
            loc_rows,
            metric_columns=["risk"],
            time_columns=["timestamp"],
        )
        c1 = projected[projected["cell_id"] == "c1"].iloc[0]
        c2 = projected[projected["cell_id"] == "c2"].iloc[0]
        self.assertAlmostEqual(float(c1["risk"]), 4.0, places=6)
        self.assertAlmostEqual(float(c2["risk"]), 6.0, places=6)

    def test_project_loc_id_metrics_to_grid_supports_sum(self):
        cell_rows = [
            {"cell_id": "c2", "timestamp": "2026-06-01"},
        ]
        overlap_rows = [
            {"cell_id": "c2", "loc_id": "USA-VA-059", "cell_fraction": 0.5},
            {"cell_id": "c2", "loc_id": "XOP", "cell_fraction": 0.5},
        ]
        loc_rows = [
            {"loc_id": "USA-VA-059", "timestamp": "2026-06-01", "people": 100.0},
            {"loc_id": "XOP", "timestamp": "2026-06-01", "people": 80.0},
        ]
        projected = project_loc_id_metrics_to_grid(
            cell_rows,
            overlap_rows,
            loc_rows,
            metric_columns=["people"],
            time_columns=["timestamp"],
            metric_aggregations={"people": "sum"},
        )
        self.assertAlmostEqual(float(projected.iloc[0]["people"]), 90.0, places=6)


if __name__ == "__main__":
    unittest.main()
