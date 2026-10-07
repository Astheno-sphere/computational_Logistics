# Energy Modeling Reference for Building Performance Simulation

This document provides a comprehensive technical reference for building energy
simulation, covering EnergyPlus methodology, construction assemblies, glazing
properties, internal loads, HVAC systems, natural ventilation, climate zones,
energy codes, and whole-life carbon assessment.

---

## 1. EnergyPlus Simulation Methodology

### Heat Balance Method

EnergyPlus uses a fundamental heat balance approach to calculate zone temperatures
and energy loads at each timestep. The method simultaneously solves:

**Outside surface heat balance:**
q_solar + q_LWR + q_conv_out - q_cond = 0

Where:
- q_solar = absorbed solar radiation on the exterior surface
- q_LWR = net longwave radiation exchange with sky, ground, and surroundings
- q_conv_out = convective heat transfer to outdoor air
- q_cond = conduction heat transfer into the construction

**Inside surface heat balance:**
q_LWR_int + q_conv_in + q_solar_int + q_SW_int - q_cond_in = 0

Where:
- q_LWR_int = net longwave radiation exchange with other room surfaces
- q_conv_in = convective heat transfer to zone air
- q_solar_int = absorbed transmitted solar radiation
- q_SW_int = absorbed shortwave radiation from internal sources (lights)
- q_cond_in = conduction heat transfer from the construction

**Zone air heat balance:**
sum(q_conv_surfaces) + q_internal_gains + q_infiltration + q_ventilation + q_HVAC = 0

The HVAC term is solved to maintain the zone air temperature within thermostat
setpoint bounds. If HVAC capacity is sufficient, the zone stays at setpoint and
q_HVAC represents the actual heating/cooling energy. If HVAC capacity is exhausted,
the zone temperature floats.

### Conduction Transfer Functions (CTF)

EnergyPlus uses CTFs to compute transient conduction through multi-layer constructions.
CTFs are pre-calculated from the material properties (conductivity, density, specific
heat, thickness) and encode the time-history response of the construction.

Benefits of CTF:
- Captures thermal mass effects (diurnal storage and release of heat).
- Accurate for steady and transient conditions.
- Computationally efficient once CTF coefficients are generated.

### Solar Distribution

EnergyPlus can distribute transmitted solar radiation using several methods:

| Method              | Description                                    | Accuracy | Speed  |
|---------------------|------------------------------------------------|----------|--------|
| MinimalShadowing    | All solar on floor, no exterior shadows        | Low      | Fast   |
| FullExterior        | Exterior shadows calculated, solar on floor    | Medium   | Medium |
| FullInteriorAndExterior| Full ray-tracing of solar patches on surfaces| High     | Slow   |
| FullExteriorWithReflections| Includes beam reflections from context  | High     | Slow   |

For energy modeling, FullExterior is typically sufficient. FullInteriorAndExterior
is recommended for spaces with significant solar gain on thermal mass.

### Timestep Considerations

- Default: 6 timesteps per hour (10-minute intervals).
- Increasing to 12 or 20 may improve accuracy for buildings with fast thermal response.
- Weather data is interpolated from hourly EPW to the simulation timestep.
- HVAC system simulation can use a different (finer) timestep than zone simulation.
- Annual simulation: 8,760 hours * 6 timesteps = 52,560 calculation points.

---

## 2. Construction Assemblies

### Wall Constructions — U-Values by Climate Zone

| Construction type                  | Layers (outside to inside)                         | U-value (W/m²K) | R-value (m²K/W) | Climate zone applicability |
|------------------------------------|---------------------------------------------------|------------------|------------------|---------------------------|
| Brick cavity (uninsulated)         | 100mm brick, 50mm air, 100mm block, 13mm plaster  | 1.50             | 0.67             | Not compliant anywhere     |
| Brick cavity (partial fill)        | 100mm brick, 50mm PUR, 50mm air, 100mm block, 13mm plaster | 0.45     | 2.22             | Zones 1–3 (hot climates)  |
| Brick cavity (full fill 100mm)     | 100mm brick, 100mm mineral wool, 100mm block, 13mm plaster | 0.28     | 3.57             | Zones 3–5 (mixed)         |
| Brick cavity (full fill 150mm)     | 100mm brick, 150mm PUR, 100mm block, 13mm plaster | 0.15             | 6.67             | Zones 5–8 (cold)          |
| External insulation (EIFS)         | Render, 120mm EPS, 200mm concrete, 13mm plaster   | 0.25             | 4.00             | Zones 4–6                 |
| External insulation (high perf.)   | Render, 200mm mineral wool, 200mm concrete, plaster| 0.15            | 6.67             | Zones 6–8                 |
| Timber frame (standard)           | Cladding, membrane, 140mm mineral wool, OSB, plaster| 0.25            | 4.00             | Zones 4–6                 |
| Timber frame (high perf.)         | Cladding, membrane, 200mm cellulose, OSB, plaster | 0.17             | 5.88             | Zones 6–8                 |
| SIP panel (165mm)                 | OSB, 140mm PUR, OSB                               | 0.16             | 6.25             | Zones 5–8                 |
| Passive House wall                | Cladding, 300mm mineral wool, concrete, plaster   | 0.10–0.12        | 8.33–10.0        | All zones (Passive House) |
| Curtain wall (insulated spandrel) | Metal panel, 100mm mineral wool, air gap, GWB     | 0.35             | 2.86             | Zones 2–5                 |
| CLT wall (with external insulation)| Cladding, 150mm mineral wool, 100mm CLT, plaster | 0.18             | 5.56             | Zones 5–7                 |

### Roof Constructions

| Construction type               | U-value (W/m²K) | Notes                              |
|--------------------------------|------------------|-------------------------------------|
| Flat roof — 100mm insulation    | 0.25             | Membrane, insulation, deck, ceiling |
| Flat roof — 200mm insulation    | 0.13             | High-performance standard           |
| Flat roof — 300mm insulation    | 0.09             | Passive House level                 |
| Green roof — extensive (150mm)  | 0.22             | Substrate provides minimal insulation|
| Green roof — intensive (300mm)  | 0.18             | Deeper soil provides moderate insulation|
| Pitched roof — between rafters  | 0.20             | 150mm mineral wool between 200mm rafters|
| Pitched roof — over rafters     | 0.13             | Continuous insulation, no thermal bridging|
| Metal deck (commercial)         | 0.22             | Standing seam, rigid insulation, vapor barrier|

### Floor Constructions

| Construction type                  | U-value (W/m²K) | Notes                            |
|-----------------------------------|------------------|-----------------------------------|
| Slab-on-grade (uninsulated)       | 0.60–0.80        | Depends on perimeter/area ratio  |
| Slab-on-grade (50mm perimeter ins.)| 0.25–0.35       | Insulation at slab edge          |
| Slab-on-grade (full under-slab)   | 0.15–0.20        | 100mm XPS under entire slab      |
| Suspended timber floor            | 0.20             | 150mm mineral wool between joists|
| Concrete slab over parking        | 0.25             | 100mm insulation below slab      |
| Raised access floor (commercial)  | N/A              | Thermal resistance from floor void|

### Thermal Bridging

Linear thermal bridges (psi-values) add significantly to heat loss:

| Junction type                   | Typical psi-value (W/mK) | Well-detailed psi (W/mK) |
|---------------------------------|--------------------------|--------------------------|
| Wall-floor (ground)             | 0.16                     | 0.04                     |
| Wall-floor (intermediate)       | 0.07                     | 0.01                     |
| Wall-roof (flat)                | 0.12                     | 0.04                     |
| Wall-roof (pitched)             | 0.08                     | 0.02                     |
| Window sill                     | 0.04                     | 0.01                     |
| Window jamb                     | 0.05                     | 0.02                     |
| Window head                     | 0.05                     | 0.02                     |
| Corner (external)               | 0.09                     | 0.02                     |
| Balcony slab penetration        | 0.90                     | 0.10 (thermal break)     |
| Steel column through insulation | 0.50                     | 0.15 (thermal break)     |

Thermal bridging can increase overall heat loss by 10–30% compared to clear-field
U-value alone. Always include thermal bridge corrections in energy models.

---

## 3. Glazing Properties

### Common Glazing Types — Detailed Properties

| Glazing type                     | U-value (W/m²K) | SHGC  | VLT (Tvis) | SC    | Notes                    |
|---------------------------------|------------------|-------|------------|-------|--------------------------|
| Single clear 6mm                | 5.8              | 0.82  | 0.88       | 0.95  | Heritage, not for new    |
| Double clear 6/12/6 air         | 2.8              | 0.70  | 0.78       | 0.81  | Baseline double glazing  |
| Double clear 6/12/6 argon       | 2.5              | 0.70  | 0.78       | 0.81  | Argon reduces U-value    |
| Double low-e (hard coat) argon  | 1.8              | 0.55  | 0.72       | 0.64  | Good balance cost/perf.  |
| Double low-e (soft coat) argon  | 1.4              | 0.40  | 0.65       | 0.46  | High performance         |
| Double low-e (solar control)    | 1.4              | 0.28  | 0.50       | 0.32  | Cooling-dominated climate|
| Triple clear argon              | 1.0              | 0.55  | 0.68       | 0.64  | Cold climates            |
| Triple low-e argon              | 0.8              | 0.35  | 0.55       | 0.40  | Cold, high-performance   |
| Triple low-e krypton            | 0.6              | 0.30  | 0.52       | 0.35  | Passive House standard   |
| Vacuum insulated                | 0.5              | 0.35  | 0.60       | 0.40  | Emerging technology      |
| Double tinted bronze            | 2.7              | 0.45  | 0.42       | 0.52  | Solar control, low VLT   |
| Double tinted grey              | 2.7              | 0.40  | 0.38       | 0.46  | Solar control, low VLT   |
| Double reflective silver        | 1.6              | 0.18  | 0.15       | 0.21  | Aggressive solar control |
| Electrochromic (clear state)    | 1.4              | 0.45  | 0.60       | 0.52  | Dynamic, controllable    |
| Electrochromic (tinted state)   | 1.4              | 0.09  | 0.05       | 0.10  | Can block almost all solar|
| Thermochromic                   | 1.8              | 0.15–0.50| 0.20–0.60| Varies| Self-tinting at high temp|

SC = Shading Coefficient = SHGC / 0.87

**Key relationships:**
- Higher SHGC admits more solar heat — beneficial in heating climates, detrimental in cooling climates.
- Higher VLT admits more daylight — always desirable up to the glare threshold.
- The ratio VLT/SHGC (Light-to-Solar Gain ratio, LSG) indicates selectivity:
  LSG > 1.25 is considered "spectrally selective" glazing. Higher LSG means more
  daylight per unit of solar heat gain.

### Glazing Selection by Climate

| Climate zone (ASHRAE) | Heating degree days | Recommended U-value | Recommended SHGC | Strategy               |
|------------------------|--------------------|--------------------|-------------------|------------------------|
| 1 (Very hot)           | < 500              | <= 3.0             | <= 0.25           | Minimize solar gain    |
| 2 (Hot)                | 500–2000           | <= 2.5             | <= 0.25           | Minimize solar gain    |
| 3 (Warm)               | 2000–3000          | <= 2.0             | 0.25–0.40         | Balance solar/daylight |
| 4 (Mixed)              | 3000–4000          | <= 1.8             | 0.25–0.40         | Balance heating/cooling|
| 5 (Cool)               | 4000–5000          | <= 1.4             | 0.30–0.45         | Moderate solar admitted|
| 6 (Cold)               | 5000–7000          | <= 1.1             | 0.35–0.50         | Maximize solar gain    |
| 7 (Very cold)          | 7000–9000          | <= 0.8             | 0.40–0.55         | Maximize solar gain    |
| 8 (Subarctic)          | > 9000             | <= 0.6             | 0.45–0.60         | Maximize solar gain    |

---

## 4. Internal Loads

### People — Sensible and Latent Heat Gains

| Activity level         | Metabolic rate (Met) | Total heat (W/person) | Sensible (W) | Latent (W) |
|------------------------|---------------------|-----------------------|---------------|------------|
| Seated, relaxed        | 1.0                 | 100                   | 60            | 40         |
| Seated, light work     | 1.1                 | 120                   | 65            | 55         |
| Standing, light work   | 1.2                 | 130                   | 70            | 60         |
| Walking (3.2 km/h)     | 2.0                 | 200                   | 100           | 100        |
| Office work            | 1.1                 | 120                   | 65            | 55         |
| Teaching               | 1.3                 | 140                   | 75            | 65         |
| Light manufacturing    | 2.0                 | 220                   | 100           | 120        |
| Heavy exercise         | 4.0                 | 430                   | 170           | 260        |
| Cooking                | 1.8                 | 190                   | 90            | 100        |
| Housekeeping           | 2.0                 | 200                   | 100           | 100        |

Occupant density by space type:

| Space type            | Area per person (m²/person) | People density (people/m²) |
|-----------------------|-----------------------------|---------------------------|
| Open office           | 10–14                       | 0.07–0.10                 |
| Private office        | 15–25                       | 0.04–0.07                 |
| Conference room       | 2–4                         | 0.25–0.50                 |
| Classroom             | 2–4                         | 0.25–0.50                 |
| Lecture hall          | 0.7–1.5                     | 0.67–1.43                 |
| Retail (general)      | 5–10                        | 0.10–0.20                 |
| Restaurant            | 1.5–3.0                     | 0.33–0.67                 |
| Hotel room            | 15–30                       | 0.03–0.07                 |
| Hospital ward         | 8–12                        | 0.08–0.13                 |
| Gym / fitness         | 5–10                        | 0.10–0.20                 |
| Lobby                 | 3–10                        | 0.10–0.33                 |

### Lighting Power Density

| Space type              | Code minimum (W/m²) | Good practice (W/m²) | Best practice (W/m²) | Technology          |
|-------------------------|---------------------|-----------------------|----------------------|---------------------|
| Open office             | 9.0                 | 6.0                   | 3.5                  | LED + daylight dim. |
| Private office          | 10.0                | 7.0                   | 4.0                  | LED + occupancy     |
| Conference room         | 11.0                | 7.5                   | 4.5                  | LED + dimming       |
| Classroom               | 10.0                | 7.0                   | 4.0                  | LED + daylight dim. |
| Retail (general)        | 13.0                | 9.0                   | 6.0                  | LED task + ambient  |
| Retail (highlight)      | 16.0                | 12.0                  | 8.0                  | LED accent + track  |
| Hospital (ward)         | 7.0                 | 5.0                   | 3.5                  | LED + bed control   |
| Hospital (examination)  | 15.0                | 10.0                  | 7.0                  | LED + task lights   |
| Corridor                | 5.0                 | 3.0                   | 1.5                  | LED + occupancy     |
| Parking (indoor)        | 2.5                 | 1.5                   | 0.8                  | LED + occupancy     |
| Warehouse               | 6.0                 | 4.0                   | 2.0                  | LED high-bay + zones|

### Equipment Power Density

| Space type              | Typical (W/m²) | Range (W/m²) | Notes                           |
|-------------------------|----------------|--------------|----------------------------------|
| Open office             | 11.0           | 8–15         | Monitors, computers, peripherals|
| Private office          | 12.0           | 8–18         | Higher if personal printers     |
| Conference room         | 5.0            | 3–10         | AV equipment, display           |
| Server room             | 400–1000+      | Varies       | Must be modeled explicitly      |
| Classroom               | 5.0            | 3–10         | Computers + projector           |
| Computer lab            | 25.0           | 15–40        | Desktops at every seat          |
| Retail                  | 5.0            | 3–10         | POS, display lighting           |
| Restaurant kitchen      | 50.0           | 30–100       | Commercial cooking equipment    |
| Hotel room              | 5.0            | 3–8          | TV, minibar, chargers           |
| Hospital (general)      | 10.0           | 5–20         | Medical devices vary widely     |
| Laboratory              | 30.0           | 15–100       | Depends on equipment type       |
| Residential             | 3.0            | 2–5          | Appliances, electronics         |

---

## 5. Occupancy Schedules

### Standard Office Schedule (ASHRAE 90.1 Appendix C)

| Hour  | Mon-Fri occupancy | Lighting | Equipment | Heating setpoint | Cooling setpoint |
|-------|-------------------|----------|-----------|------------------|------------------|
| 00–06 | 0.00              | 0.05     | 0.20      | 15.6°C (60°F)    | 30.0°C (86°F)   |
| 06–07 | 0.10              | 0.30     | 0.40      | 21.0°C (70°F)    | 24.0°C (75°F)   |
| 07–08 | 0.20              | 0.60     | 0.60      | 21.0°C           | 24.0°C           |
| 08–12 | 0.95              | 0.90     | 0.90      | 21.0°C           | 24.0°C           |
| 12–13 | 0.50              | 0.90     | 0.80      | 21.0°C           | 24.0°C           |
| 13–17 | 0.95              | 0.90     | 0.90      | 21.0°C           | 24.0°C           |
| 17–18 | 0.50              | 0.70     | 0.60      | 21.0°C           | 24.0°C           |
| 18–20 | 0.20              | 0.40     | 0.40      | 15.6°C           | 30.0°C           |
| 20–24 | 0.05              | 0.10     | 0.20      | 15.6°C           | 30.0°C           |

Saturday: 50% of weekday occupancy, 06–18 only.
Sunday / Holiday: 10% of weekday occupancy, minimal lighting and equipment.

### Residential Schedule (Typical)

| Hour  | Weekday occupancy | Weekend occupancy | Notes                      |
|-------|-------------------|-------------------|----------------------------|
| 00–07 | 1.00              | 1.00              | Sleeping                   |
| 07–08 | 0.75              | 1.00              | Waking, morning routine    |
| 08–09 | 0.25              | 0.90              | Leaving for work           |
| 09–17 | 0.10              | 0.50              | Away at work vs. at home   |
| 17–18 | 0.25              | 0.60              | Returning from work        |
| 18–22 | 0.80              | 0.90              | Evening at home            |
| 22–24 | 0.90              | 0.90              | Winding down, sleeping     |

---

## 6. HVAC System Types

### System Classification

| System type                    | Heating source       | Cooling source    | Distribution    | Efficiency (COP/AFUE) | Common application    |
|-------------------------------|---------------------|-------------------|-----------------|------------------------|-----------------------|
| Split DX + gas furnace        | Gas furnace          | DX compressor     | Forced air      | COP 3.5 / AFUE 0.92   | Residential           |
| Packaged rooftop unit (RTU)   | Gas or electric      | DX compressor     | Forced air      | COP 3.0–4.0            | Small commercial      |
| VAV with reheat               | Boiler (hot water)   | Chiller (chilled water)| Ductwork + VAV boxes| Chiller COP 5.0–6.5| Large office, lab     |
| Fan coil units (FCU)          | Boiler or heat pump  | Chiller           | Piped water     | Chiller COP 5.0–6.5   | Hotel, residential    |
| Chilled beams (active)        | Boiler or heat pump  | Chiller           | Water + DOAS    | Chiller COP 6.0        | Office, lab           |
| VRF (Variable Refrigerant Flow)| Heat pump           | Heat pump         | Refrigerant pipe| COP 4.0–6.0           | Multi-zone commercial |
| GSHP (Ground Source Heat Pump)| Ground loop          | Ground loop       | Water/air       | COP 4.5–6.0           | Any, where feasible   |
| ASHP (Air Source Heat Pump)   | Outdoor air          | Outdoor air       | Air or water    | COP 3.0–5.0           | Residential, small comm.|
| District heating/cooling      | Central plant        | Central plant     | Piped water     | Varies                 | Campus, urban district|
| Radiant floor/ceiling         | Boiler or heat pump  | Chiller           | Embedded pipes  | High (low temp. diff.) | Office, residential   |
| DOAS (Dedicated Outdoor Air) | Heat pump / ERV      | Heat pump / ERV   | Separate duct   | ERV effectiveness 75%+ | Pairs with any local  |
| Natural ventilation only      | Passive solar        | Ventilation cooling| Windows         | COP = infinity (no energy)| Mild climates      |

### HVAC System Efficiency Metrics

| Metric | Full name                              | Typical range | Notes                    |
|--------|----------------------------------------|---------------|--------------------------|
| COP    | Coefficient of Performance             | 3.0–6.5       | Cooling output / electric input |
| EER    | Energy Efficiency Ratio                | 10–20         | BTU/h per watt (COP * 3.412)|
| SEER   | Seasonal EER                           | 14–25         | Annual average efficiency |
| AFUE   | Annual Fuel Utilization Efficiency     | 0.80–0.98     | Gas heating efficiency   |
| HSPF   | Heating Seasonal Performance Factor    | 8–13          | Heat pump heating efficiency|
| IPLV   | Integrated Part-Load Value             | 5–10          | Chiller efficiency at part-load|

---

## 7. Natural Ventilation Modeling

### Ventilation Modes

**Single-sided ventilation:**
- One opening (window) on one wall.
- Driven by buoyancy (stack effect) and turbulent fluctuations.
- Effective depth: approximately 2.5 times floor-to-ceiling height.
- Flow rate: Q ≈ 0.025 * A * v_wind (wind-driven) or Q ≈ Cd * A/3 * sqrt(g * H * dT/T) (buoyancy).

**Cross ventilation:**
- Openings on two opposite (or nearly opposite) walls.
- Driven primarily by wind pressure difference.
- Effective depth: up to 5 times floor-to-ceiling height.
- Flow rate: Q = Cd * A_eff * v_wind * sqrt(delta_Cp).
- Where A_eff = (A1 * A2) / sqrt(A1² + A2²), delta_Cp = Cp_windward - Cp_leeward.

**Stack ventilation:**
- Warm air rises through a tall space (atrium, chimney, stairwell).
- Driven by temperature difference between indoor and outdoor air.
- Flow rate: Q = Cd * A * sqrt(2 * g * H * (Ti - To) / Ti).
- Where H = height difference between inlet and outlet, g = 9.81 m/s².
- Effective in calm conditions when wind-driven ventilation is weak.

### EnergyPlus Natural Ventilation Methods

**Scheduled ventilation (ZoneVentilation:DesignFlowRate):**
- Specifies a fixed or scheduled ventilation rate (ACH or m³/s).
- Wind and stack coefficients modify the rate based on conditions.
- Simple to set up but does not capture airflow physics accurately.

**Airflow Network (AirflowNetwork):**
- Models openings, cracks, ducts, and fans as a network of flow paths.
- Solves pressure-flow relationships at each timestep.
- Accounts for wind pressure, stack effect, and mechanical fan interactions.
- Most accurate for complex multi-zone natural ventilation.
- Requires Cp values for each facade (from CFD or published data).

### Pressure Coefficient (Cp) Reference Values

| Facade orientation | Isolated building Cp | Sheltered (urban) Cp | Notes          |
|-------------------|---------------------|---------------------|----------------|
| Windward           | +0.6 to +0.8        | +0.3 to +0.5        | Positive pressure |
| Leeward            | -0.3 to -0.5        | -0.2 to -0.3        | Negative pressure |
| Side walls          | -0.5 to -0.8        | -0.3 to -0.5        | Varies with angle |
| Roof (flat)         | -0.5 to -1.2        | -0.4 to -0.8        | Strong suction    |

Delta_Cp (windward - leeward) for cross ventilation:
- Isolated building: 0.9–1.3
- Urban (sheltered): 0.5–0.8
- Dense urban: 0.3–0.5

---

## 8. ASHRAE Climate Zones

### Zone Definitions

| Zone | Type        | HDD18 (°C-days) | CDD10 (°C-days) | Representative cities                |
|------|------------|------------------|------------------|--------------------------------------|
| 1A   | Very hot humid| < 500           | > 5000           | Miami, Singapore, Mumbai             |
| 1B   | Very hot dry  | < 500           | > 5000           | Riyadh (borderline)                  |
| 2A   | Hot humid     | 500–2000         | 3500–5000        | Houston, Cairo, Brisbane             |
| 2B   | Hot dry       | 500–2000         | 3500–5000        | Phoenix, Abu Dhabi                   |
| 3A   | Warm humid    | 2000–3000        | 2500–3500        | Atlanta, Sydney, Shanghai            |
| 3B   | Warm dry      | 2000–3000        | 2500–3500        | Los Angeles, Casablanca              |
| 3C   | Warm marine   | 2000–3000        | < 2500           | San Francisco, Lisbon                |
| 4A   | Mixed humid   | 3000–4000        | 1500–2500        | New York, Seoul, Milan               |
| 4B   | Mixed dry     | 3000–4000        | 1500–2500        | Albuquerque                          |
| 4C   | Mixed marine  | 3000–4000        | < 1500           | Seattle, London, Paris               |
| 5A   | Cool humid    | 4000–5000        | 500–1500         | Chicago, Berlin, Beijing             |
| 5B   | Cool dry      | 4000–5000        | 500–1500         | Denver, Salt Lake City               |
| 5C   | Cool marine   | 4000–5000        | < 500            | Vancouver                            |
| 6A   | Cold humid    | 5000–7000        | < 500            | Minneapolis, Moscow, Montreal        |
| 6B   | Cold dry      | 5000–7000        | < 500            | Helena, Boise                        |
| 7    | Very cold     | 7000–9000        | < 500            | Anchorage, Tromsoe, Ulaanbaatar      |
| 8    | Subarctic     | > 9000           | < 500            | Fairbanks, Yakutsk                   |

### Envelope Requirements by Climate Zone (ASHRAE 90.1-2022 Reference)

| Component          | Zone 1  | Zone 3  | Zone 5  | Zone 7  | Unit      |
|--------------------|---------|---------|---------|---------|-----------|
| Roof U-value       | 0.36    | 0.27    | 0.18    | 0.12    | W/m²K     |
| Wall U-value       | 0.70    | 0.45    | 0.32    | 0.21    | W/m²K     |
| Floor U-value      | 0.73    | 0.46    | 0.32    | 0.19    | W/m²K     |
| Glazing U-value    | 3.69    | 2.84    | 2.27    | 1.59    | W/m²K     |
| Glazing SHGC       | 0.25    | 0.25    | 0.36    | 0.45    | —         |
| Max WWR            | 40%     | 40%     | 40%     | 40%     | %         |

---

## 9. Energy Code Comparison

### Major Energy Codes Worldwide

| Code / Standard        | Jurisdiction  | Type        | Key features                            |
|------------------------|--------------|-------------|------------------------------------------|
| ASHRAE 90.1-2022       | US / International| Prescriptive + Performance| Most widely referenced globally |
| IECC 2021              | US           | Prescriptive + Performance| Residential and commercial          |
| Part L (Building Regs) | England      | Performance | Target Emission Rate + fabric limits    |
| NCC 2022 (Section J)   | Australia    | Performance | JV3 simulation path                     |
| EPBD (recast 2023)     | EU           | Performance | Nearly Zero Energy Building requirement |
| TEK 17                 | Norway       | Prescriptive| Among strictest in the world             |
| Passive House (PHI)    | International| Performance | 15 kWh/m²/yr heating/cooling demand     |
| LEED (Energy)          | International| Performance | % improvement over ASHRAE baseline       |
| BREEAM (Energy)        | UK / International| Performance| EPR reduction credits               |
| Green Star (Energy)    | Australia    | Performance | Reference building comparison           |
| NABERS (operational)   | Australia    | Operational | Actual measured energy performance       |

### Passive House Requirements

| Criterion              | Requirement                      | Notes                          |
|------------------------|----------------------------------|--------------------------------|
| Heating demand         | <= 15 kWh/m²/yr                  | Or heating load <= 10 W/m²    |
| Cooling demand         | <= 15 kWh/m²/yr                  | Climate-dependent adjustment  |
| Primary energy (PER)   | <= 60 kWh/m²/yr (Classic)        | 45 (Plus), 30 (Premium)       |
| Airtightness           | n50 <= 0.6 ACH                   | Tested by blower door         |
| Thermal bridging       | Psi <= 0.01 W/mK at all junctions| "Thermal bridge free"        |
| Window U-value         | <= 0.80 W/m²K (installed)        | Including frame and spacer    |
| Ventilation            | MVHR with >= 75% heat recovery   | Mandatory for airtight envelope|

---

## 10. Net Zero Energy Methodology

### Definition Hierarchy

| Level                     | Definition                                           | Boundary           |
|---------------------------|-----------------------------------------------------|---------------------|
| Net Zero Site Energy      | Annual on-site generation >= annual site consumption | Building site only  |
| Net Zero Source Energy    | Primary energy balance (accounting for grid losses)  | Source/primary      |
| Net Zero Energy Cost      | Annual energy revenue >= annual energy cost          | Financial           |
| Net Zero Energy Emissions | Annual renewable generation offsets fossil emissions | Carbon              |

### Path to Net Zero

1. **Reduce demand** through passive design (insulation, orientation, shading, daylight).
   Target: 50–70% reduction from code baseline.
2. **Maximize efficiency** of active systems (LED lighting, high-COP heat pumps, ERV).
   Target: additional 20–30% reduction.
3. **Generate on-site** from renewables (rooftop PV, facade PV, wind).
   Target: generate remaining energy demand.

Typical achievable: office building at 80 kWh/m²/yr with rooftop PV generating
40–60 kWh/m²/yr (depends on roof-to-floor area ratio and climate). Multi-story
buildings with small roof area relative to floor area struggle to achieve net zero
from rooftop PV alone — facade PV, off-site renewables, or PPAs may be needed.

---

## 11. Embodied Energy and Whole-Life Carbon

### Lifecycle Stages (EN 15978)

| Stage | Code    | Description                          | Included in whole-life carbon? |
|-------|---------|--------------------------------------|-------------------------------|
| A1-A3 | Product | Raw material extraction, manufacturing| Yes (embodied carbon)        |
| A4    | Transport| Transport to site                   | Yes                           |
| A5    | Construction| On-site construction processes    | Yes                           |
| B1    | Use     | Emissions from installed products    | Yes                           |
| B2-B5 | Maintenance/Refurbishment| Replacements over 60-yr life| Yes                    |
| B6    | Operational energy| Energy use during operation    | Yes (operational carbon)     |
| B7    | Operational water| Water use during operation      | Sometimes                    |
| C1-C4 | End of life| Demolition, transport, disposal   | Yes                           |
| D     | Beyond lifecycle| Recycling, reuse benefits       | Reported separately          |

### Embodied Carbon of Common Materials

| Material                   | Embodied carbon (kgCO2e/kg) | Embodied carbon (kgCO2e/m³) | Notes                    |
|---------------------------|-----------------------------|-----------------------------|--------------------------|
| Concrete (C30/37)          | 0.10–0.15                   | 240–360                     | Cement content dependent |
| Low-carbon concrete        | 0.06–0.09                   | 140–220                     | SCM replacement, CEM III |
| Steel (structural, virgin) | 1.50–2.00                   | 12,000–16,000               | Highest per kg           |
| Steel (recycled content)   | 0.50–0.80                   | 4,000–6,300                 | EAF route, 70%+ recycled |
| Timber (softwood)          | -1.60 to -0.50              | -800 to -250                | Biogenic carbon stored   |
| CLT (Cross Laminated Timber)| -0.70 to -0.40             | -340 to -200                | Including manufacturing  |
| Aluminum                   | 8.00–12.00                  | 22,000–33,000               | Very high, use sparingly |
| Aluminum (recycled)        | 0.50–1.50                   | 1,350–4,050                 | Recycling is essential   |
| Glass (float)              | 1.20–1.50                   | 3,000–3,750                 | Facade area drives total |
| Insulation (mineral wool)  | 1.00–1.50                   | 30–100                      | Low density = low per m³ |
| Insulation (EPS)           | 3.00–4.00                   | 60–120                      | Petroleum-based          |
| Insulation (PUR/PIR)       | 3.50–5.00                   | 105–200                     | High per kg, low per m³  |
| Brick (fired clay)         | 0.20–0.30                   | 360–540                     | Kiln energy dependent    |
| Gypsum plasterboard        | 0.12–0.20                   | 80–140                      | Low embodied carbon      |
| Copper                     | 2.50–4.00                   | 22,000–36,000               | Piping, electrical       |

### Whole-Life Carbon Benchmarks

| Building type    | Total WLC (kgCO2e/m²) over 60 years | Structure | Facade | Services | Operational |
|-----------------|--------------------------------------|-----------|--------|----------|-------------|
| Office (typical) | 1800–2500                           | 400–600   | 200–350| 150–250  | 800–1200    |
| Office (low-carbon)| 1000–1400                         | 200–350   | 100–200| 100–150  | 400–600     |
| Residential      | 1200–1800                           | 300–500   | 150–250| 100–200  | 600–900     |
| Education        | 1400–2000                           | 350–550   | 150–250| 100–200  | 600–900     |

The critical insight: as operational energy decreases (through better insulation
and efficient systems), embodied carbon becomes a proportionally larger share of
whole-life carbon. For a Net Zero Energy building, embodied carbon can represent
50–70% of total lifecycle emissions. This means material selection and structural
efficiency are as important as energy efficiency for truly low-carbon buildings.
