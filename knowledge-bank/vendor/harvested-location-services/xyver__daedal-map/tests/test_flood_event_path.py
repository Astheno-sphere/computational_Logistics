from pathlib import Path
import unittest
from unittest.mock import patch

from mapmover.duckdb_helpers import resolve_flood_events_path


class FloodEventPathTests(unittest.TestCase):
    def test_cloud_path_uses_canonical_published_object(self):
        with patch("mapmover.duckdb_helpers.is_cloud_mode", return_value=True):
            result = resolve_flood_events_path(Path("/data/global"))

        self.assertEqual(
            result,
            Path("/data/global/disasters/floods/events.parquet"),
        )


if __name__ == "__main__":
    unittest.main()
