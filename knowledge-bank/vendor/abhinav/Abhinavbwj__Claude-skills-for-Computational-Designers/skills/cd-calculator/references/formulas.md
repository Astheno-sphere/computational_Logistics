# Computational Design Calculator - Formula Reference

Complete mathematical reference for all seven calculators. Every formula is sourced from published engineering standards and textbooks. Variables use consistent notation throughout.

---

## 1. Geometry Formulas

### 1.1 Rectangle

| Property | Formula |
|----------|---------|
| Area | A = b * h |
| Perimeter | P = 2(b + h) |
| Centroid | (b/2, h/2) |
| Moment of Inertia Ix | Ix = (b * h^3) / 12 |
| Moment of Inertia Iy | Iy = (h * b^3) / 12 |
| Section Modulus Sx | Sx = (b * h^2) / 6 |
| Section Modulus Sy | Sy = (h * b^2) / 6 |
| Radius of Gyration rx | rx = h / sqrt(12) |
| Radius of Gyration ry | ry = b / sqrt(12) |

### 1.2 Circle

| Property | Formula |
|----------|---------|
| Area | A = pi * r^2 |
| Perimeter | P = 2 * pi * r |
| Centroid | (r, r) relative to bounding box; (0, 0) relative to center |
| Moment of Inertia Ix = Iy | I = (pi * r^4) / 4 |
| Section Modulus Sx = Sy | S = (pi * r^3) / 4 |
| Radius of Gyration rx = ry | rg = r / 2 |

### 1.3 Triangle (base b, height h, vertex at top center)

| Property | Formula |
|----------|---------|
| Area | A = (b * h) / 2 |
| Perimeter | P = b + s1 + s2 (computed from vertices) |
| Centroid | (b/2, h/3) from base |
| Moment of Inertia Ix | Ix = (b * h^3) / 36 |
| Moment of Inertia Iy | Iy = (h * b^3) / 48 |
| Section Modulus Sx | Sx = (b * h^2) / 24 |

### 1.4 I-Beam (Symmetric)

Given: total width b, total height h, flange thickness tf, web thickness tw.

| Property | Formula |
|----------|---------|
| Area | A = 2 * b * tf + (h - 2*tf) * tw |
| Centroid | (b/2, h/2) by symmetry |
| Ix | Ix = (b*h^3)/12 - ((b-tw)*(h-2*tf)^3)/12 |
| Iy | Iy = (2*tf*b^3)/12 + ((h-2*tf)*tw^3)/12 |
| Sx | Sx = Ix / (h/2) |
| Sy | Sy = Iy / (b/2) |

### 1.5 Hollow Rectangle (RHS)

Given: outer width b, outer height h, wall thickness t.

| Property | Formula |
|----------|---------|
| Area | A = b*h - (b-2t)*(h-2t) |
| Centroid | (b/2, h/2) by symmetry |
| Ix | Ix = (b*h^3)/12 - ((b-2t)*(h-2t)^3)/12 |
| Iy | Iy = (h*b^3)/12 - ((h-2t)*(b-2t)^3)/12 |
| Sx | Sx = Ix / (h/2) |
| Sy | Sy = Iy / (b/2) |

### 1.6 Hollow Circle (CHS)

Given: outer radius R, inner radius r.

| Property | Formula |
|----------|---------|
| Area | A = pi * (R^2 - r^2) |
| Centroid | (0, 0) at center |
| Ix = Iy | I = (pi/4) * (R^4 - r^4) |
| Sx = Sy | S = (pi/4) * (R^4 - r^4) / R |
| Radius of Gyration | rg = sqrt((R^2 + r^2) / 4) |

### 1.7 L-Shape (Equal Angle)

Given: width b, height h, leg thickness t. Origin at outer corner.

| Property | Formula |
|----------|---------|
| Area | A = t*(b + h - t) |
| Centroid x | cx = (b^2*t + (h-t)*t^2) / (2*A) |
| Centroid y | cy = (h^2*t + (b-t)*t^2) / (2*A) |
| Ix | Computed by composite section method |
| Iy | Computed by composite section method |

### 1.8 T-Shape

Given: flange width b, total height h, flange thickness tf, web thickness tw.

| Property | Formula |
|----------|---------|
| Area | A = b*tf + (h-tf)*tw |
| Centroid y | cy = (b*tf*(h-tf/2) + (h-tf)*tw*(h-tf)/2) / A |
| Ix | By parallel axis theorem on flange + web |

### 1.9 Arbitrary Polygon (Shoelace Formula)

Given n vertices (x_i, y_i) ordered counterclockwise:

| Property | Formula |
|----------|---------|
| Signed Area | A = 0.5 * sum(x_i * y_{i+1} - x_{i+1} * y_i) |
| Centroid x | cx = (1/(6A)) * sum((x_i + x_{i+1})(x_i*y_{i+1} - x_{i+1}*y_i)) |
| Centroid y | cy = (1/(6A)) * sum((y_i + y_{i+1})(x_i*y_{i+1} - x_{i+1}*y_i)) |
| Ix | Ix = (1/12) * sum((y_i^2 + y_i*y_{i+1} + y_{i+1}^2)(x_i*y_{i+1} - x_{i+1}*y_i)) |
| Iy | Iy = (1/12) * sum((x_i^2 + x_i*x_{i+1} + x_{i+1}^2)(x_i*y_{i+1} - x_{i+1}*y_i)) |

---

## 2. Structural Formulas

### 2.1 Steel Yield Strengths

| Grade | fy (MPa) | fu (MPa) |
|-------|----------|----------|
| S235 | 235 | 360 |
| S275 | 275 | 430 |
| S355 | 355 | 510 |
| S460 | 460 | 550 |

### 2.2 Bending Moment Formulas

**Simply Supported Beam:**

| Load Case | Max Moment | Location |
|-----------|-----------|----------|
| UDL (w kN/m) | M = w*L^2 / 8 | Midspan |
| Point load at center (P) | M = P*L / 4 | Midspan |
| Point load at a from left | M = P*a*(L-a) / L | At load point |
| Two point loads at thirds | M = P*L / 3 | Between loads |

**Cantilever:**

| Load Case | Max Moment | Location |
|-----------|-----------|----------|
| UDL (w kN/m) | M = w*L^2 / 2 | Fixed end |
| Point load at tip (P) | M = P*L | Fixed end |

**Fixed-Fixed Beam:**

| Load Case | Max Moment (at supports) | Midspan Moment |
|-----------|--------------------------|----------------|
| UDL (w kN/m) | M = w*L^2 / 12 | M = w*L^2 / 24 |
| Point load at center | M = P*L / 8 | M = P*L / 8 |

### 2.3 Shear Force Formulas

| Load Case (Simply Supported) | Max Shear |
|------------------------------|-----------|
| UDL (w kN/m) | V = w*L / 2 |
| Point load at center | V = P / 2 |
| Point load at a from left | V = P*(L-a)/L or P*a/L |

### 2.4 Deflection Formulas

**Simply Supported:**

| Load Case | Max Deflection |
|-----------|---------------|
| UDL | delta = 5*w*L^4 / (384*E*I) |
| Point load at center | delta = P*L^3 / (48*E*I) |

**Cantilever:**

| Load Case | Max Deflection |
|-----------|---------------|
| UDL | delta = w*L^4 / (8*E*I) |
| Point load at tip | delta = P*L^3 / (3*E*I) |

**Fixed-Fixed:**

| Load Case | Max Deflection |
|-----------|---------------|
| UDL | delta = w*L^4 / (384*E*I) |
| Point load at center | delta = P*L^3 / (192*E*I) |

Young's Modulus of Steel: E = 210,000 MPa (210 GPa)

### 2.5 Deflection Limits (Eurocode)

| Usage | Limit |
|-------|-------|
| General floors | L/250 |
| Floors with brittle finishes | L/360 |
| Roofs | L/200 |
| Cantilevers | L/125 (= 2 * L/250) |

### 2.6 Required Section Modulus

For bending: S_req = M / fy

Where:
- M is the maximum bending moment (N*mm)
- fy is the yield strength (MPa = N/mm^2)
- S_req is the required elastic section modulus (mm^3)

### 2.7 Euler Buckling Load

Critical buckling load for a column:

P_cr = (pi^2 * E * I) / (L_e)^2

Where:
- E = Young's modulus (MPa)
- I = minimum moment of inertia (mm^4)
- L_e = effective buckling length = k * L
- k = buckling length factor

| End Conditions | k |
|---------------|---|
| Pinned-Pinned | 1.0 |
| Fixed-Free | 2.0 |
| Fixed-Pinned | 0.7 |
| Fixed-Fixed | 0.5 |

### 2.8 Combined Stress Check (Simplified)

Utilization ratio (interaction formula):

U = (N / N_Rd) + (M / M_Rd) <= 1.0

Where:
- N = applied axial load
- N_Rd = axial resistance = A * fy
- M = applied moment
- M_Rd = moment resistance = S * fy

### 2.9 Common IPE Section Properties

| Section | h (mm) | b (mm) | tw (mm) | tf (mm) | A (mm^2) | Ix (mm^4) | Sx (mm^3) | Mass (kg/m) |
|---------|--------|--------|---------|---------|----------|-----------|-----------|-------------|
| IPE 200 | 200 | 100 | 5.6 | 8.5 | 2,850 | 19,430,000 | 194,300 | 22.4 |
| IPE 220 | 220 | 110 | 5.9 | 9.2 | 3,340 | 27,720,000 | 252,000 | 26.2 |
| IPE 240 | 240 | 120 | 6.2 | 9.8 | 3,910 | 38,920,000 | 324,300 | 30.7 |
| IPE 270 | 270 | 135 | 6.6 | 10.2 | 4,590 | 57,900,000 | 429,000 | 36.1 |
| IPE 300 | 300 | 150 | 7.1 | 10.7 | 5,380 | 83,560,000 | 557,100 | 42.2 |
| IPE 330 | 330 | 160 | 7.5 | 11.5 | 6,260 | 117,700,000 | 713,100 | 49.1 |
| IPE 360 | 360 | 170 | 8.0 | 12.7 | 7,270 | 162,700,000 | 904,000 | 57.1 |
| IPE 400 | 400 | 180 | 8.6 | 13.5 | 8,450 | 231,300,000 | 1,156,000 | 66.3 |
| IPE 450 | 450 | 190 | 9.4 | 14.6 | 9,880 | 337,400,000 | 1,500,000 | 77.6 |
| IPE 500 | 500 | 200 | 10.2 | 16.0 | 11,550 | 482,000,000 | 1,928,000 | 90.7 |
| IPE 550 | 550 | 210 | 11.1 | 17.2 | 13,440 | 671,200,000 | 2,441,000 | 105.5 |
| IPE 600 | 600 | 220 | 12.0 | 19.0 | 15,600 | 920,800,000 | 3,069,000 | 122.4 |

---

## 3. Solar Formulas

### 3.1 Solar Declination (Spencer, 1971)

Day angle: B = (360/365) * (n - 81) degrees, where n = day of year.

Declination: delta = 23.45 * sin(B)

More precise (Fourier series):
delta = 0.3963723 - 22.9132745*cos(B) + 4.0254304*sin(B) - 0.3872050*cos(2B) + 0.05196728*sin(2B)

### 3.2 Hour Angle

omega = 15 * (solar_time - 12) degrees

Where solar_time is in hours (0-24). Each hour = 15 degrees. Negative before noon, positive after.

### 3.3 Solar Altitude Angle

sin(alpha) = sin(phi)*sin(delta) + cos(phi)*cos(delta)*cos(omega)

Where:
- alpha = solar altitude angle (0 = horizon, 90 = zenith)
- phi = latitude
- delta = declination
- omega = hour angle

### 3.4 Solar Azimuth Angle

cos(A_s) = (sin(alpha)*sin(phi) - sin(delta)) / (cos(alpha)*cos(phi))

Convention: 0 = North, 90 = East, 180 = South, 270 = West (in Northern Hemisphere).

For the correct quadrant, use atan2:
A_s = atan2(-sin(omega)*cos(delta), cos(phi)*sin(delta) - sin(phi)*cos(delta)*cos(omega))

### 3.5 Sunrise and Sunset

Hour angle at sunrise/sunset:
cos(omega_s) = -tan(phi) * tan(delta)

Sunrise solar time = 12 - omega_s / 15
Sunset solar time = 12 + omega_s / 15
Day length = 2 * omega_s / 15 hours

### 3.6 Shadow Length

shadow_length = object_height / tan(alpha)

Shadow direction = azimuth + 180 degrees (opposite to sun direction)

### 3.7 Optimal PV Tilt Angle

Rule of thumb: optimal annual tilt = latitude (for fixed mount)

More precise monthly optimal:
tilt = phi - delta (summer: flatter; winter: steeper)

### 3.8 Radiation on Tilted Surface (Liu & Jordan)

R_b = cos(theta) / cos(theta_z)

Where:
- theta = angle of incidence on tilted surface
- theta_z = zenith angle = 90 - alpha
- cos(theta) = sin(delta)*sin(phi-beta) + cos(delta)*cos(omega)*cos(phi-beta)
- beta = tilt angle from horizontal

Total radiation on tilted surface:
I_T = I_b*R_b + I_d*(1+cos(beta))/2 + I*rho*(1-cos(beta))/2

Where:
- I_b = beam (direct) radiation
- I_d = diffuse radiation
- I = global horizontal radiation
- rho = ground reflectance (albedo, typically 0.2)

### 3.9 Approximate Annual Solar Radiation

Global horizontal irradiance (simplified model):
GHI_annual ~ GHI_0 * clearness_index

Where GHI_0 is extraterrestrial radiation and clearness_index varies by climate:
- Clear/arid: 0.65 - 0.75
- Temperate: 0.45 - 0.55
- Cloudy/maritime: 0.35 - 0.45

Extraterrestrial radiation on horizontal:
H_0 = (24/pi) * I_sc * E_0 * (cos(phi)*cos(delta)*sin(omega_s) + (pi*omega_s/180)*sin(phi)*sin(delta))

Where I_sc = 1367 W/m^2 (solar constant), E_0 = eccentricity correction.

---

## 4. Mesh Formulas

### 4.1 Euler Characteristic

chi = V - E + F

Where:
- V = number of vertices
- E = number of edges
- F = number of faces
- For a closed orientable surface: chi = 2 - 2g (g = genus)

### 4.2 Genus Calculation

g = (2 - chi) / 2 = (2 - V + E - F) / 2

For a mesh with boundary: chi = 2 - 2g - b, where b = number of boundary loops.

### 4.3 Edge Count from Faces (Triangle Mesh)

For a closed triangle mesh: E = 3F/2 (every edge shared by 2 faces)
For a mesh with boundary: E = (3F + boundary_edges) / 2

General: count unique unordered pairs (i,j) from all face edge lists.

### 4.4 Face Area (Triangle)

Given vertices A, B, C:
area = 0.5 * |AB x AC|

Where AB = B - A, AC = C - A, and x denotes cross product.

For a polygon face with n vertices, triangulate from first vertex:
area = sum of triangle areas (v0, v_i, v_{i+1}) for i in [1, n-1]

### 4.5 Face Normal

n = (AB x AC) / |AB x AC|

### 4.6 Aspect Ratio (Triangle)

aspect_ratio = longest_edge / shortest_altitude

Or equivalently: aspect_ratio = longest_edge * circumradius / (2 * area)

Ideal equilateral triangle: aspect_ratio = 1.155

Quality threshold: aspect_ratio > 3.0 is considered poor for FEA.

### 4.7 Manifold Check

A mesh is manifold if:
1. Every edge is shared by exactly 2 faces (interior) or 1 face (boundary)
2. The fan of faces around each vertex forms a single connected cycle (or arc for boundary vertices)

Non-manifold edges: edges shared by 3+ faces.
Non-manifold vertices: vertices whose face fan is disconnected.

### 4.8 Normal Consistency

For an orientable mesh, adjacent faces should have consistently oriented normals. Check: for each edge shared by two faces, the edge appears in opposite directions in the two face vertex lists.

### 4.9 Discrete Gaussian Curvature (Angle Deficit)

K_i = 2*pi - sum(theta_j)

Where theta_j are the interior angles of all faces meeting at vertex i.

For a boundary vertex: K_i = pi - sum(theta_j)

Gauss-Bonnet theorem: sum(K_i) = 2*pi*chi

### 4.10 Discrete Mean Curvature

H_i = (1 / (4*A_i)) * sum_j (cot(alpha_j) + cot(beta_j)) * (x_i - x_j)

Where the sum is over edges (i,j), alpha_j and beta_j are opposite angles, and A_i is the mixed Voronoi area at vertex i.

---

## 5. Material Estimation Formulas

### 5.1 Concrete Quantity

Volume: V_concrete = footprint_area * avg_thickness * floors (for slabs)
Plus columns, beams, walls, foundations.

Parametric estimate by building type:

| Building Type | Concrete (m^3 / m^2 GFA) | Notes |
|--------------|--------------------------|-------|
| Residential | 0.15 - 0.20 | Flat slab, shear walls |
| Office | 0.12 - 0.18 | Post-tensioned slabs |
| Industrial | 0.08 - 0.12 | Ground slab + footings |
| Retail | 0.10 - 0.15 | Flat slab, columns |

Weight: W_concrete = V * 2400 kg/m^3

### 5.2 Reinforcement Steel

Typical reinforcement ratios (kg/m^3 of concrete):

| Element | Ratio (kg/m^3) |
|---------|---------------|
| Slabs (flat) | 80 - 120 |
| Beams | 100 - 150 |
| Columns | 150 - 250 |
| Walls (shear) | 80 - 120 |
| Foundations | 60 - 100 |
| Overall average | 90 - 130 |

Weight: W_rebar = V_concrete * ratio

### 5.3 Structural Steel

Typical steel tonnage by building type:

| Building Type | Steel (kg/m^2 GFA) |
|--------------|-------------------|
| Residential (concrete frame) | 8 - 15 |
| Office (steel frame) | 30 - 50 |
| Office (composite) | 25 - 40 |
| Industrial (portal frame) | 20 - 35 |
| Retail (steel frame) | 25 - 40 |

### 5.4 Glass Quantity

Glass area ratio (to GFA):

| Building Type | Glass Ratio (m^2 glass / m^2 GFA) |
|--------------|-----------------------------------|
| Residential | 0.10 - 0.15 |
| Office | 0.20 - 0.40 |
| Retail | 0.15 - 0.25 |

Weight: W_glass = area * thickness * density (2500 kg/m^3)
For 6mm glass: ~15 kg/m^2
For 8mm glass: ~20 kg/m^2

Typical IGU (insulated glass unit): ~30 kg/m^2

### 5.5 Timber Quantity

| Building Type | Timber (m^3 / m^2 GFA) |
|--------------|------------------------|
| Timber-frame residential | 0.10 - 0.15 |
| CLT residential | 0.15 - 0.25 |
| Mixed structure | 0.02 - 0.05 |

Weight: W_timber = V * density
- Softwood (spruce/pine): 450 kg/m^3
- Hardwood (oak): 700 kg/m^3
- CLT: 480 kg/m^3
- Glulam: 460 kg/m^3

### 5.6 Waste Factors

| Material | Waste Factor | Notes |
|----------|-------------|-------|
| Concrete (in-situ) | 1.05 - 1.10 | Spillage, over-ordering |
| Concrete (precast) | 1.02 - 1.05 | Factory controlled |
| Steel (rebar) | 1.05 - 1.10 | Laps, wastage |
| Steel (structural) | 1.03 - 1.05 | Off-cuts |
| Glass | 1.05 - 1.10 | Breakage, cutting |
| Timber | 1.10 - 1.15 | Off-cuts, defects |
| Brickwork | 1.05 - 1.08 | Breakage |

### 5.7 Embodied Carbon Factors

| Material | kgCO2e per unit | Unit |
|----------|----------------|------|
| Concrete (C30/37) | 250 | per m^3 |
| Concrete (C40/50) | 320 | per m^3 |
| Rebar steel | 1,500 | per tonne |
| Structural steel | 1,500 | per tonne |
| Glass (float) | 1,100 | per tonne |
| Glass (IGU) | 55 | per m^2 |
| Timber (softwood) | -450 | per m^3 (carbon stored) |
| CLT | -500 | per m^3 (carbon stored) |
| Glulam | -480 | per m^3 (carbon stored) |
| Aluminum | 8,200 | per tonne |
| Brick | 230 | per tonne |

Source: ICE Database (Inventory of Carbon and Energy), University of Bath.

---

## 6. Fabrication Formulas

### 6.1 CNC Milling Time

Total time = setup_time + cutting_time + tool_change_time

- cutting_time = path_length / feed_rate
- tool_change_time = num_changes * time_per_change
- setup_time (typical): 10-20 minutes

Default feed rates by material:

| Material | Feed Rate (mm/min) | Notes |
|----------|-------------------|-------|
| Softwood | 3,000 - 5,000 | Depends on cutter, depth |
| Hardwood | 2,000 - 3,500 | |
| MDF | 3,000 - 6,000 | |
| Plywood | 2,500 - 4,000 | |
| Acrylic | 1,000 - 2,000 | |
| Aluminum | 800 - 2,000 | |
| Mild Steel | 200 - 600 | |
| Foam (EPS) | 5,000 - 10,000 | |

Tool change time: typically 1-3 minutes per change.

### 6.2 3D Print Time (FDM)

Layers = print_height / layer_height

Time per layer = perimeter_time + infill_time + travel_time

Simplified estimation:
print_time = (volume * infill_factor) / volumetric_flow_rate + layers * layer_overhead

Where:
- infill_factor accounts for shells and internal structure
- volumetric_flow_rate = nozzle_area * print_speed (typically 1-5 mm^3/s for desktop FDM)
- layer_overhead = ~2-5 seconds (z-hop, retraction)

Material-specific print speeds:

| Material | Print Speed (mm/s) | Nozzle Temp (C) | Bed Temp (C) |
|----------|-------------------|-----------------|-------------|
| PLA | 50 - 80 | 190 - 220 | 50 - 60 |
| PETG | 40 - 60 | 220 - 250 | 70 - 80 |
| ABS | 40 - 60 | 230 - 260 | 90 - 110 |
| Nylon | 30 - 50 | 240 - 270 | 70 - 90 |
| TPU | 20 - 40 | 210 - 230 | 40 - 60 |

Material density and cost:

| Material | Density (g/cm^3) | Filament Cost ($/kg) |
|----------|-----------------|---------------------|
| PLA | 1.24 | 20 - 30 |
| PETG | 1.27 | 25 - 35 |
| ABS | 1.04 | 20 - 30 |
| Nylon | 1.14 | 40 - 60 |
| TPU | 1.21 | 35 - 50 |

### 6.3 Laser Cutting Time

cut_time = cut_length / cut_speed

Laser cut speeds by material and thickness:

| Material | Thickness (mm) | Speed (mm/min) | Power (W) |
|----------|---------------|----------------|-----------|
| Acrylic | 3 | 2,400 | 40 |
| Acrylic | 6 | 1,200 | 60 |
| Acrylic | 10 | 600 | 80 |
| Plywood | 3 | 3,000 | 40 |
| Plywood | 6 | 1,500 | 60 |
| Plywood | 9 | 800 | 80 |
| MDF | 3 | 2,500 | 40 |
| MDF | 6 | 1,200 | 60 |
| Cardboard | 1 | 6,000 | 30 |
| Cardboard | 3 | 3,500 | 40 |
| Steel (mild) | 1 | 3,000 | 500 (fiber) |
| Steel (mild) | 3 | 1,500 | 1000 (fiber) |
| Steel (mild) | 6 | 800 | 2000 (fiber) |
| Aluminum | 1 | 2,500 | 500 (fiber) |
| Aluminum | 3 | 1,000 | 1000 (fiber) |

Material cost per sheet (typical):

| Material | Sheet Size | Thickness | Cost ($) |
|----------|-----------|-----------|----------|
| Acrylic (clear) | 1200x600 mm | 3 mm | 15-25 |
| Acrylic (clear) | 1200x600 mm | 6 mm | 30-45 |
| Plywood (birch) | 1220x610 mm | 3 mm | 8-15 |
| Plywood (birch) | 1220x610 mm | 6 mm | 12-20 |
| MDF | 1220x610 mm | 3 mm | 5-10 |
| Cardboard | 1000x700 mm | 3 mm | 2-5 |

---

## 7. Unit Conversions

### 7.1 Length

| From | To | Multiply by |
|------|-----|------------|
| mm | m | 0.001 |
| mm | in | 0.03937 |
| mm | ft | 0.003281 |
| m | ft | 3.28084 |
| m | in | 39.3701 |
| in | mm | 25.4 |
| ft | m | 0.3048 |
| ft | mm | 304.8 |

### 7.2 Area

| From | To | Multiply by |
|------|-----|------------|
| mm^2 | m^2 | 1e-6 |
| mm^2 | in^2 | 0.00155 |
| m^2 | ft^2 | 10.7639 |
| m^2 | acres | 0.000247105 |
| ft^2 | m^2 | 0.092903 |
| in^2 | mm^2 | 645.16 |

### 7.3 Volume

| From | To | Multiply by |
|------|-----|------------|
| mm^3 | m^3 | 1e-9 |
| m^3 | ft^3 | 35.3147 |
| m^3 | liters | 1000 |
| m^3 | US gallons | 264.172 |
| cm^3 | in^3 | 0.061024 |
| ft^3 | m^3 | 0.028317 |

### 7.4 Force

| From | To | Multiply by |
|------|-----|------------|
| kN | N | 1000 |
| kN | lbf | 224.809 |
| kN | kip | 0.224809 |
| kip | kN | 4.44822 |
| lbf | N | 4.44822 |

### 7.5 Stress / Pressure

| From | To | Multiply by |
|------|-----|------------|
| MPa | N/mm^2 | 1 |
| MPa | psi | 145.038 |
| MPa | ksi | 0.145038 |
| MPa | kPa | 1000 |
| psi | MPa | 0.006895 |
| ksi | MPa | 6.89476 |

### 7.6 Moment of Inertia

| From | To | Multiply by |
|------|-----|------------|
| mm^4 | m^4 | 1e-12 |
| mm^4 | in^4 | 2.4025e-6 |
| in^4 | mm^4 | 416,231 |
| in^4 | cm^4 | 41.6231 |

### 7.7 Section Modulus

| From | To | Multiply by |
|------|-----|------------|
| mm^3 | m^3 | 1e-9 |
| mm^3 | in^3 | 6.1024e-5 |
| in^3 | mm^3 | 16,387.1 |
| in^3 | cm^3 | 16.3871 |

### 7.8 Mass / Weight

| From | To | Multiply by |
|------|-----|------------|
| kg | lb | 2.20462 |
| kg | tonne | 0.001 |
| tonne | kg | 1000 |
| tonne | US ton | 1.10231 |
| lb | kg | 0.453592 |

### 7.9 Temperature

| Conversion | Formula |
|-----------|---------|
| Celsius to Fahrenheit | F = C * 9/5 + 32 |
| Fahrenheit to Celsius | C = (F - 32) * 5/9 |
| Celsius to Kelvin | K = C + 273.15 |

### 7.10 Angle

| From | To | Multiply by |
|------|-----|------------|
| degrees | radians | pi / 180 |
| radians | degrees | 180 / pi |

### 7.11 Energy / Carbon

| From | To | Multiply by |
|------|-----|------------|
| kWh | MJ | 3.6 |
| MJ | kWh | 0.2778 |
| kWh | BTU | 3412.14 |
| tCO2e | kgCO2e | 1000 |

---

## Sources

1. Eurocode 3: Design of steel structures (EN 1993-1-1)
2. Eurocode 2: Design of concrete structures (EN 1992-1-1)
3. ASCE 7: Minimum Design Loads for Buildings
4. Duffie & Beckman, Solar Engineering of Thermal Processes, 4th ed.
5. ICE Database v3.0 (Inventory of Carbon and Energy), University of Bath
6. Botsch et al., Polygon Mesh Processing, AK Peters, 2010
7. ASHRAE Handbook: Fundamentals
8. Spencer, J.W. (1971), Fourier series representation of the position of the sun
9. Liu, B.Y.H. and Jordan, R.C. (1960), The interrelationship and characteristic distribution of direct, diffuse and total solar radiation
