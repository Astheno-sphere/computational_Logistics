from __future__ import annotations

import unittest
from unittest.mock import patch

from mapmover.default_load_prewarm import (
    iter_pack_confirmed_order_defaults,
    prewarm_catalog_default_loads,
)


class DefaultLoadPrewarmTests(unittest.TestCase):
    def test_iter_pack_confirmed_order_defaults_uses_authored_pack_defaults(self) -> None:
        catalog = {
            "packs": [
                {
                    "pack_id": "world_factbook",
                    "default_load": {
                        "kind": "confirmed_order",
                        "items": [{"source_id": "world_factbook", "pack_id": "world_factbook"}],
                    },
                },
                {
                    "pack_id": "earthquakes",
                    "default_load": {
                        "kind": "overlay_range_load",
                        "overlay_id": "earthquakes",
                        "relative_years": 10,
                    },
                },
                {"pack_id": "empty", "default_load": {"kind": "confirmed_order", "items": []}},
            ]
        }

        defaults = iter_pack_confirmed_order_defaults(catalog)

        self.assertEqual(["world_factbook"], [pack_id for pack_id, _ in defaults])
        self.assertEqual("world_factbook", defaults[0][1]["items"][0]["pack_id"])

    def test_prewarm_catalog_default_loads_executes_each_confirmed_order(self) -> None:
        catalog = {
            "packs": [
                {
                    "pack_id": "currency",
                    "default_load": {
                        "kind": "confirmed_order",
                        "items": [{"source_id": "fx_usd_historical_monthly", "pack_id": "currency"}],
                    },
                },
                {
                    "pack_id": "floods",
                    "default_load": {"kind": "overlay_range_load", "overlay_id": "floods"},
                },
            ]
        }
        executed = []

        with patch("mapmover.default_load_prewarm.is_cloud_mode", return_value=True):
            prewarm_catalog_default_loads(
                load_catalog_func=lambda: catalog,
                execute_order_func=lambda order: executed.append(order) or {"type": "metrics", "count": 3},
            )

        self.assertEqual(1, len(executed))
        self.assertEqual("currency", executed[0]["items"][0]["pack_id"])


if __name__ == "__main__":
    unittest.main()
