# OSM extracts

Not committed: OpenStreetMap data is fetched at use, not vendored (ODbL; see `docs/CHECKLIST.md`).
Scripts look for extracts here.

| File | Used by | Area |
|---|---|---|
| `molde.osm.bz2` | `skills/visual-narrative/scripts/*` (plates 01–04) | 62.72–62.78 N, 7.05–7.25 E |
| `kristiansund.osm.bz2` | case study (proposal demo) | 63.079–63.134 N, 7.647–7.801 E |

Fetch Molde (Overpass; any machine with internet):

```bash
curl -s https://overpass-api.de/api/interpreter \
  --data-urlencode 'data=[out:xml][timeout:180];(nwr(62.72,7.05,62.78,7.25););(._;>;);out meta;' \
  | bzip2 -9 > data/osm/molde.osm.bz2
```

The query keeps the `<bounds>` header the plate uses to cut the coastline.

Kristiansund came as a GDAL/ogr2ogr export (GeoJSONL from GeoLibre, 2026-10-08). Convert any such export
with `python skills/osm-network/scripts/gdal_osm_to_xml.py export.geojsonl data/osm/<place>.osm.bz2`; it
rebuilds shared junctions from identical vertices, unpacks `other_tags`, and takes `<bounds>` from the
export box (the bulk of point features), dropping far-reaching routes such as the coastal ferry. Data © OpenStreetMap
contributors, ODbL.
