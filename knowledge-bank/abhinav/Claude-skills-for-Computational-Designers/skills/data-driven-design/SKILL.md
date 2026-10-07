---
title: Data-Driven Design
description: GIS integration, sensor data, occupancy analytics, space syntax analysis, urban data analytics, climate data processing, and API data sources for evidence-based AEC computational design
version: 1.0.0
tags: [data-driven, GIS, sensors, IoT, space-syntax, occupancy, analytics, API, climate-data, evidence-based]
auto_activate: true
user_invocable: true
invocation: /data-driven-design
---

# Data-Driven Design

This skill provides comprehensive guidance on integrating quantitative data into every stage of the architectural and urban design process. It covers geospatial data, environmental sensing, occupancy analytics, spatial network analysis, climate processing, urban datasets, and the APIs that serve them. The goal is to replace intuition-only design with evidence-based reasoning while preserving creative agency.

---

## 1. Data-Driven Design Philosophy

### 1.1 Evidence-Based vs. Intuition-Based Design

Traditional design relies heavily on precedent, aesthetic judgment, and professional intuition. These are valuable but unverifiable. Evidence-based design augments intuition with measurable inputs:

| Dimension | Intuition-Based | Evidence-Based |
|---|---|---|
| Site analysis | Walkthrough, photos | GIS layers, sensor grids, satellite imagery |
| Program sizing | Rules of thumb | Occupancy analytics, utilization studies |
| Circulation | Designer judgment | Space syntax integration/choice values |
| Orientation | Sun path intuition | EPW-parsed radiation/temperature analysis |
| Massing | Formal exploration | Daylight/energy simulation feedback loops |
| Post-occupancy | Anecdotal feedback | Sensor-driven POE dashboards |

Evidence-based design does not eliminate intuition. It provides a quantitative substrate on which creative decisions rest, making design rationale transparent, defensible, and reproducible.

### 1.2 Data as Design Input, Not Just Validation

The critical shift: data must enter the design process at the very beginning, not after decisions are made. In the traditional workflow, simulation runs after design is locked, serving only to confirm or reject. In a data-driven workflow:

1. **Pre-design data collection** -- site climate, demographics, transport, land use, environmental constraints
2. **Data-informed brief** -- program areas derived from utilization studies, not guesses
3. **Generative exploration** -- design options generated with data constraints embedded
4. **Continuous feedback** -- every design iteration evaluated against data-derived KPIs
5. **Post-occupancy loop** -- sensor data feeds back into future project templates

### 1.3 The Data-to-Design Pipeline

```
[Raw Data Sources]
    |
    v
[Acquisition] -- APIs, sensors, manual surveys, open data portals
    |
    v
[Cleaning & Validation] -- missing value handling, outlier detection, CRS alignment
    |
    v
[Processing & Analysis] -- statistical summaries, spatial analysis, temporal patterns
    |
    v
[Translation to Design Parameters] -- the critical creative step
    |
    v
[Parametric Model Integration] -- Grasshopper data trees, Dynamo lists, scripted geometry
    |
    v
[Design Evaluation] -- simulation, scoring, multi-criteria comparison
    |
    v
[Visualization & Communication] -- dashboards, reports, AR overlays
```

### 1.4 Ethical Considerations in Data Use

- **Bias recognition**: Census data reflects historical segregation. Transport data skews toward car owners. WiFi tracking data skews toward smartphone owners. Understand what populations are invisible in your dataset.
- **Consent and transparency**: Occupancy data collection must be disclosed to building users. GDPR, CCPA, and equivalent regulations apply.
- **Algorithmic fairness**: When data drives automated design decisions (e.g., park placement), audit for equitable outcomes across demographics.
- **Data provenance**: Document the source, date, methodology, and known limitations of every dataset used in design decisions.

### 1.5 Privacy and Anonymization

- Aggregate occupancy data to zones and time windows (minimum 15-minute bins, minimum 5-person zones) to prevent individual identification.
- Strip MAC addresses, device IDs, and personal identifiers before storage.
- Use k-anonymity (k >= 5) for any published spatial movement data.
- Separate data collection infrastructure from building access control systems.
- Establish data retention policies: raw sensor data purged after 12 months, aggregated statistics retained indefinitely.

---

## 2. GIS Integration

### 2.1 GIS Fundamentals for Designers

**Coordinate Reference Systems (CRS)**:
- **Geographic CRS**: Latitude/longitude on an ellipsoid (WGS84 = EPSG:4326). Units: degrees. Not suitable for distance/area measurement.
- **Projected CRS**: Flat plane projection. UTM zones (EPSG:326xx for north, 327xx for south), State Plane (US), British National Grid. Units: meters or feet. Required for accurate geometric operations.
- **Rule**: Always know your CRS. Always reproject to a projected CRS before measuring distances or areas.

**Projections**:
- **Conformal** (preserve angles): Mercator, Transverse Mercator, Lambert Conformal Conic. Best for navigation and local design.
- **Equal-area** (preserve area): Albers, Mollweide. Best for thematic mapping at continental/global scale.
- **Equidistant** (preserve distance along certain lines): Azimuthal Equidistant.
- For site-scale AEC work, UTM or local State Plane projections are almost always appropriate.

**Vector vs. Raster**:
- **Vector**: Points (trees, sensors), lines (roads, utilities), polygons (parcels, buildings). Precise geometry. Attribute tables. Formats: Shapefile, GeoJSON, GeoPackage, KML.
- **Raster**: Grid of pixels. Each pixel holds a value (elevation, temperature, land cover class). Formats: GeoTIFF, IMG, ASCII Grid. Resolution matters: 1m DEM vs. 30m DEM.

### 2.2 Key GIS Data Sources

| Source | Data Types | Resolution/Coverage | Cost |
|---|---|---|---|
| OpenStreetMap | Buildings, roads, POIs, land use | Global, variable quality | Free |
| USGS 3DEP | DEM, LiDAR point clouds | 1m (US), 10m (US) | Free |
| Copernicus DEM | Elevation | 30m global | Free |
| NLCD | Land cover classification | 30m (US) | Free |
| Census TIGER | Boundaries, roads, tracts | US | Free |
| Ordnance Survey | Buildings, terrain, addresses | UK | Mixed |
| Google Earth Engine | Satellite imagery, derived products | 10m--1km, global | Free (research) |
| Mapbox | Vector tiles, satellite | Global | Freemium |
| Local government GIS portals | Parcels, zoning, utilities, trees | City-level | Usually free |

### 2.3 GIS Tools

- **QGIS**: Free, open-source, full-featured desktop GIS. Plugin ecosystem. Python scripting (PyQGIS). Best for data preparation and analysis before importing to design tools.
- **ArcGIS Pro**: Industry standard. CityEngine integration. Geodatabase management. Advanced spatial analysis. Expensive license.
- **Mapbox**: Web-based tiles and APIs. Excellent for interactive maps. Mapbox GL JS for web dashboards.
- **Google Earth Engine**: Planetary-scale raster analysis. JavaScript/Python API. Best for satellite time-series analysis (vegetation change, urban growth, heat island).

### 2.4 Grasshopper GIS Plugins

- **Elk** (free): Imports OSM data (buildings, roads, topography) into Grasshopper. Supports .osm files. Terrain from .img files. Simple but effective for urban context models.
- **Heron** (free): Imports Shapefiles, raster images, topography. More format support than Elk. GeoTIFF import for terrain. Reprojection built in.
- **Meerkat** (free): Real-time GIS data streaming. OpenStreetMap tiles. WMS/WMTS service connections.
- **Urbano** (commercial): Urban mobility analysis. Walkability scoring. Amenity accessibility. Network-based analysis integrated with Grasshopper geometry.
- **DeCodingSpaces Toolbox** (free): Space syntax, network analysis, urban morphology metrics computed directly on GIS-imported geometry.

### 2.5 Typical GIS-to-Design Workflows

1. **Terrain modeling**: Download DEM (GeoTIFF) -> import via Heron -> create mesh surface -> drape site boundary -> cut/fill analysis.
2. **Site boundary extraction**: Download parcel Shapefile from local GIS portal -> import via Heron -> extract target parcel polygon -> set as design boundary.
3. **Context building generation**: Download OSM buildings -> import via Elk -> extrude by height attribute (or estimate floors x 3.5m) -> use as solar/wind context.
4. **Road network import**: OSM road centerlines -> import -> offset for right-of-way widths -> classify by road type.
5. **Land use mapping**: Zoning Shapefile -> import -> color-code by zone type -> overlay with site boundary -> identify constraints.
6. **Walkability analysis**: Import road network + POIs -> compute walking distances via network -> generate isochrone maps -> identify underserved areas.

---

## 3. Sensor Data & IoT

### 3.1 Sensor Types for Buildings

| Sensor | Measures | Range | Accuracy | Placement |
|---|---|---|---|---|
| Thermocouple/RTD | Temperature | -200 to +850 C | +/-0.5 C | Duct, room, outdoor |
| Capacitive RH | Relative humidity | 0--100% | +/-2% | Room center, avoid direct airflow |
| NDIR CO2 | CO2 concentration | 0--5000 ppm | +/-50 ppm | Breathing zone (1.2m height) |
| Photodiode/Lux | Illuminance | 0--100,000 lux | +/-5% | Desktop height, avoid direct sun |
| PIR | Occupancy (binary) | 5--12m range | N/A | Ceiling, corner mount |
| MEMS microphone | Sound level | 30--130 dBA | +/-1.5 dB | Wall, 1.5m height |
| Electrochemical | PM2.5, VOC, O3, NO2 | Varies | +/-10--20% | Representative location |
| Ultrasonic | Distance/presence | 0.2--6m | +/-1cm | Desk, doorway |

### 3.2 Building Management Systems (BMS)

Modern BMS systems (Siemens Desigo, Honeywell Niagara, Johnson Controls Metasys, Schneider EcoStruxure) centralize HVAC, lighting, and fire/safety data. Key concepts:
- **Points**: Individual data values (supply air temp, damper position, setpoint). A typical office building has 5,000--50,000 points.
- **Trends**: Historical time-series logs of point values. Typical interval: 5--15 minutes.
- **Alarms**: Threshold-triggered events.
- **Schedules**: Time-based control programs.

### 3.3 Data Protocols

- **BACnet**: Building Automation and Control Networks. The dominant building protocol. Defines object types (analog input, binary output, schedule). IP-based or MS/TP (RS-485). Read via BACnet libraries (BAC0 for Python).
- **Modbus**: Simple register-based protocol. RTU (serial) or TCP (Ethernet). Each device has a register map. Common for submetering, VFDs.
- **MQTT**: Lightweight publish/subscribe messaging. Ideal for IoT sensors. Broker-based (Mosquitto, HiveMQ). JSON payloads. Topics structured as building/floor/zone/sensor_type.
- **REST API**: HTTP-based. Many modern BMS and IoT platforms expose REST endpoints. JSON responses. Polling-based (not real-time without webhooks/WebSockets).

### 3.4 Time-Series Data Handling

- **Storage**: InfluxDB (purpose-built time-series DB), TimescaleDB (PostgreSQL extension), or cloud (AWS Timestream, Azure Time Series Insights).
- **Sampling rate**: Environmental sensors: 1--5 minute intervals. Energy meters: 1--15 minute intervals. Occupancy: 1--5 minute intervals.
- **Missing data**: Forward-fill for slow-changing variables (temperature). Interpolation for gradual variables. Flag and exclude for fast-changing variables (occupancy).
- **Aggregation**: Downsample to hourly/daily for long-term storage. Preserve min/max/mean/count.
- **Anomaly detection**: Z-score method for univariate, Isolation Forest for multivariate. Flag sensor drift (gradual offset), sensor failure (flatline or NaN), and impossible values (negative CO2).

### 3.5 Digital Twin Sensor Integration

A digital twin is a live 3D model synchronized with real-time sensor data. Architecture:

```
[Physical Building]
    |
    v
[Sensors + BMS] -- BACnet, Modbus, MQTT
    |
    v
[Data Ingestion Layer] -- Node-RED, Apache Kafka, custom ETL
    |
    v
[Time-Series Database] -- InfluxDB, TimescaleDB
    |
    v
[API Layer] -- REST/GraphQL endpoints
    |
    v
[3D Visualization] -- Unity/Unreal, Three.js, Forge Viewer
    |
    v
[Digital Twin Dashboard] -- color-coded zones, real-time charts, alerts
```

Sensor data maps to 3D model via spatial identifiers (room ID, zone ID, floor number). Color gradients on room surfaces represent temperature, CO2, occupancy density. Historical playback enables pattern discovery.

---

## 4. Occupancy Analytics

### 4.1 Sensing Technologies

| Technology | Accuracy | Granularity | Privacy Impact | Cost |
|---|---|---|---|---|
| PIR sensors | 85--90% (binary only) | Room-level, binary | Low | Low |
| WiFi probe requests | 70--80% (counting) | Zone-level, count + dwell | Medium--High | Low (uses existing infra) |
| Bluetooth beacons | 80--90% | Zone-level, individual tracking | High | Medium |
| Camera + AI counting | 95%+ | Entry-level, count + direction | High (even anonymized) | Medium--High |
| Badge/access card | 99% (entry only, no exit) | Door-level, individual | Medium | Low (uses existing infra) |
| Desk sensors (ultrasonic/PIR) | 95%+ | Desk-level, binary | Low | Medium |
| CO2-based estimation | 60--75% | Room-level, count estimate | None | Low |
| LiDAR people counting | 95%+ | Entry-level, count + height | Low--Medium | High |

### 4.2 Occupancy Density Mapping

Convert raw sensor counts to spatial density:
1. Assign sensors to spatial zones (rooms, departments, floors).
2. Compute occupancy rate: actual_count / design_capacity.
3. Aggregate over time: peak (95th percentile), typical (median), average (mean).
4. Visualize as heat map overlay on floor plan.

Key metrics:
- **Utilization rate**: Hours occupied / total available hours (a room used 4 of 8 workday hours = 50% utilization).
- **Peak occupancy**: Maximum simultaneous occupants (drives HVAC sizing).
- **Diversity factor**: Peak of whole building / sum of individual room peaks (typically 0.6--0.8).
- **Frequency**: How often a space is used per week.

### 4.3 Design Implications of Occupancy Data

- **Right-sizing**: If meeting rooms average 30% utilization, reduce count and add more informal collaboration zones.
- **HVAC zoning**: High-variability zones need VAV with fast response. Consistently occupied zones can use simpler systems.
- **Circulation sizing**: Peak flow data from entry sensors drives corridor width and elevator sizing.
- **Flexible programming**: Low-utilization spaces become candidates for multi-use or hot-desking.
- **Post-occupancy feedback**: Compare design assumptions (occupancy schedules in energy models) with reality.

---

## 5. Space Syntax

### 5.1 Core Concepts

Space syntax, developed by Bill Hillier and Julienne Hanson at UCL in the 1980s, quantifies the configurational properties of spatial networks. It reveals how the structure of space itself shapes movement, encounter, and social outcomes.

**Axial map**: The minimum set of longest straight lines (axial lines) that pass through all convex spaces and make all connections in a spatial system. Constructed by drawing lines of sight and access.

**Key measures** (computed on the axial graph where nodes = axial lines, edges = intersections):

| Measure | Definition | Interpretation |
|---|---|---|
| Connectivity | Number of lines directly intersecting a given line | Local accessibility |
| Depth | Shortest topological distance from one line to another | Remoteness |
| Mean Depth | Average depth from a line to all other lines | Overall accessibility |
| Integration (Rn) | Reciprocal of Relative Asymmetry (normalized mean depth) | Global accessibility; high = well-connected |
| Integration (R3) | Integration computed within topological radius 3 | Local accessibility within 3 steps |
| Choice (Rn) | Number of shortest paths passing through a line | Through-movement potential; high = likely route |

### 5.2 Axial Analysis

Global integration formula:
```
RA = 2(MD - 1) / (k - 2)
```
Where MD = mean depth, k = number of lines in the system.

Real Relative Asymmetry (normalized for system size):
```
RRA = RA / D_k
```
Where D_k is the diamond value for a graph of k nodes.

Integration = 1 / RRA. Higher values = more integrated (accessible).

Choice counts how many shortest paths between all pairs of nodes pass through a given node. Normalized choice (NACH) enables cross-system comparison.

### 5.3 Segment Analysis

More recent method. Axial lines are broken at intersections into segments. Analysis uses angular distance (cumulative turn angle) rather than topological distance. This better predicts vehicular movement and pedestrian route choice.

Angular choice and angular integration at various metric radii (400m, 800m, 1200m, 2000m, 5000m, n) reveal multi-scale spatial structure.

### 5.4 Visibility Graph Analysis (VGA)

1. Overlay a regular grid of points on the floor plan (typically 0.5--1.0m spacing).
2. For each pair of points, determine mutual visibility (unobstructed straight line).
3. Construct the visibility graph (nodes = grid points, edges = mutual visibility).
4. Compute graph measures: visual connectivity, visual integration, visual mean depth, clustering coefficient.

VGA reveals:
- Visual fields and their depth
- Spaces that are visually dominant or hidden
- Potential for natural surveillance (high clustering = many mutual visibility connections)
- Wayfinding legibility

### 5.5 Isovist Analysis

An isovist is the set of all points visible from a given vantage point. Isovist properties:
- **Area**: Total visible floor area. Larger = more open.
- **Perimeter**: Boundary length. Longer relative to area = more complex visual field.
- **Compactness**: 4 * pi * area / perimeter^2. Circle = 1. Lower = more elongated/fragmented.
- **Occlusivity**: Length of the isovist boundary not formed by real surfaces (i.e., depth edges). Higher = more hidden areas beyond view.
- **Drift**: Distance from the isovist centroid to the vantage point. Higher = directional bias in the visual field.
- **Min/Max radial**: Shortest and longest line of sight.

Isovist fields: compute isovists at every point on a grid. Map each property as a scalar field. Reveals spatial character continuously across the plan.

### 5.6 Tools for Space Syntax

- **depthmapX** (free, open-source): The reference implementation. Axial, segment, VGA, isovist, agent analysis. Import DXF plans. Export CSV results for statistical analysis.
- **Syntactic (Paco Holanda)**: Grasshopper plugin. Axial and segment analysis within parametric workflow. Enables real-time space syntax feedback during design.
- **SpiderWeb (Paco Holanda)**: Agent-based pedestrian simulation in Grasshopper. Agents navigate using space syntax logic.
- **DeCodingSpaces Toolbox**: Grasshopper plugin. Includes space syntax, shape grammar, and urban morphology analysis.

### 5.7 Correlation Studies

Space syntax measures consistently correlate with observed phenomena:
- **Pedestrian flow**: Integration (R3) correlates with pedestrian counts (r = 0.7--0.9 in many studies).
- **Retail rents**: Choice (Rn) correlates with commercial property values. High-choice streets attract retail.
- **Crime**: Low integration (segregated spaces) correlates with higher burglary rates. "Eyes on the street" effect.
- **Wayfinding**: Higher visual integration correlates with faster navigation and fewer wrong turns.

### 5.8 Application Scales

- **Floor plan**: Optimize room connectivity, visual relationships, circulation efficiency. Compare design variants quantitatively.
- **Building complex/campus**: Analyze building-to-building connectivity, identify isolated zones, optimize pedestrian routes.
- **Urban district**: Street network analysis. Identify high-integration streets for active frontages. Locate public amenities on high-choice streets. Predict pedestrian and vehicular flow distribution.
- **City scale**: Metropolitan integration structure. Identify integration cores, deformed wheels, urban villages.

---

## 6. Climate Data Processing

### 6.1 EPW Weather Files

EPW (EnergyPlus Weather) is the standard weather file format for building energy simulation. Each file represents one year (8760 hours) of weather data for a specific location.

**Structure**: Header (8 lines with location, design conditions, ground temperatures) + 8760 data rows (one per hour).

**Key data fields** (67 total, most important listed):

| Field | Unit | Description |
|---|---|---|
| Dry Bulb Temperature | C | Air temperature |
| Dew Point Temperature | C | Moisture indicator |
| Relative Humidity | % | Moisture ratio |
| Atmospheric Pressure | Pa | Station pressure |
| Global Horizontal Radiation | Wh/m2 | Total solar on horizontal |
| Direct Normal Radiation | Wh/m2 | Solar beam component |
| Diffuse Horizontal Radiation | Wh/m2 | Scattered solar |
| Wind Direction | degrees | 0=N, 90=E, 180=S, 270=W |
| Wind Speed | m/s | At measurement height (usually 10m) |
| Total Sky Cover | tenths | 0=clear, 10=overcast |
| Precipitable Water | mm | Column water vapor |
| Horizontal Infrared Radiation | Wh/m2 | Longwave from sky |

**Sources**: climate.onebuilding.org (4000+ locations), EnergyPlus website, Ladybug Tools EPW Map.

### 6.2 TMY Methodology

Typical Meteorological Year (TMY) files are composites: each month is selected from a multi-year record (typically 15--30 years) as the most "typical" month for that calendar month. Selection uses Finkelstein-Schafer statistics on key variables (solar radiation, temperature, humidity, wind). TMY represents normal conditions, not extremes. For extreme event analysis, use AMY (Actual Meteorological Year) files.

### 6.3 Climate Analysis Techniques

**Temperature bins**: Histogram of hourly temperatures. Reveals heating/cooling balance points, dominant temperature ranges. Drives passive design strategy selection.

**Degree-days**: Heating Degree Days (HDD) = sum of (base_temp - outdoor_temp) for all hours where outdoor < base. Cooling Degree Days (CDD) = sum of (outdoor_temp - base_temp) for all hours where outdoor > base. Typical base: 18.3C (65F). Used for energy benchmarking and climate classification.

**Psychrometric chart**: Plots temperature vs. humidity ratio. Overlay with comfort zone and passive strategy boundaries (evaporative cooling, thermal mass + night ventilation, natural ventilation). Givoni's bioclimatic chart is the classic reference.

**Wind rose**: Polar histogram of wind speed and direction. Segment by season, time of day, or temperature range for nuanced analysis. Critical for natural ventilation orientation, windbreak placement, and outdoor comfort.

**Sun path diagram**: Stereographic projection of solar positions throughout the year. Plot obstructions to determine solar access. Overlay with direct normal irradiance for useful solar hours. Essential for shading device design and PV placement.

### 6.4 Ladybug Weather Data Components

Ladybug (Grasshopper plugin) provides comprehensive weather data visualization and analysis:
- `LB Import EPW`: Parse EPW file into individual data streams.
- `LB Hourly Plot`: Time-series visualization of any weather variable.
- `LB Wind Rose`: Directional wind analysis.
- `LB Sun Path`: 3D sun path diagram in Rhino.
- `LB Psychrometric Chart`: Interactive psychrometric analysis with strategy overlays.
- `LB Adaptive Comfort`: Thermal comfort assessment using ASHRAE 55 adaptive model.
- `LB UTCI`: Universal Thermal Climate Index for outdoor comfort.
- `LB Degree Days`: Heating and cooling degree day calculation.

### 6.5 Future Climate Projections

Climate change requires designers to consider 2050 and 2080 conditions. Methods:
- **CCWorldWeatherGen** (free tool): "Morphs" present-day EPW files using IPCC AR4/AR5 climate model outputs. Applies monthly shift factors to temperature, radiation, humidity, wind.
- **WeatherShift** (commercial): Similar morphing with probabilistic approach (10th, 50th, 90th percentile outcomes).
- **Meteonorm future files**: Generated using climate model projections for specific emission scenarios (RCP 4.5, 8.5 / SSP 2-4.5, 5-8.5).

Typical 2050 shifts for mid-latitude cities: +1.5 to +3.0C mean temperature, +5 to +15% cooling energy, -5 to -15% heating energy, increased extreme heat events.

### 6.6 Urban Heat Island Effect

Urban areas are typically 1--5C warmer than surrounding rural areas due to:
- Reduced vegetation and evapotranspiration
- Increased thermal mass (concrete, asphalt)
- Waste heat from buildings, vehicles, industry
- Reduced sky view factor (canyon geometry traps longwave radiation)
- Reduced wind speed from surface roughness

Monitoring: Mobile transect surveys, fixed weather station networks, satellite-derived land surface temperature (Landsat, MODIS). Integration with design: adjust EPW data for urban context using UWG (Urban Weather Generator) by MIT.

---

## 7. Urban Data Analytics

### 7.1 Census Data Integration

Census data provides demographic, socioeconomic, and housing characteristics at multiple geographic levels (block, block group, tract, county, state in the US). Key variables for design:
- Population density (drives infrastructure sizing)
- Age distribution (playground vs. senior center needs)
- Household size (unit mix for housing projects)
- Income levels (affordability requirements)
- Commute mode (parking vs. transit infrastructure)
- Housing tenure (own vs. rent, vacancy rates)

Access via Census Bureau API (api.census.gov), IPUMS, or processed datasets (Social Explorer, PolicyMap).

### 7.2 Transport Data

**GTFS (General Transit Feed Specification)**: Standardized format for public transit schedules and routes. Published by transit agencies worldwide. Contains: stops, routes, trips, stop_times, calendar, shapes. Use for:
- Transit accessibility mapping (isochrone from any point via transit)
- Service frequency analysis (headways by time of day)
- Transit coverage gap identification

**Traffic counts**: State DOTs publish AADT (Annual Average Daily Traffic) counts on major roads. Available as GIS layers. Use for noise modeling, pedestrian safety analysis, roadway capacity assessment.

**Cycling/pedestrian counts**: Increasingly available from permanent counters (Eco-Counter) and Strava Metro data. Reveals active transport patterns and demand.

### 7.3 Real Estate Data

- **Transaction data**: Sale prices, rent levels, cap rates. Sources: Zillow (US), Zoopla (UK), local MLS feeds.
- **Land values**: Assessed values from tax records. Useful for development feasibility analysis.
- **Spatial patterns**: Price gradients, gentrification indicators, correlation with transit/amenity proximity.

### 7.4 Social Media and Sentiment Data

- **Geotagged posts**: Twitter/X, Instagram, Flickr. Reveal popular gathering spots, underused areas, perception of places.
- **Sentiment analysis**: NLP on location-tagged text. Identify areas perceived as unsafe, beautiful, lively, boring.
- **Limitations**: Severe demographic bias (young, tech-savvy, English-speaking over-represented). Use as supplement, not primary evidence.

### 7.5 Noise Mapping Data

EU Environmental Noise Directive requires strategic noise maps for agglomerations >100,000 population. Data includes:
- Road traffic noise (Lden, Lnight contours)
- Rail noise
- Aircraft noise
- Industrial noise

Use for: facade acoustic design, building orientation, buffer zone planning, amenity placement (playgrounds away from noise sources).

### 7.6 Air Quality Data

Sources: EPA AirNow (US), EEA (Europe), OpenAQ (global aggregator). Key pollutants: PM2.5, PM10, O3, NO2, SO2, CO. Available as station measurements and modeled surfaces. Design implications:
- Air intake placement (away from high-pollution zones)
- Filtration specification
- Outdoor space programming (avoid exercising near highways)
- Green infrastructure placement for particulate capture

### 7.7 Urban Metabolism Data

Material and energy flow analysis for cities: water consumption, waste generation, energy use, food supply. Data from utility companies, waste management, and municipal sustainability reports. Design implications for circular economy buildings and net-zero neighborhoods.

---

## 8. API Data Sources for AEC

### 8.1 Comprehensive API Reference

#### OpenStreetMap Overpass API
- **Endpoint**: `https://overpass-api.de/api/interpreter`
- **Data**: Buildings (footprints + height + levels), roads, railways, waterways, land use, POIs, amenities, trees
- **Rate limits**: Fair use; heavy queries may be throttled. Use local Overpass instance for production.
- **Auth**: None
- **Python library**: `overpy`, `osmnx`
- **Query language**: Overpass QL. Example: `[out:json];way["building"]({{bbox}});out body;>;out skel qt;`

#### Mapbox APIs
- **Endpoints**: `api.mapbox.com/v4/` (tiles), `/directions/v5/`, `/isochrone/v1/`, `/geocoding/v5/`
- **Data**: Vector/raster tiles, driving/walking/cycling directions, isochrones (travel time polygons), geocoding
- **Rate limits**: 100,000 free tile requests/month; 100,000 free directions/month
- **Auth**: Access token (free tier available)
- **Python library**: `mapbox` SDK, or direct HTTP via `requests`

#### Google Maps Platform
- **Endpoints**: `maps.googleapis.com/maps/api/place/`, `/directions/`, `/elevation/`
- **Data**: Place details (ratings, hours, type), directions with traffic, elevation profiles
- **Rate limits**: $200 free monthly credit; ~40,000 direction requests
- **Auth**: API key + billing account
- **Python library**: `googlemaps`

#### OpenWeather / NOAA
- **Endpoints**: `api.openweathermap.org/data/2.5/`, `www.ncdc.noaa.gov/cdo-web/api/v2/`
- **Data**: Current weather, forecasts, historical observations, climate normals
- **Rate limits**: OpenWeather: 1000 calls/day free. NOAA: 1000 calls/day free.
- **Auth**: API key
- **Python library**: `pyowm`, `noaa-sdk`

#### EPA APIs
- **Endpoints**: `aqs.epa.gov/data/api/`, `enviro.epa.gov/`
- **Data**: Air quality (AQI, criteria pollutants), brownfield/superfund sites, toxic release inventory, water quality
- **Rate limits**: Generous; registration required
- **Auth**: Email registration
- **Python library**: Direct `requests`; some community wrappers

#### Census Bureau API
- **Endpoint**: `api.census.gov/data/`
- **Data**: ACS (demographics, income, housing), Decennial Census, Economic Census, TIGER boundaries
- **Rate limits**: 500 calls/day without key; unlimited with free key
- **Auth**: Free API key
- **Python library**: `census`, `cenpy`

#### USGS 3DEP
- **Endpoint**: `elevation.nationalmap.gov/arcgis/rest/services/`
- **Data**: DEM (1/3 arc-second = ~10m, 1m where available), LiDAR point clouds
- **Rate limits**: Generous
- **Auth**: None
- **Python library**: `py3dep`, `requests`

#### Zillow / Zoopla
- **Endpoints**: `api.bridgedataoutput.com/api/v2/` (Zillow via Bridge), `api.zoopla.co.uk/api/v1/`
- **Data**: Property values, listings, Zestimates, comparable sales, neighborhood data
- **Rate limits**: Varies by plan; Bridge API has free tier
- **Auth**: API key
- **Python library**: Direct `requests`

#### GTFS Feeds
- **Source**: `transitfeeds.com`, individual agency websites
- **Data**: Static schedules (stops, routes, trips, stop_times) and GTFS-realtime (vehicle positions, trip updates, alerts)
- **Format**: ZIP of CSV files (static), Protocol Buffers (real-time)
- **Python library**: `gtfs-kit`, `partridge`, `gtfs-realtime-bindings`

#### Copernicus Data
- **Endpoint**: `scihub.copernicus.eu/dhus/`, `dataspace.copernicus.eu/`
- **Data**: Sentinel-2 (10m multispectral imagery), Sentinel-1 (SAR), Copernicus DEM (30m global)
- **Rate limits**: Generous; large file downloads
- **Auth**: Free registration
- **Python library**: `sentinelsat`, `eodag`, Google Earth Engine

---

## 9. Data Visualization for Design

### 9.1 Charts and Plots for Design Communication

Choose chart type by data type and audience:
- **Bar/column**: Compare categories (land use areas, room counts by type)
- **Line**: Time-series (temperature over year, occupancy over week)
- **Scatter**: Correlation (integration vs. pedestrian count, rent vs. distance to transit)
- **Heatmap**: 2D intensity (occupancy by hour and day-of-week, solar radiation by month and hour)
- **Radar/spider**: Multi-criteria comparison (design variant scoring across KPIs)
- **Sankey**: Flow diagrams (energy flow, material flow, movement distribution)
- **Box plot**: Distribution and outliers (indoor temperatures across zones)
- **Violin**: Distribution shape (daylight factor across rooms)

### 9.2 Spatial Data Visualization

- **Choropleth map**: Polygon fill color by data value (census tract by income, parcels by zoning).
- **Dot density**: Random dots within polygon proportional to value (population distribution).
- **Isoline/contour**: Equal-value lines (noise contours, temperature isotherms).
- **3D extrusion**: Height proportional to data (buildings by energy use, blocks by density).
- **Flow map**: Lines with width proportional to flow (pedestrian routes, transit ridership).
- **Heat map**: Continuous surface interpolated from point observations (air quality, temperature).

### 9.3 Dashboard Design for Stakeholder Engagement

Key principles:
- Lead with the "so what" -- headline KPI at top, detail below.
- Maximum 5--7 visualizations per dashboard view.
- Interactive filtering by time, zone, scenario.
- Consistent color coding across views.
- Annotations explaining thresholds and benchmarks.
- Export to PDF for offline review.

### 9.4 Grasshopper Visualization Tools

- **Human UI** (free): Build interactive WPF dashboards inside Grasshopper. Sliders, charts, data grids, buttons. Excellent for design review sessions.
- **Design Explorer** (free): Multi-objective design space exploration. Parallel coordinates plot. Filter Pareto-optimal solutions. Integrates with Colibri for automated iteration capture.
- **Colibri** (free): Automated design iteration. Records images, data, and parameters for every iteration. Exports to Design Explorer for interactive exploration.
- **TT Toolbox**: Data tree manipulation and visualization utilities.
- **Squid**: PDF generation from Grasshopper for automated reporting.

### 9.5 Web-Based Dashboards

- **Plotly Dash** (Python): Full-featured dashboarding framework. Interactive charts (Plotly.js). Layout with HTML/CSS. Callbacks for interactivity. Deploy as web app.
- **Streamlit** (Python): Rapid dashboard prototyping. Minimal code. Auto-refresh on script change. Built-in chart types. Map support (Folium, Pydeck, Mapbox).
- **Kepler.gl**: WebGL-powered large-scale geospatial visualization. 3D building layers, arc layers, heatmaps, hexbin. Jupyter integration.
- **Three.js / Speckle**: 3D model visualization in browser with data overlay. Speckle provides AEC-specific 3D viewer with data streams.

### 9.6 AR/VR Data Overlay

Emerging capability: overlay sensor data, simulation results, and analytics on physical or virtual building models.
- **AR**: Microsoft HoloLens, Apple Vision Pro. Overlay temperature gradients, occupancy counts, maintenance alerts on physical spaces during walkthroughs.
- **VR**: Oculus/Meta Quest, HTC Vive. Navigate data-rich virtual models during design review. Color-code surfaces by daylight factor, acoustic performance, energy flux.
- **Frameworks**: Unity with custom shaders for data visualization. Unreal Engine with Datasmith for AEC model import. WebXR for browser-based lightweight experiences.

---

## Summary of Key Workflows

| Workflow | Data Source | Processing Tool | Design Integration |
|---|---|---|---|
| Site context model | OSM, DEM | QGIS, Elk/Heron | Grasshopper geometry |
| Climate-responsive orientation | EPW | Ladybug | Parametric massing |
| Walkability analysis | OSM, GTFS | Urbano, osmnx | Site plan, amenity placement |
| Occupancy-driven program | Sensors, BMS | InfluxDB, Python | Area schedule adjustment |
| Circulation optimization | Floor plan | depthmapX, Syntactic | Layout refinement |
| Noise-informed planning | Noise maps | QGIS, Python | Building orientation, buffer zones |
| Demographic-responsive design | Census | cenpy, Python | Unit mix, community facilities |
| Real-time building performance | IoT sensors | Digital twin platform | Ongoing operations optimization |

---

## References and Further Reading

- Hillier, B. & Hanson, J. (1984). *The Social Logic of Space*. Cambridge University Press.
- Hillier, B. (1996). *Space is the Machine*. Cambridge University Press.
- Al-Sayed, K. et al. (2014). *Space Syntax Methodology*. Bartlett School of Architecture, UCL.
- Reinhart, C. (2014). *Daylighting Handbook I*. MIT Press.
- Ratti, C. & Claudel, M. (2016). *The City of Tomorrow*. Yale University Press.
- Batty, M. (2013). *The New Science of Cities*. MIT Press.
- EnergyPlus Documentation: Weather Data format specifications.
- Ladybug Tools documentation: ladybug.tools
- QGIS documentation: docs.qgis.org
