from datetime import date

import pytest

from mapmover.runtime.source_release_review import requested_interval, review_window


SOURCE = {
    "source_release_id": "deu_bkg_vg250_2026_01_01",
    "date_evidence_url": "https://example.org/source-date",
    "current_checked_at": "2026-10-02",
}
ROW = {
    "source_release_id": SOURCE["source_release_id"],
    "temporal_scope": "source_release",
    "valid_from": date(2026, 1, 1),
    "valid_from_precision": "year",
    "valid_to": None,
    "valid_to_precision": None,
}


def test_year_precision_flags_2026_transition_with_source_link():
    notice = review_window(ROW, SOURCE, "2026-06-15")
    assert notice["date_review_required"] is True
    assert notice["status"] == "coarse_release_boundary"
    assert notice["review_interval"] == {
        "from": "2026-01-01", "to_exclusive": "2027-01-01"}
    assert notice["date_evidence_url"] == SOURCE["date_evidence_url"]
    assert notice["other_edition_unresolved"] is True


def test_before_release_is_not_presented_as_applicable():
    notice = review_window(ROW, SOURCE, "2025-12-31")
    assert notice["date_review_required"] is True
    assert notice["status"] == "outside_supported_window"


def test_open_end_after_last_check_requires_review():
    notice = review_window(ROW, SOURCE, "2027-01-01")
    assert notice["date_review_required"] is True
    assert notice["status"] == "after_current_check"


def test_day_precision_interior_has_no_warning():
    row = {**ROW, "valid_from": date(2020, 1, 1), "valid_from_precision": "day",
           "valid_to": date(2025, 1, 1), "valid_to_precision": "day"}
    notice = review_window(row, SOURCE, "2022-06-15")
    assert notice["date_review_required"] is False
    assert notice["status"] == "within_supported_window"


def test_coarse_end_flags_its_transition_year():
    row = {**ROW, "valid_from": date(2020, 1, 1), "valid_from_precision": "day",
           "valid_to": date(2027, 1, 1), "valid_to_precision": "year"}
    notice = review_window(row, SOURCE, "2026-08")
    assert notice["date_review_required"] is True
    assert notice["review_interval"] == {
        "from": "2026-01-01", "to_exclusive": "2027-01-01"}


@pytest.mark.parametrize("value", ["yesterday", "2026-13", "2026-02-30"])
def test_invalid_requested_date_is_rejected(value):
    with pytest.raises(ValueError):
        requested_interval(value)
