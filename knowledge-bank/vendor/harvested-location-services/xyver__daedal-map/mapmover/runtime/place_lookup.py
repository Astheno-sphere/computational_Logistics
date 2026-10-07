"""Resolve ordinary populated-place names from compact country lookup indexes."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from ..paths import COUNTRY_GEOMETRY_DIR


def normalize_place_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _country_codes(country_hint: str | None) -> list[str]:
    hint = str(country_hint or "").strip().upper()
    aliases = {"CA": "CAN", "CANADA": "CAN", "US": "USA", "UNITED STATES": "USA", "AU": "AUS", "AUSTRALIA": "AUS"}
    if hint:
        return [aliases.get(hint, hint)]
    if not COUNTRY_GEOMETRY_DIR.is_dir():
        return []
    return sorted(path.name.upper() for path in COUNTRY_GEOMETRY_DIR.iterdir() if path.is_dir())


@lru_cache(maxsize=16)
def _load_index(path_text: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return pd.read_parquet(Path(path_text))


def resolve_populated_place(query: str, *, country_hint: str | None = None, limit: int = 10) -> dict[str, Any] | None:
    key = normalize_place_name(query)
    if not key:
        return None
    frames: list[pd.DataFrame] = []
    for country in _country_codes(country_hint):
        path = COUNTRY_GEOMETRY_DIR / country / "place_lookup" / "places.parquet"
        if not path.is_file():
            continue
        frame = _load_index(str(path), path.stat().st_mtime_ns)
        matched = frame.loc[frame.lookup_key.astype(str).eq(key)].copy()
        if not matched.empty:
            frames.append(matched)
    if not frames:
        return None
    matches = pd.concat(frames, ignore_index=True).sort_values(
        ["subtype_rank", "country_code", "region_label", "loc_id"]
    ).drop_duplicates("loc_id")
    best_rank = int(matches.subtype_rank.min())
    best = matches.loc[matches.subtype_rank.eq(best_rank)]
    candidates = matches.head(max(1, int(limit))).to_dict("records")
    if len(best) != 1:
        return {"status": "ambiguous", "query": query, "lookup_key": key, "candidates": candidates}
    return {"status": "matched", "query": query, "lookup_key": key, "match": best.iloc[0].to_dict(), "candidates": candidates}
