"""Spatial statistics tools for LocuSync Server.

These tools require the optional 'statistics' dependencies:
    pip install locusync-server[statistics]
"""

import logging
from typing import Any

from locusync.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)

# Check if PySAL is available
try:
    import esda
    import libpysal  # noqa: F401
    import numpy as np
    PYSAL_AVAILABLE = True
except ImportError:
    PYSAL_AVAILABLE = False
    logger.warning("PySAL not available. Spatial statistics tools will be disabled.")


def _check_pysal() -> dict[str, Any] | None:
    """Check if PySAL is available."""
    if not PYSAL_AVAILABLE:
        return make_error_response(
            "PySAL not installed. Install with: pip install locusync-server[statistics]"
        )
    return None


async def calculate_moran_i(
    features: dict[str, Any],
    value_field: str,
    weight_type: str = "queen",
    permutations: int = 999
) -> dict[str, Any]:
    """Calculate Global Moran's I statistic for spatial autocorrelation.

    Moran's I measures the overall clustering of spatial data:
    - Positive values indicate clustering of similar values
    - Negative values indicate dispersion
    - Values near 0 indicate random distribution

    Args:
        features: GeoJSON FeatureCollection with polygons/points.
        value_field: Property name containing the numeric values to analyze.
        weight_type: Spatial weights type ('queen', 'rook', or 'knn').
        permutations: Number of permutations for significance testing.

    Returns:
        GIS response with Moran's I results.
    """
    error = _check_pysal()
    if error is not None:
        return error

    try:
        import geopandas as gpd
        from libpysal.weights import KNN, Queen, Rook
    except ImportError:
        return make_error_response("GeoPandas required for spatial statistics")

    try:
        if features.get("type") != "FeatureCollection":
            return make_error_response("Input must be a FeatureCollection")

        gdf = gpd.GeoDataFrame.from_features(features["features"])

        if value_field not in gdf.columns:
            return make_error_response(
                f"Field '{value_field}' not found. Available: {list(gdf.columns)}"
            )

        # Get values
        y = gdf[value_field].values.astype(float)

        # Check for NaN
        if np.isnan(y).any():
            return make_error_response(f"Field '{value_field}' contains NaN values")

        # Create spatial weights
        weight_type = weight_type.lower()
        if weight_type == "queen":
            w = Queen.from_dataframe(gdf)
        elif weight_type == "rook":
            w = Rook.from_dataframe(gdf)
        elif weight_type == "knn":
            w = KNN.from_dataframe(gdf, k=5)
        else:
            return make_error_response(
                "Invalid weight_type. Use 'queen', 'rook', or 'knn'"
            )

        # Calculate Moran's I
        mi = esda.Moran(y, w, permutations=permutations)

        # Interpret result
        if mi.p_sim < 0.05:
            if mi.I > 0:
                interpretation = "Significant positive spatial autocorrelation (clustering)"
            else:
                interpretation = "Significant negative spatial autocorrelation (dispersion)"
        else:
            interpretation = "No significant spatial autocorrelation (random pattern)"

        data = {
            "morans_i": round(mi.I, 6),
            "expected_i": round(mi.EI, 6),
            "variance": round(mi.VI_sim, 6),
            "z_score": round(mi.z_sim, 4),
            "p_value": round(mi.p_sim, 4),
            "significant_at_005": mi.p_sim < 0.05,
            "interpretation": interpretation,
        }

        metadata = {
            "value_field": value_field,
            "weight_type": weight_type,
            "permutations": permutations,
            "n_features": len(gdf),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error calculating Moran's I: {e}")
        return make_error_response(f"Moran's I calculation failed: {str(e)}")


async def calculate_local_moran(
    features: dict[str, Any],
    value_field: str,
    weight_type: str = "queen",
    permutations: int = 999
) -> dict[str, Any]:
    """Calculate Local Moran's I (LISA) for each feature.

    Local Indicators of Spatial Association identify local clusters and outliers:
    - High-High: Cluster of high values (hot spot)
    - Low-Low: Cluster of low values (cold spot)
    - High-Low: High value surrounded by low values (outlier)
    - Low-High: Low value surrounded by high values (outlier)

    Args:
        features: GeoJSON FeatureCollection.
        value_field: Property name for analysis.
        weight_type: Spatial weights type.
        permutations: Number of permutations.

    Returns:
        GIS response with local statistics for each feature.
    """
    error = _check_pysal()
    if error is not None:
        return error

    try:
        import geopandas as gpd
        from libpysal.weights import KNN, Queen, Rook
    except ImportError:
        return make_error_response("GeoPandas required")

    try:
        if features.get("type") != "FeatureCollection":
            return make_error_response("Input must be a FeatureCollection")

        gdf = gpd.GeoDataFrame.from_features(features["features"])

        if value_field not in gdf.columns:
            return make_error_response(f"Field '{value_field}' not found")

        y = gdf[value_field].values.astype(float)

        if np.isnan(y).any():
            return make_error_response(f"Field '{value_field}' contains NaN values")

        # Create weights
        weight_type = weight_type.lower()
        if weight_type == "queen":
            w = Queen.from_dataframe(gdf)
        elif weight_type == "rook":
            w = Rook.from_dataframe(gdf)
        elif weight_type == "knn":
            w = KNN.from_dataframe(gdf, k=5)
        else:
            return make_error_response("Invalid weight_type")

        # Calculate Local Moran's I
        lisa = esda.Moran_Local(y, w, permutations=permutations)

        # Classify clusters
        # Quadrant: 1=HH, 2=LH, 3=LL, 4=HL
        quadrant_labels = {1: "High-High", 2: "Low-High", 3: "Low-Low", 4: "High-Low"}

        local_results = []
        for i in range(len(gdf)):
            significant = lisa.p_sim[i] < 0.05
            quad_label = quadrant_labels.get(lisa.q[i], "Not significant")
            cluster_type = quad_label if significant else "Not significant"

            local_results.append({
                "feature_index": i,
                "local_i": round(float(lisa.Is[i]), 6),
                "z_score": round(float(lisa.z_sim[i]), 4),
                "p_value": round(float(lisa.p_sim[i]), 4),
                "quadrant": int(lisa.q[i]),
                "cluster_type": cluster_type,
                "significant": significant,
            })

        # Summary - count each cluster type
        def count_type(t: str) -> int:
            return sum(1 for r in local_results if r["cluster_type"] == t)

        cluster_counts = {
            "High-High (hot spots)": count_type("High-High"),
            "Low-Low (cold spots)": count_type("Low-Low"),
            "High-Low (outliers)": count_type("High-Low"),
            "Low-High (outliers)": count_type("Low-High"),
            "Not significant": count_type("Not significant"),
        }

        data = {
            "local_statistics": local_results,
            "cluster_summary": cluster_counts,
            "total_significant": sum(1 for r in local_results if r["significant"]),
        }

        metadata = {
            "value_field": value_field,
            "weight_type": weight_type,
            "permutations": permutations,
            "n_features": len(gdf),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error calculating Local Moran's I: {e}")
        return make_error_response(f"Local Moran's I failed: {str(e)}")


async def calculate_getis_ord(
    features: dict[str, Any],
    value_field: str,
    weight_type: str = "distance",
    threshold: float | None = None,
    permutations: int = 999
) -> dict[str, Any]:
    """Calculate Getis-Ord Gi* statistic for hot spot analysis.

    Getis-Ord Gi* identifies statistically significant hot spots and cold spots:
    - High positive z-scores indicate hot spots (clustering of high values)
    - Low negative z-scores indicate cold spots (clustering of low values)

    Args:
        features: GeoJSON FeatureCollection.
        value_field: Property name for analysis.
        weight_type: Weight type ('distance' or 'queen').
        threshold: Distance threshold for distance-based weights.
        permutations: Number of permutations.

    Returns:
        GIS response with Gi* statistics.
    """
    error = _check_pysal()
    if error is not None:
        return error

    try:
        import geopandas as gpd
        from libpysal.weights import DistanceBand, Queen
    except ImportError:
        return make_error_response("GeoPandas required")

    try:
        if features.get("type") != "FeatureCollection":
            return make_error_response("Input must be a FeatureCollection")

        gdf = gpd.GeoDataFrame.from_features(features["features"])

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        if value_field not in gdf.columns:
            return make_error_response(f"Field '{value_field}' not found")

        y = gdf[value_field].values.astype(float)

        if np.isnan(y).any():
            return make_error_response(f"Field '{value_field}' contains NaN values")

        # Create weights
        weight_type = weight_type.lower()
        if weight_type == "distance":
            # Calculate threshold if not provided
            if threshold is None:
                # Use centroid distances
                from libpysal.weights import min_threshold_distance
                centroids = gdf.geometry.centroid
                coords = np.array([[p.x, p.y] for p in centroids])
                threshold = min_threshold_distance(coords) * 1.5

            # Need to reproject to projected CRS for distance
            gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())
            w = DistanceBand.from_dataframe(gdf_proj, threshold=threshold)
        elif weight_type == "queen":
            w = Queen.from_dataframe(gdf)
        else:
            return make_error_response("Invalid weight_type. Use 'distance' or 'queen'")

        # Calculate Getis-Ord G*
        g_star = esda.G_Local(y, w, star=True, permutations=permutations)

        # Classify results
        local_results = []
        for i in range(len(gdf)):
            z = float(g_star.Zs[i])
            p = float(g_star.p_sim[i])

            if p < 0.01:
                confidence = "99%"
            elif p < 0.05:
                confidence = "95%"
            elif p < 0.10:
                confidence = "90%"
            else:
                confidence = "Not significant"

            if confidence != "Not significant":
                spot_type = "Hot spot" if z > 0 else "Cold spot"
            else:
                spot_type = "Not significant"

            local_results.append({
                "feature_index": i,
                "gi_star": round(float(g_star.Gs[i]), 6),
                "z_score": round(z, 4),
                "p_value": round(p, 4),
                "spot_type": spot_type,
                "confidence": confidence,
            })

        # Summary
        hot_spots = sum(1 for r in local_results if r["spot_type"] == "Hot spot")
        cold_spots = sum(1 for r in local_results if r["spot_type"] == "Cold spot")

        data = {
            "local_statistics": local_results,
            "summary": {
                "hot_spots": hot_spots,
                "cold_spots": cold_spots,
                "not_significant": len(local_results) - hot_spots - cold_spots,
            },
        }

        metadata = {
            "value_field": value_field,
            "weight_type": weight_type,
            "threshold": threshold,
            "permutations": permutations,
            "n_features": len(gdf),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error calculating Getis-Ord Gi*: {e}")
        return make_error_response(f"Getis-Ord calculation failed: {str(e)}")


async def create_spatial_weights(
    features: dict[str, Any],
    weight_type: str = "queen",
    k: int = 5,
    threshold: float | None = None
) -> dict[str, Any]:
    """Create a spatial weights matrix from features.

    Spatial weights define the neighbor relationships between features.

    Args:
        features: GeoJSON FeatureCollection.
        weight_type: Type of weights ('queen', 'rook', 'knn', 'distance').
        k: Number of neighbors for KNN weights.
        threshold: Distance threshold for distance-band weights.

    Returns:
        GIS response with weights matrix summary.
    """
    error = _check_pysal()
    if error is not None:
        return error

    try:
        import geopandas as gpd
        from libpysal.weights import KNN, DistanceBand, Queen, Rook
    except ImportError:
        return make_error_response("GeoPandas required")

    try:
        if features.get("type") != "FeatureCollection":
            return make_error_response("Input must be a FeatureCollection")

        gdf = gpd.GeoDataFrame.from_features(features["features"])

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        # Create weights
        weight_type = weight_type.lower()
        if weight_type == "queen":
            w = Queen.from_dataframe(gdf)
            description = "Queen contiguity (shared edge or vertex)"
        elif weight_type == "rook":
            w = Rook.from_dataframe(gdf)
            description = "Rook contiguity (shared edge only)"
        elif weight_type == "knn":
            w = KNN.from_dataframe(gdf, k=k)
            description = f"K-Nearest Neighbors (k={k})"
        elif weight_type == "distance":
            if threshold is None:
                from libpysal.weights import min_threshold_distance
                gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())
                centroids = gdf_proj.geometry.centroid
                coords = np.array([[p.x, p.y] for p in centroids])
                threshold = min_threshold_distance(coords)
            gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())
            w = DistanceBand.from_dataframe(gdf_proj, threshold=threshold)
            description = f"Distance band (threshold={threshold:.2f})"
        else:
            return make_error_response(
                "Invalid weight_type. Use 'queen', 'rook', 'knn', or 'distance'"
            )

        # Get neighbor counts
        neighbor_counts = [len(neighbors) for neighbors in w.neighbors.values()]

        data = {
            "weight_type": weight_type,
            "description": description,
            "n_features": w.n,
            "n_nonzero": w.nonzero,
            "min_neighbors": min(neighbor_counts),
            "max_neighbors": max(neighbor_counts),
            "mean_neighbors": round(sum(neighbor_counts) / len(neighbor_counts), 2),
            "islands": len(w.islands),  # Features with no neighbors
        }

        if weight_type == "knn":
            data["k"] = k
        if weight_type == "distance":
            data["threshold"] = threshold

        metadata = {
            "weight_type": weight_type,
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error creating spatial weights: {e}")
        return make_error_response(f"Spatial weights creation failed: {str(e)}")
