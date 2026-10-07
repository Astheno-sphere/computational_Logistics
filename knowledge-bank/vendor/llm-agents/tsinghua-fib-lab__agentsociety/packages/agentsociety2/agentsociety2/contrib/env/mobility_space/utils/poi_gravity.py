"""Gravity-model POI selection shared by mobility harness and mobility skill."""

from __future__ import annotations

import math
import random
from typing import Any

LEGACY_GRAVITY_SAMPLE_SIZE = 50


def _distance_bin_index(distance: float) -> int | None:
    for d in range(1, 11):
        if (d - 1) * 1000 <= distance < d * 1000:
            return d
    return None


def _legacy_gravity_weights(
    candidates: list[dict],
) -> list[tuple[dict, float, float]]:
    bins: dict[str, list[dict]] = {f"{d}k": [] for d in range(1, 11)}
    bins["more"] = []
    for poi in candidates:
        d = float(poi.get("distance", 99999))
        idx = _distance_bin_index(d)
        if idx is None:
            bins["more"].append(poi)
        else:
            bins[f"{idx}k"].append(poi)

    weighted: list[tuple[dict, float, float]] = []
    for poi in candidates:
        d = max(float(poi.get("distance", 1)), 1.0)
        idx = _distance_bin_index(d)
        if idx is None:
            weight = 1e-10
        else:
            n_in_bin = len(bins[f"{idx}k"])
            ring_area = math.pi * ((idx * 1000) ** 2 - ((idx - 1) * 1000) ** 2)
            density = n_in_bin / ring_area if ring_area > 0 else 0.0
            weight = density / (d**2)
        weighted.append((poi, weight, d))
    return weighted


def gravity_model_candidates(
    pois: list[dict],
    *,
    sample_size: int = LEGACY_GRAVITY_SAMPLE_SIZE,
) -> list[tuple[dict, float]]:
    if not pois:
        return []
    if len(pois) == 1:
        return [(pois[0], 1.0)]

    weighted = _legacy_gravity_weights(pois)
    distance_probs = [1.0 / math.sqrt(item[2]) for item in weighted]
    total_dist = sum(distance_probs)
    if total_dist <= 0:
        distance_probs = [1.0 / len(weighted)] * len(weighted)
    else:
        distance_probs = [p / total_dist for p in distance_probs]

    draw_n = min(sample_size, len(weighted))
    sampled_indices = random.choices(
        range(len(weighted)),
        weights=distance_probs,
        k=draw_n,
    )
    sampled = [weighted[i] for i in sampled_indices]
    total_weight = sum(item[1] for item in sampled)
    if total_weight <= 0:
        return [(sampled[0][0], 1.0)]

    return [(item[0], item[1] / total_weight) for item in sampled]


def gravity_model(pois: list[dict]) -> dict | None:
    candidates = gravity_model_candidates(pois)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    poi_list, probs = zip(*candidates)
    return random.choices(poi_list, weights=probs, k=1)[0]


def poi_travel_mode(distance: float) -> str:
    return "walking" if distance < 1000 else "driving"


def _poi_aoi_id(p: dict) -> int | None:
    aoi_id = p.get("aoi_id")
    if aoi_id is None:
        position = p.get("position")
        if isinstance(position, dict):
            aoi_id = position.get("aoi_id")
    if aoi_id is None:
        return None
    return int(aoi_id)


def normalize_poi_candidates(raw_pois: list[Any]) -> list[dict]:
    normalized: list[dict] = []
    for p in raw_pois:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            poi_data, distance = p[0], p[1]
            if hasattr(poi_data, "model_dump"):
                poi_data = poi_data.model_dump()
            if isinstance(poi_data, dict):
                item = {
                    "poi_id": int(poi_data.get("poi_id") or poi_data.get("id")),
                    "name": poi_data.get("name", "unknown"),
                    "category": poi_data.get("category", ""),
                    "distance": float(distance),
                }
                aoi_id = _poi_aoi_id(poi_data)
                if aoi_id is not None:
                    item["aoi_id"] = aoi_id
                normalized.append(item)
            continue
        if hasattr(p, "model_dump"):
            p = p.model_dump()
        elif hasattr(p, "id"):
            p = {
                "id": p.id,
                "name": getattr(p, "name", "unknown"),
                "category": getattr(p, "category", ""),
                "distance": getattr(p, "distance", 0),
                "aoi_id": getattr(p, "aoi_id", None),
            }
        if not isinstance(p, dict):
            continue
        poi_id = p.get("poi_id") or p.get("id")
        distance = p.get("distance", 0)
        if isinstance(distance, str):
            try:
                distance = float(distance)
            except ValueError:
                distance = 0
        if poi_id is None:
            continue
        item = {
            "poi_id": int(poi_id),
            "name": p.get("name", "unknown"),
            "category": p.get("category", ""),
            "distance": float(distance),
        }
        aoi_id = _poi_aoi_id(p)
        if aoi_id is not None:
            item["aoi_id"] = aoi_id
        normalized.append(item)
    return normalized


def filter_out_of_anchor_aoi_pois(
    candidates: list[dict],
    *,
    home_aoi: int | None,
    work_aoi: int | None,
) -> list[dict]:
    if home_aoi is not None and work_aoi is not None and home_aoi == work_aoi:
        return candidates
    blocked = {int(x) for x in (home_aoi, work_aoi) if x is not None}
    if not blocked:
        return candidates
    filtered: list[dict] = []
    for poi in candidates:
        aoi_id = poi.get("aoi_id")
        if aoi_id is None:
            filtered.append(poi)
            continue
        if int(aoi_id) in blocked:
            continue
        filtered.append(poi)
    return filtered


def _extract_poi_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if hasattr(payload, "pois"):
        pois_attr = getattr(payload, "pois", None)
        if isinstance(pois_attr, list):
            return pois_attr
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("pois"), list):
        return payload["pois"]
    observations = payload.get("observations")
    if isinstance(observations, dict):
        for key, val in observations.items():
            if "find_nearby_pois" not in key:
                continue
            if hasattr(val, "pois"):
                pois_attr = getattr(val, "pois", None)
                if isinstance(pois_attr, list):
                    return pois_attr
            if hasattr(val, "model_dump"):
                val = val.model_dump()
            if isinstance(val, dict) and isinstance(val.get("pois"), list):
                return val["pois"]
    for key in ("response", "find_nearby_pois", "result"):
        nested = payload.get(key)
        if nested is not None and key != "response":
            extracted = _extract_poi_list(nested)
            if extracted:
                return extracted
    response = payload.get("response")
    if response is not None:
        return _extract_poi_list(response)
    return []


def parse_nearby_pois_from_ctx(ctx: dict) -> list[dict]:
    raw = _extract_poi_list(ctx)
    if not raw:
        observations = ctx.get("observations")
        if isinstance(observations, dict):
            for val in observations.values():
                raw = _extract_poi_list(val)
                if raw:
                    break
    return normalize_poi_candidates(raw)


def select_poi_by_gravity(
    ctx: dict,
    *,
    home_aoi: int | None = None,
    work_aoi: int | None = None,
    exclude_anchor_aois: bool = False,
) -> dict | None:
    candidates = parse_nearby_pois_from_ctx(ctx)
    if exclude_anchor_aois:
        candidates = filter_out_of_anchor_aoi_pois(
            candidates,
            home_aoi=home_aoi,
            work_aoi=work_aoi,
        )
    if not candidates:
        return None
    return gravity_model(candidates)
