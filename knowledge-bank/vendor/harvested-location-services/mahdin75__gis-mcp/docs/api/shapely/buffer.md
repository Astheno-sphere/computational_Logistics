### buffer

Create a buffer around a geometry.

- Tool: `buffer`
- Geometry format: WKT

Parameters

- geometry (string): Input WKT geometry
- distance (number): Buffer distance
- resolution (integer, default 16): Quadrant segments
- join_style (integer, default 1): 1=round, 2=mitre, 3=bevel
- mitre_limit (number, default 5.0)
- single_sided (boolean, default false)

Returns

- geometry (string, WKT)
- status (string), message (string)

Example

```json
{
  "tool": "buffer",
  "params": {
    "geometry": "POINT(0 0)",
    "distance": 10,
    "resolution": 16,
    "join_style": 1,
    "mitre_limit": 5.0,
    "single_sided": false
  }
}
```
