"""Shared derived-result calculation helpers."""

from __future__ import annotations


def _coerce_year_key(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def apply_derived_fields(boxes: dict, derived_specs: list, year: int = None, year_data: dict | None = None) -> dict:
    """Apply derived field calculations to filled metric boxes."""
    warnings = []
    produced_comparison_boxes = False

    def _resolve_metric_value(metrics: dict, candidates) -> tuple[object, str | None]:
        candidate_list = [candidate for candidate in (candidates or []) if candidate]
        if not candidate_list:
            return None, None

        for candidate in candidate_list:
            if candidate in metrics:
                return metrics[candidate], candidate

        lowered = {str(key).lower(): key for key in metrics.keys()}
        for candidate in candidate_list:
            matched_key = lowered.get(str(candidate).lower())
            if matched_key is not None:
                return metrics[matched_key], matched_key

        return None, None

    def _resolve_time_metric(loc_id: str, candidates, target_year: int | None, fallback: str) -> tuple[object, int | None]:
        if not isinstance(year_data, dict) or not year_data:
            return None, None
        matches = []
        for raw_key, loc_map in year_data.items():
            year_key = _coerce_year_key(raw_key)
            if year_key is None or not isinstance(loc_map, dict):
                continue
            metrics = loc_map.get(loc_id)
            if not isinstance(metrics, dict):
                continue
            value, _ = _resolve_metric_value(metrics, candidates)
            if value is None:
                continue
            matches.append((year_key, value))
        if not matches:
            warnings.append(f"{loc_id}: {fallback} unavailable")
            return None, None
        if target_year is not None:
            exact = [entry for entry in matches if entry[0] == target_year]
            if exact:
                return exact[0][1], exact[0][0]
        matches.sort(key=lambda entry: entry[0])
        if target_year is None:
            return matches[-1][1], matches[-1][0]
        if target_year < matches[0][0]:
            return matches[0][1], matches[0][0]
        if target_year > matches[-1][0]:
            return matches[-1][1], matches[-1][0]
        return min(matches, key=lambda entry: abs(entry[0] - target_year))[1], min(matches, key=lambda entry: abs(entry[0] - target_year))[0]

    for spec in derived_specs:
        if spec.get("calculation") == "time_delta":
            metric_name = spec.get("metric")
            metric_candidates = spec.get("metric_candidates") or [metric_name]
            label = spec.get("label", f"Change in {metric_name}")
            start_year = _coerce_year_key(spec.get("start_year"))
            end_year = _coerce_year_key(spec.get("end_year")) or year
            better_direction = str(spec.get("better_direction") or "").strip().lower()
            intent = str(spec.get("intent") or "change").strip().lower()

            loc_ids = set(boxes.keys())
            if isinstance(year_data, dict):
                for loc_map in year_data.values():
                    if isinstance(loc_map, dict):
                        loc_ids.update(loc_map.keys())

            for loc_id in loc_ids:
                start_val, resolved_start_year = _resolve_time_metric(loc_id, metric_candidates, start_year, f"{metric_name} baseline")
                end_val, resolved_end_year = _resolve_time_metric(loc_id, metric_candidates, end_year, f"{metric_name} latest")
                if start_val is None or end_val is None:
                    continue

                raw_delta = float(end_val) - float(start_val)
                if intent == "improvement":
                    result = -raw_delta if better_direction == "down" else raw_delta
                elif intent == "decline":
                    result = raw_delta if better_direction == "down" else -raw_delta
                elif intent == "volatility":
                    result = abs(raw_delta)
                else:
                    result = raw_delta

                metrics = boxes.setdefault(loc_id, {})
                metrics[f"{label} (calculated)"] = result
                if resolved_start_year is not None:
                    metrics["_comparison_start_year"] = resolved_start_year
                if resolved_end_year is not None:
                    metrics["_comparison_end_year"] = resolved_end_year
                produced_comparison_boxes = True
            continue

        numerator_name = spec.get("numerator")
        denominator_name = spec.get("denominator")
        numerator_candidates = spec.get("numerator_candidates") or [numerator_name]
        denominator_candidates = spec.get("denominator_candidates") or [denominator_name]
        label = spec.get("label", f"{numerator_name}/{denominator_name}")
        multiplier = spec.get("multiplier", 1)

        for loc_id, metrics in boxes.items():
            num_val, _ = _resolve_metric_value(metrics, numerator_candidates)
            if num_val is None:
                continue

            denom_val, resolved_denominator_key = _resolve_metric_value(metrics, denominator_candidates)
            if denom_val is None:
                warnings.append(f"{loc_id}: {denominator_name} unavailable")
                continue

            if denom_val == 0:
                zero_name = resolved_denominator_key or denominator_name
                warnings.append(f"{loc_id}: {zero_name} is zero")
                continue

            result = (float(num_val) / float(denom_val)) * multiplier
            metrics[f"{label} (calculated)"] = result

    return {
        "warnings": warnings,
        "produced_comparison_boxes": produced_comparison_boxes,
    }
