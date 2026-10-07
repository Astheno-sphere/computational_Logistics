---
title: Environmental Simulation
description: Daylight analysis, solar radiation, energy simulation, CFD wind analysis, thermal comfort, acoustic simulation, and the Ladybug Tools ecosystem for performance-driven AEC computational design
version: 1.0.0
tags: [environmental, daylight, solar, energy, CFD, thermal-comfort, acoustic, Ladybug, Honeybee, Radiance, EnergyPlus]
auto_activate: true
user_invocable: true
invocation: /environmental-simulation
---

# Environmental Simulation for AEC Computational Design

This skill provides a comprehensive reference for environmental performance simulation
in the Architecture, Engineering, and Construction industry. It covers daylight analysis,
solar radiation studies, energy modeling, computational fluid dynamics for wind, thermal
comfort assessment, acoustic simulation, and the Ladybug Tools ecosystem that ties these
workflows together within parametric design environments.

---

## 1. Performance-Driven Design Philosophy

### Why Simulate Early

The single most consequential decision in building performance is made in the first
five percent of the design timeline. Orientation, massing, window-to-wall ratio, and
floor plate depth are locked in during concept design, yet their impact on energy
consumption, daylight quality, and occupant comfort persists for the entire operational
life of the building — typically 50 to 100 years.

Late-stage simulation is a diagnostic exercise. Early-stage simulation is a generative
tool. The distinction matters because retrofitting performance into an already-resolved
form is orders of magnitude more expensive than shaping the form around performance
from the beginning.

**Cost of late performance analysis:**

| Stage where issue discovered | Relative cost to fix |
|------------------------------|---------------------|
| Concept design               | 1x (baseline)       |
| Schematic design              | 5x                  |
| Design development            | 15x                 |
| Construction documents        | 50x                 |
| Construction                  | 150x                |
| Post-occupancy                | 500x+               |

These multipliers are well-documented across the AEC industry and reflect the reality
that changing a window-to-wall ratio on a sketch costs nothing, but changing it after
curtain wall shop drawings are issued can cost hundreds of thousands of dollars.

### Integration of Simulation into the Design Loop

Performance simulation must not live in a separate silo from the design model. The
traditional workflow — architect designs, sends model to energy consultant, waits two
weeks, receives PDF report, ignores half the recommendations because they conflict
with the architectural intent — is fundamentally broken.

The correct workflow is a tight feedback loop:

1. **Parametric model** defines geometry with variable parameters (orientation, WWR,
   floor depth, shading depth, envelope composition).
2. **Simulation engine** evaluates one or more performance metrics against that geometry.
3. **Results** feed back into the model as color-mapped surfaces, numeric dashboards,
   or fitness values for optimization.
4. **Designer** adjusts parameters or launches an automated optimization run.
5. **Repeat** at increasing fidelity as the design matures.

This loop should complete in seconds to minutes during early design and in minutes to
hours during detailed design. Any simulation that takes days to return results is, by
definition, excluded from the design loop and relegated to post-rationalization.

### Performance as a Design Driver

Performance-driven design does not mean surrendering architectural intent to a
spreadsheet. It means treating environmental performance as a first-class design
variable alongside spatial quality, structural logic, and aesthetic expression. The
best performing buildings in the world — the Bullitt Center, One Angel Court, the
Manitoba Hydro Place — are also among the most architecturally compelling because their
designers used performance constraints as creative catalysts.

Metrics that can drive design decisions:

- **Daylight autonomy** drives floor plate depth, section profile, and facade design.
- **Solar radiation** drives orientation, massing articulation, and shading strategy.
- **Energy use intensity** drives envelope specification, HVAC selection, and renewable capacity.
- **Wind comfort** drives podium design, canopy placement, and landscape strategy.
- **Thermal comfort** drives material selection, ventilation strategy, and public realm design.
- **Acoustic performance** drives room proportions, material specification, and partition layout.

### Iterative vs. Single-Pass Simulation Strategies

**Single-pass simulation** runs one analysis on a fixed design. It answers the question
"how does this design perform?" This is the minimum viable use of simulation and is
appropriate only for compliance checking at the end of a design phase.

**Iterative simulation** runs multiple analyses across a parameter space. It answers the
question "which design performs best?" This is the correct use of simulation in a
computational design workflow.

Iterative strategies include:

- **Manual parameter sweeps**: Designer changes one variable at a time and observes the
  effect on performance. Simple but slow and unable to capture multi-variable interactions.
- **Parametric studies**: Systematic variation of two or three parameters across defined
  ranges, producing a response surface that reveals optimal regions.
- **Evolutionary optimization**: Genetic algorithms (Galapagos, Wallacei) explore a
  high-dimensional parameter space, evolving toward Pareto-optimal solutions across
  multiple conflicting objectives.
- **Machine learning surrogates**: A neural network is trained on a sample of simulation
  results and then used to predict performance across the full parameter space at near
  zero computational cost. This enables real-time performance feedback during design.

---

## 2. Daylight Analysis

### Core Metrics

**Daylight Factor (DF)**
The ratio of indoor illuminance to outdoor diffuse horizontal illuminance under a CIE
overcast sky, expressed as a percentage. DF is climate-independent and therefore useful
for comparing designs but not for predicting actual illuminance.

- Minimum DF of 2% is generally required for a space to be considered "daylit."
- Average DF of 5% or more indicates strong daylight availability.
- DF does not account for direct sunlight, building orientation, or climate.

**Spatial Daylight Autonomy (sDA)**
The percentage of analysis area that achieves at least 300 lux for at least 50% of
occupied hours annually. sDA is the primary metric in LEED v4.1 and IES LM-83.

- sDA300/50% >= 55% is the LEED threshold for 2 points.
- sDA300/50% >= 75% earns 3 points.
- Based on annual simulation with climate-specific weather data.
- Accounts for orientation, context, and dynamic shading.

**Annual Sunlight Exposure (ASE)**
The percentage of analysis area that receives more than 1000 lux of direct sunlight
for more than 250 occupied hours per year. ASE measures visual discomfort risk from
excessive direct sun.

- ASE1000/250h must be <= 10% for LEED compliance.
- High ASE indicates glare risk and potential overheating.
- ASE is often in tension with sDA — maximizing daylight can increase glare risk.

**Useful Daylight Illuminance (UDI)**
The percentage of occupied hours that illuminance falls within a useful range:

| UDI category          | Illuminance range | Interpretation           |
|-----------------------|-------------------|--------------------------|
| UDI-fell-short        | < 100 lux         | Too dark, electric light needed |
| UDI-supplementary     | 100–300 lux       | Useful with supplemental light |
| UDI-autonomous        | 300–3000 lux      | Ideal daylight range     |
| UDI-exceeded          | > 3000 lux        | Too bright, glare likely |

UDI is more nuanced than sDA because it penalizes both under-lit and over-lit conditions.

**Daylight Glare Probability (DGP)**
A metric for evaluating glare from a specific viewpoint, based on luminance distribution
in the field of view.

| DGP value   | Glare perception       |
|-------------|------------------------|
| < 0.35      | Imperceptible          |
| 0.35–0.40   | Perceptible            |
| 0.40–0.45   | Disturbing             |
| > 0.45      | Intolerable            |

DGP is evaluated using Evalglare from the Radiance suite and requires a rendered
fisheye luminance image from the occupant's viewpoint.

### Standards Reference

**LEED v4.1 IEQ Credit: Daylight**
- Option 1 (Simulation): sDA300/50% >= 55% in 55% of regularly occupied area (2 pts),
  >= 75% (3 pts). ASE1000/250h <= 10%. Analysis grid at workplane height (0.76 m).
- Option 2 (Measurement): Illuminance between 300–3000 lux at 9 AM and 3 PM on equinox.

**EN 17037: Daylight in Buildings**
- Target illuminance of 300 lux for 50% of daylight hours at the worst point.
- Minimum illuminance of 100 lux for 50% of daylight hours across 95% of area.
- Recommends evaluation of view out, sunlight exposure, and glare protection.

**BREEAM Hea 01: Visual Comfort**
- Average daylight factor >= 2% or point daylight factor >= 0.8% at the worst point.
- Uniformity ratio (minimum DF / average DF) >= 0.4.
- View of sky from desk height (requirement for higher credits).

### Simulation Engines

**Radiance**
The gold standard for physically-based lighting simulation. Uses backward ray-tracing
to compute illuminance and luminance with high accuracy. All major daylight standards
reference Radiance as a validated engine.

Key Radiance parameters for annual simulation:

| Parameter   | Low quality | Medium quality | High quality |
|-------------|-------------|----------------|--------------|
| -ab (bounces)| 2          | 3              | 5            |
| -ad (divisions)| 512      | 2048           | 4096         |
| -as (super-samples)| 128  | 1024           | 2048         |
| -ar (resolution)| 64      | 128            | 256          |
| -aa (accuracy)| 0.25      | 0.15           | 0.1          |

**3-Phase Method**
Decomposes daylight transport into three matrices:
1. View matrix (V): sensor points to interior surface patches
2. Transmission matrix (T): window group behavior
3. Daylight matrix (D): sky patches to exterior window surfaces

Annual daylight = V * T * D * sky_vector. This allows rapid recalculation when only
the window system changes (swap T matrix) without recomputing V or D.

**5-Phase Method**
Adds direct solar contribution more accurately by separating the direct sun component
from the diffuse sky component and computing it with higher resolution. Essential for
accurate ASE calculations and glare analysis.

### Material Properties

Common material reflectances for Radiance modeling:

| Material                | Reflectance | Specularity | Roughness |
|-------------------------|-------------|-------------|-----------|
| White painted wall       | 0.70        | 0.0         | 0.0       |
| Light grey painted wall  | 0.50        | 0.0         | 0.0       |
| Dark grey painted wall   | 0.20        | 0.0         | 0.0       |
| Concrete (raw)           | 0.30        | 0.0         | 0.05      |
| Wood flooring (light)    | 0.40        | 0.02        | 0.02      |
| Carpet (medium)          | 0.20        | 0.0         | 0.0       |
| Ceiling tile (white)     | 0.80        | 0.0         | 0.0       |
| Glass (clear single)     | Tvis: 0.88  | —           | —         |
| Glass (clear double)     | Tvis: 0.78  | —           | —         |
| Glass (low-e double)     | Tvis: 0.65  | —           | —         |
| Ground (grass)           | 0.20        | 0.0         | 0.0       |
| Ground (asphalt)         | 0.10        | 0.0         | 0.0       |
| Ground (concrete paving) | 0.30        | 0.0         | 0.0       |
| Red brick                | 0.25        | 0.0         | 0.03      |
| Aluminum (brushed)       | 0.60        | 0.50        | 0.05      |

### Grid-Based vs. Point-in-Time Analysis

**Grid-based analysis** places sensors at regular intervals across a horizontal workplane
(typically 0.76 m above floor for offices, 0.85 m for standing desks). Grid spacing
should be no larger than 0.5 m for final analysis and no larger than 1.0 m for early
design studies. Results are spatial maps showing illuminance distribution.

**Point-in-time analysis** evaluates illuminance or luminance at a specific moment
(date, time, sky condition). Useful for worst-case glare checks (e.g., December 21
at 3 PM with low sun angle) or for visualizing light distribution at critical moments.

### Parametric Daylight Optimization Workflow

1. Define variable parameters: window-to-wall ratio (20–80%), window sill height,
   head height, external shading depth (0–1.5 m), light shelf depth, room depth.
2. Set up Honeybee model with Radiance modifiers for all surfaces.
3. Run annual daylight simulation (Honeybee-Radiance recipe).
4. Extract sDA, ASE, and UDI from results.
5. Feed metrics into multi-objective optimizer (Wallacei recommended).
6. Objectives: maximize sDA, minimize ASE, minimize facade cost.
7. Analyze Pareto front to select design variants that balance performance and cost.

### Common Modeling Mistakes

- **Missing context buildings**: Omitting neighboring buildings that cast shadows leads
  to dramatically overstated daylight predictions. Always include context within at
  least 200 m radius for urban sites.
- **Wrong material reflectance**: Using default white (0.50) for all surfaces when
  actual materials are much darker (0.20–0.30) can overpredict daylight by 30–50%.
- **Insufficient grid resolution**: A 2 m grid misses spatial variation entirely. Use
  0.5 m maximum for compliance analysis.
- **Ignoring furniture**: Large obstructions like tall storage units significantly
  affect daylight distribution in deep plans.
- **Wrong analysis period**: Using calendar year instead of occupied hours misrepresents
  sDA values. Always define occupancy schedule correctly.
- **Not modeling window frames**: Frames reduce glazed area by 15–30%. Omitting them
  overpredicts daylight proportionally.

---

## 3. Solar Radiation Analysis

### Solar Geometry

The position of the sun is defined by two angles:

- **Altitude (elevation)**: Angle above the horizon (0° at horizon, 90° at zenith).
- **Azimuth**: Angle measured clockwise from true north (0° = N, 90° = E, 180° = S, 270° = W).

Solar position depends on latitude, longitude, date, and time. Key concepts:

- **Solar noon**: The moment the sun crosses the local meridian (highest altitude).
- **Equation of time**: Correction for the difference between solar time and clock
  time due to Earth's elliptical orbit and axial tilt. Varies by +/- 16 minutes.
- **Declination**: The angle between the sun's rays and the equatorial plane. Ranges
  from +23.45° (summer solstice) to -23.45° (winter solstice).
- **Hour angle**: Angular displacement of the sun from solar noon. 15° per hour.

### Solar Radiation Components

| Component   | Source                           | Behavior           | Typical share (annual) |
|-------------|----------------------------------|---------------------|----------------------|
| Direct beam | Sun disk                         | Casts sharp shadows | 50–70%               |
| Diffuse     | Sky vault (scattered by atmosphere)| Uniform, no shadows| 25–40%               |
| Reflected   | Ground and surrounding surfaces  | Depends on albedo   | 5–15%                |

Total solar radiation (global) = direct + diffuse + reflected.

### Radiation Analysis Types

**Cumulative annual radiation**: Total solar energy received by a surface over an
entire year, measured in kWh/m². This is the most common analysis for facade studies
and PV potential assessment. Typical values for a horizontal surface range from
900 kWh/m²/yr (northern Europe) to 2200 kWh/m²/yr (desert regions).

**Monthly radiation**: Breakdown of annual radiation by month, revealing seasonal
patterns. Critical for understanding heating vs. cooling season dynamics.

**Hourly radiation**: Instantaneous radiation values for specific hours, used for
peak load calculations and shadow studies.

### Solar Access Hours

Solar access analysis counts the number of hours per year (or per day for a specific
date) that a point receives direct sunlight. Used for:

- Right-to-light assessments (UK planning requirement: 2+ hours on March 21).
- BRE Site Layout Planning guidelines (25+ hours on March 21 for outdoor amenity).
- Passive solar design (minimum 4 hours winter solstice for south-facing facades).

### Shadow Range Analysis

Shadow range diagrams overlay all shadow positions for a specific date or period,
showing which areas are always in shade, always in sun, or intermittently shaded.
Useful for:

- Public space design (ensuring benches get winter sun).
- Urban planning (assessing impact of new tall buildings on surrounding neighborhoods).
- PV array siting (avoiding partially shaded zones).

### Radiation on Tilted Surfaces

Radiation on a tilted surface differs from horizontal radiation. The optimal tilt
angle for annual energy collection is approximately equal to the site latitude. For
winter-optimized collection, add 15° to latitude. For summer-optimized, subtract 15°.

Isotropic sky model: Diffuse radiation is uniform across the sky dome. Simple but
inaccurate — underestimates radiation near the horizon and circumsolar region.

Perez all-weather model: Divides the sky into circumsolar, horizon brightening, and
isotropic components. Most accurate model for tilted surface calculations.

### PV Potential Assessment

1. Calculate annual radiation on candidate surfaces (roof, facade, canopy).
2. Subtract shading losses from context geometry and self-shading.
3. Apply panel efficiency (monocrystalline: 20–22%, polycrystalline: 16–18%, thin-film: 10–13%).
4. Apply system losses (inverter: 3–5%, wiring: 2–3%, soiling: 2–5%, temperature: 5–10%).
5. Result: annual energy yield in kWh per panel or per m².

Typical yield: 150–200 kWh/m²/yr in northern Europe, 250–350 kWh/m²/yr in southern
US and Middle East.

### Sky Models

| Sky model       | Use case                     | Characteristics                        |
|-----------------|------------------------------|----------------------------------------|
| CIE overcast    | Daylight factor calculation  | Luminance varies only with altitude     |
| CIE clear       | Sunny day analysis           | Includes circumsolar and horizon zones  |
| CIE intermediate| Partly cloudy conditions     | Blend of clear and overcast             |
| Perez all-weather| Annual simulation           | Uses weather data, most accurate        |
| Uniform         | Simple diffuse analysis      | Equal luminance everywhere (unrealistic)|

### EPW Weather Files

EPW (EnergyPlus Weather) files contain hourly data for a typical meteorological year:

- Dry bulb temperature, dew point temperature, relative humidity
- Direct normal radiation, diffuse horizontal radiation, global horizontal radiation
- Wind speed, wind direction
- Atmospheric pressure, sky cover, precipitation

**Sources**: EnergyPlus.net, Climate.OneBuilding.org (most comprehensive), ASHRAE IWEC2,
Meteonorm (commercial, can generate for any location).

**TMY methodology**: Typical Meteorological Year data is constructed by selecting the
most representative month from a 15–30 year record for each calendar month. TMY data
represents typical conditions, not extreme conditions. For resilience analysis, use
actual year data or future climate projections.

---

## 4. Energy Simulation

### Building Energy Model Components

A complete building energy model requires the following layers:

1. **Geometry**: Thermal zones defined by enclosed volumes. Each zone has a single
   air temperature assumption. Zones should be separated where significantly different
   thermal conditions exist (perimeter vs. core, different orientations, different uses).

2. **Constructions**: Material layers for each opaque surface (walls, roofs, floors)
   and glazing properties for windows. Each layer defined by thickness, conductivity,
   density, and specific heat.

3. **Schedules**: Hourly profiles for occupancy, lighting, equipment, thermostat
   setpoints, HVAC availability, and ventilation rates. Schedules are the single most
   influential input in energy modeling after geometry.

4. **Internal loads**: Heat gains from people (sensible + latent), lighting, and
   equipment. Specified as peak values modulated by schedules.

5. **HVAC systems**: Heating, cooling, and ventilation equipment. Ranges from
   ideal air (unlimited capacity, perfect efficiency — for early design) to fully
   detailed systems with specific equipment curves.

6. **Infiltration**: Uncontrolled air leakage through the envelope. Specified as
   ACH (air changes per hour) or flow per unit envelope area.

7. **Natural ventilation**: Window opening behavior, stack effect, wind-driven
   ventilation. Can be modeled as scheduled or as airflow network.

### EnergyPlus Engine Fundamentals

EnergyPlus is a whole-building energy simulation engine developed by the US Department
of Energy. It uses a heat-balance method that simultaneously solves:

- Conduction through opaque surfaces (conduction transfer functions)
- Solar radiation through windows (detailed optical calculations)
- Internal convection (TARP algorithm)
- Longwave radiation exchange between surfaces
- Air heat balance (zone energy balance)
- HVAC system response

EnergyPlus runs sub-hourly timesteps (typically 6 per hour = 10-minute intervals)
with weather data interpolated from hourly EPW values.

### Honeybee-Energy Workflow

1. **Create rooms**: Define thermal zone geometry from Rhino surfaces or procedural
   generation. Each room = one thermal zone.
2. **Assign program types**: Predefined combinations of loads, schedules, and setpoints
   for common space types (office, residential, retail, etc.).
3. **Set construction sets**: Climate-appropriate envelope specifications. Honeybee
   includes ASHRAE baseline construction sets by climate zone.
4. **Define HVAC**: Start with IdealAirSystem for early design. Progress to detailed
   systems (VAV, VRF, DOAS, radiant) for later stages.
5. **Set simulation parameters**: Run period, timestep, terrain, solar distribution.
6. **Run simulation**: Honeybee generates IDF file and calls EnergyPlus.
7. **Parse results**: Monthly/annual energy by end use, zone temperatures, comfort hours.

### Key Outputs

**Energy Use Intensity (EUI)**
Total annual energy consumption divided by gross floor area, measured in kWh/m²/yr
(or kBtu/ft²/yr in US practice). EUI is the primary benchmark for building energy
performance.

| Building type      | Good EUI (kWh/m²/yr) | Average EUI | Poor EUI |
|--------------------|-----------------------|-------------|----------|
| Office             | 80–120                | 150–200     | 250+     |
| Residential (apt)  | 50–80                 | 100–140     | 180+     |
| Retail             | 100–150               | 200–280     | 350+     |
| Education          | 70–110                | 130–170     | 220+     |
| Hospital           | 200–300               | 350–450     | 550+     |
| Hotel              | 120–180               | 220–300     | 400+     |
| Laboratory         | 250–400               | 500–700     | 900+     |
| Warehouse          | 30–50                 | 60–100      | 150+     |

**Heating/Cooling Loads**
Annual energy required for space heating and cooling, broken down monthly. The ratio
of heating to cooling reveals the building's dominant load and guides passive strategy
selection.

**Peak Loads**
Maximum instantaneous heating and cooling demand, measured in kW or W/m². Peak loads
size the HVAC equipment. Reducing peak loads through passive design (thermal mass,
shading, high-performance envelope) allows smaller, less expensive mechanical systems.

### Early-Stage Energy Estimation

For concept design, full EnergyPlus simulation may be premature. Simplified methods:

- **Degree-day method**: Estimate heating/cooling energy from HDD/CDD and envelope
  UA-value. Fast but ignores solar gains, internal gains, and thermal mass.
- **Lookup tables**: Reference EUI values from benchmarking databases (CBECS, CIBSE
  TM46, EU building typologies) adjusted for climate and building features.
- **Shoebox models**: Single-zone energy models representing a typical floor section.
  Capture the essential physics in 1% of the modeling effort.
- **Regression surrogates**: Train a model on thousands of EnergyPlus runs, then
  predict EUI from a handful of input parameters in milliseconds.

### Parametric Energy Optimization

Key parameters for early-stage energy optimization:

| Parameter          | Typical range     | Impact on EUI          |
|--------------------|-------------------|------------------------|
| Orientation        | 0–360°            | 5–15% (climate-dependent)|
| WWR (north)        | 15–60%            | 5–20%                  |
| WWR (south)        | 15–60%            | 10–30%                 |
| WWR (east/west)    | 15–40%            | 10–25%                 |
| Wall U-value       | 0.15–0.50 W/m²K   | 5–15%                  |
| Roof U-value       | 0.10–0.30 W/m²K   | 3–10%                  |
| Glazing U-value    | 0.8–3.0 W/m²K     | 5–20%                  |
| Glazing SHGC       | 0.20–0.60         | 10–25%                 |
| Shading depth      | 0–2.0 m           | 5–15%                  |
| Infiltration rate  | 0.1–1.0 ACH       | 5–15%                  |
| Lighting power     | 4–12 W/m²         | 10–20%                 |

### Passive Design Strategies Validated by Simulation

- **Orientation**: Long axis east-west maximizes southern exposure (northern hemisphere),
  improving winter solar gain while allowing effective summer shading.
- **Thermal mass**: Exposed concrete soffits absorb daytime gains and release heat
  at night, reducing peak cooling loads by 10–20%.
- **Night purge ventilation**: Flushing the building with cool night air pre-cools
  thermal mass, shifting cooling loads and reducing HVAC energy by 15–30%.
- **External shading**: Horizontal overhangs on south, vertical fins on east/west.
  Fixed shading design derived from sun path analysis.
- **High-performance glazing**: Triple glazing with low-e coatings (U < 1.0 W/m²K,
  SHGC 0.25–0.40) dramatically reduces both heating and cooling loads.
- **Daylighting with dimming**: Photosensor-controlled dimming of electric lights in
  daylit zones reduces lighting energy by 40–60%.

---

## 5. CFD Wind Analysis

### Outdoor Wind Comfort — Lawson Criteria

The Lawson comfort criteria classify wind conditions by acceptable activity:

| Category          | Mean wind speed threshold | Gust equivalent | Acceptable activity       |
|-------------------|--------------------------|-----------------|---------------------------|
| Sitting (long)    | < 2.5 m/s                | < 4.0 m/s       | Outdoor dining, reading   |
| Sitting (short)   | < 4.0 m/s                | < 6.0 m/s       | Bus stops, café terraces  |
| Standing          | < 6.0 m/s                | < 8.0 m/s       | Window shopping, waiting  |
| Walking (leisure) | < 8.0 m/s                | < 10.0 m/s      | Strolling, walking routes |
| Business walking  | < 10.0 m/s               | < 12.0 m/s      | Walking to work, commuting|
| Uncomfortable     | 10–15 m/s                | 12–18 m/s       | Hair disturbed, clothing flaps|
| Dangerous         | > 15 m/s                 | > 20 m/s        | Structural damage risk    |

Wind comfort is typically assessed at pedestrian level (1.5 m above ground) for the
annual wind climate, reporting the worst-season or annual probability of exceedance.

### Computational Wind Tunnel Setup

**Domain sizing rules** (H = tallest building height):

| Boundary           | Distance from buildings | Rationale                           |
|--------------------|------------------------|-------------------------------------|
| Inlet              | 5H upstream            | Allow boundary layer to develop     |
| Outlet             | 15H downstream         | Allow wake to dissipate             |
| Lateral walls      | 5H from edge of model  | Prevent blockage effects (< 3%)     |
| Top                | 5H above tallest point | Prevent artificial acceleration     |

**Blockage ratio** (frontal area of buildings / domain cross-section) must be < 3%.
Higher blockage artificially accelerates flow around buildings.

**Mesh resolution guidelines**:

| Region                        | Cell size          |
|-------------------------------|--------------------|
| Near building surfaces        | 0.5–1.0 m         |
| Pedestrian level (0–3 m)      | 0.5–1.0 m         |
| Near-field (within 2H)        | 1.0–3.0 m         |
| Far-field (beyond 2H)         | 3.0–10.0 m        |
| Boundary layer refinement     | First cell < 0.5 m|

Total cell count for a typical urban study: 2–10 million cells.

### Turbulence Models

**RANS (Reynolds-Averaged Navier-Stokes)**: Time-averaged equations with turbulence
closure models. Solves for mean flow quantities. Computationally affordable.

| Model              | Strengths                          | Weaknesses                    | Use case              |
|--------------------|------------------------------------|-------------------------------|-----------------------|
| Standard k-epsilon | Robust, well-validated             | Poor for separation, wakes    | Initial screening     |
| Realizable k-epsilon| Better for recirculation          | Still struggles with anisotropy| General urban studies |
| k-omega SST        | Excellent near-wall, good separation| Higher cost than k-epsilon  | Detailed pedestrian comfort|
| Spalart-Allmaras   | Low cost, good for attached flow   | Poor for complex urban geometry| Aerospace, not urban  |

**LES (Large Eddy Simulation)**: Resolves large-scale turbulent structures directly,
models only the smallest scales. Much more accurate for urban flows but 100–1000x
more expensive than RANS. Reserved for research and critical safety assessments.

### Butterfly (OpenFOAM for Grasshopper) Workflow

1. Create geometry in Rhino/Grasshopper (buildings as closed Breps).
2. Define wind tunnel (domain) using Butterfly components.
3. Set inlet boundary condition: atmospheric boundary layer profile with reference
   wind speed, direction, roughness length (z0), and reference height.
4. Set mesh parameters: base cell size, refinement levels near buildings.
5. Select turbulence model (k-epsilon or k-omega SST).
6. Run snappyHexMesh for mesh generation.
7. Run simpleFoam (steady-state RANS solver).
8. Post-process: extract wind speed at 1.5 m height plane, map to Lawson categories.

### Simplified Wind Analysis for Early Design

Full CFD is expensive and time-consuming. For early design, use:

- **Desktop wind assessment**: Classify building form using standard typologies
  (slab, tower, podium-tower, courtyard) and apply known wind behavior patterns.
- **Wind comfort rules of thumb**: Tall buildings create downwash proportional to
  their height. Corner acceleration increases with building width. Through-building
  passages create venturi effects.
- **Lawson screening tool**: Quick assessment based on building height, width, and
  surroundings without running CFD.
- **Reduced-order models**: Pre-computed wind pressure databases for simple shapes.

### Natural Ventilation Potential

CFD can assess whether natural ventilation is viable:

- Calculate pressure coefficients (Cp) on building facades from wind simulation.
- Derive pressure difference between windward and leeward openings.
- Estimate ventilation flow rate: Q = Cd * A * sqrt(2 * dP / rho).
- Compare achieved air change rate against minimum ventilation requirements.

### Wind-Driven Rain

Wind-driven rain analysis predicts wetting patterns on building facades:

- Combines rainfall intensity with wind speed and direction.
- Identifies facade zones at risk of water penetration.
- Informs material selection, detailing, and drainage design.
- Quantified as catch ratio: rain on vertical surface / rain on horizontal surface.

---

## 6. Thermal Comfort

### Indoor Thermal Comfort

**PMV/PPD (Fanger Model)**
Predicted Mean Vote (PMV) is a steady-state thermal comfort index on a 7-point scale:

| PMV value | Thermal sensation |
|-----------|-------------------|
| -3        | Cold              |
| -2        | Cool              |
| -1        | Slightly cool     |
| 0         | Neutral           |
| +1        | Slightly warm     |
| +2        | Warm              |
| +3        | Hot               |

Predicted Percentage Dissatisfied (PPD) is derived from PMV. At PMV = 0, PPD = 5%
(some people are always dissatisfied). ASHRAE 55 requires -0.5 < PMV < +0.5 (PPD < 10%).

PMV inputs:
| Parameter              | Symbol | Typical indoor range    |
|------------------------|--------|-------------------------|
| Air temperature        | Ta     | 18–28°C                 |
| Mean radiant temperature| Tr    | 16–35°C                 |
| Air speed              | Va     | 0.05–0.5 m/s            |
| Relative humidity      | RH     | 30–70%                  |
| Metabolic rate         | Met    | 1.0–2.0 met (office: 1.1)|
| Clothing insulation    | Clo    | 0.5–1.5 clo             |

**Adaptive Model**
For naturally ventilated buildings, the adaptive model (ASHRAE 55 Section 5.4, EN 15251)
defines acceptable indoor temperature as a function of outdoor running mean temperature.

Acceptable operative temperature = 17.8 + 0.31 * outdoor running mean temperature
(80% acceptability band: +/- 3.5°C; 90% band: +/- 2.5°C).

The adaptive model acknowledges that occupants in naturally ventilated buildings
tolerate wider temperature ranges because they have more control (opening windows,
adjusting clothing).

### Outdoor Thermal Comfort

**Universal Thermal Climate Index (UTCI)**
An equivalent temperature that represents the physiological response of the human
body to the outdoor thermal environment.

| UTCI range (°C)  | Stress category           | Thermal perception |
|-------------------|---------------------------|--------------------|
| > 46              | Extreme heat stress       | Unbearable         |
| 38–46             | Very strong heat stress   | Very hot           |
| 32–38             | Strong heat stress        | Hot                |
| 26–32             | Moderate heat stress      | Warm               |
| 9–26              | No thermal stress         | Comfortable        |
| 0–9               | Slight cold stress        | Slightly cool      |
| -13–0             | Moderate cold stress      | Cool               |
| -27–(-13)         | Strong cold stress        | Cold               |
| -40–(-27)         | Very strong cold stress   | Very cold          |
| < -40             | Extreme cold stress       | Extreme cold       |

**Physiological Equivalent Temperature (PET)**
The air temperature at which the body's heat balance would be the same in a standard
indoor reference environment. More intuitive for non-specialists.

**Mean Radiant Temperature (MRT)**
The uniform temperature of an imaginary black enclosure that would result in the same
net radiation heat exchange as the actual environment. MRT is often the dominant factor
in outdoor comfort and is strongly influenced by:

- Direct solar radiation (sun exposure vs. shade)
- Longwave radiation from surrounding surfaces (hot pavement vs. vegetation)
- Sky view factor (open sky vs. enclosed courtyard)

MRT can be 20–30°C higher in direct sun than in shade. This is why shade trees and
canopies are the single most effective microclimate intervention in hot climates.

### Microclimate Simulation Workflow

1. Model urban geometry (buildings, ground surfaces, vegetation).
2. Assign surface materials (albedo, emissivity, thermal admittance).
3. Set meteorological boundary conditions from EPW data.
4. Run coupled simulation: radiation (solar + longwave) + CFD (wind field) + energy
   balance (surface temperatures).
5. Calculate MRT at pedestrian height from radiation field.
6. Compute UTCI or PET at grid of points.
7. Map comfort categories spatially and temporally.

Tools: ENVI-met (most comprehensive urban microclimate tool), Ladybug Tools (MRT
and UTCI from weather data and simplified radiation), RayMan, SOLWEIG.

---

## 7. Acoustic Simulation

### Room Acoustics Metrics

| Metric | Full name                     | Target (speech)    | Target (music)       |
|--------|-------------------------------|--------------------|----------------------|
| RT60   | Reverberation time (60 dB decay)| 0.4–0.8 s (office)| 1.5–2.5 s (concert) |
| EDT    | Early Decay Time              | ≈ RT60             | ≈ RT60 (uniform)     |
| C80    | Clarity (ratio early/late)    | —                  | -2 to +4 dB          |
| D50    | Definition (early/total ratio)| > 0.50             | —                    |
| STI    | Speech Transmission Index     | > 0.60 (good)      | —                    |
| G      | Strength (dB re: 10 m free field)| —               | 0 to +10 dB          |

**RT60** is the most commonly specified acoustic metric. It depends on room volume
and total absorption:

Sabine equation: RT60 = 0.161 * V / A

Where V = room volume (m³) and A = total absorption (m² Sabins).

**Eyring equation** (more accurate for highly absorptive rooms):
RT60 = 0.161 * V / (-S * ln(1 - alpha_avg))

Where S = total surface area and alpha_avg = average absorption coefficient.

### Material Absorption Coefficients

| Material                  | 125 Hz | 250 Hz | 500 Hz | 1 kHz | 2 kHz | 4 kHz |
|---------------------------|--------|--------|--------|-------|-------|-------|
| Concrete (painted)         | 0.01   | 0.01   | 0.02   | 0.02  | 0.02  | 0.03  |
| Brick (unglazed)           | 0.03   | 0.03   | 0.03   | 0.04  | 0.05  | 0.07  |
| Plasterboard on studs      | 0.29   | 0.10   | 0.06   | 0.05  | 0.04  | 0.04  |
| Glass (window)             | 0.35   | 0.25   | 0.18   | 0.12  | 0.07  | 0.04  |
| Timber floor               | 0.15   | 0.11   | 0.10   | 0.07  | 0.06  | 0.07  |
| Carpet (heavy on pad)      | 0.08   | 0.24   | 0.57   | 0.69  | 0.71  | 0.73  |
| Acoustic ceiling tile      | 0.50   | 0.70   | 0.60   | 0.70  | 0.70  | 0.50  |
| Curtain (heavy, draped)    | 0.07   | 0.31   | 0.49   | 0.75  | 0.70  | 0.60  |
| Mineral wool (50 mm)       | 0.15   | 0.45   | 0.70   | 0.80  | 0.80  | 0.80  |
| Perforated metal + absorber| 0.40   | 0.70   | 0.80   | 0.85  | 0.75  | 0.65  |
| Upholstered seat (occupied)| 0.60   | 0.75   | 0.85   | 0.90  | 0.90  | 0.85  |
| Open doorway               | 1.00   | 1.00   | 1.00   | 1.00  | 1.00  | 1.00  |

### Ray-Tracing Acoustic Simulation

**Pachyderm Acoustics** is a Grasshopper plugin for room acoustics simulation:

1. Define room geometry as closed meshes in Rhino.
2. Assign absorption and scattering coefficients to each surface.
3. Place source and receiver points.
4. Run ray-tracing simulation (10,000–100,000 rays).
5. Extract impulse response at each receiver.
6. Compute RT60, EDT, C80, D50, STI from impulse response.
7. Visualize sound pressure level distribution as color map.

### Sound Insulation

**STC (Sound Transmission Class)**: Single-number rating for airborne sound insulation
of partitions (North American standard, ASTM E413).

| STC rating | Performance                                       |
|------------|---------------------------------------------------|
| 25         | Normal speech easily understood                    |
| 30         | Loud speech understood, normal speech audible      |
| 35         | Loud speech audible but not easily understood      |
| 40         | Loud speech audible as murmur                      |
| 45         | Loud speech not audible                            |
| 50         | Very loud sounds barely heard                      |
| 55+        | Most sounds inaudible                              |

**Rw (Weighted Sound Reduction Index)**: ISO equivalent of STC (ISO 717-1).

Typical constructions:
- Single plasterboard on studs: STC 33–38
- Double plasterboard on studs with insulation: STC 45–50
- Concrete block (200 mm): STC 45–50
- Concrete slab (200 mm): STC 50–55
- Double stud wall with resilient channels: STC 55–60

### Outdoor Noise Propagation

Environmental noise from roads, railways, and aircraft is assessed using:

- **ISO 9613-2**: Attenuation of sound during outdoor propagation (geometric spreading,
  atmospheric absorption, ground effect, screening by barriers).
- **CNOSSOS-EU**: Harmonized European noise calculation method.
- **Distance attenuation**: Point source: -6 dB per doubling of distance. Line source
  (road): -3 dB per doubling of distance.
- **Barrier effect**: A solid barrier provides 5–15 dB insertion loss depending on
  path length difference.
- **Noise mapping**: Color-coded maps of facade or free-field noise levels, typically
  at 4 m height. Required for Environmental Impact Assessments.

---

## 8. Ladybug Tools Ecosystem

### Overview

Ladybug Tools is an open-source collection of plugins for Grasshopper (Rhino) that
provides comprehensive environmental analysis capabilities for building and urban
design. It connects parametric geometry to validated simulation engines.

### Ladybug (Weather Data and Outdoor Analysis)

Core capabilities:
- **EPW import and visualization**: Dry bulb temperature, radiation, wind, humidity
  as hourly heatmaps, bar charts, and statistical summaries.
- **Sun path diagram**: 3D stereographic or orthographic sun path with hourly sun
  positions, analemmas, and sun vectors for any location.
- **Wind rose**: Frequency and speed distribution by direction for any analysis period.
- **Radiation rose**: Directional radiation distribution for facade orientation studies.
- **Shadow study**: Calculate sunlight hours on test surfaces with context geometry.
- **Outdoor comfort**: UTCI, PET, and other outdoor comfort models from weather data.
- **Sky dome**: Visualize sky luminance/radiance distribution (Tregenza sky patches).
- **Direct sun hours**: Mesh-based analysis of solar access hours.
- **View analysis**: Assess visual exposure from points to targets.

### Honeybee (Building Simulation)

**Honeybee-Radiance** (daylight):
- Create Radiance models from Grasshopper geometry.
- Assign material modifiers (plastic, glass, trans, BSDF).
- Define sensor grids and views.
- Run point-in-time illuminance, daylight factor, annual daylight (sDA/ASE/UDI).
- Glare analysis with Evalglare.
- Parametric blind/shade studies.

**Honeybee-Energy** (thermal/energy):
- Create thermal zones (rooms) from geometry.
- Assign program types (loads and schedules by space type).
- Define construction sets (opaque + glazing assemblies).
- Set HVAC systems (ideal air, detailed systems).
- Run EnergyPlus simulations.
- Parse results: energy by end use, zone temperatures, comfort.

Key Honeybee concepts:
- **Room**: A closed volume representing one thermal zone.
- **Face**: A planar surface bounding a room (wall, floor, roof/ceiling).
- **Aperture**: A window or skylight within a face.
- **Door**: An opaque or glass door within a face.
- **Shade**: An external shading surface (overhang, fin, context building).
- **Modifier**: Radiance material properties (reflectance, transmittance).
- **Construction**: Energy material layers (conductivity, density, specific heat).
- **ProgramType**: Combination of people, lighting, equipment, ventilation, setpoints.
- **ConstructionSet**: Collection of constructions for all face types.

### Butterfly (CFD)

- Wraps OpenFOAM for use in Grasshopper.
- Creates computational domain (wind tunnel) around building geometry.
- Generates block-structured mesh with refinement regions.
- Sets boundary conditions (inlet velocity profile, outlet, walls).
- Runs steady-state RANS solver (simpleFoam).
- Extracts velocity and pressure fields for visualization.
- Current status: Less actively maintained than Ladybug/Honeybee. For production
  CFD work, consider standalone OpenFOAM or commercial tools.

### Dragonfly (Urban Scale)

- **Urban weather generator (UWG)**: Modifies rural EPW data to account for urban
  heat island effect, producing urban-specific weather data.
- **District energy modeling**: Aggregates building energy models for neighborhood-scale
  analysis.
- **Urban geometry**: Creates building footprint extrusions from GIS data.
- **REopt integration**: Optimizes distributed energy resources (PV, storage, CHP).
- **Urban microclimate**: Couples with other tools for outdoor comfort mapping.

### Version Compatibility

| Component         | Current version | Rhino compatibility | Python   |
|-------------------|-----------------|---------------------|----------|
| Ladybug           | 1.8.x           | Rhino 7, Rhino 8    | IronPython / CPython |
| Honeybee          | 1.8.x           | Rhino 7, Rhino 8    | IronPython / CPython |
| Honeybee-Radiance | 1.66.x          | Rhino 7, Rhino 8    | CPython 3.7+         |
| Honeybee-Energy   | 1.104.x         | Rhino 7, Rhino 8    | CPython 3.7+         |
| Butterfly         | 0.0.x           | Rhino 6, Rhino 7    | IronPython           |
| Dragonfly         | 1.8.x           | Rhino 7, Rhino 8    | CPython 3.7+         |

Note: Ladybug Tools 1.x (LBT) uses the Pollination installer, which manages
Radiance, EnergyPlus, and OpenStudio dependencies automatically.

### Installation

1. Install Rhino 7 or 8.
2. Download Pollination Grasshopper installer from pollination.cloud.
3. Run installer — it sets up Ladybug Tools, Radiance 5.4+, EnergyPlus 23.1+,
   and OpenStudio 3.7+ automatically.
4. Alternatively, install from Food4Rhino and manually configure engine paths.
5. Verify installation: drop LB Versioner component on Grasshopper canvas.

### Common Workflows

| Workflow                     | Components used                         | Engine   | Output                |
|------------------------------|-----------------------------------------|----------|-----------------------|
| Daylight factor              | HB Model, HB Modifier, HB Grid, HB DF  | Radiance | DF spatial map        |
| Annual daylight (sDA/ASE)    | HB Model, HB Annual Daylight            | Radiance | sDA, ASE percentages  |
| Point-in-time illuminance    | HB Model, HB Point-in-Time              | Radiance | Illuminance grid      |
| Glare analysis               | HB Model, HB Glare, Evalglare           | Radiance | DGP images            |
| Energy model (annual)        | HB Room, HB Program, HB Construction, HB Energy| EnergyPlus| EUI, loads, temps |
| Outdoor solar radiation      | LB Direct Sun Hours, LB Radiation       | Built-in | kWh/m² map            |
| Sun path + shadow study      | LB Sun Path, LB Shadow Study            | Built-in | Hours of sunlight     |
| Wind rose                    | LB Wind Rose                            | Built-in | Directional wind plot |
| Outdoor comfort (UTCI)       | LB UTCI, LB MRT                         | Built-in | UTCI spatial map      |
| Parametric optimization      | Above + Galapagos / Wallacei            | Various  | Pareto-optimal designs|

### Integration with Optimization

**Galapagos** (single-objective): Built into Grasshopper. Uses genetic algorithm.
Connect performance metric to fitness input. Good for single-metric optimization
(e.g., minimize EUI). Limited to one objective.

**Wallacei** (multi-objective): NSGA-2 algorithm for Grasshopper. Handles 2–10+
objectives simultaneously. Produces Pareto front of non-dominated solutions. Includes
built-in analytics for exploring the solution space. Recommended for performance-driven
design where multiple conflicting objectives exist.

**Colibri** (design space exploration): Records every iteration of a parametric
study (inputs and outputs) to a structured data file. Pairs with Design Explorer
web app for parallel coordinates visualization. Useful for understanding parameter
sensitivity before launching optimization.

---

## 9. Simulation Quality Assurance

### Validation Strategies

Every simulation result should be viewed with appropriate skepticism. Validation builds
confidence in results:

- **Analytical validation**: Compare simulation output against known analytical
  solutions for simple cases (e.g., steady-state heat flow through a wall, illuminance
  from a point source). If the engine cannot reproduce analytical results, something
  is fundamentally wrong.
- **Empirical validation**: Compare simulation output against measured data from real
  buildings or controlled experiments. ASHRAE Standard 140 (BESTEST) provides
  standardized test cases for energy simulation engines.
- **Comparative validation**: Compare results from two different simulation engines
  on the same model. Agreement builds confidence; disagreement demands investigation.
- **Sensitivity analysis**: Vary uncertain inputs (material properties, schedules,
  weather data) and observe the effect on outputs. If results are highly sensitive to
  an uncertain input, invest effort in getting that input right.

### Mesh Independence Studies

For any spatially discretized simulation (daylight grids, CFD meshes, FEM meshes):

1. Run the simulation with a coarse mesh.
2. Refine the mesh (halve cell size) and rerun.
3. Compare results at key locations.
4. If results change by more than 5%, refine further.
5. Repeat until results converge (< 2% change between successive refinements).
6. Report the final mesh resolution and the convergence behavior.

Mesh independence is non-negotiable for CFD and strongly recommended for daylight grids.
A simulation on an inadequate mesh is not worth the computation time.

### Result Interpretation Guidelines

- **Order of magnitude**: Do results fall within the expected range for this building
  type and climate? An EUI of 500 kWh/m²/yr for a well-insulated office is wrong.
- **Spatial distribution**: Do daylight, temperature, and wind maps show physically
  plausible patterns? Symmetric buildings should produce symmetric results.
- **Temporal patterns**: Do energy loads follow expected seasonal patterns? Cooling
  should peak in summer, heating in winter (for most climates).
- **Comparative ranking**: Even if absolute values are uncertain, the relative ranking
  of design options is usually reliable. Use simulation for comparison, not prediction.

### Common Errors and Diagnostic Checklist

| Error                          | Symptom                              | Fix                                    |
|--------------------------------|--------------------------------------|----------------------------------------|
| Missing surfaces               | Unrealistic heat loss / daylight     | Check for gaps in geometry             |
| Wrong boundary conditions      | Adiabatic exterior walls             | Verify face types (wall/floor/roof)    |
| Interior walls as exterior     | Excessive heating/cooling loads      | Check adjacencies between rooms        |
| Wrong weather file             | Results don't match climate          | Verify EPW location matches project    |
| Schedule errors                | Overnight loads in unoccupied building| Review occupancy and HVAC schedules   |
| Unit confusion                 | Values 10x too high or low           | Check W vs kW, m² vs ft², °C vs °F    |
| Insufficient Radiance bounces  | Dark interiors, low daylight values  | Increase -ab parameter                 |
| Coarse CFD mesh                | Smoothed-out wind patterns           | Refine mesh, check independence        |
| Wrong material properties      | Unrealistic surface temperatures     | Verify conductivity, reflectance, etc. |
| Unconverged CFD                | Oscillating residuals                | Improve mesh quality, check BC setup   |

### When to Trust Results vs. Use Engineering Judgment

Trust simulation results when:
- The model has been validated against analytical or empirical benchmarks.
- Mesh independence has been demonstrated.
- Material properties and boundary conditions are well-characterized.
- Results are within expected physical ranges.
- Sensitivity analysis shows results are robust to uncertain inputs.

Use engineering judgment when:
- Input data is highly uncertain (occupant behavior, future climate).
- The simulation engine has known limitations for the specific case.
- Results contradict well-established physical principles.
- The model uses significant simplifications (shoebox model, ideal HVAC).
- Computational constraints prevented adequate mesh resolution.

### Reporting Simulation Results

Professional simulation reports should include:

1. **Executive summary**: Key findings and recommendations in non-technical language.
2. **Model description**: Geometry, materials, boundary conditions, assumptions.
3. **Simulation setup**: Engine, version, settings, mesh details, weather data.
4. **Results**: Spatial maps, charts, tables with clear units and legends.
5. **Interpretation**: What the results mean for design decisions.
6. **Limitations**: What the simulation does not capture, uncertainty bounds.
7. **Recommendations**: Specific design actions supported by the analysis.
8. **Appendices**: Detailed input data, convergence plots, sensitivity results.

Never present simulation results without stating the assumptions and limitations.
A number without context is more dangerous than no number at all.

---

## Quick Reference: Simulation Engine Selection

| Analysis need                  | Recommended engine          | Ladybug tool    | Accuracy level    |
|--------------------------------|-----------------------------|-----------------|-------------------|
| Daylight factor                | Radiance                    | Honeybee        | High              |
| Annual daylight (sDA/ASE)      | Radiance (3/5-phase)        | Honeybee        | High              |
| Glare analysis                 | Radiance + Evalglare        | Honeybee        | High              |
| Solar radiation                | Built-in (Tregenza method)  | Ladybug         | Medium-High       |
| Sun hours / shadow             | Built-in (ray intersection) | Ladybug         | High              |
| Building energy (annual)       | EnergyPlus                  | Honeybee        | High              |
| Building energy (early stage)  | Degree-day / lookup         | Manual          | Low-Medium        |
| Outdoor wind comfort           | OpenFOAM                    | Butterfly       | Medium-High       |
| Indoor thermal comfort (PMV)   | EnergyPlus                  | Honeybee        | High              |
| Outdoor thermal comfort (UTCI) | Built-in                    | Ladybug         | Medium            |
| Urban microclimate             | ENVI-met                    | External        | High              |
| Room acoustics                 | Pachyderm                   | External (GH)   | Medium-High       |
| Outdoor noise                  | ISO 9613 / CadnaA           | External        | Medium-High       |

---

## Key Formulas Reference

**Daylight Factor:**
DF = (Ei / Eo) * 100%
Where Ei = indoor illuminance, Eo = unobstructed outdoor diffuse horizontal illuminance.

**Sabine reverberation time:**
RT60 = 0.161 * V / A
Where V = volume (m³), A = total absorption (m² Sabins).

**Natural ventilation flow rate:**
Q = Cd * A * sqrt(2 * deltaP / rho)
Where Cd = discharge coefficient (~0.6), A = opening area, deltaP = pressure difference, rho = air density.

**Solar heat gain through glazing:**
Qsolar = A_glazing * SHGC * I_solar
Where SHGC = solar heat gain coefficient, I_solar = incident solar radiation (W/m²).

**Thermal transmittance (U-value):**
U = 1 / R_total
R_total = R_si + sum(d_i / k_i) + R_se
Where R_si/R_se = surface resistances, d = thickness, k = conductivity.

**UTCI (simplified approximation):**
UTCI ≈ f(Ta, Tr, va, RH) — computed via 6th-order polynomial regression.

**Reynolds number:**
Re = rho * v * L / mu
Where rho = air density, v = velocity, L = characteristic length, mu = dynamic viscosity.
Re > 4000 indicates turbulent flow (for external aerodynamics, Re >> 10^6 always turbulent).
