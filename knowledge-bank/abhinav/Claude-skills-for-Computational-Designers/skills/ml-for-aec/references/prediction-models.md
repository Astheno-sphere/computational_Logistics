# Prediction Models for AEC: Deep Reference

This reference covers the methodology, feature engineering, model comparison, and deployment of ML-based prediction models for building performance in architecture, engineering, and construction.

---

## 1. Feature Engineering for Building Performance Prediction

### 1.1 Geometric Features

Geometric features encode building shape and spatial properties. These are the most important predictors for energy, daylight, and wind performance.

**Building-level features**:

| Feature | Formula / Definition | Units | Relevance |
|---------|---------------------|-------|-----------|
| Gross floor area | Sum of all floor plate areas | m2 | Scale factor for all loads |
| Footprint area | Ground floor plan area | m2 | Solar exposure, ground heat loss |
| Building volume | Sum of floor areas * floor-to-floor heights | m3 | Thermal mass, HVAC sizing |
| Surface area | Total exterior envelope area | m2 | Heat loss/gain surface |
| Surface-to-volume ratio (S/V) | Envelope_area / Volume | 1/m | Compact buildings have lower S/V → less energy |
| Compactness | 6 * V^(2/3) / A_envelope (cube = 1.0) | dimensionless | 1.0 = cube (most compact); lower = more surface exposure |
| Aspect ratio | Building length / building width | dimensionless | Affects solar exposure and wind loading |
| Number of stories | Count of above-grade floors | count | Determines stack effect, elevator energy |
| Floor-to-floor height | Typical distance between floors | m | Affects volume, facade area |
| Building height | Grade to highest occupied floor | m | Wind exposure, stack effect |
| Perimeter length | Floor plate perimeter | m | Determines possible window area |
| Core-to-perimeter depth | Distance from core to nearest exterior wall | m | Affects daylight penetration, thermal zoning |

**Facade-level features**:

| Feature | Formula / Definition | Units | Relevance |
|---------|---------------------|-------|-----------|
| WWR (Window-to-Wall Ratio) | Glazing_area / Gross_wall_area | fraction (0-1) | Key energy and daylight driver |
| WWR by orientation | WWR_north, WWR_south, WWR_east, WWR_west | fraction | Directional solar exposure |
| Glazing U-value | Thermal transmittance of window assembly | W/(m2K) | Heat loss through glazing |
| Wall U-value | Thermal transmittance of opaque wall | W/(m2K) | Heat loss through walls |
| Roof U-value | Thermal transmittance of roof assembly | W/(m2K) | Heat loss through roof (top floor) |
| SHGC | Solar Heat Gain Coefficient of glazing | fraction (0-1) | Solar heat gain |
| VLT | Visible Light Transmittance of glazing | fraction (0-1) | Daylight transmission |
| Shading depth | Horizontal shade projection / window height | fraction | External shading effectiveness |

**Room-level features (for daylight and thermal zone prediction)**:

| Feature | Formula / Definition | Units |
|---------|---------------------|-------|
| Room area | Floor area of the room | m2 |
| Room depth | Distance from window wall to back wall | m |
| Room width | Width of the window wall | m |
| Room height | Floor-to-ceiling height | m |
| Window head height | Top of window above floor | m |
| Window sill height | Bottom of window above floor | m |
| Window width ratio | Window_width / Room_width | fraction |
| Ceiling reflectance | Reflectance of ceiling surface | fraction (0-1) |
| Wall reflectance | Average reflectance of wall surfaces | fraction (0-1) |
| Floor reflectance | Reflectance of floor surface | fraction (0-1) |
| Obstruction angle | Angle from window to top of nearest obstruction | degrees |

### 1.2 Climate Features

| Feature | Source | Units | Notes |
|---------|--------|-------|-------|
| Heating Degree Days (HDD) | Weather file (TMY) | degree-days | Base 18.3C or 15.5C |
| Cooling Degree Days (CDD) | Weather file | degree-days | Base 10C |
| Annual mean temperature | Weather file | C | |
| Design heating temperature | ASHRAE 99.6% | C | Coldest design condition |
| Design cooling temperature | ASHRAE 0.4% | C | Hottest design condition |
| Annual solar radiation (horizontal) | Weather file | kWh/(m2yr) | Global horizontal irradiance |
| Solar radiation by orientation | Calculated from TMY | kWh/(m2yr) | N, S, E, W facade irradiance |
| Latitude | Project location | degrees | Determines solar angles |
| Elevation | Project location | m above sea level | Affects air pressure, temperature |
| Average wind speed | Weather file | m/s | Wind-related losses |
| ASHRAE climate zone | Lookup | zone code (1A-8) | Standard climate classification |

### 1.3 Operational Features

| Feature | Source | Units |
|---------|--------|-------|
| Occupant density | Building program / code | m2/person |
| Equipment power density | Building type lookup | W/m2 |
| Lighting power density | Energy code / design | W/m2 |
| Occupancy schedule | Building type (ASHRAE 90.1 schedules) | fraction by hour |
| Heating setpoint | Mechanical design | C |
| Cooling setpoint | Mechanical design | C |
| Ventilation rate | Code (ASHRAE 62.1) | L/s per person |
| HVAC system type | Mechanical design | categorical |
| HVAC COP/efficiency | Equipment specification | dimensionless |

### 1.4 Feature Preprocessing

```python
import numpy as np
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer

# Define feature types
numeric_features = [
    "gross_floor_area", "surface_to_volume", "wwr_north", "wwr_south",
    "wwr_east", "wwr_west", "wall_u_value", "roof_u_value",
    "glazing_u_value", "shgc", "hdd", "cdd", "latitude",
    "lpd", "epd", "occupant_density", "hvac_cop"
]

categorical_features = [
    "building_type", "hvac_system", "climate_zone"
]

# Create preprocessing pipeline
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(drop="first", sparse_output=False), categorical_features),
    ]
)

# Fit and transform
X_processed = preprocessor.fit_transform(X_raw)
```

### 1.5 Feature Selection for AEC

**Correlation-based**: Remove features with correlation > 0.95 (e.g., gross_floor_area and building_volume are highly correlated; keep the more physically interpretable one).

**Importance-based**: Train a Random Forest; inspect feature importances; remove features with near-zero importance.

**Domain knowledge**: Keep features that are architecturally meaningful and controllable by the designer. Remove features that are downstream consequences rather than design decisions.

**Recommended feature set for energy prediction** (parsimonious):
1. Compactness (or S/V ratio)
2. WWR by orientation (4 features)
3. Envelope U-value (wall, roof, glazing)
4. SHGC
5. HDD and CDD
6. HVAC system type
7. Lighting power density
8. Occupant density

This set of ~12-15 features typically achieves R2 > 0.90 for EUI prediction.

---

## 2. Surrogate Model Methodology

### 2.1 What Is a Surrogate Model?

A surrogate model (also called metamodel or emulator) is a computationally cheap approximation of an expensive simulation. In AEC:

```
Expensive simulation:
  Input: Building parameters → [EnergyPlus, 5 minutes per run] → Output: Annual EUI

Surrogate model:
  Input: Building parameters → [Trained ML model, 5 milliseconds per run] → Output: Predicted EUI

Speedup: ~60,000x
```

Surrogates enable:
- Real-time performance feedback during design (parametric slider → instant EUI estimate)
- Optimization over thousands of variants (infeasible with full simulation)
- Sensitivity analysis (which parameters matter most?)
- Design space exploration (map the landscape of possible designs)

### 2.2 Surrogate Model Workflow

```
Step 1: Define parameter space
  - List all input parameters with ranges
  - Determine which parameters are fixed vs. variable
  - Total: 10-50 parameters typically

Step 2: Design of experiments (sampling plan)
  - Latin Hypercube Sampling (LHS): Space-filling, efficient for high dimensions
  - Sobol sequence: Quasi-random, good for sensitivity analysis
  - Full factorial: Complete coverage of discrete parameters (if few discrete levels)
  - Number of samples: 10x to 100x the number of parameters (e.g., 20 params → 200-2000 samples)

Step 3: Run simulations
  - Each sample = one simulation run with specific parameter values
  - Parallelize across multiple cores / machines
  - Total time: 200 runs * 5 min = 17 hours (1 machine) or 2 hours (8 machines)

Step 4: Train surrogate model
  - Input: Parameter vectors from Step 2
  - Output: Simulation results from Step 3
  - Model: Random Forest, XGBoost, Neural Network, or Gaussian Process
  - Validation: k-fold cross-validation on the simulation dataset

Step 5: Validate surrogate
  - Run 50-100 additional simulations not in training set
  - Compare surrogate predictions to simulation results
  - Accept if R2 > 0.90 and MAPE < 10% (typical thresholds)

Step 6: Deploy surrogate
  - Embed in Grasshopper, Revit add-in, or web tool
  - Provide instant predictions during design
  - Document accuracy bounds and applicability range
```

### 2.3 Latin Hypercube Sampling (LHS)

```python
from scipy.stats import qmc

def generate_lhs_samples(param_ranges, n_samples, seed=42):
    """
    Generate Latin Hypercube Samples for building parameter space.

    Args:
        param_ranges: Dict of {param_name: (min, max)}
        n_samples: Number of samples to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame of parameter samples
    """
    n_params = len(param_ranges)
    sampler = qmc.LatinHypercube(d=n_params, seed=seed)
    samples_unit = sampler.random(n=n_samples)  # [0, 1] range

    # Scale to actual parameter ranges
    param_names = list(param_ranges.keys())
    lower = np.array([param_ranges[p][0] for p in param_names])
    upper = np.array([param_ranges[p][1] for p in param_names])
    samples_scaled = qmc.scale(samples_unit, lower, upper)

    return pd.DataFrame(samples_scaled, columns=param_names)

# Example: Building energy parameters
param_ranges = {
    "wwr_south":     (0.10, 0.80),
    "wwr_north":     (0.10, 0.60),
    "wwr_east":      (0.10, 0.60),
    "wwr_west":      (0.10, 0.60),
    "wall_u_value":  (0.15, 0.60),   # W/(m2K)
    "roof_u_value":  (0.10, 0.40),   # W/(m2K)
    "glazing_u_value": (0.80, 3.00), # W/(m2K)
    "shgc":          (0.20, 0.70),
    "lpd":           (5.0, 15.0),    # W/m2
    "hvac_cop":      (2.5, 5.0),
    "infiltration":  (0.1, 1.0),     # ACH
    "orientation":   (0, 360),        # degrees
}

samples = generate_lhs_samples(param_ranges, n_samples=500)
```

---

## 3. Training Data Generation via Parametric Simulation

### 3.1 EnergyPlus Parametric Pipeline

```python
"""
Generate training data for energy surrogate model using EnergyPlus.
"""
import subprocess
import json
from eppy import modeleditor

def run_parametric_energy_simulations(template_idf, samples_df, weather_file,
                                      output_dir):
    """
    Run EnergyPlus simulations for each parameter sample.

    Args:
        template_idf: Path to template IDF file
        samples_df: DataFrame of parameter samples
        weather_file: Path to EPW weather file
        output_dir: Directory for simulation outputs

    Returns:
        List of (parameters, results) tuples
    """
    results = []

    for idx, row in samples_df.iterrows():
        # Load and modify IDF
        idf = modeleditor.IDF(template_idf)

        # Set envelope parameters
        for surface in idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
            if surface.Surface_Type == "Wall":
                set_wall_construction(idf, surface, row["wall_u_value"])
            elif surface.Surface_Type == "Roof":
                set_roof_construction(idf, surface, row["roof_u_value"])

        # Set window parameters
        for window in idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]:
            set_glazing(idf, window, row["glazing_u_value"],
                       row["shgc"], wwr=row[f"wwr_{window.orientation}"])

        # Set internal loads
        set_lighting_power_density(idf, row["lpd"])
        set_hvac_efficiency(idf, row["hvac_cop"])
        set_infiltration(idf, row["infiltration"])

        # Set orientation
        idf.idfobjects["BUILDING"][0].North_Axis = row["orientation"]

        # Save modified IDF
        run_dir = f"{output_dir}/run_{idx:04d}"
        os.makedirs(run_dir, exist_ok=True)
        idf_path = f"{run_dir}/in.idf"
        idf.save(idf_path)

        # Run EnergyPlus
        subprocess.run([
            "energyplus",
            "-w", weather_file,
            "-d", run_dir,
            idf_path
        ], timeout=600)

        # Parse results
        eui = parse_eui(f"{run_dir}/eplustbl.htm")
        heating = parse_heating_energy(f"{run_dir}/eplustbl.htm")
        cooling = parse_cooling_energy(f"{run_dir}/eplustbl.htm")

        results.append({
            **row.to_dict(),
            "eui_total": eui,
            "eui_heating": heating,
            "eui_cooling": cooling,
        })

    return pd.DataFrame(results)
```

### 3.2 Radiance/DAYSIM Parametric Pipeline (Daylight)

```python
def run_daylight_simulations(room_params_df, weather_file):
    """Generate daylight training data using Radiance/DAYSIM."""
    results = []

    for idx, row in room_params_df.iterrows():
        # Generate Radiance scene
        scene = create_room_scene(
            width=row["room_width"],
            depth=row["room_depth"],
            height=row["room_height"],
            window_width=row["window_width"],
            window_height=row["window_height"],
            sill_height=row["sill_height"],
            vlt=row["vlt"],
            ceiling_reflectance=row["ceil_refl"],
            wall_reflectance=row["wall_refl"],
            floor_reflectance=row["floor_refl"],
            orientation=row["orientation"],
            obstruction_angle=row["obstruction_angle"],
        )

        # Define sensor grid (workplane at 0.75m height)
        sensors = create_sensor_grid(
            width=row["room_width"],
            depth=row["room_depth"],
            height=0.75,  # Workplane height
            spacing=0.5,  # 500mm grid
        )

        # Run annual daylight simulation
        sda, ase, mean_da = run_annual_daylight(scene, sensors, weather_file)

        results.append({
            **row.to_dict(),
            "sda_300_50": sda,       # Spatial Daylight Autonomy (300 lux, 50%)
            "ase_1000_250": ase,     # Annual Sunlight Exposure (1000 lux, 250h)
            "mean_daylight_autonomy": mean_da,
        })

    return pd.DataFrame(results)
```

### 3.3 Structural Parametric Pipeline (FEA)

```python
def run_structural_simulations(structural_params_df):
    """Generate structural training data using FEA."""
    results = []

    for idx, row in structural_params_df.iterrows():
        # Create structural model
        model = create_frame_model(
            num_stories=int(row["num_stories"]),
            bay_width_x=row["bay_width_x"],
            bay_width_y=row["bay_width_y"],
            num_bays_x=int(row["num_bays_x"]),
            num_bays_y=int(row["num_bays_y"]),
            floor_height=row["floor_height"],
            beam_depth=row["beam_depth"],
            column_size=row["column_size"],
            slab_thickness=row["slab_thickness"],
            concrete_strength=row["fc"],
            steel_yield=row["fy"],
        )

        # Apply loads
        apply_gravity_loads(model, row["dead_load"], row["live_load"])
        apply_wind_loads(model, row["wind_speed"], row["exposure_category"])
        apply_seismic_loads(model, row["seismic_zone"], row["soil_class"])

        # Run FEA
        fea_results = run_analysis(model)

        results.append({
            **row.to_dict(),
            "max_drift_ratio": fea_results.max_interstory_drift,
            "max_deflection_mm": fea_results.max_beam_deflection * 1000,
            "base_shear_kn": fea_results.base_shear,
            "max_column_axial_kn": fea_results.max_column_force,
            "period_t1": fea_results.fundamental_period,
            "weight_tonnes": fea_results.total_weight / 9.81 / 1000,
        })

    return pd.DataFrame(results)
```

---

## 4. Model Comparison

### 4.1 Random Forest

```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score

rf = RandomForestRegressor(
    n_estimators=500,       # Number of trees
    max_depth=None,         # Grow full trees
    min_samples_split=5,    # Minimum samples to split
    min_samples_leaf=2,     # Minimum samples in leaf
    max_features="sqrt",    # Features per split: sqrt(total)
    random_state=42,
    n_jobs=-1               # Use all cores
)

# Cross-validation
scores = cross_val_score(rf, X_train, y_train, cv=5, scoring="r2")
print(f"RF R2: {scores.mean():.3f} ± {scores.std():.3f}")
```

**Strengths for AEC**:
- No feature scaling needed (tree-based)
- Handles mixed feature types (numeric + categorical)
- Built-in feature importance
- Robust to outliers
- Good baseline performance (R2 > 0.90 typical for energy prediction)
- Fast training (seconds to minutes)

**Weaknesses**:
- Cannot extrapolate beyond training range
- Large ensemble size (memory for deployment)
- Does not capture smooth functions as well as GP or NN

### 4.2 XGBoost

```python
import xgboost as xgb

xgb_model = xgb.XGBRegressor(
    n_estimators=1000,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,          # L1 regularization
    reg_lambda=1.0,         # L2 regularization
    random_state=42,
    early_stopping_rounds=50,
    eval_metric="rmse",
)

xgb_model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    verbose=False
)
```

**Strengths for AEC**:
- State-of-the-art for tabular data (typically best R2)
- Built-in regularization (prevents overfitting)
- Handles missing values natively
- Fast inference
- Feature importance via gain, cover, frequency

**Weaknesses**:
- Requires hyperparameter tuning for best results
- Cannot extrapolate
- Less interpretable than linear models

### 4.3 MLP (Multi-Layer Perceptron)

```python
import torch
import torch.nn as nn

class EnergyPredictor(nn.Module):
    def __init__(self, input_dim, hidden_dims=[256, 128, 64], dropout=0.2):
        super().__init__()
        layers = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            prev_dim = h_dim
        layers.append(nn.Linear(prev_dim, 1))  # Single output: EUI
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)

model = EnergyPredictor(input_dim=15, hidden_dims=[256, 128, 64])
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10)
criterion = nn.MSELoss()

# Training loop
for epoch in range(500):
    model.train()
    for X_batch, y_batch in train_loader:
        pred = model(X_batch).squeeze()
        loss = criterion(pred, y_batch)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # Validation
    model.eval()
    with torch.no_grad():
        val_pred = model(X_val_tensor).squeeze()
        val_loss = criterion(val_pred, y_val_tensor)
    scheduler.step(val_loss)
```

**Strengths for AEC**:
- Universal approximator (can learn any function given enough data)
- Smooth predictions (differentiable; good for gradient-based optimization)
- Can capture complex non-linear interactions
- Scalable to large datasets

**Weaknesses**:
- Requires feature scaling (StandardScaler)
- Needs more data than tree-based methods (500+ samples typically)
- Hyperparameter-sensitive (architecture, learning rate, dropout)
- Black-box (less interpretable)
- Training is slower than RF/XGBoost

### 4.4 Gaussian Process Regression (GPR)

```python
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel

# Define kernel (covariance function)
kernel = (
    ConstantKernel(1.0, (1e-3, 1e3))
    * RBF(length_scale=np.ones(X_train.shape[1]), length_scale_bounds=(1e-2, 1e2))
    + WhiteKernel(noise_level=1e-2, noise_level_bounds=(1e-5, 1e1))
)

gpr = GaussianProcessRegressor(
    kernel=kernel,
    n_restarts_optimizer=10,
    normalize_y=True,
    alpha=1e-6,  # Nugget for numerical stability
)

gpr.fit(X_train, y_train)

# Prediction with uncertainty
y_pred, y_std = gpr.predict(X_test, return_std=True)

# 95% confidence interval
y_lower = y_pred - 1.96 * y_std
y_upper = y_pred + 1.96 * y_std
```

**Strengths for AEC**:
- Provides uncertainty estimates (confidence intervals)
- Excellent with small datasets (100-5000 samples)
- Principled Bayesian framework
- Smooth interpolation
- Hyperparameters learned from data (kernel optimization)

**Weaknesses**:
- O(n^3) training complexity (impractical for >10,000 samples)
- O(n^2) memory
- Sensitive to kernel choice
- Cannot handle categorical features natively (need encoding)

**When to use GPR in AEC**: Early design stages with limited simulation budget (100-1000 runs); when uncertainty quantification is important (structural safety margins, energy guarantee performance).

### 4.5 CNN for Field Prediction

For predicting spatial fields (temperature maps, daylight maps, wind fields):

```python
class FieldPredictor(nn.Module):
    """CNN that predicts a 2D performance field from a building geometry image."""

    def __init__(self):
        super().__init__()
        # Encoder (geometry image → features)
        self.encoder = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(128, 256, 3, padding=1), nn.ReLU(),
        )
        # Decoder (features → performance field)
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(256, 128, 4, stride=2, padding=1), nn.ReLU(),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1), nn.ReLU(),
            nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(32, 1, 1),  # Single-channel output (predicted field)
        )

    def forward(self, geometry_image):
        features = self.encoder(geometry_image)
        field = self.decoder(features)
        return field

# Input: 64x64 binary image of building floor plan (1=room, 0=wall/void)
# Output: 64x64 daylight factor map (float values 0-20%)
```

### 4.6 Model Comparison Summary

| Metric | Random Forest | XGBoost | MLP | GPR | CNN |
|--------|:------------:|:-------:|:---:|:---:|:---:|
| Typical R2 (energy) | 0.90-0.95 | 0.92-0.97 | 0.93-0.97 | 0.95-0.98 | 0.90-0.95* |
| Training time | Seconds | Minutes | Minutes-Hours | Hours | Hours |
| Inference time | ~1ms | ~0.5ms | ~0.1ms | ~10ms | ~5ms |
| Min training data | 100 | 200 | 500 | 50 | 1000 |
| Interpretability | Medium | Medium | Low | High** | Low |
| Uncertainty | No*** | No | No | Yes | No |
| Extrapolation | No | No | Limited | Limited | No |
| Feature scaling needed | No | No | Yes | Yes | Yes |
| Handles categoricals | Yes | Yes | Encoded | Encoded | N/A |

*CNN for field prediction, not scalar prediction
**GPR interpretability from kernel analysis
***RF can provide prediction intervals from tree variance, but not principled uncertainty

---

## 5. Hyperparameter Tuning

### 5.1 Tuning Strategy

```python
import optuna

def objective(trial):
    """Optuna objective function for XGBoost hyperparameter tuning."""

    params = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 2000),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
    }

    model = xgb.XGBRegressor(**params, random_state=42, early_stopping_rounds=50)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    y_pred = model.predict(X_val)
    r2 = r2_score(y_val, y_pred)
    return r2

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=200, timeout=3600)
print(f"Best R2: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")
```

### 5.2 Recommended Search Ranges

| Model | Hyperparameter | Range | Notes |
|-------|---------------|-------|-------|
| Random Forest | n_estimators | 100-1000 | More trees rarely hurts (diminishing returns) |
| Random Forest | max_depth | None, 10-50 | None = full depth; limit for speed/memory |
| Random Forest | min_samples_leaf | 1-10 | Higher = more regularization |
| XGBoost | n_estimators | 100-2000 | Use early stopping |
| XGBoost | max_depth | 3-10 | 6 is a good default |
| XGBoost | learning_rate | 0.01-0.3 | Lower lr + more trees = better |
| MLP | hidden_layers | 2-4 | 3 is usually sufficient |
| MLP | hidden_dim | 32-512 | Scale with dataset size |
| MLP | dropout | 0.1-0.5 | Higher for small datasets |
| MLP | learning_rate | 1e-4 to 1e-2 | Use scheduler |
| GPR | kernel | RBF, Matern, RQ | RBF is default; Matern(nu=2.5) for less smooth |
| GPR | length_scale | 0.01-100 | Per-feature; learned automatically |

---

## 6. Cross-Validation for AEC

### 6.1 Standard k-Fold

```python
from sklearn.model_selection import KFold, cross_val_score

kf = KFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(model, X, y, cv=kf, scoring="r2")
print(f"R2: {scores.mean():.3f} ± {scores.std():.3f}")
```

### 6.2 Spatial Cross-Validation (Group k-Fold)

For AEC data where samples from the same project/building should not be split between train and test:

```python
from sklearn.model_selection import GroupKFold

# group_labels: project ID for each sample
gkf = GroupKFold(n_splits=5)
scores = cross_val_score(model, X, y, cv=gkf, groups=group_labels, scoring="r2")
```

This prevents data leakage when multiple rooms/floors from the same building are in the dataset. Samples from the same building are correlated; putting some in train and others in test inflates the R2 estimate.

### 6.3 Leave-One-Building-Out (LOBO)

The most stringent validation for AEC:

```python
from sklearn.model_selection import LeaveOneGroupOut

logo = LeaveOneGroupOut()
scores = cross_val_score(model, X, y, cv=logo, groups=building_ids, scoring="r2")
# Each fold: train on all buildings except one; test on the held-out building
```

If R2 is high in LOBO cross-validation, the model generalizes well to new buildings.

---

## 7. Model Interpretability

### 7.1 SHAP (SHapley Additive exPlanations)

```python
import shap

# Train model
model = xgb.XGBRegressor(**best_params)
model.fit(X_train, y_train)

# Compute SHAP values
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)

# Summary plot: feature importance + direction of effect
shap.summary_plot(shap_values, X_test, feature_names=feature_names)

# For a single prediction: why did the model predict this EUI?
shap.force_plot(explainer.expected_value, shap_values[0], X_test.iloc[0])

# Dependence plot: how does one feature affect prediction?
shap.dependence_plot("wwr_south", shap_values, X_test, feature_names=feature_names)
```

**SHAP interpretation for AEC**:
- "The model predicts EUI = 145 kWh/m2/yr because: high WWR_south (+15), low wall_U_value (-20), warm climate CDD (+12), ..."
- Provides both global feature importance AND local explanation for each prediction
- Essential for building trust with architects and engineers ("why does the model say this?")

### 7.2 Partial Dependence Plots

```python
from sklearn.inspection import PartialDependenceDisplay

# How does EUI change with WWR_south (holding all other features constant)?
PartialDependenceDisplay.from_estimator(
    model, X_train,
    features=["wwr_south", "wall_u_value", ("wwr_south", "wall_u_value")],
    kind="both",  # Individual + average
    feature_names=feature_names
)
```

**AEC insight**: PDP shows that EUI increases linearly with WWR_south beyond 0.40 in cooling-dominated climates, confirming the diminishing returns of daylighting above certain glazing ratios.

### 7.3 Confidence Intervals

For GP models, confidence intervals come free. For other models, approximate with:

**Bootstrap confidence intervals**:
```python
from sklearn.utils import resample

n_bootstrap = 100
predictions = []

for i in range(n_bootstrap):
    X_boot, y_boot = resample(X_train, y_train, random_state=i)
    model_boot = xgb.XGBRegressor(**best_params)
    model_boot.fit(X_boot, y_boot)
    pred = model_boot.predict(X_test)
    predictions.append(pred)

predictions = np.array(predictions)
y_mean = predictions.mean(axis=0)
y_lower = np.percentile(predictions, 2.5, axis=0)
y_upper = np.percentile(predictions, 97.5, axis=0)
# 95% confidence interval: [y_lower, y_upper]
```

---

## 8. Model Updating with New Data

### 8.1 Online Learning / Incremental Update

When new simulation data or measurement data becomes available:

**For tree-based models (XGBoost)**: Continue training (warm start) with new data:
```python
# Initial training
model = xgb.XGBRegressor(n_estimators=500)
model.fit(X_initial, y_initial)

# Update with new data (add more trees)
model.fit(X_new, y_new, xgb_model=model.get_booster())
```

**For neural networks**: Fine-tune on new data with low learning rate:
```python
optimizer = torch.optim.Adam(model.parameters(), lr=1e-5)  # Low LR
for epoch in range(50):
    for X_batch, y_batch in new_data_loader:
        pred = model(X_batch)
        loss = criterion(pred, y_batch)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
```

**For Gaussian Processes**: Add new data points and re-compute posterior (exact update).

### 8.2 Transfer Learning Between Building Types

Train on data-rich building type (e.g., office); transfer to data-poor building type (e.g., museum):

1. Train base model on office data (large dataset)
2. Freeze early layers (general building physics features)
3. Fine-tune late layers on museum data (small dataset)
4. Evaluate on held-out museum buildings

---

## 9. Deployment as Grasshopper Component

### 9.1 Grasshopper + Python via Hops

```python
"""Grasshopper Hops endpoint for energy prediction."""
from flask import Flask
import ghhops_server as hs
import joblib
import numpy as np

app = Flask(__name__)
hops = hs.Hops(app)

# Load pre-trained model
model = joblib.load("energy_surrogate_xgboost.joblib")
scaler = joblib.load("feature_scaler.joblib")

@hops.component(
    "/predict_eui",
    name="Predict EUI",
    description="Predict building EUI from design parameters",
    inputs=[
        hs.HopsNumber("WWR_S", "WWR South", "Window-to-wall ratio south"),
        hs.HopsNumber("WWR_N", "WWR North", "Window-to-wall ratio north"),
        hs.HopsNumber("WWR_E", "WWR East", "Window-to-wall ratio east"),
        hs.HopsNumber("WWR_W", "WWR West", "Window-to-wall ratio west"),
        hs.HopsNumber("Wall_U", "Wall U-value", "W/(m2K)"),
        hs.HopsNumber("Glaz_U", "Glazing U-value", "W/(m2K)"),
        hs.HopsNumber("SHGC", "SHGC", "Solar heat gain coefficient"),
    ],
    outputs=[
        hs.HopsNumber("EUI", "EUI", "Predicted EUI (kWh/m2/yr)"),
        hs.HopsString("Rating", "Rating", "Energy performance rating"),
    ]
)
def predict_eui(wwr_s, wwr_n, wwr_e, wwr_w, wall_u, glaz_u, shgc):
    features = np.array([[wwr_s, wwr_n, wwr_e, wwr_w, wall_u, glaz_u, shgc]])
    features_scaled = scaler.transform(features)
    eui = float(model.predict(features_scaled)[0])

    if eui < 80:
        rating = "Excellent"
    elif eui < 120:
        rating = "Good"
    elif eui < 170:
        rating = "Average"
    else:
        rating = "Poor"

    return eui, rating

if __name__ == "__main__":
    app.run(port=5000)
```

### 9.2 ONNX Runtime for Revit Add-in

```csharp
// C# Revit add-in using ONNX Runtime for energy prediction
using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;

public class EnergyPredictor
{
    private InferenceSession session;

    public EnergyPredictor(string modelPath)
    {
        session = new InferenceSession(modelPath);
    }

    public float PredictEUI(float[] features)
    {
        var tensor = new DenseTensor<float>(features, new[] { 1, features.Length });
        var inputs = new List<NamedOnnxValue>
        {
            NamedOnnxValue.CreateFromTensor("input", tensor)
        };

        using var results = session.Run(inputs);
        return results.First().AsTensor<float>().First();
    }
}
```

---

## 10. Case Studies

### 10.1 Office Building Energy Surrogate

**Project**: Surrogate for EnergyPlus model of a 10-story office building in London
**Parameters**: 15 (envelope, WWR, HVAC, LPD, infiltration, orientation)
**Training data**: 2,000 LHS samples, EnergyPlus runs (total: 167 hours on 12-core machine)
**Model**: XGBoost (500 estimators, max_depth=6)
**Result**: R2 = 0.96, RMSE = 6.2 kWh/m2/yr (mean EUI = 142)
**Deployment**: Grasshopper Hops component; architects adjust sliders, see instant EUI
**Impact**: 10,000+ evaluations during design optimization vs. ~50 possible with full simulation

### 10.2 Residential Daylight Prediction

**Project**: sDA prediction for residential rooms in Singapore
**Parameters**: 8 (room dimensions, window geometry, orientation, obstruction)
**Training data**: 5,000 Radiance simulations (3-point bounce, annual daylight)
**Model**: GPR with RBF kernel (per-feature length scales)
**Result**: R2 = 0.94, MAE = 3.2% sDA
**Uncertainty**: 95% CI width = ±8% sDA (useful for design decisions)
**Deployment**: Web app (Streamlit); designers input room parameters, get sDA prediction with confidence band

### 10.3 Wind Comfort Surrogate

**Project**: Pedestrian-level wind speed prediction for urban development in Hong Kong
**Parameters**: Voxelized building massing (64x64x16 grid) + wind direction (16 sectors)
**Training data**: 1,200 CFD simulations (OpenFOAM, ~2 hours each)
**Model**: 3D CNN encoder → FC layers → wind speed map
**Result**: R2 = 0.88, RMSE = 0.45 m/s (mean wind speed = 3.2 m/s)
**Deployment**: Python API called from Grasshopper; massing model → voxelized → inference → wind map overlay
**Impact**: Massing options evaluated in 2 seconds instead of 2 hours; enabled optimization of building placement for wind comfort

### 10.4 Structural Weight Prediction

**Project**: Early-stage structural weight estimation for high-rise buildings
**Parameters**: 12 (stories, bay sizes, floor height, live load, seismic zone, wind speed)
**Training data**: 800 structural models analyzed in ETABS
**Model**: Random Forest (300 estimators)
**Result**: R2 = 0.92, MAPE = 8% for total structural weight
**Feature importance**: Number of stories (32%), bay width (18%), seismic zone (15%), wind speed (12%)
**Deployment**: Excel VBA macro calling Python model via subprocess

### 10.5 Acoustic RT60 Surrogate

**Project**: Reverberation time prediction for concert halls and lecture theaters
**Parameters**: 10 (volume, surface areas by material, absorption coefficients, seating)
**Training data**: 600 ODEON acoustic simulations + 50 measured rooms
**Model**: MLP (3 hidden layers: 128-64-32) with uncertainty via MC dropout
**Result**: R2 = 0.93 for mid-frequency RT60 (500-1000 Hz)
**Deployment**: Grasshopper component for real-time acoustic feedback during auditorium design
**Validation**: Compared predictions against 15 measured rooms not in training data; all within ±0.2s of measured RT60
