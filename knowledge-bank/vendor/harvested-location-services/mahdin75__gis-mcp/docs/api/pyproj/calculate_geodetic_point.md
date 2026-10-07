### calculate_geodetic_point

From a start lon/lat, azimuth, and distance, compute the destination point.

- Tool: `calculate_geodetic_point`

Parameters

- start_point (array [lon, lat])
- azimuth (number, degrees)
- distance (number, meters)
- ellps (string, default "WGS84")

Returns

- point [lon, lat], back_azimuth, ellps; status, message
