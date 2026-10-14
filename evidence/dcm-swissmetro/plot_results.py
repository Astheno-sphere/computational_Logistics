"""
Make one figure from results_summary.json (written by estimate_swissmetro.py):
the estimated distribution of the value-of-time coefficient across travellers.

Reading the figure: the time coefficient is Normal(mean=B_TIME, sd=B_TIME_S).
Mostly negative (more travel time = less utility), with a thin tail above zero
that is an artefact of assuming a normal shape (see README).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
res = json.loads((HERE / "results_summary.json").read_text())
p = {r["Name"]: r for r in res["parameters"]}
mu, sd = p["B_TIME"]["Value"], abs(p["B_TIME_S"]["Value"])

x = np.linspace(mu - 4 * sd, mu + 4 * sd, 600)
y = norm.pdf(x, mu, sd)

fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=150)
ax.fill_between(x, y, where=x <= 0, color="#2b6cb0", alpha=0.35, label="negative (expected sign)")
ax.fill_between(x, y, where=x > 0, color="#c53030", alpha=0.55,
                label=f"positive ({res['share_of_population_with_positive_time_coefficient']:.1%} of travellers)")
ax.plot(x, y, color="#1a365d", lw=1.8)
ax.axvline(mu, color="#1a365d", ls="--", lw=1)
ax.axvline(0, color="black", lw=0.8)
ax.annotate(f"mean = {mu:.2f}\n(t = {p['B_TIME']['Robust t-stat.']:.1f})", xy=(mu, y.max()),
            xytext=(mu + 0.3 * sd, y.max() * 0.80), fontsize=9)
ax.set_xlabel("Time coefficient (utility per 100 minutes of travel time)")
ax.set_ylabel("Density across travellers")
ax.set_title("Swissmetro mixed logit: estimated distribution of the time coefficient\n"
             f"N = {res['number_of_observations']}, {res['number_of_draws']} Halton draws, "
             f"final LL = {res['final_log_likelihood']:.1f}, rho-bar-sq = {res['rho_bar_square_null']:.3f}",
             fontsize=9.5)
ax.legend(frameon=False, fontsize=8.5, loc="upper right")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(HERE / "time_coefficient_distribution.png")
print("saved time_coefficient_distribution.png")
