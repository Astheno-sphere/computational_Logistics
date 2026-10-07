from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mapmover import duckdb_helpers, foundation_helpers
from mapmover.runtime import geometry_loader
from mapmover.runtime.read_posture import geometry_read_mode
from mapmover.runtime_config import (
    force_remote_data_reads,
    get_data_plane_mode,
    get_runtime_config,
    set_local_data_plane_mode,
)


class LocalDataPlaneRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_mode = get_data_plane_mode()

    def tearDown(self) -> None:
        set_local_data_plane_mode(self.previous_mode)
        foundation_helpers.clear_foundation_helper_cache()

    def test_cloud_override_changes_reads_without_changing_deployment_config(self) -> None:
        configured_runtime_mode = get_runtime_config()["runtime_mode"]
        set_local_data_plane_mode("cloud")

        self.assertEqual("cloud", get_data_plane_mode())
        self.assertEqual(configured_runtime_mode, get_runtime_config()["runtime_mode"])
        self.assertTrue(force_remote_data_reads())
        self.assertTrue(duckdb_helpers.is_cloud_mode())
        self.assertEqual("runtime", geometry_read_mode())

        set_local_data_plane_mode("local")
        self.assertFalse(force_remote_data_reads())
        self.assertFalse(duckdb_helpers.is_cloud_mode())

    def test_cloud_override_does_not_accept_an_existing_local_parquet_as_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "installed.parquet"
            path.write_bytes(b"local")
            set_local_data_plane_mode("cloud")
            with patch.object(geometry_loader, "parquet_columns", return_value={"loc_id"}) as columns:
                self.assertTrue(geometry_loader.parquet_accessible(path))

        columns.assert_called_once_with(path)

    def test_cloud_override_ignores_an_installed_country_crosswalk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            country_root = Path(temp_name)
            local_path = country_root / "USA" / "crosswalk.json"
            local_path.parent.mkdir(parents=True)
            local_path.write_text('{"source": "local"}', encoding="utf-8")
            set_local_data_plane_mode("cloud")
            foundation_helpers.clear_foundation_helper_cache()
            with patch.object(
                foundation_helpers, "COUNTRY_GEOMETRY_DIR", country_root
            ), patch.object(
                foundation_helpers, "read_artifact_json", return_value={"source": "cloud"}
            ) as cloud_read:
                payload = foundation_helpers.load_country_crosswalk("USA")

        self.assertEqual({"source": "cloud"}, payload)
        cloud_read.assert_called_once_with("geometry/countries/USA/crosswalk.json", lane="published")


if __name__ == "__main__":
    unittest.main()
