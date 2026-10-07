"""Rain CSV parsing + unit conversion (pure; the dfs0 writing lives in the worker)."""
import pandas as pd
import pytest

from mikeplus_mcp.contracts import rain


def _csv(tmp_path, body, name="r.csv"):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return str(p)


def test_load_defaults_to_first_two_columns_and_sorts(tmp_path):
    p = _csv(tmp_path, "time,mm\n2020-01-01 00:20,3\n2020-01-01 00:00,1\n2020-01-01 00:10,2\n")
    s = rain.load_rain_csv(p)
    assert s.tolist() == [1.0, 2.0, 3.0]
    assert isinstance(s.index, pd.DatetimeIndex)


def test_load_named_columns_and_rejects_bad_values(tmp_path):
    p = _csv(tmp_path, "id,when,val\n1,2020-01-01 00:00,0\n2,2020-01-01 00:10,x\n")
    with pytest.raises(ValueError, match="non-numeric"):
        rain.load_rain_csv(p, time_col="when", value_col="val")
    with pytest.raises(ValueError, match="not in CSV"):
        rain.load_rain_csv(p, time_col="nope")


def test_load_rejects_negative_and_too_short(tmp_path):
    with pytest.raises(ValueError, match="negative"):
        rain.load_rain_csv(_csv(tmp_path, "t,v\n2020-01-01 00:00,-1\n2020-01-01 00:10,0\n"))
    with pytest.raises(ValueError, match="two time steps"):
        rain.load_rain_csv(_csv(tmp_path, "t,v\n2020-01-01 00:00,1\n"))


def _series():
    idx = pd.date_range("2020-01-01 00:00", periods=4, freq="10min")
    return pd.Series([0.0, 6.0, 12.0, 0.0], index=idx)


def test_intensity_passthrough_reports_depth():
    inten, info = rain.to_intensity(_series(), "mm/h")
    assert inten.tolist() == [0.0, 6.0, 12.0, 0.0]
    assert info["conversion"] == "none"
    assert info["timestep_s"] == 600.0 and info["uniform_step"] is True
    # depth = sum(intensity * 600 s / 3600) = (6 + 12) / 6 = 3 mm
    assert info["total_depth_mm"] == pytest.approx(3.0)
    assert info["peak_intensity_mm_h"] == 12.0


def test_depth_per_step_converts_to_intensity():
    inten, info = rain.to_intensity(_series(), "mm")      # 10-min depths
    assert inten.tolist() == [0.0, 36.0, 72.0, 0.0]        # mm per 10 min -> mm/h
    assert info["total_depth_mm"] == 18.0
    assert "depth per step" in info["conversion"]


def test_unknown_unit_rejected():
    with pytest.raises(ValueError, match="unsupported rain unit"):
        rain.to_intensity(_series(), "inch")
