import os
import folium
import geopandas as gpd
from shapely import wkt
from matplotlib import cm, colors
from ..mcp import gis_mcp

try:
    from folium.plugins import ScaleBar, MiniMap
    HAS_SCALEBAR = True
except ImportError:
    from folium.plugins import MiniMap
    HAS_SCALEBAR = False


@gis_mcp.tool()
def create_web_map(
    layers,
    filename: str = "map.html",
    title: str = "My Map",
    output_dir: str = "outputs",
    show_grid: bool = True,
    add_legend: bool = True,
    basemap: str = "OpenStreetMap",
    add_minimap: bool = True,
):
    """
    Create an interactive web map (HTML) using Folium.
    Supports unique per-feature coloring when 'column' is provided in style.

    Args:
        layers (list): List of dicts like {"data": "...", "style": {...}}
            - "style" may include:
                {"label": "Layer Name", "color": "blue"}
                {"column": "NAME_1", "cmap": "tab20"}  # for unique feature colors
        filename (str): Output HTML filename.
        title (str): Main map title.
        output_dir (str): Output directory for HTML.
    """
    try:
        m = folium.Map(location=[20, 0], zoom_start=2, tiles=basemap)
        legend_items = []

        for layer in layers:
            data = layer.get("data")
            style = layer.get("style", {})
            label = style.get("label", "Layer")

            if isinstance(data, str):
                data = os.path.abspath(data)
                if data.lower().endswith((".shp", ".geojson")):
                    gdf = gpd.read_file(data)
                else:
                    geom = wkt.loads(data)
                    gdf = gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
            elif isinstance(data, gpd.GeoDataFrame):
                gdf = data
            else:
                raise ValueError(f"Unsupported data type for {data}")

            fields = [c for c in gdf.columns if c != gdf.geometry.name]

            if "column" in style:
                column = style["column"]
                cmap = cm.get_cmap(style.get("cmap", "tab20"), len(gdf[column].unique()))
                norm = colors.Normalize(vmin=0, vmax=len(gdf[column].unique()) - 1)

                color_map = {
                    val: colors.to_hex(cmap(i))
                    for i, val in enumerate(sorted(gdf[column].unique()))
                }

                def style_func(feature):
                    val = feature["properties"].get(column, "Unknown")
                    col = color_map.get(val, "#000000")
                    return {
                        "color": "black",
                        "fillColor": col,
                        "weight": 1,
                        "fillOpacity": 0.7,
                    }

                gj = folium.GeoJson(
                    gdf,
                    name=label,
                    style_function=style_func,
                    tooltip=folium.GeoJsonTooltip(fields=[column], aliases=[column]),
                )
                gj.add_to(m)

                legend_items.extend([(val, col) for val, col in color_map.items()])

            else:
                color = style.get("color", "blue")
                gj = folium.GeoJson(
                    gdf,
                    name=label,
                    style_function=lambda x, col=color: {
                        "color": col,
                        "fillColor": col,
                        "weight": 2,
                        "fillOpacity": 0.5,
                    },
                    tooltip=folium.GeoJsonTooltip(fields=fields, aliases=fields) if fields else None,
                )
                gj.add_to(m)
                legend_items.append((label, color))

        folium.LayerControl().add_to(m)
        if show_grid:
            folium.LatLngPopup().add_to(m)
            if HAS_SCALEBAR:
                ScaleBar(position="bottomleft").add_to(m)
        if add_minimap:
            MiniMap(toggle_display=True, position="bottomright").add_to(m)

        # Legend
        if add_legend and legend_items:
            legend_html = """
            <div style="
                position: fixed; 
                bottom: 50px; left: 50px; width: 220px; 
                background-color: white; 
                border:2px solid grey; 
                z-index:9999; 
                font-size:14px;
                padding: 10px;
                max-height: 300px;
                overflow-y: auto;
            ">
            <b>Legend</b><br>
            """
            for label, color in legend_items:
                legend_html += f"<i style='background:{color};width:18px;height:18px;float:left;margin-right:8px;'></i>{label}<br>"
            legend_html += "</div>"
            m.get_root().html.add_child(folium.Element(legend_html))

        # Title
        if title:
            title_html = f"""
                <div id="mapTitle" style="
                    position: fixed;
                    top: 10px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 9999;
                    font-size: 20px;
                    font-weight: bold;
                    background-color: rgba(255, 255, 255, 0.7);
                    padding: 5px 10px;
                    border-radius: 5px;
                    text-align: center;
                ">
                    {title}
                </div>
            """
            m.get_root().html.add_child(folium.Element(title_html))

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.abspath(os.path.join(output_dir, filename))
        m.save(output_path)

        return {"status": "success", "message": f"Map created: {output_path}", "output_path": output_path}

    except Exception as e:
        return {"status": "error", "message": f"create_web_map failed: {str(e)}"}
