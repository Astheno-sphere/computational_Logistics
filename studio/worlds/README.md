# Worlds

A world is the geography a scenario runs in: land, installations, lanes, credits. Each is a YAML
config here and a packaged GeoJSON set published as GitHub release `world-<name>`. Nothing is committed.

| World | Box | Automated sources | Manual sources (see YAML) |
|---|---|---|---|
| `oslofjord` | 10.20-11.05 E, 58.95-59.95 N | OSM coastline | NGU 1 m bathymetry, Kartverket depth, Kystverket AIS, reference routes |
| `north-sea-stavanger` | 1.5-6.2 E, 57.8-60.2 N | OSM coastline, Sodir FactMaps (facilities, fields, pipelines, discoveries, wellbores) | Kystverket AIS (offshore/supply), Kartverket depth |

**Fetch** (open internet): run the `studio-fetch-world` workflow, or `python -m studio.worlds.fetch_world --world <name>`.
**Use** (this workspace, anywhere): `python -m studio.worlds.fetch_world --pull <name>` → `data/worlds/<name>/`.

Why releases: the Claude workspace's network allowlist blocks Kartverket, Kystverket, Sodir, Overpass and
map-tile hosts, but GitHub release downloads work. Actions does the fetching; we pull the result.

Credits travel with the data in `manifest.json` and must appear on every video: "© OpenStreetMap
contributors (ODbL)", "Source: Norwegian Offshore Directorate (NLOD)", Kartverket / Kystverket as used.
