"""Unit tests for the engine-agnostic schema helpers (no license / no mikeio)."""
import numpy as np
import pandas as pd

from mikeplus_mcp.contracts import schema


def test_parse_column_node():
    assert schema.parse_column("WaterLevel:C14150801") == {
        "quantity": "WaterLevel",
        "element_id": "C14150801",
        "chainage": None,
    }


def test_parse_column_reach_with_chainage():
    out = schema.parse_column("Discharge:C14150801.2:30.71")
    assert out["quantity"] == "Discharge"
    assert out["element_id"] == "C14150801.2"  # the dot belongs to the reach id
    assert out["chainage"] == 30.71


def test_parse_column_non_numeric_chainage_falls_back_to_string():
    assert schema.parse_column("X:Y:notnum")["chainage"] == "notnum"


# real-world column shapes taken from the Sirius_RTC HD result
COLS = [
    "WaterLevel:C14150801",            # node
    "WaterLevel:C14150801.2:30.71",    # reach (synthetic) sharing the id stem
    "Discharge:C14150801.2:30.71",     # reach
    "Discharge:Link_29:33.5333",       # reach with a named link
]


def test_match_columns_node_is_not_confused_with_reach():
    # node 'C14150801' must NOT match reach 'C14150801.2'
    assert schema.match_columns(COLS, "WaterLevel", "C14150801") == ["WaterLevel:C14150801"]


def test_match_columns_reach_prefix():
    assert schema.match_columns(COLS, "Discharge", "C14150801.2") == ["Discharge:C14150801.2:30.71"]
    assert schema.match_columns(COLS, "Discharge", "Link_29") == ["Discharge:Link_29:33.5333"]


def test_match_columns_no_match():
    assert schema.match_columns(COLS, "Discharge", "Nope") == []


def _frame():
    idx = pd.date_range("2020-01-01", periods=5, freq="h")
    return pd.DataFrame(
        {
            "Discharge:Link_1:10": [0.0, 1.0, 2.0, 1.0, 0.0],
            "Discharge:Link_2:5": [0.0, 0.0, 5.0, 0.0, 0.0],   # global Discharge peak
            "WaterLevel:Node_1": [1.0, 1.0, 1.0, 1.0, 1.0],
            "WaterLevel:Node_2": [np.nan] * 5,                  # all-NaN column
        },
        index=idx,
    )


def test_summarize_picks_global_peak_and_time():
    rows = {r["quantity"]: r for r in schema.summarize(_frame())}
    assert set(rows) == {"Discharge", "WaterLevel"}

    dis = rows["Discharge"]
    assert dis["peak_value"] == 5.0
    assert dis["peak_element"] == "Link_2"
    assert dis["peak_time"].startswith("2020-01-01 02:00")
    assert dis["unit"] == "m3/s"
    assert dis["n_series"] == 2


def test_summarize_skips_all_nan_within_quantity():
    rows = {r["quantity"]: r for r in schema.summarize(_frame())}
    # WaterLevel:Node_2 is all-NaN; the peak must come from Node_1, not crash/NaN
    assert rows["WaterLevel"]["peak_value"] == 1.0


def test_summarize_quantity_filter():
    rows = schema.summarize(_frame(), quantities=["Discharge"])
    assert [r["quantity"] for r in rows] == ["Discharge"]
