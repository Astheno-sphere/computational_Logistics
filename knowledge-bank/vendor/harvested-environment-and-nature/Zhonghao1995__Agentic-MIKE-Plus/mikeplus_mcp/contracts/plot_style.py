"""Zhonghao's publication plot style — shared by SWMM & MIKE+ (the figures layer).

Verbatim spec from agentic-swmm/skills/swmm-plot:
    Arial 12 . ticks inward . SI units . no title . inverted hyetograph . dpi 300

matplotlib is imported lazily inside the functions so this module stays cheap to
import and free of any engine dependency.
"""
from __future__ import annotations

from pathlib import Path

RCPARAMS = {
    "font.family": "Arial",
    "font.size": 12,
    "axes.titlesize": 12,
    "axes.labelsize": 12,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "xtick.direction": "in",
    "ytick.direction": "in",
}

RAIN_COLOR = "#4C78A8"
FLOW_COLOR = "#F58518"
BASE_COLOR = "#4D4D4D"     # baseline series in a comparison (scenario keeps FLOW_COLOR)
# longitudinal profile
BED_COLOR = "#333333"
CROWN_COLOR = "#8C8C8C"
GROUND_COLOR = "#8B5A2B"
WATER_COLOR = "#4C78A8"


def apply() -> None:
    import matplotlib.pyplot as plt
    plt.rcParams.update(RCPARAMS)


def rain_flow_stacked(flow, out_png, rain=None, flow_label="Discharge",
                      flow_unit="m3/s", rain_unit="mm/h", height_ratios=(1, 2),
                      maxticks=12, dpi=300, figsize=(9, 4.8)):
    """Stacked two-panel hydrograph: rain (top, inverted) over flow (bottom).

    ``flow`` and ``rain`` are pandas Series indexed by datetime; ``rain`` optional.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    apply()
    fig, (ax_rain, ax_flow) = plt.subplots(
        2, 1, sharex=True, figsize=figsize, dpi=dpi,
        gridspec_kw={"height_ratios": list(height_ratios), "hspace": 0.08},
    )

    if rain is not None and len(rain) > 1:
        tnum = mdates.date2num(rain.index.to_pydatetime())
        widths = np.diff(tnum)
        widths = np.append(widths, widths[-1] if len(widths) else 1.0)
        ax_rain.bar(tnum, rain.values, width=widths, align="edge",
                    color=RAIN_COLOR, alpha=0.7, edgecolor="none")
        rmax = float(np.nanmax(rain.values))
        ax_rain.set_ylim(rmax * 1.15 if rmax > 0 else 1.0, 0.0)  # inverted hyetograph
    else:
        ax_rain.set_yticks([])
    ax_rain.set_ylabel(f"Rainfall\n({rain_unit})")
    ax_rain.tick_params(direction="in", which="both", top=True, right=True)

    ax_flow.plot(flow.index, flow.values, color=FLOW_COLOR, linewidth=1.8)
    ax_flow.set_ylabel(f"{flow_label} ({flow_unit})")
    ax_flow.set_xlabel("Time")
    fmax = float(np.nanmax(flow.values)) if len(flow) else 0.0
    if fmax > 0:
        ax_flow.set_ylim(0.0, fmax * 1.15)
    ax_flow.set_xlim(flow.index[0], flow.index[-1])
    loc = mdates.AutoDateLocator(maxticks=maxticks)
    ax_flow.xaxis.set_major_locator(loc)
    ax_flow.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    ax_flow.tick_params(direction="in", which="both", top=True, right=True)

    fig.align_ylabels([ax_rain, ax_flow])
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def timeseries(series, out_png, ylabel, color=FLOW_COLOR, maxticks=12,
               dpi=300, figsize=(9, 3.6)):
    """Single-panel time series in the house style."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    apply()
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.plot(series.index, series.values, color=color, linewidth=1.8)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time")
    ax.set_xlim(series.index[0], series.index[-1])
    loc = mdates.AutoDateLocator(maxticks=maxticks)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    ax.tick_params(direction="in", which="both", top=True, right=True)

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def overlay(series, labels, out_png, ylabel, rain=None, rain_unit="mm/h",
            colors=(BASE_COLOR, FLOW_COLOR), maxticks=12, dpi=300, figsize=(9, 4.8)):
    """Baseline-vs-scenario overlay in the house style.

    ``series``/``labels`` are parallel lists (2+ pandas Series). With ``rain`` a
    stacked figure is drawn (inverted hyetograph on top, overlay below); without it
    a single panel.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    apply()
    if rain is not None and len(rain) > 1:
        fig, (ax_rain, ax) = plt.subplots(
            2, 1, sharex=True, figsize=figsize, dpi=dpi,
            gridspec_kw={"height_ratios": [1, 2], "hspace": 0.08},
        )
        tnum = mdates.date2num(rain.index.to_pydatetime())
        widths = np.diff(tnum)
        widths = np.append(widths, widths[-1] if len(widths) else 1.0)
        ax_rain.bar(tnum, rain.values, width=widths, align="edge",
                    color=RAIN_COLOR, alpha=0.7, edgecolor="none")
        rmax = float(np.nanmax(rain.values))
        ax_rain.set_ylim(rmax * 1.15 if rmax > 0 else 1.0, 0.0)
        ax_rain.set_ylabel(f"Rainfall\n({rain_unit})")
        ax_rain.tick_params(direction="in", which="both", top=True, right=True)
        axes = [ax_rain, ax]
    else:
        fig, ax = plt.subplots(figsize=(figsize[0], 3.6), dpi=dpi)
        axes = [ax]

    ymax = 0.0
    for i, (s, lab) in enumerate(zip(series, labels)):
        c = colors[i % len(colors)]
        ax.plot(s.index, s.values, color=c, linewidth=1.8 if i else 1.5,
                linestyle="-" if i else "--", label=lab)
        ymax = max(ymax, float(np.nanmax(s.values)) if len(s) else 0.0)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time")
    if ymax > 0:
        ax.set_ylim(0.0, ymax * 1.15)
    lo = min(s.index[0] for s in series)
    hi = max(s.index[-1] for s in series)
    ax.set_xlim(lo, hi)
    loc = mdates.AutoDateLocator(maxticks=maxticks)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    ax.tick_params(direction="in", which="both", top=True, right=True)
    ax.legend(frameon=False, loc="best")

    fig.align_ylabels(axes)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def profile(x, bed, water, out_png, crown=None, ground=None, node_marks=None,
            water_label="Max water level", dpi=300, figsize=(10, 4.2), max_node_labels=15):
    """Longitudinal profile: bed / crown / ground / max water level along chainage.

    ``x, bed, water`` are equal-length sequences (m). ``crown``/``ground`` optional
    (may contain None/NaN gaps). ``node_marks`` = list of ``(x, node_id)`` boundaries.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    apply()
    x = np.asarray(x, dtype=float)
    bed = np.asarray(bed, dtype=float)
    water = np.asarray(water, dtype=float)
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.fill_between(x, bed, water, where=water >= bed, color=WATER_COLOR, alpha=0.18, linewidth=0)
    ax.plot(x, water, color=WATER_COLOR, linewidth=1.8, label=water_label)
    ax.plot(x, bed, color=BED_COLOR, linewidth=1.5, label="Bed / invert")
    if crown is not None:
        cr = np.asarray([np.nan if v is None else v for v in crown], dtype=float)
        if np.isfinite(cr).any():
            ax.plot(x, cr, color=CROWN_COLOR, linewidth=1.2, linestyle="--", label="Crown")
    if ground is not None:
        gr = np.asarray([np.nan if v is None else v for v in ground], dtype=float)
        if np.isfinite(gr).any():
            ax.plot(x, gr, color=GROUND_COLOR, linewidth=1.2, linestyle="-.", label="Ground")

    if node_marks:
        ylo, yhi = ax.get_ylim()
        # every boundary gets a line + label unless the chain is long; then only the ends
        labelled = node_marks if len(node_marks) <= max_node_labels else [node_marks[0], node_marks[-1]]
        for xm, nid in labelled:   # first label sits right of its line so it clears the y-axis
            ax.axvline(xm, color="#BBBBBB", linewidth=0.6, zorder=0)
            ax.text(xm, yhi, str(nid), rotation=90, fontsize=8, va="top", color="#666666",
                    ha="left" if xm == node_marks[0][0] else "right")
        ax.set_ylim(ylo, yhi)

    ax.set_xlabel("Chainage (m)")
    ax.set_ylabel("Level (m)")
    ax.set_xlim(float(np.nanmin(x)), float(np.nanmax(x)))
    ax.tick_params(direction="in", which="both", top=True, right=True)
    ax.legend(frameon=False, loc="best", fontsize=10)

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png


def network_map(reach_lines, node_xy, out_png, dpi=300, figsize=(8, 8),
                line_color=RAIN_COLOR, node_color=FLOW_COLOR):
    """Network layout map: reaches as polylines, nodes as points, equal aspect.

    ``reach_lines``: list of coordinate lists [[(x,y),...], ...].
    ``node_xy``: list of (x, y).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    apply()
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    if reach_lines:
        ax.add_collection(LineCollection(reach_lines, colors=line_color, linewidths=0.7))
    if node_xy:
        xs, ys = zip(*node_xy)
        ax.scatter(xs, ys, s=3, c=node_color, edgecolors="none", zorder=3)
    ax.set_aspect("equal", adjustable="datalim")
    ax.autoscale_view()
    ax.set_xlabel("Easting (m)")
    ax.set_ylabel("Northing (m)")
    ax.tick_params(direction="in", which="both", top=True, right=True)

    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out_png
