import unittest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from starlette.requests import Request

from mapmover.api_query_runtime import (
    ApiMetricSpec,
    ApiSourceSpec,
    _get_mcp_pack_source_ids,
    execute_dataset_query,
    resolve_pack_sources_for_metrics,
)
from mapmover.api_query_scope import format_year_end, format_year_start, parse_time_filter
from mapmover.execution.event_execution import _build_single_event_message
from mapmover.runtime.filter_primitives import partition_region_filter_codes
from mapmover.runtime.postprocess_pipeline import (
    apply_default_time_windows,
    apply_event_qualifier_defaults,
    apply_query_derived_order_hints,
)
from mapmover.runtime.query_constraint_primitives import extract_query_constraints


class EventQueryRuntimeTests(unittest.TestCase):
    def test_pack_source_discovery_skips_unreadable_optional_companion(self):
        catalog = {
            "sources": [
                {"pack_id": "floods", "source_id": "flood_aggregates"},
                {"pack_id": "floods", "source_id": "floods"},
            ]
        }
        canonical_spec = ApiSourceSpec(
            source_id="floods",
            pack_id="floods",
            parquet_name="events.parquet",
            query_mode="single_source_events",
            location_field="loc_id",
            time_field="timestamp",
            time_granularity="timestamp",
            metrics={},
            filterable_fields={"loc_id", "timestamp"},
            sortable_fields={"loc_id", "timestamp"},
        )

        def source_spec(source_id):
            if source_id == "flood_aggregates":
                raise RuntimeError("optional aggregate artifact is unavailable")
            return canonical_spec

        with patch("mapmover.api_query_runtime.load_catalog", return_value=catalog), patch(
            "mapmover.api_query_runtime.is_mcp_distribution_source", return_value=True
        ), patch(
            "mapmover.api_query_runtime.get_api_source_spec", side_effect=source_spec
        ):
            source_ids = _get_mcp_pack_source_ids("floods")

        self.assertEqual(source_ids, ["floods"])

    def test_pack_event_count_prefers_canonical_event_source_over_aggregate(self):
        event_spec = ApiSourceSpec(
            source_id="floods",
            pack_id="floods",
            parquet_name="events.parquet",
            query_mode="single_source_events",
            location_field="loc_id",
            time_field="timestamp",
            time_granularity="timestamp",
            metrics={
                "event_count": ApiMetricSpec(
                    metric_id="event_count",
                    column="event_count",
                    description="Count matching events",
                )
            },
            filterable_fields={"loc_id", "timestamp"},
            sortable_fields={"loc_id", "timestamp", "event_count"},
        )
        aggregate_spec = ApiSourceSpec(
            source_id="flood_aggregates",
            pack_id="floods",
            parquet_name="metrics.parquet",
            query_mode="single_source",
            location_field="loc_id",
            time_field="year",
            time_granularity="yearly",
            metrics={
                "event_count": ApiMetricSpec(
                    metric_id="event_count",
                    column="event_count",
                    description="Annual event count",
                )
            },
            filterable_fields={"loc_id", "year"},
            sortable_fields={"loc_id", "year", "event_count"},
        )
        specs = {"floods": event_spec, "flood_aggregates": aggregate_spec}
        with patch(
            "mapmover.api_query_runtime._get_mcp_pack_source_ids",
            return_value=["flood_aggregates", "floods", "noaa_storm_events_floods"],
        ), patch(
            "mapmover.api_query_runtime.get_api_source_spec",
            side_effect=lambda source_id: specs.get(source_id, event_spec),
        ), patch(
            "mapmover.api_query_runtime.load_source_metadata",
            side_effect=lambda source_id: (
                (_ for _ in ()).throw(FileNotFoundError(source_id))
                if source_id == "noaa_storm_events_floods"
                else {"metrics": {}}
            ),
        ):
            resolved = resolve_pack_sources_for_metrics("floods", ["event_count"])

        self.assertEqual(resolved["resolution"], "single_source")
        self.assertEqual(resolved["selected_source_id"], "floods")

    def test_dataset_query_empty_in_filter_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "rows.parquet"
            pd.DataFrame([{"loc_id": "USA", "year": 2026}]).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="test", pack_id="test", parquet_name="rows.parquet",
                query_mode="single_source", location_field="loc_id",
                time_field="year", time_granularity="yearly", metrics={},
                filterable_fields={"loc_id", "year"}, sortable_fields={"loc_id", "year"},
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))
            rows = execute_dataset_query(
                spec, select_columns=["loc_id"], in_filters={"loc_id": []},
            )
        self.assertEqual(rows, [])

    def test_dataset_query_unknown_filter_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "rows.parquet"
            pd.DataFrame([{"loc_id": "USA"}]).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="test", pack_id="test", parquet_name="rows.parquet",
                query_mode="single_source_static", location_field="loc_id",
                time_field=None, time_granularity=None, metrics={},
                filterable_fields={"loc_id"}, sortable_fields={"loc_id"},
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))
            with self.assertRaisesRegex(ValueError, "absent from source"):
                execute_dataset_query(
                    spec, select_columns=["loc_id"], exact_filters={"missing": "value"},
                )

    def test_dataset_query_matches_delimited_hierarchical_region_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "events.parquet"
            pd.DataFrame(
                [
                    {
                        "loc_id": "USA",
                        "affected_loc_ids": "USA-CA-001|USA-CA-037",
                        "timestamp": "2020-01-01T00:00:00Z",
                    },
                    {
                        "loc_id": "USA",
                        "affected_loc_ids": "USA-TX-201",
                        "timestamp": "2020-01-02T00:00:00Z",
                    },
                ]
            ).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="nws_alerts_historical",
                pack_id="nws_alerts",
                parquet_name="events.parquet",
                query_mode="single_source_events",
                location_field="loc_id",
                time_field="timestamp",
                time_granularity="timestamp",
                metrics={
                    "event_count": ApiMetricSpec(
                        metric_id="event_count",
                        column="event_count",
                        description="Count of events matching the applied filters",
                    )
                },
                filterable_fields={"loc_id", "affected_loc_ids", "timestamp"},
                sortable_fields={"loc_id", "timestamp", "event_count"},
                hierarchical_filter_fields=("affected_loc_ids",),
                delimited_hierarchical_filter_fields=("affected_loc_ids",),
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))

            rows = execute_dataset_query(
                spec,
                select_columns=["loc_id", "timestamp", "event_count"],
                hierarchical_prefix_filters={"loc_id": ["USA-CA"]},
                sort_items=[("timestamp", "asc")],
                limit=10,
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_count"], 1)
        self.assertEqual(rows[0]["timestamp"], "2020-01-01T00:00:00Z")

    def test_dataset_query_derives_usa_iso3166_2_prefix_for_admin_spine_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "classification.parquet"
            pd.DataFrame(
                [
                    {"loc_id": "USA-PR-001-000100", "year": 2024, "disadvantaged": True},
                    {"loc_id": "USA-CA-037-000100", "year": 2024, "disadvantaged": False},
                ]
            ).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="cejst_classification",
                pack_id="cejst",
                parquet_name="classification.parquet",
                query_mode="single_source",
                location_field="loc_id",
                time_field="year",
                time_granularity="yearly",
                metrics={
                    "disadvantaged": ApiMetricSpec(
                        metric_id="disadvantaged",
                        column="disadvantaged",
                        description="Disadvantaged community flag",
                    )
                },
                filterable_fields={"loc_id", "year", "disadvantaged"},
                sortable_fields={"loc_id", "year", "disadvantaged"},
                derive_usa_iso3166_2_prefixes=True,
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))

            with patch(
                "mapmover.api_query_runtime._usa_admin1_aliases_for_region_id",
                return_value=("USA-PR",),
            ):
                rows = execute_dataset_query(
                    spec,
                    select_columns=["loc_id", "year", "disadvantaged"],
                    hierarchical_prefix_filters={"loc_id": ["USA-G166186276B86072070009793"]},
                    exact_filters={"year": 2024},
                    limit=10,
                )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["loc_id"], "USA-PR-001-000100")

    def test_dataset_query_derives_geometry_admin1_alias_for_usa_state_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "events.parquet"
            alaska_geometry_id = "USA-G166186276BTEST"
            pd.DataFrame(
                [
                    {"loc_id": f"{alaska_geometry_id}-G252423323B001", "timestamp": "2026-01-01T00:00:00Z", "magnitude": 5.0},
                    {"loc_id": "USA-G166186276BOTHER-G252423323B001", "timestamp": "2026-01-02T00:00:00Z", "magnitude": 4.0},
                ]
            ).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="earthquakes_events",
                pack_id="earthquakes",
                parquet_name="events.parquet",
                query_mode="single_source_events",
                location_field="loc_id",
                time_field="timestamp",
                time_granularity="timestamp",
                metrics={
                    "magnitude": ApiMetricSpec(
                        metric_id="magnitude",
                        column="magnitude",
                        description="Magnitude",
                    )
                },
                filterable_fields={"loc_id", "timestamp"},
                sortable_fields={"loc_id", "timestamp", "magnitude"},
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))

            with patch(
                "mapmover.api_query_runtime._usa_admin1_aliases_for_region_id",
                return_value=(alaska_geometry_id,),
            ):
                rows = execute_dataset_query(
                    spec,
                    select_columns=["loc_id", "timestamp", "magnitude"],
                    hierarchical_prefix_filters={"loc_id": ["USA-AK"]},
                    sort_items=[("magnitude", "desc")],
                    limit=10,
                )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["loc_id"], f"{alaska_geometry_id}-G252423323B001")

    def test_dataset_query_expands_source_owned_filter_value_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            parquet_path = Path(tmp) / "locations.parquet"
            pd.DataFrame(
                [
                    {"loc_id": "DEU", "year": 2026, "facility_type": "fab_lab", "latitude": 1.0},
                    {"loc_id": "DEU", "year": 2026, "facility_type": "hackerspace", "latitude": 2.0},
                    {"loc_id": "DEU", "year": 2026, "facility_type": "prusa_user", "latitude": 3.0},
                ]
            ).to_parquet(parquet_path, index=False)
            spec = ApiSourceSpec(
                source_id="distributed_manufacturing",
                pack_id="distributed_manufacturing",
                parquet_name="locations.parquet",
                query_mode="single_source",
                location_field="loc_id",
                time_field="year",
                time_granularity="yearly",
                metrics={
                    "latitude": ApiMetricSpec(
                        metric_id="latitude",
                        column="latitude",
                        description="Latitude",
                    )
                },
                filterable_fields={"loc_id", "year", "facility_type"},
                sortable_fields={"loc_id", "year", "facility_type", "latitude"},
                filter_value_aliases={
                    "facility_type": {
                        "makerspace": ("makerspace", "fab_lab", "hackerspace"),
                    }
                },
            )
            object.__setattr__(spec, "local_parquet_path", str(parquet_path))

            rows = execute_dataset_query(
                spec,
                select_columns=["loc_id", "year", "latitude"],
                hierarchical_prefix_filters={"loc_id": ["DEU"]},
                exact_filters={"year": 2026, "facility_type": "makerspace"},
                sort_items=[("latitude", "asc")],
                limit=10,
            )

        self.assertEqual([row["latitude"] for row in rows], [1.0, 2.0])

    def test_dataset_query_expands_declared_family_admin_crosswalk(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "classification.parquet"
            crosswalk_path = Path(tmp) / "overlay_tribal_to_admin_3_USA.parquet"
            pd.DataFrame(
                [
                    {"loc_id": "USA-AZ-005-945000", "year": 2024, "disadvantaged": True},
                    {"loc_id": "USA-AZ-005-945100", "year": 2024, "disadvantaged": False},
                    {"loc_id": "USA-CA-037-000100", "year": 2024, "disadvantaged": False},
                ]
            ).to_parquet(source_path, index=False)
            pd.DataFrame(
                [
                    {
                        "source_family": "overlay_tribal",
                        "source_loc_id": "USA-TRIBAL-2430",
                        "source_name": "Navajo Nation",
                        "target_family": "admin",
                        "target_admin_level": "admin_3",
                        "target_loc_id": "USA-AZ-005-945000",
                        "target_name": "Census Tract 9450",
                        "intersection_area": 10.0,
                        "source_area": 100.0,
                        "target_area": 10.0,
                        "source_area_share": 0.7,
                        "target_area_share": 1.0,
                        "rank_by_source_area": 1,
                        "rank_by_target_area": 1,
                        "is_primary": True,
                        "primary_policy": "largest_source_area_share",
                        "source_centroid_target_loc_id": "USA-AZ-005-945000",
                        "relationship_vintage": "test",
                        "area_crs": "EPSG:5070",
                    },
                    {
                        "source_family": "overlay_tribal",
                        "source_loc_id": "USA-TRIBAL-2430",
                        "source_name": "Navajo Nation",
                        "target_family": "admin",
                        "target_admin_level": "admin_3",
                        "target_loc_id": "USA-AZ-005-945100",
                        "target_name": "Census Tract 9451",
                        "intersection_area": 5.0,
                        "source_area": 100.0,
                        "target_area": 10.0,
                        "source_area_share": 0.3,
                        "target_area_share": 0.5,
                        "rank_by_source_area": 2,
                        "rank_by_target_area": 1,
                        "is_primary": False,
                        "primary_policy": "largest_source_area_share",
                        "source_centroid_target_loc_id": "USA-AZ-005-945000",
                        "relationship_vintage": "test",
                        "area_crs": "EPSG:5070",
                    },
                ]
            ).to_parquet(crosswalk_path, index=False)
            spec = ApiSourceSpec(
                source_id="cejst_classification",
                pack_id="cejst",
                parquet_name="classification.parquet",
                query_mode="single_source",
                location_field="loc_id",
                time_field="year",
                time_granularity="yearly",
                metrics={
                    "disadvantaged": ApiMetricSpec(
                        metric_id="disadvantaged",
                        column="disadvantaged",
                        description="Disadvantaged community flag",
                    )
                },
                filterable_fields={"loc_id", "year", "disadvantaged"},
                sortable_fields={"loc_id", "year", "disadvantaged"},
                family_admin_crosswalks=(
                    {
                        "source_family": "overlay_tribal",
                        "target_admin_level": "admin_3",
                        "iso3": "USA",
                        "crosswalk_path": str(crosswalk_path),
                    },
                ),
            )
            object.__setattr__(spec, "local_parquet_path", str(source_path))

            rows = execute_dataset_query(
                spec,
                select_columns=["loc_id", "year", "disadvantaged"],
                hierarchical_prefix_filters={"loc_id": ["USA-TRIBAL-2430"]},
                exact_filters={"year": 2024},
                sort_items=[("loc_id", "asc")],
                limit=10,
            )

        self.assertEqual([row["loc_id"] for row in rows], ["USA-AZ-005-945000", "USA-AZ-005-945100"])

    def test_dataset_query_response_attaches_metric_response_obligations(self):
        from mapmover.routes.api_query import execute_query_dataset_payload

        spec = ApiSourceSpec(
            source_id="tsunamis_events",
            pack_id="tsunamis",
            parquet_name="events.parquet",
            query_mode="single_source_events",
            location_field="loc_id",
            time_field="year",
            time_granularity="yearly",
            metrics={
                "max_water_height_m": ApiMetricSpec(
                    metric_id="max_water_height_m",
                    column="max_water_height_m",
                    description="Maximum reported local water height / runup (m)",
                )
            },
            filterable_fields={"loc_id", "year"},
            sortable_fields={"loc_id", "year", "max_water_height_m"},
        )
        metadata = {
            "metrics": {
                "max_water_height_m": {
                    "years": [-2000, 2026],
                    "countries": 147,
                    "density": 0.62,
                    "response_semantics": {
                        "canonical_term": "reported local water height or runup observation",
                        "required_framing": "These values are reported local observations.",
                    }
                }
            }
        }
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/query/dataset",
                "headers": [(b"accept", b"application/json")],
                "client": ("test", 0),
                "server": ("test", 0),
                "scheme": "http",
                "query_string": b"",
            }
        )
        request.state.research_source_contract = True

        with patch("mapmover.routes.api_query.resolve_pack_source_for_query", return_value=(spec.pack_id, spec.source_id)), patch(
            "mapmover.routes.api_query.get_api_source_spec", return_value=spec
        ), patch(
            "mapmover.routes.api_query.api_source_ready", return_value=True
        ), patch(
            "mapmover.routes.api_query.get_api_source_columns", return_value=["loc_id", "year", "max_water_height_m"]
        ), patch(
            "mapmover.routes.api_query.resolve_effective_time_spec", side_effect=lambda source_spec, _time: source_spec
        ), patch(
            "mapmover.routes.api_query.get_api_source_time_bounds", return_value=(-2000, 2026)
        ), patch(
            "mapmover.routes.api_query.execute_dataset_query",
            return_value=[{"loc_id": "IHO1953-240001003", "year": 1609, "max_water_height_m": 2.5}],
        ), patch(
            "mapmover.routes.api_query.load_source_metadata", return_value=metadata
        ), patch(
            "mapmover.routes.api_query.pack_requires_commercial_access", return_value=False
        ), patch(
            "mapmover.routes.api_query.is_local_loopback_request", return_value=True
        ), patch(
            "mapmover.routes.api_query.log_api_query_event"
        ):
            response = asyncio.run(
                execute_query_dataset_payload(
                    request,
                    {
                        "source_id": "tsunamis_events",
                        "metrics": ["max_water_height_m"],
                        "filters": {"time": {"start": -2000, "end": 2026}},
                        "limit": 1,
                    },
                )
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.body)
        self.assertEqual(
            payload["metric_availability"]["max_water_height_m"],
            {"start": -2000, "end": 2026, "years": [-2000, 2026], "countries": 147, "density": 0.62},
        )
        self.assertEqual(
            payload["response_obligations"][0]["canonical_term"],
            "reported local water height or runup observation",
        )
        self.assertEqual(payload["response_obligations"][0]["required_framing"], "These values are reported local observations.")

    def test_event_qualifier_defaults_are_config_driven_for_single_event_query(self):
        items = [
            {
                "source_id": "earthquakes_events",
                "pack_id": "earthquakes",
                "mode": "events",
                "_hints": {"original_query": "show me the biggest earthquake of all time"},
            }
        ]

        apply_event_qualifier_defaults(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "events",
                "pack_id": "earthquakes",
            },
            load_reference_json=lambda _path: {
                "event_qualifier_defaults": {
                    "earthquakes": {"biggest": "magnitude"},
                    "wildfires": {"biggest": "area_km2"},
                }
            },
        )

        self.assertEqual(items[0]["sort"], {"by": "magnitude", "order": "desc"})
        self.assertEqual(items[0]["limit"], 1)

    def test_event_qualifier_defaults_do_not_force_single_limit_for_plural_query(self):
        items = [
            {
                "source_id": "earthquakes_events",
                "pack_id": "earthquakes",
                "mode": "events",
                "_hints": {"original_query": "show me the largest earthquakes in 2004"},
            }
        ]

        apply_event_qualifier_defaults(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "events",
                "pack_id": "earthquakes",
            },
            load_reference_json=lambda _path: {
                "event_qualifier_defaults": {
                    "earthquakes": {"largest": "magnitude"},
                }
            },
        )

        self.assertEqual(items[0]["sort"], {"by": "magnitude", "order": "desc"})
        self.assertNotIn("limit", items[0])

    def test_event_qualifier_defaults_support_ascending_rank_queries(self):
        items = [
            {
                "source_id": "earthquakes_events",
                "pack_id": "earthquakes",
                "mode": "events",
                "_hints": {"original_query": "show me the smallest earthquake in 2004"},
            }
        ]

        apply_event_qualifier_defaults(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "events",
                "pack_id": "earthquakes",
            },
            load_reference_json=lambda _path: {
                "event_qualifier_defaults": {
                    "earthquakes": {
                        "smallest": {"metric": "magnitude", "order": "asc"},
                    },
                }
            },
        )

        self.assertEqual(items[0]["sort"], {"by": "magnitude", "order": "asc"})
        self.assertEqual(items[0]["limit"], 1)

    def test_default_time_windows_skip_open_ended_all_time_queries(self):
        items = [
            {
                "source_id": "earthquakes_events",
                "_hints": {"original_query": "show me the biggest earthquake of all time"},
            }
        ]

        apply_default_time_windows(
            items,
            load_source_metadata=lambda _source_id: {
                "temporal_coverage": {"start": 1900, "end": 2025}
            },
        )

        self.assertNotIn("year_start", items[0])
        self.assertNotIn("year_end", items[0])
        self.assertTrue(items[0].get("_time_hint_applied"))

    def test_parse_time_filter_uses_utc_year_boundaries_for_temporal_sources(self):
        spec = ApiSourceSpec(
            source_id="earthquakes_events",
            pack_id="earthquakes",
            parquet_name="events.parquet",
            query_mode="single_source",
            location_field="loc_id",
            time_field="timestamp",
            time_granularity="timestamp",
            metrics={},
            filterable_fields={"timestamp"},
            sortable_fields={"timestamp"},
        )

        normalized_time, exact_filters, compare_filters = parse_time_filter(spec, {"year": 2004})

        self.assertEqual(normalized_time["start"], format_year_start(2004))
        self.assertEqual(normalized_time["end"], format_year_end(2004))
        self.assertEqual(exact_filters, {})
        self.assertEqual(
            compare_filters,
            [
                ("timestamp", ">=", format_year_start(2004)),
                ("timestamp", "<=", format_year_end(2004)),
            ],
        )

    def test_parse_time_filter_rejects_partial_or_malformed_temporal_values(self):
        spec = ApiSourceSpec(
            source_id="earthquakes_events",
            pack_id="earthquakes",
            parquet_name="events.parquet",
            query_mode="single_source",
            location_field="loc_id",
            time_field="timestamp",
            time_granularity="timestamp",
            metrics={},
            filterable_fields={"timestamp"},
            sortable_fields={"timestamp"},
        )

        for invalid in ("2024-01", "2026\r-01\r-01", "2000:2024"):
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ValueError, "invalid_temporal_value"
            ):
                parse_time_filter(spec, {"start": invalid, "end": "2024-12-31"})

    def test_single_event_message_formats_timestamp_in_utc(self):
        message = _build_single_event_message(
            "earthquake",
            {
                "magnitude": 9.1,
                "place": "Off the west coast of northern Sumatra",
                "timestamp": "2004-12-26T00:58:53Z",
            },
            query_text="show me the biggest earthquake in 2004",
        )

        self.assertEqual(
            message,
            "The earthquake in 2004 was M 9.1 - Off the west coast of northern Sumatra - Dec 26, 2004 UTC.",
        )

    def test_single_event_message_preserves_smallest_qualifier(self):
        message = _build_single_event_message(
            "earthquake",
            {
                "magnitude": 1.2,
                "place": "Nevada",
                "timestamp": "2004-01-02T00:00:00Z",
            },
            query_text="show me the smallest earthquake in 2004",
        )

        self.assertEqual(
            message,
            "The smallest earthquake in 2004 was M 1.2 - Nevada - Jan 02, 2004 UTC.",
        )

    def test_query_derived_order_hints_convert_acres_to_area_km2(self):
        items = [
            {
                "source_id": "can_wildfires",
                "pack_id": "wildfires",
                "mode": "events",
                "_hints": {
                    "original_query": "show me fires in BC, canada, from 2017 to present, bigger than 1000 acres"
                },
            }
        ]

        apply_query_derived_order_hints(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "events",
                "metrics": {
                    "area_km2": {"name": "Burned area"},
                    "burned_acres": {"name": "Burned acres"},
                },
            },
            hints={
                "query_constraints": {
                    "region_loc_id": "CAN-BC",
                    "area_constraint": {"normalized_value": 4.04686},
                }
            },
        )

        self.assertAlmostEqual(items[0]["filters"]["area_km2_min"], 4.04686, places=5)
        self.assertEqual(items[0]["region"], "CAN-BC")

    def test_query_derived_order_hints_preserve_existing_narrower_area_filter(self):
        items = [
            {
                "source_id": "can_wildfires",
                "pack_id": "wildfires",
                "mode": "events",
                "filters": {"area_km2_min": 10.0},
                "_hints": {
                    "original_query": "show me fires in BC, canada, bigger than 1000 acres"
                },
            }
        ]

        apply_query_derived_order_hints(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "events",
                "metrics": {"area_km2": {"name": "Burned area"}},
            },
            hints={
                "query_constraints": {
                    "region_loc_id": "CAN-BC",
                    "area_constraint": {"normalized_value": 4.04686},
                }
            },
        )

        self.assertEqual(items[0]["filters"]["area_km2_min"], 10.0)
        self.assertEqual(items[0]["region"], "CAN-BC")

    def test_query_derived_order_hints_replace_free_text_region_with_canonical_loc_id(self):
        items = [
            {
                "source_id": "worldpop",
                "region": "Paris, France",
                "_hints": {
                    "original_query": "give me a data point for paris, france"
                },
            }
        ]

        apply_query_derived_order_hints(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "metrics",
                "metrics": {"population": {"name": "Population"}},
            },
            hints={
                "query_constraints": {
                    "region_loc_id": "FRA-G147427",
                }
            },
        )

        self.assertEqual(items[0]["region"], "FRA-G147427")

    def test_query_derived_order_hints_preserve_existing_canonical_region(self):
        items = [
            {
                "source_id": "worldpop",
                "region": "FRA-G147427",
                "_hints": {
                    "original_query": "give me a data point for paris, france"
                },
            }
        ]

        apply_query_derived_order_hints(
            items,
            load_source_metadata=lambda _source_id: {
                "data_type": "metrics",
                "metrics": {"population": {"name": "Population"}},
            },
            hints={
                "query_constraints": {
                    "region_loc_id": "FRA-G147427",
                }
            },
        )

        self.assertEqual(items[0]["region"], "FRA-G147427")

    def test_extract_query_constraints_resolve_subregion_and_area_units(self):
        constraints = extract_query_constraints(
            "show me fires in BC, canada, from 2017 to present, bigger than 1000 acres",
            resolve_admin_text_to_loc_id_func=lambda value, country_hint=None, admin_level_hint=None: (
                {"deepest_resolved_loc_id": "CAN"} if str(value).strip().lower() == "canada"
                else {"deepest_resolved_loc_id": "CAN-BC"}
            ),
            load_reference_file_func=lambda _path: {"iso3_to_name": {"CAN": "Canada"}},
            reference_dir=".",
        )

        self.assertEqual(constraints["region_loc_id"], "CAN-BC")
        self.assertEqual(constraints["location"]["iso3"], "CAN")
        self.assertAlmostEqual(constraints["filters"]["area_km2_min"], 4.04686, places=5)

    def test_extract_query_constraints_resolve_space_separated_subregion_and_country(self):
        def _resolve(value, country_hint=None, admin_level_hint=None):
            normalized = str(value).strip().lower()
            if normalized == "canada":
                return {"deepest_resolved_loc_id": "CAN"}
            if normalized == "ontario":
                return {"deepest_resolved_loc_id": "CAN-ON"}
            return {}

        constraints = extract_query_constraints(
            "show me the fires in ontario canada bigger than 200km2",
            resolve_admin_text_to_loc_id_func=_resolve,
            load_reference_file_func=lambda _path: {"iso3_to_name": {"CAN": "Canada"}},
            reference_dir=".",
        )

        self.assertEqual(constraints["region_loc_id"], "CAN-ON")
        self.assertEqual(constraints["location"]["matched_term"], "ontario")
        self.assertAlmostEqual(constraints["filters"]["area_km2_min"], 200.0, places=5)

    def test_extract_query_constraints_does_not_force_admin_level_one_for_subregions(self):
        calls = []

        def _resolve(value, country_hint=None, admin_level_hint=None):
            calls.append(
                {
                    "value": str(value).strip().lower(),
                    "country_hint": country_hint,
                    "admin_level_hint": admin_level_hint,
                }
            )
            normalized = str(value).strip().lower()
            if normalized == "canada":
                return {"deepest_resolved_loc_id": "CAN"}
            if normalized == "toronto":
                return {"deepest_resolved_loc_id": "CAN-ON-TOR"}
            return {}

        constraints = extract_query_constraints(
            "show me fires in toronto canada bigger than 1 km2",
            resolve_admin_text_to_loc_id_func=_resolve,
            load_reference_file_func=lambda _path: {"iso3_to_name": {"CAN": "Canada"}},
            reference_dir=".",
        )

        self.assertEqual(constraints["region_loc_id"], "CAN-ON-TOR")
        self.assertEqual(calls[0]["admin_level_hint"], 0)
        self.assertIsNone(calls[-1]["admin_level_hint"])

    def test_partition_region_filter_codes_keeps_subnational_loc_ids_as_prefixes(self):
        prefixes, countries = partition_region_filter_codes(
            ["CAN-BC", "USA-CA-037", "CAN", "USA", "EEZ-CAN", "XNA"]
        )

        self.assertEqual(prefixes, ["CAN-BC", "USA-CA-037", "EEZ-CAN", "XNA"])
        self.assertEqual(countries, ["CAN", "USA"])


if __name__ == "__main__":
    unittest.main()
