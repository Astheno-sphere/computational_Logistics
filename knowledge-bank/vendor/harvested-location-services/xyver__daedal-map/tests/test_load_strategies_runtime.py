import pytest
import unittest

from mapmover.execution.load_strategies import (
    _classify_pushdown_filters,
    collect_source_metadata,
    load_order_item_dataframe,
)


class LoadStrategiesRuntimeTests(unittest.TestCase):
    @pytest.mark.fixture_drift(
        "classify_pushdown_filters now also returns ignored_presence; fixture predates it. Not spine related."
    )
    def test_classify_pushdown_filters_maps_common_filter_shapes(self):
        exact_filters, in_filters, compare_filters = _classify_pushdown_filters(
            {
                "naics": "31----",
                "enterprise_size": {"op": "eq", "value": "2: <20 employees"},
                "risk_score": {"min": 90},
                "facility_type": {"op": "in", "values": ["fab_lab", "hackerspace"]},
                "year_max": 2024,
                "ignored_presence": True,
            }
        )

        self.assertEqual(
            exact_filters,
            {
                "naics": "31----",
                "enterprise_size": "2: <20 employees",
                "ignored_presence": True,
            },
        )
        self.assertEqual(
            in_filters,
            {
                "facility_type": ["fab_lab", "hackerspace"],
            },
        )
        self.assertEqual(
            compare_filters,
            [
                ("risk_score", ">=", 90),
                ("year", "<=", 2024),
            ],
        )

    def test_collect_source_metadata_uses_metadata_loader_without_loading_rows(self):
        seen = {"metadata_calls": 0, "aggregate_calls": 0}

        def expand_region(_region):
            return set()

        def load_disaster_aggregate_data(source_id, item):
            seen["aggregate_calls"] += 1
            self.assertEqual(source_id, "cbp")
            self.assertEqual(item["source_id"], "cbp")
            return None, None

        def load_source_metadata(source_id):
            seen["metadata_calls"] += 1
            self.assertEqual(source_id, "cbp")
            return {"source_id": "cbp", "geographic_level": "admin_2"}

        state = collect_source_metadata(
            items=[{"source_id": "cbp"}],
            expand_region_func=expand_region,
            load_disaster_aggregate_data_func=load_disaster_aggregate_data,
            load_source_metadata_func=load_source_metadata,
            logger=type("Logger", (), {"warning": lambda *args, **kwargs: None})(),
            trace_id="test-trace",
        )

        self.assertEqual(seen["metadata_calls"], 1)
        self.assertEqual(seen["aggregate_calls"], 0)
        self.assertEqual(state["geo_levels"], {"admin_2"})
        self.assertIn("cbp", state["sources_used"])

    def test_load_order_item_dataframe_pushes_filters_into_loader(self):
        captured = {}

        def load_disaster_aggregate_data(_source_id, _item):
            return None, None

        def load_source_data(source_id, **kwargs):
            captured["source_id"] = source_id
            captured["kwargs"] = kwargs
            return [], {"source_id": source_id}

        load_order_item_dataframe(
            item={
                "source_id": "cbp",
                "metric": "est",
                "filters": {
                    "naics": "31----",
                    "risk_score": {"min": 90},
                    "facility_type": {"op": "in", "values": ["fab_lab", "hackerspace"]},
                },
                "region": "USA-VA",
            },
            temporal_mode=False,
            aggregate_item_cache={},
            load_disaster_aggregate_data_func=load_disaster_aggregate_data,
            load_source_data_func=load_source_data,
        )

        self.assertEqual(captured["source_id"], "cbp")
        self.assertEqual(captured["kwargs"]["loc_id_prefix"], "USA-VA")
        self.assertEqual(captured["kwargs"]["exact_filters"], {"naics": "31----"})
        self.assertEqual(
            captured["kwargs"]["in_filters"],
            {"facility_type": ["fab_lab", "hackerspace"]},
        )
        self.assertEqual(
            captured["kwargs"]["compare_filters"],
            [("risk_score", ">=", 90)],
        )

    def test_load_order_item_dataframe_normalizes_lowercase_region_prefix(self):
        captured = {}

        def load_disaster_aggregate_data(_source_id, _item):
            return None, None

        def load_source_data(source_id, **kwargs):
            captured["source_id"] = source_id
            captured["kwargs"] = kwargs
            return [], {"source_id": source_id}

        load_order_item_dataframe(
            item={
                "source_id": "worldpop",
                "metric": "population",
                "region": "usa-ca",
                "filters": {
                    "loc_id_prefix": "usa-ca",
                },
            },
            temporal_mode=False,
            aggregate_item_cache={},
            load_disaster_aggregate_data_func=load_disaster_aggregate_data,
            load_source_data_func=load_source_data,
        )

        self.assertEqual(captured["source_id"], "worldpop")
        self.assertEqual(captured["kwargs"]["loc_id_prefix"], "USA-CA")

    def test_load_order_item_dataframe_does_not_treat_region_slug_as_loc_id_prefix(self):
        captured = {}

        def load_disaster_aggregate_data(_source_id, _item):
            return None, None

        def load_source_data(source_id, **kwargs):
            captured["source_id"] = source_id
            captured["kwargs"] = kwargs
            return [], {"source_id": source_id}

        load_order_item_dataframe(
            item={
                "source_id": "fairfax_buildings",
                "metric": "BLDG_HEIGHT",
                "region": "usa-va-fairfax",
            },
            temporal_mode=False,
            aggregate_item_cache={},
            load_disaster_aggregate_data_func=load_disaster_aggregate_data,
            load_source_data_func=load_source_data,
        )

        self.assertEqual(captured["source_id"], "fairfax_buildings")
        self.assertFalse(captured["kwargs"]["loc_id_prefix"])

    def test_load_order_item_dataframe_pushes_source_geo_level_contract(self):
        captured = {}

        def load_disaster_aggregate_data(_source_id, _item):
            return None, None

        def load_source_data(source_id, **kwargs):
            captured["source_id"] = source_id
            captured["kwargs"] = kwargs
            return [], {"source_id": source_id}

        load_order_item_dataframe(
            item={
                "source_id": "fairfax_nlcd_impervious",
                "metric": "impervious_max_pct",
                "geo_level": "blockgroup",
                "year": 2024,
            },
            temporal_mode=False,
            aggregate_item_cache={},
            load_disaster_aggregate_data_func=load_disaster_aggregate_data,
            load_source_data_func=load_source_data,
            load_source_metadata_func=lambda _source_id: {
                "geographic_coverage": {"country": "USA"},
                "geographic_level": "admin_3",
                "dimensions": {
                    "geo_level": {
                        "values": {
                            "county": "county",
                            "tract": "tract",
                            "blockgroup": "blockgroup",
                            "block": "block",
                        }
                    }
                },
            },
        )

        self.assertEqual(captured["source_id"], "fairfax_nlcd_impervious")
        self.assertEqual(captured["kwargs"]["exact_filters"]["geo_level"], "block_group")

    def test_load_order_item_dataframe_uses_timestamp_bounds_for_monthly_source(self):
        captured = {}

        def load_source_data(source_id, **kwargs):
            captured["source_id"] = source_id
            captured["kwargs"] = kwargs
            return [], {"source_id": source_id}

        load_order_item_dataframe(
            item={
                "source_id": "era5_land_temperature",
                "metric": "air_temperature_2m_anomaly_c",
                "date_start": "2015-12-01",
                "date_end": "2015-12-31",
            },
            temporal_mode=False,
            aggregate_item_cache={},
            load_disaster_aggregate_data_func=lambda *_args: (None, None),
            load_source_data_func=load_source_data,
            load_source_metadata_func=lambda _source_id: {
                "time_field": "timestamp",
                "temporal_coverage": {"field": "timestamp", "granularity": "monthly"},
            },
        )

        self.assertIsNone(captured["kwargs"]["year"])
        self.assertEqual(
            captured["kwargs"]["compare_filters"],
            [
                ("timestamp", ">=", "2015-12-01T00:00:00Z"),
                ("timestamp", "<=", "2015-12-31T00:00:00Z"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
