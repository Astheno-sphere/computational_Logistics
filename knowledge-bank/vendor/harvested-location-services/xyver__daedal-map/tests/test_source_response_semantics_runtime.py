from __future__ import annotations

import unittest

from mapmover.runtime.source_response_semantics import (
    append_source_caveats,
    collect_metric_availability,
    collect_metric_availability_warnings,
    collect_metric_caveats,
    collect_metric_response_obligations,
)
from mapmover.runtime.postprocess_validation import _should_enforce_event_count_intent


class SourceResponseSemanticsRuntimeTests(unittest.TestCase):
    def test_selected_metric_adds_its_required_source_caveat(self) -> None:
        items = [{"_valid": True, "source_id": "tsunamis_events", "metric": "max_water_height_m"}]
        metadata = {
            "metrics": {
                "max_water_height_m": {
                    "response_semantics": {
                        "required_framing": "Reported local water-height observations are not necessarily open-ocean wave heights."
                    }
                }
            }
        }

        caveats = collect_metric_caveats(items, load_source_metadata_func=lambda _source_id: metadata)

        self.assertEqual(caveats, ["Reported local water-height observations are not necessarily open-ocean wave heights."])
        self.assertEqual(items[0]["source_caveats"], caveats)
        self.assertEqual(
            append_source_caveats("Showing tsunami events.", caveats),
            "Showing tsunami events. Reported local water-height observations are not necessarily open-ocean wave heights.",
        )

    def test_unselected_metric_does_not_add_a_caveat(self) -> None:
        items = [{"_valid": True, "source_id": "tsunamis_events", "metric": "event_count"}]
        metadata = {
            "metrics": {
                "max_water_height_m": {
                    "response_semantics": {"required_framing": "A caveat."}
                }
            }
        }

        self.assertEqual(collect_metric_caveats(items, load_source_metadata_func=lambda _source_id: metadata), [])

    def test_selected_metric_projects_response_obligation(self) -> None:
        metadata = {
            "metrics": {
                "max_water_height_m": {
                    "response_semantics": {
                        "canonical_term": "reported local water height or runup observation",
                        "required_framing": "These values are reported local observations.",
                        "avoid_unqualified_terms": ["wave height"],
                        "accepted_framing_terms_any": ["reported local"],
                    }
                },
                "event_count": {},
            }
        }

        obligations = collect_metric_response_obligations(
            "tsunamis_events",
            ["event_count", "max_water_height_m"],
            load_source_metadata_func=lambda _source_id: metadata,
        )

        self.assertEqual(len(obligations), 1)
        self.assertEqual(obligations[0]["source_id"], "tsunamis_events")
        self.assertEqual(obligations[0]["metric"], "max_water_height_m")
        self.assertEqual(obligations[0]["canonical_term"], "reported local water height or runup observation")
        self.assertEqual(obligations[0]["required_framing"], "These values are reported local observations.")
        self.assertEqual(obligations[0]["avoid_unqualified_terms"], ["wave height"])

    def test_metric_availability_warns_when_requested_time_is_outside_metric_years(self) -> None:
        metadata = {
            "metrics": {
                "internet_users": {
                    "years": [2000, 2019],
                    "countries": 236,
                    "density": 0.386,
                }
            }
        }

        availability = collect_metric_availability(
            "world_factbook",
            ["internet_users"],
            load_source_metadata_func=lambda _source_id: metadata,
        )
        warnings = collect_metric_availability_warnings(availability, {"value": 2025})

        self.assertEqual(
            availability["internet_users"],
            {"start": 2000, "end": 2019, "years": [2000, 2019], "countries": 236, "density": 0.386},
        )
        self.assertEqual(warnings[0]["code"], "requested_time_outside_metric_availability")
        self.assertEqual(warnings[0]["metrics"][0]["metric"], "internet_users")
        self.assertEqual(warnings[0]["metrics"][0]["available_end"], 2019)

    def test_plain_event_listing_overrides_an_unrelated_model_metric(self) -> None:
        metadata = {"routing_hints": {"metric_aliases": {"events": "event_count", "deaths": "deaths"}}}
        self.assertTrue(_should_enforce_event_count_intent("Show tsunami events since 2000", metadata, "event_count"))
        self.assertFalse(_should_enforce_event_count_intent("Show tsunami events and deaths since 2000", metadata, "event_count"))


if __name__ == "__main__":
    unittest.main()
