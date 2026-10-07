"""Visualization tools for GIS MCP Server."""

import base64
import io
import logging
import tempfile
from typing import Any

from locusync.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)

# Check if visualization libraries are available
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlib not available. Static map tools will be disabled.")

try:
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False
    logger.warning("Folium not available. Web map tools will be disabled.")


async def create_static_map(
    features: dict[str, Any] | list[dict[str, Any]],
    output_path: str | None = None,
    title: str | None = None,
    figsize: tuple[int, int] = (10, 10),
    style: dict[str, Any] | None = None,
    basemap: bool = False,
    return_base64: bool = False
) -> dict[str, Any]:
    """Create a static map image from GeoJSON features.

    Args:
        features: GeoJSON FeatureCollection or list of features.
        output_path: Optional path to save the image (PNG, PDF, SVG).
        title: Optional map title.
        figsize: Figure size in inches (width, height).
        style: Optional style dict with fill_color, edge_color, alpha, linewidth.
        basemap: If True, attempt to add a basemap (requires contextily).
        return_base64: If True, return base64-encoded image.

    Returns:
        GIS response with map file path or base64 data.
    """
    if not MATPLOTLIB_AVAILABLE:
        return make_error_response(
            "Matplotlib not installed. Install with: pip install matplotlib"
        )

    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        return make_error_response(
            "GeoPandas required. Install with: pip install geopandas"
        )

    # Parse features
    try:
        if isinstance(features, dict):
            if features.get("type") == "FeatureCollection":
                gdf = gpd.GeoDataFrame.from_features(features["features"])
            elif features.get("type") == "Feature":
                gdf = gpd.GeoDataFrame.from_features([features])
            else:
                # Assume it's a geometry
                geom = shape(features)
                gdf = gpd.GeoDataFrame(geometry=[geom])
        elif isinstance(features, list):
            gdf = gpd.GeoDataFrame.from_features(features)
        else:
            return make_error_response("Invalid features format")

        if gdf.empty:
            return make_error_response("No valid features to plot")

        # Set CRS if not present
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

    except Exception as e:
        return make_error_response(f"Failed to parse features: {str(e)}")

    # Default style
    default_style = {
        "fill_color": "#3388ff",
        "edge_color": "#000000",
        "alpha": 0.5,
        "linewidth": 1,
    }
    if style:
        default_style.update(style)

    try:
        fig, ax = plt.subplots(1, 1, figsize=figsize)

        # Plot features
        gdf.plot(
            ax=ax,
            color=default_style["fill_color"],
            edgecolor=default_style["edge_color"],
            alpha=default_style["alpha"],
            linewidth=default_style["linewidth"]
        )

        # Add basemap if requested
        if basemap:
            try:
                import contextily as ctx
                # Reproject to Web Mercator for basemap
                gdf_wm = gdf.to_crs(epsg=3857)
                gdf_wm.plot(
                    ax=ax,
                    color=default_style["fill_color"],
                    edgecolor=default_style["edge_color"],
                    alpha=default_style["alpha"],
                    linewidth=default_style["linewidth"]
                )
                ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
                ax.clear()
                gdf_wm.plot(
                    ax=ax,
                    color=default_style["fill_color"],
                    edgecolor=default_style["edge_color"],
                    alpha=default_style["alpha"],
                    linewidth=default_style["linewidth"]
                )
                ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
            except ImportError:
                logger.warning("contextily not available for basemap")
            except Exception as e:
                logger.warning(f"Failed to add basemap: {e}")

        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save or encode
        result_data = {}

        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            result_data["file_path"] = output_path

        if return_base64 or not output_path:
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            result_data["base64"] = base64.b64encode(buffer.read()).decode('utf-8')
            result_data["mime_type"] = "image/png"

        plt.close(fig)

        data = {
            "success": True,
            "feature_count": len(gdf),
            "bounds": list(gdf.total_bounds),
            **result_data
        }

        return make_success_response(data, {"title": title, "figsize": figsize})

    except Exception as e:
        logger.exception(f"Error creating static map: {e}")
        return make_error_response(f"Map creation failed: {str(e)}")


async def create_web_map(
    features: dict[str, Any] | list[dict[str, Any]],
    output_path: str | None = None,
    center: list[float] | None = None,
    zoom: int = 10,
    title: str | None = None,
    layer_name: str = "Features",
    style: dict[str, Any] | None = None,
    popup_fields: list[str] | None = None,
    basemap: str = "OpenStreetMap"
) -> dict[str, Any]:
    """Create an interactive web map from GeoJSON features.

    Args:
        features: GeoJSON FeatureCollection or list of features.
        output_path: Path to save HTML file.
        center: Map center [lat, lon]. If None, calculated from features.
        zoom: Initial zoom level (1-18).
        title: Optional map title.
        layer_name: Name for the feature layer.
        style: Style dict with color, fillColor, weight, opacity, fillOpacity.
        popup_fields: List of properties to show in popups.
        basemap: Basemap provider (OpenStreetMap, CartoDB positron, etc.).

    Returns:
        GIS response with HTML file path or content.
    """
    if not FOLIUM_AVAILABLE:
        return make_error_response(
            "Folium not installed. Install with: pip install folium"
        )

    try:
        import geopandas as gpd
        from shapely.geometry import shape
    except ImportError:
        return make_error_response(
            "GeoPandas required. Install with: pip install geopandas"
        )

    # Parse features
    try:
        if isinstance(features, dict):
            if features.get("type") == "FeatureCollection":
                gdf = gpd.GeoDataFrame.from_features(features["features"])
                geojson_data = features
            elif features.get("type") == "Feature":
                gdf = gpd.GeoDataFrame.from_features([features])
                geojson_data = {"type": "FeatureCollection", "features": [features]}
            else:
                geom = shape(features)
                gdf = gpd.GeoDataFrame(geometry=[geom])
                geojson_data = {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": features, "properties": {}}]
                }
        elif isinstance(features, list):
            gdf = gpd.GeoDataFrame.from_features(features)
            geojson_data = {"type": "FeatureCollection", "features": features}
        else:
            return make_error_response("Invalid features format")

        if gdf.empty:
            return make_error_response("No valid features to plot")

        gdf = gdf.set_crs("EPSG:4326") if gdf.crs is None else gdf.to_crs("EPSG:4326")

    except Exception as e:
        return make_error_response(f"Failed to parse features: {str(e)}")

    # Calculate center if not provided
    if center is None:
        bounds = gdf.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    # Default style
    default_style = {
        "color": "#3388ff",
        "fillColor": "#3388ff",
        "weight": 2,
        "opacity": 1,
        "fillOpacity": 0.5,
    }
    if style:
        default_style.update(style)

    try:
        # Create map
        basemap_tiles = {
            "OpenStreetMap": "OpenStreetMap",
            "CartoDB positron": "CartoDB positron",
            "CartoDB dark_matter": "CartoDB dark_matter",
            "Stamen Terrain": "Stamen Terrain",
            "Stamen Toner": "Stamen Toner",
        }

        tiles = basemap_tiles.get(basemap, "OpenStreetMap")
        m = folium.Map(location=center, zoom_start=zoom, tiles=tiles)

        if title:
            title_html = f'''
                <h3 style="position:fixed;
                           top:10px; left:50px;
                           z-index:9999;
                           background-color:white;
                           padding:10px;
                           border-radius:5px;
                           box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
                    {title}
                </h3>
            '''
            m.get_root().html.add_child(folium.Element(title_html))

        # Create style function
        def style_function(feature: dict[str, Any]) -> dict[str, Any]:
            return default_style

        # Create popup function
        def create_popup(feature: dict[str, Any]) -> folium.Popup | None:
            if popup_fields:
                props = feature.get("properties", {})
                html = "<br>".join([
                    f"<b>{field}</b>: {props.get(field, 'N/A')}"
                    for field in popup_fields
                    if field in props
                ])
                return folium.Popup(html, max_width=300)
            elif feature.get("properties"):
                props = feature["properties"]
                html = "<br>".join([
                    f"<b>{k}</b>: {v}"
                    for k, v in props.items()
                    if v is not None
                ])
                return folium.Popup(html, max_width=300) if html else None
            return None

        # Add GeoJSON layer
        geojson_layer = folium.GeoJson(
            geojson_data,
            name=layer_name,
            style_function=style_function,
            popup=folium.GeoJsonPopup(fields=popup_fields) if popup_fields else None,
        )
        geojson_layer.add_to(m)

        # Add layer control
        folium.LayerControl().add_to(m)

        # Fit bounds
        bounds = gdf.total_bounds
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        # Save or return
        result_data: dict[str, Any] = {}

        if output_path:
            m.save(output_path)
            result_data["file_path"] = output_path
        else:
            # Save to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                m.save(f.name)
                result_data["file_path"] = f.name

        # Also return HTML string for embedding
        html_repr = m._repr_html_()
        if html_repr is not None:
            result_data["html_size_kb"] = round(len(html_repr) / 1024, 2)

        data = {
            "success": True,
            "feature_count": len(gdf),
            "center": center,
            "zoom": zoom,
            "bounds": list(gdf.total_bounds),
            **result_data
        }

        return make_success_response(data, {
            "title": title,
            "layer_name": layer_name,
            "basemap": basemap
        })

    except Exception as e:
        logger.exception(f"Error creating web map: {e}")
        return make_error_response(f"Web map creation failed: {str(e)}")


async def create_choropleth_map(
    features: dict[str, Any],
    value_field: str,
    output_path: str | None = None,
    center: list[float] | None = None,
    zoom: int = 10,
    title: str | None = None,
    color_scheme: str = "YlOrRd",
    legend_name: str | None = None,
    bins: int = 5
) -> dict[str, Any]:
    """Create a choropleth (thematic) map based on a property value.

    Args:
        features: GeoJSON FeatureCollection with properties.
        value_field: Property name to use for coloring.
        output_path: Path to save HTML file.
        center: Map center [lat, lon].
        zoom: Initial zoom level.
        title: Optional map title.
        color_scheme: Color scheme (YlOrRd, Blues, Greens, etc.).
        legend_name: Legend title.
        bins: Number of color bins.

    Returns:
        GIS response with choropleth map.
    """
    if not FOLIUM_AVAILABLE:
        return make_error_response(
            "Folium not installed. Install with: pip install folium"
        )

    try:
        import branca.colormap as cm
        import geopandas as gpd
    except ImportError:
        return make_error_response(
            "GeoPandas and branca required for choropleth maps"
        )

    try:
        if features.get("type") != "FeatureCollection":
            return make_error_response("Choropleth requires a FeatureCollection")

        gdf = gpd.GeoDataFrame.from_features(features["features"])

        if value_field not in gdf.columns:
            return make_error_response(
                f"Field '{value_field}' not found. Available: {list(gdf.columns)}"
            )

        gdf = gdf.set_crs("EPSG:4326") if gdf.crs is None else gdf.to_crs("EPSG:4326")

        # Get value range
        values = gdf[value_field].dropna()
        if len(values) == 0:
            return make_error_response(f"No valid values in field '{value_field}'")

        vmin, vmax = float(values.min()), float(values.max())

        # Calculate center
        if center is None:
            bounds = gdf.total_bounds
            center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

        # Create map
        m = folium.Map(location=center, zoom_start=zoom)

        if title:
            title_html = f'''
                <h3 style="position:fixed;
                           top:10px; left:50px;
                           z-index:9999;
                           background-color:white;
                           padding:10px;
                           border-radius:5px;">
                    {title}
                </h3>
            '''
            m.get_root().html.add_child(folium.Element(title_html))

        # Create colormap
        colormap = cm.linear.YlOrRd_09.scale(vmin, vmax)
        if legend_name:
            colormap.caption = legend_name
        else:
            colormap.caption = value_field

        # Style function
        def style_function(feature: dict[str, Any]) -> dict[str, Any]:
            value = feature["properties"].get(value_field)
            if value is None:
                return {"fillColor": "#gray", "fillOpacity": 0.3}
            return {
                "fillColor": colormap(value),
                "fillOpacity": 0.7,
                "color": "#000",
                "weight": 1,
            }

        # Add GeoJSON
        folium.GeoJson(
            features,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(fields=[value_field])
        ).add_to(m)

        colormap.add_to(m)

        # Fit bounds
        bounds = gdf.total_bounds
        m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

        # Save
        result_data = {}
        if output_path:
            m.save(output_path)
            result_data["file_path"] = output_path
        else:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
                m.save(f.name)
                result_data["file_path"] = f.name

        data = {
            "success": True,
            "feature_count": len(gdf),
            "value_field": value_field,
            "value_range": {"min": vmin, "max": vmax},
            "center": center,
            **result_data
        }

        return make_success_response(data, {
            "color_scheme": color_scheme,
            "bins": bins
        })

    except Exception as e:
        logger.exception(f"Error creating choropleth map: {e}")
        return make_error_response(f"Choropleth creation failed: {str(e)}")
