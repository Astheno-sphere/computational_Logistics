# Visualization API

The visualization module provides tools for creating both static and interactive maps from geospatial data. This module requires the `[visualize]` extra to be installed.

## Installation

```bash
pip install gis-mcp[visualize]
```

## Available Functions

### Static Maps

- **[create_map](create_map.md)** - Create static maps (PNG, PDF, JPG) from multiple data sources

### Interactive Web Maps

- **[create_web_map](create_web_map.md)** - Create interactive HTML maps using Folium

## Dependencies

The visualize module requires the following additional packages:

- `folium>=0.15.0` - For interactive web maps
- `pydeck>=0.9.0` - For advanced 3D visualizations

## Data Sources Supported

Both visualization functions support multiple data input types:

- **Shapefiles** (`.shp`) - Vector data files
- **GeoJSON** (`.geojson`) - Vector data in GeoJSON format
- **Raster files** (`.tif`, `.tiff`) - GeoTIFF raster data
- **WKT strings** - Well-Known Text geometry representations
- **Coordinate lists** - Arrays of coordinate pairs
- **GeoPandas DataFrames** - In-memory geospatial data

## Styling Options

Both functions support extensive styling options:

- **Colors** - Custom colors for features
- **Labels** - Layer names and legends
- **Transparency** - Fill and stroke opacity
- **Line weights** - Border thickness
- **Markers** - Point styling options

## Output Formats

- **Static maps**: PNG, PDF, JPG with high DPI support
- **Interactive maps**: HTML files with embedded JavaScript
- **Customizable titles and legends**
- **Grid overlays and coordinate displays**
