#!/usr/bin/env python3
"""
Mesh Analyzer for AEC Computational Design
=============================================
Evaluates mesh quality and topological properties for architectural meshes.
Reads standard OBJ files or accepts inline vertex/face data.

Computes: vertex/face/edge count, Euler characteristic, genus, manifold check,
boundary edges, face area statistics, aspect ratios, normal consistency,
and bounding box.

Usage:
    python mesh_analyzer.py --file model.obj
    python mesh_analyzer.py --vertices "0,0,0;1,0,0;1,1,0;0,1,0" --faces "0,1,2;0,2,3"
    python mesh_analyzer.py --file facade.obj --json
"""

import argparse
import json
import math
import sys


# ---------------------------------------------------------------------------
# Mesh data structures and parsing
# ---------------------------------------------------------------------------

def parse_obj_file(filepath):
    """Parse an OBJ file and return vertices and faces."""
    vertices = []
    faces = []
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0] == "v" and len(parts) >= 4:
                    try:
                        vertices.append((
                            float(parts[1]),
                            float(parts[2]),
                            float(parts[3]),
                        ))
                    except ValueError:
                        continue
                elif parts[0] == "f":
                    face_indices = []
                    for p in parts[1:]:
                        # Handle formats: "1", "1/2", "1/2/3", "1//3"
                        idx = p.split("/")[0]
                        try:
                            face_indices.append(int(idx) - 1)  # OBJ is 1-indexed
                        except ValueError:
                            continue
                    if len(face_indices) >= 3:
                        faces.append(face_indices)
    except FileNotFoundError:
        return None, None, f"File not found: {filepath}"
    except IOError as e:
        return None, None, f"Error reading file: {e}"

    return vertices, faces, None


def parse_inline_vertices(verts_str):
    """Parse semicolon-separated x,y,z vertices."""
    vertices = []
    for part in verts_str.strip().split(";"):
        part = part.strip()
        if not part:
            continue
        coords = part.split(",")
        if len(coords) < 3:
            return None, f"Vertex needs 3 coordinates, got: '{part}'"
        try:
            vertices.append((float(coords[0]), float(coords[1]), float(coords[2])))
        except ValueError:
            return None, f"Non-numeric vertex coordinate: '{part}'"
    return vertices, None


def parse_inline_faces(faces_str):
    """Parse semicolon-separated vertex index lists."""
    faces = []
    for part in faces_str.strip().split(";"):
        part = part.strip()
        if not part:
            continue
        indices = part.split(",")
        try:
            face = [int(i) for i in indices]
        except ValueError:
            return None, f"Non-integer face index: '{part}'"
        if len(face) < 3:
            return None, f"Face needs at least 3 vertices, got: '{part}'"
        faces.append(face)
    return faces, None


# ---------------------------------------------------------------------------
# Vector math helpers
# ---------------------------------------------------------------------------

def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vec_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec_length(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


def vec_normalize(a):
    l = vec_length(a)
    if l < 1e-15:
        return (0, 0, 0)
    return (a[0] / l, a[1] / l, a[2] / l)


# ---------------------------------------------------------------------------
# Mesh analysis functions
# ---------------------------------------------------------------------------

def extract_edges(faces):
    """Extract unique edges and build edge-face adjacency."""
    edge_faces = {}  # (min_idx, max_idx) -> [face_indices]
    for fi, face in enumerate(faces):
        n = len(face)
        for i in range(n):
            v0 = face[i]
            v1 = face[(i + 1) % n]
            edge = (min(v0, v1), max(v0, v1))
            if edge not in edge_faces:
                edge_faces[edge] = []
            edge_faces[edge].append(fi)
    return edge_faces


def compute_face_area(vertices, face):
    """Compute face area. For triangles, uses cross product. For polygons, triangulates from first vertex."""
    if len(face) < 3:
        return 0.0

    total_area = 0.0
    v0 = vertices[face[0]]
    for i in range(1, len(face) - 1):
        v1 = vertices[face[i]]
        v2 = vertices[face[i + 1]]
        ab = vec_sub(v1, v0)
        ac = vec_sub(v2, v0)
        cross = vec_cross(ab, ac)
        total_area += vec_length(cross) / 2.0
    return total_area


def compute_face_normal(vertices, face):
    """Compute face normal using Newell's method for robustness."""
    n = len(face)
    nx, ny, nz = 0.0, 0.0, 0.0
    for i in range(n):
        v_curr = vertices[face[i]]
        v_next = vertices[face[(i + 1) % n]]
        nx += (v_curr[1] - v_next[1]) * (v_curr[2] + v_next[2])
        ny += (v_curr[2] - v_next[2]) * (v_curr[0] + v_next[0])
        nz += (v_curr[0] - v_next[0]) * (v_curr[1] + v_next[1])
    return vec_normalize((nx, ny, nz))


def compute_aspect_ratio(vertices, face):
    """
    Compute aspect ratio of a face (triangle or polygon).
    For triangles: longest edge / (2 * area / longest edge) = longest_edge^2 / (2*area).
    For polygons: approximate using bounding-box ratio.
    """
    if len(face) == 3:
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]
        edges = [
            vec_length(vec_sub(v1, v0)),
            vec_length(vec_sub(v2, v1)),
            vec_length(vec_sub(v0, v2)),
        ]
        longest = max(edges)
        shortest = min(edges)
        area = compute_face_area(vertices, face)
        if area < 1e-15:
            return float('inf')
        # Aspect ratio: longest edge * circumradius / (2 * area)
        # Simplified: longest / shortest is a practical proxy
        if shortest < 1e-15:
            return float('inf')
        # Use the more standard definition: longest_edge / shortest_altitude
        # shortest_altitude = 2 * area / longest_edge
        shortest_alt = 2 * area / longest
        return longest / shortest_alt
    else:
        # For polygons, use edge length range
        n = len(face)
        edge_lengths = []
        for i in range(n):
            e = vec_length(vec_sub(vertices[face[(i + 1) % n]], vertices[face[i]]))
            edge_lengths.append(e)
        longest = max(edge_lengths)
        shortest = min(edge_lengths)
        if shortest < 1e-15:
            return float('inf')
        return longest / shortest


def check_normal_consistency(faces, edge_faces):
    """
    Check if adjacent face normals are consistently oriented.
    Two faces sharing an edge should traverse the edge in opposite directions.
    """
    inconsistent_edges = 0
    total_shared_edges = 0

    for edge, face_indices in edge_faces.items():
        if len(face_indices) != 2:
            continue
        total_shared_edges += 1
        fi_a, fi_b = face_indices[0], face_indices[1]
        face_a = faces[fi_a]
        face_b = faces[fi_b]

        v0, v1 = edge

        # Find direction of edge in face A
        dir_a = None
        for i in range(len(face_a)):
            if face_a[i] == v0 and face_a[(i + 1) % len(face_a)] == v1:
                dir_a = 1
                break
            elif face_a[i] == v1 and face_a[(i + 1) % len(face_a)] == v0:
                dir_a = -1
                break

        # Find direction of edge in face B
        dir_b = None
        for i in range(len(face_b)):
            if face_b[i] == v0 and face_b[(i + 1) % len(face_b)] == v1:
                dir_b = 1
                break
            elif face_b[i] == v1 and face_b[(i + 1) % len(face_b)] == v0:
                dir_b = -1
                break

        if dir_a is not None and dir_b is not None:
            # For consistent orientation, the edge should be traversed in opposite directions
            if dir_a == dir_b:
                inconsistent_edges += 1

    return inconsistent_edges, total_shared_edges


def analyze_mesh(vertices, faces):
    """Full mesh analysis."""
    V = len(vertices)
    F = len(faces)

    # Validate face indices
    max_idx = max(max(f) for f in faces)
    min_idx = min(min(f) for f in faces)
    if min_idx < 0 or max_idx >= V:
        return None, f"Face index out of range. Vertices: 0..{V-1}, but found indices {min_idx}..{max_idx}."

    # Edges
    edge_faces = extract_edges(faces)
    E = len(edge_faces)

    # Euler characteristic
    chi = V - E + F

    # Boundary edges (shared by exactly 1 face)
    boundary_edges = sum(1 for ef in edge_faces.values() if len(ef) == 1)

    # Non-manifold edges (shared by 3+ faces)
    non_manifold_edges = sum(1 for ef in edge_faces.values() if len(ef) > 2)

    # Is manifold?
    is_manifold = non_manifold_edges == 0

    # Genus (for closed orientable surface: chi = 2 - 2g)
    # For surface with boundary: chi = 2 - 2g - b (b = boundary loops)
    # Approximate: assume single boundary loop if boundary edges > 0
    if boundary_edges == 0:
        genus = (2 - chi) // 2
    else:
        # Count boundary loops by following boundary edges
        boundary_loops = count_boundary_loops(edge_faces, faces)
        genus = max(0, (2 - chi - boundary_loops) // 2)

    # Face areas
    face_areas = [compute_face_area(vertices, f) for f in faces]
    total_area = sum(face_areas)
    min_area = min(face_areas) if face_areas else 0
    max_area = max(face_areas) if face_areas else 0
    mean_area = total_area / F if F > 0 else 0
    if F > 1:
        variance = sum((a - mean_area) ** 2 for a in face_areas) / F
        std_area = math.sqrt(variance)
    else:
        std_area = 0

    # Aspect ratios
    aspect_ratios = [compute_aspect_ratio(vertices, f) for f in faces]
    finite_ratios = [r for r in aspect_ratios if r != float('inf')]
    if finite_ratios:
        min_ar = min(finite_ratios)
        max_ar = max(finite_ratios)
        mean_ar = sum(finite_ratios) / len(finite_ratios)
    else:
        min_ar = max_ar = mean_ar = 0
    poor_faces = sum(1 for r in aspect_ratios if r > 3.0)

    # Normal consistency
    inconsistent, total_shared = check_normal_consistency(faces, edge_faces)
    normals_consistent = inconsistent == 0

    # Bounding box
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]

    result = {
        "vertex_count": V,
        "face_count": F,
        "edge_count": E,
        "euler_characteristic": chi,
        "genus": genus,
        "is_manifold": is_manifold,
        "boundary_edges": boundary_edges,
        "non_manifold_edges": non_manifold_edges,
        "face_area_stats": {
            "min": round(min_area, 6),
            "max": round(max_area, 6),
            "mean": round(mean_area, 6),
            "std_dev": round(std_area, 6),
            "total": round(total_area, 6),
        },
        "aspect_ratio_stats": {
            "min": round(min_ar, 4),
            "max": round(max_ar, 4),
            "mean": round(mean_ar, 4),
            "poor_faces_count": poor_faces,
            "poor_faces_percent": round(poor_faces / F * 100, 1) if F > 0 else 0,
        },
        "normal_consistency": {
            "consistent": normals_consistent,
            "inconsistent_edges": inconsistent,
            "total_shared_edges": total_shared,
        },
        "bounding_box": {
            "x_min": round(min(xs), 6),
            "x_max": round(max(xs), 6),
            "x_range": round(max(xs) - min(xs), 6),
            "y_min": round(min(ys), 6),
            "y_max": round(max(ys), 6),
            "y_range": round(max(ys) - min(ys), 6),
            "z_min": round(min(zs), 6),
            "z_max": round(max(zs), 6),
            "z_range": round(max(zs) - min(zs), 6),
        },
    }
    return result, None


def count_boundary_loops(edge_faces, faces):
    """Count the number of boundary loops by tracing boundary edges."""
    # Collect boundary edges as directed edges
    boundary_directed = {}
    for edge, fi_list in edge_faces.items():
        if len(fi_list) == 1:
            fi = fi_list[0]
            face = faces[fi]
            v0, v1 = edge
            # Determine the direction in the face
            for i in range(len(face)):
                a = face[i]
                b = face[(i + 1) % len(face)]
                if (min(a, b), max(a, b)) == edge:
                    # Boundary edge direction: opposite to face direction for outer boundary
                    boundary_directed[b] = a
                    break

    if not boundary_directed:
        return 0

    visited = set()
    loops = 0
    for start in boundary_directed:
        if start in visited:
            continue
        # Trace the loop
        current = start
        while current not in visited:
            visited.add(current)
            current = boundary_directed.get(current)
            if current is None:
                break
        loops += 1

    return loops


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def fmt(val, decimals=3):
    return f"{val:,.{decimals}f}"


def print_results(r):
    print("=" * 48)
    print("  MESH ANALYZER")
    print("=" * 48)
    print()
    print("  Topology:")
    print(f"    Vertices         : {r['vertex_count']:>8}")
    print(f"    Faces            : {r['face_count']:>8}")
    print(f"    Edges            : {r['edge_count']:>8}")
    print(f"    Euler Char. (V-E+F): {r['euler_characteristic']:>5}")
    print(f"    Genus            : {r['genus']:>8}")
    mani = "Yes" if r['is_manifold'] else "No"
    print(f"    Is Manifold      : {mani:>8}")
    print(f"    Boundary Edges   : {r['boundary_edges']:>8}")
    if r['non_manifold_edges'] > 0:
        print(f"    Non-manifold Edges: {r['non_manifold_edges']:>7}")
    print()

    fa = r['face_area_stats']
    print("  Face Area Statistics:")
    print(f"    Min Area         : {fmt(fa['min'])} units^2")
    print(f"    Max Area         : {fmt(fa['max'])} units^2")
    print(f"    Mean Area        : {fmt(fa['mean'])} units^2")
    print(f"    Std Dev          : {fmt(fa['std_dev'])} units^2")
    print(f"    Total Area       : {fmt(fa['total'])} units^2")
    print()

    ar = r['aspect_ratio_stats']
    print("  Aspect Ratio Statistics:")
    print(f"    Min              : {fmt(ar['min'], 4)}")
    print(f"    Max              : {fmt(ar['max'], 4)}")
    print(f"    Mean             : {fmt(ar['mean'], 4)}")
    print(f"    Faces > 3.0      : {ar['poor_faces_count']:>8}  ({ar['poor_faces_percent']:.1f}%)")
    print()

    nc = r['normal_consistency']
    status = "PASS (all normals consistent)" if nc['consistent'] else f"FAIL ({nc['inconsistent_edges']} inconsistent edges)"
    print(f"  Normal Consistency : {status}")
    print()

    bb = r['bounding_box']
    print("  Bounding Box:")
    print(f"    X range          : {fmt(bb['x_min'])} to {fmt(bb['x_max'])} ({fmt(bb['x_range'])})")
    print(f"    Y range          : {fmt(bb['y_min'])} to {fmt(bb['y_max'])} ({fmt(bb['y_range'])})")
    print(f"    Z range          : {fmt(bb['z_min'])} to {fmt(bb['z_max'])} ({fmt(bb['z_range'])})")
    print("=" * 48)


# ---------------------------------------------------------------------------
# Argument parsing and main
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Mesh Analyzer - Mesh quality and topology analysis"
    )
    parser.add_argument("--file", type=str, default=None, help="Path to OBJ file")
    parser.add_argument(
        "--vertices",
        type=str,
        default=None,
        help='Inline vertices: "x,y,z;x,y,z;..."',
    )
    parser.add_argument(
        "--faces",
        type=str,
        default=None,
        help='Inline faces: "i,j,k;i,j,k;..."',
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    vertices = None
    faces = None

    if args.file:
        vertices, faces, err = parse_obj_file(args.file)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            sys.exit(1)
    elif args.vertices and args.faces:
        vertices, err = parse_inline_vertices(args.vertices)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            sys.exit(1)
        faces, err = parse_inline_faces(args.faces)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        print("ERROR: Provide either --file (OBJ path) or both --vertices and --faces.", file=sys.stderr)
        sys.exit(1)

    if not vertices or not faces:
        print("ERROR: No valid mesh data found.", file=sys.stderr)
        sys.exit(1)

    if len(vertices) < 3:
        print("ERROR: Mesh requires at least 3 vertices.", file=sys.stderr)
        sys.exit(1)

    if len(faces) < 1:
        print("ERROR: Mesh requires at least 1 face.", file=sys.stderr)
        sys.exit(1)

    result, err = analyze_mesh(vertices, faces)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_results(result)


if __name__ == "__main__":
    main()
