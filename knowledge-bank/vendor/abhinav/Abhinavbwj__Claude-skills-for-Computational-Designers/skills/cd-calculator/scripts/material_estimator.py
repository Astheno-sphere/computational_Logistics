#!/usr/bin/env python3
"""
Material Estimator for AEC Computational Design
==================================================
Estimates material quantities, weights, and embodied carbon for buildings
at the early design stage. Two modes:

  - Parametric: from building type and gross floor area (GFA)
  - Direct: from explicit material volumes/areas

Usage:
    python material_estimator.py --building-type residential --gfa 5000 --floors 8
    python material_estimator.py --concrete-volume 450 --steel-ratio 120 --glass-area 2000 --include-embodied-carbon
    python material_estimator.py --building-type office --gfa 12000 --floors 20 --waste-factor 1.12 --include-embodied-carbon
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Constants and benchmarks
# ---------------------------------------------------------------------------

# Concrete benchmarks: m^3 per m^2 GFA
CONCRETE_RATES = {
    "residential": 0.17,
    "office": 0.15,
    "industrial": 0.10,
    "retail": 0.12,
}

# Reinforcement steel ratio: kg per m^3 of concrete
REBAR_RATES = {
    "residential": 100,
    "office": 110,
    "industrial": 85,
    "retail": 95,
}

# Structural steel: kg per m^2 GFA
STEEL_RATES = {
    "residential": 10,
    "office": 35,
    "industrial": 28,
    "retail": 30,
}

# Glass: m^2 glass per m^2 GFA
GLASS_RATES = {
    "residential": 0.12,
    "office": 0.30,
    "industrial": 0.05,
    "retail": 0.20,
}

# Timber: m^3 per m^2 GFA
TIMBER_RATES = {
    "residential": 0.03,
    "office": 0.01,
    "industrial": 0.005,
    "retail": 0.01,
}

# Material densities (kg/m^3 or kg/m^2)
DENSITIES = {
    "concrete": 2400,       # kg/m^3
    "steel": 7850,          # kg/m^3
    "glass_per_m2": 30,     # kg/m^2 (typical IGU)
    "timber_softwood": 450, # kg/m^3
}

# Default waste factors
DEFAULT_WASTE = {
    "concrete": 1.07,
    "rebar": 1.07,
    "structural_steel": 1.04,
    "glass": 1.07,
    "timber": 1.12,
}

# Embodied carbon factors
CARBON_FACTORS = {
    "concrete_per_m3": 250,         # kgCO2e per m^3 (C30/37)
    "rebar_per_tonne": 1500,        # kgCO2e per tonne
    "structural_steel_per_tonne": 1500,  # kgCO2e per tonne
    "glass_per_m2": 55,             # kgCO2e per m^2 (IGU)
    "timber_per_m3": -450,          # kgCO2e per m^3 (carbon stored, negative)
}


# ---------------------------------------------------------------------------
# Estimation functions
# ---------------------------------------------------------------------------

def estimate_parametric(building_type, gfa, floors, waste_override=None, include_carbon=False):
    """Estimate material quantities from building type and GFA."""
    bt = building_type.lower()
    if bt not in CONCRETE_RATES:
        return None, f"Unknown building type '{building_type}'. Choose from: {', '.join(CONCRETE_RATES.keys())}."
    if gfa <= 0:
        return None, "GFA must be positive."
    if floors <= 0:
        return None, "Number of floors must be positive."

    floor_area = gfa / floors

    # Base quantities (before waste)
    concrete_vol = CONCRETE_RATES[bt] * gfa
    rebar_mass = concrete_vol * REBAR_RATES[bt] / 1000  # tonnes
    structural_steel_mass = STEEL_RATES[bt] * gfa / 1000  # tonnes
    glass_area = GLASS_RATES[bt] * gfa
    timber_vol = TIMBER_RATES[bt] * gfa

    # Apply waste factors
    wf = waste_override if waste_override else None

    concrete_waste = wf if wf else DEFAULT_WASTE["concrete"]
    rebar_waste = wf if wf else DEFAULT_WASTE["rebar"]
    steel_waste = wf if wf else DEFAULT_WASTE["structural_steel"]
    glass_waste = wf if wf else DEFAULT_WASTE["glass"]
    timber_waste = wf if wf else DEFAULT_WASTE["timber"]

    concrete_vol_w = concrete_vol * concrete_waste
    rebar_mass_w = rebar_mass * rebar_waste
    steel_mass_w = structural_steel_mass * steel_waste
    glass_area_w = glass_area * glass_waste
    timber_vol_w = timber_vol * timber_waste

    # Weights
    concrete_weight = concrete_vol_w * DENSITIES["concrete"] / 1000  # tonnes
    glass_weight = glass_area_w * DENSITIES["glass_per_m2"] / 1000  # tonnes
    timber_weight = timber_vol_w * DENSITIES["timber_softwood"] / 1000  # tonnes

    total_weight = concrete_weight + rebar_mass_w + steel_mass_w + glass_weight + timber_weight

    result = {
        "mode": "parametric",
        "building_type": building_type.capitalize(),
        "gfa_m2": gfa,
        "floors": floors,
        "floor_area_m2": round(floor_area, 2),
        "materials": {
            "concrete": {
                "volume_m3": round(concrete_vol_w, 2),
                "weight_tonnes": round(concrete_weight, 2),
                "waste_factor": concrete_waste,
            },
            "rebar_steel": {
                "weight_tonnes": round(rebar_mass_w, 2),
                "ratio_kg_per_m3": REBAR_RATES[bt],
                "waste_factor": rebar_waste,
            },
            "structural_steel": {
                "weight_tonnes": round(steel_mass_w, 2),
                "ratio_kg_per_m2": STEEL_RATES[bt],
                "waste_factor": steel_waste,
            },
            "glass": {
                "area_m2": round(glass_area_w, 2),
                "weight_tonnes": round(glass_weight, 2),
                "waste_factor": glass_waste,
            },
            "timber": {
                "volume_m3": round(timber_vol_w, 2),
                "weight_tonnes": round(timber_weight, 2),
                "waste_factor": timber_waste,
            },
        },
        "total_weight_tonnes": round(total_weight, 2),
    }

    if include_carbon:
        carbon = compute_embodied_carbon(
            concrete_vol_w, rebar_mass_w, steel_mass_w, glass_area_w, timber_vol_w, gfa
        )
        result["embodied_carbon"] = carbon

    return result, None


def estimate_direct(concrete_vol, steel_ratio, glass_area, timber_vol,
                    waste_override=None, include_carbon=False):
    """Estimate from explicit material quantities."""
    # Default values for missing inputs
    if concrete_vol is None:
        concrete_vol = 0
    if steel_ratio is None:
        steel_ratio = 100  # default kg/m^3
    if glass_area is None:
        glass_area = 0
    if timber_vol is None:
        timber_vol = 0

    if concrete_vol < 0 or glass_area < 0 or timber_vol < 0:
        return None, "Material quantities must be non-negative."

    wf = waste_override

    # Rebar
    rebar_mass = concrete_vol * steel_ratio / 1000  # tonnes

    # Apply waste
    concrete_waste = wf if wf else DEFAULT_WASTE["concrete"]
    rebar_waste = wf if wf else DEFAULT_WASTE["rebar"]
    glass_waste = wf if wf else DEFAULT_WASTE["glass"]
    timber_waste = wf if wf else DEFAULT_WASTE["timber"]

    concrete_vol_w = concrete_vol * concrete_waste
    rebar_mass_w = rebar_mass * rebar_waste
    glass_area_w = glass_area * glass_waste
    timber_vol_w = timber_vol * timber_waste

    # Weights
    concrete_weight = concrete_vol_w * DENSITIES["concrete"] / 1000
    glass_weight = glass_area_w * DENSITIES["glass_per_m2"] / 1000
    timber_weight = timber_vol_w * DENSITIES["timber_softwood"] / 1000

    total_weight = concrete_weight + rebar_mass_w + glass_weight + timber_weight

    result = {
        "mode": "direct",
        "materials": {
            "concrete": {
                "volume_m3": round(concrete_vol_w, 2),
                "weight_tonnes": round(concrete_weight, 2),
                "waste_factor": concrete_waste,
            },
            "rebar_steel": {
                "weight_tonnes": round(rebar_mass_w, 2),
                "ratio_kg_per_m3": steel_ratio,
                "waste_factor": rebar_waste,
            },
            "glass": {
                "area_m2": round(glass_area_w, 2),
                "weight_tonnes": round(glass_weight, 2),
                "waste_factor": glass_waste,
            },
            "timber": {
                "volume_m3": round(timber_vol_w, 2),
                "weight_tonnes": round(timber_weight, 2),
                "waste_factor": timber_waste,
            },
        },
        "total_weight_tonnes": round(total_weight, 2),
    }

    if include_carbon:
        carbon = compute_embodied_carbon(
            concrete_vol_w, rebar_mass_w, 0, glass_area_w, timber_vol_w, None
        )
        result["embodied_carbon"] = carbon

    return result, None


def compute_embodied_carbon(concrete_vol, rebar_tonnes, steel_tonnes, glass_m2, timber_vol, gfa):
    """Compute embodied carbon for all materials."""
    c_concrete = concrete_vol * CARBON_FACTORS["concrete_per_m3"]
    c_rebar = rebar_tonnes * CARBON_FACTORS["rebar_per_tonne"]
    c_steel = steel_tonnes * CARBON_FACTORS["structural_steel_per_tonne"]
    c_glass = glass_m2 * CARBON_FACTORS["glass_per_m2"]
    c_timber = timber_vol * CARBON_FACTORS["timber_per_m3"]  # negative (carbon stored)

    total = c_concrete + c_rebar + c_steel + c_glass + c_timber

    carbon = {
        "concrete_kgCO2e": round(c_concrete, 0),
        "rebar_kgCO2e": round(c_rebar, 0),
        "structural_steel_kgCO2e": round(c_steel, 0),
        "glass_kgCO2e": round(c_glass, 0),
        "timber_kgCO2e": round(c_timber, 0),
        "total_kgCO2e": round(total, 0),
    }
    if gfa and gfa > 0:
        carbon["per_m2_gfa_kgCO2e"] = round(total / gfa, 2)

    return carbon


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    return f"{val:,.{decimals}f}"


def print_parametric_results(r):
    print("=" * 52)
    print("  MATERIAL ESTIMATOR - Parametric")
    print("=" * 52)
    print()
    print("  Building Parameters:")
    print(f"    Type             : {r['building_type']}")
    print(f"    Gross Floor Area : {fmt(r['gfa_m2'])} m^2")
    print(f"    Floors           : {r['floors']:>8}")
    print(f"    Floor Area/Floor : {fmt(r['floor_area_m2'])} m^2")
    print()

    m = r["materials"]
    print("  Material Quantities (incl. waste):")
    print(f"    Concrete         : {fmt(m['concrete']['volume_m3'])} m^3  ({fmt(m['concrete']['weight_tonnes'])} tonnes)")
    print(f"    Rebar Steel      : {fmt(m['rebar_steel']['weight_tonnes'])} tonnes")
    print(f"    Structural Steel : {fmt(m['structural_steel']['weight_tonnes'])} tonnes")
    print(f"    Glass            : {fmt(m['glass']['area_m2'])} m^2  ({fmt(m['glass']['weight_tonnes'])} tonnes)")
    print(f"    Timber           : {fmt(m['timber']['volume_m3'])} m^3  ({fmt(m['timber']['weight_tonnes'])} tonnes)")
    print()
    print(f"  Total Weight       : {fmt(r['total_weight_tonnes'])} tonnes")

    if "embodied_carbon" in r:
        print()
        print_carbon(r["embodied_carbon"])

    print("=" * 52)


def print_direct_results(r):
    print("=" * 52)
    print("  MATERIAL ESTIMATOR - Direct")
    print("=" * 52)
    print()

    m = r["materials"]
    print("  Material Quantities (incl. waste):")
    if m["concrete"]["volume_m3"] > 0:
        print(f"    Concrete         : {fmt(m['concrete']['volume_m3'])} m^3  ({fmt(m['concrete']['weight_tonnes'])} tonnes)")
        print(f"    Rebar Steel      : {fmt(m['rebar_steel']['weight_tonnes'])} tonnes")
    if m["glass"]["area_m2"] > 0:
        print(f"    Glass            : {fmt(m['glass']['area_m2'])} m^2  ({fmt(m['glass']['weight_tonnes'])} tonnes)")
    if m["timber"]["volume_m3"] > 0:
        print(f"    Timber           : {fmt(m['timber']['volume_m3'])} m^3  ({fmt(m['timber']['weight_tonnes'])} tonnes)")
    print()
    print(f"  Total Weight       : {fmt(r['total_weight_tonnes'])} tonnes")

    if "embodied_carbon" in r:
        print()
        print_carbon(r["embodied_carbon"])

    print("=" * 52)


def print_carbon(c):
    print("  Embodied Carbon:")
    if c["concrete_kgCO2e"] != 0:
        print(f"    Concrete         : {fmt(c['concrete_kgCO2e'], 0)} kgCO2e")
    if c["rebar_kgCO2e"] != 0:
        print(f"    Rebar Steel      : {fmt(c['rebar_kgCO2e'], 0)} kgCO2e")
    if c["structural_steel_kgCO2e"] != 0:
        print(f"    Structural Steel : {fmt(c['structural_steel_kgCO2e'], 0)} kgCO2e")
    if c["glass_kgCO2e"] != 0:
        print(f"    Glass            : {fmt(c['glass_kgCO2e'], 0)} kgCO2e")
    if c["timber_kgCO2e"] != 0:
        label = "kgCO2e (carbon stored)" if c["timber_kgCO2e"] < 0 else "kgCO2e"
        print(f"    Timber           : {fmt(c['timber_kgCO2e'], 0)} {label}")
    print(f"    {'-' * 36}")
    print(f"    Total            : {fmt(c['total_kgCO2e'], 0)} kgCO2e")
    if "per_m2_gfa_kgCO2e" in c:
        print(f"    Per m^2 GFA      : {fmt(c['per_m2_gfa_kgCO2e'])} kgCO2e/m^2")


# ---------------------------------------------------------------------------
# Argument parsing and main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Material Estimator - Quantity takeoff and embodied carbon"
    )
    # Parametric mode
    parser.add_argument("--building-type", type=str, default=None,
                        help="Building type: residential, office, industrial, retail")
    parser.add_argument("--gfa", type=float, default=None, help="Gross floor area (m^2)")
    parser.add_argument("--floors", type=int, default=None, help="Number of floors")

    # Direct mode
    parser.add_argument("--concrete-volume", type=float, default=None, help="Concrete volume (m^3)")
    parser.add_argument("--steel-ratio", type=float, default=None, help="Rebar ratio (kg/m^3 of concrete)")
    parser.add_argument("--glass-area", type=float, default=None, help="Glass area (m^2)")
    parser.add_argument("--timber-volume", type=float, default=None, help="Timber volume (m^3)")

    # Options
    parser.add_argument("--waste-factor", type=float, default=None,
                        help="Override waste factor (e.g. 1.10)")
    parser.add_argument("--include-embodied-carbon", action="store_true",
                        help="Calculate embodied carbon")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Validate waste factor
    if args.waste_factor is not None and args.waste_factor < 1.0:
        print("ERROR: Waste factor should be >= 1.0 (e.g. 1.10 for 10% waste).", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    parametric_args = [args.building_type, args.gfa, args.floors]
    direct_args = [args.concrete_volume, args.glass_area, args.timber_volume]

    parametric_mode = all(a is not None for a in parametric_args)
    direct_mode = any(a is not None for a in direct_args) and not parametric_mode

    if parametric_mode:
        result, error = estimate_parametric(
            args.building_type, args.gfa, args.floors,
            args.waste_factor, args.include_embodied_carbon
        )
        printer = print_parametric_results
    elif direct_mode:
        result, error = estimate_direct(
            args.concrete_volume, args.steel_ratio, args.glass_area, args.timber_volume,
            args.waste_factor, args.include_embodied_carbon
        )
        printer = print_direct_results
    else:
        print("ERROR: Provide either parametric inputs (--building-type, --gfa, --floors)", file=sys.stderr)
        print("       or direct inputs (--concrete-volume, --glass-area, --timber-volume).", file=sys.stderr)
        sys.exit(1)

    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        printer(result)


if __name__ == "__main__":
    main()
