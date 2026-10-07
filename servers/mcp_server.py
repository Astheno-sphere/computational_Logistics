#!/usr/bin/env python3
"""Asthenosphere MCP server: our logistics skills as tools for any MCP client
(Claude Code, Claude Desktop, Hermes Agent, MCP Inspector).

    python servers/mcp_server.py          # stdio transport (what MCP clients launch)

Written for the MCP Python SDK v2 (`from mcp.server import MCPServer`; v1 called it FastMCP).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402
from mcp.server import MCPServer  # noqa: E402

mcp = MCPServer("asthenosphere")


@mcp.tool()
def network_summary(source: str, dem: str | None = None) -> dict:
    """Build the drivable road graph for an OSM file path or a place name (e.g. "Molde, Norway") and
    summarise it: CRS, nodes, edges, length, one-way edges, max grade, connectivity."""
    return core.network_summary(source, dem)


@mcp.tool()
def route(source: str, origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float,
          weight: str = "travel_time", dem: str | None = None) -> dict:
    """Route on the road network. weight: travel_time, length or energy_kwh (least-energy routing with
    regeneration). Returns totals (length_m, travel_time_s, energy_kwh, climb_m), node ids and local
    x,y,z points in metres."""
    return core.route(source, origin_lon, origin_lat, dest_lon, dest_lat, weight, dem)


@mcp.tool()
def solve_vrp(source: str, problem: str, solver: str = "both", seconds: float = 2.0,
              dem: str | None = None) -> list:
    """Vehicle routing with capacities and time windows on road-network costs. problem is JSON in the
    vrp-solve format (depot, clients, vehicles, objective). solver: pyvrp, ortools or both (cross-check).
    Each plan lists routes, stops with arrival times, loads, violations and local x,y,z points."""
    return core.solve_vrp(source, problem, solver, seconds, dem)


@mcp.tool()
def solve_model(model: str, data: str, solver: str = "auto") -> dict:
    """Solve an AMPL-style optimisation model: transportation, facility_location, min_cost_flow or
    cvrp_exact, with data as JSON. solver: auto, all (cross-check), gurobi, cplex or highs."""
    return core.solve_model(model, data, solver)


@mcp.tool()
def diagnose_tree(probe: str) -> dict:
    """Diagnose Grasshopper data-tree problems from a gh_tree_probe.py JSON dump: cross products,
    branch mismatches, nulls, hidden graft/flatten flags, deep paths. Returns findings and a report."""
    return core.diagnose_tree(probe)



@mcp.tool()
def pathways(package: str = "best", n_futures: int = 20, target: float = 0.2) -> dict:
    """CO2 pathways of a policy package across sampled futures (abm-transport ensemble). Returns years,
    a tree {future} -> CO2 relative to 2025 per year, success flags against the 2050 target, and the
    package's robustness. package: best, no_policy or a study package id such as P12."""
    return core.pathways(package, n_futures, target)

if __name__ == "__main__":
    mcp.run()
