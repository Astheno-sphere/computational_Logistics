"""Canonical place/time coverage vocabulary shared by catalog surfaces.

The helpers in this module are deliberately stdlib-only.  Builders use them
before emitting Agent Catalog artifacts and the hosted MCP uses the same
contract when resolving ``get_catalog`` filters.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any, Iterable


ISO3 = re.compile(r"^[A-Z]{3}$")
_BARE_YEAR = re.compile(r"-?\d{1,4}")
RESERVED_SCOPES = {"global", "marine", "unknown"}


def normalize_scope(value: Any) -> str:
    """Return ISO3 scopes uppercase and reserved scopes lowercase."""
    text = str(value or "").strip()
    if not text:
        return "unknown"
    lowered = text.lower().replace("-", "_").replace(" ", "_")
    if lowered in {"world", "worldwide", "global"}:
        return "global"
    if lowered in {"ocean", "oceans", "marine"}:
        return "marine"
    upper = text.upper()
    if ISO3.fullmatch(upper):
        return upper
    return "unknown"


def normalize_scopes(values: Iterable[Any]) -> list[str]:
    scopes = {normalize_scope(value) for value in values}
    scopes.discard("unknown")
    return sorted(scopes, key=lambda value: (value not in RESERVED_SCOPES, value)) or ["unknown"]


def normalize_geographic_levels(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalize administrative levels and explain an intentionally empty set."""
    raw = entry.get("geographic_levels")
    if not isinstance(raw, list):
        raw = [entry.get("geographic_level")]
    levels: set[int] = set()
    aliases = {
        "country": 0, "admin_0": 0, "admin0": 0, "adm0": 0,
        "state": 1, "province": 1, "region": 1, "admin_1": 1, "admin1": 1, "adm1": 1,
        "county": 2, "district": 2, "municipality": 2, "admin_2": 2, "admin2": 2, "adm2": 2,
        "tract": 3, "admin_3": 3, "admin3": 3, "adm3": 3,
        "blockgroup": 4, "block_group": 4, "admin_4": 4, "admin4": 4, "adm4": 4,
        "block": 5, "admin_5": 5, "admin5": 5, "adm5": 5,
        "admin_6": 6, "admin6": 6, "adm6": 6,
    }
    for value in raw:
        if value is None:
            continue
        if isinstance(value, int) and 0 <= value <= 6:
            levels.add(value)
            continue
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if text.isdigit() and 0 <= int(text) <= 6:
            levels.add(int(text))
        elif text in aliases:
            levels.add(aliases[text])

    if levels:
        semantics = "administrative_levels"
    else:
        scope = normalize_scope(entry.get("scope"))
        data_type = str(entry.get("data_type") or "").strip().lower()
        family = str(entry.get("geometry_family") or "").strip().lower()
        if scope == "marine" or family == "marine":
            semantics = "marine_non_administrative"
        elif any(token in data_type for token in ("raster", "grid", "image", "climate")):
            semantics = "raster_or_grid_non_administrative"
        else:
            semantics = "not_declared"
    return {"levels": sorted(levels), "empty_meaning": None if levels else semantics}


def coverage_contract(entry: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative, filter-safe geographic coverage assertion.

    ``global`` means worldwide only when the metadata explicitly says so and
    carries no exclusions.  A legacy global label with exclusions is reported
    as regional/unknown rather than silently matching every country.
    """
    coverage = entry.get("geographic_coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    declared_scope = normalize_scope(entry.get("scope"))
    countries = {
        str(value).strip().upper()
        for value in (coverage.get("countries") or [])
        if ISO3.fullmatch(str(value).strip().upper())
    }
    for key in ("country_code", "iso3"):
        value = str(entry.get(key) or "").strip().upper()
        if ISO3.fullmatch(value):
            countries.add(value)
    if ISO3.fullmatch(declared_scope):
        countries.add(declared_scope)
    uncommon = {
        str(value).strip().upper()
        for value in (coverage.get("uncommonly_included") or [])
        if ISO3.fullmatch(str(value).strip().upper())
    }
    countries.update(uncommon)
    missing = sorted({
        str(value).strip().upper()
        for value in (coverage.get("common_missing") or [])
        if ISO3.fullmatch(str(value).strip().upper())
    })
    coverage_type = str(coverage.get("type") or "").strip().lower()
    worldwide = (
        declared_scope == "global"
        and coverage_type in {"global", "worldwide"}
        and not missing
        and not countries
    )
    if worldwide:
        assertion = "worldwide"
        scopes = ["global"]
    elif countries:
        assertion = "explicit_countries"
        scopes = sorted(countries)
    elif declared_scope == "marine":
        assertion = "marine_domain"
        scopes = ["marine"]
    elif declared_scope == "global" and (missing or coverage_type == "regional"):
        assertion = "regional_countries_not_declared"
        scopes = ["unknown"]
    else:
        assertion = "not_declared"
        scopes = [declared_scope] if declared_scope != "unknown" else ["unknown"]
    levels = normalize_geographic_levels(entry)
    return {
        "assertion": assertion,
        "scopes": scopes,
        "countries": sorted(countries),
        "worldwide": worldwide,
        "excluded_countries": missing,
        "geographic_levels": levels["levels"],
        "empty_geographic_levels_meaning": levels["empty_meaning"],
    }


def coverage_matches_country(contract: dict[str, Any], iso3: str | None) -> bool | None:
    country = str(iso3 or "").strip().upper()
    if not country:
        return True
    if not ISO3.fullmatch(country):
        return False
    if contract.get("worldwide") is True:
        return country not in set(contract.get("excluded_countries") or [])
    countries = set(contract.get("countries") or [])
    if countries:
        return country in countries
    if country in set(contract.get("excluded_countries") or []):
        return False
    return None


def normalize_time_range(value: Any) -> dict[str, str | None] | None:
    if value in (None, "", {}):
        return None
    if not isinstance(value, dict):
        raise ValueError("time_range must be an object with start and/or end")
    start = _time_value(value.get("start"))
    end = _time_value(value.get("end"))
    if start is None and end is None:
        raise ValueError("time_range requires start and/or end")
    if start is not None and end is not None and _time_key(start) > _time_key(end):
        raise ValueError("time_range.start must not be after time_range.end")
    return {"start": start, "end": end}


def temporal_intersects(start: Any, end: Any, requested: dict[str, Any] | None) -> bool | None:
    if not requested:
        return True
    available_start = _time_value(start)
    available_end = _time_value(end)
    if available_start is None and available_end is None:
        return None
    requested_start = _time_value(requested.get("start"))
    requested_end = _time_value(requested.get("end"))
    if available_end is not None and requested_start is not None and _time_before(available_end, requested_start):
        return False
    if available_start is not None and requested_end is not None and _time_before(requested_end, available_start):
        return False
    return True


def _time_before(left: str, right: str) -> bool:
    """True when ``left`` ends before ``right`` begins.

    A bare year is a whole-year span, not an instant at 1 January: when either
    side is a bare year, compare at year granularity so ``end=1950`` keeps a
    source starting 1950-01-03 and a source ending ``2024`` keeps a request
    starting 2024-06-01.
    """
    if _BARE_YEAR.fullmatch(left) or _BARE_YEAR.fullmatch(right):
        return _time_key(left)[0] < _time_key(right)[0]
    return _time_key(left) < _time_key(right)


def source_coverage_window(entry: dict[str, Any]) -> dict[str, Any]:
    """One source's coupled place/time coverage, read from a catalog source row."""
    temporal = entry.get("temporal_coverage")
    temporal = temporal if isinstance(temporal, dict) else {}
    return {
        "source_id": entry.get("source_id"),
        "coverage_contract": coverage_contract(entry),
        "temporal_start": temporal.get("start"),
        "temporal_end": temporal.get("end"),
    }


def coverage_windows(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep place and time coupled at source granularity for intersection queries."""
    return [source_coverage_window(entry) for entry in entries]


def resolve_pack_coverage_match(
    pack: dict[str, Any],
    country: str | None,
    requested_time: dict[str, Any] | None,
) -> tuple[bool | None, bool | None]:
    """Return (place_match, time_match) for one pack: True, False, or None (unknown).

    A pack is confirmed when any one source window matches both place and time,
    so a USA-only early source cannot lend its years to a later global source.
    Packs without windows fall back to their pack-level coverage fields.
    """
    windows = [window for window in pack.get("coverage_windows") or [] if isinstance(window, dict)]
    if windows:
        outcomes = []
        for window in windows:
            coverage = window.get("coverage_contract")
            coverage = coverage if isinstance(coverage, dict) else {}
            outcomes.append((
                coverage_matches_country(coverage, country),
                temporal_intersects(window.get("temporal_start"), window.get("temporal_end"), requested_time),
            ))
        if any(place is True and time is True for place, time in outcomes):
            return True, True
        if any(place is not False and time is not False for place, time in outcomes):
            return None, None
        return False, False
    coverage = pack.get("coverage_contract")
    coverage = coverage if isinstance(coverage, dict) else {}
    return (
        coverage_matches_country(coverage, country),
        temporal_intersects(pack.get("temporal_start"), pack.get("temporal_end"), requested_time),
    )


def _time_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(int(value)) if float(value).is_integer() else str(value)
    text = str(value).strip()
    if re.fullmatch(r"-?\d{1,4}", text):
        return text
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"invalid time value: {text}") from exc
    return text


def _time_key(value: str) -> tuple[int, str]:
    if re.fullmatch(r"-?\d{1,4}", value):
        return (int(value), "")
    year = int(value[:4]) if re.fullmatch(r"\d{4}.*", value) else 0
    return (year, value)
