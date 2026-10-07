import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover.runtime.geometry_loader import (
    resolve_country_admin_spine_source,
    resolve_country_display_geometry_sources,
    resolve_country_display_release,
    resolve_country_geometry_source,
)


class GeometryLoaderRuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        resolve_country_display_release.cache_clear()

    def test_admin_spine_source_uses_shared_catalog_layout_root(self):
        root = Path("geometry/countries/USA/admin_spine/exact/usa_geometry_1_0_0")
        with patch("mapmover.runtime.admin_spine_query.layout_root", return_value=root):
            source = resolve_country_admin_spine_source("usa")

        self.assertEqual(root / "admin_0_3.parquet", source)

    def test_geometry_source_prefers_active_exact_release_projection(self):
        exact = Path(
            "geometry/countries/USA/admin_spine/exact/"
            "usa_geometry_1_0_0/admin_0_3.parquet"
        )
        with patch(
            "mapmover.runtime.geometry_loader.resolve_country_admin_spine_source",
            return_value=exact,
        ), patch(
            "mapmover.runtime.geometry_loader.parquet_accessible",
            side_effect=lambda path: path == exact,
        ), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk",
            return_value=None,
        ):
            resolved = resolve_country_geometry_source("USA", admin_level=2)

        self.assertEqual("authority_spine", resolved["source_kind"])
        self.assertEqual(exact, resolved["parquet_file"])

    def test_display_release_follows_country_index_and_semver_manifest(self):
        index = {
            "release_unit": {"id": "USA", "kind": "country"},
            "current": {"manifest": {
                "path": "geometry/countries/USA/releases/1.0.0/manifest.json",
            }},
        }
        manifest = {
            "release_unit": {"id": "USA", "kind": "country"},
            "runtime": {"display": "geometry/countries/USA/admin_spine/display/usa_display_1_0_0_web_v1/"},
            "objects": [{"sha256": "a" * 64, "size_bytes": 123, "source_paths": [
                "geometry/countries/USA/admin_spine/display/usa_display_1_0_0_web_v1/admin_0_3.parquet",
            ]}],
        }
        with patch(
            "mapmover.runtime.geometry_loader._read_active_json",
            side_effect=[index, manifest],
        ):
            paths = resolve_country_display_geometry_sources("usa", admin_level=2)

        self.assertEqual(1, len(paths))
        self.assertTrue(str(paths[0]).endswith("admin_spine\\display\\usa_display_1_0_0_web_v1\\admin_0_3.parquet"))

    def test_display_release_uses_only_contained_release_controls(self):
        index = {
            "release_unit": {"id": "USA", "kind": "country"},
            "current": {"manifest": {
                "path": "geometry/countries/USA/releases/1.0.0/manifest.json",
            }},
        }
        manifest = {
            "release_unit": {"id": "USA", "kind": "country"},
            "runtime": {"display": "geometry/countries/USA/admin_spine/display/usa_display_1_0_0_web_v1/"},
            "objects": [{"source_paths": [
                "geometry/countries/USA/admin_spine/display/usa_display_1_0_0_web_v1/admin_0_3.parquet",
            ]}],
        }
        with patch("mapmover.runtime.geometry_loader._read_active_json", side_effect=[index, manifest]) as reader:
            release = resolve_country_display_release("USA")
        self.assertEqual("usa_display_1_0_0_web_v1", release["release_id"])
        self.assertEqual(index, release["pointer"])
        self.assertEqual(2, reader.call_count)

    def test_display_release_rejects_artifact_outside_immutable_root(self):
        index = {
            "release_unit": {"id": "USA", "kind": "country"},
            "current": {"manifest": {
                "path": "geometry/countries/USA/releases/1.0.0/manifest.json",
            }},
        }
        manifest = {
            "release_unit": {"id": "USA", "kind": "country"},
            "runtime": {"display": "geometry/countries/USA/admin_spine/display/usa_display_1_0_0_web_v1/"},
            "objects": [{"source_paths": [
                "geometry/countries/USA/admin_spine/admin_0_3.parquet",
            ]}],
        }
        with patch(
            "mapmover.runtime.geometry_loader._read_active_json",
            side_effect=[index, manifest],
        ):
            self.assertIsNone(resolve_country_display_release("USA"))

    def test_prefers_shared_authority_spine_for_admin2(self):
        with patch(
            "mapmover.runtime.geometry_loader.resolve_country_admin_spine_source",
            return_value=Path("geometry/countries/USA/admin_spine/admin_0_3.parquet"),
        ), patch(
            "mapmover.runtime.geometry_loader.parquet_accessible",
            side_effect=lambda path: str(path).endswith(
                "geometry\\countries\\USA\\admin_spine\\admin_0_3.parquet"
            ),
        ), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk",
            return_value={"mappings": {"USA-VA": "USA-G125186"}},
        ):
            resolved = resolve_country_geometry_source("USA", admin_level=2)

        self.assertEqual(resolved["source_kind"], "authority_spine")
        self.assertTrue(
            str(resolved["parquet_file"]).endswith(
                "geometry\\countries\\USA\\admin_spine\\admin_0_3.parquet"
            )
        )
        self.assertFalse(resolved["uses_crosswalk"])

    def test_prefers_shared_authority_spine_for_unfiltered_country_load(self):
        with patch(
            "mapmover.runtime.geometry_loader.resolve_country_admin_spine_source",
            return_value=Path("geometry/countries/CAN/admin_spine/admin_0_3.parquet"),
        ), patch(
            "mapmover.runtime.geometry_loader.parquet_accessible",
            side_effect=lambda path: str(path).endswith(
                "geometry\\countries\\CAN\\admin_spine\\admin_0_3.parquet"
            ),
        ), patch("mapmover.runtime.geometry_loader.load_country_crosswalk", return_value=None):
            resolved = resolve_country_geometry_source("can")

        self.assertEqual(resolved["source_kind"], "authority_spine")

    def test_deeper_admin_level_does_not_use_admin_0_3_spine(self):
        def accessible(path: Path | None) -> bool:
            return str(path).endswith("geometry\\countries\\CAN\\geometry.parquet")

        with patch("mapmover.runtime.geometry_loader.parquet_accessible", side_effect=accessible), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk", return_value=None
        ):
            resolved = resolve_country_geometry_source("CAN", admin_level=4)

        self.assertEqual(resolved["source_kind"], "country_base")

    def test_prefers_country_geometry_base_before_crosswalk_fallback(self):
        def accessible(path: Path | None) -> bool:
            text = str(path)
            return text.endswith("geometry\\countries\\GBR\\geometry.parquet")

        with patch("mapmover.runtime.geometry_loader.parquet_accessible", side_effect=accessible), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk",
            return_value={"mappings": {"FRA-IDF": "FRA-GEO"}},
        ):
            resolved = resolve_country_geometry_source("GBR")

        self.assertEqual(resolved["source_kind"], "country_base")
        self.assertTrue(str(resolved["parquet_file"]).endswith("geometry\\countries\\GBR\\geometry.parquet"))
        self.assertFalse(resolved["uses_crosswalk"])

    def test_uses_crosswalk_base_when_local_geometry_missing(self):
        def accessible(path: Path | None) -> bool:
            text = str(path)
            return text.endswith("geometry\\USA.parquet")

        crosswalk = {"mappings": {"USA-VA": "USA-G125186"}}
        with patch("mapmover.runtime.geometry_loader.parquet_accessible", side_effect=accessible), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk",
            return_value=crosswalk,
        ):
            resolved = resolve_country_geometry_source("USA")

        self.assertEqual(resolved["source_kind"], "crosswalk_base")
        self.assertTrue(str(resolved["parquet_file"]).endswith("geometry\\USA.parquet"))
        self.assertTrue(resolved["uses_crosswalk"])
        self.assertEqual(resolved["crosswalk"], crosswalk)

    def test_uses_global_base_when_crosswalk_missing(self):
        def accessible(path: Path | None) -> bool:
            text = str(path)
            return text.endswith("geometry\\BRA.parquet")

        with patch("mapmover.runtime.geometry_loader.parquet_accessible", side_effect=accessible), patch(
            "mapmover.runtime.geometry_loader.load_country_crosswalk",
            return_value=None,
        ):
            resolved = resolve_country_geometry_source("BRA")

        self.assertEqual(resolved["source_kind"], "global_base")
        self.assertTrue(str(resolved["parquet_file"]).endswith("geometry\\BRA.parquet"))
        self.assertFalse(resolved["uses_crosswalk"])


if __name__ == "__main__":
    unittest.main()
