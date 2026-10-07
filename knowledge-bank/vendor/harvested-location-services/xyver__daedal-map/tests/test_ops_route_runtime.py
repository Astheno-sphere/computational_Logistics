import pytest
import unittest
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from mapmover.ops_route_runtime import load_or_create_ops_watch
from mapmover.ops_route_runtime import _allowed_ops_feeds, _public_default_ops_feeds
from mapmover import ops_orchestrator_runtime
from mapmover.ops_feed_registry import load_ops_feed_records, validate_ops_feed_registry
from mapmover.routes import ops as ops_routes


class DummyCache:
    def __init__(self):
        self.map_state = {}


class DummyRouteContext:
    def __init__(self, *, allowed_feeds=None, effective_feeds=None):
        self.allowed_feeds = list(allowed_feeds or [])
        self.effective_feeds = list(effective_feeds or [])


class OpsRouteRuntimeTest(unittest.TestCase):
    def setUp(self):
        with ops_orchestrator_runtime._LIVE_STATE_CACHE_LOCK:
            ops_orchestrator_runtime._LIVE_STATE_CACHE.clear()

    def test_nws_current_state_prefers_railway_hot_surface(self):
        hot = {
            "collector": "usa_nws_alerts",
            "payload_summary": {"alerts": []},
            "payload_hash": "hot",
        }
        with patch.object(
            ops_orchestrator_runtime, "_fetch_live_state_via_site", return_value=hot
        ) as site, patch.object(
            ops_orchestrator_runtime, "_read_json_object", return_value={"collector": "stale"}
        ) as cloud:
            result = ops_orchestrator_runtime.load_current_state_snapshot("usa_nws_alerts")
        self.assertEqual("hot", result["payload_hash"])
        site.assert_called_once_with("usa_nws_alerts", "snapshot")
        cloud.assert_not_called()

    def test_nws_history_prefers_railway_hot_surface(self):
        hot = [{"collector": "usa_nws_alerts", "payload_hash": "hot-history"}]
        with patch.object(
            ops_orchestrator_runtime, "_fetch_live_state_via_site", return_value=hot
        ) as site, patch.object(ops_orchestrator_runtime, "_read_jsonl_object") as cloud:
            result = ops_orchestrator_runtime.load_current_state_history("usa_nws_alerts")
        self.assertEqual(hot, result)
        site.assert_called_once_with("usa_nws_alerts", "history")
        cloud.assert_not_called()

    def test_timeline_feed_filter_uses_effective_ops_feed_scope(self):
        route_context = DummyRouteContext(
            allowed_feeds=[],
            effective_feeds=["hurricanes_live", "usa_nws_alerts", "noaa_ndbc"],
        )
        requested = ["hurricanes_live", "usa_nws_alerts", "noaa_ndbc", "not_allowed"]

        self.assertEqual(
            ["hurricanes_live", "usa_nws_alerts", "noaa_ndbc"],
            ops_routes._requested_timeline_feeds(requested, route_context),
        )

    def test_timeline_feed_filter_accepts_overlay_aliases(self):
        route_context = DummyRouteContext(
            allowed_feeds=[],
            effective_feeds=["hurricanes_live", "usa_nws_alerts", "noaa_ndbc"],
        )
        requested = ["hurricanes", "nws_alerts", "buoys"]

        self.assertEqual(
            ["hurricanes_live", "usa_nws_alerts", "noaa_ndbc"],
            ops_routes._requested_timeline_feeds(requested, route_context),
        )

    def test_replaced_lazy_timeline_frames_keep_preload_contract(self):
        timeline = {"feeds": {}, "preload_history": {}}
        contract = {
            "provider": "nws_alerts",
            "preload_history": True,
            "cache_posture": "background_full",
        }
        frames = [{"start_at": "2026-09-07T12:00:00+00:00", "payload_hash": "abc"}]

        with patch.object(
            ops_routes, "ops_timeline_preload_history_contract", return_value=contract
        ):
            ops_routes._replace_timeline_provider_frames(
                timeline, "usa_nws_alerts", frames
            )

        self.assertEqual(frames, timeline["feeds"]["usa_nws_alerts"])
        self.assertEqual(contract, timeline["preload_history"]["usa_nws_alerts"])

    def test_strict_registry_requires_runtime_contract_fields(self):
        payload = {
            "schema_version": 2,
            "feeds": [{
                "feed_id": "example",
                "runtime_enabled": True,
                "collector_ids": ["example_collector"],
                "presentation": ["map"],
                "timeline": {
                    "provider": "inline_frame",
                    "mode": "full_snapshot",
                    "cache_posture": "inline_frame",
                    "preload_history": False,
                },
            }],
        }
        self.assertEqual([], validate_ops_feed_registry(payload, strict=True))
        del payload["feeds"][0]["timeline"]["mode"]
        self.assertTrue(validate_ops_feed_registry(payload, strict=True))

    def test_runtime_reads_prior_registry_without_strict_contract_fields(self):
        payload = {
            "schema_version": 1,
            "feeds": [{
                "feed_id": "older_feed",
                "runtime_enabled": True,
                "timeline": {"provider": "inline_frame", "preload_history": False},
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ops_feed_registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual("older_feed", load_ops_feed_records(path)[0]["feed_id"])

    @pytest.mark.fixture_drift(
        "Test reads real local NWS alert state instead of its fixture (got 759 alerts, expected 2). Test isolation, not logic."
    )
    def test_nws_background_batch_returns_compact_selected_frames(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        snapshot = {
            "published_at": now.isoformat(),
            "payload_hash": "nws-current",
            "payload_summary": {
                "alerts": [{
                    "alert_id": "nws-1",
                    "event": "Special Marine Warning",
                    "description": "Detailed retained bulletin text.",
                    "point": [-77.0, 38.9],
                }]
            },
        }
        with patch.object(ops_routes, "load_current_state_history", return_value=[]), patch.object(
            ops_routes, "load_current_state_snapshot", return_value=snapshot
        ):
            frames = ops_routes._local_nws_timeline_frames_at([now.isoformat()])

        self.assertEqual(1, len(frames))
        props = frames[0]["geojson"]["features"][0]["properties"]
        self.assertEqual("nws-1", props["alert_id"])
        self.assertNotIn("description", props)
        self.assertTrue(props["detail_available"])

    def test_nws_timeline_uses_compact_index_without_reading_raw_history(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        frame_key = "timeline_frames/" + ("a" * 64) + ".json"
        index = {
            "collector": "usa_nws_alerts",
            "frames": [{
                "start_at": now.isoformat(),
                "payload_hash": "a" * 64,
                "frame_key": frame_key,
            }],
        }
        stored_frame = {
            "collector": "usa_nws_alerts",
            "payload_summary": {"alerts": [{
                "alert_id": "nws-indexed",
                "event": "Tornado Warning",
                "point": [-90, 35],
            }]},
        }
        with patch.object(ops_routes, "load_current_state_timeline_index", return_value=index), patch.object(
            ops_routes, "load_current_state_timeline_frame", return_value=stored_frame
        ), patch.object(ops_routes, "load_current_state_history") as history:
            frame = ops_routes._local_nws_timeline_frame_at(now.isoformat())

        history.assert_not_called()
        self.assertEqual("nws-indexed", frame["geojson"]["features"][0]["properties"]["alert_id"])

    def test_nws_timeline_frame_hash_skips_timeline_index(self):
        payload_hash = "b" * 64
        stored_frame = {
            "collector": "usa_nws_alerts",
            "published_at": "2026-09-07T12:00:00+00:00",
            "payload_hash": payload_hash,
            "payload_summary": {"alerts": [{
                "alert_id": "nws-hash",
                "event": "Flash Flood Warning",
                "point": [-90, 35],
            }]},
        }
        with patch.object(
            ops_routes, "load_current_state_timeline_frame", return_value=stored_frame
        ) as frame_loader, patch.object(
            ops_routes, "load_current_state_timeline_index"
        ) as index_loader:
            frame = ops_routes._local_nws_timeline_frame_by_hash(payload_hash)

        index_loader.assert_not_called()
        frame_loader.assert_called_once_with(
            "usa_nws_alerts", f"timeline_frames/{payload_hash}.json"
        )
        self.assertEqual("nws-hash", frame["geojson"]["features"][0]["properties"]["alert_id"])

    def test_nws_timeline_frame_hash_rejects_invalid_identity(self):
        with patch.object(ops_routes, "load_current_state_timeline_frame") as frame_loader:
            self.assertIsNone(ops_routes._local_nws_timeline_frame_by_hash("../../snapshot"))
        frame_loader.assert_not_called()

    def test_nws_timeline_frame_accepts_published_hash_key(self):
        key = "timeline_frames/" + ("a" * 64) + ".json"
        with patch.object(ops_orchestrator_runtime, "_read_json_object", return_value={"collector": "usa_nws_alerts"}) as reader:
            frame = ops_orchestrator_runtime.load_current_state_timeline_frame("usa_nws_alerts", key)

        self.assertEqual({"collector": "usa_nws_alerts"}, frame)
        reader.assert_called_once_with("usa_nws_alerts/" + key)

    def test_requested_sources_replace_cached_watch_feeds(self):
        cache = DummyCache()
        cache.map_state["ops_watch"] = {
            "watch_id": "watch_ops",
            "label": "Old watch",
            "geography": {"viewport": {}},
            "active_feeds": ["earthquakes", "wildfires_us_nifc"],
        }

        watch = load_or_create_ops_watch(
            cache=cache,
            session_id="ops",
            body={
                "watch_id": "watch_ops",
                "watch_context": {
                    "label": "Updated watch",
                    "sources": ["earthquakes", "hurricanes"],
                },
            },
            allowed_feeds=["earthquakes", "hurricanes_live", "wildfires_us_nifc"],
        )

        self.assertEqual(["earthquakes", "hurricanes_live"], watch["active_feeds"])
        self.assertEqual("Updated watch", watch["label"])
        self.assertEqual(watch, cache.map_state["ops_watch"])

    def test_account_default_load_resets_cached_narrow_watch(self):
        cache = DummyCache()
        cache.map_state["ops_watch"] = {
            "watch_id": "watch_ops",
            "label": "Ops deep link",
            "geography": {"viewport": {}},
            "active_feeds": ["earthquakes"],
        }

        watch = load_or_create_ops_watch(
            cache=cache,
            session_id="ops",
            body={
                "watch_id": "watch_ops",
                "watch_context": {
                    "label": "Ops watch",
                    "reset_to_allowed": True,
                },
            },
            allowed_feeds=["earthquakes", "hurricanes_live", "wildfires_us_nifc"],
        )

        self.assertEqual(["earthquakes", "hurricanes_live", "wildfires_us_nifc"], watch["active_feeds"])
        self.assertEqual("Ops watch", watch["label"])

    def test_report_without_reset_preserves_cached_narrow_watch(self):
        cache = DummyCache()
        cache.map_state["ops_watch"] = {
            "watch_id": "watch_ops",
            "label": "Ops deep link",
            "geography": {"viewport": {}},
            "active_feeds": ["earthquakes"],
        }

        watch = load_or_create_ops_watch(
            cache=cache,
            session_id="ops",
            body={
                "watch_id": "watch_ops",
                "watch_context": {
                    "label": "Ops watch",
                },
            },
            allowed_feeds=["earthquakes", "hurricanes_live", "wildfires_us_nifc"],
        )

        self.assertEqual(["earthquakes"], watch["active_feeds"])
        self.assertEqual("Ops deep link", watch["label"])

    def test_active_available_and_inactive_feed_context_updates_watch(self):
        cache = DummyCache()
        cache.map_state["ops_watch"] = {
            "watch_id": "watch_ops",
            "label": "Old watch",
            "geography": {"viewport": {}},
            "active_feeds": ["hurricanes_live"],
        }

        watch = load_or_create_ops_watch(
            cache=cache,
            session_id="ops",
            body={
                "watch_id": "watch_ops",
                "watch_context": {
                    "label": "Ops watch",
                    "sources": ["usa_nws_alerts"],
                    "available_sources": ["usa_nws_alerts", "hurricanes_live", "noaa_ndbc"],
                    "inactive_sources": ["hurricanes_live", "noaa_ndbc"],
                },
            },
            allowed_feeds=["hurricanes_live", "usa_nws_alerts", "noaa_ndbc"],
        )

        self.assertEqual(["usa_nws_alerts"], watch["active_feeds"])
        self.assertEqual(["usa_nws_alerts", "hurricanes_live", "noaa_ndbc"], watch["available_feeds"])
        self.assertEqual(["hurricanes_live", "noaa_ndbc"], watch["inactive_feeds"])

    def test_public_default_ops_feeds_exclude_currency(self):
        feeds = _public_default_ops_feeds()
        self.assertNotIn("currency", feeds)
        self.assertIn("earthquakes", feeds)
        self.assertIn("hurricanes_live", feeds)
        self.assertIn("noaa_ndbc", feeds)
        self.assertIn("ocean_sst", feeds)
        self.assertIn("usa_nws_alerts", feeds)
        self.assertNotIn("airnow", feeds)

    def test_anonymous_public_deep_link_can_activate_non_default_currency(self):
        allowed = _allowed_ops_feeds(
            auth_user=None,
            caller_ctx={"caller_kind": "anonymous"},
            body={"watch_context": {"sources": ["currency"]}},
        )

        self.assertIn("currency", allowed)
        self.assertIn("earthquakes", allowed)

    def test_anonymous_deep_link_does_not_activate_wip_feed(self):
        allowed = _allowed_ops_feeds(
            auth_user=None,
            caller_ctx={"caller_kind": "anonymous"},
            body={"watch_context": {"sources": ["airnow"]}},
        )

        self.assertNotIn("airnow", allowed)

    @pytest.mark.fixture_drift(
        "Test reads real local NWS alert state instead of its fixture. Test isolation, not logic."
    )
    def test_nws_timeline_reconstructs_full_alert_state_from_deltas(self):
        original_history = ops_routes.load_current_state_history
        original_snapshot = ops_routes.load_current_state_snapshot
        first_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
        second_at = first_at + timedelta(minutes=5)
        first = {
            "published_at": first_at.isoformat(),
            "summary": {"alert_count": 1},
            "delta": {"added": [{"alert_id": "a-1", "event": "Tornado Warning", "geometry": {"type": "Point", "coordinates": [-90, 35]}}], "updated": [], "removed": []},
        }
        second = {
            "published_at": second_at.isoformat(),
            "summary": {"alert_count": 1},
            # Geometry is deliberately omitted from an unchanged-geometry update.
            "delta": {"added": [], "updated": [{"alert_id": "a-1", "headline": "Updated warning"}], "removed": []},
        }
        try:
            ops_routes.load_current_state_history = lambda _feed: [first, second]
            ops_routes.load_current_state_snapshot = lambda _feed: None
            entries = ops_routes._local_nws_timeline_entries()
        finally:
            ops_routes.load_current_state_history = original_history
            ops_routes.load_current_state_snapshot = original_snapshot

        self.assertEqual(2, len(entries))
        reconstructed = entries[-1]["payload_summary"]["alerts"]
        self.assertEqual(1, len(reconstructed))
        self.assertEqual("Updated warning", reconstructed[0]["headline"])
        self.assertEqual({"type": "Point", "coordinates": [-90, 35]}, reconstructed[0]["geometry"])

    def test_retained_point_frame_uses_snapshot_at_cursor_time(self):
        original_history = ops_routes.load_current_state_history
        original_snapshot = ops_routes.load_current_state_snapshot
        first_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
        second_at = first_at + timedelta(minutes=5)
        first = {
            "published_at": first_at.isoformat(),
            "payload_hash": "first",
            "payload_summary": {"buoys": [{"station_id": "A", "lat": 10, "lon": 20, "sst_c": 11.0}]},
        }
        second = {
            "published_at": second_at.isoformat(),
            "payload_hash": "second",
            "payload_summary": {"buoys": [{"station_id": "A", "lat": 10, "lon": 20, "sst_c": 12.5}]},
        }
        try:
            ops_routes.load_current_state_history = lambda _feed: [first, second]
            ops_routes.load_current_state_snapshot = lambda _feed: second
            frame = ops_routes._local_point_timeline_frame_at("buoys", (first_at + timedelta(minutes=3)).isoformat())
        finally:
            ops_routes.load_current_state_history = original_history
            ops_routes.load_current_state_snapshot = original_snapshot

        self.assertEqual("first", frame["payload_hash"])
        self.assertEqual(11.0, frame["geojson"]["features"][0]["properties"]["sst_c"])

    def test_retained_point_frames_batch_uses_each_requested_snapshot(self):
        original_history = ops_routes.load_current_state_history
        original_snapshot = ops_routes.load_current_state_snapshot
        first_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
        second_at = first_at + timedelta(minutes=5)
        first = {
            "published_at": first_at.isoformat(),
            "payload_hash": "first",
            "payload_summary": {"buoys": [{"station_id": "A", "lat": 10, "lon": 20, "sst_c": 11.0}]},
        }
        second = {
            "published_at": second_at.isoformat(),
            "payload_hash": "second",
            "payload_summary": {"buoys": [{"station_id": "A", "lat": 10, "lon": 20, "sst_c": 12.5}]},
        }
        try:
            ops_routes.load_current_state_history = lambda _feed: [first, second]
            ops_routes.load_current_state_snapshot = lambda _feed: second
            frames = ops_routes._local_point_timeline_frames_at(
                "buoys", [(first_at + timedelta(minutes=3)).isoformat(), (first_at + timedelta(minutes=6)).isoformat()]
            )
        finally:
            ops_routes.load_current_state_history = original_history
            ops_routes.load_current_state_snapshot = original_snapshot

        self.assertEqual(["first", "second"], [frame["payload_hash"] for frame in frames])
        self.assertEqual(12.5, frames[-1]["geojson"]["features"][0]["properties"]["sst_c"])

    def test_timeline_expands_to_declared_display_window(self):
        original_history = ops_orchestrator_runtime.load_current_state_history
        original_snapshot = ops_orchestrator_runtime.load_current_state_snapshot
        snapshot = {
            "published_at": "2026-07-27T00:00:00+00:00",
            "ops_history_retention_hours": 720,
            "ops_history_display_hours": 720,
            "ops_timeline_display_hours": 72,
            "payload_summary": {"event_count": 0},
        }
        try:
            ops_orchestrator_runtime.load_current_state_history = lambda _feed: []
            ops_orchestrator_runtime.load_current_state_snapshot = lambda _feed: snapshot
            timeline = ops_orchestrator_runtime.build_ops_timeline_payload(effective_feeds=["earthquakes"])
        finally:
            ops_orchestrator_runtime.load_current_state_history = original_history
            ops_orchestrator_runtime.load_current_state_snapshot = original_snapshot

        self.assertEqual(72, timeline["history_hours"])

    def test_shared_timeline_does_not_load_long_nws_history(self):
        snapshot = {
            "published_at": "2026-08-12T00:00:00+00:00",
            "ops_history_retention_hours": 1440,
            "ops_history_display_hours": 1440,
            "ops_timeline_display_hours": 72,
            "payload_summary": {"alert_count": 0, "alerts": []},
        }
        with patch.object(
            ops_orchestrator_runtime, "load_current_state_snapshot", return_value=snapshot
        ), patch.object(ops_orchestrator_runtime, "load_current_state_history") as history:
            timeline = ops_orchestrator_runtime.build_ops_timeline_payload(
                effective_feeds=["usa_nws_alerts"]
            )

        history.assert_not_called()
        self.assertEqual(72, timeline["history_hours"])

    def test_initial_report_does_not_preload_declared_history(self):
        snapshot = {
            "collector": "hurricanes_live",
            "published_at": "2026-08-12T00:00:00+00:00",
            "last_checked_at": "2026-08-12T00:00:00+00:00",
            "last_changed_at": "2026-08-12T00:00:00+00:00",
            "payload_hash": "current",
            "collector_status": "quiet",
            "ops_default_load": "history",
            "payload_summary": {"storms": []},
        }
        with patch.object(
            ops_orchestrator_runtime, "load_current_state_snapshot", return_value=snapshot
        ), patch.object(ops_orchestrator_runtime, "load_current_state_history") as history:
            ops_orchestrator_runtime.build_ops_report(
                watch={"watch_id": "default"},
                effective_feeds=["hurricanes_live"],
            )

        history.assert_not_called()

    def test_snapshot_prewarmer_uses_default_watch_without_history(self):
        snapshot = {"collector": "earthquakes", "payload_summary": {}}
        with patch.object(
            ops_orchestrator_runtime, "ops_feed_ids", return_value=("earthquakes",)
        ), patch.object(
            ops_orchestrator_runtime, "load_current_state_snapshot", return_value=snapshot
        ) as current, patch.object(
            ops_orchestrator_runtime, "load_current_state_history"
        ) as history:
            result = ops_orchestrator_runtime.prewarm_ops_snapshots()

        self.assertEqual(["earthquakes"], result["warmed"])
        current.assert_called_once_with("earthquakes")
        history.assert_not_called()

    def test_timeline_allows_external_provider_only_request(self):
        timeline = ops_orchestrator_runtime.build_ops_timeline_payload(effective_feeds=[])
        self.assertEqual(72, timeline["history_hours"])
        self.assertEqual({}, timeline["feeds"])

    def test_latest_event_snapshot_does_not_expire_at_expected_poll_time(self):
        original_history = ops_orchestrator_runtime.load_current_state_history
        original_snapshot = ops_orchestrator_runtime.load_current_state_snapshot
        now = datetime.now(timezone.utc).replace(microsecond=0)
        snapshot = {
            "published_at": now.isoformat(),
            "expected_next_at": (now - timedelta(minutes=5)).isoformat(),
            "payload_hash": "latest",
            "payload_summary": {
                "events": [{"event_id": "q1", "longitude": -122.3, "latitude": 47.6}],
            },
        }
        try:
            ops_orchestrator_runtime.load_current_state_history = lambda _feed: []
            ops_orchestrator_runtime.load_current_state_snapshot = lambda _feed: snapshot
            timeline = ops_orchestrator_runtime.build_ops_timeline_payload(effective_feeds=["earthquakes"])
        finally:
            ops_orchestrator_runtime.load_current_state_history = original_history
            ops_orchestrator_runtime.load_current_state_snapshot = original_snapshot

        self.assertIsNone(timeline["feeds"]["earthquakes"][-1]["end_at"])


if __name__ == "__main__":
    unittest.main()
