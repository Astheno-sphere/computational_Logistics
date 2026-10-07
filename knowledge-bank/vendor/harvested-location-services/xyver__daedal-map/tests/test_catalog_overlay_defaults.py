from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import msgpack

from mapmover.routes.system import get_catalog_overlays


class CatalogOverlayDefaultsTests(unittest.TestCase):
    def _catalog(self) -> dict:
        return {
            "sources": [
                {
                    "source_id": "geometry_global",
                    "pack_id": "geometry_global",
                    "overlay": {"path": "admin_layers"},
                },
                {
                    "source_id": "world_factbook",
                    "pack_id": "world_factbook",
                    "overlay": {"path": "world_factbook"},
                    "default_load": {
                        "kind": "confirmed_order",
                        "items": [{"source_id": "world_factbook", "pack_id": "world_factbook"}],
                    },
                    "default_question": "Show World Factbook countries",
                    "default_response": "Showing World Factbook countries.",
                },
            ],
            "packs": [
                {
                    "pack_id": "world_factbook",
                    "default_load": {
                        "kind": "confirmed_order",
                        "items": [{"source_id": "world_factbook", "pack_id": "world_factbook"}],
                    },
                    "default_question": "Show the World Factbook pack",
                    "default_response": "Showing the World Factbook pack.",
                }
            ],
        }

    def test_anonymous_overlay_catalog_keeps_source_default_deep_links(self) -> None:
        catalog = self._catalog()
        request = SimpleNamespace(headers={}, query_params={}, client=SimpleNamespace(host="203.0.113.10"))

        with patch("mapmover.routes.system.get_authenticated_user", return_value=None):
            with patch("mapmover.routes.system._get_entitled_packs", return_value=set()):
                with patch("mapmover.catalog_surface.request_uses_wip_catalog", return_value=False):
                    with patch("mapmover.data_loading.load_catalog", return_value=catalog):
                        response = asyncio.run(get_catalog_overlays(request))

        payload = msgpack.unpackb(response.body, raw=False)

        self.assertNotIn("world_factbook", [src.get("source_id") for src in payload["sources"]])
        self.assertIn("world_factbook", payload["source_defaults"])
        self.assertEqual("world_factbook", payload["source_defaults"]["world_factbook"]["pack_id"])
        self.assertIn("default_load", payload["source_defaults"]["world_factbook"])
        self.assertEqual(
            "Show World Factbook countries",
            payload["source_defaults"]["world_factbook"]["default_question"],
        )
        self.assertEqual(
            "Showing World Factbook countries.",
            payload["source_defaults"]["world_factbook"]["default_response"],
        )
        self.assertIn("world_factbook", payload["pack_defaults"])
        self.assertIn("default_load", payload["pack_defaults"]["world_factbook"])
        self.assertEqual(
            "Show the World Factbook pack",
            payload["pack_defaults"]["world_factbook"]["default_question"],
        )
        self.assertEqual(
            "Showing the World Factbook pack.",
            payload["pack_defaults"]["world_factbook"]["default_response"],
        )

    def test_local_logged_out_overlay_catalog_matches_anonymous_production_shape(self) -> None:
        request = SimpleNamespace(
            headers={},
            query_params={},
            client=SimpleNamespace(host="127.0.0.1"),
        )

        with patch("mapmover.routes.system.get_authenticated_user", return_value=None):
            with patch("mapmover.catalog_surface.request_uses_wip_catalog", return_value=False):
                with patch("mapmover.data_loading.load_catalog", return_value=self._catalog()):
                    response = asyncio.run(get_catalog_overlays(request))

        payload = msgpack.unpackb(response.body, raw=False)

        self.assertEqual(["geometry_global"], [src.get("source_id") for src in payload["sources"]])
        self.assertIn("world_factbook", payload["pack_defaults"])
        self.assertIn("world_factbook", payload["source_defaults"])


if __name__ == "__main__":
    unittest.main()
