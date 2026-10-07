#!/usr/bin/env python3
"""
Fabrication Calculator for AEC Computational Design
=====================================================
Estimates fabrication time and cost for three digital fabrication processes:
CNC milling, FDM 3D printing, and laser cutting.

Uses industry-standard feed rates, material costs, and process parameters
to provide realistic estimates for budgeting and scheduling.

Usage:
    python fabrication_calculator.py --process cnc-milling --path-length 5000 --tool-changes 3 --material wood
    python fabrication_calculator.py --process 3d-print --volume 500 --height 200 --layer-height 0.2
    python fabrication_calculator.py --process laser-cut --cut-length 8000 --material acrylic --thickness 6
    python fabrication_calculator.py --process cnc-milling --path-length 12000 --tool-changes 5 --material aluminum --hourly-rate 120
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Material and process databases
# ---------------------------------------------------------------------------

# CNC milling: feed rates in mm/min
CNC_MATERIALS = {
    "wood": {
        "name": "Wood (Hardwood)",
        "feed_rate": 3000,
        "material_cost_per_cm3": 0.008,  # $/cm^3
        "tool_change_time": 2.0,  # minutes
    },
    "softwood": {
        "name": "Wood (Softwood)",
        "feed_rate": 4500,
        "material_cost_per_cm3": 0.005,
        "tool_change_time": 2.0,
    },
    "mdf": {
        "name": "MDF",
        "feed_rate": 4000,
        "material_cost_per_cm3": 0.003,
        "tool_change_time": 2.0,
    },
    "plywood": {
        "name": "Plywood",
        "feed_rate": 3500,
        "material_cost_per_cm3": 0.006,
        "tool_change_time": 2.0,
    },
    "acrylic": {
        "name": "Acrylic (PMMA)",
        "feed_rate": 1500,
        "material_cost_per_cm3": 0.025,
        "tool_change_time": 2.5,
    },
    "aluminum": {
        "name": "Aluminum",
        "feed_rate": 1200,
        "material_cost_per_cm3": 0.015,
        "tool_change_time": 3.0,
    },
    "steel": {
        "name": "Mild Steel",
        "feed_rate": 400,
        "material_cost_per_cm3": 0.010,
        "tool_change_time": 3.0,
    },
    "foam": {
        "name": "Foam (EPS/XPS)",
        "feed_rate": 7500,
        "material_cost_per_cm3": 0.002,
        "tool_change_time": 1.5,
    },
    "brass": {
        "name": "Brass",
        "feed_rate": 800,
        "material_cost_per_cm3": 0.045,
        "tool_change_time": 3.0,
    },
}

# 3D printing: material properties
PRINT_MATERIALS = {
    "pla": {
        "name": "PLA",
        "density": 1.24,  # g/cm^3
        "print_speed": 60,  # mm/s
        "cost_per_kg": 25,  # $/kg
        "nozzle_temp": "190-220",
        "bed_temp": "50-60",
    },
    "petg": {
        "name": "PETG",
        "density": 1.27,
        "print_speed": 50,
        "cost_per_kg": 30,
        "nozzle_temp": "220-250",
        "bed_temp": "70-80",
    },
    "abs": {
        "name": "ABS",
        "density": 1.04,
        "print_speed": 50,
        "cost_per_kg": 25,
        "nozzle_temp": "230-260",
        "bed_temp": "90-110",
    },
    "nylon": {
        "name": "Nylon",
        "density": 1.14,
        "print_speed": 40,
        "cost_per_kg": 50,
        "nozzle_temp": "240-270",
        "bed_temp": "70-90",
    },
    "tpu": {
        "name": "TPU",
        "density": 1.21,
        "print_speed": 30,
        "cost_per_kg": 40,
        "nozzle_temp": "210-230",
        "bed_temp": "40-60",
    },
}

# Laser cutting: speed tables (mm/min) by material and thickness
LASER_MATERIALS = {
    "acrylic": {
        "name": "Acrylic",
        "speeds": {
            2: 3000, 3: 2400, 4: 1800, 5: 1400, 6: 1200,
            8: 800, 10: 600, 12: 400, 15: 250, 20: 150,
        },
        "cost_per_m2": {  # by thickness
            2: 18, 3: 22, 4: 28, 5: 32, 6: 38,
            8: 48, 10: 60, 12: 75, 15: 95, 20: 130,
        },
    },
    "plywood": {
        "name": "Plywood (Birch)",
        "speeds": {
            2: 3500, 3: 3000, 4: 2200, 5: 1800, 6: 1500,
            8: 1000, 9: 800, 10: 600, 12: 400,
        },
        "cost_per_m2": {
            2: 8, 3: 10, 4: 13, 5: 15, 6: 18,
            8: 24, 9: 28, 10: 32, 12: 42,
        },
    },
    "mdf": {
        "name": "MDF",
        "speeds": {
            2: 3000, 3: 2500, 4: 2000, 5: 1600, 6: 1200,
            8: 800, 10: 500, 12: 350,
        },
        "cost_per_m2": {
            2: 5, 3: 7, 4: 9, 5: 11, 6: 14, 8: 18, 10: 24, 12: 30,
        },
    },
    "cardboard": {
        "name": "Cardboard",
        "speeds": {
            1: 6000, 2: 4500, 3: 3500, 4: 2500, 5: 1800,
        },
        "cost_per_m2": {
            1: 2, 2: 3, 3: 4, 4: 5, 5: 7,
        },
    },
    "steel": {
        "name": "Mild Steel (Fiber Laser)",
        "speeds": {
            0.5: 6000, 1: 3000, 1.5: 2200, 2: 1800, 3: 1500,
            4: 1100, 5: 900, 6: 800, 8: 500, 10: 300, 12: 200,
        },
        "cost_per_m2": {
            0.5: 12, 1: 20, 1.5: 28, 2: 35, 3: 50,
            4: 65, 5: 80, 6: 95, 8: 130, 10: 170, 12: 210,
        },
    },
    "aluminum": {
        "name": "Aluminum (Fiber Laser)",
        "speeds": {
            0.5: 5000, 1: 2500, 1.5: 1800, 2: 1400, 3: 1000,
            4: 700, 5: 500, 6: 350,
        },
        "cost_per_m2": {
            0.5: 15, 1: 25, 1.5: 35, 2: 45, 3: 65,
            4: 85, 5: 110, 6: 135,
        },
    },
}

DEFAULT_HOURLY_RATE = 75.0  # $/hr
CNC_SETUP_TIME = 15.0  # minutes
PRINT_LAYER_OVERHEAD = 3.0  # seconds per layer (retraction, z-hop)
LASER_SETUP_TIME = 5.0  # minutes
DEFAULT_NOZZLE_DIAMETER = 0.4  # mm


# ---------------------------------------------------------------------------
# Process estimators
# ---------------------------------------------------------------------------

def estimate_cnc(args):
    """CNC milling time and cost estimate."""
    mat_key = args.material.lower() if args.material else "wood"
    if mat_key not in CNC_MATERIALS:
        return None, f"Unknown CNC material '{args.material}'. Choose from: {', '.join(CNC_MATERIALS.keys())}."

    path_length = args.path_length
    if path_length is None or path_length <= 0:
        return None, "Path length must be a positive number (mm)."

    tool_changes = args.tool_changes if args.tool_changes else 0
    if tool_changes < 0:
        return None, "Tool changes must be non-negative."

    mat = CNC_MATERIALS[mat_key]
    feed_rate = args.feed_rate if args.feed_rate else mat["feed_rate"]
    hourly_rate = args.hourly_rate if args.hourly_rate else DEFAULT_HOURLY_RATE

    # Time calculations
    cutting_time = path_length / feed_rate  # minutes
    tool_change_time = tool_changes * mat["tool_change_time"]  # minutes
    setup_time = CNC_SETUP_TIME
    total_time = cutting_time + tool_change_time + setup_time

    # Cost
    machine_cost = (total_time / 60) * hourly_rate
    # Rough material cost estimate (based on path length and typical depth)
    # Assume average cut depth of 5mm, width of 6mm (typical endmill)
    material_volume_cm3 = (path_length * 6 * 5) / 1000  # mm^3 to cm^3
    material_cost = material_volume_cm3 * mat["material_cost_per_cm3"]
    total_cost = machine_cost + material_cost

    result = {
        "process": "CNC Milling",
        "material": mat["name"],
        "path_length_mm": path_length,
        "feed_rate_mm_per_min": feed_rate,
        "tool_changes": tool_changes,
        "tool_change_time_min": mat["tool_change_time"],
        "cutting_time_min": round(cutting_time, 2),
        "tool_change_total_min": round(tool_change_time, 2),
        "setup_time_min": setup_time,
        "total_time_min": round(total_time, 2),
        "total_time_hr": round(total_time / 60, 2),
        "hourly_rate": hourly_rate,
        "machine_cost": round(machine_cost, 2),
        "material_cost_est": round(material_cost, 2),
        "total_cost": round(total_cost, 2),
    }
    return result, None


def estimate_3d_print(args):
    """FDM 3D printing time and cost estimate."""
    mat_key = (args.material or "pla").lower()
    if mat_key not in PRINT_MATERIALS:
        return None, f"Unknown print material '{args.material}'. Choose from: {', '.join(PRINT_MATERIALS.keys())}."

    volume = args.volume  # cm^3
    height = args.height  # mm
    layer_height = args.layer_height if args.layer_height else 0.2  # mm
    infill = args.infill if args.infill else 20  # percent

    if volume is None or volume <= 0:
        return None, "Volume must be a positive number (cm^3)."
    if height is None or height <= 0:
        return None, "Height must be a positive number (mm)."
    if layer_height <= 0 or layer_height > 1.0:
        return None, "Layer height must be between 0.01 and 1.0 mm."
    if infill < 0 or infill > 100:
        return None, "Infill must be between 0 and 100 percent."

    mat = PRINT_MATERIALS[mat_key]
    hourly_rate = args.hourly_rate if args.hourly_rate else DEFAULT_HOURLY_RATE

    # Number of layers
    num_layers = math.ceil(height / layer_height)

    # Effective volume considering infill
    # Shells are solid, interior uses infill percentage
    # Approximate: 30% of volume is shell, rest is infill
    shell_fraction = 0.30
    effective_volume = volume * (shell_fraction + (1 - shell_fraction) * (infill / 100))

    # Volumetric flow rate: nozzle_area * print_speed
    nozzle_area = DEFAULT_NOZZLE_DIAMETER * layer_height  # mm^2 (width * height)
    flow_rate = nozzle_area * mat["print_speed"]  # mm^3/s
    flow_rate_cm3_per_s = flow_rate / 1000  # cm^3/s

    # Print time
    extrusion_time_s = effective_volume / flow_rate_cm3_per_s
    layer_overhead_s = num_layers * PRINT_LAYER_OVERHEAD
    total_time_s = extrusion_time_s + layer_overhead_s
    total_time_min = total_time_s / 60
    total_time_hr = total_time_min / 60

    # Material weight and cost
    mass_g = effective_volume * mat["density"]
    mass_kg = mass_g / 1000
    material_cost = mass_kg * mat["cost_per_kg"]

    # Machine/labor cost
    machine_cost = total_time_hr * hourly_rate

    # For 3D printing, machine cost is often lower since it's unattended
    # Apply an unattended factor
    unattended_factor = 0.15  # only 15% of hourly rate for unattended operation
    adjusted_machine_cost = total_time_hr * hourly_rate * unattended_factor
    total_cost = adjusted_machine_cost + material_cost

    result = {
        "process": "3D Printing (FDM)",
        "material": mat["name"],
        "volume_cm3": volume,
        "effective_volume_cm3": round(effective_volume, 2),
        "height_mm": height,
        "layer_height_mm": layer_height,
        "num_layers": num_layers,
        "infill_percent": infill,
        "print_speed_mm_per_s": mat["print_speed"],
        "nozzle_temp": mat["nozzle_temp"],
        "bed_temp": mat["bed_temp"],
        "extrusion_time_min": round(extrusion_time_s / 60, 1),
        "layer_overhead_min": round(layer_overhead_s / 60, 1),
        "total_time_min": round(total_time_min, 1),
        "total_time_hr": round(total_time_hr, 2),
        "material_mass_g": round(mass_g, 1),
        "material_cost": round(material_cost, 2),
        "machine_cost": round(adjusted_machine_cost, 2),
        "total_cost": round(total_cost, 2),
    }
    return result, None


def interpolate_speed(speeds, thickness):
    """Interpolate or extrapolate cutting speed for a given thickness."""
    thicknesses = sorted(speeds.keys())

    if thickness in speeds:
        return speeds[thickness]

    # Find bracketing thicknesses
    lower = None
    upper = None
    for t in thicknesses:
        if t <= thickness:
            lower = t
        if t >= thickness and upper is None:
            upper = t

    if lower is None:
        return speeds[thicknesses[0]]
    if upper is None:
        return speeds[thicknesses[-1]]
    if lower == upper:
        return speeds[lower]

    # Linear interpolation
    s_lower = speeds[lower]
    s_upper = speeds[upper]
    frac = (thickness - lower) / (upper - lower)
    return s_lower + (s_upper - s_lower) * frac


def estimate_laser(args):
    """Laser cutting time and cost estimate."""
    mat_key = (args.material or "acrylic").lower()
    if mat_key not in LASER_MATERIALS:
        return None, f"Unknown laser material '{args.material}'. Choose from: {', '.join(LASER_MATERIALS.keys())}."

    cut_length = args.cut_length
    thickness = args.thickness

    if cut_length is None or cut_length <= 0:
        return None, "Cut length must be a positive number (mm)."
    if thickness is None or thickness <= 0:
        return None, "Thickness must be a positive number (mm)."

    mat = LASER_MATERIALS[mat_key]
    hourly_rate = args.hourly_rate if args.hourly_rate else DEFAULT_HOURLY_RATE

    # Get cutting speed
    cut_speed = interpolate_speed(mat["speeds"], thickness)

    # Time
    cutting_time = cut_length / cut_speed  # minutes
    setup_time = LASER_SETUP_TIME
    total_time = cutting_time + setup_time

    # Cost
    machine_cost = (total_time / 60) * hourly_rate

    # Material cost estimate (based on bounding sheet area)
    # Assume cut encloses a roughly square area
    side = math.sqrt(cut_length * 10)  # rough estimate: cut_length / perimeter ratio
    area_m2 = (side * side) / 1e6
    cost_per_m2 = interpolate_speed(mat["cost_per_m2"], thickness)  # reuse interpolation
    material_cost = area_m2 * cost_per_m2
    # Minimum material cost
    material_cost = max(material_cost, 2.0)

    total_cost = machine_cost + material_cost

    result = {
        "process": "Laser Cutting",
        "material": mat["name"],
        "cut_length_mm": cut_length,
        "thickness_mm": thickness,
        "cut_speed_mm_per_min": round(cut_speed, 0),
        "cutting_time_min": round(cutting_time, 2),
        "setup_time_min": setup_time,
        "total_time_min": round(total_time, 2),
        "total_time_hr": round(total_time / 60, 3),
        "hourly_rate": hourly_rate,
        "machine_cost": round(machine_cost, 2),
        "material_cost_est": round(material_cost, 2),
        "total_cost": round(total_cost, 2),
    }
    return result, None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    return f"{val:,.{decimals}f}"


def print_cnc_results(r):
    print("=" * 48)
    print("  FABRICATION CALCULATOR - CNC Milling")
    print("=" * 48)
    print()
    print("  Process Parameters:")
    print(f"    Material         : {r['material']}")
    print(f"    Path Length       : {fmt(r['path_length_mm'])} mm")
    print(f"    Feed Rate        : {fmt(r['feed_rate_mm_per_min'], 0)} mm/min")
    print(f"    Tool Changes     : {r['tool_changes']:>8}")
    print(f"    Change Time      : {fmt(r['tool_change_time_min'])} min each")
    print()
    print("  Time Estimate:")
    print(f"    Cutting Time     : {fmt(r['cutting_time_min'])} min")
    print(f"    Tool Change Time : {fmt(r['tool_change_total_min'])} min")
    print(f"    Setup Time       : {fmt(r['setup_time_min'])} min")
    print(f"    Total Time       : {fmt(r['total_time_min'])} min ({fmt(r['total_time_hr'])} hr)")
    print()
    print("  Cost Estimate:")
    print(f"    Machine Time     : ${fmt(r['machine_cost'])}")
    print(f"    Material (est.)  : ${fmt(r['material_cost_est'])}")
    print(f"    {'-' * 32}")
    print(f"    Total            : ${fmt(r['total_cost'])}")
    print("=" * 48)


def print_3d_print_results(r):
    print("=" * 48)
    print("  FABRICATION CALCULATOR - 3D Printing (FDM)")
    print("=" * 48)
    print()
    print("  Process Parameters:")
    print(f"    Material         : {r['material']}")
    print(f"    Part Volume      : {fmt(r['volume_cm3'])} cm^3")
    print(f"    Effective Volume : {fmt(r['effective_volume_cm3'])} cm^3")
    print(f"    Print Height     : {fmt(r['height_mm'])} mm")
    print(f"    Layer Height     : {fmt(r['layer_height_mm'])} mm")
    print(f"    Layers           : {r['num_layers']:>8}")
    print(f"    Infill           : {r['infill_percent']:>7}%")
    print(f"    Print Speed      : {r['print_speed_mm_per_s']:>5} mm/s")
    print(f"    Nozzle Temp      : {r['nozzle_temp']} C")
    print(f"    Bed Temp         : {r['bed_temp']} C")
    print()
    print("  Time Estimate:")
    print(f"    Extrusion Time   : {fmt(r['extrusion_time_min'], 1)} min")
    print(f"    Layer Overhead   : {fmt(r['layer_overhead_min'], 1)} min")
    print(f"    Total Time       : {fmt(r['total_time_min'], 1)} min ({fmt(r['total_time_hr'])} hr)")
    print()
    print("  Cost Estimate:")
    print(f"    Material ({fmt(r['material_mass_g'], 0)}g) : ${fmt(r['material_cost'])}")
    print(f"    Machine (unattn.): ${fmt(r['machine_cost'])}")
    print(f"    {'-' * 32}")
    print(f"    Total            : ${fmt(r['total_cost'])}")
    print("=" * 48)


def print_laser_results(r):
    print("=" * 48)
    print("  FABRICATION CALCULATOR - Laser Cutting")
    print("=" * 48)
    print()
    print("  Process Parameters:")
    print(f"    Material         : {r['material']}")
    print(f"    Cut Length       : {fmt(r['cut_length_mm'])} mm")
    print(f"    Thickness        : {fmt(r['thickness_mm'])} mm")
    print(f"    Cut Speed        : {fmt(r['cut_speed_mm_per_min'], 0)} mm/min")
    print()
    print("  Time Estimate:")
    print(f"    Cutting Time     : {fmt(r['cutting_time_min'])} min")
    print(f"    Setup Time       : {fmt(r['setup_time_min'])} min")
    print(f"    Total Time       : {fmt(r['total_time_min'])} min ({fmt(r['total_time_hr'], 3)} hr)")
    print()
    print("  Cost Estimate:")
    print(f"    Machine Time     : ${fmt(r['machine_cost'])}")
    print(f"    Material (est.)  : ${fmt(r['material_cost_est'])}")
    print(f"    {'-' * 32}")
    print(f"    Total            : ${fmt(r['total_cost'])}")
    print("=" * 48)


# ---------------------------------------------------------------------------
# Argument parsing and main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Fabrication Calculator - CNC, 3D print, and laser cut time/cost estimation"
    )
    parser.add_argument(
        "--process",
        required=True,
        choices=["cnc-milling", "3d-print", "laser-cut"],
        help="Fabrication process",
    )

    # CNC parameters
    parser.add_argument("--path-length", type=float, default=None, help="CNC tool path length (mm)")
    parser.add_argument("--tool-changes", type=int, default=0, help="Number of tool changes")
    parser.add_argument("--feed-rate", type=float, default=None, help="Override feed rate (mm/min)")

    # 3D print parameters
    parser.add_argument("--volume", type=float, default=None, help="Part volume (cm^3)")
    parser.add_argument("--height", type=float, default=None, help="Print height (mm)")
    parser.add_argument("--layer-height", type=float, default=None, help="Layer height (mm, default 0.2)")
    parser.add_argument("--infill", type=float, default=None, help="Infill percentage (default 20)")

    # Laser parameters
    parser.add_argument("--cut-length", type=float, default=None, help="Total cut path length (mm)")
    parser.add_argument("--thickness", type=float, default=None, help="Material thickness (mm)")

    # Common parameters
    parser.add_argument("--material", type=str, default=None, help="Material type (depends on process)")
    parser.add_argument("--hourly-rate", type=float, default=None, help="Machine/labor rate ($/hr, default 75)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    process_map = {
        "cnc-milling": (estimate_cnc, print_cnc_results),
        "3d-print": (estimate_3d_print, print_3d_print_results),
        "laser-cut": (estimate_laser, print_laser_results),
    }

    estimate_fn, print_fn = process_map[args.process]
    result, error = estimate_fn(args)

    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_fn(result)


if __name__ == "__main__":
    main()
