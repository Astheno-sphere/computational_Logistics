# OSM extracts

Not committed: OpenStreetMap data is fetched at use, not vendored (ODbL; see `docs/CHECKLIST.md`).
Scripts look for extracts here.

| File | Used by | Area |
|---|---|---|
| `molde.osm.bz2` | `skills/visual-narrative/scripts/pinch_points.py` (plate 01) | 62.72–62.78 N, 7.05–7.25 E |

Fetch Molde (Overpass; any machine with internet):

```bash
curl -s https://overpass-api.de/api/interpreter \
  --data-urlencode 'data=[out:xml][timeout:180];(nwr(62.72,7.05,62.78,7.25););(._;>;);out meta;' \
  | bzip2 -9 > data/osm/molde.osm.bz2
```

The query keeps the `<bounds>` header the plate uses to cut the coastline. Data © OpenStreetMap
contributors, ODbL.
