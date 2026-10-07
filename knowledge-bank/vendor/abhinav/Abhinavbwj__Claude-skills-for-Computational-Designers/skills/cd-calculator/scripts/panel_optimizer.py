#!/usr/bin/env python3
"""
Panel Optimizer for AEC Computational Design
==============================================
Rationalizes facade panel inventories by clustering similar panel dimensions
within a configurable tolerance. Estimates material waste and cost impacts
for design-for-manufacture workflows.

Usage:
    python panel_optimizer.py --panels "1200x800,1200x810,1205x800,1200x800,1190x795,1200x800,2400x800,2400x810"
    python panel_optimizer.py --panels "1200x800,1200x810,1205x800" --tolerance 15 --sheet-width 3000 --sheet-height 2000
    python panel_optimizer.py --panels "1200x800,1200x810" --cost-per-unique 750 --json
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Panel parsing and clustering
# ---------------------------------------------------------------------------

def parse_panels(panels_str):
    """Parse a comma-separated list of WxH panel dimensions."""
    panels = []
    raw = panels_str.strip().split(",")
    for i, p in enumerate(raw):
        p = p.strip()
        if not p:
            continue
        parts = p.lower().split("x")
        if len(parts) != 2:
            return None, f"Invalid panel format at index {i}: '{p}'. Expected WxH (e.g. 1200x800)."
        try:
            w = float(parts[0])
            h = float(parts[1])
        except ValueError:
            return None, f"Non-numeric dimension at index {i}: '{p}'."
        if w <= 0 or h <= 0:
            return None, f"Dimensions must be positive at index {i}: '{p}'."
        panels.append((w, h))
    if len(panels) == 0:
        return None, "No panels provided."
    return panels, None


def cluster_panels(panels, tolerance):
    """
    Cluster panels by similarity within tolerance.
    Uses greedy nearest-centroid clustering.
    Returns list of families: [{"centroid": (w,h), "members": [(w,h),...]}]
    """
    families = []

    for panel in panels:
        placed = False
        for family in families:
            cw, ch = family["centroid"]
            if abs(panel[0] - cw) <= tolerance and abs(panel[1] - ch) <= tolerance:
                family["members"].append(panel)
                # Update centroid as average of all members
                members = family["members"]
                family["centroid"] = (
                    sum(m[0] for m in members) / len(members),
                    sum(m[1] for m in members) / len(members),
                )
                placed = True
                break
        if not placed:
            families.append({
                "centroid": panel,
                "members": [panel],
            })

    return families


def compute_waste(families, sheet_w, sheet_h):
    """
    Estimate material waste for cutting panels from standard sheets.
    Uses a simple greedy strip-packing estimate.
    """
    if sheet_w is None or sheet_h is None:
        return None

    total_panel_area = 0
    total_sheet_area = 0
    sheet_area = sheet_w * sheet_h

    for family in families:
        # Use the rationalized (centroid) dimensions for all members
        pw = round(family["centroid"][0])
        ph = round(family["centroid"][1])
        count = len(family["members"])

        # How many panels fit per sheet?
        # Try both orientations
        fit_a = int(sheet_w // pw) * int(sheet_h // ph)
        fit_b = int(sheet_w // ph) * int(sheet_h // pw)
        panels_per_sheet = max(fit_a, fit_b, 1)

        sheets_needed = math.ceil(count / panels_per_sheet)
        total_panel_area += pw * ph * count
        total_sheet_area += sheet_area * sheets_needed

    if total_sheet_area == 0:
        return None

    waste_fraction = 1.0 - (total_panel_area / total_sheet_area)
    return {
        "total_panel_area_mm2": total_panel_area,
        "total_sheet_area_mm2": total_sheet_area,
        "waste_percent": round(waste_fraction * 100, 1),
        "sheets_required": math.ceil(total_sheet_area / sheet_area),
    }


def compute_cost_impact(raw_unique, rationalized_unique, cost_per_unique):
    """Compute cost impact of panel rationalization."""
    raw_cost = raw_unique * cost_per_unique
    rationalized_cost = rationalized_unique * cost_per_unique
    savings = raw_cost - rationalized_cost

    return {
        "raw_unique_types": raw_unique,
        "rationalized_unique_types": rationalized_unique,
        "cost_per_unique_type": cost_per_unique,
        "raw_uniqueness_cost": raw_cost,
        "rationalized_uniqueness_cost": rationalized_cost,
        "savings": savings,
    }


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def optimize_panels(panels, tolerance, sheet_w, sheet_h, cost_per_unique):
    """Run full panel optimization."""
    total = len(panels)
    raw_unique = len(set(panels))

    families = cluster_panels(panels, tolerance)
    rationalized_unique = len(families)

    # Build family detail
    family_details = []
    for i, fam in enumerate(families):
        centroid = (round(fam["centroid"][0]), round(fam["centroid"][1]))
        members_str = [f"{int(m[0])}x{int(m[1])}" for m in fam["members"]]
        family_details.append({
            "family_id": i + 1,
            "rationalized_size_mm": f"{centroid[0]}x{centroid[1]}",
            "centroid_w": centroid[0],
            "centroid_h": centroid[1],
            "count": len(fam["members"]),
            "member_sizes": members_str,
        })

    # Waste estimation
    waste = compute_waste(families, sheet_w, sheet_h)

    # Cost impact
    cost = compute_cost_impact(raw_unique, rationalized_unique, cost_per_unique)

    reduction = 0 if raw_unique == 0 else round((1 - rationalized_unique / raw_unique) * 100, 1)

    result = {
        "total_panels": total,
        "raw_unique_sizes": raw_unique,
        "tolerance_mm": tolerance,
        "rationalized_unique_sizes": rationalized_unique,
        "reduction_percent": reduction,
        "families": family_details,
        "waste_estimation": waste,
        "cost_impact": cost,
    }
    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    return f"{val:,.{decimals}f}"


def print_results(r):
    print("=" * 52)
    print("  PANEL OPTIMIZER - Clustering")
    print("=" * 52)
    print()
    print("  Input Summary:")
    print(f"    Total Panels     : {r['total_panels']:>5}")
    print(f"    Raw Unique Sizes : {r['raw_unique_sizes']:>5}")
    print(f"    Tolerance        : {r['tolerance_mm']:>5.0f} mm")
    print()
    print("  Panel Families:")
    for fam in r["families"]:
        print(f"    Family {fam['family_id']} ({fam['rationalized_size_mm']} mm):")
        # Show members in groups of 6 per line
        members = fam["member_sizes"]
        line = "      Members: "
        for j, m in enumerate(members):
            if j > 0:
                line += ", "
            if len(line) > 70:
                print(line)
                line = "               "
            line += m
        print(line)
        print(f"      Count: {fam['count']}")
    print()
    print("  Rationalization:")
    print(f"    Unique types (before) : {r['raw_unique_sizes']:>5}")
    print(f"    Unique types (after)  : {r['rationalized_unique_sizes']:>5}")
    print(f"    Reduction             : {r['reduction_percent']:>5.1f}%")
    print()

    if r["waste_estimation"] is not None:
        w = r["waste_estimation"]
        print("  Waste Estimation:")
        print(f"    Total Panel Area : {fmt(w['total_panel_area_mm2'] / 1e6, 3)} m^2")
        print(f"    Total Sheet Area : {fmt(w['total_sheet_area_mm2'] / 1e6, 3)} m^2")
        print(f"    Waste            : {w['waste_percent']:.1f}%")
        print(f"    Sheets Required  : {w['sheets_required']}")
        print()

    c = r["cost_impact"]
    print("  Cost Impact:")
    print(f"    Uniqueness premium    : ${fmt(c['rationalized_uniqueness_cost'], 2)}")
    print(f"    Savings vs. raw       : ${fmt(c['savings'], 2)}")
    print("=" * 52)


# ---------------------------------------------------------------------------
# Argument parsing and main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Panel Optimizer - Facade panel clustering and waste estimation"
    )
    parser.add_argument(
        "--panels",
        type=str,
        required=True,
        help="Comma-separated panel dimensions WxH in mm, e.g. '1200x800,1200x810'",
    )
    parser.add_argument("--tolerance", type=float, default=10, help="Grouping tolerance in mm (default 10)")
    parser.add_argument("--sheet-width", type=float, default=None, help="Raw sheet width in mm")
    parser.add_argument("--sheet-height", type=float, default=None, help="Raw sheet height in mm")
    parser.add_argument("--cost-per-unique", type=float, default=500, help="Cost premium per unique panel type (default 500)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    panels, error = parse_panels(args.panels)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.tolerance < 0:
        print("ERROR: Tolerance must be non-negative.", file=sys.stderr)
        sys.exit(1)

    # Validate sheet dimensions if provided
    if (args.sheet_width is not None) != (args.sheet_height is not None):
        print("ERROR: Provide both --sheet-width and --sheet-height, or neither.", file=sys.stderr)
        sys.exit(1)

    if args.sheet_width is not None and (args.sheet_width <= 0 or args.sheet_height <= 0):
        print("ERROR: Sheet dimensions must be positive.", file=sys.stderr)
        sys.exit(1)

    result = optimize_panels(
        panels,
        args.tolerance,
        args.sheet_width,
        args.sheet_height,
        args.cost_per_unique,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_results(result)


if __name__ == "__main__":
    main()
