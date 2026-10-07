# Preparing Your Own Data

This guide is for researchers converting a dataset for local use in DaedalMap.
It describes the public runtime contract, not DaedalMap's maintained production
pipelines.

Read [DATA_SCHEMAS.md](DATA_SCHEMAS.md) for field shapes and
[PACK_AUTHORING.md](PACK_AUTHORING.md) when you are ready to group sources into
a reusable pack.

## Workflow

1. Classify the source as metrics, events, geometry, or gridded data.
2. Preserve the original download and record its URL, license, version, and
   retrieval date.
3. Normalize geography to canonical `loc_id` values.
4. Normalize time and numeric values.
5. Write Parquet plus `metadata.json` and `reference.json`.
6. Place the source under your local `DATA_ROOT`.
7. Rebuild the catalog, start the app, and test real questions.

Keep raw inputs separate from the runtime data directory. This makes rebuilds
repeatable and prevents archives or credentials from being served accidentally.

## Shape the rows

Use long, tidy rows. A metric table might look like:

| loc_id | timestamp | year | population | unemployment_rate |
|---|---|---:|---:|---:|
| USA-CA | 2024-01-01 | 2024 | 39431263 | 5.3 |
| USA-NV | 2024-01-01 | 2024 | 3267467 | 5.6 |

An event table might look like:

| event_id | timestamp | latitude | longitude | event_type | loc_id |
|---|---|---:|---:|---|---|
| quake-001 | 2024-04-05T14:23:00Z | 40.69 | -74.75 | earthquake | USA-NJ |

Avoid year-per-column layouts such as `population_2022`, `population_2023`.
Avoid duplicating location names and source-native IDs when `loc_id` already
encodes the relationship.

## Normalize geography

`loc_id` is the join between data and geometry. It must match geometry in the
same `DATA_ROOT`.

Examples include `USA`, `USA-CA`, `USA-CA-037`, `CAN-BC`, and `DEU-DE11`.

Do not guess identifiers from names. Build a documented crosswalk from the
source's geographic key to `loc_id`, retain unmatched rows for review, and
report the match rate.

## Normalize time

Use `timestamp` as the canonical temporal field:

- yearly: `YYYY-01-01T00:00:00`
- monthly: first day of the month
- weekly: ISO-week Monday
- daily: start of that day
- events: the source's actual timestamp

Keep useful helpers such as `year`, `date`, `iso_year`, or `iso_week`. Add
`time_granularity` when the timestamp represents a normalized period start
rather than an exact instant.

Missing values must remain null. Do not turn missing observations into zero.

## Write source files

A minimal global source looks like:

```text
DATA_ROOT/
  global/
    my_source/
      data.parquet
      metadata.json
      reference.json
```

A country-specific source uses
`DATA_ROOT/countries/{ISO3}/my_source/`.

`metadata.json` describes how the runtime discovers and queries the source.
`reference.json` records provenance and human-readable metric definitions.
Keep stable research provenance in both the conversion project and the shipped
source folder.

## Build the local catalog

From the public repository:

```powershell
python converters/catalog_builder.py "C:\path\to\your\data"
```

The builder scans standard source folders and writes `catalog.json` and
`index.json`. Point the app at the same directory:

```text
INSTALL_MODE=local
RUNTIME_MODE=local
DATA_ROOT=C:/path/to/your/data
```

Restart the app after structural catalog changes.

## Validation checklist

- Every row has a valid geographic or event identity.
- `loc_id` values join to the intended geometry.
- Temporal rows have canonical `timestamp` values.
- Metric columns are numeric, with null used for missing data.
- Logical keys such as `(loc_id, timestamp)` are unique.
- Units, transformations, and aggregation behavior are documented.
- URL, license, version, and retrieval date are recorded.
- Metadata year ranges match the Parquet contents.
- Expected and edge-case questions work in the local runtime.
- A second person can reproduce the conversion from recorded inputs.

## Public helpers

- [`converters/catalog_builder.py`](../converters/catalog_builder.py) builds
  catalogs and indexes.
- [`scripts/add_temporal_columns.py`](../scripts/add_temporal_columns.py)
  normalizes temporal columns.
- [`scripts/simplify_geometry.py`](../scripts/simplify_geometry.py) simplifies
  geometry.
- [`converters/setup_gadm.py`](../converters/setup_gadm.py) is a public geometry
  compatibility example, not the production geometry-spine build path.

You may use pandas, Polars, DuckDB, GeoPandas, R, or another reproducible tool
for conversion. Compatibility is defined by the resulting files, not by a
private converter framework.
