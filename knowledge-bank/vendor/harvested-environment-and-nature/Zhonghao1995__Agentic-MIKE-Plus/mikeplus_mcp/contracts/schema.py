"""Canonical, engine-agnostic result schema + helpers.

A mikeio1d res1d column is named ``<Quantity>:<ElementId>`` or
``<Quantity>:<ElementId>:<chainage>``. We normalize everything to::

    {engine, quantity, element_id, chainage, unit, ...}

so downstream skills (plot / calibration / uncertainty / audit) can be identical
across SWMM, MIKE+, and LSTM. Keep this module pure (no mikeio/mikeplus imports).
"""
from __future__ import annotations

import math

from .units import unit_for

ENGINE = "mikeplus"


def parse_column(col: str) -> dict:
    """``'Discharge:Link_29:33.5333'`` -> ``{quantity, element_id, chainage}``."""
    parts = str(col).split(":")
    quantity = parts[0]
    element_id = parts[1] if len(parts) > 1 else ""
    chainage = None
    if len(parts) > 2:
        try:
            chainage = float(parts[2])
        except ValueError:
            chainage = parts[2]
    return {"quantity": quantity, "element_id": element_id, "chainage": chainage}


def match_columns(columns, quantity: str, element: str) -> list:
    """res1d columns whose ``Quantity:ElementId`` matches ``quantity``/``element``.

    Matches an exact node series (``Quantity:Element``) OR a reach series carrying a
    chainage suffix (``Quantity:Element:chainage``). The trailing ``':'`` guard keeps a
    node ``X`` distinct from a reach ``X.2`` (the reach id contains the dot, so it never
    matches the ``X:`` prefix). Returns the original column objects, in input order.
    """
    base = f"{quantity}:{element}"
    return [c for c in columns if str(c) == base or str(c).startswith(base + ":")]


def summarize(df, quantities=None) -> list[dict]:
    """Per-quantity peak summary (canonical). ``df`` = mikeio1d ``res.read()``."""
    cols_by_q: dict[str, list] = {}
    for c in df.columns:
        q = str(c).split(":", 1)[0]
        cols_by_q.setdefault(q, []).append(c)

    out: list[dict] = []
    for q, cols in cols_by_q.items():
        if quantities and q not in quantities:
            continue
        sub = df[cols]
        colmax = sub.max()
        peak = float(colmax.max())
        if math.isnan(peak):
            continue
        elem_col = colmax.idxmax()
        t_peak = sub[elem_col].idxmax()
        meta = parse_column(elem_col)
        out.append({
            "engine": ENGINE,
            "quantity": q,
            "unit": unit_for(q),
            "peak_value": round(peak, 4),
            "peak_element": meta["element_id"],
            "peak_chainage": meta["chainage"],
            "peak_time": str(t_peak),
            "n_series": len(cols),
        })
    return out
