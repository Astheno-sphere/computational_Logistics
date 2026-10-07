# NSS Shelters Local Audit Extract

> This folder is a public reproducibility snapshot of an audit against the
> public National Shelter System dataset. It includes facility names,
> addresses, status, and coordinates from the source snapshot; review source
> terms and sensitivity before redistributing or operationally relying on it.

- `state_only_fallback_rows.csv`: 893 rows with `assigned_geo_level = state`
- `zero_zero_coordinate_rows.csv`: 29 rows with `(latitude, longitude) = (0, 0)`

Generated from `county-map-data/countries/USA/nss_shelters/shelters.parquet` after the local Pattern B build.

## Post-Fix Outcome

- `542` rows were conservatively recovered from state fallback to county by direct county polygon containment.
- `36` clearly questionable rows were excluded from the canonical shelter parquet and written to:
  - `county-map-data/countries/USA/nss_shelters/questionable_rows.csv`
- The current canonical shelter parquet now has:
  - `68,901` rows
  - `67,660` tract-level anchors
  - `926` county-level anchors
  - `315` retained state-level anchors
  - `0` remaining `(0,0)` rows

## First-Pass Findings

- All `29` `(0,0)` rows are `CLOSED` and appear to be upstream bad coordinates rather than runtime geometry failures.
- The `(0,0)` bucket is concentrated in California (`24` rows), with a few in Colorado (`3`), Oregon (`1`), and Florida (`1`).
- Of the `893` state-only fallback rows:
  - `122` are in territories (`AS`, `GU`, `MP`, `PR`, `VI`)
  - `105` are in Alaska or Hawaii
  - `666` are in the continental states
- This looks like a mixed bucket:
  - genuine shoreline / island / territory geometry misses
  - some source-coordinate edge cases
  - some obvious upstream data-quality errors

## Clear Source Anomalies

- `shelter_id 109328`
  - state = `AR`
  - city = `Van Buren`
  - county_parish = `GRAYS HARBOUR`
  - coordinates = `46.972482, -123.837558`
  - appears to be a Washington-area point attached to an Arkansas record
- `shelter_id 364861`
  - state = `CA`
  - city = `SANTA CRUZ`
  - zip = `80538`
  - coordinates = `(0,0)`
  - appears mixed with the Loveland, Colorado facility identity

Use this folder as the staging area for any later cleanup pass before worrying about publishing.
