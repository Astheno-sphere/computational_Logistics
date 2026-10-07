"""
Cache Signature System - Unified data identification across cache layers.

This module provides:
- CacheSignature: Identifies what data is in a cache (loc_ids, years, metrics)
- DataPackage: Container for data with its signature, supports export
- CacheInventory: Tracks what's loaded across the system

The loc_id system is the canonical identifier:
    {ISO3}[-{admin1}[-{admin2}]]

Examples:
    USA         - United States (country)
    USA-CA      - California (admin1)
    USA-CA-037  - Los Angeles County (admin2)

Usage:
    # Create signature from data
    sig = CacheSignature.from_data(records, source_id="owid_co2")

    # Check if cache can serve a request
    if cached_sig.contains(requested_sig):
        # Serve from cache
    else:
        # Fetch delta
        delta = requested_sig.subtract(cached_sig)
"""

from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union
import calendar
import json
import math


@dataclass(frozen=True)
class CacheSignature:
    """
    Immutable signature identifying what data is in a cache.

    The three axes of data identification:
    1. loc_ids: Which locations (using canonical loc_id format)
    2. years: Which years are present (as a set, not range - shows gaps)
    3. metrics: Which metrics/columns

    Optionally tracks source_id for multi-source caches.

    Using FrozenSet[int] for years instead of year_start/year_end because:
    - Shows gaps: If data has 2018, 2020, 2022 but not 2019, 2021 - signature shows this
    - Sparse data: Some sources have irregular years (1990, 2000, 2010, 2020)
    - Precision: contains() check is exact, not approximate
    """

    loc_ids: FrozenSet[str]
    years: FrozenSet[int]
    metrics: FrozenSet[str]
    source_id: Optional[str] = None

    @classmethod
    def from_data(
        cls,
        records: List[Dict],
        source_id: str = None,
        loc_id_field: str = "loc_id",
        year_field: str = "year"
    ) -> "CacheSignature":
        """
        Create signature by inspecting actual data records.

        Args:
            records: List of data dictionaries with loc_id, year, and metrics
            source_id: Optional source identifier
            loc_id_field: Field name for location ID (default: "loc_id")
            year_field: Field name for year (default: "year")

        Returns:
            CacheSignature describing the data
        """
        if not records:
            return cls(
                loc_ids=frozenset(),
                years=frozenset(),
                metrics=frozenset(),
                source_id=source_id
            )

        loc_ids = set()
        years = set()
        metrics = set()

        # Reserved fields that are not metrics
        reserved = {loc_id_field, year_field, "geometry", "_id", "properties"}

        for record in records:
            if loc_id_field in record:
                loc_ids.add(record[loc_id_field])
            if year_field in record:
                year_val = record[year_field]
                if isinstance(year_val, (int, float)) and year_val > 0:
                    years.add(int(year_val))

            # Collect metric fields
            for key in record.keys():
                if key not in reserved and not key.startswith("_"):
                    metrics.add(key)

        return cls(
            loc_ids=frozenset(loc_ids),
            years=frozenset(years),
            metrics=frozenset(metrics),
            source_id=source_id
        )

    @classmethod
    def from_order_items(cls, items: List[Dict]) -> "CacheSignature":
        """
        Create signature from order items (preprocessor output).

        Args:
            items: List of order items with source_id, metric, region, year/year_start/year_end

        Returns:
            CacheSignature describing what the order requests
        """
        loc_ids = set()
        years = set()
        metrics = set()
        source_ids = set()

        for item in items:
            # Collect metrics
            if "metric" in item:
                metrics.add(item["metric"])

            # Collect source_ids
            if "source_id" in item:
                source_ids.add(item["source_id"])

            # Collect loc_ids from region (may be expanded list or single value)
            region = item.get("region")
            if region:
                if isinstance(region, list):
                    loc_ids.update(region)
                else:
                    loc_ids.add(region)

            # Collect years - can be single year or range
            if "year" in item and item["year"]:
                years.add(int(item["year"]))
            if "year_start" in item and "year_end" in item:
                start = item.get("year_start")
                end = item.get("year_end")
                if start and end:
                    # Expand range into individual years
                    years.update(range(int(start), int(end) + 1))
            elif "year_start" in item and item["year_start"]:
                years.add(int(item["year_start"]))
            elif "year_end" in item and item["year_end"]:
                years.add(int(item["year_end"]))

        return cls(
            loc_ids=frozenset(loc_ids),
            years=frozenset(years),
            metrics=frozenset(metrics),
            source_id=list(source_ids)[0] if len(source_ids) == 1 else None
        )

    def contains(self, other: "CacheSignature") -> bool:
        """
        Check if this signature fully contains another.

        Returns True if this cache can serve all data requested by other.
        All checks are set subset operations - O(n) where n = smaller set.
        """
        # Check loc_ids
        if not other.loc_ids.issubset(self.loc_ids):
            return False

        # Check years - exact check, shows gaps
        if not other.years.issubset(self.years):
            return False

        # Check metrics
        if not other.metrics.issubset(self.metrics):
            return False

        return True

    def subtract(self, other: "CacheSignature") -> "CacheSignature":
        """
        Calculate what's in self but NOT in other (the delta to fetch).

        Returns a signature representing the missing data.
        """
        missing_locs = self.loc_ids - other.loc_ids
        missing_years = self.years - other.years
        missing_metrics = self.metrics - other.metrics

        return CacheSignature(
            loc_ids=missing_locs if missing_locs else self.loc_ids,
            years=missing_years if missing_years else self.years,
            metrics=missing_metrics if missing_metrics else self.metrics,
            source_id=self.source_id
        )

    def merge(self, other: "CacheSignature") -> "CacheSignature":
        """
        Merge two signatures (union of data).
        """
        return CacheSignature(
            loc_ids=self.loc_ids | other.loc_ids,
            years=self.years | other.years,
            metrics=self.metrics | other.metrics,
            source_id=self.source_id if self.source_id == other.source_id else None
        )

    def is_empty(self) -> bool:
        """Check if signature represents no data."""
        return len(self.loc_ids) == 0 and len(self.years) == 0 and len(self.metrics) == 0

    def to_dict(self) -> Dict:
        """Serialize to dictionary for transport."""
        return {
            "loc_ids": sorted(self.loc_ids),
            "years": sorted(self.years),
            "metrics": sorted(self.metrics),
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CacheSignature":
        """Deserialize from dictionary."""
        return cls(
            loc_ids=frozenset(data.get("loc_ids", [])),
            years=frozenset(data.get("years", [])),
            metrics=frozenset(data.get("metrics", [])),
            source_id=data.get("source_id"),
        )

    def summary(self) -> str:
        """Human-readable summary."""
        loc_count = len(self.loc_ids)
        metric_count = len(self.metrics)
        year_count = len(self.years)
        if year_count == 0:
            year_str = "no years"
        elif year_count <= 5:
            year_str = f"years {sorted(self.years)}"
        else:
            years_sorted = sorted(self.years)
            year_str = f"{year_count} years ({years_sorted[0]}-{years_sorted[-1]})"
        return f"{loc_count} locations, {metric_count} metrics, {year_str}"

    def year_range(self) -> Tuple[int, int]:
        """Get min/max years as tuple (for compatibility)."""
        if not self.years:
            return (0, 0)
        years_sorted = sorted(self.years)
        return (years_sorted[0], years_sorted[-1])

    def to_claim(self, source: str = None) -> "CoverageClaim":
        """
        Bridge: convert this legacy signature into a CoverageClaim.

        Lossless mapping (v1 bridge, see Task L4 in
        coverage_ledger_implementation.md):
        - loc_ids -> scope {kind: "loc_ids", value: loc_ids}
        - years   -> time  {kind: "years", years: years}
        - metrics -> explicit metrics set ('*' only if this signature has
          no metrics recorded -- an empty metrics set has no CoverageClaim
          equivalent, so it is broadened to '*' rather than raising).

        geo_level, filters, and version have no legacy equivalent and are
        left at their CoverageClaim defaults (None / "" / None).
        """
        resolved_source = source or self.source_id
        if not resolved_source:
            raise ValueError(
                "CacheSignature.to_claim: source is required (pass source= or set source_id)"
            )
        metrics: Union[str, FrozenSet[str]] = "*" if not self.metrics else frozenset(self.metrics)
        return CoverageClaim(
            source=resolved_source,
            metrics=metrics,
            scope=ClaimScope(kind="loc_ids", value=frozenset(self.loc_ids)),
            time=ClaimTime(kind="years", years=frozenset(self.years)),
        )


@dataclass
class DataPackage:
    """
    Container for data with its signature.

    Enables:
    - Tracking what data is loaded
    - Export to CSV/Parquet
    - Verification against other caches
    """

    signature: CacheSignature
    records: List[Dict]
    metadata: Dict = field(default_factory=dict)

    @classmethod
    def from_records(
        cls,
        records: List[Dict],
        source_id: str = None,
        metadata: Dict = None
    ) -> "DataPackage":
        """Create package from records, auto-computing signature."""
        sig = CacheSignature.from_data(records, source_id=source_id)
        return cls(
            signature=sig,
            records=records,
            metadata=metadata or {}
        )

    def filter(
        self,
        loc_ids: Set[str] = None,
        years: Set[int] = None,
        year_start: int = None,
        year_end: int = None,
        metrics: Set[str] = None
    ) -> "DataPackage":
        """
        Filter package to subset of data.

        Args:
            loc_ids: Filter to these location IDs
            years: Filter to these specific years (set)
            year_start: Filter to years >= this value
            year_end: Filter to years <= this value
            metrics: Filter columns (not yet implemented)

        Returns new DataPackage with filtered records and updated signature.
        """
        filtered = self.records

        if loc_ids:
            filtered = [r for r in filtered if r.get("loc_id") in loc_ids]

        if years:
            filtered = [r for r in filtered if r.get("year") in years]

        if year_start is not None:
            filtered = [r for r in filtered if r.get("year", 0) >= year_start]

        if year_end is not None:
            filtered = [r for r in filtered if r.get("year", 9999) <= year_end]

        # Note: metric filtering would need column selection logic
        # For now, just filter rows

        return DataPackage.from_records(
            filtered,
            source_id=self.signature.source_id,
            metadata=self.metadata
        )

    def to_csv_rows(self) -> List[Dict]:
        """
        Prepare records for CSV export.

        Returns list of flat dictionaries suitable for csv.DictWriter.
        """
        if not self.records:
            return []

        # Flatten any nested structures
        rows = []
        for record in self.records:
            row = {}
            for key, value in record.items():
                if isinstance(value, dict):
                    # Flatten nested dict with prefix
                    for k, v in value.items():
                        row[f"{key}_{k}"] = v
                elif isinstance(value, (list, tuple)):
                    row[key] = json.dumps(value)
                else:
                    row[key] = value
            rows.append(row)

        return rows

    def get_columns(self) -> List[str]:
        """Get all column names from records."""
        if not self.records:
            return []

        columns = set()
        for record in self.records:
            columns.update(record.keys())

        # Order: loc_id, year first, then sorted metrics
        priority = ["loc_id", "year"]
        result = [c for c in priority if c in columns]
        result.extend(sorted(c for c in columns if c not in priority))
        return result

    def verify_against(self, other_sig: CacheSignature) -> Dict:
        """
        Verify this package against another signature.

        Returns dict with:
        - matches: bool
        - missing_locs: set of loc_ids in other but not here
        - extra_locs: set of loc_ids here but not in other
        - year_coverage: dict with comparison
        - metric_coverage: dict with comparison
        """
        my_sig = self.signature

        return {
            "matches": my_sig.contains(other_sig) and other_sig.contains(my_sig),
            "missing_locs": list(other_sig.loc_ids - my_sig.loc_ids),
            "extra_locs": list(my_sig.loc_ids - other_sig.loc_ids),
            "year_coverage": {
                "self_years": sorted(my_sig.years),
                "other_years": sorted(other_sig.years),
                "self_covers_other": other_sig.years.issubset(my_sig.years),
                "missing_years": sorted(other_sig.years - my_sig.years),
                "extra_years": sorted(my_sig.years - other_sig.years),
            },
            "metric_coverage": {
                "self": list(my_sig.metrics),
                "other": list(other_sig.metrics),
                "missing": list(other_sig.metrics - my_sig.metrics),
                "extra": list(my_sig.metrics - other_sig.metrics),
            }
        }


class CacheInventory:
    """
    Tracks what data is loaded in a cache layer.

    Each layer (backend, order_taker, frontend) can have its own inventory.
    Supports checking coverage and computing deltas.
    """

    def __init__(self, name: str = "unnamed"):
        self.name = name
        self._packages: Dict[str, DataPackage] = {}  # key -> package
        self._signatures: Dict[str, CacheSignature] = {}  # key -> signature

    def add(self, key: str, package: DataPackage):
        """Add or update a data package."""
        self._packages[key] = package
        self._signatures[key] = package.signature

    def add_signature(self, key: str, signature: CacheSignature):
        """Add just a signature (when we don't have the full data)."""
        self._signatures[key] = signature

    def get(self, key: str) -> Optional[DataPackage]:
        """Get package by key."""
        return self._packages.get(key)

    def get_signature(self, key: str) -> Optional[CacheSignature]:
        """Get signature by key."""
        return self._signatures.get(key)

    def has(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._signatures

    def remove(self, key: str):
        """Remove a key from inventory."""
        self._packages.pop(key, None)
        self._signatures.pop(key, None)

    def clear(self):
        """Clear all entries."""
        self._packages.clear()
        self._signatures.clear()

    def combined_signature(self) -> CacheSignature:
        """Get merged signature of all cached data."""
        if not self._signatures:
            return CacheSignature(
                loc_ids=frozenset(),
                years=frozenset(),
                metrics=frozenset()
            )

        result = None
        for sig in self._signatures.values():
            if result is None:
                result = sig
            else:
                result = result.merge(sig)

        return result

    def can_serve(self, requested: CacheSignature) -> bool:
        """Check if inventory can fully serve a request."""
        combined = self.combined_signature()
        return combined.contains(requested)

    def compute_delta(self, requested: CacheSignature) -> CacheSignature:
        """Compute what needs to be fetched to serve request."""
        combined = self.combined_signature()
        return requested.subtract(combined)

    def stats(self) -> Dict:
        """Get inventory statistics."""
        combined = self.combined_signature()
        return {
            "name": self.name,
            "entry_count": len(self._signatures),
            "total_locations": len(combined.loc_ids),
            "total_metrics": len(combined.metrics),
            "total_years": len(combined.years),
            "year_range": combined.year_range(),
            "has_data": len(self._packages),
            "signature_only": len(self._signatures) - len(self._packages),
        }

    def to_dict(self) -> Dict:
        """Serialize inventory (signatures only, not data)."""
        return {
            "name": self.name,
            "entries": {
                key: sig.to_dict()
                for key, sig in self._signatures.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CacheInventory":
        """Deserialize inventory."""
        inv = cls(name=data.get("name", "unnamed"))
        for key, sig_data in data.get("entries", {}).items():
            inv.add_signature(key, CacheSignature.from_dict(sig_data))
        return inv


# ==============================================================================
# CoverageClaim (v1) -- unified coverage contract
#
# Python port of "The Claim Contract (v1)" in
# county-map-private/docs/future/coverage_ledger_implementation.md, kept in
# axis-by-axis agreement with the JS reference implementation
# (static/modules/coverage-ledger.js). Read that doc's "Claim Contract"
# section before changing anything here -- this file follows it exactly and
# should not invent behavior the doc does not describe.
#
# This is a claim-level port (covers/diff operate claim-against-need), not a
# ledger. A full ledger (record/markInFlight/resolveInFlight/invalidateVersion/
# timeUnion/...) is out of scope for Task L4; session_cache.py continues to
# hold multiple entries the way it always has, and a single-claim diff is
# equivalent to a one-claim ledger's diff.
#
# Wire format: to_json_dict()/from_json_dict() intentionally use the JS
# module's camelCase key names (geoLevel, and scope.kind "locIds") even
# though the internal Python attribute/kind names are snake_case
# (geo_level, "loc_ids") to match this file's existing style. The mapping
# is confined to the JSON boundary so both sides speak byte-identical JSON.
# ==============================================================================

# Sentinel filter signature for data merged in without a real fetch
# signature (e.g. chat-order seeded slices). Mirrors SEEDED_FILTERS in
# coverage-ledger.js -- a seeded claim must never silently satisfy a real
# (non-ignore_filters) need.
SEEDED_FILTERS = "__seeded__"

_MS_PER_DAY = 24 * 60 * 60 * 1000

_SCOPE_KIND_TO_JSON = {"all": "all", "region": "region", "loc_ids": "locIds", "bbox": "bbox"}
_SCOPE_KIND_FROM_JSON = {v: k for k, v in _SCOPE_KIND_TO_JSON.items()}


def _loc_id_matches_region(loc_id: str, region_value: str) -> bool:
    return loc_id == region_value or loc_id.startswith(f"{region_value}-")


def _year_bounds_ms(year: int) -> Tuple[int, int]:
    """UTC [start, end] ms-epoch bounds for a calendar year (Jan 1 - Dec 31)."""
    start = calendar.timegm((year, 1, 1, 0, 0, 0, 0, 0, 0)) * 1000
    end = calendar.timegm((year, 12, 31, 23, 59, 59, 0, 0, 0)) * 1000 + 999
    return start, end


def _range_covers_year(range_time: "ClaimTime", year: int) -> bool:
    """
    Does a 'range' time claim cover a single year? v1 requires the full
    Jan 1 - Dec 31 span inside the range (the 'six-month' yearCoverageRule
    policy from the JS ledger is a ledger-level query option, out of scope
    for this claim-level port -- see module docstring).
    """
    start, end = _year_bounds_ms(year)
    return range_time.min <= start and range_time.max >= end


def _subtract_intervals(
    base_min: int, base_max: int, covering: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """
    Subtract a set of covering [min,max] intervals (inclusive ms) from a
    base [base_min,base_max] interval. Returns the remainder as 0..N
    intervals. Direct port of subtractIntervals() in coverage-ledger.js.
    """
    clipped = sorted(
        (max(a, base_min), min(b, base_max))
        for a, b in covering
        if max(a, base_min) <= min(b, base_max)
    )

    merged: List[List[int]] = []
    for a, b in clipped:
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    remainder: List[Tuple[int, int]] = []
    cursor = base_min
    for a, b in merged:
        if a > cursor:
            remainder.append((cursor, a - 1))
        cursor = max(cursor, b + 1)
    if cursor <= base_max:
        remainder.append((cursor, base_max))
    return remainder


@dataclass(frozen=True)
class ClaimScope:
    """
    scope: { kind: 'all' }
         | { kind: 'region',  value: str }        # loc_id prefix, e.g. 'USA-VA'
         | { kind: 'loc_ids', value: FrozenSet[str] }
         | { kind: 'bbox',    value: (w, s, e, n) }  # v1: stored, weak containment
    """

    kind: str
    value: Any = None

    def __post_init__(self) -> None:
        kind = self.kind
        if kind == "all":
            object.__setattr__(self, "value", None)
        elif kind == "region":
            if not isinstance(self.value, str) or not self.value:
                raise ValueError(
                    "CoverageClaim: region scope.value must be a non-empty loc_id prefix string"
                )
        elif kind == "loc_ids":
            value = self.value
            if not isinstance(value, (set, frozenset, list, tuple)):
                raise ValueError(
                    "CoverageClaim: loc_ids scope.value must be an iterable of non-empty strings"
                )
            items = list(value)
            if not all(isinstance(v, str) and v for v in items):
                raise ValueError("CoverageClaim: loc_ids scope.value entries must be non-empty strings")
            object.__setattr__(self, "value", frozenset(items))
        elif kind == "bbox":
            value = self.value
            if not isinstance(value, (list, tuple)) or len(value) != 4:
                raise ValueError(
                    "CoverageClaim: bbox scope.value must be [west, south, east, north] finite numbers"
                )
            try:
                nums = tuple(float(v) for v in value)
            except (TypeError, ValueError):
                raise ValueError(
                    "CoverageClaim: bbox scope.value must be [west, south, east, north] finite numbers"
                )
            if not all(math.isfinite(n) for n in nums):
                raise ValueError(
                    "CoverageClaim: bbox scope.value must be [west, south, east, north] finite numbers"
                )
            object.__setattr__(self, "value", nums)
        else:
            raise ValueError(f"CoverageClaim: unknown scope.kind '{kind}'")


@dataclass(frozen=True)
class ClaimTime:
    """
    time: { kind: 'all' }
        | { kind: 'range', min: msEpoch, max: msEpoch }
        | { kind: 'years', years: FrozenSet[int] }    # gap-aware, may be sparse
        | { kind: 'stamps', stamps: FrozenSet[int] }  # v1.1: explicit sparse timestamps
    """

    kind: str
    min: Optional[float] = None
    max: Optional[float] = None
    years: FrozenSet[int] = frozenset()
    stamps: FrozenSet[float] = frozenset()

    def __post_init__(self) -> None:
        if self.kind == "all":
            object.__setattr__(self, "min", None)
            object.__setattr__(self, "max", None)
            object.__setattr__(self, "years", frozenset())
            object.__setattr__(self, "stamps", frozenset())
        elif self.kind == "range":
            if self.min is None or self.max is None:
                raise ValueError("CoverageClaim: range time.min/time.max must be finite numbers")
            try:
                mn = float(self.min)
                mx = float(self.max)
            except (TypeError, ValueError):
                raise ValueError("CoverageClaim: range time.min/time.max must be finite numbers")
            if not (math.isfinite(mn) and math.isfinite(mx)):
                raise ValueError("CoverageClaim: range time.min/time.max must be finite numbers")
            if mn > mx:
                raise ValueError("CoverageClaim: range time.min must be <= time.max")
            object.__setattr__(self, "min", mn)
            object.__setattr__(self, "max", mx)
            object.__setattr__(self, "years", frozenset())
            object.__setattr__(self, "stamps", frozenset())
        elif self.kind == "years":
            years = self.years
            if not isinstance(years, (set, frozenset, list, tuple)):
                raise ValueError("CoverageClaim: years time.years must be an iterable of integers")
            try:
                yrs = frozenset(int(y) for y in years)
            except (TypeError, ValueError):
                raise ValueError("CoverageClaim: years time.years must be an iterable of integers")
            object.__setattr__(self, "years", yrs)
            object.__setattr__(self, "min", None)
            object.__setattr__(self, "max", None)
            object.__setattr__(self, "stamps", frozenset())
        elif self.kind == "stamps":
            stamps = self.stamps
            if not isinstance(stamps, (set, frozenset, list, tuple)):
                raise ValueError("CoverageClaim: stamps time.stamps must be an iterable of finite numbers")
            try:
                vals = [float(s) for s in stamps]
            except (TypeError, ValueError):
                raise ValueError("CoverageClaim: stamps time.stamps must be an iterable of finite numbers")
            if not all(math.isfinite(v) for v in vals):
                raise ValueError("CoverageClaim: stamps time.stamps must be an iterable of finite numbers")
            frozen = frozenset(vals)
            if not frozen:
                raise ValueError("CoverageClaim: stamps time.stamps must not be empty")
            object.__setattr__(self, "stamps", frozen)
            object.__setattr__(self, "min", None)
            object.__setattr__(self, "max", None)
            object.__setattr__(self, "years", frozenset())
        else:
            raise ValueError(f"CoverageClaim: unknown time.kind '{self.kind}'")


@dataclass(frozen=True)
class CoverageClaim:
    """
    Immutable coverage claim: "for source S, I hold metrics M at geo_level L
    over scope C for time T, fetched under filters F, cut from artifact
    version V." See coverage_ledger_implementation.md "The Claim Contract
    (v1)" for the normative schema and rules; this class implements it
    exactly (normalization + validation in __post_init__, containment in
    covers(), the v1 one-axis-at-a-time subtraction policy in diff()).

    Construction normalizes + validates like the JS normalizeClaim(): raw
    list/set inputs for metrics/loc_ids/years are accepted and coerced to
    frozensets; malformed claims raise ValueError synchronously (never
    silently coerced/dropped).
    """

    source: str
    metrics: Union[str, FrozenSet[str]] = "*"
    geo_level: Optional[str] = None
    scope: "ClaimScope" = field(default_factory=lambda: ClaimScope(kind="all"))
    time: "ClaimTime" = field(default_factory=lambda: ClaimTime(kind="all"))
    filters: str = ""
    version: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("CoverageClaim: source must be a non-empty string")

        if self.metrics != "*":
            if not isinstance(self.metrics, (set, frozenset, list, tuple)):
                raise ValueError("CoverageClaim: metrics must be '*' or a string collection")
            items = list(self.metrics)
            if not items:
                raise ValueError(
                    "CoverageClaim: metrics collection must not be empty (use '*' instead)"
                )
            if not all(isinstance(m, str) and m for m in items):
                raise ValueError("CoverageClaim: metrics entries must be non-empty strings")
            object.__setattr__(self, "metrics", frozenset(items))

        if self.geo_level is not None and (not isinstance(self.geo_level, str) or not self.geo_level):
            raise ValueError("CoverageClaim: geo_level must be a non-empty string or None")

        if isinstance(self.scope, dict):
            object.__setattr__(self, "scope", ClaimScope(**self.scope))
        elif not isinstance(self.scope, ClaimScope):
            raise ValueError("CoverageClaim: scope must be a ClaimScope or dict")

        if isinstance(self.time, dict):
            object.__setattr__(self, "time", ClaimTime(**self.time))
        elif not isinstance(self.time, ClaimTime):
            raise ValueError("CoverageClaim: time must be a ClaimTime or dict")

        if self.filters is None:
            object.__setattr__(self, "filters", "")
        elif not isinstance(self.filters, str):
            raise ValueError("CoverageClaim: filters must be a string")

        if self.version is not None and not isinstance(self.version, str):
            raise ValueError("CoverageClaim: version must be a string or None")

    # -- containment helpers, per axis -----------------------------------

    def _metrics_covers(self, need_metrics: Union[str, FrozenSet[str]]) -> bool:
        if self.metrics == "*":
            return True
        if need_metrics == "*":
            return False  # need '*' is only covered by held '*'
        return need_metrics.issubset(self.metrics)

    def _scope_covers_loc_id(self, loc_id: str) -> bool:
        scope = self.scope
        if scope.kind == "all":
            return True
        if scope.kind == "region":
            return _loc_id_matches_region(loc_id, scope.value)
        if scope.kind == "loc_ids":
            return loc_id in scope.value
        return False  # bbox: geometry containment deferred to the bbox phase

    def _scope_covers(self, need_scope: ClaimScope) -> bool:
        held = self.scope
        if held.kind == "all":
            return True
        if need_scope.kind == "all":
            return False  # 'all' need only covered by held 'all'
        if held.kind == "region":
            if need_scope.kind == "region":
                return _loc_id_matches_region(need_scope.value, held.value)
            if need_scope.kind == "loc_ids":
                return all(_loc_id_matches_region(i, held.value) for i in need_scope.value)
            return False  # bbox
        if held.kind == "loc_ids":
            if need_scope.kind == "loc_ids":
                return need_scope.value.issubset(held.value)
            return False
        if held.kind == "bbox":
            return need_scope.kind == "bbox" and held.value == need_scope.value
        return False

    def _time_covers(self, need_time: ClaimTime) -> bool:
        held = self.time
        if held.kind == "all":
            return True
        if need_time.kind == "all":
            return False  # 'all' need only covered by held 'all'
        if held.kind == "range":
            if need_time.kind == "range":
                return held.min <= need_time.min and held.max >= need_time.max
            if need_time.kind == "years":
                return all(_range_covers_year(held, y) for y in need_time.years)
            if need_time.kind == "stamps":
                return all(held.min <= s <= held.max for s in need_time.stamps)
            return False
        if held.kind == "years":
            if need_time.kind == "years":
                return need_time.years.issubset(held.years)
            return False  # years never covers a range or stamps need (v1, conservative)
        if held.kind == "stamps":
            # stamps never covers a range or years need (a finite sample
            # never proves interval coverage).
            if need_time.kind == "stamps":
                return need_time.stamps.issubset(held.stamps)
            return False
        return False

    def _filters_covers(self, need_filters: str, ignore_filters: bool) -> bool:
        if ignore_filters:
            return True
        if self.filters == SEEDED_FILTERS and need_filters != SEEDED_FILTERS:
            return False
        return self.filters == need_filters

    def covers(self, need: "CoverageClaim", ignore_filters: bool = False) -> bool:
        """
        Does this (held) claim cover the need claim? ALL axes must hold:
        source, metrics, geo_level, scope, time, filters. See the "Claim
        Contract (v1)" containment rules for the per-axis semantics.
        """
        return (
            self.source == need.source
            and self._metrics_covers(need.metrics)
            and self.geo_level == need.geo_level
            and self._scope_covers(need.scope)
            and self._time_covers(need.time)
            and self._filters_covers(need.filters, ignore_filters)
        )

    # -- diff (need minus held), v1 one-axis-at-a-time policy ------------

    def _time_remainder(self, need_time: ClaimTime) -> Optional[List[ClaimTime]]:
        held_time = self.time
        if need_time.kind == "all":
            return None if held_time.kind == "all" else [ClaimTime(kind="all")]

        if need_time.kind == "range":
            if held_time.kind == "all":
                return None
            covering = [(held_time.min, held_time.max)] if held_time.kind == "range" else []
            remainder = _subtract_intervals(need_time.min, need_time.max, covering)
            if not remainder:
                return None
            return [ClaimTime(kind="range", min=a, max=b) for a, b in remainder]

        if need_time.kind == "years":
            if held_time.kind == "all":
                return None
            covered: Set[int] = set()
            if held_time.kind == "years":
                covered |= held_time.years
            elif held_time.kind == "range":
                for y in need_time.years:
                    if _range_covers_year(held_time, y):
                        covered.add(y)
            # held_time.kind == "stamps" never contributes to a years need
            # (different semantics: a Jan-1 stamp is an instant, a year is a
            # bucket).
            missing = sorted(set(need_time.years) - covered)
            if not missing:
                return None
            return [ClaimTime(kind="years", years=frozenset(missing))]

        # need_time.kind == "stamps"
        if held_time.kind == "all":
            return None
        covered_stamps: Set[float] = set()
        if held_time.kind == "stamps":
            covered_stamps |= held_time.stamps
        # held_time.kind in ("range", "years") never contributes to a stamps
        # need -- a finite sample is never proven by an interval or year
        # bucket; that partial pairing naturally falls out below as the full
        # remainder, matching the over-fetch fallback.
        missing_stamps = sorted(set(need_time.stamps) - covered_stamps)
        if not missing_stamps:
            return None
        return [ClaimTime(kind="stamps", stamps=frozenset(missing_stamps))]

    def diff(self, need: "CoverageClaim", ignore_filters: bool = False) -> List["CoverageClaim"]:
        """
        Claim-level diff(need): what part of need is NOT covered by this
        held claim, per the v1 policy (subtract along ONE axis at a time,
        only when every other axis is contained):

        1. drop need entirely if this claim covers it;
        2. else if exactly the time axis is partially covered (every other
           axis contained), return need with the uncovered time remainder;
        3. else if exactly the loc_ids axis is partially covered, return
           need with the missing loc_ids;
        4. otherwise return [need] unchanged (deliberate over-fetch).

        A ledger diffing against a POOL of held claims would union each
        axis across the pool first (see coverage-ledger.js); this
        claim-level port only has `self` to diff against, which is exactly
        equivalent to a one-claim ledger.
        """
        if self.covers(need, ignore_filters):
            return []

        other_axes_ok = (
            self.source == need.source
            and self._metrics_covers(need.metrics)
            and self.geo_level == need.geo_level
            and self._scope_covers(need.scope)
            and self._filters_covers(need.filters, ignore_filters)
        )
        if other_axes_ok:
            remainder = self._time_remainder(need.time)
            if remainder is None:
                return []
            return [replace(need, time=t) for t in remainder]

        if need.scope.kind == "loc_ids":
            loc_relevant = (
                self.source == need.source
                and self._metrics_covers(need.metrics)
                and self.geo_level == need.geo_level
                and self._time_covers(need.time)
                and self._filters_covers(need.filters, ignore_filters)
                and self.scope.kind in ("region", "loc_ids", "all")
            )
            if loc_relevant:
                missing = [i for i in sorted(need.scope.value) if not self._scope_covers_loc_id(i)]
                if not missing:
                    return []
                return [replace(need, scope=ClaimScope(kind="loc_ids", value=frozenset(missing)))]

        return [need]

    # -- JSON wire format (matches coverage-ledger.js's per-claim shape) --

    def to_json_dict(self) -> Dict[str, Any]:
        """Serialize to the same JSON shape the JS module emits per claim."""
        if self.scope.kind == "all":
            scope_json: Dict[str, Any] = {"kind": "all"}
        elif self.scope.kind == "region":
            scope_json = {"kind": "region", "value": self.scope.value}
        elif self.scope.kind == "loc_ids":
            scope_json = {"kind": "locIds", "value": sorted(self.scope.value)}
        else:  # bbox
            scope_json = {"kind": "bbox", "value": list(self.scope.value)}

        if self.time.kind == "all":
            time_json: Dict[str, Any] = {"kind": "all"}
        elif self.time.kind == "range":
            time_json = {"kind": "range", "min": self.time.min, "max": self.time.max}
        elif self.time.kind == "years":
            time_json = {"kind": "years", "years": sorted(self.time.years)}
        else:  # stamps
            time_json = {"kind": "stamps", "stamps": sorted(self.time.stamps)}

        return {
            "source": self.source,
            "metrics": "*" if self.metrics == "*" else sorted(self.metrics),
            "geoLevel": self.geo_level,
            "scope": scope_json,
            "time": time_json,
            "filters": self.filters,
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> "CoverageClaim":
        """Deserialize from the JSON shape the JS module emits per claim."""
        if not isinstance(data, dict):
            raise ValueError("CoverageClaim: JSON claim must be an object")

        scope_data = data.get("scope") or {}
        scope_kind_json = scope_data.get("kind")
        scope_kind = _SCOPE_KIND_FROM_JSON.get(scope_kind_json)
        if scope_kind is None:
            raise ValueError(f"CoverageClaim: unknown scope.kind '{scope_kind_json}'")
        scope = ClaimScope(kind=scope_kind, value=scope_data.get("value"))

        time_data = data.get("time") or {}
        time_kind = time_data.get("kind")
        if time_kind == "range":
            time = ClaimTime(kind="range", min=time_data.get("min"), max=time_data.get("max"))
        elif time_kind == "years":
            time = ClaimTime(kind="years", years=time_data.get("years") or [])
        elif time_kind == "stamps":
            time = ClaimTime(kind="stamps", stamps=time_data.get("stamps") or [])
        elif time_kind == "all":
            time = ClaimTime(kind="all")
        else:
            raise ValueError(f"CoverageClaim: unknown time.kind '{time_kind}'")

        return cls(
            source=data.get("source"),
            metrics=data.get("metrics", "*"),
            geo_level=data.get("geoLevel"),
            scope=scope,
            time=time,
            filters=data.get("filters", ""),
            version=data.get("version"),
        )

    # -- bridge back to the legacy CacheSignature shape -------------------

    def to_legacy_signature(self) -> "CacheSignature":
        """
        Bridge: convert to a legacy CacheSignature, where lossless.

        Only claims with explicit metrics, scope.kind == 'loc_ids', and
        time.kind == 'years' convert losslessly (CacheSignature has no
        concept of '*' metrics, region/bbox scope, or ranged time). Raises
        ValueError otherwise rather than silently dropping information.
        """
        if self.metrics == "*":
            raise ValueError(
                "CoverageClaim.to_legacy_signature: '*' metrics has no legacy equivalent; "
                "pass a claim with explicit metrics"
            )
        if self.scope.kind != "loc_ids":
            raise ValueError(
                f"CoverageClaim.to_legacy_signature: scope.kind '{self.scope.kind}' has no legacy "
                "equivalent (only loc_ids scope converts losslessly)"
            )
        if self.time.kind != "years":
            raise ValueError(
                f"CoverageClaim.to_legacy_signature: time.kind '{self.time.kind}' has no legacy "
                "equivalent (only years time converts losslessly)"
            )
        return CacheSignature(
            loc_ids=frozenset(self.scope.value),
            years=frozenset(self.time.years),
            metrics=frozenset(self.metrics),
            source_id=self.source,
        )
