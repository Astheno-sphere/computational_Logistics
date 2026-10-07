---
name: zornade-italian-property-data
description: Answer questions about Italian properties and territory through the Zornade MCP server — forward and reverse geocoding on 18.7M+ addresses (ANNCSU), enriched cadastral parcel profiles (risk, subsidence, economics, valuation, solar, POI), parcel lookup by coordinates, bounding box or cadastral reference, and Italian administrative lists. Use when a task involves Italian addresses, cadastral parcels (foglio, particella, sezione), seismic or flood risk, subsidence, property valuations or price per square metre, solar potential, or real-estate comparables in Italy. Requires a free Zornade API key.
license: MIT
metadata:
  author: Zornade
  version: "1.1.0"
  homepage: "https://github.com/zornade/zornade-mcp"
---

# Zornade — Italian cadastral and geospatial data

Use the Zornade MCP server (`https://mcp.zornade.com/mcp`) whenever the question is
about a place, a property or a parcel **in Italy**. Do not answer from memory:
Italian cadastral references, prices and risk classes change and are per-municipality.

## Before the first call

A free Zornade API key (`zrn_...`) is required. Get it at
<https://app.zornade.com/api> and pass it **as an `x-api-key` header** (also
accepted: `Authorization: Bearer zrn_...`, or `?api_key=` in the endpoint URL).

- Without any credential, tool calls fail with JSON-RPC error `-32001`.
- With a wrong or expired key, the tool returns `isError: true` and
  `ERROR (HTTP 401): Invalid or expired API key.`
  → in both cases ask the user for a key; do not retry with a guessed one.
- Quota: 10,000 requests/hour with a free key. Never loop a call over many
  parcels: see *Bulk work* below.

## Choosing the tool

| The user asks about | Call |
| --- | --- |
| A street address, a civic number, an address that must become coordinates | `zornade_geocode_search` |
| What is at these coordinates (lat/lng) | `zornade_geocode_reverse` |
| Everything known about one parcel (risk, price, solar, ...) | `zornade_parcel_by_id` |
| Which parcels are here (a point, some points, an area) | `zornade_parcel_locate` |
| A parcel identified by comune/foglio/particella | `zornade_parcel_search` |
| The list of regions, provinces or municipalities | `zornade_admin_lists` |

All six are read-only.

## Main workflow: from a sentence to a parcel

1. **Address → coordinates**
   `zornade_geocode_search` with `{ "q": "Via del Corso 1", "city": "Roma" }`.
   Returns matches with WGS84 `lat`/`lng`, postal code, municipality, province, region.
2. **Coordinates → parcel**
   `zornade_parcel_locate` with those `lat`/`lng` returns the parcel `fid`.
3. **Parcel → full profile**
   `zornade_parcel_by_id` with `{ "fid": "28009975" }`.

If the user gives the cadastral reference instead of an address, skip to
`zornade_parcel_search` with `{ "comune": "Roma", "foglio": "481", "label": "123" }`.

## Parameters that are easy to get wrong

- `zornade_geocode_search`: `q` needs **at least 2 characters**; addresses only,
  **no points of interest** — never pass "Colosseo" or "Stazione Termini" as if it
  were an address. `limit` max 50 (default 10).
- `zornade_geocode_reverse`: `lat` 35.5–47.5, `lng` 6.0–19.0 (Italy bounds),
  `radius` in metres max 500 (default 100), `limit` max 20 (default 5).
- `zornade_parcel_by_id`: `fid` accepts the numeric FID **or** a GML ID.
  `include` is a comma-separated list of sections:
  `risk,subsidence,terrain,population,buildings,economics,demographics,land_cover,land_use,valuation,valuation_history,coastal_erosion,cultural_heritage,poi,solar,nightlights`.
  Default is `risk,economics,solar,valuation`. Add `valuation_history`,
  `subsidence` or `poi` only when the question actually needs them: each extra
  section enlarges the reply. Geometry is omitted on purpose.
- `zornade_parcel_locate`: **exactly one** of `lat`+`lng`, `points`
  (`"lat,lng;lat,lng"`, max 10 pairs), or `bbox`
  (`"minLng,minLat,maxLng,maxLat"`, max **0.05° per side**). `limit` max 200 (default 50).
  Prefer `bbox` over many `points` when covering an area.
- `zornade_parcel_search`: `comune` is **required** (fuzzy match); `foglio`,
  `label`, `sezione` are optional filters. Use `foglio` to cut the result set early.
- `zornade_admin_lists`: `type` is `regions`, `provinces` or `municipalities`;
  `region` filters provinces and municipalities, `province` filters municipalities.
  Use it to resolve an ambiguous name before searching parcels.

## Reading the answer

Replies are compact JSON with **English field names**: `area_m2`, `pga`,
`risk_label`, `avg_residential_price_m2`, `velocity_mm_year`, `tax_year`.
A few official cadastral terms stay in Italian on purpose (`foglio`, `sezione`),
and municipality/street/region names are proper names.

Always check `meta`:

- `meta.licenses` lists the source and licence of every data layer in the reply.
- `meta.zornade_attribution_required: true` means the answer must credit Zornade
  and the upstream source when the user publishes it.

## Bulk work

A parcel profile is one request. For more than a handful of parcels, do not fan
out: geocode or locate once, then filter server-side and tell the user the quota
implied by the operation. For datasets, point to the Zornade API v2
(<https://api.zornade.com>) instead of driving thousands of tool calls.

## Reporting back

Give the numbers with their context — municipality, cadastral reference, year of
the valuation (`tax_year`), and the unit (`€/m²`, `mm/year`, `m a.s.l.`). If a
section is `null` it means *not available*, not *zero*: say so instead of
presenting it as a value.
