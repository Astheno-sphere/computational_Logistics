"""Shared runtime metric alias bundles.

These aliases are still hand-maintained and should eventually be reviewed for
possible source metadata ownership.
"""

from __future__ import annotations

from typing import Optional

from mapmover.runtime.metric_matching import find_metric_column_generic


RUNTIME_METRIC_ALIAS_CANDIDATES = {
    "event count": ["event_count"],
    "frequency": ["event_count"],
    "tornado count": ["event_count", "tornado_count"],
    "earthquake count": ["event_count"],
    "hurricane count": ["event_count"],
    "wildfire count": ["event_count"],
    "tsunami count": ["event_count"],
    "railways length": [
        "railways_km", "railway_km", "railways_length_km", "railways_length", "railways",
    ],
    "railway length": [
        "railways_km", "railway_km", "railways_length_km", "railways_length", "railways",
    ],
    "life expectancy": [
        "life_expectancy", "life_expectancy_years", "life_expectancy_at_birth",
    ],
    "gdp per capita": [
        "gdp_per_capita", "gdp_per_capita_ppp", "gdp_per_capita_usd", "gdp_per_capita_ppp_usd",
    ],
    "birth rate": [
        "birth_rate", "birth_rate_per_1000", "births_per_1000_population", "crude_birth_rate",
    ],
    "highest peaks": ["highest_point_m"],
    "highest peak": ["highest_point_m"],
    "coastline length": ["coastline_km"],
    "coastline": ["coastline_km"],
}


RUNTIME_METRIC_ALIAS_TERM_BUNDLES = {
    "event count": [{"event", "count"}],
    "frequency": [{"event", "count"}],
    "tornado count": [{"event", "count"}, {"tornado", "count"}],
    "earthquake count": [{"event", "count"}, {"earthquake", "count"}],
    "hurricane count": [{"event", "count"}, {"hurricane", "count"}],
    "wildfire count": [{"event", "count"}, {"wildfire", "count"}],
    "tsunami count": [{"event", "count"}, {"tsunami", "count"}],
    "railways length": [{"railways"}, {"railway"}, {"railways", "km"}],
    "railway length": [{"railways"}, {"railway"}, {"railway", "km"}],
    "life expectancy": [{"life", "expectancy"}],
    "gdp per capita": [{"gdp", "capita"}, {"income", "capita"}],
    "birth rate": [{"birth", "rate"}, {"births", "rate"}],
    "highest peaks": [{"highest", "point"}, {"peak"}],
    "highest peak": [{"highest", "point"}, {"peak"}],
    "coastline length": [{"coastline"}, {"coast", "length"}],
    "coastline": [{"coastline"}],
}


def find_runtime_metric_column(df, metric: str, metadata: Optional[dict] = None) -> Optional[str]:
    return find_metric_column_generic(
        df,
        metric,
        metadata,
        alias_candidates=RUNTIME_METRIC_ALIAS_CANDIDATES,
        alias_term_bundles=RUNTIME_METRIC_ALIAS_TERM_BUNDLES,
    )
