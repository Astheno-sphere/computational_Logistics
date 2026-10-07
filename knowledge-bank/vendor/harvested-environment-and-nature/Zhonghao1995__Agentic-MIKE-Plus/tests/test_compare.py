"""Baseline-vs-scenario comparison helpers (pure; no mikeio / license)."""
import numpy as np
import pandas as pd
import pytest

from mikeplus_mcp.contracts import compare


def _series(values, start="2020-01-01", freq="10min"):
    idx = pd.date_range(start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


def test_align_exact_when_indexes_match():
    a = _series([0, 1, 2, 1, 0])
    b = _series([0, 2, 4, 2, 0])
    aa, bb, how = compare.align(a, b)
    assert how == "exact"
    assert len(aa) == len(bb) == 5


def test_align_interpolates_onto_a_when_steps_differ():
    a = _series([0, 1, 2, 3, 4], freq="10min")            # 0..40 min
    b = _series([0, 2, 4], freq="20min")                    # 0, 20, 40 min
    aa, bb, how = compare.align(a, b)
    assert how == "interpolated"
    assert list(aa.index) == list(a.index)
    assert bb.tolist() == pytest.approx([0, 1, 2, 3, 4])   # linear in time


def test_align_never_extrapolates_beyond_b():
    a = _series([0, 1, 2, 3, 4, 5, 6], freq="10min")       # 0..60 min
    b = _series([0, 2, 4], freq="20min")                    # 0..40 min
    aa, bb, _ = compare.align(a, b)
    assert aa.index[-1] == b.index[-1]                      # trimmed to b's span
    assert not bb.isna().any()


def test_compare_series_deltas_and_volume_for_a_flow():
    a = _series([0.0, 1.0, 2.0, 1.0, 0.0])
    b = _series([0.0, 1.0, 3.0, 2.0, 0.0])                  # peak later? no: same time, +1
    out = compare.compare_series(a, b, "Discharge")
    assert out["unit"] == "m3/s"
    assert out["peak_a"] == 2.0 and out["peak_b"] == 3.0
    assert out["delta_peak"] == 1.0
    assert out["delta_peak_pct"] == 50.0
    assert out["peak_time_shift_min"] == 0.0
    # trapezoid over 10-min steps: a = (0+1+2+1+0 - (0+0)/2) * 600 = 2400 m3
    assert out["volume_a"] == pytest.approx(2400.0)
    assert out["volume_b"] == pytest.approx(3600.0)
    assert out["delta_volume"] == pytest.approx(1200.0)
    assert out["volume_unit"] == "m3"
    assert out["nse_b_vs_a"] < 1.0
    assert out["max_abs_diff"] == 1.0


def test_compare_series_peak_time_shift_sign():
    a = _series([0, 3, 0, 0, 0])            # peak at t=10 min
    b = _series([0, 0, 0, 3, 0])            # peak at t=30 min
    out = compare.compare_series(a, b, "WaterLevel")
    assert out["peak_time_shift_min"] == 20.0
    assert "volume_a" not in out            # a level has no volume


def test_compare_series_identical_gives_nse_one_and_zero_deltas():
    a = _series([0, 1, 2, 1, 0])
    out = compare.compare_series(a, a.copy(), "Discharge")
    assert out["delta_peak"] == 0.0 and out["rmse"] == 0.0 and out["nse_b_vs_a"] == 1.0


def _frames():
    idx = pd.date_range("2020-01-01", periods=4, freq="h")
    a = pd.DataFrame({"Discharge:L1:5": [0, 1, 2, 0], "Discharge:L2:5": [0, 5, 1, 0],
                      "WaterLevel:N1": [1, 1, 1, 1], "Discharge:OnlyA:1": [0, 1, 0, 0]}, index=idx)
    b = pd.DataFrame({"Discharge:L1:5": [0, 1, 4, 0], "Discharge:L2:5": [0, 4, 1, 0],
                      "WaterLevel:N1": [1, 1, 1, 1], "Discharge:OnlyB:1": [0, 1, 0, 0]}, index=idx)
    return a, b


def test_compare_frames_ranks_by_absolute_delta_and_counts():
    a, b = _frames()
    out = compare.compare_frames(a, b, "Discharge", top_n=5)
    assert out["n_shared"] == 2 and out["n_only_a"] == 1 and out["n_only_b"] == 1
    assert [r["element_id"] for r in out["top"]] == ["L1", "L2"]   # |+2| before |-1|
    assert out["top"][0]["delta_peak"] == 2.0 and out["top"][1]["delta_peak"] == -1.0
    assert out["n_increased"] == 1 and out["n_decreased"] == 1 and out["n_unchanged"] == 0


def test_compare_frames_no_shared_columns_raises():
    a, b = _frames()
    with pytest.raises(ValueError):
        compare.compare_frames(a, b, "FlowVelocity")
