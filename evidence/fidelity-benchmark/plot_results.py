#!/usr/bin/env python3
"""Figure: zonal vs network mean car travel time per OD cell (y=x line), one panel per town."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
res = json.loads((HERE / "results.json").read_text())
z = np.load(HERE / "per_trip_times.npz")
fig, axs = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
for ax, name, title in zip(axs, ("molde", "kristiansund"), ("Molde", "Kristiansund")):
    tA, tB = z[f"{name}_tA"], z[f"{name}_tB"]
    key = z[f"{name}_zone_o"].astype(np.int64) * 100000 + z[f"{name}_zone_d"]
    cells, inv = np.unique(key, return_inverse=True)
    n = np.bincount(inv)
    mA, mB = np.bincount(inv, weights=tA) / n, np.bincount(inv, weights=tB) / n
    m = n >= res["meta"]["min_cell_trips"]
    ax.scatter(mB[m], mA[m], s=6 + 3 * np.sqrt(n[m]), alpha=0.55, color="#1f5fa8", edgecolor="none")
    lim = max(mA[m].max(), mB[m].max()) * 1.05
    ax.plot([0, lim], [0, lim], color="#333", lw=1, label="y = x")
    k = res["towns"][name]["primary_apriori"]
    ax.set_title(f"{title}: cell MAPE {k['cell_MAPE_pct']:.1f}%, r = {k['cell_pearson_r']:.2f}\n"
                 f"total vehicle-min error {k['total_error_pct']:+.1f}%  (n = {k['n_cells_ge_min']} cells)", fontsize=10)
    ax.set_xlabel("Network engine (B): mean car time per OD cell [min]")
    ax.set_xlim(0, lim); ax.set_ylim(0, lim); ax.set_aspect("equal"); ax.grid(alpha=0.25)
axs[0].set_ylabel("Zonal engine (A): car time per OD cell [min]")
axs[0].legend(loc="upper left", frameon=False)
fig.suptitle("Zonal vs static-network car travel time, 1 km zones, a-priori parameters (free flow, synthetic OD)", fontsize=10.5)
fig.tight_layout()
fig.savefig(HERE / "fidelity_scatter.png", dpi=160)
print("wrote", HERE / "fidelity_scatter.png")
