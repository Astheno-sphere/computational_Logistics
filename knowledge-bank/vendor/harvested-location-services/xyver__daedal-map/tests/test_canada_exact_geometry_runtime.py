from __future__ import annotations

import os
import unittest
from unittest import mock

from mapmover.runtime import canada_exact_geometry


class _Connection:
    def close(self) -> None:
        pass


class CanadaExactGeometryTests(unittest.TestCase):
    def test_adoption_flag_is_explicit(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CANADA_QUERY_EXACT_ENABLED", None)
            self.assertFalse(canada_exact_geometry.canada_query_exact_enabled())
        with mock.patch.dict(os.environ, {"CANADA_QUERY_EXACT_ENABLED": "true"}, clear=False):
            self.assertTrue(canada_exact_geometry.canada_query_exact_enabled())

    def test_exact_result_preserves_complete_admin_chain(self) -> None:
        loc_ids = [
            "CAN", "CAN-BC", "CAN-BC-5931", "CAN-BC-5931-021",
            "CAN-BC-5931-021-0221", "CAN-BC-5931-021-0221-067",
        ]

        def match(_connection, points, level, _province):
            self.assertEqual(len(points), 1)
            return {0: {
                "component_row_id": level,
                "loc_id": loc_ids[level],
                "parent_id": loc_ids[level - 1] if level else None,
                "admin_level": level,
                "name": None,
                "source_system": "statistics_canada",
                "source_vintage": "statcan_cbf_2021",
                "source_id": loc_ids[level],
            }}

        names = [{"loc_id": loc_id, "name": loc_id} for loc_id in loc_ids]
        with mock.patch.object(
            canada_exact_geometry, "lease_query_connection", return_value=_Connection()
        ), mock.patch.object(
            canada_exact_geometry, "_match_partition", side_effect=match
        ), mock.patch(
            "mapmover.runtime.reference_graph.identities", return_value=names
        ):
            result = canada_exact_geometry.resolve_canada_query_exact_points(
                [{"lon": -122.95, "lat": 49.96}], target_admin_level=5,
            )[0]

        self.assertEqual(result["matched"]["loc_id"], loc_ids[-1])
        self.assertEqual([row["loc_id"] for row in result["stack"]], loc_ids)
        self.assertEqual(result["resolution_fidelity"], "query_exact_predicate_components")


if __name__ == "__main__":
    unittest.main()
