from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[4]
AUDIT_DIR = Path(__file__).resolve().parent
INPUT_CSV = AUDIT_DIR / "state_only_fallback_rows.csv"
OUTPUT_CSV = AUDIT_DIR / "state_only_fallback_geo_analysis.csv"
SUMMARY_MD = AUDIT_DIR / "state_only_fallback_geo_summary.md"
USA_GEOMETRY = ROOT / "county-map-data" / "geometry" / "USA.parquet"
USA_COUNTIES = ROOT / "county-map-data" / "geometry" / "countries" / "USA" / "county.parquet"


def _load_geometry(value):
    if isinstance(value, str):
        return shape(json.loads(value))
    return value


def _load_state_geometries() -> dict[str, object]:
    from mapmover.runtime.geography_reference import translate_loc_id_to_geometry_id

    df = pd.read_parquet(USA_GEOMETRY, columns=["loc_id", "admin_level", "geometry", "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat"])
    df = df[df["admin_level"] == 1].copy()
    df["geometry"] = df["geometry"].map(_load_geometry)

    states: dict[str, object] = {}
    for local_state in sorted({f"USA-{abbr}" for abbr in (
        "AK","AL","AR","AS","AZ","CA","CO","CT","DC","DE","FL","GA","GU","HI","IA","ID","IL","IN","KS","KY","LA","MA","MD",
        "ME","MI","MN","MO","MP","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY","OH","OK","OR","PA","PR","RI","SC","SD",
        "TN","TX","UT","VA","VI","VT","WA","WI","WV","WY"
    )}):
        geom_id = translate_loc_id_to_geometry_id(local_state)
        match = df[df["loc_id"] == geom_id]
        if not match.empty:
            states[local_state] = match.iloc[0].to_dict()
    return states


def _load_counties() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(
        USA_COUNTIES,
        columns=["loc_id", "parent_id", "geometry", "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat"],
    ).copy()
    df["geometry"] = df["geometry"].map(_load_geometry)
    grouped: dict[str, pd.DataFrame] = {}
    for state_loc_id, group in df.groupby(df["loc_id"].astype(str).str.rsplit("-", n=1).str[0]):
        grouped[str(state_loc_id)] = group.reset_index(drop=True)
    return grouped


def _bbox_contains(row: dict, lon: float, lat: float) -> bool:
    return (
        row["bbox_min_lon"] <= lon <= row["bbox_max_lon"]
        and row["bbox_min_lat"] <= lat <= row["bbox_max_lat"]
    )


def _classify_row(row: pd.Series, state_geoms: dict[str, object], county_groups: dict[str, pd.DataFrame]) -> dict[str, object]:
    lon = float(row["longitude"])
    lat = float(row["latitude"])
    state_loc_id = str(row["state_loc_id"] or "").strip()
    point = Point(lon, lat)

    result: dict[str, object] = {
        "state_contains_point": False,
        "county_contains_point": False,
        "nearest_county_loc_id": None,
        "nearest_county_distance_deg": None,
        "geo_classification": None,
    }

    if lon == 0.0 and lat == 0.0:
        result["geo_classification"] = "zero_zero_bad_source_point"
        return result

    state_geom_row = state_geoms.get(state_loc_id)
    if state_geom_row is None:
        result["geo_classification"] = "missing_state_geometry"
        return result

    if _bbox_contains(state_geom_row, lon, lat) and state_geom_row["geometry"].covers(point):
        result["state_contains_point"] = True

    counties = county_groups.get(state_loc_id)
    if counties is None or counties.empty:
        result["geo_classification"] = "no_county_bank_for_state"
        return result

    bbox_candidates = counties[
        (counties["bbox_min_lon"] <= lon)
        & (counties["bbox_max_lon"] >= lon)
        & (counties["bbox_min_lat"] <= lat)
        & (counties["bbox_max_lat"] >= lat)
    ]
    for _, county in bbox_candidates.iterrows():
        if county["geometry"].covers(point):
            result["county_contains_point"] = True
            result["nearest_county_loc_id"] = county["loc_id"]
            result["nearest_county_distance_deg"] = 0.0
            result["geo_classification"] = "runtime_missed_county_containment"
            return result

    county_distances = counties["geometry"].map(lambda geom: geom.distance(point))
    nearest_idx = county_distances.idxmin()
    nearest_distance = float(county_distances.loc[nearest_idx])
    nearest_county = counties.loc[nearest_idx]
    result["nearest_county_loc_id"] = nearest_county["loc_id"]
    result["nearest_county_distance_deg"] = nearest_distance

    if result["state_contains_point"]:
        if nearest_distance <= 0.01:
            result["geo_classification"] = "inside_state_near_county_edge"
        else:
            result["geo_classification"] = "inside_state_far_from_any_county"
        return result

    if nearest_distance <= 0.25:
        result["geo_classification"] = "outside_state_but_near_claimed_state_county"
    else:
        result["geo_classification"] = "outside_claimed_state_far_away"
    return result


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT / "county-map"))

    state_geoms = _load_state_geometries()
    county_groups = _load_counties()
    df = pd.read_csv(INPUT_CSV)

    analysis_rows = []
    for row in df.to_dict(orient="records"):
        analysis = _classify_row(pd.Series(row), state_geoms, county_groups)
        analysis_rows.append({**row, **analysis})

    out = pd.DataFrame(analysis_rows)
    out.to_csv(OUTPUT_CSV, index=False)

    counts = out["geo_classification"].fillna("NULL").value_counts()
    state_counts = out.groupby(["geo_classification", "state"]).size().sort_values(ascending=False).head(20)
    lines = [
        "# State-Only Fallback Geo Summary",
        "",
        f"- input rows: {len(out)}",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- `{key}`: {int(value)}")
    lines.extend([
        "",
        "## Top State Splits",
        "",
        "```",
        state_counts.to_string(),
        "```",
    ])
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUTPUT_CSV)
    print(SUMMARY_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
