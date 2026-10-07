# Kaggle Dataset Proposal

## Dataset 1: "World Cities Database 2026 — Population, Coordinates, Timezone"

### Metadata
- **Title:** World Cities Database 2026 — 4,500+ Cities with Population & Coordinates
- **Subtitle:** Curated dataset of cities worldwide with population above 100,000
- **Tags:** geography, cities, population, geospatial, geonames, world-data, coordinates
- **License:** CC BY 4.0
- **File format:** CSV (primary) + Parquet (alternative)

### Description (Kaggle dataset page)

```markdown
# World Cities Database 2026

A curated dataset of **4,500+ cities worldwide** with population above 100,000.
Includes coordinates, timezone, elevation, and country association.

## Source
[Bamwor](https://bamwor.com) — Based on GeoNames data, curated and enriched.

## Columns
- `geoname_id` — GeoNames unique identifier
- `name` — City name (English)
- `country_code` — ISO 3166-1 alpha-2 country code
- `population` — City population
- `latitude` / `longitude` — Geographic coordinates
- `timezone` — IANA timezone identifier
- `elevation` — Elevation in meters
- `feature_code` — GeoNames feature code (PPLC=capital, PPLA=admin center, etc.)

## Quick Stats
- **4,500+ cities** across 200+ countries
- Population range: 100,000 to 37,000,000+
- Geographic coverage: All continents except Antarctica

## Want More?
This is a sample of the complete dataset:
- **Full dataset:** 13.4M cities — available at [bamwor.com/datasets](https://bamwor.com/en/datasets)
- **REST API:** Real-time access to all data — [bamwor.com/developers](https://bamwor.com/en/developers)
- **MCP Server:** AI agent integration — [bamwor-mcp-server on npm](https://npmjs.com/package/bamwor-mcp-server)
```

---

## Dataset 2: "World Countries Complete Dataset 2026"

### Metadata
- **Title:** World Countries Dataset 2026 — 261 Countries with Population & Area
- **Subtitle:** Complete list of countries and territories with basic demographics
- **Tags:** geography, countries, population, demographics, world-data, ISO
- **License:** CC BY 4.0

### Description

```markdown
# World Countries Dataset 2026

Complete dataset of **261 countries and territories** with population, area,
capital, geographic region, and coordinates.

## Source
[Bamwor](https://bamwor.com) — Aggregated from CIA World Factbook, UN, World Bank.

## Columns
- `name` — Country name (English)
- `slug` — URL-friendly identifier
- `iso_code` — ISO 3166-1 alpha-2 code
- `capital` — Capital city
- `region` — Geographic region
- `population` — Total population
- `area_sq_km` — Area in square kilometers
- `latitude` / `longitude` — Geographic center
- `category` — "country" or "territory"

## Want More?
- 20+ statistics per country (GDP, HDI, etc.) via API
- [Bamwor API](https://bamwor.com/en/developers) | [Datasets](https://bamwor.com/en/datasets)
```

---

## Notebook Proposal: "Exploring World Urbanization"

### Metadata
- **Title:** Exploring World Urbanization: Top Cities by Country (2026)
- **Tags:** geography, data-visualization, urbanization, population

### Notebook outline

```python
# Cell 1 — Introduction
"""
# Exploring World Urbanization

In this notebook, we analyze the distribution of major cities worldwide
using the Bamwor World Cities Dataset.

Data source: [Bamwor](https://bamwor.com) — 4,500+ cities (100K+ population)
Full dataset: 13.4M cities at bamwor.com/datasets
"""

# Cell 2 — Load data
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px

df = pd.read_csv("/kaggle/input/world-cities-2026/world_cities.csv")
print(f"Total cities: {len(df):,}")
print(f"Countries represented: {df['country_code'].nunique()}")

# Cell 3 — Top 20 largest cities
top20 = df.nlargest(20, "population")
fig = px.bar(top20, x="name", y="population", color="country_code",
             title="20 Largest Cities in the World (2026)")
fig.show()

# Cell 4 — Cities by continent/region
# Join with countries dataset for region info
countries = pd.read_csv("/kaggle/input/world-countries-2026/world_countries.csv")
merged = df.merge(countries[["iso_code", "region"]],
                  left_on="country_code", right_on="iso_code")
region_counts = merged.groupby("region").size().sort_values(ascending=False)
fig = px.pie(values=region_counts.values, names=region_counts.index,
             title="Distribution of Major Cities by Region")
fig.show()

# Cell 5 — Interactive world map
fig = px.scatter_geo(df.nlargest(500, "population"),
                     lat="latitude", lon="longitude",
                     size="population", hover_name="name",
                     title="500 Largest Cities in the World",
                     projection="natural earth")
fig.show()

# Cell 6 — Population distribution
fig = px.histogram(df, x="population", nbins=50,
                   title="Population Distribution of Cities (100K+)")
fig.update_xaxes(title="Population")
fig.show()

# Cell 7 — Countries with most cities above 1M
megacities = df[df["population"] >= 1_000_000]
mega_by_country = megacities.groupby("country_code").size().sort_values(ascending=False).head(15)
fig = px.bar(x=mega_by_country.index, y=mega_by_country.values,
             title="Countries with Most Cities Above 1M Population")
fig.show()

# Cell 8 — CTA
"""
## Want more data?

This dataset contains **4,500 cities** with population above 100,000.

The complete Bamwor dataset includes **13.4M cities** with:
- Multilingual names (English, Spanish, Portuguese, Italian)
- Administrative regions and provinces
- URL slugs for web integration
- Nearby city search

**Access options:**
- 📊 [Full datasets](https://bamwor.com/en/datasets)
- 🔌 [REST API](https://bamwor.com/en/developers) (free tier available)
- 🤖 [MCP Server](https://npmjs.com/package/bamwor-mcp-server) for AI agents
"""
```
