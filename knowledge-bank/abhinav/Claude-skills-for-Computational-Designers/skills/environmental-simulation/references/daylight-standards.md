# Daylight Standards and Simulation Reference

This document provides a comprehensive reference for daylight analysis in building
design, covering international standards, material databases, simulation setup
procedures, advanced methods, glare analysis, and design rules of thumb.

---

## 1. LEED v4.1 IEQ Credit: Daylight

### Credit Requirements

LEED v4.1 BD+C offers up to 3 points for the Daylight credit under Indoor
Environmental Quality (IEQ).

**Option 1: Simulation — sDA and ASE (preferred path)**

| Requirement                          | Threshold                           | Points |
|--------------------------------------|-------------------------------------|--------|
| sDA300/50% in regularly occupied area| >= 55% of floor area achieves target| 2      |
| sDA300/50% in regularly occupied area| >= 75% of floor area achieves target| 3      |
| ASE1000/250h in regularly occupied area| <= 10% of floor area              | Required for either point level |

Definitions:
- **sDA300/50%**: Percentage of analysis points that receive at least 300 lux for
  at least 50% of annual occupied hours.
- **ASE1000/250h**: Percentage of analysis points that receive more than 1000 lux
  of direct sunlight for more than 250 occupied hours per year.
- **Regularly occupied area**: Spaces where people work, learn, or spend extended
  time. Excludes corridors, lobbies, restrooms, storage, mechanical rooms.

**Analysis requirements:**
- Use annual simulation with climate-specific EPW weather data.
- Analysis grid at workplane height: 0.762 m (30 inches) for standard desks.
- Grid spacing: no greater than 0.61 m (2 feet).
- Include all permanent interior obstructions (columns, core walls, fixed furniture).
- Include external context within at least 60 m (200 feet) of the building.
- Dynamic shading devices may be modeled as always deployed for ASE calculation
  or as dynamically operated with documented control logic.
- Blinds modeled for ASE must be included in the sDA calculation as well.

**Option 2: Measurement (post-construction verification)**
- Measure illuminance on a grid at workplane height on any date between September
  15 and March 15 (heating season) at 9 AM and 3 PM.
- Target: 300–3000 lux at both measurement times for at least 75% of regularly
  occupied area (3 points) or 55% (2 points).
- Blinds and shades should be in the position typically used by occupants.

### Compliance Documentation

For simulation-based compliance:
1. Floor plans showing regularly occupied areas and analysis grid boundaries.
2. Simulation model screenshots showing geometry, context, and material assignments.
3. Description of simulation engine (Radiance version), settings, and weather file.
4. sDA and ASE results as spatial color maps overlaid on floor plans.
5. Summary table: total regularly occupied area, area achieving sDA threshold,
   percentage achieving threshold.
6. If dynamic shading is modeled: description of control logic and schedule.

### Common Compliance Challenges

- **Deep floor plates**: Open offices deeper than 12 m from the facade struggle to
  achieve sDA >= 55% without toplighting or light wells.
- **East/west glazing**: Large windows on east and west facades often cause ASE > 10%
  due to low-angle sun. Solutions: vertical fins, fritted glass, automated blinds.
- **Urban context**: Dense urban sites with tall neighboring buildings may receive
  insufficient daylight regardless of facade design.
- **Internal partitions**: Private offices along the perimeter block daylight from
  reaching the open office behind them. Glass partitions help but reduce sDA.

---

## 2. EN 17037: Daylight in Buildings

### Overview

EN 17037 is the European standard for daylight in buildings, published in 2018 and
adopted by CEN member countries. It evaluates four aspects of daylight quality.

### Aspect 1: Daylight Provision

Target illuminance must be achieved across the horizontal workplane for at least
50% of daylight hours.

| Recommendation level | Target illuminance (50% of area) | Minimum illuminance (95% of area) |
|----------------------|----------------------------------|-----------------------------------|
| Minimum              | 300 lux                          | 100 lux                           |
| Medium               | 500 lux                          | 300 lux                           |
| High                 | 750 lux                          | 500 lux                           |

Target illuminance by room type:

| Room type             | Minimum target | Medium target | High target |
|-----------------------|----------------|---------------|-------------|
| Office                | 300 lux        | 500 lux       | 750 lux     |
| Classroom             | 300 lux        | 500 lux       | 750 lux     |
| Hospital ward         | 300 lux        | 500 lux       | 750 lux     |
| Residential living    | 300 lux        | 500 lux       | 750 lux     |
| Residential kitchen   | 300 lux        | 500 lux       | 750 lux     |
| Residential bedroom   | 200 lux        | 300 lux       | 500 lux     |
| Circulation (corridor)| 100 lux        | 200 lux       | 300 lux     |

### Aspect 2: View Out

Evaluates the quality of the view from occupied spaces:
- **View distance layer**: External features > 6 m away (buildings, landscape).
- **View content**: Ground, sky, and landscape should all be visible.
- **View width**: Horizontal angle of view to the outside >= 14° (minimum),
  >= 28° (medium), >= 54° (high).
- **Window position**: View should be available from seated work positions.

### Aspect 3: Sunlight Exposure

The space should receive direct sunlight for a minimum number of hours:
- **Minimum**: 1.5 hours on a reference date (typically March 21 or a date with
  equivalent solar altitude).
- **Medium**: 3.0 hours.
- **High**: 4.0 hours.
- At least one point in the room must receive these hours.

### Aspect 4: Glare Protection

- Glare protection must be available when DGP > 0.45 (intolerable) or DGP > 0.40
  (disturbing, for higher recommendation levels).
- Automated or manual blinds must be capable of reducing DGP below the threshold.
- Evaluation at the worst-case position and time.

---

## 3. BREEAM Hea 01: Visual Comfort

### Requirements

BREEAM (Building Research Establishment Environmental Assessment Method) awards
credits for daylight under Hea 01: Visual Comfort.

**Prerequisite (1 credit):**
- Glare control provided on all windows in relevant building areas.
- Minimum view-of-sky criterion: 80% of workplane area has a direct line of sight
  to a patch of sky from the desk height.

**Daylight Factor (2 credits):**

| Space type         | Average DF   | Minimum point DF | Uniformity ratio |
|--------------------|-------------|-------------------|------------------|
| Office (general)   | >= 2.0%     | >= 0.8%           | >= 0.4           |
| Office (cellular)  | >= 1.5%     | >= 0.6%           | >= 0.4           |
| Education          | >= 2.0%     | >= 0.8%           | >= 0.4           |
| Residential living | >= 1.5%     | >= 0.5%           | >= 0.3           |
| Residential kitchen| >= 1.5%     | >= 0.5%           | >= 0.3           |
| Retail (general)   | >= 2.0%     | >= 0.8%           | >= 0.4           |
| Hospital ward      | >= 2.0%     | >= 0.8%           | >= 0.4           |

**Additional credits:**
- 3 credits: Average DF >= 3.0% in 80% of relevant spaces.
- View out: occupied spaces within 8 m of a window with a view.

### Calculation Method

BREEAM accepts:
- BRE Digest 309 method (manual calculation for simple rooms).
- CIE overcast sky simulation (Radiance or other validated engine).
- DF is calculated under CIE standard overcast sky (type 16 sky model in Radiance).
- Analysis grid at workplane height (0.7 m for desks, 0.85 m for counters).

---

## 4. Radiance Material Database

### Opaque Materials (Plastic Primitive)

The Radiance `plastic` material type is defined by RGB reflectance, specularity,
and roughness. For daylight simulation, the weighted average reflectance is used:
R_avg = 0.265 * R_red + 0.670 * R_green + 0.065 * R_blue

| Material                       | R_red | R_green | R_blue | Specularity | Roughness | Weighted R |
|--------------------------------|-------|---------|--------|-------------|-----------|------------|
| White paint (high quality)     | 0.85  | 0.85    | 0.85   | 0.00        | 0.00      | 0.85       |
| White paint (standard)         | 0.70  | 0.70    | 0.70   | 0.00        | 0.00      | 0.70       |
| Off-white / cream paint        | 0.65  | 0.62    | 0.52   | 0.00        | 0.00      | 0.60       |
| Light grey paint               | 0.50  | 0.50    | 0.50   | 0.00        | 0.00      | 0.50       |
| Medium grey paint              | 0.35  | 0.35    | 0.35   | 0.00        | 0.00      | 0.35       |
| Dark grey paint                | 0.20  | 0.20    | 0.20   | 0.00        | 0.00      | 0.20       |
| Black paint                    | 0.05  | 0.05    | 0.05   | 0.00        | 0.00      | 0.05       |
| White ceiling tile             | 0.80  | 0.80    | 0.80   | 0.00        | 0.00      | 0.80       |
| Acoustic ceiling (perforated)  | 0.65  | 0.65    | 0.65   | 0.00        | 0.00      | 0.65       |
| Concrete (raw, light)          | 0.40  | 0.38    | 0.35   | 0.00        | 0.05      | 0.38       |
| Concrete (raw, dark)           | 0.28  | 0.26    | 0.24   | 0.00        | 0.05      | 0.26       |
| Red brick                      | 0.28  | 0.15    | 0.10   | 0.00        | 0.03      | 0.18       |
| Yellow brick                   | 0.45  | 0.40    | 0.25   | 0.00        | 0.03      | 0.39       |
| Sandstone                      | 0.50  | 0.42    | 0.30   | 0.00        | 0.03      | 0.43       |
| Granite (grey)                 | 0.30  | 0.30    | 0.30   | 0.02        | 0.02      | 0.30       |
| Marble (white)                 | 0.70  | 0.70    | 0.68   | 0.05        | 0.01      | 0.70       |
| Timber (light oak)             | 0.45  | 0.35    | 0.22   | 0.02        | 0.02      | 0.36       |
| Timber (dark walnut)           | 0.22  | 0.15    | 0.10   | 0.02        | 0.02      | 0.16       |
| Timber (pine, clear)           | 0.55  | 0.45    | 0.30   | 0.02        | 0.02      | 0.46       |
| Carpet (light beige)           | 0.35  | 0.32    | 0.25   | 0.00        | 0.00      | 0.32       |
| Carpet (medium grey)           | 0.20  | 0.20    | 0.20   | 0.00        | 0.00      | 0.20       |
| Carpet (dark blue)             | 0.08  | 0.10    | 0.18   | 0.00        | 0.00      | 0.10       |
| Linoleum (light)               | 0.45  | 0.42    | 0.35   | 0.01        | 0.01      | 0.42       |
| Vinyl flooring (grey)          | 0.30  | 0.30    | 0.30   | 0.01        | 0.01      | 0.30       |
| Polished concrete floor        | 0.35  | 0.35    | 0.35   | 0.03        | 0.01      | 0.35       |
| Metal panel (white coated)     | 0.75  | 0.75    | 0.75   | 0.03        | 0.01      | 0.75       |
| Metal panel (dark grey)        | 0.25  | 0.25    | 0.25   | 0.05        | 0.02      | 0.25       |
| Aluminum (brushed)             | 0.60  | 0.60    | 0.60   | 0.50        | 0.05      | 0.60       |
| Aluminum (anodized, dark)      | 0.20  | 0.20    | 0.20   | 0.30        | 0.03      | 0.20       |
| Grass / vegetation             | 0.15  | 0.25    | 0.08   | 0.00        | 0.00      | 0.21       |
| Asphalt                        | 0.10  | 0.10    | 0.10   | 0.00        | 0.00      | 0.10       |
| Concrete paving                | 0.30  | 0.30    | 0.28   | 0.00        | 0.02      | 0.30       |
| Water (diffuse approximation)  | 0.05  | 0.08    | 0.12   | 0.00        | 0.00      | 0.07       |

### Glazing Materials (Glass/Trans Primitive)

| Glazing type                    | Tvis  | SHGC  | U-value (W/m²K) | Radiance type |
|--------------------------------|-------|-------|------------------|---------------|
| Clear single (6mm)             | 0.88  | 0.82  | 5.8              | glass         |
| Clear double (6/12/6 air)      | 0.78  | 0.70  | 2.8              | glass         |
| Clear double (6/12/6 argon)    | 0.78  | 0.70  | 2.5              | glass         |
| Low-e double (hard coat)       | 0.72  | 0.55  | 1.8              | glass         |
| Low-e double (soft coat)       | 0.65  | 0.40  | 1.4              | glass         |
| Low-e double (high perf.)      | 0.55  | 0.30  | 1.1              | glass         |
| Low-e triple (argon)           | 0.55  | 0.35  | 0.8              | glass         |
| Low-e triple (krypton)         | 0.52  | 0.30  | 0.6              | glass         |
| Tinted bronze double           | 0.42  | 0.45  | 2.8              | glass         |
| Tinted grey double             | 0.38  | 0.40  | 2.8              | glass         |
| Reflective silver              | 0.15  | 0.18  | 1.6              | glass         |
| Electrochromic (clear state)   | 0.60  | 0.45  | 1.4              | glass         |
| Electrochromic (tinted state)  | 0.05  | 0.09  | 1.4              | glass         |
| Translucent panel (Kalwall)    | 0.20  | 0.22  | 1.5              | trans         |
| Fritted glass (50% frit)       | 0.35  | 0.30  | 1.6              | trans         |
| Etched/sandblasted glass       | 0.70  | 0.60  | 2.8              | trans         |

For Radiance `glass` material, transmissivity (tn) is derived from transmittance (T):
tn = (sqrt(0.8402528435 + 0.0072522239 * T * T) - 0.9166530661) / 0.0036261119 / T

---

## 5. Simulation Setup Checklist

### Pre-Simulation Verification

Use this checklist before running any daylight simulation to ensure valid results:

**Geometry:**
- [ ] All rooms are fully enclosed (no gaps between surfaces).
- [ ] Floor, walls, and ceiling surfaces are correctly oriented (normals facing inward).
- [ ] Window surfaces are coplanar with and contained within wall surfaces.
- [ ] Window frames are modeled or accounted for (reduce glazed area by 15–30%).
- [ ] Interior partitions and core walls are included.
- [ ] Furniture and major obstructions are modeled (for detailed analysis).
- [ ] External context buildings included within 200 m radius (minimum 60 m for LEED).
- [ ] Ground plane extends beyond the context model.
- [ ] No duplicate or overlapping surfaces.

**Materials:**
- [ ] All surfaces have assigned Radiance modifiers (no default materials).
- [ ] Reflectance values verified against actual specifications.
- [ ] Glazing transmittance matches product data or IGDB entry.
- [ ] Ground reflectance set appropriately (0.2 for grass, 0.3 for concrete, 0.1 for asphalt).
- [ ] Specular and rough surfaces identified and assigned correctly.

**Analysis Grid:**
- [ ] Grid height set to workplane height (0.762 m for LEED, 0.7 m for BREEAM).
- [ ] Grid spacing <= 0.61 m for LEED compliance, <= 0.5 m recommended.
- [ ] Grid boundary set to regularly occupied area only (exclude circulation, storage).
- [ ] Grid inset from walls by at least 0.3 m (sensor at wall is not meaningful).
- [ ] Total sensor count is manageable (< 50,000 for annual simulation on typical hardware).

**Sky Model:**
- [ ] CIE overcast sky for daylight factor analysis.
- [ ] Climate-based sky (Perez) for annual simulation (sDA, ASE, UDI).
- [ ] Correct EPW weather file for project location.
- [ ] EPW file reviewed for data quality (no missing radiation data).

**Radiance Parameters:**
- [ ] Ambient bounces (-ab) >= 2 for simple rooms, >= 5 for complex interiors.
- [ ] Ambient divisions (-ad) >= 1024 for production quality.
- [ ] Ambient accuracy (-aa) <= 0.15 for final results.
- [ ] Direct sampling parameters adequate for glazing complexity.

**Simulation Period:**
- [ ] Occupied hours defined correctly (e.g., 8 AM–6 PM weekdays for office).
- [ ] Full calendar year for annual metrics.
- [ ] Correct time zone offset in EPW file.

---

## 6. Annual Daylight Methods: 3-Phase and 5-Phase

### The Need for Matrix Methods

Direct Radiance ray-tracing for each of the 4,380 occupied hours in a year would
require thousands of CPU-hours for a single room. Matrix methods decompose the light
transport into reusable components, reducing annual simulation to minutes.

### 3-Phase Method

The 3-phase method splits the daylight path into three segments:

```
Illuminance = V * T * D * s
```

Where:
- **V (View matrix)**: Maps light from the interior side of the window to the sensor
  points. Computed once by shooting rays from sensors toward the window group. Size:
  [n_sensors x n_window_patches].

- **T (Transmission matrix)**: Describes the bidirectional transmission of the
  window system. For clear glass, this is a diagonal matrix. For complex fenestration
  (blinds, prismatic film, light shelves), T is a BSDF (Bidirectional Scattering
  Distribution Function) matrix. Size: [n_window_patches x n_sky_patches].

- **D (Daylight matrix)**: Maps light from the sky hemisphere to the exterior side
  of the window. Computed once by shooting rays from the window group toward the sky.
  Size: [n_window_patches x n_sky_patches].

- **s (Sky vector)**: The luminance of each sky patch for a given hour, derived from
  EPW weather data using the Perez sky model. Size: [n_sky_patches x 1]. The
  Tregenza sky subdivision has 145 patches (+ 1 ground).

**Workflow:**
1. Subdivide the sky hemisphere into 145 Tregenza patches.
2. Compute V matrix: trace rays from each sensor to each window patch.
3. Compute D matrix: trace rays from each window patch to each sky patch.
4. Define T matrix: clear glass = diagonal, complex = measured BSDF.
5. For each hour: look up sky vector s, multiply V * T * D * s.
6. Annual result: 8,760 illuminance values per sensor, computed in seconds.

**Advantages:**
- Extremely fast for annual simulation once matrices are computed.
- Easy to swap window systems (just change T matrix).
- Handles complex fenestration (BSDFs from WINDOW 7 or genBSDF).

**Limitations:**
- Treats direct sun the same as diffuse sky — distributes direct sun across the
  sky patch containing the sun, smearing it over ~6° of sky. This underestimates
  direct sun illuminance and glare. Not accurate for ASE calculation.

### 5-Phase Method

The 5-phase method improves upon the 3-phase method by separating the direct solar
contribution:

```
Illuminance = (V * T * D * s) - (V * Td * Dd * sd) + (V * Td * Cd * sd)
```

Where the additional terms are:
- **Td**: Direct-only transmission matrix (BSDF direct component only).
- **Dd**: Direct daylight matrix (sun-only, no sky diffuse).
- **sd**: Direct sun sky vector (only the sun patch is non-zero).
- **Cd**: Direct sun coefficient matrix (high-resolution sun-to-sensor contribution
  computed with many more sun positions than sky patches).

The subtraction removes the low-resolution direct sun contribution from the 3-phase
result, and the addition replaces it with a high-resolution direct sun calculation.

**When to use 5-phase:**
- ASE calculation (requires accurate direct sun tracking).
- Glare analysis with DGP.
- Any analysis where direct sunlight penetration pattern matters.
- Spaces with complex fenestration where direct sun behavior is critical.

**When 3-phase is sufficient:**
- Diffuse daylight metrics (DF, sDA in overcast-dominated climates).
- Comparative studies where relative performance matters more than absolute values.
- Early-design studies where speed is more important than direct-sun accuracy.

---

## 7. Glare Analysis Methodology

### Daylight Glare Probability (DGP)

DGP is the primary metric for evaluating glare from daylight. It is computed from
a high-dynamic-range (HDR) fisheye image of the visual field using Evalglare.

**DGP formula (simplified):**
DGP = c1 * Ev + c2 * log(1 + sum(Ls_i² * omega_s_i / (Ev * P_i²))) + c3

Where:
- Ev = vertical eye illuminance (lux)
- Ls_i = luminance of glare source i (cd/m²)
- omega_s_i = solid angle of glare source i (sr)
- P_i = position index of glare source i (Guth position index)
- c1, c2, c3 = regression coefficients

### DGP Thresholds

| DGP value   | Category      | Description                                  |
|-------------|---------------|----------------------------------------------|
| < 0.35      | Imperceptible | No glare discomfort. Ideal.                  |
| 0.35–0.38   | Perceptible   | Glare is noticed but not disturbing.          |
| 0.38–0.40   | Noticeable    | Transition zone. Some occupants may complain. |
| 0.40–0.45   | Disturbing    | Glare causes discomfort. Shading recommended. |
| > 0.45      | Intolerable   | Glare is unacceptable. Shading mandatory.     |

### Evaluation Positions

Glare must be evaluated from the occupant's actual viewpoint:

- **Position**: Seated at desk, eyes at 1.2 m above floor (for standard desk).
  Standing: 1.5 m. Reclined (auditorium): 1.0 m.
- **View direction**: Toward the task (typically toward the computer screen, which
  is usually facing the window or at 90° to the window).
- **Critical orientations**: Directly facing a window, especially south-facing
  (northern hemisphere) or east/west-facing during morning/afternoon.
- **Critical times**: Low sun angles — morning (east), late afternoon (west),
  winter midday (south). Equinox dates often produce worst-case conditions.

### Annual Glare Analysis

Rather than evaluating glare at a single point in time, annual glare analysis
computes DGP for all occupied hours and reports:

- **DGPexceed,5%**: The DGP value exceeded for no more than 5% of occupied hours.
  Should be < 0.40 for most applications.
- **DGP frequency distribution**: Histogram showing percentage of occupied hours
  in each DGP category.
- **Spatial DGP map**: Maximum or 95th-percentile DGP at multiple viewpoints
  across the floor plan.

### Glare Mitigation Strategies

| Strategy                    | Effectiveness | Impact on daylight | Cost      |
|----------------------------|---------------|-------------------|-----------|
| External horizontal overhang| High (south) | Moderate reduction| Medium    |
| External vertical fins      | High (E/W)   | Moderate reduction| Medium    |
| Internal roller blind       | High          | Significant reduction| Low    |
| Automated venetian blind    | Very high     | Adjustable        | High      |
| Fritted glass (ceramic dots)| Medium-High   | Fixed reduction   | Medium    |
| Electrochromic glazing      | Very high     | Adjustable        | Very high |
| Light shelf                 | Medium        | Improves deep light| Medium   |
| Light-redirecting film      | Medium        | Redirects, not blocks| Medium |
| Interior partition (glass)  | Low           | Minimal           | Low       |

---

## 8. Daylight Design Rules of Thumb

These rules of thumb provide quick guidance for early design decisions. They are
approximations and should always be verified with simulation for final design.

### Window-to-Floor Area Ratio (WFR)

| Target DF   | Required WFR (single-sided) | Notes                        |
|-------------|----------------------------|------------------------------|
| 1% average  | 10–15%                     | Minimum for habitable space  |
| 2% average  | 15–25%                     | Standard daylight level      |
| 3% average  | 25–35%                     | Good daylight level          |
| 5% average  | 35–50%                     | Excellent daylight level     |

WFR = total window area / total floor area (for the rooms served by those windows).

### Room Depth

Maximum effective daylight penetration depth depends on window head height and room
surface reflectances:

**Rule of thumb (single-sided daylighting):**
- Maximum depth for 2% DF at back wall: d <= 2.5 * h_window_head
- For better performance: d <= 2.0 * h_window_head
- With light shelf: effective depth increases by 30–50%
- Bilateral daylighting (windows on two sides): effective depth doubles

**Example:**
- Window head height: 2.7 m (standard office, floor-to-ceiling - 0.3 m sill)
- Maximum depth for 2% DF: 2.5 * 2.7 = 6.75 m from facade
- For 1% DF: depth can reach 8–10 m
- Typical open office depth: 12–15 m — core zone will not achieve 2% DF

### Clerestory and Toplighting

- Clerestory windows illuminate the back of deep spaces. Position at 2.4 m+ above
  floor. Tilt reflective ceiling surface to redirect light downward.
- Skylights: spacing = 1.0 to 1.5 times floor-to-skylight height for even distribution.
- Skylight-to-floor ratio: 3–5% for 2% DF equivalent.
- North-facing clerestories avoid direct sun and provide even diffuse light.

### Sill Height and Head Height

- **Sill height**: 0.0 m (floor-to-ceiling) maximizes daylight but causes glare
  and furniture conflicts. 0.75–0.9 m (desk height) is practical for offices.
- **Head height**: Higher is better for daylight penetration. Every 0.1 m of
  additional head height extends daylight penetration by approximately 0.25 m.
- **Transom window**: Adding a transom above a door or above a standard window
  head height pushes daylight deeper into the room.

### Reflectance Targets

For good daylight distribution, maintain high surface reflectances:

| Surface  | Minimum reflectance | Recommended reflectance |
|----------|--------------------|-----------------------|
| Ceiling  | 0.70               | 0.80–0.90             |
| Walls    | 0.40               | 0.50–0.70             |
| Floor    | 0.15               | 0.20–0.40             |
| Furniture| 0.25               | 0.30–0.50             |

Dark surfaces absorb light and prevent it from bouncing deeper into the room. A
room with dark walls and floors requires 30–50% more window area to achieve the
same daylight factor as a room with light surfaces.

---

## 9. Case Studies: Daylight Optimization Results

### Case Study 1: Open Office Floor Plate Optimization

**Context:** 15 m deep open office floor, south-facing facade, moderate urban context.

**Variables optimized:**
- WWR: 30% to 70% (5% increments)
- External overhang depth: 0 to 1.5 m (0.25 m increments)
- Glazing type: clear double (Tvis 0.78), low-e double (Tvis 0.65), high-perf low-e (Tvis 0.55)

**Findings:**
- sDA increased with WWR up to 55%, then plateaued as core zone remained unlit regardless.
- ASE exceeded 10% threshold at WWR > 45% without shading.
- Optimal combination: WWR 50%, overhang 0.75 m, low-e double glazing.
  - sDA = 62% (passes LEED 2-point threshold)
  - ASE = 8.5% (passes LEED < 10% requirement)
- Adding a 0.5 m light shelf increased sDA to 68% with no ASE penalty.
- Switching to high-performance low-e reduced ASE to 5% but dropped sDA to 54%.

### Case Study 2: Residential Tower Unit Daylighting

**Context:** 8 m deep residential unit, east-facing, dense urban context (adjacent
tower 20 m away at 45° angle from facade center).

**Variables optimized:**
- Window sill height: 0 m (floor-to-ceiling) to 0.9 m
- Glazing Tvis: 0.55 to 0.78
- Interior surface reflectance: base case (ceiling 0.70, walls 0.50, floor 0.20)
  vs. optimized (ceiling 0.85, walls 0.65, floor 0.35)

**Findings:**
- Floor-to-ceiling glazing (sill 0 m) improved sDA by 15% over sill 0.9 m.
- Optimized reflectances improved sDA by 22% — the single most impactful change.
- Increasing Tvis from 0.55 to 0.78 improved sDA by 18% but increased ASE by 12%.
- Best combination: sill 0.3 m, Tvis 0.65, optimized reflectances.
  - sDA = 58% (acceptable for residential)
  - ASE = 6% (comfortable)
  - The adjacent tower reduced available daylight by approximately 35% compared
    to an unobstructed scenario.

### Case Study 3: Classroom Bilateral Daylighting

**Context:** 9 m wide x 7 m deep classroom, north and south windows, suburban setting.

**Variables optimized:**
- North WWR: 20–50%
- South WWR: 20–60%
- South overhang depth: 0–1.2 m
- Ceiling reflectance: 0.70 vs. 0.85

**Findings:**
- Bilateral daylighting achieved sDA > 75% across the classroom — a dramatic
  improvement over single-sided.
- South-facing glare (ASE) was the binding constraint. Without shading, ASE
  exceeded 30% in the first two rows of desks.
- Optimal: South WWR 40% with 0.9 m overhang, North WWR 35%, ceiling 0.85.
  - sDA = 82% (exceeds LEED 3-point threshold)
  - ASE = 7% (below 10% limit)
  - Uniformity ratio = 0.45 (good)
- Adding operable blinds modeled as deployed when direct sun exceeds 300 W/m²
  on glass reduced ASE to 3% while only reducing sDA to 78%.

---

## 10. Troubleshooting Guide

### Simulation Produces Unrealistically High Daylight Values

**Possible causes:**
1. Missing context buildings — the model acts as if the building is in an open field.
2. Ground reflectance set too high (default 0.5 in some tools vs. realistic 0.2).
3. Surface reflectances not assigned (default may be 0.5 for all surfaces).
4. Model geometry has gaps allowing light to "leak" through walls.
5. Radiance -ab (ambient bounces) set too low — can sometimes cause artifacts that
   appear as bright spots, though more commonly this causes values that are too low.

### Simulation Produces Unrealistically Low Daylight Values

**Possible causes:**
1. Glazing transmittance not assigned or set to opaque.
2. Radiance -ab too low — insufficient inter-reflections make rooms appear darker.
3. Window normals facing the wrong direction (outward instead of inward).
4. Analysis grid placed below floor level or above window head.
5. Wrong sky model — using CIE overcast for a sunny climate (appropriate for DF but
   not for absolute illuminance prediction).
6. Missing ground plane — no ground reflection contribution.

### ASE Exceeds 10% Despite Shading

**Possible causes:**
1. Shading is modeled but not deep enough for the sun angles that cause exceedance.
2. East/west facades receive low-angle sun that horizontal shading cannot block.
3. The 250-hour threshold is cumulative — even brief daily sun penetration adds up.
4. Ground-reflected sunlight enters through lower windows (overlooked contribution).
5. Adjacent buildings with reflective facades redirect sunlight into the space.

### sDA and ASE Appear Contradictory

It is possible to have low sDA (insufficient daylight) and high ASE (too much direct
sun) simultaneously. This occurs when:
- The floor plate is very deep and only the perimeter receives adequate daylight (low sDA),
  but the perimeter is blasted with direct sun for part of the year (high ASE at perimeter).
- The solution is not to add more glass but to better distribute existing daylight
  through light shelves, higher ceilings, and optimized surface reflectances.
