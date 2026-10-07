"""
Tests for CoverageClaim (Task L4, coverage_ledger_implementation.md).

These transliterate the JS reference test vectors in
tests/js/coverage-ledger.test.mjs wherever a single-claim equivalent
exists, so both sides provably agree axis-by-axis on:
- normalization + validation,
- containment (covers()) per axis: source, metrics, geo_level, scope,
  time, filters (including the seeded/ignore_filters exceptions),
- diff() along the time and loc_ids axes plus the over-fetch fallback,
- JSON round-trip against the JS wire shape,
- the CacheSignature <-> CoverageClaim bridge conversions.

Run with: python -m pytest tests/test_coverage_claim.py -v
"""

from __future__ import annotations

import unittest

from mapmover.cache_signature import (
    CacheSignature,
    ClaimScope,
    ClaimTime,
    CoverageClaim,
    SEEDED_FILTERS,
)


def base_claim(**overrides) -> CoverageClaim:
    fields = {
        "source": "nri",
        "metrics": "*",
        "geo_level": None,
        "scope": ClaimScope(kind="all"),
        "time": ClaimTime(kind="all"),
        "filters": "",
        "version": None,
    }
    fields.update(overrides)
    return CoverageClaim(**fields)


def ymd(year: int, month: int, day: int) -> int:
    import calendar

    return calendar.timegm((year, month, day, 0, 0, 0, 0, 0, 0)) * 1000


DAY_MS = 24 * 60 * 60 * 1000


class NormalizationTests(unittest.TestCase):
    def test_sorts_dedupes_metrics_loc_ids_years_without_rejecting(self):
        claim = base_claim(
            metrics=["b", "a", "b"],
            scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-CA-001", "USA-VA-059"]),
            time=ClaimTime(kind="years", years=[2021, 2019, 2020, 2019]),
        )
        self.assertEqual(claim.metrics, frozenset(["a", "b"]))
        self.assertEqual(claim.scope.value, frozenset(["USA-CA-001", "USA-VA-059"]))
        self.assertEqual(claim.time.years, frozenset([2019, 2020, 2021]))

    def test_rejects_empty_metrics_collection(self):
        with self.assertRaises(ValueError):
            base_claim(metrics=[])

    def test_rejects_range_with_min_greater_than_max(self):
        with self.assertRaises(ValueError):
            base_claim(time=ClaimTime(kind="range", min=100, max=50))

    def test_rejects_missing_invalid_source(self):
        with self.assertRaises(ValueError):
            base_claim(source="")

    def test_rejects_unknown_scope_time_kind(self):
        with self.assertRaises(ValueError):
            ClaimScope(kind="bogus")
        with self.assertRaises(ValueError):
            ClaimTime(kind="bogus")

    def test_stamps_time_normalizes_unsorted_dupes_rejects_empty(self):
        claim = base_claim(time=ClaimTime(kind="stamps", stamps=[300, 100, 300, 200]))
        self.assertEqual(claim.time.stamps, frozenset([100, 200, 300]))
        with self.assertRaises(ValueError):
            ClaimTime(kind="stamps", stamps=[])


class JsonRoundTripTests(unittest.TestCase):
    def test_to_json_from_json_round_trip(self):
        claim = base_claim(
            source="a",
            time=ClaimTime(kind="range", min=0, max=100),
        )
        json_dict = claim.to_json_dict()
        self.assertEqual(
            json_dict,
            {
                "source": "a",
                "metrics": "*",
                "geoLevel": None,
                "scope": {"kind": "all"},
                "time": {"kind": "range", "min": 0, "max": 100},
                "filters": "",
                "version": None,
            },
        )
        restored = CoverageClaim.from_json_dict(json_dict)
        self.assertEqual(restored, claim)

    def test_json_shape_matches_js_key_names_for_region_and_loc_ids(self):
        region_claim = base_claim(scope=ClaimScope(kind="region", value="USA-VA"))
        self.assertEqual(region_claim.to_json_dict()["scope"], {"kind": "region", "value": "USA-VA"})

        loc_ids_claim = base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-CA-001"]))
        self.assertEqual(
            loc_ids_claim.to_json_dict()["scope"],
            {"kind": "locIds", "value": ["USA-CA-001", "USA-VA-059"]},
        )

    def test_json_shape_years_and_geo_level_and_metrics_array(self):
        claim = base_claim(
            metrics=["b", "a"],
            geo_level="admin_2",
            time=ClaimTime(kind="years", years=[2021, 2019]),
        )
        json_dict = claim.to_json_dict()
        self.assertEqual(json_dict["metrics"], ["a", "b"])
        self.assertEqual(json_dict["geoLevel"], "admin_2")
        self.assertEqual(json_dict["time"], {"kind": "years", "years": [2019, 2021]})

    def test_stamps_time_json_round_trip_matches_js_key_names(self):
        claim = base_claim(source="raster", time=ClaimTime(kind="stamps", stamps=[300, 100, 200]))
        json_dict = claim.to_json_dict()
        self.assertEqual(json_dict["time"], {"kind": "stamps", "stamps": [100, 200, 300]})
        restored = CoverageClaim.from_json_dict(json_dict)
        self.assertEqual(restored, claim)


class ContainmentSourceMetricsGeoLevelTests(unittest.TestCase):
    def test_source_is_strict_equality(self):
        held = base_claim(source="nri")
        self.assertTrue(held.covers(base_claim(source="nri")))
        self.assertFalse(held.covers(base_claim(source="owid")))

    def test_metrics_rules(self):
        cases = [
            ("*", "*", True),
            ("*", ["a"], True),
            (["a", "b"], "*", False),  # need '*' only covered by held '*'
            (["a", "b"], ["a"], True),
            (["a"], ["a", "b"], False),
        ]
        for held_metrics, need_metrics, expected in cases:
            held = base_claim(metrics=held_metrics)
            need = base_claim(metrics=need_metrics)
            self.assertEqual(held.covers(need), expected, (held_metrics, need_metrics))

    def test_geo_level_strict_equality_non_transitive(self):
        held = base_claim(geo_level="admin_2")
        self.assertTrue(held.covers(base_claim(geo_level="admin_2")))
        self.assertFalse(held.covers(base_claim(geo_level="admin_1")))
        self.assertFalse(held.covers(base_claim(geo_level=None)))

        held_null = base_claim(geo_level=None)
        self.assertTrue(held_null.covers(base_claim(geo_level=None)))
        self.assertFalse(held_null.covers(base_claim(geo_level="admin_2")))


class ContainmentScopeTests(unittest.TestCase):
    def test_scope_all_covers_everything_only_all_covers_all(self):
        held = base_claim(scope=ClaimScope(kind="all"))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="all"))))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="region", value="USA-VA"))))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]))))

        region = base_claim(scope=ClaimScope(kind="region", value="USA-VA"))
        self.assertFalse(region.covers(base_claim(scope=ClaimScope(kind="all"))))

    def test_region_prefix_rule(self):
        held = base_claim(scope=ClaimScope(kind="region", value="USA-VA"))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="region", value="USA-VA"))))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]))))
        self.assertFalse(held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VAX"]))))
        self.assertFalse(held.covers(base_claim(scope=ClaimScope(kind="region", value="USA-VAX"))))
        self.assertFalse(
            held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-VAX"]))),
            "one uncovered id in the batch means the whole need is not covered",
        )

    def test_loc_ids_covers_loc_ids_by_superset(self):
        held = base_claim(
            scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-VA-013", "USA-CA-001"])
        )
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]))))
        self.assertFalse(
            held.covers(base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-TX-001"])))
        )

    def test_bbox_v1_only_all_or_identical_bbox_covers_bbox(self):
        held = base_claim(scope=ClaimScope(kind="bbox", value=[-80, 36, -75, 39]))
        self.assertTrue(held.covers(base_claim(scope=ClaimScope(kind="bbox", value=[-80, 36, -75, 39]))))
        self.assertFalse(held.covers(base_claim(scope=ClaimScope(kind="bbox", value=[-79, 36, -75, 39]))))


class ContainmentFiltersTests(unittest.TestCase):
    def test_filters_strict_equality_by_default(self):
        held = base_claim(filters="min_severity=3")
        self.assertTrue(held.covers(base_claim(filters="min_severity=3")))
        self.assertFalse(held.covers(base_claim(filters="min_severity=4")))
        self.assertFalse(held.covers(base_claim(filters="")))

    def test_ignore_filters_bypasses_the_filters_axis(self):
        held = base_claim(filters="min_severity=3")
        self.assertTrue(held.covers(base_claim(filters="min_severity=999"), ignore_filters=True))

    def test_seeded_never_satisfies_a_non_ignore_filters_need(self):
        held = base_claim(filters=SEEDED_FILTERS)
        self.assertFalse(held.covers(base_claim(filters="")))
        self.assertFalse(held.covers(base_claim(filters="min_severity=3")))
        self.assertTrue(held.covers(base_claim(filters="min_severity=3"), ignore_filters=True))


class ContainmentTimeTests(unittest.TestCase):
    def test_time_matrix(self):
        range_2020 = ClaimTime(kind="range", min=ymd(2020, 1, 1), max=ymd(2021, 1, 1) - 1)
        years_full = ClaimTime(kind="years", years=[2019, 2020])

        cases = [
            (ClaimTime(kind="all"), ClaimTime(kind="all"), True),
            (ClaimTime(kind="all"), range_2020, True),
            (ClaimTime(kind="all"), ClaimTime(kind="years", years=[2020]), True),
            (range_2020, ClaimTime(kind="all"), False),
            (range_2020, range_2020, True),
            (range_2020, ClaimTime(kind="years", years=[2020]), True),
            (range_2020, ClaimTime(kind="years", years=[2019]), False),
            (years_full, ClaimTime(kind="years", years=[2020]), True),
            (years_full, ClaimTime(kind="years", years=[2021]), False),
            (years_full, range_2020, False),  # years does NOT cover range in v1
        ]
        for held_time, need_time, expected in cases:
            held = base_claim(time=held_time)
            need = base_claim(time=need_time)
            self.assertEqual(held.covers(need), expected, (held_time, need_time))

    def test_range_covers_years_requires_full_year_span(self):
        held = base_claim(time=ClaimTime(kind="range", min=ymd(2020, 1, 1), max=ymd(2021, 6, 30)))
        self.assertTrue(held.covers(base_claim(time=ClaimTime(kind="years", years=[2020]))))
        self.assertFalse(held.covers(base_claim(time=ClaimTime(kind="years", years=[2021]))))

    def test_stamps_matrix_v1_1_addendum(self):
        range_2020 = ClaimTime(kind="range", min=ymd(2020, 1, 1), max=ymd(2021, 1, 1) - 1)
        years_full = ClaimTime(kind="years", years=[2019, 2020])
        stamps_held = ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1), ymd(2020, 7, 1)])

        cases = [
            (ClaimTime(kind="all"), ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1)]), True, "'all' covers stamps"),
            (
                range_2020,
                ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1), ymd(2020, 7, 1)]),
                True,
                "range covers stamps when every stamp lies in [min,max]",
            ),
            (
                range_2020,
                ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1), ymd(2021, 6, 1)]),
                False,
                "range does not cover a stamp outside its span",
            ),
            (
                stamps_held,
                ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1)]),
                True,
                "stamps covers stamps by superset",
            ),
            (
                stamps_held,
                ClaimTime(kind="stamps", stamps=[ymd(2020, 6, 1), ymd(2020, 8, 1)]),
                False,
                "stamps does not cover a stamp it does not hold",
            ),
            (stamps_held, range_2020, False, "stamps does NOT cover range"),
            (stamps_held, years_full, False, "stamps does NOT cover years"),
            (
                years_full,
                ClaimTime(kind="stamps", stamps=[ymd(2019, 1, 1)]),
                False,
                "years does NOT cover stamps (an instant vs a bucket)",
            ),
            (stamps_held, ClaimTime(kind="all"), False, "'all' need only covered by held 'all'"),
        ]
        for held_time, need_time, expected, note in cases:
            held = base_claim(time=held_time)
            need = base_claim(time=need_time)
            self.assertEqual(held.covers(need), expected, note)


class DiffTests(unittest.TestCase):
    def test_fully_covered_need_returns_empty_list(self):
        held = base_claim(time=ClaimTime(kind="range", min=0, max=1000))
        need = base_claim(time=ClaimTime(kind="range", min=100, max=500))
        self.assertEqual(held.diff(need), [])

    def test_time_axis_range_remainder_splits_into_up_to_two_ranges(self):
        held = base_claim(time=ClaimTime(kind="range", min=100, max=200))
        need = base_claim(time=ClaimTime(kind="range", min=0, max=300))
        result = held.diff(need)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].time, ClaimTime(kind="range", min=0, max=99))
        self.assertEqual(result[1].time, ClaimTime(kind="range", min=201, max=300))
        for claim in result:
            self.assertEqual(claim.source, "nri")
            self.assertEqual(claim.scope, ClaimScope(kind="all"))

    def test_time_axis_range_remainder_on_one_side_only(self):
        held = base_claim(time=ClaimTime(kind="range", min=0, max=200))
        need = base_claim(time=ClaimTime(kind="range", min=0, max=300))
        result = held.diff(need)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].time, ClaimTime(kind="range", min=201, max=300))

    def test_time_axis_missing_year_set(self):
        held = base_claim(time=ClaimTime(kind="years", years=[2019, 2021]))
        need = base_claim(time=ClaimTime(kind="years", years=[2019, 2020, 2021, 2022]))
        result = held.diff(need)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].time, ClaimTime(kind="years", years=frozenset([2020, 2022])))

    def test_time_axis_stamps_set_difference(self):
        held = base_claim(time=ClaimTime(kind="stamps", stamps=[100, 300]))
        need = base_claim(time=ClaimTime(kind="stamps", stamps=[100, 200, 300, 400]))
        result = held.diff(need)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].time, ClaimTime(kind="stamps", stamps=frozenset([200, 400])))

    def test_time_axis_stamps_need_paired_with_non_stamps_held_falls_back_to_over_fetch(self):
        # Held claim matches every other axis but its range does not contain
        # the needed stamps, so covers() is false; a stamps need is only ever
        # satisfied (fully or partially) by stamps-kind held claims, so this
        # must not attempt a set-difference against the range -- it must
        # return the need unchanged (over-fetch fallback).
        held = base_claim(time=ClaimTime(kind="range", min=0, max=50))
        need = base_claim(time=ClaimTime(kind="stamps", stamps=[100, 200]))
        result = held.diff(need)
        self.assertEqual(result, [need])

    def test_time_axis_range_need_paired_with_stamps_only_held_falls_back_to_over_fetch(self):
        held = base_claim(time=ClaimTime(kind="stamps", stamps=[100, 200]))
        need = base_claim(time=ClaimTime(kind="range", min=0, max=1000))
        result = held.diff(need)
        self.assertEqual(result, [need])

    def test_loc_ids_axis_missing_loc_ids_when_all_other_axes_contained(self):
        held = base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]))
        need = base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-CA-001"]))
        result = held.diff(need)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].scope, ClaimScope(kind="loc_ids", value=["USA-CA-001"]))

    def test_loc_ids_axis_region_claim_can_satisfy_part_of_a_loc_ids_need(self):
        held = base_claim(scope=ClaimScope(kind="region", value="USA-VA"))
        need = base_claim(scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-CA-001"]))
        result = held.diff(need)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].scope, ClaimScope(kind="loc_ids", value=["USA-CA-001"]))

    def test_deliberate_over_fetch_fallback_when_more_than_one_axis_is_partial(self):
        held = base_claim(
            scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]),
            time=ClaimTime(kind="range", min=0, max=100),
        )
        need = base_claim(
            scope=ClaimScope(kind="loc_ids", value=["USA-VA-059", "USA-CA-001"]),
            time=ClaimTime(kind="range", min=0, max=200),
        )
        result = held.diff(need)
        self.assertEqual(result, [need])

    def test_nothing_held_that_matches_returns_the_need_unchanged(self):
        held = base_claim(source="other-source")
        need = base_claim(time=ClaimTime(kind="range", min=0, max=100))
        self.assertEqual(held.diff(need), [need])


class CacheSignatureBridgeTests(unittest.TestCase):
    def test_cache_signature_to_claim_round_trips_through_to_legacy_signature(self):
        sig = CacheSignature(
            loc_ids=frozenset(["USA-VA-059", "USA-CA-001"]),
            years=frozenset([2019, 2020]),
            metrics=frozenset(["population", "gdp"]),
            source_id="owid_co2",
        )
        claim = sig.to_claim()
        self.assertEqual(claim.source, "owid_co2")
        self.assertEqual(claim.metrics, frozenset(["population", "gdp"]))
        self.assertEqual(claim.scope, ClaimScope(kind="loc_ids", value=frozenset(["USA-VA-059", "USA-CA-001"])))
        self.assertEqual(claim.time, ClaimTime(kind="years", years=frozenset([2019, 2020])))
        self.assertIsNone(claim.geo_level)
        self.assertEqual(claim.filters, "")
        self.assertIsNone(claim.version)

        restored = claim.to_legacy_signature()
        self.assertEqual(restored.loc_ids, sig.loc_ids)
        self.assertEqual(restored.years, sig.years)
        self.assertEqual(restored.metrics, sig.metrics)
        self.assertEqual(restored.source_id, sig.source_id)

    def test_to_claim_requires_a_source(self):
        sig = CacheSignature(loc_ids=frozenset(), years=frozenset(), metrics=frozenset())
        with self.assertRaises(ValueError):
            sig.to_claim()

    def test_to_legacy_signature_rejects_star_metrics(self):
        claim = base_claim(scope=ClaimScope(kind="loc_ids", value=[]), time=ClaimTime(kind="years", years=[]))
        with self.assertRaises(ValueError):
            claim.to_legacy_signature()

    def test_to_legacy_signature_rejects_non_loc_ids_scope_and_non_years_time(self):
        region_claim = base_claim(metrics=["a"], scope=ClaimScope(kind="region", value="USA-VA"))
        with self.assertRaises(ValueError):
            region_claim.to_legacy_signature()

        range_claim = base_claim(
            metrics=["a"],
            scope=ClaimScope(kind="loc_ids", value=["USA-VA-059"]),
            time=ClaimTime(kind="range", min=0, max=100),
        )
        with self.assertRaises(ValueError):
            range_claim.to_legacy_signature()


if __name__ == "__main__":
    unittest.main()
