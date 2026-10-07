from unittest import mock

import pytest

from mapmover import control_catalog_prewarm


def test_prewarm_control_catalogs_uses_all_canonical_loaders() -> None:
    with (
        mock.patch.object(
            control_catalog_prewarm,
            "load_catalog",
            return_value={"sources": [{"source_id": "published"}]},
        ) as published,
        mock.patch.object(
            control_catalog_prewarm,
            "load_full_catalog",
            return_value={"sources": [{"source_id": "wip-1"}, {"source_id": "wip-2"}]},
        ) as wip,
        mock.patch.object(
            control_catalog_prewarm,
            "load_geometry_catalog",
            return_value={"geometry_banks": [{"bank_id": "admin"}]},
        ) as geometry,
        mock.patch.object(
            control_catalog_prewarm,
            "load_ops_feed_records",
            return_value=[{"feed_id": "earthquakes"}],
        ) as ops,
    ):
        counts = control_catalog_prewarm.prewarm_control_catalogs()

    assert counts == {"published": 1, "wip": 2, "geometry": 1, "ops_feeds": 1}
    published.assert_called_once_with()
    wip.assert_called_once_with()
    geometry.assert_called_once_with()
    ops.assert_called_once_with()


def test_prewarm_control_catalogs_fails_readiness_for_empty_catalog() -> None:
    with (
        mock.patch.object(control_catalog_prewarm, "load_catalog", return_value={"sources": []}),
        mock.patch.object(control_catalog_prewarm, "load_full_catalog", return_value={"sources": [{}]}),
        mock.patch.object(
            control_catalog_prewarm,
            "load_geometry_catalog",
            return_value={"geometry_banks": [{}]},
        ),
        mock.patch.object(
            control_catalog_prewarm,
            "load_ops_feed_records",
            return_value=[{"feed_id": "earthquakes"}],
        ),
    ):
        with pytest.raises(RuntimeError, match="published"):
            control_catalog_prewarm.prewarm_control_catalogs()
