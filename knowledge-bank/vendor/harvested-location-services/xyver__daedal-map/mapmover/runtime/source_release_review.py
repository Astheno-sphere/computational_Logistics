"""Precision-aware review notices for dated country Full geometry queries."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import admin_spine_query


_DATE = re.compile(r"^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def requested_interval(as_of: str) -> tuple[date, date, str]:
    """Return a half-open interval for an exact day, month, or year request."""
    match = _DATE.fullmatch(str(as_of or ""))
    if not match:
        raise ValueError("as_of must be an ISO day, month, or year")
    year, month, day = match.groups()
    if day is not None:
        start = date(int(year), int(month), int(day))
        return start, start + timedelta(days=1), "day"
    if month is not None:
        start = date(int(year), int(month), 1)
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
        return start, end, "month"
    start = date(int(year), 1, 1)
    return start, date(start.year + 1, 1, 1), "year"


def _day(value: Any) -> date | None:
    if value is None or str(value) in {"NaT", "nan", "<NA>"}:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _transition_end(bound: date, precision: str) -> date:
    if precision == "year":
        return date(bound.year + 1, 1, 1)
    if precision == "month":
        return date(bound.year + (bound.month == 12), bound.month % 12 + 1, 1)
    return bound + timedelta(days=1)


def review_window(row: dict[str, Any], metadata: dict[str, Any], as_of: str) -> dict[str, Any]:
    """Evaluate source-release applicability without claiming polygon birth dates."""
    start, end, requested_precision = requested_interval(as_of)
    release_id = str(row.get("source_release_id") or "")
    if (not release_id or release_id != metadata.get("source_release_id") or
            row.get("temporal_scope") != "source_release"):
        return {"as_of": as_of, "date_review_required": True,
                "status": "unsupported_temporal_scope",
                "reason": "No matching source-release window is available for this geometry."}
    valid_from, valid_to = _day(row.get("valid_from")), _day(row.get("valid_to"))
    precision = str(row.get("valid_from_precision") or "")
    if valid_from is None or precision not in {"day", "month", "year"}:
        return {"as_of": as_of, "date_review_required": True,
                "status": "unsupported_temporal_scope",
                "reason": "The source-release start or its precision is missing."}
    evidence_url = str(metadata.get("date_evidence_url") or "")
    if not evidence_url.startswith("https://"):
        raise ValueError("source-release date evidence URL is missing")
    check_date = _day(metadata.get("current_checked_at"))
    possible_ids = [release_id]
    common = {
        "as_of": as_of, "requested_precision": requested_precision,
        "source_release_id": release_id, "possible_source_release_ids": possible_ids,
        "valid_from": valid_from.isoformat(),
        "valid_to": valid_to.isoformat() if valid_to else None,
        "valid_from_precision": precision,
        "valid_to_precision": row.get("valid_to_precision"),
        "date_evidence_url": evidence_url,
        "current_checked_at": check_date.isoformat() if check_date else None,
    }
    if end <= valid_from or (valid_to is not None and start >= valid_to):
        return {**common, "possible_source_release_ids": [],
                "date_review_required": True,
                "status": "outside_supported_window",
                "reason": "This Full release does not establish a source edition for the requested date."}
    current_check_expired = valid_to is None and (
        check_date is None or end > check_date + timedelta(days=1)
    )
    transition_end = _transition_end(valid_from, precision)
    if start < transition_end and end > valid_from and precision != "day":
        return {**common, "date_review_required": True,
                "status": "coarse_release_boundary",
                "current_check_expired": current_check_expired,
                "review_interval": {"from": valid_from.isoformat(),
                                    "to_exclusive": transition_end.isoformat()},
                "other_edition_unresolved": True,
                "reason": (
                    "The source names a coarse edition start; check the publisher before relying on this date."
                    + (" The open-ended edition also needs a current check."
                       if current_check_expired else "")
                )}
    end_precision = str(row.get("valid_to_precision") or "")
    if valid_to is not None and end_precision in {"month", "year"}:
        transition_start = (
            date(valid_to.year - 1, 1, 1) if end_precision == "year"
            else date(valid_to.year - (valid_to.month == 1),
                      12 if valid_to.month == 1 else valid_to.month - 1, 1)
        )
        if start < valid_to and end > transition_start:
            return {**common, "date_review_required": True,
                    "status": "coarse_release_boundary",
                    "review_interval": {"from": transition_start.isoformat(),
                                        "to_exclusive": valid_to.isoformat()},
                    "other_edition_unresolved": True,
                    "reason": "The source names a coarse edition end; check the publisher before relying on this date."}
    if current_check_expired:
        return {**common, "date_review_required": True,
                "status": "after_current_check",
                "reason": "The open-ended edition has not been checked through the requested date."}
    return {**common, "date_review_required": False, "status": "within_supported_window",
            "reason": None}


def review_loc_id(loc_id: str, as_of: str) -> dict[str, Any]:
    """Read the admitted Full row and hash-pinned keyed metadata for one loc_id."""
    requested_interval(as_of)
    canonical = str(loc_id or "").strip().upper()
    country = canonical.split("-", 1)[0]
    columns = ["source_release_id", "temporal_scope", "valid_from", "valid_to",
               "valid_from_precision", "valid_to_precision"]
    rows = admin_spine_query.load_rows_by_loc_ids(country, [canonical], columns=columns)
    if rows.empty:
        return {"as_of": as_of, "loc_id": canonical, "date_review_required": True,
                "status": "full_row_unavailable",
                "reason": "No dated Full Admin row is available for this loc_id."}
    layout_root = admin_spine_query.layout_root(country)
    release_root = layout_root.parent.parent
    package_path = release_root / "full_package_manifest.json"
    if not package_path.is_file():
        return {"as_of": as_of, "loc_id": canonical, "date_review_required": True,
                "status": "source_metadata_unavailable",
                "reason": "The source-release citation metadata is unavailable."}
    package = json.loads(package_path.read_text(encoding="utf-8"))
    metadata_path = release_root / "runtime" / "source_releases.json"
    layout_digest = hashlib.sha256((layout_root / "manifest.json").read_bytes()).hexdigest()
    digest = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    if (package.get("country") != country or
            package.get("release_id") != release_root.name or
            package.get("admin_manifest_sha256") != layout_digest or
            package.get("source_release_metadata_sha256") != digest):
        raise ValueError("Full layout or source-release citation metadata hash mismatch")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    result = review_window(rows.iloc[0].to_dict(), metadata, as_of)
    return {"loc_id": canonical, **result}
