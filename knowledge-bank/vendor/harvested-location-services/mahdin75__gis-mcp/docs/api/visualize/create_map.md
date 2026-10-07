# create_map

Create a styled static map from multiple geospatial data sources.

## Description

The `create_map` function generates high-quality static maps (PNG, PDF, JPG) from various geospatial data sources including shapefiles, rasters, WKT geometries, and coordinate arrays. The function supports multiple layers with individual styling options.

## Parameters

| Parameter    | Type                   | Default      | Description                                                         |
| ------------ | ---------------------- | ------------ | ------------------------------------------------------------------- |
| `layers`     | `List[Dict[str, Any]]` | **Required** | List of layer dictionaries, each containing "data" and "style" keys |
| `filename`   | `str`                  | `"map"`      | Output filename without extension                                   |
| `filetype`   | `str`                  | `"png"`      | Output format: "png", "pdf", "jpg", etc.                            |
| `title`      | `str`                  | `None`       | Optional map title                                                  |
| `show_grid`  | `bool`                 | `True`       | Display coordinate grid                                             |
| `add_legend` | `bool`                 | `True`       | Add legend if layer labels provided                                 |
| `output_dir` | `str`                  | `"outputs"`  | Directory to save the output file                                   |

## Layer Structure

Each layer in the `layers` list should be a dictionary with:

```python
{
    "data": "path/to/data.shp",  # or WKT string, or coordinate list
    "style": {
        "label": "Layer Name",     # Optional: for legend
        "color": "blue",           # Optional: feature color
        "alpha": 0.7,             # Optional: transparency
        "linewidth": 2,           # Optional: line thickness
        "markersize": 8,          # Optional: point size
        # ... other matplotlib styling options
    }
}
```

## Supported Data Types

### Shapefiles

```python
{
    "data": "path/to/features.shp",
    "style": {"label": "Buildings", "color": "red", "alpha": 0.6}
}
```

### Raster Files

```python
{
    "data": "path/to/raster.tif",
    "style": {"cmap": "viridis", "alpha": 0.8}
}
```

### WKT Geometries

```python
{
    "data": "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
    "style": {"label": "Custom Area", "color": "green"}
}
```

### Coordinate Arrays

```python
{
    "data": [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]],  # Polygon
    "style": {"label": "Polygon", "color": "blue"}
}
```

## Example Usage

```python
# Create a map with multiple layers
layers = [
    {
        "data": "buildings.shp",
        "style": {"label": "Buildings", "color": "red", "alpha": 0.7}
    },
    {
        "data": "roads.shp",
        "style": {"label": "Roads", "color": "black", "linewidth": 1}
    },
    {
        "data": "satellite.tif",
        "style": {"cmap": "terrain", "alpha": 0.5}
    }
]

result = create_map(
    layers=layers,
    filename="city_analysis",
    filetype="png",
    title="City Infrastructure Analysis",
    show_grid=True,
    add_legend=True,
    output_dir="maps"
)
```

## Return Value

Returns a dictionary with:

```python
{
    "status": "success",  # or "error"
    "message": "Map created and saved to /path/to/output.png",
    "output_path": "/full/path/to/output/file"
}
```

## Error Handling

If an error occurs, the function returns:

```python
{
    "status": "error",
    "message": "Error description"
}
```

## Styling Options

The `style` dictionary supports all matplotlib plotting parameters:

- **Colors**: `color`, `facecolor`, `edgecolor`
- **Transparency**: `alpha` (0.0 to 1.0)
- **Line styling**: `linewidth`, `linestyle`, `linecolor`
- **Point styling**: `markersize`, `marker`, `markerfacecolor`
- **Fill patterns**: `hatch`, `fill`
- **Colormaps**: `cmap` (for rasters)

## Output Quality

- **DPI**: 300 (high resolution)
- **Format**: Supports PNG, PDF, JPG, SVG
- **Bbox**: Tight bounding box around data
- **Transparency**: Preserved in PNG format
