### get_crs_info

Return detailed information about a CRS string.

- Tool: `get_crs_info`

Parameters

- crs (string): e.g., "EPSG:4326" or WKT

Returns

- name, type, axis_info, is_geographic, is_projected,
  datum, ellipsoid, prime_meridian, area_of_use,
  status, message

Example

```json
{
  "tool": "get_crs_info",
  "params": {
    "crs": "EPSG:4326"
  }
}
```
