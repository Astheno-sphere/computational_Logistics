import unittest
from unittest.mock import patch

from mapmover.runtime.orchestrator_helper_runtime import (
    apply_runtime_result_cap_to_payload_result,
    maybe_build_explainer_chat_response,
    resolve_result_source_id,
)


class OrchestratorHelperRuntimeTests(unittest.TestCase):
    def test_resolve_result_source_id_prefers_top_level_source_id(self):
        self.assertEqual(
            resolve_result_source_id({"source_id": "worldpop", "dataset": "ignored"}),
            "worldpop",
        )

    def test_resolve_result_source_id_falls_back_to_order_item(self):
        self.assertEqual(
            resolve_result_source_id(
                {
                    "order": {
                        "items": [
                            {"source_id": "cejst_classification"},
                        ]
                    }
                }
            ),
            "cejst_classification",
        )

    def test_apply_runtime_result_cap_to_payload_result_uses_shared_cap_contract(self):
        result = {
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"loc_id": f"USA-VA-{idx:03d}"}}
                    for idx in range(5)
                ],
            },
            "source_id": "worldpop",
        }
        confirmed_order = {
            "items": [
                {
                    "sort": {
                        "by": "loc_id",
                        "limit": 2,
                    }
                }
            ]
        }

        capped = apply_runtime_result_cap_to_payload_result(
            result,
            confirmed_order=confirmed_order,
            load_source_metadata_func=lambda _source_id: {
                "runtime": {
                    "default_render_cap": 100,
                    "max_render_cap": 3,
                }
            },
        )

        self.assertTrue(capped["truncated"])
        self.assertEqual(len(capped["geojson"]["features"]), 2)
        self.assertEqual(capped["cap_info"]["available_rows"], 5)
        self.assertEqual(capped["cap_info"]["returned_rows"], 2)
        self.assertEqual(capped["cap_info"]["cap_reason"], "requested_limit")

    def test_maybe_build_explainer_chat_response_uses_shared_explainer_helper(self):
        def load_source_metadata(_source_id):
            return {
                "source_id": "distributed_manufacturing",
                "pack_id": "distributed_manufacturing",
            }

        def build_chat_response(message, **kwargs):
            payload = {"message": message}
            payload.update(kwargs)
            return payload

        with patch(
            "mapmover.runtime.orchestrator_helper_runtime.load_runtime_explainer_helpers",
            return_value={
                "build_explainer_response": lambda source_metadata, query, source_reference: {
                    "text": f"Explainer for {source_metadata['source_id']}: {query}",
                    "source_id": source_metadata["source_id"],
                    "pack_id": source_metadata["pack_id"],
                    "sections": {"summary": "Test summary"},
                    "stub_order": {"type": "explainer_stub"},
                }
            },
        ):
            payload = maybe_build_explainer_chat_response(
                query="What is distributed manufacturing?",
                hints={"detected_source": {"source_id": "distributed_manufacturing"}},
                build_chat_response_func=build_chat_response,
                load_source_metadata_func=load_source_metadata,
                load_source_reference_func=lambda _source_id: {"source": {"description": "Ignored in patched helper"}},
            )

        self.assertIsNotNone(payload)
        self.assertEqual(
            payload["message"],
            "Explainer for distributed_manufacturing: What is distributed manufacturing?",
        )
        self.assertEqual(payload["source_id"], "distributed_manufacturing")
        self.assertEqual(payload["pack_id"], "distributed_manufacturing")
        self.assertEqual(payload["stub_order"]["type"], "explainer_stub")


if __name__ == "__main__":
    unittest.main()
