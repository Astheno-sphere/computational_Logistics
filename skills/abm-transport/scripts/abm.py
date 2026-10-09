#!/usr/bin/env python3
"""Agent-based transport model, 2025-2050, driven by an estimated discrete choice model.

Agents are commuters in a two-town region (synthetic, inspired by Molde-Kristiansund; every number is
illustrative and uncalibrated). Each year:
  1. Fleet: car owners replace their car with probability 1/lifetime and pick EV or ICE with a binary
     logit on the purchase-price gap (closing to parity by an uncertain year), a subsidy lever, the
     yearly running-cost saving (energy and any toll exemption) and a peer effect (EV share among
     owners in the agent's zone).
  2. Mode choice: each agent chooses own car, bus or bike with the MNL utilities from dcm-estimate
     (time, cost, wait; ASCs). Choices use sample enumeration (the agent's choice probabilities).
  3. Congestion: car times follow a BPR curve on each zone's road capacity; car demand and times are
     found by the method of successive averages (MSA).
Outcomes: yearly mode shares, EV fleet share, car km, CO2, consumer surplus (logsum / -b_cost), and the public
money that moves per commuter (EV subsidies paid, tolls collected; thousand NOK). Mode constants are calibrated so
the 2025 shares match TARGET_SHARES_2025; levers phase in from 2026 to full strength in 2030.

    from abm import run
    out = run(levers={"toll_nok": 30}, uncertainties={"ev_parity_year": 2030}, seed=1)
"""
import numpy as np

YEARS = np.arange(2025, 2051)
BETA_DEFAULT = {"ASC_ev": -0.8, "ASC_bus": 0.6, "ASC_bike": -0.4,   # dcm-estimate's illustrative truth
                "B_TIME": -0.06, "B_COST": -0.025, "B_WAIT": -0.09}

LEVERS = {                  # name: (low, high, default = no policy)
    "toll_nok": (0.0, 60.0, 0.0),           # per car trip
    "ev_toll_share": (0.0, 1.0, 1.0),       # share of the toll EVs pay (1 = no exemption)
    "transit_freq_gain": (0.0, 1.0, 0.0),   # 1 = bus headways halved
    "bike_infra": (0.0, 1.0, 0.0),          # 1 = full network of safe, fast bike routes
    "ev_subsidy_knok": (0.0, 100.0, 0.0),   # purchase subsidy, thousand NOK
}
UNCERTAINTIES = {
    "ev_parity_year": (2026.0, 2040.0, 2032.0),   # EV purchase price reaches ICE
    "fuel_price_growth": (-0.02, 0.04, 0.01),     # per year, real
    "telework_2050": (0.0, 0.3, 0.1),             # share of commute days replaced by telework by 2050
    "pop_growth": (0.0, 0.015, 0.005),            # per year
    "peer_effect": (0.0, 3.0, 1.0),               # utility per unit zone EV share
    "vehicle_lifetime": (10.0, 18.0, 13.0),       # years
    "cost_sens_scale": (0.7, 1.3, 1.0),           # transferability of the estimated cost coefficient
    "time_sens_scale": (0.7, 1.3, 1.0),           # ... and of the time coefficients
    "ice_ef_decline": (0.0, 0.03, 0.01),          # yearly efficiency gain of the ICE fleet
}

ZONES = {  # name: (population share, median commute km, road capacity in car trips per peak, free speed km/h)
    "Molde": (0.55, 7.0, 900.0, 45.0),
    "Kristiansund": (0.35, 6.0, 600.0, 40.0),
    "Between": (0.10, 30.0, 400.0, 70.0),
}
# Base-year (2025) commute mode shares the constants are calibrated to: own car, bus, bike.
# Illustrative placeholders until replaced by Norwegian travel survey (RVU) shares for the region.
TARGET_SHARES_2025 = {"car": 0.68, "bus": 0.10, "bike": 0.22}
POLICY_START, POLICY_FULL = 2026, 2030   # levers phase in linearly between these years
EF_ICE_2025 = 0.12      # kg CO2 per car km (illustrative)
EF_EV = 0.004           # kg CO2 per car km on a low-carbon grid (illustrative)
EF_BUS_PKM = 0.04       # kg CO2 per bus passenger km (illustrative)


def defaults(table):
    return {k: v[2] for k, v in table.items()}


def population(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    names = list(ZONES)
    shares = np.array([ZONES[z][0] for z in names])
    zone = rng.choice(len(names), size=n, p=shares / shares.sum())
    med = np.array([ZONES[z][1] for z in names])[zone]
    dist = np.clip(rng.lognormal(np.log(med), 0.5), 1.0, 80.0)
    income_high = rng.uniform(size=n) < 0.45
    owns_car = rng.uniform(size=n) < np.where(zone == 2, 0.95, 0.78)
    is_ev = owns_car & (rng.uniform(size=n) < 0.30)            # EV share of the fleet in 2025 (illustrative)
    age = rng.integers(0, 15, size=n)
    return {"zone": zone, "dist": dist, "income_high": income_high, "owns_car": owns_car, "is_ev": is_ev,
            "age": age, "zone_names": names}


def ramp(year):
    return min(1.0, max(0.0, (year - POLICY_START + 1) / (POLICY_FULL - POLICY_START + 1)))


def run(levers=None, uncertainties=None, beta=None, n=3000, seed=0, msa_iters=6, calibrate_to=TARGET_SHARES_2025,
        trace_years=(), agent_cs_years=()):
    L = {**defaults(LEVERS), **(levers or {})}
    U = {**defaults(UNCERTAINTIES), **(uncertainties or {})}
    b = dict(beta or BETA_DEFAULT)
    b["B_COST"] *= U["cost_sens_scale"]
    b["B_TIME"] *= U["time_sens_scale"]
    b["B_WAIT"] *= U["time_sens_scale"]
    rng = np.random.default_rng(seed)
    P = population(n, seed)
    zone, dist = P["zone"], P["dist"]
    nz = len(P["zone_names"])
    cap = np.array([ZONES[z][2] for z in P["zone_names"]])
    vfree = np.array([ZONES[z][3] for z in P["zone_names"]])
    cost_scale = np.where(P["income_high"], 0.75, 1.3)          # income heterogeneity in cost sensitivity
    owns, ev, age = P["owns_car"].copy(), P["is_ev"].copy(), P["age"].copy()
    shift = {"car": 0.0, "bus": 0.0, "bike": 0.0}
    calib_iters = 30 if calibrate_to else 0
    series = {k: [] for k in ("car_share", "bus_share", "bike_share", "ev_fleet_share", "car_km", "co2_t", "cs_nok",
                                 "subsidy_knok_pc", "toll_knok_pc")}
    # per-agent trace for maps: a separate random stream, so tracing never changes the results
    trng, trace, agent_cs = np.random.default_rng(seed + 7919), {}, {}
    for t, year in enumerate(YEARS):
        # ---- 1. fleet turnover and EV adoption -------------------------------------------------------
        replace = owns & (rng.uniform(size=n) < 1.0 / U["vehicle_lifetime"])
        age = np.where(replace, 0, age + 1)
        gap_knok = 120.0 * max(0.0, (U["ev_parity_year"] - year) / (U["ev_parity_year"] - 2024.0)) - L["ev_subsidy_knok"]
        zone_ev = np.array([ev[owns & (zone == z)].mean() if (owns & (zone == z)).any() else 0.0 for z in range(nz)])
        # yearly running-cost saving of an EV (energy and toll), thousand NOK; 220 commute days, 2 trips
        fuel_now = 1.6 * (1 + U["fuel_price_growth"]) ** t
        saving_knok = (dist * (fuel_now - 0.5) + ramp(year) * L["toll_nok"] * (1 - L["ev_toll_share"])) * 2 * 220 / 1000.0
        u_ev = (0.5 - 0.03 * gap_knok + 0.08 * saving_knok + U["peer_effect"] * zone_ev[zone]
                - 0.4 * (dist > 40))                                                   # range concern
        p_ev = 1.0 / (1.0 + np.exp(-u_ev))
        ev = np.where(replace, rng.uniform(size=n) < p_ev, ev)
        subsidy_pc = float((replace & ev).sum()) * L["ev_subsidy_knok"] / n        # thousand NOK per commuter
        # ---- 2-3. mode choice with congestion (MSA); constants calibrated in the base year ----------
        r = ramp(year)
        fuel_nok_km = 1.6 * (1 + U["fuel_price_growth"]) ** t
        toll = r * L["toll_nok"]
        car_cost = dist * np.where(ev, 0.5, fuel_nok_km) + toll * np.where(ev, L["ev_toll_share"], 1.0)
        bus_time = dist / 30.0 * 60 + 5
        bus_wait = 7.5 * (1 - 0.5 * r * L["transit_freq_gain"])     # half the headway
        bike_time = dist / (16.0 + 6.0 * r * L["bike_infra"]) * 60
        commute = (1 - U["telework_2050"] * t / (len(YEARS) - 1)) * (1 + U["pop_growth"]) ** t
        for _c in range(calib_iters if t == 0 else 1):
            Pm, Vm, E = _mode_choice(b, shift, ev, owns, zone, dist, cost_scale, car_cost, bus_time, bus_wait,
                                     bike_time, r * L["bike_infra"], commute, vfree, cap, nz, n, msa_iters)
            if t == 0 and calibrate_to:
                sh = Pm.mean(axis=0)
                for j, m in enumerate(("car", "bus", "bike")):
                    shift[m] += np.log(calibrate_to[m] / max(sh[j], 1e-9))
        shares = Pm.mean(axis=0)
        if year in trace_years:   # one realised mode per agent, drawn from its choice probabilities
            u = trng.uniform(size=n)[:, None]
            trace[int(year)] = {"mode": (u > Pm.cumsum(axis=1)).sum(axis=1).clip(0, 2).tolist(),
                                "ev": (ev & owns).tolist()}
        toll_pc = float((Pm[:, 0] * commute * 2 * 220 * toll * np.where(ev, L["ev_toll_share"], 1.0)).sum()) / n / 1000
        car_km = float((Pm[:, 0] * dist * 2 * commute).sum() * 220 * (6000.0 / n))   # 2 trips, 220 days, scaled
        ice_km = float((Pm[:, 0] * dist * 2 * commute * ~ev).sum() * 220 * (6000.0 / n))
        bus_pkm = float((Pm[:, 1] * dist * 2 * commute).sum() * 220 * (6000.0 / n))
        ef_ice = EF_ICE_2025 * (1 - U["ice_ef_decline"]) ** t
        co2 = (ice_km * ef_ice + (car_km - ice_km) * EF_EV + bus_pkm * EF_BUS_PKM) / 1000.0
        ls = (Vm[:, 0] + np.log(E.sum(axis=1)))
        cs_i = ls / (-b["B_COST"] * cost_scale)                   # NOK per agent (logsum / cost coefficient)
        cs = float(cs_i.mean())
        if year in agent_cs_years:
            agent_cs[int(year)] = cs_i.tolist()
        for k, v in zip(series, (shares[0], shares[1], shares[2], ev[owns].mean(), car_km, co2, cs,
                                  subsidy_pc, toll_pc)):
            series[k].append(float(v))
    s = {k: np.array(v) for k, v in series.items()}
    return {
        "years": YEARS.tolist(), "series": {k: v.tolist() for k, v in s.items()},
        "co2_2050_rel": float(s["co2_t"][-1] / s["co2_t"][0]),
        "co2_cum_kt": float(s["co2_t"].sum() / 1000.0),
        "car_share_2050": float(s["car_share"][-1]),
        "ev_fleet_2050": float(s["ev_fleet_share"][-1]),
        "cs_2050_nok": float(s["cs_nok"][-1]),
        "calibration_shift": shift,
        "levers": L, "uncertainties": U,
        **({"agent_cs": agent_cs} if agent_cs_years else {}),
        **({"trace": {"modes": ["car", "bus", "bike"], "zone": [P["zone_names"][z] for z in zone],
                      "dist_km": dist.round(2).tolist(), "years": trace}} if trace_years else {}),
    }


def _mode_choice(b, shift, ev, owns, zone, dist, cost_scale, car_cost, bus_time, bus_wait, bike_time, bike_infra,
                 commute, vfree, cap, nz, n, msa_iters):
    speed = vfree.copy()
    p_car_avg = None
    bike_asc = b["ASC_bike"] + shift["bike"] + 0.8 * bike_infra - 1.5 * (dist > 15)   # long trips rarely biked
    for it in range(msa_iters):
        car_time = dist / speed[zone] * 60 + 3
        V_car = shift["car"] + np.where(ev, b["ASC_ev"], 0.0) + b["B_TIME"] * car_time + b["B_COST"] * cost_scale * car_cost
        V_bus = b["ASC_bus"] + shift["bus"] + b["B_TIME"] * bus_time + b["B_WAIT"] * bus_wait + b["B_COST"] * cost_scale * 40.0
        V_bike = bike_asc + b["B_TIME"] * bike_time
        V = np.column_stack([np.where(owns, V_car, -np.inf), V_bus, V_bike])
        Vm = V.max(axis=1, keepdims=True)
        E = np.exp(V - Vm)
        Pm = E / E.sum(axis=1, keepdims=True)
        p_car_avg = Pm[:, 0] if p_car_avg is None else p_car_avg + (Pm[:, 0] - p_car_avg) / (it + 1)
        demand = np.bincount(zone, weights=p_car_avg * commute, minlength=nz) * (6000.0 / n)
        speed = vfree / (1 + 0.15 * (demand / cap) ** 4)            # BPR
    return Pm, Vm, E


def ema_function(beta=None, **kw):
    """Flat keyword interface for EMA Workbench: every lever and uncertainty is a keyword. `beta` is the
    choice model to use (e.g. estimates from dcm-estimate); default is BETA_DEFAULT."""
    lev = {k: kw[k] for k in LEVERS if k in kw}
    unc = {k: kw[k] for k in UNCERTAINTIES if k in kw}
    r = run(lev, unc, beta=beta, n=int(kw.get("n_agents", 1500)), seed=int(kw.get("seed", 0)))
    return {k: r[k] for k in ("co2_2050_rel", "co2_cum_kt", "car_share_2050", "ev_fleet_2050", "cs_2050_nok")}
