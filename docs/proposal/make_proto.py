#!/usr/bin/env python3
"""Prototype ensemble: 904 road-pricing pathways x 1,000 futures, 2026-2050 -> plates/proto.json

A deliberately small version of the thesis model, to show the shape of the result and to exercise
the method end to end. Every parameter below is an assumption with a stated range, to be replaced by
estimates in A1 and A2. Anchors: Kristiansund tariffs (27.20 / 19.04 with tag), 40% electric share of
crossings in 2026 (national), short-run toll elasticities around -0.45 (Odeck and Brathen 2008).

Pathway: up to four instruments in any order; the first applies from 2026, each later one switches on
when the electric share of crossings passes a signpost threshold (50, 65 or 80%), so 904 pathways.
  P  package revision    all tariffs x 1.25
  Z  zero-emission rate  electric discount removed (slows adoption a little)
  D  distance charge     one vehicle-neutral rate, NOK 24
  E  earmarking          revenue to public transport: acceptance up, net revenue down 10%
A pathway meets the 2050 targets in a future if road CO2 falls 85% from 2026, revenue never sits below
debt service for three consecutive years, and acceptance never falls below that future's threshold.

    python docs/proposal/make_proto.py
"""
import itertools
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
YEARS = np.arange(2026, 2051)
NF = 1000
FOSSIL, EV = 27.20, 19.04


def futures(rng):
    k = rng.uniform(0.08, 0.30, NF)                      # adoption speed (40% in 2026, ~5 points a year early on)
    return dict(k=k, t0=2026 + np.log(1.5) / k,          # e(2026) = 0.40
                g=rng.uniform(-0.005, 0.01, NF),         # traffic growth per year
                eps=rng.uniform(-0.55, -0.25, NF),       # price elasticity of crossings
                a0=rng.uniform(0.38, 0.58, NF),          # baseline acceptance
                kap=rng.uniform(0.3, 0.9, NF),           # acceptance lost per unit of price rise
                rho=rng.uniform(0.3, 0.9, NF),           # memory
                lam=rng.uniform(0.30, 0.45, NF),         # acceptance threshold
                noise=rng.normal(0, 0.02, (NF, len(YEARS))))


def run(order, thr, F):
    T = len(YEARS)
    active = {order[0]: np.zeros(NF, int)}               # year index from which each instrument is on
    e = np.zeros((NF, T)); A = np.zeros((NF, T)); rev = np.zeros((NF, T)); co2 = np.zeros((NF, T))
    on_from = {i: np.full(NF, T) for i in "PZDE"}
    on_from[order[0]] = np.zeros(NF, int)
    nxt = np.ones(NF, int)                                # index in order of the next instrument
    k_eff = F["k"].copy()
    share = 0.40 * np.ones(NF)
    a_prev = F["a0"].copy()
    base_price = 0.6 * FOSSIL + 0.4 * EV
    for t in range(T):
        on = {i: on_from[i] <= t for i in "PZDE"}
        k_eff = np.where(on["Z"], F["k"] * 0.85, F["k"])
        share = 1 / (1 + np.exp(-k_eff * (YEARS[t] - (2026 + np.log(1.5) / k_eff))))
        pf = np.where(on["P"], FOSSIL * 1.25, FOSSIL)
        pe = np.where(on["Z"], pf, np.where(on["P"], EV * 1.25, EV))
        pf = np.where(on["D"], 24.0, pf); pe = np.where(on["D"], 24.0, pe)
        price = (1 - share) * pf + share * pe
        idx = price / base_price
        vol = (1 + F["g"]) ** t * idx ** F["eps"]
        r = vol * price * np.where(on["E"], 0.9, 1.0)
        target = F["a0"] - F["kap"] * (idx - 1) + np.where(on["E"], 0.08, 0)
        a = F["rho"] * a_prev + (1 - F["rho"]) * target + F["noise"][:, t]
        e[:, t], A[:, t], rev[:, t], co2[:, t] = share, a, r, vol * (1 - share)
        a_prev = a
        # signposts: switch on the next instrument when the electric share passes the threshold
        for j in range(1, len(order)):
            fire = (nxt == j) & (share >= thr[j - 1]) & (on_from[order[j]] == T)
            on_from[order[j]] = np.where(fire, t + 1, on_from[order[j]])
            nxt = np.where(fire, j + 1, nxt)
    debt = np.full(NF, 0.6 * FOSSIL + 0.4 * EV) / 1.15     # debt service: 2026 revenue of the package as approved, with 15% headroom
    below = rev < debt[:, None]
    run3 = below[:, 2:] & below[:, 1:-1] & below[:, :-2]
    fin_ok = ~run3.any(axis=1)
    co2_ok = co2[:, -1] <= 0.15 * co2[:, 0]
    minA = A.min(axis=1)
    return fin_ok, co2_ok, minA, A, e, rev / debt[:, None]


def main():
    rng = np.random.default_rng(2026)
    F = futures(rng)
    paths = []
    for n in range(1, 5):
        for order in itertools.permutations("PZDE", n):
            for thr in itertools.product((0.5, 0.65, 0.8), repeat=n - 1):
                paths.append((order, thr))
    assert len(paths) == 904, len(paths)
    grid = np.round(np.arange(-0.30, 0.3001, 0.005), 3)
    res = []
    paths.sort(key=lambda p: len(p[0]))
    for order, thr in paths:
        fin, co2, minA, A, e, cover = run(order, thr, F)
        ok = fin & co2 & (minA >= F["lam"])
        s = [(fin & co2 & (minA >= F["lam"] + d)).mean() for d in grid]
        margin = float(max([d for d, v in zip(grid, s) if v >= 0.5], default=-0.30))
        res.append(dict(code="".join(order), thr=list(thr), share=round(float(ok.mean()), 3), margin=round(margin, 3),
                        fin=round(float(fin.mean()), 3), co2=round(float(co2.mean()), 3),
                        acc=round(float((minA >= F["lam"]).mean()), 3)))
    shares = np.array([r["share"] for r in res]); margins = np.array([r["margin"] for r in res])
    # non-dominated front on (margin, share)
    front = [i for i in range(len(res)) if not any((margins[j] >= margins[i]) and (shares[j] >= shares[i]) and
                                                   ((margins[j] > margins[i]) or (shares[j] > shares[i])) for j in range(len(res)))]
    front = sorted(front, key=lambda i: margins[i])
    env = {}
    for i in range(len(res)):                                 # upper envelope: the best pathway at each margin
        m = margins[i]
        if m > -0.3 and (m not in env or shares[i] > shares[env[m]]):
            env[m] = i
    env_pts = [env[m] for m in sorted(env)]
    env_pts = [i for k, i in enumerate(env_pts) if shares[i] >= 0.3]
    fdist = {}
    for i in front:
        fdist.setdefault((margins[i], shares[i]), i)
    pick = list(fdist.values())                               # every distinct non-dominated point
    for q in (0, 0.33, 0.66):
        i = env_pts[int(round(q * (len(env_pts) - 1)))]
        if len(pick) < 5 and i not in pick:
            pick.append(i)
    pick = sorted(pick, key=lambda i: margins[i])
    best = max(pick, key=lambda i: margins[i])          # the widest margin of acceptance on the front
    # trajectories for the chosen pathway and for doing nothing beyond the 2026 package (order "P" with no change? use baseline = no instrument)
    ch = res[best]
    fin, co2, minA, A, e, cover = run(tuple(ch["code"]), tuple(ch["thr"]), F)
    sample = rng.choice(NF, 120, replace=False)
    out = dict(note="prototype; parameters assumed (see make_proto.py), to be estimated in A1 and A2",
               n_paths=len(res), n_futures=NF, years=YEARS.tolist(), paths=res, front=front, pick=pick, best=best,
               robust=int((shares >= 0.6).sum()), near=int(((shares >= 0.4) & (shares < 0.6)).sum()),
               fail=int((shares < 0.4).sum()), envelope=env_pts,
               chosen_A=[[round(float(v), 3) for v in A[i]] for i in sample],
               chosen_lam=[round(float(F["lam"][i]), 3) for i in sample],
               ev_median=[round(float(v), 3) for v in np.median(e, axis=0)],
               acc_median=[round(float(v), 3) for v in np.median(A, axis=0)],
               cover_median=[round(float(v), 3) for v in np.median(cover, axis=0)])
    (HERE / "plates").mkdir(exist_ok=True)
    (HERE / "plates" / "proto.json").write_text(json.dumps(out))
    print("paths", len(res), "robust(>=.6)", out["robust"], "near", out["near"], "fail", out["fail"], "front", len(front))
    for i in pick:
        r = res[i]; print(("*" if i == best else " "), r["code"], r["thr"], "share", r["share"], "margin", r["margin"],
                          "fin", r["fin"], "co2", r["co2"], "acc", r["acc"])
    print("EV median 2026/2035/2050:", out["ev_median"][0], out["ev_median"][9], out["ev_median"][-1],
          "| acceptance median:", out["acc_median"][0], out["acc_median"][9], out["acc_median"][-1])


if __name__ == "__main__":
    main()
