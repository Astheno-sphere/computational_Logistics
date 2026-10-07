#!/usr/bin/env python3
"""
Structural Checker for AEC Computational Design
=================================================
Quick structural sizing and verification for steel members.
Based on simplified Eurocode 3 / ASCE formulas for early-stage feasibility.

Check types:
  - beam:       Bending capacity, shear, and deflection for UDL simply-supported beam
  - column:     Axial capacity with Euler buckling check
  - deflection: Serviceability deflection verification

Usage:
    python structural_checker.py --check beam --span 6000 --load 15 --steel-grade S355
    python structural_checker.py --check column --load 2000 --height 4000 --steel-grade S355
    python structural_checker.py --check deflection --span 8000 --load 10 --section IPE300
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

E_STEEL = 210_000  # MPa (Young's modulus of steel)

STEEL_GRADES = {
    "S235": {"fy": 235, "fu": 360},
    "S275": {"fy": 275, "fu": 430},
    "S355": {"fy": 355, "fu": 510},
    "S460": {"fy": 460, "fu": 550},
}

# IPE section database: h, b, tw, tf, A (mm^2), Ix (mm^4), Iy (mm^4), Sx (mm^3), mass (kg/m)
IPE_SECTIONS = {
    "IPE200": {"h": 200, "b": 100, "tw": 5.6, "tf": 8.5, "A": 2850, "Ix": 19_430_000, "Iy": 1_424_000, "Sx": 194_300, "mass": 22.4},
    "IPE220": {"h": 220, "b": 110, "tw": 5.9, "tf": 9.2, "A": 3340, "Ix": 27_720_000, "Iy": 2_049_000, "Sx": 252_000, "mass": 26.2},
    "IPE240": {"h": 240, "b": 120, "tw": 6.2, "tf": 9.8, "A": 3910, "Ix": 38_920_000, "Iy": 2_836_000, "Sx": 324_300, "mass": 30.7},
    "IPE270": {"h": 270, "b": 135, "tw": 6.6, "tf": 10.2, "A": 4590, "Ix": 57_900_000, "Iy": 4_199_000, "Sx": 429_000, "mass": 36.1},
    "IPE300": {"h": 300, "b": 150, "tw": 7.1, "tf": 10.7, "A": 5380, "Ix": 83_560_000, "Iy": 6_038_000, "Sx": 557_100, "mass": 42.2},
    "IPE330": {"h": 330, "b": 160, "tw": 7.5, "tf": 11.5, "A": 6260, "Ix": 117_700_000, "Iy": 7_881_000, "Sx": 713_100, "mass": 49.1},
    "IPE360": {"h": 360, "b": 170, "tw": 8.0, "tf": 12.7, "A": 7270, "Ix": 162_700_000, "Iy": 10_430_000, "Sx": 904_000, "mass": 57.1},
    "IPE400": {"h": 400, "b": 180, "tw": 8.6, "tf": 13.5, "A": 8450, "Ix": 231_300_000, "Iy": 13_180_000, "Sx": 1_156_000, "mass": 66.3},
    "IPE450": {"h": 450, "b": 190, "tw": 9.4, "tf": 14.6, "A": 9880, "Ix": 337_400_000, "Iy": 16_760_000, "Sx": 1_500_000, "mass": 77.6},
    "IPE500": {"h": 500, "b": 200, "tw": 10.2, "tf": 16.0, "A": 11_550, "Ix": 482_000_000, "Iy": 21_370_000, "Sx": 1_928_000, "mass": 90.7},
    "IPE550": {"h": 550, "b": 210, "tw": 11.1, "tf": 17.2, "A": 13_440, "Ix": 671_200_000, "Iy": 26_670_000, "Sx": 2_441_000, "mass": 105.5},
    "IPE600": {"h": 600, "b": 220, "tw": 12.0, "tf": 19.0, "A": 15_600, "Ix": 920_800_000, "Iy": 33_870_000, "Sx": 3_069_000, "mass": 122.4},
}


def parse_deflection_limit(limit_str):
    """Parse deflection limit string like 'L/250' and return the divisor."""
    limit_str = limit_str.strip().upper()
    if limit_str.startswith("L/"):
        try:
            return float(limit_str[2:])
        except ValueError:
            return 250.0
    try:
        return float(limit_str)
    except ValueError:
        return 250.0


def find_suitable_section(required_sx, required_ix=None):
    """Find the smallest IPE section that meets the required section modulus."""
    sorted_sections = sorted(IPE_SECTIONS.items(), key=lambda x: x[1]["Sx"])
    for name, props in sorted_sections:
        if props["Sx"] >= required_sx:
            if required_ix is not None and props["Ix"] < required_ix:
                continue
            return name, props
    # Return the largest available
    return sorted_sections[-1]


def get_section_by_name(name):
    """Look up a section by name, handling common variations."""
    key = name.upper().replace(" ", "").replace("-", "")
    if key in IPE_SECTIONS:
        return key, IPE_SECTIONS[key]
    # Try with 'IPE' prefix
    if not key.startswith("IPE"):
        key = "IPE" + key
    if key in IPE_SECTIONS:
        return key, IPE_SECTIONS[key]
    return None, None


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def check_beam(args):
    """Simply-supported beam under UDL."""
    span = args.span  # mm
    w = args.load  # kN/m
    grade_name = args.steel_grade.upper()

    if span is None or span <= 0:
        return None, "Span must be a positive number (mm)."
    if w is None or w <= 0:
        return None, "Load (UDL) must be a positive number (kN/m)."
    if grade_name not in STEEL_GRADES:
        return None, f"Unknown steel grade '{grade_name}'. Choose from: {', '.join(STEEL_GRADES.keys())}."

    fy = STEEL_GRADES[grade_name]["fy"]  # MPa
    L = span  # mm
    w_Nmm = w  # kN/m = N/mm (1 kN/m = 1 N/mm)

    # Maximum bending moment: M = wL^2/8 (N*mm)
    M = w_Nmm * L ** 2 / 8  # N*mm
    M_kNm = M / 1e6  # kN*m

    # Required section modulus
    required_Sx = M / fy  # mm^3

    # Maximum shear: V = wL/2
    V = w_Nmm * L / 2  # N
    V_kN = V / 1000

    # Find suitable section
    section_name, section = find_suitable_section(required_Sx)

    # Compute deflection with the selected section
    Ix = section["Ix"]
    delta = (5 * w_Nmm * L ** 4) / (384 * E_STEEL * Ix)  # mm

    # Deflection limit
    limit_div = parse_deflection_limit(args.deflection_limit)
    delta_limit = L / limit_div

    # Utilization ratios
    bending_util = required_Sx / section["Sx"]
    deflection_util = delta / delta_limit

    # Shear check (simplified: V / (A_web * fy/sqrt(3)))
    A_web = section["h"] * section["tw"]
    V_Rd = A_web * fy / math.sqrt(3)  # N
    shear_util = V / V_Rd

    overall_pass = bending_util <= 1.0 and deflection_util <= 1.0 and shear_util <= 1.0

    result = {
        "check_type": "beam",
        "span_mm": L,
        "span_m": L / 1000,
        "udl_kN_per_m": w,
        "steel_grade": grade_name,
        "fy_MPa": fy,
        "max_moment_kNm": round(M_kNm, 2),
        "max_shear_kN": round(V_kN, 2),
        "required_Sx_mm3": round(required_Sx, 0),
        "suggested_section": section_name,
        "section_Sx_mm3": section["Sx"],
        "section_Ix_mm4": Ix,
        "section_mass_kg_per_m": section["mass"],
        "bending_utilization": round(bending_util, 3),
        "shear_utilization": round(shear_util, 3),
        "max_deflection_mm": round(delta, 2),
        "deflection_limit_mm": round(delta_limit, 2),
        "deflection_limit_ratio": f"L/{int(limit_div)}",
        "deflection_utilization": round(deflection_util, 3),
        "overall_status": "PASS" if overall_pass else "FAIL",
    }
    return result, None


def check_column(args):
    """Axial column check with Euler buckling."""
    P = args.load  # kN (axial)
    H = args.height  # mm
    grade_name = args.steel_grade.upper()
    k = args.buckling_length_factor

    if P is None or P <= 0:
        return None, "Axial load must be a positive number (kN)."
    if H is None or H <= 0:
        return None, "Column height must be a positive number (mm)."
    if grade_name not in STEEL_GRADES:
        return None, f"Unknown steel grade '{grade_name}'. Choose from: {', '.join(STEEL_GRADES.keys())}."

    fy = STEEL_GRADES[grade_name]["fy"]
    P_N = P * 1000  # convert to N
    Le = k * H  # effective buckling length in mm

    # Required area from squash load: A_req = P / fy
    A_req = P_N / fy  # mm^2

    # Try each section in ascending order of area
    sorted_sections = sorted(IPE_SECTIONS.items(), key=lambda x: x[1]["A"])

    selected_name = None
    selected_props = None
    Pcr = 0
    slenderness = 0
    buckling_util = 0

    for name, props in sorted_sections:
        A = props["A"]
        if A < A_req:
            continue
        # Check Euler buckling with minimum I
        I_min = min(props["Ix"], props["Iy"])
        Pcr_N = (math.pi ** 2 * E_STEEL * I_min) / Le ** 2
        if Pcr_N >= P_N:
            selected_name = name
            selected_props = props
            Pcr = Pcr_N
            # Slenderness ratio
            r_min = math.sqrt(I_min / A)
            slenderness = Le / r_min
            buckling_util = P_N / Pcr_N
            break

    if selected_name is None:
        # Use the largest section and report failure
        selected_name, selected_props = sorted_sections[-1]
        I_min = min(selected_props["Ix"], selected_props["Iy"])
        Pcr = (math.pi ** 2 * E_STEEL * I_min) / Le ** 2
        r_min = math.sqrt(I_min / selected_props["A"])
        slenderness = Le / r_min
        buckling_util = P_N / Pcr

    squash_util = P_N / (selected_props["A"] * fy)
    overall_pass = squash_util <= 1.0 and buckling_util <= 1.0

    result = {
        "check_type": "column",
        "axial_load_kN": P,
        "height_mm": H,
        "height_m": H / 1000,
        "steel_grade": grade_name,
        "fy_MPa": fy,
        "buckling_length_factor": k,
        "effective_length_mm": Le,
        "required_area_mm2": round(A_req, 0),
        "suggested_section": selected_name,
        "section_area_mm2": selected_props["A"],
        "section_mass_kg_per_m": selected_props["mass"],
        "euler_buckling_load_kN": round(Pcr / 1000, 1),
        "slenderness_ratio": round(slenderness, 1),
        "squash_utilization": round(squash_util, 3),
        "buckling_utilization": round(buckling_util, 3),
        "overall_status": "PASS" if overall_pass else "FAIL",
    }
    return result, None


def check_deflection(args):
    """Deflection check for simply-supported beam under UDL."""
    span = args.span
    w = args.load
    section_name = args.section
    Ix_direct = args.moment_of_inertia

    if span is None or span <= 0:
        return None, "Span must be a positive number (mm)."
    if w is None or w <= 0:
        return None, "Load (UDL) must be a positive number (kN/m)."

    L = span
    w_Nmm = w  # kN/m = N/mm

    # Get Ix from section name or direct input
    if section_name:
        sec_key, sec_props = get_section_by_name(section_name)
        if sec_props is None:
            return None, f"Unknown section '{section_name}'. Available: {', '.join(IPE_SECTIONS.keys())}."
        Ix = sec_props["Ix"]
        section_label = sec_key
        section_mass = sec_props["mass"]
    elif Ix_direct is not None and Ix_direct > 0:
        Ix = Ix_direct
        section_label = f"Custom (Ix = {Ix:,.0f} mm^4)"
        section_mass = None
    else:
        return None, "Provide either --section (e.g. IPE300) or --moment-of-inertia (mm^4)."

    # Deflection: delta = 5wL^4 / (384EI)
    delta = (5 * w_Nmm * L ** 4) / (384 * E_STEEL * Ix)

    # Check against multiple limits
    limit_div = parse_deflection_limit(args.deflection_limit)
    delta_limit = L / limit_div
    utilization = delta / delta_limit

    # Also compute L/200, L/250, L/360 for reference
    limits_ref = {}
    for div in [200, 250, 360]:
        lim = L / div
        limits_ref[f"L/{div}"] = {
            "limit_mm": round(lim, 2),
            "utilization": round(delta / lim, 3),
            "status": "PASS" if delta <= lim else "FAIL",
        }

    # Also compute the max moment for reference
    M_kNm = (w_Nmm * L ** 2 / 8) / 1e6

    overall_pass = utilization <= 1.0

    result = {
        "check_type": "deflection",
        "span_mm": L,
        "span_m": L / 1000,
        "udl_kN_per_m": w,
        "section": section_label,
        "Ix_mm4": Ix,
        "max_moment_kNm": round(M_kNm, 2),
        "max_deflection_mm": round(delta, 2),
        "applied_limit": f"L/{int(limit_div)}",
        "limit_mm": round(delta_limit, 2),
        "utilization": round(utilization, 3),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "reference_limits": limits_ref,
    }
    if section_mass is not None:
        result["section_mass_kg_per_m"] = section_mass

    return result, None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    return f"{val:,.{decimals}f}"


def status_tag(util):
    return "[OK]" if util <= 1.0 else "[FAIL]"


def print_beam_results(r):
    print("=" * 48)
    print("  STRUCTURAL CHECKER - Beam Sizing")
    print("=" * 48)
    print()
    print("  Input:")
    print(f"    Span             : {fmt(r['span_mm'], 0)} mm ({fmt(r['span_m'])} m)")
    print(f"    UDL              : {fmt(r['udl_kN_per_m'])} kN/m")
    print(f"    Steel Grade      : {r['steel_grade']} (fy = {r['fy_MPa']} MPa)")
    print()
    print("  Bending Analysis:")
    print(f"    Max Moment (M)   : {fmt(r['max_moment_kNm'])} kN*m")
    print(f"    Required Sx      : {fmt(r['required_Sx_mm3'], 0)} mm^3")
    print(f"    Suggested Section: {r['suggested_section']} (Sx = {fmt(r['section_Sx_mm3'], 0)} mm^3)")
    print(f"    Bending Util.    : {fmt(r['bending_utilization'], 3)}  {status_tag(r['bending_utilization'])}")
    print()
    print("  Shear Analysis:")
    print(f"    Max Shear (V)    : {fmt(r['max_shear_kN'])} kN")
    print(f"    Shear Util.      : {fmt(r['shear_utilization'], 3)}  {status_tag(r['shear_utilization'])}")
    print()
    print("  Deflection:")
    print(f"    Max Deflection   : {fmt(r['max_deflection_mm'])} mm")
    print(f"    Limit ({r['deflection_limit_ratio']}){' ' * (5 - len(r['deflection_limit_ratio']))} : {fmt(r['deflection_limit_mm'])} mm")
    print(f"    Deflection Util. : {fmt(r['deflection_utilization'], 3)}  {status_tag(r['deflection_utilization'])}")
    print()
    print(f"  Section Mass       : {fmt(r['section_mass_kg_per_m'], 1)} kg/m")
    print(f"  Overall Status     : {r['overall_status']}")
    print("=" * 48)


def print_column_results(r):
    print("=" * 48)
    print("  STRUCTURAL CHECKER - Column Check")
    print("=" * 48)
    print()
    print("  Input:")
    print(f"    Axial Load       : {fmt(r['axial_load_kN'])} kN")
    print(f"    Height           : {fmt(r['height_mm'], 0)} mm ({fmt(r['height_m'])} m)")
    print(f"    Steel Grade      : {r['steel_grade']} (fy = {r['fy_MPa']} MPa)")
    print(f"    Buckling Factor k: {fmt(r['buckling_length_factor'], 2)}")
    print(f"    Effective Length  : {fmt(r['effective_length_mm'], 0)} mm")
    print()
    print("  Sizing:")
    print(f"    Required Area    : {fmt(r['required_area_mm2'], 0)} mm^2")
    print(f"    Suggested Section: {r['suggested_section']} (A = {fmt(r['section_area_mm2'], 0)} mm^2)")
    print()
    print("  Buckling Analysis:")
    print(f"    Euler Load (Pcr) : {fmt(r['euler_buckling_load_kN'], 1)} kN")
    print(f"    Slenderness (Le/r): {fmt(r['slenderness_ratio'], 1)}")
    print(f"    Squash Util.     : {fmt(r['squash_utilization'], 3)}  {status_tag(r['squash_utilization'])}")
    print(f"    Buckling Util.   : {fmt(r['buckling_utilization'], 3)}  {status_tag(r['buckling_utilization'])}")
    print()
    print(f"  Section Mass       : {fmt(r['section_mass_kg_per_m'], 1)} kg/m")
    print(f"  Overall Status     : {r['overall_status']}")
    print("=" * 48)


def print_deflection_results(r):
    print("=" * 48)
    print("  STRUCTURAL CHECKER - Deflection Check")
    print("=" * 48)
    print()
    print("  Input:")
    print(f"    Span             : {fmt(r['span_mm'], 0)} mm ({fmt(r['span_m'])} m)")
    print(f"    UDL              : {fmt(r['udl_kN_per_m'])} kN/m")
    print(f"    Section          : {r['section']}")
    print(f"    Ix               : {fmt(r['Ix_mm4'], 0)} mm^4")
    print()
    print("  Results:")
    print(f"    Max Moment       : {fmt(r['max_moment_kNm'])} kN*m")
    print(f"    Max Deflection   : {fmt(r['max_deflection_mm'])} mm")
    print(f"    Limit ({r['applied_limit']}){' ' * max(0, 5 - len(r['applied_limit']))} : {fmt(r['limit_mm'])} mm")
    print(f"    Utilization      : {fmt(r['utilization'], 3)}  {status_tag(r['utilization'])}")
    print()
    print("  Reference Limits:")
    for name, data in r["reference_limits"].items():
        print(f"    {name:6s}: {fmt(data['limit_mm'])} mm  |  util: {fmt(data['utilization'], 3)}  {data['status']}")
    if "section_mass_kg_per_m" in r:
        print()
        print(f"  Section Mass       : {fmt(r['section_mass_kg_per_m'], 1)} kg/m")
    print()
    print(f"  Overall Status     : {r['overall_status']}")
    print("=" * 48)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Structural Checker - Steel member sizing & verification"
    )
    parser.add_argument(
        "--check",
        required=True,
        choices=["beam", "column", "deflection"],
        help="Check type",
    )
    parser.add_argument("--span", type=float, default=None, help="Beam span or length (mm)")
    parser.add_argument("--load", type=float, default=None, help="UDL (kN/m) for beams, axial load (kN) for columns")
    parser.add_argument("--steel-grade", type=str, default="S355", help="Steel grade: S235, S275, S355, S460")
    parser.add_argument("--height", type=float, default=None, help="Column height (mm)")
    parser.add_argument("--buckling-length-factor", type=float, default=1.0, help="Effective length factor k (default 1.0)")
    parser.add_argument("--moment-of-inertia", type=float, default=None, help="Section Ix (mm^4) for deflection check")
    parser.add_argument("--section", type=str, default=None, help="Named section (e.g. IPE300)")
    parser.add_argument("--deflection-limit", type=str, default="L/250", help="Deflection limit (default L/250)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    check_map = {
        "beam": (check_beam, print_beam_results),
        "column": (check_column, print_column_results),
        "deflection": (check_deflection, print_deflection_results),
    }

    check_fn, print_fn = check_map[args.check]
    result, error = check_fn(args)

    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_fn(result)

    # Exit with code 0 for pass, 0 for fail (data is in output)
    sys.exit(0)


if __name__ == "__main__":
    main()
