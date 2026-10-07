"""Render the 'one sentence -> agent runs it' workflow banner for the README.

Pure matplotlib, monochrome (black on white), large Arial. No MIKE+/license needed.
Output: docs/figs/workflow.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.family": "Arial"})
BLACK = "#000000"

stages = [
    ("Plain-language\ngoal", 'e.g. "resize this\npipe and re-run"'),
    ("Agent", "reads skills,\nplans the steps"),
    ("MCP tools", "inspect, edit, run,\nread, plot"),
    ("Headless\nworkers", "mikeplus +\nmikeio1d  (no GUI)"),
    ("Outputs", "res1d, JSON,\nfigures"),
]

n = len(stages)
step, bw, bh, y = 2.85, 2.50, 1.95, 0.45
fig, ax = plt.subplots(figsize=(14.5, 3.3), dpi=200)
ax.set_xlim(0, (n - 1) * step + bw + 0.3)
ax.set_ylim(0, 3.15)
ax.axis("off")

for i, (title, sub) in enumerate(stages):
    x = i * step + 0.15
    ax.add_patch(FancyBboxPatch((x, y), bw, bh,
                 boxstyle="round,pad=0.02,rounding_size=0.08",
                 linewidth=2.4, edgecolor=BLACK, facecolor="white"))
    cx = x + bw / 2
    ax.text(cx, y + bh - 0.55, title, ha="center", va="center",
            fontsize=17, fontweight="bold", color=BLACK, linespacing=1.05)
    ax.text(cx, y + 0.52, sub, ha="center", va="center",
            fontsize=12.5, color=BLACK, linespacing=1.2)
    if i < n - 1:
        ax.add_patch(FancyArrowPatch((x + bw + 0.03, y + bh / 2),
                     ((i + 1) * step + 0.12, y + bh / 2),
                     arrowstyle="-|>", mutation_scale=22, linewidth=2.4, color=BLACK))

ax.text(((n - 1) * step + bw + 0.3) / 2, 2.92,
        "From one sentence to a finished MIKE+ run, automatically, without the GUI",
        ha="center", va="center", fontsize=15.5, fontweight="bold", color=BLACK)

out = os.path.join("docs", "figs", "workflow.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
fig.savefig(out, dpi=200, bbox_inches="tight")
print("saved", out)
