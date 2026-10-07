# Authoring Data Packs

A DaedalMap source is one queryable dataset. A pack is a named collection of
related sources. Researchers can use packs for a project, course, lab, or
replication bundle without changing the runtime.

This public contract does not require DaedalMap's hosted release system or
maintained private pipelines.

## Source, pack, and corpus

- **Source:** one canonical dataset with Parquet data, metadata, and provenance.
- **Pack:** sources grouped by the same stable `pack_id`.
- **Corpus:** a user-selected working set of installed sources or packs used in
  Research mode.

The source is the unit of schema and provenance. The pack is the unit of
organization. A corpus is a local research choice, not a copy of the data.

## Start with a source

Prepare each source using [DATA_PREPARATION.md](DATA_PREPARATION.md) and
[DATA_SCHEMAS.md](DATA_SCHEMAS.md).

Source metadata should communicate at least:

```json
{
  "source_id": "regional_health",
  "source_name": "Regional Health Indicators",
  "pack_id": "my_health_project",
  "category": "health",
  "data_type": "metrics",
  "geographic_level": "admin_2",
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
      "aggregation": "weighted_avg",
      "weight_metric": "population"
    }
  },
  "llm_summary": "Annual regional health indicators for the study area."
}
```

Use stable, lowercase identifiers. Changing `source_id` or `pack_id` later can
break saved references and corpora.

## Keep provenance with the source

`reference.json` should identify the original source independently of the pack:

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

Record transformations, exclusions, crosswalks, and known limitations in a
README beside the source. A pack should remain interpretable without access to
your notebook history.

## Declare aggregation rules

Aggregation behavior is part of the research claim:

- `sum` for additive counts
- `weighted_avg` for rates with an explicit weight metric
- `mean` only when an unweighted mean is substantively correct
- `min` or `max` for extrema
- `period_end` for stocks measured at a point in time
- `skip` when aggregation would be misleading

Do not rely on generated guesses for a shared research pack.

## Group and test sources

Give related sources the same `pack_id`, then rebuild the local catalog:

```powershell
python converters/catalog_builder.py "C:\path\to\your\data"
```

Good boundaries include a research project, teaching bundle, reproducibility
package, or coherent topic bundle. Avoid catch-all packs that hide unrelated
licenses, units, or methods.

Validate that:

1. the pack and all intended sources appear in discovery;
2. metric names and units are understandable;
3. map joins resolve at every claimed geographic level;
4. Explore discovers the sources from ordinary language;
5. a corpus containing the pack works in Research;
6. time filters stay within metric-level coverage;
7. aggregation produces defensible results;
8. provenance and license information remain available.

## Share a research pack

Distribute source folders, catalog files, geometry dependencies, and a README
that states:

- compatible runtime revision;
- data versions and retrieval dates;
- licenses and citation text;
- conversion and validation method;
- geographic and temporal coverage;
- known limitations;
- checksums for large artifacts when practical.

You may host or transfer these files using infrastructure you control. Hosted
release operations, account systems, commercial controls, internal collectors,
and DaedalMap's production converters are not required for compatible academic
packs.

