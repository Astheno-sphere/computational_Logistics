### get_centroid

Return the centroid point of a geometry.

- Tool: `get_centroid`
- Geometry format: WKT

Parameters

- geometry (string)

Returns

- geometry (string, WKT point)
- status (string), message (string)

Example

```json
{
  "tool": "get_centroid",
  "params": {
    "geometry": "POLYGON((0 0,10 0,10 10,0 10,0 0))"
  }
}
```
