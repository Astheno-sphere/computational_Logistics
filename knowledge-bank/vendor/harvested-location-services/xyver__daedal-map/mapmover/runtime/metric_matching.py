from __future__ import annotations

from typing import Optional

import pandas as pd


def find_metric_column_generic(
    df: pd.DataFrame,
    metric: str,
    metadata: Optional[dict] = None,
    *,
    alias_candidates: dict[str, list[str]] | None = None,
    alias_term_bundles: dict[str, list[set[str]]] | None = None,
) -> Optional[str]:
    """
    Find a matching column for a metric using generic metadata/fuzzy matching.

    Source-family-specific alias tables may be passed in by callers, but the
    core matching algorithm lives here.
    """

    def _norm(value: str) -> str:
        return str(value).lower().replace("_", " ").replace("-", " ").strip()

    def _find_alias_match(candidates: list[str]) -> Optional[str]:
        normalized_columns = {_norm(col): col for col in df.columns}
        for candidate in candidates:
            matched = normalized_columns.get(_norm(candidate))
            if matched:
                return matched
        return None

    def _find_term_bundle_match(term_bundles: list[set[str]]) -> Optional[str]:
        best_match = None
        best_score = 0
        for col in df.columns:
            if col in ("loc_id", "year"):
                continue
            col_words = set(_norm(col).split())
            for bundle in term_bundles:
                if bundle.issubset(col_words):
                    score = len(bundle)
                    if score > best_score:
                        best_match = col
                        best_score = score
        return best_match

    def _find_metadata_metric_match() -> Optional[str]:
        metrics_meta = (metadata or {}).get("metrics") or {}
        if not isinstance(metrics_meta, dict):
            return None

        best_match = None
        best_score = 0

        for col, metric_meta in metrics_meta.items():
            if col not in df.columns:
                continue

            phrases = [col]
            if isinstance(metric_meta, dict):
                metric_name = metric_meta.get("name")
                if metric_name:
                    phrases.append(metric_name)
                metric_keywords = metric_meta.get("keywords") or []
                if isinstance(metric_keywords, list):
                    phrases.extend(str(keyword) for keyword in metric_keywords if keyword)
            elif metric_meta:
                phrases.append(str(metric_meta))

            for phrase in phrases:
                phrase_norm = _norm(phrase)
                if not phrase_norm:
                    continue
                if phrase_norm == metric_lower or metric_lower == phrase_norm:
                    return col
                if metric_lower in phrase_norm or phrase_norm in metric_lower:
                    score = len(set(phrase_norm.split()) & metric_words) + 2
                else:
                    phrase_words = set(phrase_norm.split())
                    score = len(metric_words & phrase_words)
                if score > best_score:
                    best_match = col
                    best_score = score

        return best_match if best_score > 0 else None

    metric_lower = _norm(metric)
    metric_words = set(metric_lower.split())
    alias_candidates = alias_candidates or {}
    alias_term_bundles = alias_term_bundles or {}

    metadata_match = _find_metadata_metric_match()
    if metadata_match:
        return metadata_match

    alias_match = _find_alias_match(alias_candidates.get(metric_lower, []))
    if alias_match:
        return alias_match

    bundle_match = _find_term_bundle_match(alias_term_bundles.get(metric_lower, []))
    if bundle_match:
        return bundle_match

    for col in df.columns:
        col_norm = _norm(col)
        if col_norm == metric_lower:
            return col

    for col in df.columns:
        col_norm = _norm(col)
        if metric_lower in col_norm:
            return col

    for col in df.columns:
        if col in ("loc_id", "year"):
            continue
        col_norm = _norm(col)
        if col_norm in metric_lower:
            return col

    if len(metric_words) >= 2:
        for col in df.columns:
            if col in ("loc_id", "year"):
                continue
            col_words = set(_norm(col).split())
            overlap = metric_words & col_words
            if len(overlap) >= 2:
                return col

    significant_words = metric_words - {"of", "the", "a", "an", "for", "in", "on", "to"}
    for col in df.columns:
        if col in ("loc_id", "year"):
            continue
        col_words = set(_norm(col).split())
        if significant_words & col_words:
            return col

    return None
