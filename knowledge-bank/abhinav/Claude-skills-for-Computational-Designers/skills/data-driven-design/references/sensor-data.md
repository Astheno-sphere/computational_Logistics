# Sensor Data Reference

This reference provides detailed technical specifications, integration architectures, data pipeline design, analysis methods, and practical implementation guidance for building sensor systems in the AEC context. It covers hardware selection, data protocols, storage, visualization, and digital twin integration.

---

## 1. Sensor Specification Tables

### 1.1 Temperature Sensors

| Parameter | RTD (Pt100) | Thermocouple (Type K) | Thermistor (NTC 10k) | Digital (SHT45) |
|---|---|---|---|---|
| Range | -200 to +850 C | -200 to +1250 C | -40 to +125 C | -40 to +125 C |
| Accuracy | +/-0.1 C (Class A) | +/-1.5 C (Class 1) | +/-0.2 C (at 25 C) | +/-0.1 C (at 25 C) |
| Resolution | 0.01 C (with 16-bit ADC) | 0.25 C (with 12-bit ADC) | 0.01 C (with 16-bit ADC) | 0.01 C |
| Response time | 1--10 s (in air) | 0.5--5 s (in air) | 2--10 s (in air) | 2--8 s (in air) |
| Output | Resistance (100 ohm at 0C) | Voltage (40 uV/C) | Resistance (10k ohm at 25C) | I2C digital |
| Self-heating | 0.1--0.5 C | None | 0.1--1.0 C | Negligible |
| Long-term drift | < 0.05 C/year | 1--2 C/year | 0.1--0.2 C/year | < 0.02 C/year |
| AEC application | HVAC calibration, lab | Industrial, extreme temp | Room temperature | Modern IoT systems |
| Cost per unit | $15--50 | $5--20 | $2--10 | $5--15 |

### 1.2 Humidity Sensors

| Parameter | Capacitive (SHT45) | Resistive | Chilled mirror |
|---|---|---|---|
| Range | 0--100% RH | 20--90% RH | 0--100% RH |
| Accuracy | +/-1.0% RH | +/-3--5% RH | +/-0.1% RH |
| Resolution | 0.01% RH | 1% RH | 0.01% RH |
| Response time (63%) | 4 s | 10--30 s | 30--60 s |
| Hysteresis | < 1% RH | 2--5% RH | None |
| Long-term drift | < 0.25% RH/year | 1--3% RH/year | None (self-calibrating) |
| AEC application | Room monitoring, HVAC | Budget monitoring | Calibration reference |
| Cost per unit | $5--15 | $2--8 | $1,000--5,000 |

### 1.3 CO2 Sensors

| Parameter | NDIR (SCD41) | Photoacoustic | Electrochemical |
|---|---|---|---|
| Range | 0--5,000 ppm | 0--10,000 ppm | 0--5,000 ppm |
| Accuracy | +/-40 ppm + 5% of reading | +/-3% of reading | +/-50 ppm + 3% of reading |
| Resolution | 1 ppm | 1 ppm | 10 ppm |
| Response time (T63) | 60 s | 30 s | 90 s |
| Operating principle | Infrared absorption at 4.26 um | Sound wave generation by IR absorption | Electrochemical reaction |
| Cross-sensitivity | Water vapor (compensated) | Water vapor | CO, H2, VOCs |
| Calibration interval | Autocalibration (ABC) or 6--12 months | Factory calibration, 5+ years | 12 months |
| Power consumption | 20--50 mA average | 10--30 mA | 5--15 mA |
| AEC application | DCV (demand-controlled ventilation), IAQ monitoring | High-accuracy IAQ | Budget sensors |
| Cost per unit | $30--80 | $100--300 | $10--30 |

### 1.4 Light Sensors

| Parameter | Photodiode (TSL2591) | Phototransistor | Spectroradiometer |
|---|---|---|---|
| Range | 0.001--88,000 lux | 1--100,000 lux | 0--200,000 lux |
| Accuracy | +/-5% | +/-10--20% | +/-2% |
| Spectral response | Visible + IR (dual channel) | Broadband | Per-wavelength (380--780 nm) |
| Resolution | 0.001 lux | 10 lux | 0.01 lux |
| Response time | < 1 ms | 1--10 ms | 100 ms -- 1 s |
| Output | I2C digital | Analog voltage | USB/RS-232 |
| AEC application | Daylight harvesting, shade control | Simple on/off control | Glare analysis, color quality |
| Cost per unit | $3--10 | $1--3 | $500--5,000 |

### 1.5 Occupancy/Presence Sensors

| Parameter | PIR (passive infrared) | Ultrasonic | Dual technology | Radar (mmWave) |
|---|---|---|---|---|
| Detection range | 5--15 m | 3--10 m | 5--12 m | 3--8 m |
| Coverage angle | 90--360 degrees | 180--360 degrees | 90--360 degrees | 60--120 degrees |
| Detection type | Motion (IR change) | Motion (Doppler) | Motion (PIR + US) | Presence (stationary detection) |
| False positive rate | Medium (drafts, sunlight) | Medium (curtains, HVAC noise) | Low | Very low |
| Stationary detection | No (requires periodic movement) | Yes (limited) | Limited | Yes |
| Power consumption | < 1 mA (passive) | 10--30 mA | 15--40 mA | 50--200 mA |
| AEC application | Lighting control, HVAC | Restroom, conference room | Open office | Desk occupancy, people counting |
| Cost per unit | $5--20 | $10--30 | $20--50 | $20--80 |

### 1.6 Air Quality Sensors

| Parameter | PM2.5 (laser scattering) | VOC (MOX) | NO2 (electrochemical) | O3 (electrochemical) |
|---|---|---|---|---|
| Range | 0--1000 ug/m3 | 0--30,000 ppb | 0--5,000 ppb | 0--5,000 ppb |
| Accuracy | +/-10 ug/m3 + 10% | +/-15% | +/-5 ppb + 15% | +/-5 ppb + 15% |
| Resolution | 1 ug/m3 | 1 ppb | 1 ppb | 1 ppb |
| Response time | 1--10 s | 1--30 s | 30--60 s | 30--60 s |
| Lifespan | 3--5 years (fan/laser) | 2--5 years | 2--3 years | 1--2 years |
| Cross-sensitivity | Humidity affects readings | Many gases | O3 | NO2 |
| Calibration needs | Factory + periodic co-location | Field calibration essential | Factory + periodic check | Factory + periodic check |
| Cost per unit | $10--50 | $5--30 | $20--80 | $20--80 |

### 1.7 Noise/Sound Sensors

| Parameter | MEMS microphone (SPH0645) | Condenser microphone | Sound level meter (Class 1) |
|---|---|---|---|
| Range | 35--120 dBA | 20--140 dBA | 20--140 dBA |
| Accuracy | +/-3 dB | +/-1 dB | +/-0.7 dB |
| Frequency response | 50 Hz -- 15 kHz | 20 Hz -- 20 kHz | 20 Hz -- 12.5 kHz |
| Resolution | 0.1 dB | 0.01 dB | 0.1 dB |
| Weighting | A-weighting (firmware) | Configurable | A, C, Z weighting |
| AEC application | Noise monitoring, IoT | Acoustic measurement | Compliance measurement |
| Cost per unit | $2--10 | $50--500 | $500--3,000 |

---

## 2. BMS Integration Architecture

### 2.1 Typical BMS System Architecture

```
[Field Level]
    Sensors (temperature, humidity, CO2, occupancy)
    Actuators (dampers, valves, VFDs, relays)
        |
        v  (Hardwired: 4-20mA, 0-10V, digital contact, RS-485)
        |
[Controller Level]
    DDC Controllers (Siemens PXC, Honeywell Spyder, JCI FX)
    1 controller per AHU / floor / zone (5-50 points each)
        |
        v  (BACnet IP, BACnet MS/TP, LonWorks, Modbus TCP)
        |
[Automation Level]
    Supervisory Controller / BMS Server
    Siemens Desigo CC, Honeywell EBI, JCI Metasys, Schneider EcoStruxure
    Central alarm management, scheduling, trending, graphics
        |
        v  (REST API, OPC-UA, BACnet/WS, MQTT, SQL database)
        |
[Enterprise Level]
    Building analytics platforms, energy management, digital twin
    Cloud dashboards, AI/ML analytics, fault detection
```

### 2.2 Point Naming Convention

A consistent naming convention is critical for building analytics. Common structure:

```
[Building].[System].[Equipment].[Point Type].[Descriptor]

Examples:
HQ.AHU.AHU01.AI.SupplyAirTemp
HQ.AHU.AHU01.AO.SupplyFanSpeed
HQ.AHU.AHU01.BI.FilterDPSwitch
HQ.CHW.CH01.AI.ChilledWaterSupplyTemp
HQ.RM.FL03.Z05.AI.ZoneTemp
HQ.RM.FL03.Z05.BI.OccupancyStatus
```

Point type codes:
- AI = Analog Input (sensor reading)
- AO = Analog Output (control signal)
- BI = Binary Input (switch/status)
- BO = Binary Output (on/off command)
- AV = Analog Value (setpoint, calculated value)
- BV = Binary Value (mode, schedule status)

### 2.3 Data Extraction Methods

| Method | Protocol | Real-time | Historical | Complexity | Vendor lock-in |
|---|---|---|---|---|---|
| BACnet polling | BACnet/IP | Yes (1s) | No (poll + store) | Medium | None |
| OPC-UA | OPC-UA | Yes (100ms) | Via historian | Medium--High | Low |
| REST API | HTTP/JSON | Varies (1--60s) | Yes (if API supports) | Low | Medium |
| MQTT bridge | MQTT | Yes (100ms) | No (broker + store) | Low--Medium | Low |
| SQL historian | ODBC/JDBC | No | Yes | Medium | High |
| CSV export | File-based | No | Yes | Low | None |

### 2.4 Python BACnet Access (BAC0 Library)

```python
import BAC0

# Connect to BACnet network
bacnet = BAC0.lite(ip="192.168.1.100/24")

# Read a point
supply_temp = bacnet.read("192.168.1.50 analogInput 1 presentValue")
print(f"Supply Air Temperature: {supply_temp} C")

# Read multiple points
points = [
    ("192.168.1.50", "analogInput", 1),   # Supply air temp
    ("192.168.1.50", "analogInput", 2),   # Return air temp
    ("192.168.1.50", "analogInput", 3),   # Outside air temp
    ("192.168.1.50", "analogOutput", 1),  # Cooling valve
]

for addr, obj_type, instance in points:
    value = bacnet.read(f"{addr} {obj_type} {instance} presentValue")
    name = bacnet.read(f"{addr} {obj_type} {instance} objectName")
    print(f"{name}: {value}")

# Discover devices on network
devices = bacnet.whois()
print(f"Found {len(devices)} BACnet devices")
```

---

## 3. Data Pipeline Architecture

### 3.1 Pipeline Stages

```
[Acquisition]
    |-- BACnet polling (BAC0, BACpypes)
    |-- MQTT subscription (paho-mqtt)
    |-- REST API polling (requests, scheduled)
    |-- File ingestion (CSV, XML from BMS exports)
    |
    v
[Ingestion / Streaming]
    |-- Message broker (MQTT Mosquitto, Apache Kafka, RabbitMQ)
    |-- Stream processing (Apache Flink, Kafka Streams)
    |-- For small scale: direct database insert
    |
    v
[Processing]
    |-- Data validation (range check, type check, null check)
    |-- Unit conversion (F to C, cfm to L/s)
    |-- Outlier detection (z-score, IQR, Isolation Forest)
    |-- Missing data handling (forward-fill, interpolation, flagging)
    |-- Derived calculations (degree-days, moving averages, efficiency)
    |
    v
[Storage]
    |-- Time-series DB (InfluxDB, TimescaleDB, QuestDB)
    |-- Relational DB (PostgreSQL for metadata, asset registry)
    |-- Object storage (S3/Azure Blob for raw files, large datasets)
    |-- Data retention: raw = 1 year, hourly aggregates = 5 years, daily = permanent
    |
    v
[Analysis]
    |-- Statistical analysis (pandas, scipy)
    |-- Anomaly detection (scikit-learn Isolation Forest, Prophet)
    |-- Pattern recognition (clustering, seasonal decomposition)
    |-- Fault detection and diagnostics (rule-based, ML-based)
    |-- Energy analysis (degree-day regression, baseline comparison)
    |
    v
[Visualization]
    |-- Dashboards (Grafana, Plotly Dash, Streamlit)
    |-- Alerts (email, SMS, Slack, PagerDuty)
    |-- Reports (automated PDF generation)
    |-- Digital twin overlay (3D model + sensor data)
```

### 3.2 InfluxDB for Building Data

InfluxDB is purpose-built for time-series data. Key concepts:

- **Measurement**: Equivalent to a table. Example: "indoor_environment".
- **Tags**: Indexed metadata (string only). Example: building="HQ", floor="3", zone="NW", sensor_type="temperature".
- **Fields**: Actual data values (numeric, string, boolean). Example: value=22.5.
- **Timestamp**: Nanosecond-precision time. Example: 2026-03-23T10:30:00Z.

Schema design for building sensors:
```
Measurement: environment
Tags: building, floor, zone, sensor_id, variable
Fields: value (float)
Timestamp: automatic

Example data point:
environment,building=HQ,floor=3,zone=NW,sensor_id=T301,variable=temperature value=22.5 1711186200000000000
```

Query example (Flux language):
```flux
from(bucket: "building_data")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "environment")
  |> filter(fn: (r) => r.building == "HQ" and r.floor == "3")
  |> filter(fn: (r) => r.variable == "temperature")
  |> aggregateWindow(every: 1h, fn: mean)
```

### 3.3 Data Quality Checks

| Check | Method | Action on Failure |
|---|---|---|
| Range check | value > min AND value < max (per sensor type) | Flag as out-of-range, discard from analysis |
| Rate-of-change | abs(value - previous_value) < max_rate | Flag as spike, investigate sensor |
| Flatline detection | std_dev(last_N_readings) < epsilon | Flag as possible sensor failure |
| Null/NaN | is_null(value) or is_nan(value) | Forward-fill or interpolate depending on variable type |
| Timestamp integrity | timestamp is monotonically increasing, no gaps > expected interval * 2 | Fill missing timestamps with NaN, flag gap |
| Cross-validation | compare redundant sensors (e.g., supply air temp in duct and at diffuser) | Alert if discrepancy > threshold |

---

## 4. Time-Series Analysis Methods

### 4.1 Descriptive Statistics

For each sensor, compute rolling and aggregate statistics:

| Statistic | Use in AEC | Typical Window |
|---|---|---|
| Mean | Average condition | Hourly, daily, monthly |
| Median | Robust central tendency (less affected by outliers) | Daily, monthly |
| Min / Max | Extreme conditions, system sizing | Daily, annual |
| 5th / 95th percentile | Design conditions excluding extremes | Annual |
| Standard deviation | Variability, control quality | Hourly, daily |
| Count of threshold exceedances | Compliance checking (e.g., hours > 26C) | Monthly, annual |
| Degree-hours | Overheating/undercooling severity | Monthly, annual |

### 4.2 Seasonal Decomposition

Decompose time-series into trend, seasonal, and residual components:

```
Y(t) = Trend(t) + Seasonal(t) + Residual(t)
```

Methods:
- **Classical decomposition**: Moving average for trend, average seasonal pattern, residual = observed - trend - seasonal.
- **STL (Seasonal and Trend decomposition using Loess)**: More robust, handles changing seasonality. Use `statsmodels.tsa.seasonal.seasonal_decompose` or `STL` in Python.
- **Prophet (Facebook/Meta)**: Automatic decomposition with holiday effects, changepoint detection. Excellent for building energy data with occupancy patterns.

### 4.3 Anomaly Detection

| Method | Type | Strengths | Weaknesses | Implementation |
|---|---|---|---|---|
| Z-score | Univariate, parametric | Simple, interpretable | Assumes normal distribution | `scipy.stats.zscore` |
| IQR (interquartile range) | Univariate, non-parametric | Robust to non-normal data | Misses subtle anomalies | Manual: Q1 - 1.5*IQR, Q3 + 1.5*IQR |
| Moving average deviation | Univariate, temporal | Accounts for trends | Lag in detection | `pandas.Series.rolling` |
| Isolation Forest | Multivariate | No distribution assumption, handles high-dimensional data | Black-box, needs parameter tuning | `sklearn.ensemble.IsolationForest` |
| DBSCAN | Multivariate, density-based | Finds clusters and outliers simultaneously | Sensitive to epsilon parameter | `sklearn.cluster.DBSCAN` |
| Prophet anomaly detection | Univariate, temporal | Handles seasonality, holidays | Requires sufficient history | `prophet` library |

### 4.4 Fault Detection and Diagnostics (FDD)

Building FDD identifies equipment faults from sensor data:

**Rule-based FDD examples**:
- Simultaneous heating and cooling: if heating_valve > 10% AND cooling_valve > 10% for > 30 min, flag as simultaneous operation fault.
- Economizer not working: if outside_air_temp < return_air_temp AND outside_air_damper < 50% AND cooling_call > 50%, flag as economizer fault.
- Sensor drift: if abs(redundant_sensor_1 - redundant_sensor_2) > threshold for > 1 hour, flag as sensor drift.
- Stuck valve: if valve_command changes by > 20% but flow/temp does not respond within 5 minutes, flag as stuck valve.

**ML-based FDD**:
- Train normal operating models (regression, neural network) on fault-free periods.
- Monitor residuals (predicted vs. actual) in real-time.
- Large residuals indicate potential faults.
- Clustering of fault signatures enables automatic fault classification.

---

## 5. Dashboarding Tools

### 5.1 Grafana

- **Purpose**: Open-source dashboarding platform. Industry standard for time-series visualization.
- **Data sources**: InfluxDB (native), PostgreSQL, MySQL, Prometheus, Elasticsearch, and 100+ via plugins.
- **Features**: Real-time auto-refresh, alerting (email, Slack, PagerDuty), templating (variable dropdowns for building/floor/zone), annotation (mark events on time-series), panel types (graph, gauge, table, heatmap, stat, geomap).
- **Deployment**: Docker container, cloud-hosted (Grafana Cloud), or standalone binary.
- **Building dashboard design**:
  - Row 1: KPI summary (current temperature, humidity, CO2, occupancy as single-stat panels)
  - Row 2: 24-hour time-series (temperature, CO2 with comfort thresholds as horizontal lines)
  - Row 3: Floor plan heatmap (custom SVG or image with data-driven color overlays)
  - Row 4: Equipment status (AHU, chiller operating parameters)
  - Variables: Building dropdown, Floor dropdown, Date range picker

### 5.2 Plotly Dash (Python)

- **Purpose**: Python web framework for analytical dashboards. Full control via Python code.
- **Architecture**: Flask backend + React frontend. Callbacks link user interactions to data updates.
- **Strengths**: Publication-quality charts (Plotly.js), 3D visualization, map integration (Mapbox), custom layouts, Python ecosystem (pandas, scikit-learn, etc.) available in callbacks.
- **Use case**: Custom analytics dashboards for design teams. Embed simulation results, sensor data, and GIS layers in a single interface.

### 5.3 Streamlit (Python)

- **Purpose**: Rapid prototyping of data apps. Minimal boilerplate code.
- **Architecture**: Script-based. Top-to-bottom execution. Automatic re-run on widget interaction.
- **Strengths**: Fastest path from Python script to web app. Built-in support for charts (Altair, Plotly, Matplotlib), maps (Folium, Pydeck), dataframes, file upload/download.
- **Limitation**: Less suitable for complex multi-page dashboards with intricate interactivity.

---

## 6. Sensor Placement Strategies

### 6.1 General Principles

- **Representative location**: Sensor should measure conditions experienced by occupants, not local anomalies (e.g., not directly under a supply air diffuser, not on an exterior wall).
- **Avoid direct solar radiation**: Shield temperature and humidity sensors from direct sunlight (use radiation shields outdoors, avoid south-facing wall locations indoors).
- **Breathing zone**: CO2 sensors at 1.0--1.5 m height (seated to standing breathing zone).
- **Desk height**: Light sensors at 0.76 m (desktop height) for task illumination measurement.
- **Sufficient density**: Minimum one multi-sensor per 50--100 m2 for meaningful spatial resolution. Higher density in zones with expected variability (perimeter vs. core).
- **Accessibility**: Mount sensors where they can be maintained (calibrated, replaced) without major disruption. Avoid above-ceiling mounting for sensors that require periodic calibration.

### 6.2 Placement by Sensor Type

| Sensor | Location | Height | Spacing | Avoid |
|---|---|---|---|---|
| Temperature | Interior wall, column | 1.2--1.5 m | 1 per zone (50--100 m2) | Direct sun, near windows, HVAC diffusers, heat sources |
| Humidity | Paired with temperature | 1.2--1.5 m | 1 per zone | Kitchen, bathroom (unless monitoring those spaces) |
| CO2 | Room center preferred | 1.0--1.5 m | 1 per enclosed room | Near operable windows, near doors, near supply diffusers |
| Light | Desktop or ceiling-mounted with cosine corrector | 0.76 m (desk) or ceiling | 1 per daylight zone + 1 per lighting zone | Direct sun beam (unless measuring it intentionally) |
| Occupancy PIR | Ceiling corner (wide view) | Ceiling (2.4--4 m) | 1 per room or 1 per 30 m2 | Near HVAC diffusers (air movement triggers false detections) |
| Noise | Wall-mounted | 1.2--1.5 m | 1 per acoustic zone | Near HVAC equipment (unless measuring that) |
| PM2.5 | Interior wall | 1.0--1.5 m | 1 per floor or zone | Near copiers, printers, kitchens (source monitoring is different from ambient monitoring) |

---

## 7. Digital Twin Sensor Integration

### 7.1 Architecture

```
[Physical Building]
    |
    [Sensor Network]          [BIM Model]
    |                         |
    [IoT Gateway]             [IFC/Revit Export]
    |                         |
    [Data Platform]           [3D Viewer Platform]
    (InfluxDB/Azure IoT)      (Unity/Unreal/Three.js/Forge)
    |                         |
    [API Layer]               [Model Loader]
    |                         |
    +--------> [Digital Twin Application] <--------+
                     |
               [Visualization]
               - Color-coded rooms by temperature
               - CO2 level indicators
               - Occupancy count overlays
               - Energy flow Sankey
               - Alert/alarm markers
               - Historical playback
```

### 7.2 Spatial Mapping: Sensor to 3D Model

The critical linkage: each sensor must be associated with a spatial entity in the 3D model.

**Mapping approaches**:
- **Room ID matching**: Sensor metadata includes room number. BIM model rooms have matching IDs. Query sensor data by room ID, apply to corresponding 3D room geometry.
- **Coordinate-based**: Sensor has x,y,z installation coordinates. Map to nearest room centroid or use point-in-polygon test against room boundaries.
- **Asset tagging**: Sensor is tagged to an equipment asset (e.g., AHU-01). Equipment asset is placed in the BIM model. Link via asset ID.

**Implementation in Three.js** (web-based digital twin):
1. Export BIM model to glTF format (via Revit IFC export, then IFC-to-glTF conversion).
2. Load glTF in Three.js scene.
3. Traverse model tree to find room/space objects by name or userData properties.
4. For each room, query sensor API for latest values.
5. Apply color to room mesh material based on value and color scale.
6. Add tooltip on hover showing sensor name, value, units, timestamp.
7. Refresh data on interval (e.g., every 60 seconds).

### 7.3 Use Cases for Digital Twin in AEC

| Use Case | Data Required | Visualization | Benefit |
|---|---|---|---|
| Comfort monitoring | Temperature, humidity, CO2 | Room color by comfort category | Identify complaint hotspots |
| Energy tracking | Sub-metering, weather | Dashboard + 3D overlay | Identify waste, benchmark |
| Space utilization | Occupancy sensors | Heatmap on floor plan | Right-size spaces, justify renovations |
| Maintenance planning | Equipment runtime, fault codes | Equipment status icons | Predictive maintenance, reduced downtime |
| Emergency response | Fire/smoke sensors, access control | Real-time floor plan | Occupant location, evacuation routing |
| Design validation | All sensors vs. design predictions | Side-by-side comparison | Calibrate future design assumptions |

---

## 8. Case Studies

### 8.1 Case Study: University Library Post-Occupancy Evaluation

**Context**: 5,000 m2 university library, 3 floors, completed 2 years prior. Complaints about temperature and air quality on upper floor.

**Sensor deployment**:
- 24 multi-sensors (temperature + humidity + CO2 + light) installed: 8 per floor.
- 6 desk occupancy sensors per floor (ultrasonic, under-desk).
- 1 outdoor weather station.
- Data logging to InfluxDB via MQTT (WiFi-connected sensors with ESP32 microcontrollers).
- 3-month monitoring period (September--November).

**Findings**:
- Upper floor CO2 regularly exceeded 1,500 ppm during afternoon peak occupancy (2--5 PM). Design ventilation rate assumed 50% occupancy; actual peak was 85%.
- Upper floor temperature reached 27C during afternoon due to solar gain from south-facing curtain wall + high occupancy + inadequate ventilation.
- Ground floor was consistently under-occupied (35% average utilization) and overcooled.

**Design implications**:
- Increased ventilation capacity to upper floor AHU (VAV terminal reheat boxes upsized).
- Added automated exterior shading to south curtain wall.
- Recommended converting part of ground floor to group study/collaboration (currently quiet study with low demand).
- Updated occupancy schedules in energy model for future library projects.

### 8.2 Case Study: Smart Office Pilot

**Context**: 2,000 m2 open-plan office, 200 desks. Hot-desking policy. Management wanted utilization data to right-size post-COVID.

**Sensor deployment**:
- 200 under-desk PIR sensors (desk-level binary occupancy, 1-minute polling).
- 8 meeting room people-counting cameras (AI-based counting, anonymized, no video storage).
- 4 zone CO2 sensors for ventilation adequacy.
- Data pipeline: sensors -> MQTT broker -> Node-RED -> InfluxDB -> Grafana dashboard.

**Findings over 6 months**:
- Average desk utilization: 42%. Peak day: 68%. Tuesdays and Wednesdays highest; Fridays lowest (28%).
- Meeting rooms: 4-person rooms used at 85% capacity. 12-person boardroom used at 25% capacity, usually by 2--4 people.
- CO2 never exceeded 1,000 ppm, indicating over-ventilation relative to actual occupancy.

**Design implications**:
- Reduced desk count from 200 to 140 (30% reduction). Reclaimed space converted to collaboration areas and phone booths.
- Converted 12-person boardroom to two 6-person rooms (higher utilization expected).
- Implemented CO2-based demand-controlled ventilation: reduced fan energy by 35%.
- Estimated annual savings: $120,000 (lease reduction from space optimization) + $15,000 (energy from DCV).

### 8.3 Case Study: Residential Tower Indoor Air Quality

**Context**: 30-story residential tower, 240 apartments. Developer wanted to market "healthy homes" with IAQ monitoring as a selling point.

**Sensor deployment**:
- 240 apartment sensors (temperature, humidity, CO2, PM2.5, VOC) mounted in living rooms.
- 4 corridor sensors per floor (CO2, temperature).
- 1 rooftop weather station.
- Cloud platform (Azure IoT Hub -> Azure Time Series Insights -> Power BI dashboards).
- Resident app showing real-time and historical IAQ data for their apartment.

**Findings (first year)**:
- 15% of apartments regularly exceeded PM2.5 threshold of 25 ug/m3 during cooking. Strong correlation with apartments lacking range hoods vented to outside (recirculating hoods only).
- Winter humidity below 30% RH in 60% of apartments (low humidity due to heating without humidification).
- CO2 exceeded 1,200 ppm overnight in bedrooms (inferred from living room readings + occupancy patterns) in apartments where windows were kept closed.

**Design implications for future projects**:
- All kitchens to have externally-vented range hoods (not recirculating).
- Central humidification system or unit-level humidifiers specified for heating season.
- ERV (energy recovery ventilator) with demand-controlled ventilation in each apartment to maintain CO2 below 1,000 ppm even with windows closed.
- IAQ monitoring retained as standard specification for all future residential projects.

---

## 9. Sensor Technology Selection Guide

### 9.1 Decision Matrix

| Project Type | Essential Sensors | Optional Sensors | Platform Recommendation |
|---|---|---|---|
| POE (existing building) | Temp, RH, CO2, light, occupancy PIR | PM2.5, noise, desk occupancy | Wireless (retrofit), InfluxDB + Grafana |
| New office (WELL certification) | Temp, RH, CO2, PM2.5, light, VOC, noise | Formaldehyde, radon, water quality | BMS-integrated + supplementary IoT |
| Smart building (ongoing operations) | All of above + energy sub-metering | Thermal camera (occupancy), mmWave (presence) | Full BMS + analytics platform |
| Residential (healthy homes) | Temp, RH, CO2, PM2.5 | VOC, radon, noise | Consumer IoT (Airthings, Awair) or custom |
| Research / monitoring | High-accuracy versions of all above | Spectroradiometer, chilled mirror hygrometer, reference-grade PM | Custom data acquisition, research-grade instruments |

### 9.2 Budget Estimation

| Component | Low-end (per sensor point) | Mid-range | High-end (research grade) |
|---|---|---|---|
| Sensor hardware | $10--30 | $50--150 | $200--5,000 |
| Gateway/connectivity | $5--15 | $20--50 | $50--200 |
| Cloud/storage (annual) | $2--5 | $10--30 | $50--200 |
| Dashboard/visualization | Free (Grafana) | $10--50/month | $100--500/month |
| Installation labor | $50--100 | $100--300 | $300--1,000 |
| Calibration (annual) | $0 (auto-cal) | $20--50 | $100--500 |

Typical project: 50 sensor points for a 2,000 m2 office = $5,000--15,000 hardware + $2,000--5,000 installation + $1,000--3,000/year operations.

---

## 10. Data Governance and Security

### 10.1 Data Classification

| Data Type | Sensitivity | Retention | Access Control |
|---|---|---|---|
| Environmental (temp, RH, CO2) | Low | 5+ years aggregated, 1 year raw | Building operations team |
| Occupancy (zone-level counts) | Medium | 2 years aggregated, 6 months raw | Facilities management, space planning |
| Occupancy (individual tracking) | High | 30 days maximum | Data privacy officer approval required |
| Energy consumption | Low--Medium | 5+ years | Building operations, sustainability team |
| Equipment fault data | Medium | 3+ years | Maintenance team |

### 10.2 Security Best Practices

- Encrypt data in transit (TLS 1.2+ for all API communication, MQTT over TLS).
- Encrypt data at rest (database encryption, encrypted backups).
- Network segmentation: IoT sensors on isolated VLAN, no direct internet access.
- Firmware updates: maintain update schedule for sensor firmware to patch vulnerabilities.
- Access control: role-based access to dashboards and raw data. Audit trail for data access.
- Penetration testing: annual assessment of IoT network and data platform.
