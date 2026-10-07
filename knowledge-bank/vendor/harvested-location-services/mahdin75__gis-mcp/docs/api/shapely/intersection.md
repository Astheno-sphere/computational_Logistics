### intersection

Find the geometric intersection of two geometries.

- Tool: `intersection`
- Geometry format: WKT

Parameters

- geometry1 (string): First WKT geometry
- geometry2 (string): Second WKT geometry

Returns

- geometry (string, WKT)
- status (string), message (string)

Example

```json
{
  "tool": "intersection",
  "params": {
    "geometry1": "POLYGON((0 0,10 0,10 10,0 10,0 0))",
    "geometry2": "POLYGON((5 5,15 5,15 15,5 15,5 5))"
  }
}
```
