"""PyProj-related MCP tool functions and resource listings."""
import logging
from typing import Any, Dict, List, Optional
from .mcp import gis_mcp

# Configure logging
logger = logging.getLogger(__name__)

@gis_mcp.resource("gis://crs/transformations")
def get_crs_transformations() -> Dict[str, List[str]]:
    """List available CRS transformation operations."""
    return {
        "operations": [
            "transform_coordinates",
            "project_geometry"
        ]
    }

@gis_mcp.resource("gis://crs/info")
def get_crs_info_operations() -> Dict[str, List[str]]:
    """List available CRS information operations."""
    return {
        "operations": [
            "get_crs_info",
            "get_available_crs",
            "get_utm_zone",
            "get_utm_crs",
            "get_geocentric_crs"
        ]
    }

@gis_mcp.resource("gis://crs/geodetic")
def get_geodetic_operations() -> Dict[str, List[str]]:
    """List available geodetic operations."""
    return {
        "operations": [
            "get_geod_info",
            "calculate_geodetic_distance",
            "calculate_geodetic_point",
            "calculate_geodetic_area"
        ]
    }

@gis_mcp.tool()
def transform_coordinates(coordinates: List[float], source_crs: str, 
                        target_crs: str) -> Dict[str, Any]:
    """Transform coordinates between CRS."""
    try:
        from pyproj import Transformer
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        x, y = coordinates
        x_transformed, y_transformed = transformer.transform(x, y)
        return {
            "status": "success",
            "coordinates": [x_transformed, y_transformed],
            "source_crs": source_crs,
            "target_crs": target_crs,
            "message": "Coordinates transformed successfully"
        }
    except Exception as e:
        logger.error(f"Error transforming coordinates: {str(e)}")
        raise ValueError(f"Failed to transform coordinates: {str(e)}")

@gis_mcp.tool()
def project_geometry(geometry: str, source_crs: str, 
                    target_crs: str) -> Dict[str, Any]:
    """Project a geometry between CRS."""
    try:
        from shapely import wkt
        from shapely.ops import transform
        from pyproj import Transformer
        geom = wkt.loads(geometry)
        transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
        projected = transform(transformer.transform, geom)
        return {
            "status": "success",
            "geometry": projected.wkt,
            "source_crs": source_crs,
            "target_crs": target_crs,
            "message": "Geometry projected successfully"
        }
    except Exception as e:
        logger.error(f"Error projecting geometry: {str(e)}")
        raise ValueError(f"Failed to project geometry: {str(e)}")

@gis_mcp.tool()
def get_crs_info(crs: str) -> Dict[str, Any]:
    """Get information about a CRS."""
    try:
        import pyproj
        crs_obj = pyproj.CRS(crs)
        return {
            "status": "success",
            "name": crs_obj.name,
            "type": crs_obj.type_name,
            "axis_info": [axis.direction for axis in crs_obj.axis_info],
            "is_geographic": crs_obj.is_geographic,
            "is_projected": crs_obj.is_projected,
            "datum": str(crs_obj.datum),
            "ellipsoid": str(crs_obj.ellipsoid),
            "prime_meridian": str(crs_obj.prime_meridian),
            "area_of_use": str(crs_obj.area_of_use) if crs_obj.area_of_use else None,
            "message": "CRS information retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting CRS info: {str(e)}")
        raise ValueError(f"Failed to get CRS info: {str(e)}")

@gis_mcp.tool()
def get_available_crs() -> Dict[str, Any]:
    """Get list of available CRS."""
    try:
        import pyproj
        from pyproj.database import get_codes
        from pyproj.enums import PJType
        
        crs_list = []
        # Get a sample of common EPSG codes (limit to avoid huge lists)
        epsg_codes = list(get_codes("EPSG", PJType.CRS))[:100]  # Limit to first 100 for performance
        
        for code in epsg_codes:
            try:
                # Directly create CRS and get info without calling the tool function
                crs_obj = pyproj.CRS.from_epsg(int(code))
                crs_list.append({
                    "auth_name": "EPSG",
                    "code": str(code),
                    "name": crs_obj.name,
                    "type": crs_obj.type_name
                })
            except Exception as ex:
                # Skip invalid CRS codes
                logger.debug(f"Skipping EPSG:{code}: {str(ex)}")
                continue
        
        if not crs_list:
            # Fallback: return some well-known CRS
            well_known_crs = [
                {"auth_name": "EPSG", "code": "4326", "name": "WGS 84", "type": "Geographic 2D CRS"},
                {"auth_name": "EPSG", "code": "3857", "name": "WGS 84 / Pseudo-Mercator", "type": "Projected CRS"},
                {"auth_name": "EPSG", "code": "4269", "name": "NAD83", "type": "Geographic 2D CRS"},
            ]
            crs_list = well_known_crs
        
        return {
            "status": "success",
            "crs_list": crs_list,
            "message": "Available CRS list retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting available CRS: {str(e)}")
        raise ValueError(f"Failed to get available CRS: {str(e)}")

@gis_mcp.tool()
def get_geod_info(ellps: str = "WGS84", a: Optional[float] = None,
                b: Optional[float] = None, f: Optional[float] = None) -> Dict[str, Any]:
    """Get information about a geodetic calculation."""
    try:
        import pyproj
        geod = pyproj.Geod(ellps=ellps, a=a, b=b, f=f)
        # Calculate e (eccentricity) from es (first eccentricity squared)
        e = (geod.es ** 0.5) if geod.es >= 0 else None
        
        return {
            "status": "success",
            "ellps": ellps,  # Return the parameter, not attribute
            "ellipsoid": ellps,  # Also include as ellipsoid for compatibility
            "a": geod.a,
            "b": geod.b,
            "f": geod.f,
            "es": geod.es,
            "e": e,
            "message": "Geodetic information retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting geodetic info: {str(e)}")
        raise ValueError(f"Failed to get geodetic info: {str(e)}")

@gis_mcp.tool()
def calculate_geodetic_distance(point1: List[float], point2: List[float], 
                            ellps: str = "WGS84") -> Dict[str, Any]:
    """Calculate geodetic distance between points."""
    try:
        import pyproj
        geod = pyproj.Geod(ellps=ellps)
        lon1, lat1 = point1
        lon2, lat2 = point2
        forward_azimuth, back_azimuth, distance = geod.inv(lon1, lat1, lon2, lat2)
        return {
            "status": "success",
            "distance": distance,
            "forward_azimuth": forward_azimuth,
            "back_azimuth": back_azimuth,
            "ellps": ellps,
            "unit": "meters",
            "message": "Geodetic distance calculated successfully"
        }
    except Exception as e:
        logger.error(f"Error calculating geodetic distance: {str(e)}")
        raise ValueError(f"Failed to calculate geodetic distance: {str(e)}")

@gis_mcp.tool()
def calculate_geodetic_point(start_point: List[float], azimuth: float, 
                        distance: float, ellps: str = "WGS84") -> Dict[str, Any]:
    """Calculate point at given distance and azimuth."""
    try:
        import pyproj
        geod = pyproj.Geod(ellps=ellps)
        lon, lat = start_point
        lon2, lat2, back_azimuth = geod.fwd(lon, lat, azimuth, distance)
        return {
            "status": "success",
            "point": [lon2, lat2],
            "back_azimuth": back_azimuth,
            "ellps": ellps,
            "message": "Geodetic point calculated successfully"
        }
    except Exception as e:
        logger.error(f"Error calculating geodetic point: {str(e)}")
        raise ValueError(f"Failed to calculate geodetic point: {str(e)}")

@gis_mcp.tool()
def calculate_geodetic_area(geometry: str, ellps: str = "WGS84") -> Dict[str, Any]:
    """Calculate area of a polygon using geodetic calculations."""
    try:
        import pyproj
        from shapely import wkt
        geod = pyproj.Geod(ellps=ellps)
        polygon = wkt.loads(geometry)
        area = abs(geod.geometry_area_perimeter(polygon)[0])
        return {
            "status": "success",
            "area": float(area),
            "ellps": ellps,
            "unit": "square_meters",
            "message": "Geodetic area calculated successfully"
        }
    except Exception as e:
        logger.error(f"Error calculating geodetic area: {str(e)}")
        raise ValueError(f"Failed to calculate geodetic area: {str(e)}")

@gis_mcp.tool()
def get_utm_zone(coordinates: List[float]) -> Dict[str, Any]:
    """Get UTM zone for given coordinates."""
    try:
        import pyproj
        from pyproj.database import query_utm_crs_info
        lon, lat = coordinates
        crs_info_list = query_utm_crs_info(
            datum_name="WGS 84",  # Use "WGS 84" with space as per standard
            area_of_interest=pyproj.aoi.AreaOfInterest(
                west_lon_degree=lon,
                south_lat_degree=lat,
                east_lon_degree=lon,
                north_lat_degree=lat
            )
        )
        if not crs_info_list:
            raise ValueError("No UTM CRS found for the given coordinates")
        
        # Create CRS from the first matching CRSInfo
        crs_obj = pyproj.CRS.from_authority(crs_info_list[0].auth_name, crs_info_list[0].code)
        # Extract zone number from CRS name (e.g., "WGS 84 / UTM zone 10N" -> 10)
        import re
        zone_match = re.search(r'zone\s+(\d+)', crs_info_list[0].name, re.IGNORECASE)
        if zone_match:
            zone = int(zone_match.group(1))
        else:
            # Fallback: try to extract from authority code
            # EPSG codes for UTM: 32601-32660 (north), 32701-32760 (south)
            code = int(crs_info_list[0].code)
            if 32601 <= code <= 32660:  # Northern hemisphere
                zone = code - 32600
            elif 32701 <= code <= 32760:  # Southern hemisphere
                zone = code - 32700
            else:
                raise ValueError("Could not extract valid UTM zone number from CRS")
        
        if zone < 1 or zone > 60:
            raise ValueError(f"Invalid UTM zone number: {zone}")
        
        return {
            "status": "success",
            "zone": zone,
            "message": "UTM zone retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting UTM zone: {str(e)}")
        raise ValueError(f"Failed to get UTM zone: {str(e)}")

@gis_mcp.tool()
def get_utm_crs(coordinates: List[float]) -> Dict[str, Any]:
    """Get UTM CRS for given coordinates."""
    try:
        import pyproj
        from pyproj.database import query_utm_crs_info
        lon, lat = coordinates
        crs_info_list = query_utm_crs_info(
            datum_name="WGS 84",  # Use "WGS 84" with space as per standard
            area_of_interest=pyproj.aoi.AreaOfInterest(
                west_lon_degree=lon,
                south_lat_degree=lat,
                east_lon_degree=lon,
                north_lat_degree=lat
            )
        )
        if not crs_info_list:
            raise ValueError("No UTM CRS found for the given coordinates")
        
        # Create CRS from CRSInfo and get its string representation
        crs_obj = pyproj.CRS.from_authority(crs_info_list[0].auth_name, crs_info_list[0].code)
        crs_str = crs_obj.to_string()
        
        return {
            "status": "success",
            "crs": crs_str,
            "message": "UTM CRS retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting UTM CRS: {str(e)}")
        raise ValueError(f"Failed to get UTM CRS: {str(e)}")

@gis_mcp.tool()
def get_geocentric_crs(coordinates: List[float]) -> Dict[str, Any]:
    """Get geocentric CRS for given coordinates."""
    try:
        import pyproj
        from pyproj.database import query_crs_info
        lon, lat = coordinates
        
        # Query for geocentric CRS (type PJType.GEOCENTRIC_CRS)
        # Since query_geocentric_crs_info doesn't exist, use a standard geocentric CRS
        # WGS 84 geocentric is a common choice: EPSG:4978
        crs_obj = pyproj.CRS.from_epsg(4978)  # WGS 84 geocentric
        
        return {
            "status": "success",
            "crs": crs_obj.to_string(),
            "message": "Geocentric CRS retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting geocentric CRS: {str(e)}")
        raise ValueError(f"Failed to get geocentric CRS: {str(e)}")

