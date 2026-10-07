"""Regression tests for deterministic source-info answers."""

from mapmover.preprocessor_candidates import detect_source_candidates
from mapmover.explore.chat_lane_runtime import maybe_build_orientation_payload
from mapmover.ops_route_runtime import build_ops_orientation_payload
from mapmover.runtime.explainer_response import build_explainer_response, build_view_orientation_response


def test_catalog_source_info_alias_resolves_without_metadata_alias():
    catalog = {
        "sources": [{
            "source_id": "cams_air_quality",
            "source_name": "CAMS Global Modeled Surface PM2.5",
            "reference_guidance": {"source_info": {"aliases": ["CAMS", "modeled PM2.5"]}},
        }]
    }
    result = detect_source_candidates(
        "What is CAMS?",
        load_catalog=lambda: catalog,
        load_source_metadata=lambda _source_id: {},
        score_source_full_match=0.8,
        score_source_id_match=0.7,
        score_source_partial_8=0.6,
        score_source_partial_4=0.5,
    )
    assert result["best"]["source_id"] == "cams_air_quality"
    assert result["best"]["match_type"] == "metadata_alias"


def test_source_info_explainer_uses_lane_guidance():
    response = build_explainer_response(
        {"source_id": "airnow", "source_name": "AirNow AQI"},
        "What is AirNow?",
        {
            "source_info": {
                "short_answer": "AirNow provides preliminary reporting-area AQI.",
                "not": ["a validated regulatory record"],
                "source_link": "https://www.airnow.gov/",
            },
            "lane_guidance": {
                "ops": {
                    "availability": "available",
                    "answer_note": "Use only as preliminary current conditions.",
                }
            },
        },
        lane="ops",
    )
    assert response is not None
    assert "AirNow provides preliminary" in response["text"]
    assert "Ops availability: available." in response["text"]
    assert "preliminary current conditions" in response["text"]


def test_context_orientation_uses_the_one_loaded_source_without_llm():
    payload = maybe_build_orientation_payload(
        hints={},
        request_context={"loaded_data": [{"source_id": "cams_air_quality"}]},
        query="What am I looking at here?",
        auth_user=None,
        load_source_metadata_func=lambda source_id: {"source_id": source_id, "source_name": "CAMS"},
        load_source_reference_func=lambda _source_id: {
            "source_info": {"short_answer": "CAMS is a modeled PM2.5 field."},
            "lane_guidance": {"explore": {"availability": "wip"}},
        },
        build_chat_response_func=lambda message, **kwargs: {"message": message, **kwargs},
    )
    assert payload is not None
    assert payload["source_id"] == "cams_air_quality"
    assert "modeled PM2.5" in payload["message"]


def test_shared_view_orientation_describes_multiple_layers_without_selecting_one():
    response = build_view_orientation_response(
        {
            "loaded_data": [
                {"source_id": "cams_air_quality", "metric": "pm2p5", "year": 2026},
                {"source_id": "fema_disasters", "metric": "total_declarations"},
            ],
            "time_state": {"isLiveLocked": True},
            "selected_popup": {"name": "Los Angeles County"},
        },
        lane="explore",
    )
    assert response is not None
    assert "cams_air_quality (pm2p5), 2026" in response["text"]
    assert "fema_disasters (total_declarations)" in response["text"]
    assert "live current conditions" in response["text"]
    assert "Los Angeles County" in response["text"]


def test_ops_orientation_uses_live_source_contract(monkeypatch):
    snapshot = {
        "payload_summary": {
            "source_info": {"aliases": ["AirNow"], "short_answer": "AirNow is preliminary AQI."},
            "lane_guidance": {"ops": {"availability": "current_snapshot"}},
        }
    }
    monkeypatch.setattr(
        "mapmover.ops_route_runtime.load_current_state_snapshot", lambda _feed: snapshot,
    )
    payload = build_ops_orientation_payload(
        query="Tell me about AirNow", effective_feeds=["airnow"],
    )
    assert payload is not None
    assert payload["source_id"] == "airnow"
    assert "preliminary AQI" in payload["message"]
    assert "Ops availability: current snapshot." in payload["message"]
