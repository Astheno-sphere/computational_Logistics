# Tool reference

All eleven are registered unless you say otherwise. `OSM_ALLOW_TOOLS` and
`OSM_DENY_TOOLS` narrow the list to the ones you want, and `essential` selects a
curated six — see
[choosing the tools that load](/guide/configuration#choosing-the-tools-that-load).

All 11 tools, every one read-only (`readOnlyHint`). Every one declares an
`outputSchema` and answers with `structuredContent` beside the text block, and
every one carries `untrusted: true` and `source: "openstreetmap"` as fields of
that object — there is no exception list, because OpenStreetMap is editable by
anyone on earth and no tool here answers with anything else.

What this server computes is described exactly; what comes out of OSM is
described but left open, because the tag namespace has no schema and the SDK
validates a result against its schema before it goes out.

Two conventions run through the whole set:

- **Every place input is a string** that accepts either a name/address
  (geocoded automatically via Nominatim) or literal coordinates as
  `"lat,lon"` — `"Eiffel Tower"`, `"5 Avenue Anatole France, Paris"` and
  `"48.8584,2.2945"` are interchangeable.
- **`language`** is accepted by every tool that resolves places: an IETF code
  like `"en"` or `"de"` for the returned place labels, default `"en"`.

Travel profiles are `"foot"`, `"car"` or `"bike"` throughout.

## Geocoding

### `geocode`

**essential**

Converts a place name or address into coordinates. Returns matching places with
lat/lon, a display label and the OSM id. Provider `nominatim` (default) is best
for addresses; `photon` is typo-tolerant and better for fuzzy place names.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `query` | string (1–300) | yes | Place name or address |
| `provider` | `"nominatim"` \| `"photon"` | no | Geocoder to use, default `nominatim` |
| `limit` | integer 1–10 | no | Maximum number of results, default 3 |
| `language` | string | no | Language for place names, default `"en"` |
| `countrycodes` | string | no | Restrict to countries: comma-separated ISO 3166-1 alpha-2 codes, e.g. `"de,lu"` (Nominatim only) |

```json
{ "query": "Luvre, Paris", "provider": "photon" }
```

…finds the Louvre despite the typo.

### `reverse_geocode`

**essential**

Converts coordinates into the nearest address or place name (Nominatim).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `latitude` | number −90…90 | yes | |
| `longitude` | number −180…180 | yes | |
| `language` | string | no | Language for the result, default `"en"` |

```json
{ "latitude": 49.6116, "longitude": 6.1319 }
```

## Routing

### `route`

**essential**

Calculates the real-world travel distance and time between two or more places,
visited in the given order. Returns a human-readable distance and duration plus
raw meters/seconds, per-leg summaries when there are more than two waypoints,
and optionally a turn-by-turn summary (capped at the first 100 steps). Uses
OSRM, or OpenRouteService when `ORS_API_KEY` is set.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `waypoints` | string[] (2–25) | yes | Start, optional stops in between, destination |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | yes | Travel mode |
| `include_steps` | boolean | no | Include a turn-by-turn step summary, default `false` |
| `language` | string | no | Language for resolved place labels, default `"en"` |

```json
{ "waypoints": ["Eiffel Tower", "Louvre, Paris"], "profile": "foot" }
```

### `route_matrix`

Computes travel times and distances from every origin to every destination in
one call — ideal for comparing options, e.g. 5 hotels against 3 sights. Cells
are `null` where no route exists. Durations come back in minutes, distances in
kilometers. Origins + destinations must stay ≤ 25 (public OSRM usage policy).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `origins` | string[] (1–12) | yes | |
| `destinations` | string[] (1–12) | yes | |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | yes | Travel mode |
| `language` | string | no | Default `"en"` |

```json
{
  "origins": ["Hotel Le Six, Paris", "Hotel des Arts Montmartre"],
  "destinations": ["Louvre", "Musée d'Orsay", "Sainte-Chapelle"],
  "profile": "foot"
}
```

### `optimize_route`

Finds the best order to visit a set of stops (traveling-salesman optimization,
OSRM `/trip`) and returns the optimized itinerary with total distance and time
plus per-leg summaries. With `roundtrip` (the default) the tour returns to the
first stop; without it the first stop is the start and the last stop the end.
Always uses OSRM — ORS has no equivalent service.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `stops` | string[] (3–12) | yes | |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | yes | Travel mode |
| `roundtrip` | boolean | no | Return to the first stop at the end, default `true` |
| `language` | string | no | Default `"en"` |

```json
{
  "stops": ["Colosseum", "Trevi Fountain", "Pantheon, Rome", "Spanish Steps"],
  "profile": "foot",
  "roundtrip": false
}
```

### `isochrone`

Shows how far you can get from a place within a time or distance budget —
"what is reachable in 15 minutes on foot?". Returns a compact summary of the
reachable area: bounding box and reach per compass direction. Give **exactly
one** of `minutes` or `kilometers`. Uses Valhalla, or OpenRouteService when
`ORS_API_KEY` is set.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `center` | string | yes | Place name, address or `"lat,lon"` |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | yes | Travel mode |
| `minutes` | number 1–120 | one of | Time budget |
| `kilometers` | number 0.1–100 | one of | Distance budget |
| `language` | string | no | Default `"en"` |

```json
{ "center": "Gare du Nord, Paris", "profile": "foot", "minutes": 15 }
```

## Points of interest

### `find_nearby_pois`

**essential**

Finds points of interest near a location, sorted by distance (Overpass).
`category` is either one of ~45 built-in shortcuts — `restaurant`, `cafe`,
`bar`, `hotel`, `hostel`, `museum`, `attraction`, `viewpoint`, `castle`,
`supermarket`, `bakery`, `pharmacy`, `hospital`, `atm`, `fuel`,
`charging_station`, `parking`, `toilets`, `drinking_water`, `bus_stop`,
`train_station`, `bicycle_rental`, `playground`, `park`, `beach` and more — or
any raw OSM tag as `key` or `key=value`, e.g. `"diet:vegan=yes"`. Each result
carries name, distance, coordinates, the OSM id and the core tags (cuisine,
opening hours, website, phone, wheelchair, …).

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `near` | string | yes | Place name, address or `"lat,lon"` |
| `category` | string (1–100) | yes | Category shortcut or OSM tag filter |
| `radius_m` | integer 50–10 000 | no | Search radius in meters, default 1 000 |
| `limit` | integer 1–25 | no | Maximum number of results, default 10 |
| `language` | string | no | Default `"en"` |

```json
{ "near": "Alexanderplatz, Berlin", "category": "diet:vegan=yes", "radius_m": 800 }
```

### `poi_details`

**essential**

Fetches the full OpenStreetMap record of one element — all tags (opening
hours, website, phone, …), coordinates and a map link. Takes an OSM id as
returned by `find_nearby_pois` or `geocode`. Responses are budgeted: at most 60
tags, values truncated at 500 characters.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `osm_id` | string | yes | `"node/<id>"`, `"way/<id>"` or `"relation/<id>"`, e.g. `"node/240109189"` |

```json
{ "osm_id": "node/240109189" }
```

### `suggest_meeting_point`

Suggests a fair place to meet for people starting from different locations:
finds venues around the geographic midpoint and picks the one with the most
balanced travel times — smallest worst-case time first, total time as the
tie-breaker. Returns the suggested venue with per-person travel times and up to
three alternatives.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `locations` | string[] (2–8) | yes | Starting points of all participants |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | no | How everyone travels, default `foot` |
| `venue_category` | string (1–100) | no | What kind of venue to meet at, default `"cafe"` |
| `search_radius_m` | integer 100–10 000 | no | Venue search radius around the midpoint, default 1 500 |
| `language` | string | no | Default `"en"` |

```json
{ "locations": ["Gare du Nord, Paris", "Bastille, Paris", "Montparnasse"], "venue_category": "bar" }
```

## Offline helpers

### `straight_line_distance`

Great-circle ("as the crow flies") distance between two places. Instant and
independent of any road network — use `route` for real travel distances. Needs
the network only to geocode place *names*; literal coordinates compute fully
offline.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `from` | string | yes | Place name, address or `"lat,lon"` |
| `to` | string | yes | Place name, address or `"lat,lon"` |
| `language` | string | no | Default `"en"` |

```json
{ "from": "Berlin", "to": "Tokyo" }
```

### `map_link`

**essential**

Generates openstreetmap.org links to open in a browser: a marker link for a
single place, or a directions link when `from` and `to` are given (the
directions engine matches the chosen profile). Provide either `place`, or both
`from` and `to`.

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `place` | string | one form | Place for a marker link |
| `from` | string | other form | Start for a directions link |
| `to` | string | other form | Destination for a directions link |
| `profile` | `"foot"` \| `"car"` \| `"bike"` | no | Travel mode for the directions link, default `foot` |
| `language` | string | no | Default `"en"` |

```json
{ "from": "Eiffel Tower", "to": "Louvre", "profile": "foot" }
```
