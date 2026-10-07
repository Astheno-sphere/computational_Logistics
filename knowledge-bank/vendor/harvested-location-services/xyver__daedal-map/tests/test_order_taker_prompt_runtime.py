import unittest
from unittest.mock import patch

from mapmover.runtime.order_taker_prompt import build_system_prompt_body


class OrderTakerPromptRuntimeTests(unittest.TestCase):
    def test_catalog_answers_require_grounded_followups(self):
        catalog = {
            "sources": [
                {
                    "source_id": "wildfires_events",
                    "source_name": "Wildfire Events",
                    "pack_id": "wildfires",
                    "scope": "global",
                    "temporal_coverage": {"start": "1930", "end": "2026"},
                    "geojson_shape": "event_shape",
                    "geographic_level": "event",
                }
            ]
        }
        conversions = {"regional_groupings": {}}
        with patch(
            "mapmover.runtime.order_taker_prompt.load_usa_admin",
            return_value={"state_abbreviations": {}},
        ):
            prompt = build_system_prompt_body(catalog, conversions)

        self.assertIn("2-4 concrete, answerable next questions", prompt)
        self.assertIn("grounded in the", prompt)
        self.assertIn("Do not end with a vague open-ended question", prompt)
        self.assertIn("show the largest wildfires in Canada since 2000", prompt)


if __name__ == "__main__":
    unittest.main()
