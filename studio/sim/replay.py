"""Replay a routing solution in time with SimPy and emit contract rows.

The solver decides *which* stops in *which* order; the replay adds *when*: sailing along real leg
geometry at the agent's speed, queueing for a shared berth or helideck, waiting for time windows,
service at each stop. Output is a trajectory DataFrame for `studio.contract.validate`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import simpy

from studio.contract import haversine_m


def _leg(nodes, a, b, legs):
    """Geometry of leg a->b as [(lon, lat), ...]; straight line unless `legs` gives a path."""
    if legs and (a, b) in legs:
        return list(legs[(a, b)])
    if legs and (b, a) in legs:
        return list(reversed(legs[(b, a)]))
    return [nodes[a], nodes[b]]


def replay(nodes, routes, agents, service_s=None, tw=None, legs=None, shared=None, move_state="sail",
           sample_m=500.0, depot=0, demand=None):
    """nodes: [(lon, lat)]; routes: {agent_id: [node, ...]} without the depot (added at both ends);
    agents: DataFrame(agent_id, cls, speed_mps, capacity, ...); service_s: {node: s};
    tw: {node: (early, late)} seconds; legs: {(a, b): [(lon, lat), ...]} sea-lane or flight paths;
    shared: {node: capacity} stops with limited berths/helidecks (agents queue: state 'wait');
    demand: {node: units} unloaded at each stop (load starts at the route total).
    Returns (trajectory DataFrame, events DataFrame)."""
    service_s = service_s or {}
    tw = tw or {}
    demand = demand or {}
    env = simpy.Environment()
    berths = {n: simpy.Resource(env, capacity=c) for n, c in (shared or {}).items()}
    rows, events = [], []
    spec = agents.set_index("agent_id")

    def emit(aid, lon, lat, state, load):
        rows.append((aid, float(env.now), float(lon), float(lat), 0.0, state, float(load)))

    def agent(aid, stops):
        v = float(spec.loc[aid, "speed_mps"])
        load = float(sum(demand.get(s, 0) for s in stops))
        path = [depot] + list(stops) + [depot]
        here = nodes[depot]
        emit(aid, *here, "idle", load)
        for a, b in zip(path, path[1:]):
            pts = _leg(nodes, a, b, legs)
            emit(aid, *pts[0], move_state, load)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                d = float(haversine_m(x0, y0, x1, y1))
                n = max(1, int(np.ceil(d / sample_m)))
                for k in range(1, n + 1):
                    yield env.timeout(d / n / v)
                    f = k / n
                    emit(aid, x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, move_state, load)
            here = nodes[b]
            if b == depot:
                emit(aid, *here, "idle", load)
                continue
            early = tw.get(b, (0, None))[0]
            if env.now < early:
                emit(aid, *here, "wait", load)
                events.append((aid, b, "tw_wait", env.now, early - env.now))
                yield env.timeout(early - env.now)
            if b in berths:
                req = berths[b].request()
                t0 = env.now
                emit(aid, *here, "wait", load)
                yield req
                if env.now > t0:
                    events.append((aid, b, "queue", t0, env.now - t0))
            emit(aid, *here, "unload", load)
            yield env.timeout(float(service_s.get(b, 0)))
            load -= float(demand.get(b, 0))
            late = tw.get(b, (0, None))[1]
            if late is not None and env.now > late:
                events.append((aid, b, "tw_late", env.now, env.now - late))
            if b in berths:
                berths[b].release(req)
            emit(aid, *here, move_state, load)

    for aid, stops in routes.items():
        env.process(agent(aid, stops))
    env.run()
    traj = pd.DataFrame(rows, columns=["agent_id", "t", "lon", "lat", "alt_m", "state", "load"])
    traj = traj.sort_values(["agent_id", "t"], kind="stable").reset_index(drop=True)
    ev = pd.DataFrame(events, columns=["agent_id", "node", "event", "t", "duration_s"])
    return traj, ev
