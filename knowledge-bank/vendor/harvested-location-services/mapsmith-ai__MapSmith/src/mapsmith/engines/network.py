"""Routing over a line network, with the ways it silently lies made visible.

Two operations — the cheapest route between two places, and everything reachable
within a budget — over a network the caller supplies as a line layer. Both come
from the discovery benchmark, where six of the twenty-one requests neither
labeller could place were network questions: *"which residential blocks are
further than a 10-minute walk from any primary care clinic using the actual street
network"*, *"the cheapest path to lay underground line from Substation 4 that
avoids steep slopes"*, *"which emergency rooms become completely cut off if the
riverfront arterial roads submerge"*.

**The failure mode this module is built around is not a wrong number, it is a
disconnected graph.** Two street segments whose endpoints are a millimetre apart
are one junction on the ground and two nodes in a naive build, so the route goes
the long way round or is reported as impossible — and nothing raises, because a
graph with a gap in it is a perfectly valid graph. That is why `tolerance` has no
default, why the number of merged endpoints and the number of connected
components are in every manifest, and why snapping an origin four kilometres to
the nearest node is reported rather than absorbed.

No new dependency: the graph and Dijkstra are forty lines here, they are exactly
deterministic, and the alternative was to pull in a package whose tie-breaking
between equal-cost paths we would not control.
"""

from __future__ import annotations

import heapq
import math
from itertools import pairwise
from typing import Any

import geopandas as gpd
from shapely import union_all

from .. import readers, verify
from ..provenance import InputRecord, ProvenanceRecord

#: Endpoint coordinates are rounded to this many decimals before being compared,
#: on top of the caller's tolerance. Purely defensive against float noise in a
#: file that has been through a reprojection: 1e-9 of a metre is not a place.
_COORDINATE_DECIMALS = 9


def _engine_info() -> dict[str, str]:
    """The routing is Dijkstra written here; shapely holds the geometries."""
    import shapely

    from .. import __version__

    return {
        "name": "mapsmith-dijkstra",
        "version": __version__,
        "x-mapsmith:geometry_library": f"shapely {shapely.__version__}",
    }


class _Graph:
    """Nodes from snapped endpoints, edges from lines. Deliberately small.

    Undirected by default because a line layer without a direction field
    describes undirected connectivity, and inventing a direction is worse than
    not having one. `oneway_field` opts into the other reading, and says so in
    the manifest.
    """

    def __init__(self) -> None:
        self.nodes: dict[tuple[float, float], int] = {}
        self.positions: list[tuple[float, float]] = []
        self.adjacency: dict[int, list[tuple[int, float, int]]] = {}
        #: Endpoints that already shared a coordinate: what the data agreed on.
        self.coincident = 0
        #: Endpoints the TOLERANCE pulled together: what the caller's choice did,
        #: and the number that says whether a bridge got welded to the road below.
        self.welded = 0

    def node_at(self, x: float, y: float, tolerance: float) -> int:
        """The node at this position, creating one only if none is within tolerance.

        Linear scan on purpose: a grid index would be faster and would also be a
        second place where "the same junction" is defined. On the networks these
        operations are for — a town's streets, a utility corridor — the scan is
        not what costs.
        """
        key = (round(x, _COORDINATE_DECIMALS), round(y, _COORDINATE_DECIMALS))
        if key in self.nodes:
            # Exactly the same coordinate: a junction the data already agreed on.
            # This used to increment the same counter as a tolerance weld, so a
            # perfectly noded 3x3 lattice reported "15 endpoints merged at
            # tolerance 0.0" — at a tolerance where nothing CAN be welded. The
            # number the module points at as evidence of what the tolerance did
            # was mostly evidence of what it did not do.
            self.coincident += 1
            return self.nodes[key]
        if tolerance > 0:
            for index, (nx, ny) in enumerate(self.positions):
                if math.hypot(nx - x, ny - y) <= tolerance:
                    self.nodes[key] = index
                    self.welded += 1
                    return index
        index = len(self.positions)
        self.positions.append((x, y))
        self.nodes[key] = index
        self.adjacency[index] = []
        return index

    def add_edge(self, a: int, b: int, cost: float, line_index: int, directed: bool):
        self.adjacency.setdefault(a, []).append((b, cost, line_index))
        if not directed:
            self.adjacency.setdefault(b, []).append((a, cost, line_index))

    def components(self) -> int:
        """How many disconnected pieces the network is in.

        One is what a caller almost always expects. More than one, unannounced,
        is the reason a route came back impossible.
        """
        seen: set[int] = set()
        count = 0
        for start in self.adjacency:
            if start in seen:
                continue
            count += 1
            stack = [start]
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                stack.extend(n for n, _, _ in self.adjacency.get(node, []) if n not in seen)
        return count

    def dijkstra(self, source: int, budget: float | None = None):
        """Least cost to every node, with the edge each was reached by.

        Ties are broken by node index so two runs on the same data give the same
        path — a route that changes between runs cannot be put in a manifest.
        """
        best: dict[int, float] = {source: 0.0}
        came_from: dict[int, tuple[int, int]] = {}
        queue: list[tuple[float, int]] = [(0.0, source)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost > best.get(node, math.inf):
                continue
            for neighbour, weight, line_index in sorted(self.adjacency.get(node, [])):
                total = cost + weight
                if budget is not None and total > budget:
                    continue
                if total < best.get(neighbour, math.inf):
                    best[neighbour] = total
                    came_from[neighbour] = (node, line_index)
                    heapq.heappush(queue, (total, neighbour))
        return best, came_from


#: What a one-way column may say. `bool("no")` is True, so a layer using the
#: OSM convention — where "no" means two-way — came out entirely one-way, every
#: reverse route failed, and the error blamed the tolerance and told the caller
#: to widen it, which is the module's other declared trap.
# `True == 1` and `False == 0` in Python, so listing both collapses them; the
# numeric forms are the ones written out, and the booleans match by equality.
_ONEWAY_TRUE = {1, "1", "yes", "true", "t", "y"}
_ONEWAY_FALSE = {0, "0", "no", "false", "f", "n", "", None}


def _oneway(value: Any, index: int, field: str) -> bool:
    if isinstance(value, str):
        value = value.strip().lower()
    if value in _ONEWAY_TRUE:
        return True
    if value in _ONEWAY_FALSE:
        return False
    raise ValueError(
        f"row {index} has {value!r} in the one-way column {field!r}, which is "
        f"neither true nor false here. Accepted: {sorted(str(v) for v in _ONEWAY_TRUE)} "
        f"and {sorted(str(v) for v in _ONEWAY_FALSE if v is not None)}. A value "
        "this does not understand used to read as one-way, which silently made "
        "the whole network directed — including the OSM convention where 'no' "
        "means two-way. If you need reverse-direction one-ways, flip those "
        "geometries first: this reads direction from the line's own order."
    )


def _build(
    lines: gpd.GeoDataFrame,
    tolerance: float,
    cost_field: str | None,
    oneway_field: str | None,
) -> tuple[_Graph, list[float]]:
    graph = _Graph()
    costs: list[float] = []
    # Columns read positionally rather than through `itertuples()` attributes:
    # pandas renames anything that is not an identifier, so a perfectly ordinary
    # `"travel time"` or `"SPEED KPH"` — which is what shapefiles and OSM exports
    # hold — passed the column-exists check above and then died on
    # `AttributeError: 'Pandas' object has no attribute 'travel time'`.
    cost_values = list(lines[cost_field]) if cost_field else None
    oneway_values = list(lines[oneway_field]) if oneway_field else None
    for index, geometry in enumerate(lines.geometry):
        if geometry is None or geometry.is_empty:
            costs.append(math.nan)
            continue
        coords = list(geometry.coords) if geometry.geom_type == "LineString" else None
        if coords is None:
            raise ValueError(
                "the network holds a MultiLineString, which has no single pair of "
                "endpoints to make a junction out of. Run explode_layer first, so "
                "the split is a recorded step rather than a guess made in here."
            )
        start = graph.node_at(coords[0][0], coords[0][1], tolerance)
        end = graph.node_at(coords[-1][0], coords[-1][1], tolerance)
        if cost_field is None:
            cost = geometry.length
        else:
            cost = cost_values[index]
            if cost is None or (isinstance(cost, float) and math.isnan(cost)):
                raise ValueError(
                    f"row {index} has no value in the cost field {cost_field!r}. A "
                    "missing cost is not a free edge: decide what it should be "
                    "rather than having this treat it as zero."
                )
            cost = float(cost)
            if cost < 0:
                raise ValueError(
                    f"row {index} has a negative cost ({cost}) in {cost_field!r}. "
                    "Dijkstra is only correct on non-negative costs, and would "
                    "return a confident wrong answer rather than fail."
                )
        costs.append(cost)
        directed = _oneway(oneway_values[index], index, oneway_field) if oneway_field else False
        graph.add_edge(start, end, cost, index, directed)
    return graph, costs


def _nearest_node(graph: _Graph, x: float, y: float) -> tuple[int, float]:
    best, distance = 0, math.inf
    for index, (nx, ny) in enumerate(graph.positions):
        d = math.hypot(nx - x, ny - y)
        if d < distance:
            best, distance = index, d
    return best, distance


#: Written out, one per position, because a check name assembled from an
#: f-string is invisible to the sweep that polices the vocabulary — which is how
#: this one shipped unexamined in the first place.
_SNAP_CHECKS = {
    "origin": "x-mapsmith:origin_is_close_to_the_network",
    "destination": "x-mapsmith:destination_is_close_to_the_network",
}


def _snap_check(name: str, distance: float, unit: str, tolerance: float) -> verify.Check:
    """How far the position moved to get onto the network.

    Not critical, because snapping is the point — but a clinic that snapped four
    kilometres to the nearest junction produces a service area for somewhere
    else, and the only evidence is this number.

    The absolute floor of 50 is in the CRS's linear unit, so it cannot be applied
    to a network in degrees: 19.8 degrees is about 1,600 km and this check passed
    it, because 19.8 is less than 50. A geographic network reaches here only when
    a `cost_field` was given (length-based costs are refused in degrees), which is
    exactly the case a unit-blind threshold gets wrong. So in degrees the check is
    not evaluated as a threshold at all — it reports the distance and declines to
    judge it, which is honest, rather than passing and implying it is fine. The
    unit is in the detail either way, because a bare number cannot be judged by a
    human reader either.
    """
    degrees = unit.startswith("degree")
    return verify.Check(
        _SNAP_CHECKS[name],
        True if degrees else distance <= max(tolerance * 10, 50.0),
        f"{name} snapped {distance:.6g} {unit} to the nearest junction"
        + (
            " — not judged: this network is in degrees, where a distance threshold "
            "means a different length at every latitude"
            if degrees
            else ""
        ),
        critical=False,
        hint="if that is far, the position is probably not on this network at all",
    )


def _unit(crs: Any) -> str:
    """The CRS's linear unit, as a word. 'degree' when there is not one."""
    try:
        return crs.axis_info[0].unit_name
    except (AttributeError, IndexError):  # pragma: no cover - exotic CRS
        return "unit"


def _network_checks(graph: _Graph, tolerance: float) -> list[verify.Check]:
    components = graph.components()
    return [
        verify.Check(
            "x-mapsmith:network_is_one_connected_piece",
            components == 1,
            f"{components} connected component(s), {len(graph.positions)} junctions",
            critical=False,
            hint="more than one piece means some destinations are unreachable by "
            "construction; a larger tolerance may be joining ends that are meant "
            "to be joined, or the network may genuinely be in pieces",
        ),
    ]


def _common_preamble(
    network_path: str, tolerance: float, cost_field: str | None, oneway_field: str | None
):
    if tolerance < 0:
        raise ValueError(f"tolerance must be zero or positive, got {tolerance}")
    lines = readers.read_vector(network_path)
    if lines.crs is None:
        raise ValueError(
            readers.no_crs_message(
                lines, f"{network_path} has no CRS, so a tolerance in its units and a "
                "cost derived from length both mean nothing."
            )
        )
    if lines.crs.is_geographic and cost_field is None:
        raise ValueError(
            f"{network_path} is in a geographic CRS and no cost_field was given, so "
            "the cost of each edge would be its length in DEGREES — which is not a "
            "distance and varies with latitude. Reproject first, or pass a cost "
            "field whose units you control."
        )
    kinds = set(lines.geom_type.dropna().unique())
    if not kinds <= {"LineString", "MultiLineString"}:
        raise ValueError(
            f"a network is a line layer; {network_path} holds {sorted(kinds)}."
        )
    for field in (cost_field, oneway_field):
        if field is not None and field not in lines.columns:
            raise ValueError(
                f"{network_path} has no column {field!r}. Columns: "
                f"{sorted(c for c in lines.columns if c != lines.geometry.name)}"
            )
    graph, costs = _build(lines, tolerance, cost_field, oneway_field)
    return lines, graph, costs


def network_shortest_path(
    network_path: str,
    output_path: str,
    from_x: float,
    from_y: float,
    to_x: float,
    to_y: float,
    tolerance: float,
    cost_field: str | None = None,
    oneway_field: str | None = None,
) -> dict[str, Any]:
    """The cheapest route between two positions over a line network.

    `tolerance` has no default and it is the parameter that decides whether the
    answer means anything: it is how far apart two line endpoints can be and
    still be the same junction. Too small and the network is silently in pieces,
    so the route detours or comes back impossible; too large and it welds
    together a bridge and the road beneath it. Look at the two checks in the
    manifest — the component count and the merged-endpoint count — before
    believing the number.

    `cost_field` is any non-negative numeric column: minutes, euros, a
    slope-weighted length. Without it the cost is geometric length, which needs
    a projected CRS. The output carries `cumulative_cost` per segment in the
    order the route uses them.
    """
    lines, graph, costs = _common_preamble(
        network_path, tolerance, cost_field, oneway_field
    )
    source, from_distance = _nearest_node(graph, from_x, from_y)
    target, to_distance = _nearest_node(graph, to_x, to_y)
    if source == target:
        raise ValueError(
            "the origin and the destination snap to the same junction, so there is "
            "no route to compute. The previous behaviour was to write an empty "
            "layer with a cost of zero and a clean manifest, which reads as "
            "'these places are adjacent' rather than as 'you asked for a route "
            "between one place and itself'."
        )

    record = ProvenanceRecord(
        operation="network_shortest_path",
        parameters={
            "from": [from_x, from_y],
            "to": [to_x, to_y],
            "tolerance": tolerance,
            # How many endpoints the tolerance welded together. It used to be a
            # `verify.Check` whose predicate was the constant True — a counter
            # wearing a check's name, which cannot fail and inflates the passed
            # count of every network manifest. It is a property of the graph that
            # was built, so it belongs beside the tolerance that built it.
            "coincident_endpoints": graph.coincident,
            "welded_by_tolerance": graph.welded,
            "junctions": len(graph.positions),
            "cost_field": cost_field,
            "oneway_field": oneway_field,
            "cost_unit": "the cost field's own unit"
            if cost_field
            else f"length in {verify.crs_label(lines.crs)} units",
        },
        inputs=[InputRecord.from_path(network_path, crs=verify.crs_label(lines.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(lines.crs),
        "reason": "the network is routed in its own CRS; tolerance and any "
        "length-based cost are read in that CRS's units",
    }

    best, came_from = graph.dijkstra(source)
    if target not in best:
        raise ValueError(
            f"no route: the destination is in a different part of the network from "
            f"the origin. The graph has {graph.components()} connected component(s) "
            f"at tolerance {tolerance} — if the streets really do join, the "
            "tolerance is too small to see it."
        )

    used: list[int] = []
    node = target
    while node != source:
        previous, line_index = came_from[node]
        used.append(line_index)
        node = previous
    used.reverse()

    route = lines.iloc[used].copy().reset_index(drop=True)
    route["step"] = range(1, len(used) + 1)
    route["segment_cost"] = [costs[i] for i in used]
    running = 0.0
    cumulative = []
    for i in used:
        running += costs[i]
        cumulative.append(running)
    route["cumulative_cost"] = cumulative

    pre = verify.verify_loaded_inputs("network_shortest_path", network_path=lines)
    with verify.audit_on_failure(record, output_path, pre):
        if str(output_path).endswith(".parquet"):
            route.to_parquet(output_path)
        else:
            route.to_file(output_path)

    total = best[target]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="network_shortest_path",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(lines.crs),
                expect_count=len(used),
                expect_geometry={"LineString"},
            ),
            # Closed form: the segment costs of the route must add up to the cost
            # Dijkstra reported, or the path reconstruction is not the path that
            # was costed — which produces a plausible route with the wrong total.
            verify.Check(
                "x-mapsmith:segment_costs_add_up_to_the_route_cost",
                math.isclose(cumulative[-1] if cumulative else 0.0, total, rel_tol=1e-9),
                f"segments sum to {cumulative[-1] if cumulative else 0.0}, "
                f"Dijkstra says {total}",
            ),
            _snap_check("origin", from_distance, _unit(lines.crs), tolerance),
            _snap_check("destination", to_distance, _unit(lines.crs), tolerance),
            *_network_checks(graph, tolerance),
        ],
    )
    return {
        "output": str(output_path),
        "total_cost": total,
        "segments": len(used),
        "origin_snap_distance": from_distance,
        "destination_snap_distance": to_distance,
        "junctions": len(graph.positions),
        "components": graph.components(),
        "provenance": str(manifest),
        **extras,
    }


def service_area(
    network_path: str,
    output_path: str,
    from_x: float,
    from_y: float,
    budget: float,
    tolerance: float,
    cost_field: str | None = None,
    oneway_field: str | None = None,
) -> dict[str, Any]:
    """Every stretch of network reachable from a position within a cost budget.

    This is the "ten-minute walk" question, and the reason it is a network
    operation rather than a buffer is the whole point: a circle of 800 m around
    a clinic includes the far side of a river with no bridge, and excludes the
    house 900 m away along a straight road. `buffer_layer` answers a different
    question and answers it confidently.

    The last segment of each branch is **cut where the budget runs out** rather
    than included or dropped whole, so the edge of the area is where the walk
    actually ends. Each output segment carries `cost_at_start` and
    `cost_at_end`; a segment that was cut is marked `partial`.
    """
    if budget <= 0:
        raise ValueError(f"budget must be positive, got {budget}")
    lines, graph, costs = _common_preamble(
        network_path, tolerance, cost_field, oneway_field
    )
    source, snap_distance = _nearest_node(graph, from_x, from_y)

    record = ProvenanceRecord(
        operation="service_area",
        parameters={
            "from": [from_x, from_y],
            "budget": budget,
            "tolerance": tolerance,
            # How many endpoints the tolerance welded together. It used to be a
            # `verify.Check` whose predicate was the constant True — a counter
            # wearing a check's name, which cannot fail and inflates the passed
            # count of every network manifest. It is a property of the graph that
            # was built, so it belongs beside the tolerance that built it.
            "coincident_endpoints": graph.coincident,
            "welded_by_tolerance": graph.welded,
            "junctions": len(graph.positions),
            "cost_field": cost_field,
            "oneway_field": oneway_field,
            "cost_unit": "the cost field's own unit"
            if cost_field
            else f"length in {verify.crs_label(lines.crs)} units",
        },
        inputs=[InputRecord.from_path(network_path, crs=verify.crs_label(lines.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(lines.crs),
        "reason": "reachability is computed in the network's own CRS; the budget is "
        "read in the cost field's unit, or in that CRS's length unit without one",
    }

    reached, _ = graph.dijkstra(source)
    pieces = []
    # Same reason as `_build`: `itertuples()` renames columns that are not
    # identifiers, and this loop has no need of them anyway.
    for index, geometry in enumerate(lines.geometry):
        if geometry is None or geometry.is_empty:
            continue
        coords = list(geometry.coords)
        a = graph.nodes[
            (
                round(coords[0][0], _COORDINATE_DECIMALS),
                round(coords[0][1], _COORDINATE_DECIMALS),
            )
        ]
        b = graph.nodes[
            (
                round(coords[-1][0], _COORDINATE_DECIMALS),
                round(coords[-1][1], _COORDINATE_DECIMALS),
            )
        ]
        cost = costs[index]
        # AN EDGE IS DECIDED ONCE, from both ends at the same time.
        #
        # Walking it from each end independently double-counted the overlap
        # whenever both ends were reachable, which on any network with a cycle is
        # most edges: a triangle with a budget of 4 emitted 8.0 metres of an edge
        # whose union is 6.83. "How many metres of road are within ten minutes"
        # is exactly the number computed from this output, and it was inflated —
        # under a `nothing_exceeds_the_budget` check that passed, because every
        # individual piece did respect the budget.
        from_a = reached.get(a)
        from_b = reached.get(b)
        budget_a = None if from_a is None or from_a > budget else budget - from_a
        budget_b = None if from_b is None or from_b > budget else budget - from_b
        if budget_a is None and budget_b is None:
            continue
        if cost <= 0:
            continue

        forward = budget_a if budget_a is not None else 0.0
        backward = budget_b if budget_b is not None else 0.0
        if forward + backward >= cost - 1e-12:
            # The two reaches meet or overlap: the whole edge is walkable. Once.
            entered_from_a = budget_a is not None and (
                budget_b is None or from_a <= from_b
            )
            at_start = from_a if entered_from_a else from_b
            pieces.append(
                {
                    "line_index": index,
                    "geometry": geometry if entered_from_a else geometry.reverse(),
                    "cost_at_start": at_start,
                    "cost_at_end": min(at_start + cost, budget),
                    "partial": forward < cost and backward < cost,
                }
            )
            continue

        # They do not meet: two disjoint stubs, one from each reachable end,
        # with a gap in the middle that nobody can walk to within the budget.
        if budget_a is not None:
            cut = _substring(geometry, budget_a / cost)
            if cut is not None:
                pieces.append(
                    {
                        "line_index": index,
                        "geometry": cut,
                        "cost_at_start": from_a,
                        "cost_at_end": budget,
                        "partial": True,
                    }
                )
        if budget_b is not None:
            cut = _substring(geometry.reverse(), budget_b / cost)
            if cut is not None:
                pieces.append(
                    {
                        "line_index": index,
                        "geometry": cut,
                        "cost_at_start": from_b,
                        "cost_at_end": budget,
                        "partial": True,
                    }
                )

    out = gpd.GeoDataFrame(
        {
            "line_index": [p["line_index"] for p in pieces],
            "cost_at_start": [p["cost_at_start"] for p in pieces],
            "cost_at_end": [p["cost_at_end"] for p in pieces],
            "partial": [p["partial"] for p in pieces],
        },
        geometry=[p["geometry"] for p in pieces],
        crs=lines.crs,
    )
    pre = verify.verify_loaded_inputs("service_area", network_path=lines)
    with verify.audit_on_failure(record, output_path, pre):
        if str(output_path).endswith(".parquet"):
            out.to_parquet(output_path)
        else:
            out.to_file(output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="service_area",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(lines.crs),
                expect_geometry={"LineString"},
                on_empty="warn",
            ),
            # The check that would have caught the double-counting, and did not
            # exist: every piece respected the budget individually while the
            # total overstated the reach by the length of the overlaps.
            #
            # PER EDGE, not over the whole output. A network legitimately holds
            # geometries that lie on top of each other — a bridge over the road
            # beneath it, a bus lane along a street, a shortcut edge parallel to
            # two others — and comparing the global sum against the global union
            # calls that an error. It did, on the first run: three edges of a
            # test network summed to 400 over 200 metres of ground, all of them
            # correct. What must never happen is one edge emitted twice over
            # itself, which is what walking it from both ends produced.
            verify.Check(
                "x-mapsmith:no_edge_is_emitted_over_itself_twice",
                all(
                    math.isclose(
                        sum(q["geometry"].length for q in group),
                        union_all([q["geometry"] for q in group]).length,
                        rel_tol=1e-9,
                        abs_tol=1e-9,
                    )
                    for group in _by_edge(pieces).values()
                ),
                _overlap_detail(pieces),
            ),
            verify.Check(
                "x-mapsmith:nothing_exceeds_the_budget",
                all(p["cost_at_end"] <= budget + 1e-9 for p in pieces),
                f"{sum(1 for p in pieces if p['cost_at_end'] > budget + 1e-9)} "
                "segment(s) end beyond the budget",
            ),
            _snap_check("origin", snap_distance, _unit(lines.crs), tolerance),
            *_network_checks(graph, tolerance),
        ],
    )
    return {
        "output": str(output_path),
        "segments": len(pieces),
        "partial_segments": sum(1 for p in pieces if p["partial"]),
        "budget": budget,
        "reachable_junctions": sum(1 for cost in reached.values() if cost <= budget),
        "junctions": len(graph.positions),
        "origin_snap_distance": snap_distance,
        "components": graph.components(),
        "provenance": str(manifest),
        **extras,
    }


def _by_edge(pieces: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for piece in pieces:
        grouped.setdefault(piece["line_index"], []).append(piece)
    return grouped


def _overlap_detail(pieces: list[dict[str, Any]]) -> str:
    worst = 0.0
    where = None
    for index, group in _by_edge(pieces).items():
        excess = sum(q["geometry"].length for q in group) - union_all(
            [q["geometry"] for q in group]
        ).length
        if excess > worst:
            worst, where = excess, index
    if where is None:
        return f"{len(pieces)} piece(s), no edge covered twice"
    return f"edge {where} is covered twice over {worst:.6g} of its length"


def _substring(line, fraction: float):
    """The first `fraction` of a line, by length. None if it degenerates."""
    from shapely.geometry import LineString

    if fraction <= 0:
        return None
    if fraction >= 1:
        return line
    target = line.length * fraction
    coords = list(line.coords)
    kept = [coords[0]]
    walked = 0.0
    for previous, current in pairwise(coords):
        step = math.dist(previous, current)
        if walked + step >= target:
            share = (target - walked) / step if step else 0.0
            kept.append(
                (
                    previous[0] + (current[0] - previous[0]) * share,
                    previous[1] + (current[1] - previous[1]) * share,
                )
            )
            break
        walked += step
        kept.append(current)
    return LineString(kept) if len(kept) > 1 else None


#: Above this many cells the search is refused rather than attempted. A grid
#: this size is 32 million edges through a Python heap: it would finish, in
#: tens of minutes, having given no sign that it was going to. Refusing with the
#: number and the remedy is more useful than a progress bar nobody sees.
MAX_COST_CELLS = 4_000_000


def least_cost_path(
    cost_path: str,
    start_path: str,
    end_path: str,
    output_path: str,
    diagonal: bool = True,
) -> dict[str, Any]:
    """The cheapest route across a surface, when there is no network to follow.

    `network_shortest_path` answers this where roads exist. This answers it where
    they do not: a cable trench avoiding steep ground, a haul road, a pipeline
    corridor, a wildlife crossing. The cost raster says what one cell of travel
    is worth — a slope reclassified into a penalty, a habitat score, a price per
    metre — and the route returned is the one whose total is smallest.

    **Cost is per unit of distance, not per cell**, and the difference decides
    the answer. Crossing a cell diagonally is √2 times as far as crossing it
    square-on, so a diagonal step costs √2 times as much; an implementation that
    charges one cell one unit finds staircase routes that a person would never
    walk and that are genuinely cheaper under its own arithmetic. Each step here
    is charged the mean of the two cells it joins, times the distance travelled.

    Nodata is impassable, not free and not expensive: a cell with no cost is a
    cell nothing is known about, and the route goes around it. Zero and negative
    costs are refused — a zero-cost cell makes every route through it free, and
    a negative one makes the shortest path infinitely cheap by going round in
    circles, which is not an error any output would show.

    The result is one line from start to end with the accumulated cost on it,
    plus the cost, the number of steps and the straight-line distance for
    comparison. A route far longer than the straight line is usually right; a
    route exactly as long as the straight line usually means the cost surface is
    uniform and nothing was avoided.
    """
    import heapq

    import numpy as np
    import rasterio
    from shapely.geometry import LineString, Point

    from .. import grid, readers, verify
    from ..provenance import InputRecord, ProvenanceRecord, alignment_decisions

    def one_point(path: str, what: str):
        frame = readers.read_vector(path)
        if frame.crs is None:
            raise ValueError(readers.no_crs_message(frame, f"{path} has no CRS."))
        present = [g for g in frame.geometry if g is not None and not g.is_empty]
        # Every feature is judged, not only the points. A layer holding one
        # point and one line used to pass with the line ignored, and after a
        # reprojection the endpoint was re-read as `iloc[0]` -- which could be
        # the line (found 2026-09-29).
        others = sorted({g.geom_type for g in present} - {"Point", "MultiPoint"})
        if others:
            raise ValueError(
                f"{what} ({path}) holds {others} geometries; it must be a single point. "
                "A route starts somewhere, and a line or a polygon is not one place."
            )
        points = [part for g in present for part in getattr(g, "geoms", [g])]
        if len(points) != 1:
            raise ValueError(
                f"{what} ({path}) must hold exactly one point; it holds "
                f"{len(points)}. Two starts is two questions."
            )
        return frame, points[0]

    starts, start_point = one_point(start_path, "the start")
    ends, end_point = one_point(end_path, "the end")

    with rasterio.open(cost_path) as src:
        if src.crs is None:
            raise ValueError(
                f"{cost_path} has no CRS, so the route could not be placed on the "
                "ground or measured."
            )
        if src.crs.is_geographic:
            raise ValueError(
                "least_cost_path needs a projected CRS: on degrees a diagonal step "
                "is not sqrt(2) cells and the distances that weight the cost are "
                "meaningless. Reproject the cost surface first."
            )
        cells = src.width * src.height
        if cells > MAX_COST_CELLS:
            raise ValueError(
                f"{cost_path} has {cells:,} cells, above the {MAX_COST_CELLS:,} this "
                "search will attempt. Clip the surface to the corridor of interest "
                "or coarsen it (resample_raster) — a least-cost route over a whole "
                "country is almost always the wrong question anyway."
            )
        cost = src.read(1, masked=True)
        crs_label = verify.crs_label(src.crs)
        # The coordinate system itself, kept apart from its label. A label
        # is a string for a manifest and `crs_label` invents one for a CRS
        # with no authority code — "unnamed CRS (sha256:...)" — so feeding
        # it back to GeoPandas raised CRSError on any national or agency
        # grid whose .prj carries no EPSG code. This is the #28 class,
        # named in CLAUDE.md, and this was its last instance in src/.
        surface_crs = src.crs
        transform = src.transform
        pixel_x = abs(transform.a)
        pixel_y = abs(transform.e)
        bounds = src.bounds

        # Named pairs rather than sentences: two endpoints can arrive in two
        # different CRSs, and each then has its own transformation. A cost
        # surface is walked cell by cell, so an endpoint that lands on the
        # wrong cell starts the route in the wrong place.
        moved = [
            (name, frame.crs)
            for frame, name in ((starts, "start_path"), (ends, "end_path"))
            if not verify.same_crs(frame.crs, src.crs)
        ]
        if not verify.same_crs(starts.crs, src.crs):
            # The point itself, reprojected -- not whatever feature comes first.
            start_point = gpd.GeoSeries([start_point], crs=starts.crs).to_crs(src.crs).iloc[0]
        if not verify.same_crs(ends.crs, src.crs):
            end_point = gpd.GeoSeries([end_point], crs=ends.crs).to_crs(src.crs).iloc[0]

        def to_cell(point, name: str) -> tuple[int, int]:
            if not (bounds.left <= point.x <= bounds.right
                    and bounds.bottom <= point.y <= bounds.top):
                raise ValueError(
                    f"the {name} point ({point.x:.6g}, {point.y:.6g}) is outside the "
                    f"cost surface, which covers {tuple(round(v, 6) for v in bounds)}."
                )
            # Through `grid`, the one place that says which cell a position is
            # in. The same answer as `src.index` under either registration
            # (D-096); it used to round to a node on a Point surface and start
            # the route half a cell from where it was asked.
            row, column = grid.sample_index(src, point.x, point.y)
            return int(min(max(row, 0), src.height - 1)), int(
                min(max(column, 0), src.width - 1)
            )

        start_cell = to_cell(start_point, "start")
        end_cell = to_cell(end_point, "end")

    values = np.ma.filled(cost.astype("float64"), np.nan)
    finite = np.isfinite(values)
    if not finite.any():
        raise ValueError(f"{cost_path} has no valid cells: every one is nodata.")
    if (values[finite] <= 0).any():
        smallest = float(values[finite].min())
        raise ValueError(
            f"the cost surface holds values of {smallest:g}. A zero-cost cell makes "
            "every route through it free and a negative one makes the cheapest route "
            "an endless loop — neither shows up as an error in the output. Reclassify "
            "so that the cheapest ground still costs something (reclassify_raster)."
        )
    for cell, name in ((start_cell, "start"), (end_cell, "end")):
        if not finite[cell]:
            raise ValueError(
                f"the {name} point sits on a nodata cell, which is impassable. Move "
                "it onto known ground, or fill the gap."
            )

    height, width = values.shape
    steps = [(-1, 0, pixel_y), (1, 0, pixel_y), (0, -1, pixel_x), (0, 1, pixel_x)]
    if diagonal:
        span = math.hypot(pixel_x, pixel_y)
        steps += [(-1, -1, span), (-1, 1, span), (1, -1, span), (1, 1, span)]

    # Dijkstra with a binary heap, written here for the same reason the network
    # module writes its own: the cost model IS the operation, and a library that
    # charges per cell instead of per distance would be a different answer under
    # the same name.
    best = np.full(values.shape, np.inf)
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    best[start_cell] = 0.0
    queue = [(0.0, start_cell)]
    settled = np.zeros(values.shape, dtype=bool)
    visited = 0
    while queue:
        accumulated, cell = heapq.heappop(queue)
        if settled[cell]:
            continue
        settled[cell] = True
        visited += 1
        if cell == end_cell:
            break
        row, column = cell
        here = values[cell]
        for dr, dc, distance in steps:
            neighbour = (row + dr, column + dc)
            if not (0 <= neighbour[0] < height and 0 <= neighbour[1] < width):
                continue
            if settled[neighbour] or not finite[neighbour]:
                continue
            # Mean of the two cells times the ground distance: the step is half
            # in one cell and half in the other, so charging either end alone
            # makes the route prefer whichever direction it is walked.
            step_cost = (here + values[neighbour]) / 2.0 * distance
            candidate = accumulated + step_cost
            if candidate < best[neighbour]:
                best[neighbour] = candidate
                came_from[neighbour] = cell
                heapq.heappush(queue, (candidate, neighbour))

    if not math.isfinite(best[end_cell]):
        raise ValueError(
            "no route exists between these points: nodata cells separate them "
            f"completely. {int(finite.sum()):,} of {values.size:,} cells are "
            "passable, and the two points are in different pieces."
        )

    path_cells = [end_cell]
    while path_cells[-1] != start_cell:
        path_cells.append(came_from[path_cells[-1]])
    path_cells.reverse()
    with rasterio.open(cost_path) as src:
        # Where each cell's value is: the centre of GDAL's cell, under either
        # registration (D-096).
        coordinates = [grid.sample_xy(src, row, column) for row, column in path_cells]
        # `manifest_decisions` and not `describe`: this one goes into
        # `crs_decisions`, where the neighbouring keys are the specification's.
        registration = grid.manifest_decisions(src)
        cell_width, cell_height = abs(src.transform.a), abs(src.transform.e)
    if len(coordinates) < 2:
        # Both endpoints landed in the same cell, so there is no route to draw:
        # `LineString` on one coordinate raises a GEOSException about the point
        # array, which tells the caller nothing about their data. Two points
        # seven metres apart on a ten-metre cost surface is not a pathological
        # input, and the answer they need is the cell size.
        raise ValueError(
            "both points fall in the same cell of the cost surface "
            f"({cell_width:g} x {cell_height:g} in the surface's own unit), so "
            "there is no path between them to compute — the least-cost route "
            "from a cell to itself is the cell. Use a finer cost surface if the "
            "distance between the points matters at this scale."
        )
    line = LineString(coordinates)

    total_cost = float(best[end_cell])
    straight = float(start_point.distance(end_point))
    out = gpd.GeoDataFrame(
        {
            "total_cost": [round(total_cost, 9)],
            "cells": [len(path_cells)],
            "path_length": [round(float(line.length), 6)],
            "straight_line": [round(straight, 6)],
        },
        geometry=[line],
        crs=surface_crs,
    )

    record = ProvenanceRecord(
        operation="least_cost_path",
        parameters={
            "diagonal": diagonal,
            "cost_model": "mean of the two cells joined, times the ground distance "
            "of the step (so a diagonal costs sqrt(2) times a square step)",
            "nodata": "impassable",
            "cells_settled": visited,
        },
        inputs=[
            InputRecord.from_path(cost_path, crs=crs_label, argument="cost_path"),
            InputRecord.from_path(
                start_path, crs=verify.crs_label(starts.crs), argument="start_path"
            ),
            InputRecord.from_path(end_path, crs=verify.crs_label(ends.crs), argument="end_path"),
        ],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        **alignment_decisions(
            crs_label,
            "the search runs on the cost surface's own grid; the endpoints are "
            "brought to it so that each one lands on the cell it occupies",
            moved,
        ),
        **registration,
    }
    if not diagonal:
        record.notes.append(
            "diagonal steps were disabled, so the route can only move square-on. "
            "That makes it longer and more expensive than the true least-cost route "
            "by up to 41%, and it is the right choice only when the movement really "
            "is grid-bound."
        )

    # The write is INSIDE the net since 2026-09-07, and it moved down here
    # rather than the record moving up: nothing this record holds depends on
    # the write, and nothing between the two positions touches the file. A
    # write that raises after opening the file left the dataset on disk with
    # no manifest beside it -- measured, 516 bytes of a partial dataset.
    with verify.audit_on_failure(record, output_path, []):
        if str(output_path).endswith(".parquet"):
            out.to_parquet(output_path)
        else:
            out.to_file(output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="least_cost_path",
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=crs_label,
                expect_count=1,
                expect_geometry={"LineString"},
                on_empty="fail",
            ),
            # The route has to start where it was told and end where it was
            # told. An off-by-one in the cell-to-coordinate conversion moves
            # both ends half a cell and nothing else looks wrong.
            verify.Check(
                "x-mapsmith:the_route_joins_the_two_points_it_was_given",
                start_point.distance(Point(coordinates[0])) <= math.hypot(pixel_x, pixel_y)
                and end_point.distance(Point(coordinates[-1]))
                <= math.hypot(pixel_x, pixel_y),
                f"ends within one cell of the requested points "
                f"({start_point.distance(Point(coordinates[0])):.6g} and "
                f"{end_point.distance(Point(coordinates[-1])):.6g})",
            ),
            # A route can never be shorter than the straight line between its
            # ends. If it is, the geometry is wrong — not the routing.
            verify.Check(
                "x-mapsmith:the_route_is_at_least_as_long_as_the_straight_line",
                float(line.length) >= straight - 1e-6,
                f"{line.length:.6g} against a straight line of {straight:.6g}",
            ),
            # Uniform cost surfaces are the commonest mistake: somebody feeds in
            # the DEM instead of a reclassified penalty and gets a route that
            # avoids nothing. Not critical — it can be legitimate — but it must
            # be said, because the map looks identical either way.
            verify.Check(
                "x-mapsmith:the_route_actually_avoided_something",
                float(line.length) > straight * 1.001,
                f"the route is {float(line.length) / straight:.4f} times the straight "
                "line",
                critical=False,
                hint="a route that is exactly the straight line means the cost "
                "surface is effectively uniform, so nothing was avoided; check that "
                "it is a penalty surface and not the raw DEM",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "total_cost": round(total_cost, 9),
        "cells": len(path_cells),
        "path_length": round(float(line.length), 6),
        "straight_line": round(straight, 6),
        "detour_ratio": round(float(line.length) / straight, 6) if straight else None,
        "cells_settled": visited,
        "diagonal": diagonal,
        "provenance": str(manifest),
        **extras,
    }
