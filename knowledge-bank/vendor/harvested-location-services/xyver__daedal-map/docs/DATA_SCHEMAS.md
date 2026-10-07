# Data Schemas

This is the public data contract for sources loaded by DaedalMap. Use it with
[DATA_PREPARATION.md](DATA_PREPARATION.md) and
[PACK_AUTHORING.md](PACK_AUTHORING.md).

## Shared identity

`loc_id` is the canonical join between data and geometry:

```text
{country}[-{admin1}[-{admin2}[-{admin3}...]]]
```

Examples:

| Level | Example |
|---|---|
| Country | `USA` |
| State or province | `USA-CA` |
| County or district | `USA-CA-037` |
| Canadian province | `CAN-BC` |
| European NUTS region | `DEU-DE11` |

Country prefixes use uppercase ISO 3166-1 alpha-3 codes. Deeper identifiers
must match the geometry and crosswalk files installed in the same `DATA_ROOT`.
Do not infer IDs from names at query time.

## Temporal contract

Temporal sources use `timestamp` as the canonical filter and ordering field.
Normalize period-based data to the beginning of its represented period:

| Granularity | Timestamp |
|---|---|
| Year | `YYYY-01-01T00:00:00` |
| Month | First day at `00:00:00` |
| ISO week | Monday at `00:00:00` |
| Day | Same day at `00:00:00` |
| Event | Exact source timestamp |

Keep helpers such as `year`, `date`, `iso_year`, and `iso_week` when useful.
Add `time_granularity` when a timestamp is a normalized period boundary rather
than an exact observation instant.

`temporal_coverage` describes the source-wide discovery range.
`metrics.{metric_id}.years` is the execution range for a selected metric when
present. The runtime should clamp requested ranges to the metric-level truth.

## Metric sources

Metric rows represent observations for a location and period.

```text
loc_id | timestamp | year | population | unemployment_rate
```

Required:

- `loc_id`
- `timestamp` for temporal data
- at least one numeric metric

Recommended:

- useful grouping helpers such as `year`;
- a `source` column when files combine records from multiple origins;
- one unique row per logical location, period, and distinguishing dimension.

Missing observations must be null, not zero or a sentinel string. Avoid
year-per-column layouts and redundant location-name or raw-code columns.

## Event sources

Event rows represent discrete incidents:

```text
event_id | timestamp | latitude | longitude | event_type | loc_id
```

Required:

- stable `event_id`;
- exact or best-known `timestamp`;
- coordinates or another documented geometry relationship;
- `event_type`.

`loc_id` is strongly recommended when an event can be assigned to installed
geometry. Severity, status, name, and source-native identifiers may be retained
when they have analytical value.

Related event files may include:

- `event_areas.parquet` for extents or affected polygons;
- `links.parquet` for explicit relationships between records;
- progression data for time-sequenced tracks or perimeters;
- aggregate files for declared summaries.

Relationships should resolve through stable event and location identities.

## Geometry sources

Typical geometry fields:

| Field | Meaning |
|---|---|
| `loc_id` | Canonical location identity |
| `name` | Display name |
| `admin_level` | Hierarchy level |
| `parent_id` | Parent `loc_id` |
| `geometry` | Polygon or multipolygon |
| `centroid_lat` | Display centroid latitude |
| `centroid_lon` | Display centroid longitude |

Geometry is stored separately from most observations and reused through
`loc_id`. Data sources should not copy polygons into every metric row.

## Gridded sources

Gridded sources use regular or source-defined cells rather than administrative
areas. They must document:

- coordinate reference system;
- cell resolution and alignment;
- time field and granularity;
- nodata convention;
- metric units;
- any transformation used to create display tiles or aggregates.

If gridded values are aggregated into administrative geography, ship the
aggregation method and resulting metric rules with that derived source.

## Source metadata

Each source needs `metadata.json`. A practical minimum is:

```json
{
  "source_id": "regional_health",
  "source_name": "Regional Health Indicators",
  "pack_id": "my_health_project",
  "category": "health",
  "data_type": "metrics",
  "geographic_level": "admin_2",
  "geographic_coverage": {
    "type": "country",
    "country_codes": ["USA"]
  },
  "temporal_coverage": {
    "start": 2010,
    "end": 2024,
    "granularity": "yearly",
    "field": "timestamp"
  },
  "metrics": {
    "life_expectancy": {
      "name": "Life expectancy",
      "unit": "years",
      "years": [2010, 2024],
      "aggregation": "weighted_avg",
      "weight_metric": "population"
    }
  },
  "llm_summary": "Annual regional health indicators for the study area."
}
```

Core fields:

| Field | Purpose |
|---|---|
| `source_id` | Stable machine identifier |
| `source_name` | Human-readable source name |
| `pack_id` | Stable grouping for related sources |
| `category` | Broad discovery topic |
| `data_type` | `metrics`, `events`, `geometry`, `gridded`, or a supported combination |
| `geographic_level` | Native geographic grain |
| `geographic_coverage` | Places represented by the source |
| `temporal_coverage` | Source-wide time range |
| `metrics` | Metric names, units, coverage, and aggregation |
| `llm_summary` | Short discovery description |

Use lowercase stable IDs. Metadata must describe observed files, not an intended
future state.

## Provenance reference

Each source should also ship `reference.json`:

```json
{
  "source": {
    "source_id": "regional_health",
    "source_name": "Regional Health Indicators",
    "source_url": "https://example.org/dataset",
    "license": "CC BY 4.0",
    "description": "Annual indicators published by Example Institute."
  },
  "metrics": {
    "life_expectancy": "Life expectancy at birth"
  }
}
```

Record retrieval dates, source versions, transformations, crosswalks,
exclusions, and limitations in a README or other durable file beside the
source.

## Aggregation

Every metric that may be combined across geography or time needs an explicit
rule:

- `sum`
- `weighted_avg` with `weight_metric`
- `mean`
- `min`
- `max`
- `period_end`
- `skip`

The rule must reflect the meaning of the measurement. A rate is not usually
additive, and an index may not be safely averaged.

## Folder layout

The public catalog builder scans these source locations:

```text
DATA_ROOT/
  catalog.json
  index.json
  global/
    {source_id}/
      data.parquet
      metadata.json
      reference.json
  countries/
    {ISO3}/
      {source_id}/
        data.parquet
        metadata.json
        reference.json
```

Recognized specialized layouts include `global/disasters/{source_id}/` and
`global/un_sdg/{goal_id}/`. A source may use descriptive Parquet filenames such
as `events.parquet` or `{ISO3}.parquet`; metadata and catalog paths determine
discovery.

Build catalogs with:

```powershell
python converters/catalog_builder.py "C:\path\to\your\data"
```

## Contract checklist

- IDs are stable and geometry-compatible.
- Time uses canonical `timestamp`.
- Metrics are numeric and units are explicit.
- Null means missing; zero means measured zero.
- Logical row keys are unique.
- Aggregation rules are defensible.
- Metadata matches actual coverage.
- Provenance and licensing travel with the source.
- Catalog paths resolve inside `DATA_ROOT`.
