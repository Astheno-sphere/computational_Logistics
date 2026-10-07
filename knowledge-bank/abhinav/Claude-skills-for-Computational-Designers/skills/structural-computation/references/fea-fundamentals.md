# Finite Element Analysis Fundamentals — Deep Reference

## 1. Stiffness Matrix Derivation

### 1.1 Truss Element (1D Axial)

A truss element connects two nodes and carries only axial force (tension or compression). Each node has translational DOFs only.

**2D Truss Element** (4 DOFs: u1, v1, u2, v2):

Local stiffness matrix (along the element axis):
```
[k_local] = (EA/L) * [ 1   0  -1   0 ]
                      [ 0   0   0   0 ]
                      [-1   0   1   0 ]
                      [ 0   0   0   0 ]
```

Transformation to global coordinates using angle theta (element orientation):
```
[T] = [ cos(theta)  sin(theta)   0           0         ]
      [-sin(theta)  cos(theta)   0           0         ]
      [ 0           0            cos(theta)  sin(theta) ]
      [ 0           0           -sin(theta)  cos(theta) ]

[k_global] = [T]^T * [k_local] * [T]
```

Expanded global stiffness matrix:
```
[k_global] = (EA/L) * [ c^2    cs    -c^2   -cs  ]
                       [ cs     s^2   -cs    -s^2 ]
                       [-c^2   -cs     c^2    cs   ]
                       [-cs    -s^2    cs     s^2  ]
```
Where c = cos(theta), s = sin(theta).

**3D Truss Element** (6 DOFs: u1, v1, w1, u2, v2, w2):

Direction cosines: l = (x2-x1)/L, m = (y2-y1)/L, n = (z2-z1)/L

```
[k_global] = (EA/L) * [ l^2   lm    ln   -l^2  -lm   -ln  ]
                       [ lm    m^2   mn   -lm   -m^2  -mn  ]
                       [ ln    mn    n^2  -ln   -mn   -n^2 ]
                       [-l^2  -lm   -ln    l^2   lm    ln  ]
                       [-lm   -m^2  -mn    lm    m^2   mn  ]
                       [-ln   -mn   -n^2   ln    mn    n^2 ]
```

### 1.2 Beam Element (1D Bending — Euler-Bernoulli)

Each node has 3 DOFs in 2D: axial displacement u, transverse displacement v, rotation theta. Total 6 DOFs per element.

The element combines axial (truss) and bending (beam) stiffness:

**Axial part** (same as truss):
```
[k_axial] = (EA/L) * [ 1  -1 ]
                      [-1   1 ]
```

**Bending part** (Euler-Bernoulli, consistent formulation):
```
[k_bending] = (EI/L^3) * [ 12    6L   -12    6L  ]
                          [ 6L    4L^2  -6L   2L^2 ]
                          [-12   -6L    12   -6L   ]
                          [ 6L    2L^2  -6L   4L^2 ]
```

**Combined 2D beam element** (6 DOFs: u1, v1, theta1, u2, v2, theta2):
```
[k_e] = [ EA/L    0        0       -EA/L   0        0      ]
         [ 0       12EI/L^3  6EI/L^2  0    -12EI/L^3 6EI/L^2]
         [ 0       6EI/L^2   4EI/L    0    -6EI/L^2  2EI/L  ]
         [-EA/L    0        0        EA/L   0        0      ]
         [ 0      -12EI/L^3 -6EI/L^2  0     12EI/L^3 -6EI/L^2]
         [ 0       6EI/L^2   2EI/L    0    -6EI/L^2  4EI/L  ]
```

**Timoshenko beam** (includes shear deformation): Adds a shear correction factor kappa and shear modulus G. Important when L/d < 10 (short, deep beams). The stiffness matrix includes shear flexibility parameter phi = 12EI/(kappa*G*A*L^2).

### 1.3 Shell Element

Shell elements combine membrane (in-plane) and plate (out-of-plane bending) behavior. Common formulations:

**Flat shell element** (superposition of membrane + plate):
- Membrane: Constant Strain Triangle (CST, 3-node) or bilinear quadrilateral (Q4)
- Plate: Discrete Kirchhoff Triangle (DKT) or Mindlin-Reissner quadrilateral (MITC4)
- 5-6 DOFs per node: u, v, w, theta_x, theta_y (and optionally theta_z for drilling DOF)

**MITC4 (Mixed Interpolation of Tensorial Components)**: The standard 4-node shell element. Uses assumed strain fields to avoid shear locking. Robust for both thin and moderately thick shells.

**Stiffness matrix assembly for shells**: Each element stiffness matrix is formulated in local coordinates (element plane), then transformed to global coordinates using a rotation matrix derived from the element normal and a reference direction.

**Shell element stiffness components**:
```
[k_shell] = [k_membrane] + [k_bending] + [k_coupling]
```

Membrane stiffness relates in-plane forces (N_x, N_y, N_xy) to in-plane strains (epsilon_x, epsilon_y, gamma_xy) through the constitutive matrix:
```
[D_membrane] = (Et/(1-nu^2)) * [ 1   nu   0          ]
                                [ nu  1    0          ]
                                [ 0   0    (1-nu)/2   ]
```

Bending stiffness relates moments (M_x, M_y, M_xy) to curvatures (kappa_x, kappa_y, kappa_xy):
```
[D_bending] = (Et^3/(12(1-nu^2))) * [ 1   nu   0          ]
                                     [ nu  1    0          ]
                                     [ 0   0    (1-nu)/2   ]
```

### 1.4 Solid Element (3D Continuum)

**4-node tetrahedron (TET4)**: Linear, constant strain. 3 DOFs per node (u, v, w), 12 DOFs total. Stiffness matrix derived from:
```
[k_e] = V * [B]^T * [D] * [B]
```
Where V = element volume, [B] = strain-displacement matrix (constant for TET4), [D] = constitutive matrix.

Isotropic constitutive matrix (6x6):
```
[D] = (E/((1+nu)(1-2nu))) * [ 1-nu  nu    nu    0           0           0          ]
                              [ nu    1-nu  nu    0           0           0          ]
                              [ nu    nu    1-nu  0           0           0          ]
                              [ 0     0     0     (1-2nu)/2   0           0          ]
                              [ 0     0     0     0           (1-2nu)/2   0          ]
                              [ 0     0     0     0           0           (1-2nu)/2  ]
```

**10-node tetrahedron (TET10)**: Quadratic. Mid-side nodes capture curved geometry and stress gradients. 30 DOFs. Preferred for stress analysis.

**8-node hexahedron (HEX8)**: Bilinear. 24 DOFs. More accurate than TET4 for the same number of elements. Requires structured meshing (harder to generate for complex geometry).

**20-node hexahedron (HEX20)**: Quadratic. 60 DOFs. Best accuracy per element, but expensive. Used for benchmark problems and critical stress zones.

---

## 2. Assembly Process

The global stiffness matrix [K] is assembled from element stiffness matrices using the Direct Stiffness Method:

**Step 1**: Number all DOFs globally. For a structure with N nodes and d DOFs per node, the global system has N*d DOFs.

**Step 2**: For each element e with nodes (i, j, ...):
1. Compute element stiffness matrix [k_e] in local coordinates
2. Transform to global coordinates: [k_e_global] = [T]^T * [k_e] * [T]
3. Map element DOFs to global DOFs using the connectivity table
4. Add element contributions to the global matrix: K(global_i, global_j) += k_e(local_i, local_j)

**Step 3**: The assembled [K] is symmetric, positive semi-definite (becomes positive definite after applying boundary conditions), banded, and sparse.

**Bandwidth**: The half-bandwidth B is determined by the maximum difference in node numbers connected by any element times d (DOFs per node). Minimizing bandwidth reduces computation time. Node renumbering algorithms (Cuthill-McKee, Reverse Cuthill-McKee, Sloan) are applied automatically by most FEA software.

**Sparse storage**: For a model with 100,000 nodes and 6 DOFs/node, [K] is 600,000 x 600,000 (360 billion entries if stored densely). But typically > 99.9% of entries are zero. CSR (Compressed Sparse Row) format stores only non-zero entries: row pointers, column indices, and values.

---

## 3. Boundary Condition Application

Boundary conditions modify the global system [K]{u} = {F} to enforce prescribed displacements:

**Method 1: Row/column elimination**
For a prescribed DOF u_i = u_bar:
1. Move the known displacement to the right-hand side: F_j -= K_ji * u_bar for all j != i
2. Set row i and column i of [K] to zero except K_ii = 1
3. Set F_i = u_bar
This preserves matrix symmetry and size.

**Method 2: Penalty method**
Add a very large stiffness (10^8 * max(K_ii)) to K_ii for the constrained DOF. Set F_i = penalty * u_bar.
Simple to implement but introduces numerical conditioning issues.

**Method 3: Lagrange multipliers**
Augment the system with constraint equations. Preserves the original stiffness matrix. Increases system size. Required for multi-point constraints (rigid links, master-slave relationships).

**Spring supports**: Add spring stiffness k_spring to the diagonal of [K] at the supported DOF. The spring allows proportional displacement: F_reaction = k_spring * u.

---

## 4. Load Combination Tables

### 4.1 Eurocode (EN 1990, Annex A)

**Combination factors psi:**

| Action | psi_0 | psi_1 | psi_2 |
|---|---|---|---|
| Imposed — domestic/residential (Cat A) | 0.7 | 0.5 | 0.3 |
| Imposed — office (Cat B) | 0.7 | 0.5 | 0.3 |
| Imposed — congregation (Cat C) | 0.7 | 0.7 | 0.6 |
| Imposed — shopping (Cat D) | 0.7 | 0.7 | 0.6 |
| Imposed — storage (Cat E) | 1.0 | 0.9 | 0.8 |
| Imposed — traffic (Cat F) | 0.7 | 0.7 | 0.6 |
| Imposed — roofs (Cat H) | 0.0 | 0.0 | 0.0 |
| Snow (< 1000m altitude) | 0.5 | 0.2 | 0.0 |
| Snow (>= 1000m altitude) | 0.7 | 0.5 | 0.2 |
| Wind | 0.6 | 0.2 | 0.0 |
| Temperature | 0.6 | 0.5 | 0.0 |

**Partial factors (EQU, STR, GEO):**

| Action Type | gamma_G,sup (unfavorable) | gamma_G,inf (favorable) | gamma_Q (unfavorable) | gamma_Q (favorable) |
|---|---|---|---|---|
| Permanent (G) | 1.35 | 1.00 | - | - |
| Variable (Q) | - | - | 1.50 | 0.00 |
| Accidental (A) | 1.00 | 1.00 | 1.00 (psi_1 or psi_2) | 0.00 |

### 4.2 ASCE 7-22 (LRFD)

| Combination | Expression | Governing for |
|---|---|---|
| LC1 | 1.4D | Permanent load only |
| LC2 | 1.2D + 1.6L + 0.5(L_r or S or R) | Gravity dominant |
| LC3 | 1.2D + 1.6(L_r or S or R) + (L or 0.5W) | Roof live/snow dominant |
| LC4 | 1.2D + 1.0W + L + 0.5(L_r or S or R) | Wind + gravity |
| LC5 | 1.2D + 1.0E + L + 0.2S | Seismic + gravity |
| LC6 | 0.9D + 1.0W | Wind uplift/overturning |
| LC7 | 0.9D + 1.0E | Seismic overturning |

**ASD (Allowable Stress Design) combinations:**

| Combination | Expression |
|---|---|
| LC1 | D |
| LC2 | D + L |
| LC3 | D + (L_r or S or R) |
| LC4 | D + 0.75L + 0.75(L_r or S or R) |
| LC5 | D + (0.6W or 0.7E) |
| LC6a | D + 0.75L + 0.75(0.6W) + 0.75(L_r or S or R) |
| LC6b | D + 0.75L + 0.75(0.7E) + 0.75S |
| LC7 | 0.6D + 0.6W |
| LC8 | 0.6D + 0.7E |

---

## 5. Stress Types and Calculations

### 5.1 Axial Stress

```
sigma_axial = N / A
```
Where N = axial force (positive = tension), A = cross-section area.
Uniform across the cross-section (for concentric loading).

### 5.2 Bending Stress

```
sigma_bending = M * y / I
```
Where M = bending moment, y = distance from neutral axis (positive to the extreme fiber), I = second moment of area about the bending axis.

- Linear distribution through the cross-section depth
- Maximum at the extreme fibers (top and bottom)
- Zero at the neutral axis
- For asymmetric sections: sigma = M * y / I uses the correct I for the relevant axis

### 5.3 Shear Stress

**Transverse shear (Jourawski formula):**
```
tau = V * Q / (I * b)
```
Where V = shear force, Q = first moment of area of the portion above (or below) the point of interest, I = second moment of area, b = width at the point of interest.

- Parabolic distribution through the depth for rectangular sections
- Maximum at the neutral axis
- Zero at the extreme fibers (top and bottom)
- For I-beams: approximately uniform across the web (tau_avg = V / A_web)

### 5.4 Torsional Shear

**Circular sections:**
```
tau_torsion = T * r / J
```
Where T = torsional moment, r = radial distance from center, J = polar moment of inertia (pi*d^4/32 for solid circular).
Linear distribution from center (zero) to surface (maximum).

**Rectangular and open sections:**
```
tau_max = T / W_t
```
Where W_t is the torsion section modulus. For thin-walled open sections (I, C, L shapes): W_t = sum(b_i * t_i^3 / 3). Open sections have very low torsional stiffness -- avoid torsional loading on I-beams.

**Closed (box) sections:**
```
tau = T / (2 * A_enclosed * t)
```
Where A_enclosed = area enclosed by the median line, t = wall thickness. Closed sections are far more efficient in torsion than open sections.

### 5.5 Von Mises Equivalent Stress

For a general 3D stress state (sigma_x, sigma_y, sigma_z, tau_xy, tau_yz, tau_xz):

```
sigma_vm = sqrt(0.5 * [(sigma_x - sigma_y)^2 + (sigma_y - sigma_z)^2 + (sigma_z - sigma_x)^2 + 6*(tau_xy^2 + tau_yz^2 + tau_xz^2)])
```

For 2D plane stress (sigma_z = tau_yz = tau_xz = 0):
```
sigma_vm = sqrt(sigma_x^2 - sigma_x*sigma_y + sigma_y^2 + 3*tau_xy^2)
```

Von Mises criterion: yielding occurs when sigma_vm >= f_y.

Used for ductile materials (steel, aluminum). NOT appropriate for brittle materials (concrete, masonry, glass).

### 5.6 Tresca (Maximum Shear) Stress

```
tau_max = (sigma_1 - sigma_3) / 2
```
Where sigma_1 >= sigma_2 >= sigma_3 are principal stresses (sorted).

Tresca criterion: yielding when tau_max >= f_y / 2.

More conservative than von Mises (by up to 15%). Simpler to compute. Used in some pressure vessel codes.

### 5.7 Principal Stresses

Principal stresses are the eigenvalues of the stress tensor. They represent the normal stresses on planes where shear stress is zero.

For 2D:
```
sigma_1,2 = (sigma_x + sigma_y)/2 +/- sqrt(((sigma_x - sigma_y)/2)^2 + tau_xy^2)
```

Principal stress directions (angle theta_p from x-axis):
```
tan(2*theta_p) = 2*tau_xy / (sigma_x - sigma_y)
```

In structural design, principal stress directions indicate the natural flow of forces. Reinforcement in concrete should align with tensile principal stress directions. Topology optimization produces material layouts aligned with principal stresses.

---

## 6. Deflection Limits Table

| Element / Condition | Eurocode Limit | ASCE/IBC Limit | Notes |
|---|---|---|---|
| Floor beam — general | L/250 (total), L/300 (variable) | L/360 (live load) | Most common check |
| Floor beam — brittle partitions | L/500 (variable actions) | L/480 (live + dead - camber) | Prevents cracking of finishes |
| Roof beam — no ceiling | L/200 (total) | L/180 (live load) | More permissive |
| Roof beam — with plaster ceiling | L/250 (total) | L/240 (live load) | Ceiling cracking concern |
| Cantilever | L/125 to L/180 | L/180 to L/240 | Cantilever doubles effective span |
| Steel beam — floor | L/250 to L/350 | L/360 | Standard practice |
| Timber beam — floor | L/250 to L/400 | L/360 | Creep factor: multiply by 1.5-2.0 for long-term |
| Concrete slab | L/250 (quasi-permanent) | L/240 (immediate + long-term) | Include creep and shrinkage |
| Portal frame — horizontal | H/300 (crane buildings) | H/400 (per AISC) | Sway limit |
| Multi-story — inter-story drift | H_story/300 to H_story/500 | H_story/400 to H_story/600 | Seismic drift: different limits |
| Total building — wind | H_total/500 | H_total/400 to H_total/600 | Perception of sway, cladding |
| Crane runway beam | L/500 to L/800 | L/600 to L/1000 | Crane operation tolerance |
| Glazing support | L/175 (glass deflection limit) | L/175 | Prevents glass breakage |

**Key notes:**
- L = span length, H = height
- Eurocode deflections typically checked under quasi-permanent load combination
- ASCE/IBC deflections checked under specific load (live, dead, or combined as specified)
- Pre-camber can offset dead load deflection but not live load deflection
- Long-term deflections (creep): multiply immediate deflection by creep factor (1.5 for steel, 2.0-3.0 for concrete, 1.5-2.0 for timber)

---

## 7. Utilization Ratio Calculation

The utilization ratio U is the fundamental design check metric. It represents the fraction of a member's capacity that is being used.

### 7.1 Axial Only (Tension or Compression)

**Tension:**
```
U_t = N_Ed / N_t,Rd
N_t,Rd = A * f_y / gamma_M0    (Eurocode)
N_t,Rd = phi * A * F_y         (AISC, phi = 0.90)
```

**Compression (with buckling):**
```
U_c = N_Ed / N_b,Rd
N_b,Rd = chi * A * f_y / gamma_M1    (Eurocode, chi = buckling reduction factor)
N_b,Rd = phi_c * A_g * F_cr           (AISC, phi_c = 0.90)
```

Euler critical load (elastic buckling):
```
N_cr = pi^2 * E * I / (L_cr)^2
```
Where L_cr = effective length (0.5L for fixed-fixed, 0.7L for fixed-pinned, 1.0L for pinned-pinned, 2.0L for cantilever).

Slenderness ratio: lambda = L_cr / r, where r = sqrt(I/A) is radius of gyration.

### 7.2 Bending Only

```
U_b = M_Ed / M_Rd
M_Rd = W_pl * f_y / gamma_M0              (Eurocode, Class 1/2 sections)
M_Rd = phi_b * M_n = phi_b * Z * F_y      (AISC, phi_b = 0.90, Z = plastic section modulus)
```

For lateral-torsional buckling:
```
M_b,Rd = chi_LT * W_pl * f_y / gamma_M1   (Eurocode)
M_n = phi_b * F_cr * S_x                    (AISC, with LTB reduction)
```

### 7.3 Combined Axial + Bending (Interaction)

**Eurocode (EN 1993-1-1, Eq. 6.61/6.62):**
```
N_Ed/N_Rd + k_yy * M_y,Ed/M_y,Rd + k_yz * M_z,Ed/M_z,Rd <= 1.0
N_Ed/N_Rd + k_zy * M_y,Ed/M_y,Rd + k_zz * M_z,Ed/M_z,Rd <= 1.0
```
Where k factors account for moment distribution and buckling interaction.

**AISC 360 (H1-1a/b):**
```
If P_r/P_c >= 0.2:  P_r/P_c + (8/9)(M_rx/M_cx + M_ry/M_cy) <= 1.0
If P_r/P_c < 0.2:   P_r/(2*P_c) + (M_rx/M_cx + M_ry/M_cy) <= 1.0
```

### 7.4 Shear

```
U_v = V_Ed / V_Rd
V_Rd = A_v * f_y / (sqrt(3) * gamma_M0)    (Eurocode, plastic shear resistance)
V_Rd = phi_v * 0.6 * F_y * A_w              (AISC, phi_v = 1.00)
```

### 7.5 Color Mapping Convention

| Utilization Range | Color | Meaning |
|---|---|---|
| U < 0.20 | Blue | Heavily oversized — consider reducing section |
| 0.20 <= U < 0.50 | Green | Adequate with reserve |
| 0.50 <= U < 0.80 | Yellow | Efficient design |
| 0.80 <= U < 1.00 | Orange | Near capacity — verify carefully |
| U >= 1.00 | Red | EXCEEDS CAPACITY — redesign required |

---

## 8. Cross-Section Properties

### 8.1 Common Cross-Section Formulas

| Property | Symbol | Rectangle (b x h) | Circle (d) | Hollow Circle (D, d) | I-beam (b_f, t_f, h_w, t_w) |
|---|---|---|---|---|---|
| Area | A | b * h | pi * d^2 / 4 | pi * (D^2 - d^2) / 4 | 2 * b_f * t_f + h_w * t_w |
| I_x (strong axis) | I | b * h^3 / 12 | pi * d^4 / 64 | pi * (D^4 - d^4) / 64 | (approx) b_f * H^3/12 - (b_f-t_w)*h_w^3/12 |
| I_y (weak axis) | I | h * b^3 / 12 | pi * d^4 / 64 | pi * (D^4 - d^4) / 64 | 2 * t_f * b_f^3/12 + h_w * t_w^3/12 |
| Elastic section modulus | S = I/c | b * h^2 / 6 | pi * d^3 / 32 | pi * (D^4-d^4) / (32*D) | I / (H/2) |
| Plastic section modulus | Z | b * h^2 / 4 | d^3 / 6 | (D^3-d^3) / 6 | (approx) b_f*t_f*(H-t_f) + t_w*h_w^2/4 |
| Radius of gyration | r = sqrt(I/A) | h / sqrt(12) | d / 4 | sqrt((D^2+d^2)/16) | sqrt(I/A) |
| Torsion constant | J | ~b * h^3 * (1/3 - 0.21*h/b) | pi*d^4/32 | pi*(D^4-d^4)/32 | sum(b_i*t_i^3/3) (open) |

Where H = total depth of I-beam = h_w + 2*t_f, c = distance from neutral axis to extreme fiber.

### 8.2 Steel Section Tables — Key Sizes (Metric / W-shapes)

| Section | Depth (mm) | Width (mm) | A (cm^2) | I_x (cm^4) | I_y (cm^4) | Z_x (cm^3) | Weight (kg/m) |
|---|---|---|---|---|---|---|---|
| HEA 200 (W8x31) | 190 | 200 | 53.8 | 3692 | 1336 | 429 | 42.3 |
| HEB 200 (W8x40) | 200 | 200 | 78.1 | 5696 | 2003 | 642 | 61.3 |
| HEA 300 (W12x50) | 290 | 300 | 112.5 | 18263 | 6310 | 1383 | 88.3 |
| HEB 300 (W12x72) | 300 | 300 | 149.1 | 25166 | 8563 | 1869 | 117.0 |
| HEA 400 (W16x77) | 390 | 300 | 159.0 | 45069 | 8564 | 2562 | 124.8 |
| IPE 200 (W8x18) | 200 | 100 | 28.5 | 1943 | 142 | 221 | 22.4 |
| IPE 300 (W12x30) | 300 | 150 | 53.8 | 8356 | 604 | 628 | 42.2 |
| IPE 400 (W16x40) | 400 | 180 | 84.5 | 23130 | 1318 | 1307 | 66.3 |
| IPE 500 (W21x55) | 500 | 200 | 115.5 | 48200 | 2142 | 2194 | 90.7 |
| IPE 600 (W24x76) | 600 | 220 | 156.0 | 92080 | 3387 | 3512 | 122.4 |

### 8.3 HSS (Hollow Structural Sections) — Key Sizes

| Section | Dimensions (mm) | Wall (mm) | A (cm^2) | I (cm^4) | Z (cm^3) | Weight (kg/m) |
|---|---|---|---|---|---|---|
| SHS 100x100 | 100 x 100 | 5.0 | 18.4 | 281 | 65 | 14.4 |
| SHS 150x150 | 150 x 150 | 6.3 | 34.9 | 1090 | 170 | 27.4 |
| SHS 200x200 | 200 x 200 | 8.0 | 59.2 | 3420 | 403 | 46.5 |
| SHS 250x250 | 250 x 250 | 10.0 | 92.0 | 8470 | 800 | 72.2 |
| CHS 114.3 | d = 114.3 | 5.0 | 17.2 | 244 | 51 | 13.5 |
| CHS 168.3 | d = 168.3 | 6.3 | 32.1 | 1053 | 145 | 25.2 |
| CHS 219.1 | d = 219.1 | 8.0 | 53.0 | 2960 | 315 | 41.6 |
| CHS 323.9 | d = 323.9 | 10.0 | 98.6 | 12390 | 894 | 77.4 |

---

## 9. Concrete Reinforcement Reference

### 9.1 Concrete Grades and Properties

| Grade (Eurocode) | Grade (ACI) | f_ck (MPa) | f_cm (MPa) | f_ctm (MPa) | E_cm (GPa) |
|---|---|---|---|---|---|
| C20/25 | 3000 psi | 20 | 28 | 2.2 | 30.0 |
| C25/30 | 3500 psi | 25 | 33 | 2.6 | 31.5 |
| C30/37 | 4000 psi | 30 | 38 | 2.9 | 33.0 |
| C35/45 | 5000 psi | 35 | 43 | 3.2 | 34.0 |
| C40/50 | 5500 psi | 40 | 48 | 3.5 | 35.0 |
| C50/60 | 7000 psi | 50 | 58 | 4.1 | 37.0 |
| C60/75 | 8500 psi | 60 | 68 | 4.4 | 39.0 |
| C80/95 | 11500 psi | 80 | 88 | 4.8 | 42.0 |

### 9.2 Reinforcement Bar Sizes

**Metric (Eurocode):**

| Bar | Diameter (mm) | Area (mm^2) | Weight (kg/m) |
|---|---|---|---|
| 6 | 6 | 28.3 | 0.222 |
| 8 | 8 | 50.3 | 0.395 |
| 10 | 10 | 78.5 | 0.617 |
| 12 | 12 | 113.1 | 0.888 |
| 16 | 16 | 201.1 | 1.579 |
| 20 | 20 | 314.2 | 2.466 |
| 25 | 25 | 490.9 | 3.854 |
| 32 | 32 | 804.2 | 6.313 |
| 40 | 40 | 1256.6 | 9.864 |

**Imperial (ACI):**

| Bar # | Diameter (in) | Area (in^2) | Weight (lb/ft) |
|---|---|---|---|
| #3 | 0.375 | 0.11 | 0.376 |
| #4 | 0.500 | 0.20 | 0.668 |
| #5 | 0.625 | 0.31 | 1.043 |
| #6 | 0.750 | 0.44 | 1.502 |
| #7 | 0.875 | 0.60 | 2.044 |
| #8 | 1.000 | 0.79 | 2.670 |
| #9 | 1.128 | 1.00 | 3.400 |
| #10 | 1.270 | 1.27 | 4.303 |
| #11 | 1.410 | 1.56 | 5.313 |

### 9.3 Reinforcement Steel Grades

| Grade | f_yk (MPa) | f_y (ksi) | E_s (GPa) | Standard |
|---|---|---|---|---|
| B500B | 500 | 72.5 | 200 | EN 10080 |
| B500C | 500 (high ductility) | 72.5 | 200 | EN 10080 |
| Grade 60 | 414 | 60 | 200 | ASTM A615 |
| Grade 75 | 517 | 75 | 200 | ASTM A615 |
| Grade 80 | 552 | 80 | 200 | ASTM A615 |

### 9.4 Minimum Cover Requirements

| Condition | Eurocode (mm) | ACI 318 (mm/in) |
|---|---|---|
| Indoor, dry | 15-25 | 19 / 0.75 |
| Indoor, moderate humidity | 25-30 | 25 / 1.0 |
| Outdoor, exposed | 30-40 | 38 / 1.5 |
| Ground contact | 40-50 | 76 / 3.0 |
| Marine / aggressive | 45-55 | 51-76 / 2.0-3.0 |
| Fire resistance (REI 60) | 25-35 | per ACI 216 |
| Fire resistance (REI 120) | 40-55 | per ACI 216 |

---

## 10. Timber Section Reference

### 10.1 Glulam (Glued Laminated Timber) Grades

| Grade (EN) | f_m,k (MPa) | f_t,0,k (MPa) | f_c,0,k (MPa) | E_0,mean (GPa) | Density (kg/m^3) |
|---|---|---|---|---|---|
| GL20h | 20 | 16 | 20 | 8.4 | 340 |
| GL24h | 24 | 19.2 | 24 | 11.5 | 380 |
| GL28h | 28 | 22.3 | 28 | 12.6 | 410 |
| GL32h | 32 | 25.6 | 32 | 13.7 | 430 |
| GL36h | 36 | 28.8 | 36 | 14.7 | 450 |

### 10.2 CLT (Cross-Laminated Timber) Properties

CLT panels consist of odd-numbered layers (3, 5, 7) with alternating grain direction.

| Property | Typical Range | Notes |
|---|---|---|
| Thickness | 60 - 300 mm | 3-layer (60-120mm), 5-layer (100-200mm), 7-layer (180-300mm) |
| In-plane shear (f_v) | 5 - 8 MPa | Rolling shear in cross-layers governs |
| Out-of-plane bending (f_m) | 24 - 32 MPa (strong direction) | Depends on layup and timber grade |
| E_0 (strong direction) | 9 - 12 GPa | Effective value for composite section |
| E_90 (weak direction) | 3 - 5 GPa | Cross-layers contribute |
| Density | 420 - 500 kg/m^3 | Spruce/fir typical |
| Fire char rate | 0.65 mm/min | EN 1995-1-2 standard charring |

### 10.3 LVL (Laminated Veneer Lumber) Properties

| Property | Kerto-S (parallel) | Kerto-Q (cross-banded) | Units |
|---|---|---|---|
| f_m,k | 44 | 32 | MPa |
| f_t,0,k | 35 | 26 | MPa |
| f_c,0,k | 35 | 26 | MPa |
| E_0,mean | 13.8 | 10.5 | GPa |
| Density | 480 | 480 | kg/m^3 |
| Typical thicknesses | 21-75 mm | 21-69 mm | mm |

### 10.4 Timber Modification Factors (Eurocode 5)

| Factor | Symbol | Description | Range |
|---|---|---|---|
| Service class | SC 1/2/3 | Moisture condition | SC1 < 12%, SC2 < 20%, SC3 > 20% |
| Load duration | k_mod | Strength modification for load duration | 0.50 (permanent) to 1.10 (instantaneous) |
| Partial safety factor | gamma_M | Material safety factor | 1.25 (solid), 1.25 (glulam), 1.25 (CLT) |
| System factor | k_sys | Multiple members sharing load | 1.10 (>= 4 members) |
| Size factor | k_h | Depth effect on bending strength | (150/h)^0.1, max 1.10 (glulam) |
| Deformation factor | k_def | Creep factor for SLS | 0.60-2.00 depending on SC and material |

### 10.5 Common Timber Beam Sizes

**Glulam (standard widths):** 80, 100, 120, 140, 160, 180, 200, 220, 240 mm
**Glulam (standard depths):** increments of lamination thickness (typically 33 or 45 mm)

| Span (m) | Depth (mm) — rule of thumb | Width (mm) | Notes |
|---|---|---|---|
| 4 | 200-280 | 100-140 | Residential floor joist |
| 6 | 300-400 | 120-160 | Light commercial beam |
| 8 | 400-520 | 140-180 | Medium-span beam |
| 10 | 500-660 | 160-200 | Large beam |
| 12 | 600-800 | 180-220 | Long-span beam |
| 15+ | 750-1000+ | 200-240+ | Consider truss or arch |

Rule of thumb for glulam beams: depth is approximately L/15 to L/20 for floor beams, L/20 to L/25 for roof beams (where L = span).

---

## 11. Convergence Procedures and Quality Assurance

### 11.1 Mesh Convergence Study Procedure

1. Build the model with a coarse mesh (baseline)
2. Run analysis and record key results (max stress, max displacement, reactions)
3. Refine the mesh globally (halve element size, approximately 4x elements in 2D, 8x in 3D)
4. Re-run and record results
5. Compare: if key results change by less than 5%, the coarser mesh is adequate
6. If results change by more than 5%, refine again
7. Report the convergence table:

| Mesh Level | Elements | Max Stress (MPa) | Max Displacement (mm) | Change (%) |
|---|---|---|---|---|
| Coarse | 500 | 142.3 | 12.1 | - |
| Medium | 2000 | 158.7 | 12.8 | 11.5 / 5.8 |
| Fine | 8000 | 163.2 | 13.0 | 2.8 / 1.6 |
| Very fine | 32000 | 164.1 | 13.0 | 0.6 / 0.0 |

In this example, the "Fine" mesh (8000 elements) is adequate -- results have converged within 3%.

### 11.2 Equilibrium Check

After every analysis, verify global equilibrium:
- Sum of all applied forces = sum of all reaction forces (within numerical tolerance, typically < 0.1%)
- Sum of moments about any point = 0
- If equilibrium is violated, check for modeling errors (disconnected elements, missing supports, zero-stiffness elements)

### 11.3 Reaction Check

Compare calculated reactions against hand-calculated estimates:
- Simply supported beam: R = wL/2 at each support
- Cantilever: R = wL at the fixed end, M = wL^2/2
- If reactions differ from estimates by more than 20%, investigate the model

### 11.4 Displacement Reasonableness

Compare calculated deflections against simple formulas:
- Simply supported beam under uniform load: delta = 5wL^4 / (384EI)
- Cantilever under tip load: delta = PL^3 / (3EI)
- Fixed-end beam under uniform load: delta = wL^4 / (384EI)
- If calculated deflections are orders of magnitude different, check units, material properties, or boundary conditions
