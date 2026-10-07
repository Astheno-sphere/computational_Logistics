import unittest

from mapmover.runtime.orchestrator_helper_runtime import (
    apply_runtime_result_cap_to_payload_result,
)
from mapmover.runtime.result_cap import merge_cap_info


class ConfirmedOrderCapGateTests(unittest.TestCase):
    def test_runtime_cap_preserves_precap_display_feature_count(self):
        result = {
            "type": "data",
            "source_id": "demo_source",
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "id": f"f-{idx}", "properties": {"loc_id": f"loc-{idx}"}}
                    for idx in range(6000)
                ],
            },
            "summary": "demo",
            "count": 6000,
        }

        capped = apply_runtime_result_cap_to_payload_result(
            result,
            confirmed_order={"items": [{"source_id": "demo_source"}]},
            load_source_metadata_func=lambda _source_id: {"source_id": "demo_source"},
        )

        self.assertEqual(capped.get("_precap_display_feature_count"), 6000)
        self.assertTrue(capped.get("truncated"))
        self.assertEqual((capped.get("cap_info") or {}).get("available_rows"), 6000)
        self.assertEqual(len((capped.get("geojson") or {}).get("features") or []), 5000)

    def test_merge_cap_info_preserves_cap_kind(self):
        merged = merge_cap_info(
            {
                "cap_hit": True,
                "returned_rows": 5000,
                "available_rows": 265922,
                "cap_value": 5000,
                "cap_reason": "runtime.default_render_cap",
                "cap_kind": "technical_truncation",
            },
            {
                "cap_hit": True,
                "returned_rows": 0,
                "available_rows": 83170,
                "cap_value": 0,
                "cap_reason": "display_warning_gate",
                "cap_kind": "display_warning",
            },
        )

        self.assertEqual(merged.get("cap_kind"), "display_warning")
        self.assertEqual(merged.get("available_rows"), 349092)


if __name__ == "__main__":
    unittest.main()
