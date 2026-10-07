import logging
import pandas as pd


def execute_geometry_overlay_impl(
    geometry_overlay: dict,
    *,
    filter_loc_ids: list = None,
    get_source_path_func,
    parquet_columns_func,
    select_columns_from_parquet_func,
    df_to_geojson_func,
) -> dict:
    logger = logging.getLogger(__name__)

    source_id = geometry_overlay.get("source_id")
    if not source_id:
        logger.warning("No source_id in geometry_overlay")
        return {"type": "FeatureCollection", "features": []}

    source_path = get_source_path_func(source_id)
    if not source_path:
        logger.warning(f"Source not found in catalog: {source_id}")
        return {"type": "FeatureCollection", "features": []}

    full_path = source_path
    parquet_files = list(full_path.glob("*.parquet")) if full_path.is_dir() else []

    if not parquet_files:
        logger.warning(f"No parquet files found in {full_path}")
        return {"type": "FeatureCollection", "features": []}

    parquet_path = parquet_files[0]
    logger.info(f"Loading geometry overlay from {parquet_path}")

    try:
        columns = parquet_columns_func(parquet_path) or ["loc_id", "name", "geometry", "parent_id"]
        df = select_columns_from_parquet_func(parquet_path, columns)
        if df.empty:
            df = pd.read_parquet(parquet_path, columns=columns)
        logger.info(f"Loaded {len(df)} features from {parquet_path}")

        if filter_loc_ids and len(filter_loc_ids) > 0 and "parent_id" in df.columns:
            filter_conditions = []
            for loc_id in filter_loc_ids:
                filter_conditions.append(df["parent_id"].str.startswith(loc_id + "-", na=False))
                filter_conditions.append(df["parent_id"] == loc_id)

            if filter_conditions:
                combined_filter = filter_conditions[0]
                for cond in filter_conditions[1:]:
                    combined_filter = combined_filter | cond
                df = df[combined_filter]
                logger.info(f"Filtered to {len(df)} features for regions: {filter_loc_ids}")

        geojson = df_to_geojson_func(df, polygon_only=True)
        logger.info(f"Returning {len(geojson.get('features', []))} geometry features")
        return geojson

    except Exception as e:
        logger.error(f"Error loading geometry overlay: {e}")
        return {"type": "FeatureCollection", "features": []}


def execute_geometry_order_impl(
    order: dict,
    *,
    execute_geometry_overlay_func,
    load_source_metadata_func,
) -> dict:
    logger = logging.getLogger(__name__)

    items = order.get("items", [])
    summary = order.get("summary", "")

    if not items:
        return {
            "type": "geometry",
            "data_type": "geometry",
            "geojson": {"type": "FeatureCollection", "features": []},
            "count": 0,
            "message": "No items in order",
        }

    all_features = []
    overlay_type = None

    for item in items:
        source_id = item.get("source_id")
        region = item.get("region")
        item_overlay_type = item.get("overlay_type")
        if not item_overlay_type and source_id:
            try:
                source_meta = load_source_metadata_func(source_id) or {}
                item_overlay_type = source_meta.get("overlay_type") or item_overlay_type
            except Exception:
                item_overlay_type = item_overlay_type

        if not source_id:
            continue

        if item_overlay_type and not overlay_type:
            overlay_type = item_overlay_type

        filter_loc_ids = [region] if region else None
        logger.info(f"Executing geometry order: source={source_id}, region={region}, overlay_type={item_overlay_type}")

        geojson = execute_geometry_overlay_func(
            {"source_id": source_id, "overlay_type": item_overlay_type},
            filter_loc_ids=filter_loc_ids,
        )

        item_features = geojson.get("features", [])
        all_features.extend(item_features)
        logger.info(f"Added {len(item_features)} features from {source_id}")

    return {
        "type": "geometry",
        "data_type": "geometry",
        "overlay_type": overlay_type or "zcta",
        "geojson": {
            "type": "FeatureCollection",
            "features": all_features,
        },
        "count": len(all_features),
        "summary": summary or f"Showing {len(all_features)} geometry features",
    }
