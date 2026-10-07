# create_web_map

Create an interactive web map (HTML) using Folium with multiple layers and dynamic controls.

## Description

The `create_web_map` function generates interactive HTML maps using Folium that can be opened in web browsers. The maps include layer controls, legends, scale bars, and dynamic titles that update based on visible layers.

## Parameters

| Parameter     | Type                   | Default           | Description                                             |
| ------------- | ---------------------- | ----------------- | ------------------------------------------------------- |
| `layers`      | `List[Dict[str, Any]]` | **Required**      | List of layer dictionaries with "data" and "style" keys |
| `filename`    | `str`                  | `"map.html"`      | Output HTML filename                                    |
| `title`       | `str`                  | `"My Map"`        | Main map title                                          |
| `output_dir`  | `str`                  | `"outputs"`       | Directory to save HTML file                             |
| `show_grid`   | `bool`                 | `True`            | Show lat/lng popup and scale bar                        |
| `add_legend`  | `bool`                 | `True`            | Add custom legend with layer colors                     |
| `basemap`     | `str`                  | `"OpenStreetMap"` | Basemap tile provider                                   |
| `add_minimap` | `bool`                 | `True`            | Add minimap in bottom-right corner                      |

## Layer Structure

Each layer should be a dictionary with:

```python
{
    "data": "path/to/data.shp",  # or GeoJSON, WKT, or GeoDataFrame
    "style": {
        "label": "Layer Name",     # Display name in legend
        "color": "blue",           # Feature color
        # Additional styling options
    }
}
```

## Supported Data Types

### Shapefiles

```python
{
    "data": "features.shp",
    "style": {"label": "Buildings", "color": "red"}
}
```

### GeoJSON Files

```python
{
    "data": "data.geojson",
    "style": {"label": "Points", "color": "blue"}
}
```

### WKT Geometries

```python
{
    "data": "POINT(-74.0 40.7)",
    "style": {"label": "Location", "color": "green"}
}
```

### GeoPandas DataFrames

```python
import geopandas as gpd
gdf = gpd.read_file("data.shp")

{
    "data": gdf,
    "style": {"label": "Vector Data", "color": "purple"}
}
```

## Basemap Options

Available basemap tile providers:

- `"OpenStreetMap"` (default)
- `"CartoDB positron"`
- `"CartoDB dark_matter"`
- `"Stamen Terrain"`
- `"Stamen Toner"`
- `"Stamen Watercolor"`

## Example Usage

```python
# Create interactive web map
layers = [
    {
        "data": "buildings.shp",
        "style": {"label": "Buildings", "color": "red"}
    },
    {
        "data": "roads.shp",
        "style": {"label": "Road Network", "color": "black"}
    },
    {
        "data": "parks.geojson",
        "style": {"label": "Parks", "color": "green"}
    }
]

result = create_web_map(
    layers=layers,
    filename="city_interactive.html",
    title="City Infrastructure Map",
    basemap="CartoDB positron",
    show_grid=True,
    add_legend=True,
    add_minimap=True,
    output_dir="web_maps"
)
```

## Interactive Features

### Layer Control

- Toggle layers on/off
- Dynamic title updates based on visible layers
- Layer-specific styling

### Navigation

- Zoom and pan controls
- Minimap for overview
- Scale bar for distance reference
- Lat/Lng popup on click

### Legend

- Custom legend with layer colors
- Fixed position (bottom-left)
- Responsive design

### Dynamic Title

- Main title at top
- Subtitle showing active layers
- Updates automatically when layers are toggled

## Return Value

Returns a dictionary with:

```python
{
    "status": "success",  # or "error"
    "message": "Map created: /path/to/map.html",
    "output_path": "/full/path/to/html/file"
}
```

## Error Handling

If an error occurs:

```python
{
    "status": "error",
    "message": "Error description"
}
```

## Advanced Features

### Tooltips

- Automatic tooltips for vector features
- Shows all non-geometry columns
- Hover to display attribute data

### Layer Styling

- Custom colors per layer
- Opacity controls
- Line weights and styles
- Fill patterns

### JavaScript Integration

- Custom JavaScript for dynamic behavior
- Layer toggle event handling
- Title updates based on layer visibility

## File Structure

The generated HTML file includes:

- **Folium map object** - Interactive map container
- **Layer controls** - Toggle switches for each layer
- **Custom CSS** - Styling for legend and title
- **JavaScript** - Dynamic behavior and event handling
- **Embedded data** - All geospatial data as GeoJSON

## Browser Compatibility

- Modern web browsers (Chrome, Firefox, Safari, Edge)
- Mobile responsive design
- Touch-friendly controls for mobile devices
