#!/usr/bin/env python3
"""
Geometry Calculator for AEC Computational Design
=================================================
Computes cross-section properties for common structural shapes:
area, perimeter, centroid, moments of inertia, section moduli,
and radii of gyration.

All inputs in millimeters. All outputs in mm-based units.

Usage:
    python geometry_calculator.py --shape rectangle --width 300 --height 500
    python geometry_calculator.py --shape circle --radius 150
    python geometry_calculator.py --shape i-beam --width 200 --height 400 --flange-thickness 15 --web-thickness 10
    python geometry_calculator.py --shape hollow-rect --width 300 --height 300 --wall-thickness 12 --json
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Shape computation functions
# ---------------------------------------------------------------------------

def compute_rectangle(args):
    """Solid rectangular cross-section."""
    b, h = args.width, args.height
    if b <= 0 or h <= 0:
        return None, "Width and height must be positive."

    area = b * h
    perimeter = 2 * (b + h)
    cx, cy = b / 2, h / 2
    Ix = (b * h ** 3) / 12
    Iy = (h * b ** 3) / 12
    Sx = (b * h ** 2) / 6
    Sy = (h * b ** 2) / 6
    rx = h / math.sqrt(12)
    ry = b / math.sqrt(12)

    return {
        "shape": "Rectangle",
        "dimensions": {"width_mm": b, "height_mm": h},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_circle(args):
    """Solid circular cross-section."""
    r = args.radius
    if r <= 0:
        return None, "Radius must be positive."

    area = math.pi * r ** 2
    perimeter = 2 * math.pi * r
    cx, cy = 0.0, 0.0
    Ix = Iy = (math.pi * r ** 4) / 4
    Sx = Sy = (math.pi * r ** 3) / 4
    rx = ry = r / 2

    return {
        "shape": "Circle",
        "dimensions": {"radius_mm": r},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_triangle(args):
    """Isosceles triangle with base b and height h, base along x-axis."""
    b, h = args.base, args.height
    if b <= 0 or h <= 0:
        return None, "Base and height must be positive."

    area = 0.5 * b * h
    # Sides: two equal legs from base corners to apex at (b/2, h)
    leg = math.sqrt((b / 2) ** 2 + h ** 2)
    perimeter = b + 2 * leg
    cx = b / 2
    cy = h / 3  # centroid at 1/3 height from base

    Ix = (b * h ** 3) / 36
    Iy = (h * b ** 3) / 48
    Sx = (b * h ** 2) / 24
    Sy = (h * b ** 2) / 24  # approximate for symmetric triangle
    rx = math.sqrt(Ix / area)
    ry = math.sqrt(Iy / area)

    return {
        "shape": "Triangle",
        "dimensions": {"base_mm": b, "height_mm": h},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_i_beam(args):
    """Symmetric I-beam (H-section)."""
    b = args.width
    h = args.height
    tf = args.flange_thickness
    tw = args.web_thickness

    if any(v is None or v <= 0 for v in [b, h, tf, tw]):
        return None, "All I-beam dimensions must be positive."
    if 2 * tf >= h:
        return None, "Flange thickness too large: 2*tf must be < height."
    if tw >= b:
        return None, "Web thickness must be less than width."

    hw = h - 2 * tf  # web clear height
    area = 2 * b * tf + hw * tw
    perimeter = 2 * b + 2 * h + 2 * (b - tw)  # outer perimeter approximation
    # More accurate perimeter: top flange outer + inner step + web + inner step + bottom flange
    perimeter = 2 * (b + h) + 2 * (b - tw) + 2 * (2 * tf)  # simplified
    # Exact outer perimeter of I-shape:
    perimeter = 2 * b + 4 * tf + 2 * hw + 2 * (b - tw)

    cx, cy = b / 2, h / 2  # symmetric

    Ix = (b * h ** 3 - (b - tw) * hw ** 3) / 12
    Iy = (2 * tf * b ** 3 + hw * tw ** 3) / 12
    Sx = Ix / (h / 2)
    Sy = Iy / (b / 2)
    rx = math.sqrt(Ix / area)
    ry = math.sqrt(Iy / area)

    return {
        "shape": "I-Beam",
        "dimensions": {
            "width_mm": b,
            "height_mm": h,
            "flange_thickness_mm": tf,
            "web_thickness_mm": tw,
        },
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_hollow_rect(args):
    """Rectangular hollow section (RHS)."""
    b, h = args.width, args.height
    t = args.wall_thickness

    if any(v is None or v <= 0 for v in [b, h, t]):
        return None, "All dimensions must be positive."
    if 2 * t >= min(b, h):
        return None, "Wall thickness too large: 2*t must be < min(width, height)."

    bi, hi = b - 2 * t, h - 2 * t
    area = b * h - bi * hi
    perimeter = 2 * (b + h)  # outer perimeter
    cx, cy = b / 2, h / 2

    Ix = (b * h ** 3 - bi * hi ** 3) / 12
    Iy = (h * b ** 3 - hi * bi ** 3) / 12
    Sx = Ix / (h / 2)
    Sy = Iy / (b / 2)
    rx = math.sqrt(Ix / area)
    ry = math.sqrt(Iy / area)

    return {
        "shape": "Hollow Rectangle",
        "dimensions": {"width_mm": b, "height_mm": h, "wall_thickness_mm": t},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_hollow_circle(args):
    """Circular hollow section (CHS)."""
    R = args.outer_radius
    r = args.inner_radius

    if R is None or r is None or R <= 0 or r <= 0:
        return None, "Both outer and inner radii must be positive."
    if r >= R:
        return None, "Inner radius must be less than outer radius."

    area = math.pi * (R ** 2 - r ** 2)
    perimeter = 2 * math.pi * R  # outer perimeter
    cx, cy = 0.0, 0.0

    Ix = Iy = (math.pi / 4) * (R ** 4 - r ** 4)
    Sx = Sy = Ix / R
    rx = ry = math.sqrt((R ** 2 + r ** 2) / 4)

    return {
        "shape": "Hollow Circle",
        "dimensions": {"outer_radius_mm": R, "inner_radius_mm": r},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [cx, cy],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_l_shape(args):
    """L-shaped angle section (two perpendicular legs)."""
    b = args.width  # horizontal leg length
    h = args.height  # vertical leg length
    t = args.thickness

    if any(v is None or v <= 0 for v in [b, h, t]):
        return None, "All L-shape dimensions must be positive."
    if t >= min(b, h):
        return None, "Thickness must be less than both width and height."

    # Two rectangles: horizontal leg (b x t) and vertical leg (t x (h - t))
    A1 = b * t  # horizontal leg
    A2 = t * (h - t)  # vertical leg (excluding overlap)
    area = A1 + A2

    # Centroids of each rectangle (origin at outer corner, bottom-left)
    cx1, cy1 = b / 2, t / 2
    cx2, cy2 = t / 2, t + (h - t) / 2

    cx = (A1 * cx1 + A2 * cx2) / area
    cy = (A1 * cy1 + A2 * cy2) / area

    # Moments of inertia using parallel axis theorem
    Ix1 = (b * t ** 3) / 12 + A1 * (cy1 - cy) ** 2
    Ix2 = (t * (h - t) ** 3) / 12 + A2 * (cy2 - cy) ** 2
    Ix = Ix1 + Ix2

    Iy1 = (t * b ** 3) / 12 + A1 * (cx1 - cx) ** 2
    Iy2 = ((h - t) * t ** 3) / 12 + A2 * (cx2 - cx) ** 2
    Iy = Iy1 + Iy2

    # Section moduli (distance from centroid to extreme fibre)
    y_top = h - cy
    y_bot = cy
    x_right = b - cx
    x_left = cx
    Sx = Ix / max(y_top, y_bot)
    Sy = Iy / max(x_right, x_left)

    rx = math.sqrt(Ix / area)
    ry = math.sqrt(Iy / area)

    perimeter = 2 * (b + h)  # outer perimeter

    return {
        "shape": "L-Shape",
        "dimensions": {"width_mm": b, "height_mm": h, "thickness_mm": t},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [round(cx, 4), round(cy, 4)],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_t_shape(args):
    """T-shaped section (flange on top)."""
    b = args.width  # flange width
    h = args.height  # total height
    tf = args.flange_thickness
    tw = args.web_thickness

    if any(v is None or v <= 0 for v in [b, h, tf, tw]):
        return None, "All T-shape dimensions must be positive."
    if tf >= h:
        return None, "Flange thickness must be less than total height."
    if tw >= b:
        return None, "Web thickness must be less than flange width."

    hw = h - tf  # web height
    A_flange = b * tf
    A_web = tw * hw
    area = A_flange + A_web

    # Centroid (origin at bottom of web)
    cy_flange = hw + tf / 2
    cy_web = hw / 2
    cy = (A_flange * cy_flange + A_web * cy_web) / area
    cx = b / 2  # symmetric about vertical axis

    # Ix by parallel axis theorem
    Ix_flange = (b * tf ** 3) / 12 + A_flange * (cy_flange - cy) ** 2
    Ix_web = (tw * hw ** 3) / 12 + A_web * (cy_web - cy) ** 2
    Ix = Ix_flange + Ix_web

    # Iy
    Iy_flange = (tf * b ** 3) / 12
    Iy_web = (hw * tw ** 3) / 12
    Iy = Iy_flange + Iy_web

    y_top = h - cy
    y_bot = cy
    Sx = Ix / max(y_top, y_bot)
    Sy = Iy / (b / 2)

    rx = math.sqrt(Ix / area)
    ry = math.sqrt(Iy / area)

    perimeter = 2 * b + 2 * h + 2 * (b - tw)  # outer perimeter

    return {
        "shape": "T-Shape",
        "dimensions": {
            "width_mm": b,
            "height_mm": h,
            "flange_thickness_mm": tf,
            "web_thickness_mm": tw,
        },
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [round(cx, 4), round(cy, 4)],
        "Ix_mm4": Ix,
        "Iy_mm4": Iy,
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


def compute_polygon(args):
    """Arbitrary polygon using the shoelace formula."""
    verts_str = args.vertices
    if not verts_str:
        return None, "Provide --vertices as comma-separated x,y pairs separated by semicolons, e.g. '0,0;100,0;100,200;0,200'."

    try:
        pairs = verts_str.strip().split(";")
        vertices = []
        for p in pairs:
            coords = p.strip().split(",")
            vertices.append((float(coords[0]), float(coords[1])))
    except (ValueError, IndexError):
        return None, "Invalid vertex format. Use 'x1,y1;x2,y2;...' e.g. '0,0;100,0;100,200;0,200'."

    if len(vertices) < 3:
        return None, "Polygon requires at least 3 vertices."

    n = len(vertices)

    # Signed area (shoelace)
    signed_area = 0
    for i in range(n):
        j = (i + 1) % n
        signed_area += vertices[i][0] * vertices[j][1]
        signed_area -= vertices[j][0] * vertices[i][1]
    signed_area /= 2.0
    area = abs(signed_area)

    if area < 1e-12:
        return None, "Polygon has zero or near-zero area. Check vertices."

    # Centroid
    cx = cy = 0
    for i in range(n):
        j = (i + 1) % n
        cross = vertices[i][0] * vertices[j][1] - vertices[j][0] * vertices[i][1]
        cx += (vertices[i][0] + vertices[j][0]) * cross
        cy += (vertices[i][1] + vertices[j][1]) * cross
    cx /= (6 * signed_area)
    cy /= (6 * signed_area)

    # Perimeter
    perimeter = 0
    for i in range(n):
        j = (i + 1) % n
        dx = vertices[j][0] - vertices[i][0]
        dy = vertices[j][1] - vertices[i][1]
        perimeter += math.sqrt(dx ** 2 + dy ** 2)

    # Second moments of area (about centroid)
    Ix_origin = 0
    Iy_origin = 0
    for i in range(n):
        j = (i + 1) % n
        cross = vertices[i][0] * vertices[j][1] - vertices[j][0] * vertices[i][1]
        Ix_origin += (vertices[i][1] ** 2 + vertices[i][1] * vertices[j][1] + vertices[j][1] ** 2) * cross
        Iy_origin += (vertices[i][0] ** 2 + vertices[i][0] * vertices[j][0] + vertices[j][0] ** 2) * cross
    Ix_origin = abs(Ix_origin) / 12
    Iy_origin = abs(Iy_origin) / 12

    # Parallel axis to centroid
    Ix = Ix_origin - area * cy ** 2
    Iy = Iy_origin - area * cx ** 2

    # Bounding box for section modulus
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    y_max_dist = max(abs(max(ys) - cy), abs(cy - min(ys)))
    x_max_dist = max(abs(max(xs) - cx), abs(cx - min(xs)))
    Sx = Ix / y_max_dist if y_max_dist > 0 else 0
    Sy = Iy / x_max_dist if x_max_dist > 0 else 0

    rx = math.sqrt(Ix / area) if Ix > 0 else 0
    ry = math.sqrt(Iy / area) if Iy > 0 else 0

    return {
        "shape": "Polygon",
        "dimensions": {"vertices": vertices, "num_vertices": n},
        "area_mm2": area,
        "perimeter_mm": perimeter,
        "centroid_mm": [round(cx, 4), round(cy, 4)],
        "Ix_mm4": abs(Ix),
        "Iy_mm4": abs(Iy),
        "Sx_mm3": Sx,
        "Sy_mm3": Sy,
        "rx_mm": rx,
        "ry_mm": ry,
    }, None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    """Format a number with thousands separator and fixed decimals."""
    return f"{val:,.{decimals}f}"


def print_results(data):
    """Print human-readable output."""
    dims = data["dimensions"]
    shape_name = data["shape"]

    print("=" * 48)
    print(f"  GEOMETRY CALCULATOR - {shape_name}")
    print("=" * 48)
    print()
    print("  Dimensions:")
    for key, val in dims.items():
        if key == "vertices":
            print(f"    Vertices     : {len(val)} points")
            for i, v in enumerate(val):
                print(f"      V{i}: ({v[0]}, {v[1]})")
        elif key == "num_vertices":
            continue
        else:
            label = key.replace("_mm", "").replace("_", " ").title()
            print(f"    {label:20s}: {fmt(val)} mm")
    print()
    print("  Section Properties:")
    print(f"    Area             : {fmt(data['area_mm2'])} mm^2")
    print(f"    Perimeter        : {fmt(data['perimeter_mm'])} mm")
    c = data["centroid_mm"]
    print(f"    Centroid (x, y)  : ({fmt(c[0])}, {fmt(c[1])}) mm")
    print()
    print("  Second Moment of Area:")
    print(f"    Ix (about x-axis): {fmt(data['Ix_mm4'])} mm^4")
    print(f"    Iy (about y-axis): {fmt(data['Iy_mm4'])} mm^4")
    print()
    print("  Section Modulus:")
    print(f"    Sx               : {fmt(data['Sx_mm3'])} mm^3")
    print(f"    Sy               : {fmt(data['Sy_mm3'])} mm^3")
    print()
    print("  Radius of Gyration:")
    print(f"    rx               : {fmt(data['rx_mm'])} mm")
    print(f"    ry               : {fmt(data['ry_mm'])} mm")
    print("=" * 48)


# ---------------------------------------------------------------------------
# Argument parsing and main
# ---------------------------------------------------------------------------

SHAPES = {
    "rectangle": compute_rectangle,
    "circle": compute_circle,
    "triangle": compute_triangle,
    "i-beam": compute_i_beam,
    "hollow-rect": compute_hollow_rect,
    "hollow-circle": compute_hollow_circle,
    "l-shape": compute_l_shape,
    "t-shape": compute_t_shape,
    "polygon": compute_polygon,
}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Geometry Calculator - Cross-section properties for AEC shapes"
    )
    parser.add_argument(
        "--shape",
        required=True,
        choices=list(SHAPES.keys()),
        help="Shape type",
    )
    parser.add_argument("--width", type=float, default=None, help="Width in mm")
    parser.add_argument("--height", type=float, default=None, help="Height in mm")
    parser.add_argument("--radius", type=float, default=None, help="Radius in mm")
    parser.add_argument("--outer-radius", type=float, default=None, help="Outer radius in mm")
    parser.add_argument("--inner-radius", type=float, default=None, help="Inner radius in mm")
    parser.add_argument("--base", type=float, default=None, help="Base width in mm (triangle)")
    parser.add_argument("--flange-thickness", type=float, default=None, help="Flange thickness in mm")
    parser.add_argument("--web-thickness", type=float, default=None, help="Web thickness in mm")
    parser.add_argument("--wall-thickness", type=float, default=None, help="Wall thickness in mm")
    parser.add_argument("--thickness", type=float, default=None, help="Leg thickness in mm (L-shape)")
    parser.add_argument(
        "--vertices",
        type=str,
        default=None,
        help="Polygon vertices as 'x1,y1;x2,y2;...'",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def validate_required(args):
    """Check that required parameters for the chosen shape are present."""
    shape = args.shape
    required_map = {
        "rectangle": [("width", args.width), ("height", args.height)],
        "circle": [("radius", args.radius)],
        "triangle": [("base", args.base), ("height", args.height)],
        "i-beam": [
            ("width", args.width),
            ("height", args.height),
            ("flange-thickness", args.flange_thickness),
            ("web-thickness", args.web_thickness),
        ],
        "hollow-rect": [
            ("width", args.width),
            ("height", args.height),
            ("wall-thickness", args.wall_thickness),
        ],
        "hollow-circle": [
            ("outer-radius", args.outer_radius),
            ("inner-radius", args.inner_radius),
        ],
        "l-shape": [
            ("width", args.width),
            ("height", args.height),
            ("thickness", args.thickness),
        ],
        "t-shape": [
            ("width", args.width),
            ("height", args.height),
            ("flange-thickness", args.flange_thickness),
            ("web-thickness", args.web_thickness),
        ],
        "polygon": [("vertices", args.vertices)],
    }

    missing = []
    for name, val in required_map.get(shape, []):
        if val is None:
            missing.append(f"--{name}")
    if missing:
        return f"Missing required parameters for {shape}: {', '.join(missing)}"
    return None


def main():
    parser = build_parser()
    args = parser.parse_args()

    err = validate_required(args)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    compute_fn = SHAPES[args.shape]
    result, error = compute_fn(args)

    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # Convert any non-serializable types
        output = {}
        for k, v in result.items():
            if isinstance(v, float):
                output[k] = round(v, 6)
            else:
                output[k] = v
        print(json.dumps(output, indent=2))
    else:
        print_results(result)


if __name__ == "__main__":
    main()
