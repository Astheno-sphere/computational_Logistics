# HuggingFace Dataset: bamwor/world-countries

## Proposed README (for HuggingFace dataset card)

---

# World Countries Dataset 2026

Structured dataset of 261 countries and territories with population, area, capital, region, coordinates, and ISO codes. Multilingual names available in the full API.

## Dataset Description

- **Source:** [Bamwor](https://bamwor.com) — aggregated from CIA World Factbook, United Nations, World Bank
- **Size:** ~500KB (CSV), ~200KB (Parquet)
- **Records:** 261 countries and territories
- **Languages:** English (names only — full multilingual data via API)
- **License:** CC BY 4.0
- **Last Updated:** March 2026

## Fields

| Column | Type | Description |
|--------|------|-------------|
| name | string | Country name (English) |
| slug | string | URL-friendly identifier |
| iso_code | string | ISO 3166-1 alpha-2 code |
| capital | string | Capital city name |
| region | string | Geographic region (e.g. "Europe", "South America") |
| population | int | Total population |
| area_sq_km | float | Total area in square kilometers |
| latitude | float | Center latitude |
| longitude | float | Center longitude |
| category | string | "country" or "territory" |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("bamwor/world-countries")
df = ds["train"].to_pandas()

# Top 10 most populous countries
print(df.nlargest(10, "population")[["name", "population", "region"]])
```

## What's NOT included (available via API)

- 20+ statistics per country (GDP, HDI, life expectancy, literacy, etc.)
- Multilingual names (English, Spanish, Portuguese, Italian)
- Multilingual URL slugs
- Country sections (detailed text descriptions)
- Detailed resources and links
- Real-time API access
- City data (13.4M cities — see bamwor/world-cities)

## Full Data Access

For complete data with statistics, multilingual support, and real-time API:
- **API:** [bamwor.com/developers](https://bamwor.com/en/developers)
- **MCP Server:** [bamwor-mcp-server](https://npmjs.com/package/bamwor-mcp-server) for AI agents
- **Full Datasets:** [bamwor.com/datasets](https://bamwor.com/en/datasets)

## Citation

```bibtex
@misc{bamwor2026countries,
  title={World Countries Dataset 2026},
  author={Bamwor},
  year={2026},
  url={https://bamwor.com},
  note={Aggregated from CIA World Factbook, UN, World Bank}
}
```

---

# HuggingFace Dataset: bamwor/world-cities

## Proposed README (for HuggingFace dataset card)

---

# World Cities Dataset 2026

Structured dataset of 4,500+ cities with population above 100,000. Includes coordinates, timezone, elevation, and country association.

## Dataset Description

- **Source:** [Bamwor](https://bamwor.com) — based on GeoNames data, curated and enriched
- **Size:** ~2MB (CSV), ~800KB (Parquet)
- **Records:** ~4,500 cities (population ≥ 100,000)
- **Full dataset:** 13.4M cities (available via API/premium)
- **License:** CC BY 4.0
- **Last Updated:** March 2026

## Fields

| Column | Type | Description |
|--------|------|-------------|
| geoname_id | int | GeoNames identifier |
| name | string | City name (English) |
| country_code | string | ISO 2-letter country code |
| population | int | City population |
| latitude | float | Latitude |
| longitude | float | Longitude |
| timezone | string | IANA timezone |
| elevation | int | Elevation in meters (if available) |
| feature_code | string | GeoNames feature code |

## Usage

```python
from datasets import load_dataset

ds = load_dataset("bamwor/world-cities")
df = ds["train"].to_pandas()

# Top 20 largest cities globally
print(df.nlargest(20, "population")[["name", "country_code", "population"]])

# Cities in Brazil above 500K
brazil = df[(df["country_code"] == "BR") & (df["population"] >= 500000)]
print(brazil.sort_values("population", ascending=False))
```

## What's NOT included (available via API/premium)

- 13.4M+ cities (this dataset only includes cities ≥ 100K population)
- Multilingual city names (Spanish, Portuguese, Italian)
- Administrative region / province names
- URL slugs for web integration
- Nearby cities search (PostGIS-powered)
- Real-time API access

## Full Data Access

- **Complete Dataset (13.4M cities):** [bamwor.com/datasets](https://bamwor.com/en/datasets)
- **REST API:** [bamwor.com/developers](https://bamwor.com/en/developers)
- **MCP Server for AI:** [bamwor-mcp-server](https://npmjs.com/package/bamwor-mcp-server)

## Citation

```bibtex
@misc{bamwor2026cities,
  title={World Cities Dataset 2026},
  author={Bamwor},
  year={2026},
  url={https://bamwor.com},
  note={Based on GeoNames, curated by Bamwor}
}
```

---

## Proposed HuggingFace Metadata (YAML frontmatter)

### world-countries
```yaml
---
license: cc-by-4.0
language:
  - en
tags:
  - geography
  - countries
  - world-data
  - geospatial
  - population
  - demographics
size_categories:
  - n<1K
task_categories:
  - tabular-classification
  - feature-extraction
pretty_name: World Countries Dataset 2026
---
```

### world-cities
```yaml
---
license: cc-by-4.0
language:
  - en
tags:
  - geography
  - cities
  - population
  - geospatial
  - geonames
  - coordinates
size_categories:
  - 1K<n<10K
task_categories:
  - tabular-classification
  - feature-extraction
pretty_name: World Cities Dataset 2026 (Population ≥ 100K)
---
```
