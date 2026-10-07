"""Rate limiting and usage tracking for the Google Maps key endpoint.

`/api/config/maps-key` hands a credential to the browser, which is unavoidable
for client-side Places. The limiter here is defense in depth against a scripted
fetch loop; the key itself is protected by the referrer/API restrictions and
quota caps set in Google Cloud, because a caller who already holds the key never
returns to this process.
"""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import msgpack
from fastapi.testclient import TestClient

import app as app_module
from mapmover import logging_analytics, security
from mapmover.routes import geometry as geometry_routes


class MapsKeyRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        # app.py imported the limiter by value, so the endpoint keeps using the
        # object it bound at import time. Rebinding mapmover.security would not
        # reach it; patch the name the route actually closes over.
        limiter_patch = patch.object(
            app_module, "rate_limiter", security.SlidingWindowRateLimiter()
        )
        limiter_patch.start()
        self.addCleanup(limiter_patch.stop)
        self.client = TestClient(app_module.app)
        self.addCleanup(self.client.close)

    def test_first_call_returns_the_key(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key-value"}):
            response = self.client.get("/api/config/maps-key")
        self.assertEqual(200, response.status_code)
        self.assertEqual("test-key-value", response.json()["key"])

    def test_second_call_inside_the_window_is_rate_limited(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key-value"}):
            first = self.client.get("/api/config/maps-key")
            second = self.client.get("/api/config/maps-key")

        self.assertEqual(200, first.status_code)
        self.assertEqual(429, second.status_code)
        self.assertIn("Retry-After", second.headers)
        self.assertGreaterEqual(int(second.headers["Retry-After"]), 1)
        # A throttled response must never leak the credential.
        self.assertNotIn("key", second.json())

    def test_window_and_limit_are_env_tunable(self) -> None:
        env = {
            "GOOGLE_MAPS_API_KEY": "test-key-value",
            "MAPS_KEY_RATE_LIMIT": "3",
            "MAPS_KEY_RATE_WINDOW_SECONDS": "5",
        }
        with patch.dict(os.environ, env):
            codes = [self.client.get("/api/config/maps-key").status_code for _ in range(4)]
        self.assertEqual([200, 200, 200, 429], codes)


class MapsKeyUsageTrackingTests(unittest.TestCase):
    def test_successful_key_fetch_reaches_the_control_plane(self) -> None:
        # Routine 2xx traffic is deliberately not mirrored; this path is an
        # explicit exception because each call bills a third party.
        self.assertTrue(
            logging_analytics._should_mirror_route_event_to_control_plane(
                "/api/config/maps-key", method="GET", status_code=200
            )
        )

    def test_ordinary_api_traffic_is_still_not_mirrored(self) -> None:
        self.assertFalse(
            logging_analytics._should_mirror_route_event_to_control_plane(
                "/api/ops/ticker", method="GET", status_code=200
            )
        )

    def test_rate_limited_key_fetch_is_recorded(self) -> None:
        self.assertTrue(
            logging_analytics._should_mirror_route_event_to_control_plane(
                "/api/config/maps-key", method="GET", status_code=429, rate_limited=True
            )
        )


class AddressSelectionUsageTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        limiter_patch = patch.object(
            app_module, "rate_limiter", security.SlidingWindowRateLimiter()
        )
        limiter_patch.start()
        self.addCleanup(limiter_patch.stop)
        self.client = TestClient(app_module.app)
        self.addCleanup(self.client.close)

    def test_selected_address_is_recorded_without_address_or_coordinates(self) -> None:
        resolved = {
            "matched": {"loc_id": "USA-CA-075", "name": "San Francisco", "admin_level": 2},
            "stack": [],
        }
        body = msgpack.packb(
            {
                "lon": -122.4194,
                "lat": 37.7749,
                "interaction_source": "address_autocomplete",
            },
            use_bin_type=True,
        )
        with (
            patch.object(geometry_routes, "resolve_points_to_locations", return_value=[resolved]),
            patch.object(geometry_routes, "log_api_query_event") as log_event,
        ):
            response = self.client.post(
                "/geometry/resolve-point",
                content=body,
                headers={"Content-Type": "application/msgpack"},
            )

        self.assertEqual(200, response.status_code)
        fields = log_event.call_args.kwargs
        self.assertEqual("address_lookup_selection", fields["capability_id"])
        self.assertEqual("address_autocomplete", fields["source_id"])
        self.assertEqual("address_lookup_selected", fields["metadata"]["event"])
        self.assertNotIn("lon", fields["metadata"])
        self.assertNotIn("lat", fields["metadata"])
        self.assertNotIn("address", fields["metadata"])

    def test_unknown_interaction_source_cannot_spoof_an_analytics_lane(self) -> None:
        body = msgpack.packb(
            {"lon": -122.4194, "lat": 37.7749, "interaction_source": "made_up"},
            use_bin_type=True,
        )
        with (
            patch.object(
                geometry_routes,
                "resolve_points_to_locations",
                return_value=[{"matched": {"loc_id": "USA-CA-075"}, "stack": []}],
            ),
            patch.object(geometry_routes, "log_api_query_event") as log_event,
        ):
            response = self.client.post(
                "/geometry/resolve-point",
                content=body,
                headers={"Content-Type": "application/msgpack"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("point_lookup", log_event.call_args.kwargs["source_id"])


class AddressCardFrontendContractTests(unittest.TestCase):
    def test_auth_failure_is_checked_before_ready_status_and_selection_is_tagged(self) -> None:
        source = (Path(__file__).parents[1] / "static" / "modules" / "chat-panel.js").read_text(encoding="utf-8")
        self.assertIn("throw new Error('maps_auth_failed')", source)
        self.assertIn("interaction_source: 'address_autocomplete'", source)
        self.assertLess(
            source.index("Loading its boundary..."),
            source.index("const geojson = await postMsgpack('/geometry/features'"),
        )


if __name__ == "__main__":
    unittest.main()
