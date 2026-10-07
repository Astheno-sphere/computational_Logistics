# Dataset Specification — HuggingFace & Kaggle

**Status:** SPECIFICATION ONLY — queries NOT executed, data NOT generated

---

## Dataset 1: World Countries

### Target platforms
- HuggingFace: `bamwor/world-countries`
- Kaggle: "World Countries Dataset 2026"

### Fields (free tier)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| name | string | `countries.name_en` | Country name (English only) |
| slug | string | `countries.slug_en` | URL-friendly identifier |
| iso_code | string | `countries.iso_code` | ISO 3166-1 alpha-2 |
| capital | string | `country_stats.value WHERE stat_key='capital'` | Capital city name |
| region | string | `regions.name_en` | Geographic region |
| population | bigint | `country_stats.value WHERE stat_key='population'` | Total population |
| area_sq_km | float | `country_stats.value WHERE stat_key='area_sq_km'` | Area in km² |
| latitude | float | `countries.latitude` | Center latitude |
| longitude | float | `countries.longitude` | Center longitude |
| category | string | `countries.category` | "country" or "territory" |

### What is NOT included (premium boundary)
- Multilingual names (es, pt, it)
- Multilingual slugs
- 20+ statistics (GDP, HDI, life expectancy, literacy, etc.)
- Country sections (detailed text descriptions)
- Resources and external links
- Flag/map URLs

### Estimated volume
- Records: 261
- CSV size: ~30KB
- Parquet size: ~15KB

### Proposed SQL query
```sql
SELECT
  c.name_en AS name,
  c.slug_en AS slug,
  c.iso_code,
  r.name_en AS region,
  c.latitude,
  c.longitude,
  c.category,
  MAX(CASE WHEN cs.stat_key = 'population' THEN cs.numeric_value END) AS population,
  MAX(CASE WHEN cs.stat_key = 'area_sq_km' THEN cs.numeric_value END) AS area_sq_km,
  MAX(CASE WHEN cs.stat_key = 'capital' THEN cs.text_value END) AS capital
FROM countries c
LEFT JOIN regions r ON c.region_id = r.id
LEFT JOIN country_stats cs ON cs.country_id = c.id
  AND cs.stat_key IN ('population', 'area_sq_km', 'capital')
GROUP BY c.id, c.name_en, c.slug_en, c.iso_code, r.name_en,
         c.latitude, c.longitude, c.category
ORDER BY c.name_en;
```

**IMPORTANT:** This query is a PROPOSAL. The actual table/column names must be verified against the Prisma schema before execution. The query above is based on common patterns observed in the codebase but may need adjustment.

### Verification before running
1. Confirm table names: `countries`, `regions`, `country_stats`
2. Confirm column names match Prisma schema
3. Confirm stat_key values for population, area, capital
4. Run with `LIMIT 5` first to verify output shape
5. Verify no premium data leaks into the output

---

## Dataset 2: World Cities

### Target platforms
- HuggingFace: `bamwor/world-cities`
- Kaggle: "World Cities Database 2026"

### Fields (free tier)

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| geoname_id | int | `geonames.geoname_id` | GeoNames unique ID |
| name | string | `geonames.ascii_name` | City name (ASCII English) |
| country_code | string | `geonames.country_code` | ISO 2-letter country code |
| population | int | `geonames.population` | City population |
| latitude | float | `geonames.latitude` | Latitude |
| longitude | float | `geonames.longitude` | Longitude |
| timezone | string | `geonames.timezone` | IANA timezone |
| elevation | int | `geonames.elevation` | Elevation in meters |
| feature_code | string | `geonames.feature_code` | GeoNames feature code |

### What is NOT included (premium boundary)
- Cities below 100,000 population (13.4M total → ~4,500 in free)
- Multilingual city names
- Province/admin region names
- URL slugs
- Nearby city relationships
- Country association details beyond country_code

### Estimated volume
- Records: ~4,500 (cities with population >= 100,000)
- CSV size: ~500KB
- Parquet size: ~200KB

### Proposed SQL query
```sql
SELECT
  geoname_id::int,
  ascii_name AS name,
  country_code,
  population::int,
  latitude::float,
  longitude::float,
  timezone,
  elevation::int,
  feature_code
FROM geonames
WHERE feature_class = 'P'
  AND population >= 100000
ORDER BY population DESC;
```

**IMPORTANT:** The geonames table is NOT in Prisma schema — it uses raw SQL via `prisma.$queryRawUnsafe`. The `::int` cast on geoname_id is critical (it's stored as bigint). The `country_code` is CHAR(2)/bpchar — but for the export query this doesn't matter since we're not using parameterized queries.

### Verification before running
1. Confirm column names in geonames table
2. Run with `LIMIT 10` to verify output shape
3. Count total: `SELECT COUNT(*) FROM geonames WHERE feature_class='P' AND population >= 100000`
4. Verify no admin1/admin2 names leak (those are premium)
5. Spot-check a few known cities (Tokyo, São Paulo, Lagos)

---

## Export Strategy

### Step 1: Generate CSVs
Execute queries against production DB (read-only) and export to CSV.

**Method A — via psql from EC2:**
```bash
ssh -i ~/.ssh/ec2-genwor.pem ec2-user@18.117.120.42

docker exec -i bamwor-mundofacts-db-1 psql -U bamwor -d bamwor_db \
  -c "\COPY (SELECT ...) TO STDOUT WITH CSV HEADER" > /tmp/world_countries.csv

docker exec -i bamwor-mundofacts-db-1 psql -U bamwor -d bamwor_db \
  -c "\COPY (SELECT ...) TO STDOUT WITH CSV HEADER" > /tmp/world_cities.csv

# Download to local
scp -i ~/.ssh/ec2-genwor.pem ec2-user@18.117.120.42:/tmp/world_countries.csv .
scp -i ~/.ssh/ec2-genwor.pem ec2-user@18.117.120.42:/tmp/world_cities.csv .
```

**Method B — via API (slower but zero DB risk):**
```bash
# Countries: paginate through /api/v1/countries
# Cities: paginate through /api/v1/countries/{slug}/cities for each country
# This is slower but 100% isolated
```

Recommended: **Method A** — single read-only query, no writes, no locks.

### Step 2: Generate Parquet (local)
```python
import pandas as pd

df = pd.read_csv("world_countries.csv")
df.to_parquet("world_countries.parquet", index=False)

df = pd.read_csv("world_cities.csv")
df.to_parquet("world_cities.parquet", index=False)
```

### Step 3: Quality Validation
- [ ] Country count = 261
- [ ] City count ≈ 4,500 (all with pop >= 100,000)
- [ ] No null names
- [ ] No null country_codes
- [ ] Population values are reasonable (no negatives, no zeros for major cities)
- [ ] Coordinates are within valid ranges (-90 to 90, -180 to 180)
- [ ] ISO codes are valid 2-letter codes
- [ ] UTF-8 encoding is clean (verify with `file --mime` and spot-check)
- [ ] No duplicate geoname_ids
- [ ] Tokyo, São Paulo, Mexico City, Lagos, Cairo are present in cities
- [ ] United States, China, India, Brazil are present in countries

---

## File Structure for Upload

### HuggingFace
```
bamwor/world-countries/
├── README.md           # From docs/huggingface-readme.md (first section)
├── data/
│   ├── train/
│   │   └── data.parquet
│   └── train.csv       # Alternative format
└── .gitattributes      # LFS for large files (not needed at this size)

bamwor/world-cities/
├── README.md           # From docs/huggingface-readme.md (second section)
├── data/
│   ├── train/
│   │   └── data.parquet
│   └── train.csv
└── .gitattributes
```

### Kaggle
```
world-countries-2026/
├── dataset-metadata.json
├── world_countries.csv
└── README.md

world-cities-2026/
├── dataset-metadata.json
├── world_cities.csv
└── README.md

# Notebook (separate upload)
exploring-world-urbanization.ipynb
```

---

## Kaggle dataset-metadata.json (proposed)

### Countries
```json
{
  "title": "World Countries Dataset 2026 — 261 Countries with Population & Area",
  "subtitle": "Complete list of countries and territories with basic demographics",
  "description": "Structured dataset of 261 countries from CIA World Factbook, UN, World Bank. Source: bamwor.com",
  "id": "KAGGLE_USERNAME/world-countries-2026",
  "licenses": [{ "name": "CC-BY-4.0" }],
  "keywords": ["geography", "countries", "population", "demographics", "world-data"],
  "resources": [
    { "path": "world_countries.csv", "description": "261 countries with population, area, coordinates" }
  ]
}
```

### Cities
```json
{
  "title": "World Cities Database 2026 — 4,500+ Cities with Population & Coordinates",
  "subtitle": "Curated dataset of cities worldwide with population above 100,000",
  "description": "4,500+ cities from GeoNames, curated by Bamwor. Source: bamwor.com",
  "id": "KAGGLE_USERNAME/world-cities-2026",
  "licenses": [{ "name": "CC-BY-4.0" }],
  "keywords": ["geography", "cities", "population", "geospatial", "geonames", "coordinates"],
  "resources": [
    { "path": "world_cities.csv", "description": "4,500+ cities with coordinates, timezone, elevation" }
  ]
}
```
