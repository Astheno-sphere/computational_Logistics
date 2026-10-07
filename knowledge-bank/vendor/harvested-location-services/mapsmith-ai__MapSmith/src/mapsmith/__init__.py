"""MapSmith — professional-grade GIS geoprocessing over MCP, with verifiable provenance."""

__version__ = "0.8.0"

# Must run before anything imports pyogrio, rasterio or duckdb's spatial
# extension: GDAL reads GDAL_SKIP/OGR_SKIP once, when it registers its drivers.
# Without it, a plain-local `.vrt` naming a remote source reaches the network in
# spite of the path guard, the SQL scan and the workspace jail — none of which
# can see inside a file GDAL resolves on its own. See gdal_policy.
from . import gdal_policy as _gdal_policy

_gdal_policy.apply()
