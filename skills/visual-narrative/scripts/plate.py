"""Plate template: the fixed page every Asthenosphere explainer uses.

kicker + document label / framed hero figure / rule / headline with one accent word /
one procedural sentence / code caption / sources / footer. 1440 x 1800 px (4:5).
"""
import textwrap
from dataclasses import dataclass

import matplotlib.pyplot as plt
from matplotlib import font_manager

INK = "#10161B"       # ground
PAPER = "#E8E1CF"     # primary linework and text
DIM = "#8C949A"       # secondary text
FAINT = "#2A343C"     # context linework (buildings, minor streets)
WATER = "#17242D"
ACCENT = "#FF5B3A"    # the one thing the plate is about

SANS = "Inter"
SERIF = "Liberation Serif"
MONO = "DejaVu Sans Mono"
W, H, DPI = 8.0, 10.0, 180


@dataclass
class Plate:
    kicker: str                 # italic, lowercase: the question the plate answers
    label: str                  # top right, caps: place / dataset / method
    headline: list              # [(text, is_accent), ...], caps
    sentence: str               # the definition written as something you do
    code: str = ""
    sources: str = ""
    number: str = "01"
    series: str = "ASTHENOSPHERE  ·  COMPUTATIONAL LOGISTICS"


def _font(family, **kw):
    return dict(fontfamily=family if family in {f.name for f in font_manager.fontManager.ttflist} else "DejaVu Sans", **kw)


def figure(p: Plate):
    """Return (fig, hero_ax). Draw the diagram into hero_ax, then call save()."""
    fig = plt.figure(figsize=(W, H), dpi=DPI, facecolor=INK)
    fig.text(0.0625, 0.935, p.kicker, color=DIM, size=13, **_font(SERIF, style="italic"))
    fig.text(0.9375, 0.935, p.label, color=PAPER, size=8.5, ha="right", **_font(SANS))
    ax = fig.add_axes([0.0625, 0.255, 0.875, 0.665], facecolor=INK)
    for s in ax.spines.values():
        s.set_color(DIM); s.set_linewidth(0.6)
    ax.set_xticks([]); ax.set_yticks([])
    fig.add_artist(plt.Line2D([0.0625, 0.9375], [0.232, 0.232], color=PAPER, lw=1.6))
    x = 0.0625
    r = fig.canvas.get_renderer()
    for text, accent in p.headline:
        t = fig.text(x, 0.178, text, color=ACCENT if accent else PAPER, size=27, weight="bold", **_font(SANS))
        x += t.get_window_extent(r).width / fig.bbox.width + 0.012
    fig.text(0.0625, 0.163, textwrap.fill(p.sentence, 100), color=PAPER, size=11.2, va="top", linespacing=1.45,
             **_font(SERIF))
    if p.code:
        fig.text(0.0625, 0.098, p.code, color=DIM, size=7.5, **_font(MONO))
    if p.sources:
        fig.text(0.0625, 0.082, p.sources, color=DIM, size=6.5, va="top", linespacing=1.6, **_font(SANS))
    fig.text(0.0625, 0.028, p.series, color=DIM, size=7, **_font(SANS))
    fig.text(0.9375, 0.028, p.number, color=ACCENT, size=7, weight="bold", ha="right", **_font(SANS))
    return fig, ax


def north_arrow(ax, x=0.94, y=0.92):
    ax.annotate("", xy=(x, y + 0.035), xytext=(x, y - 0.01), xycoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color=PAPER, lw=0.8))
    ax.text(x, y + 0.045, "N", transform=ax.transAxes, color=PAPER, ha="center", size=8, **_font(SANS))


def scale_bar(ax, metres, x0_data, y0_data, label=None):
    ax.plot([x0_data, x0_data + metres], [y0_data, y0_data], color=PAPER, lw=0.9, solid_capstyle="butt")
    for xx, t in [(x0_data, "0"), (x0_data + metres, label or f"{metres:g} m")]:
        ax.plot([xx, xx], [y0_data - metres * 0.03, y0_data + metres * 0.03], color=PAPER, lw=0.9)
        ax.text(xx, y0_data + metres * 0.07, t, color=PAPER, ha="center", size=7, **_font(SANS))


def save(fig, path):
    fig.savefig(path, dpi=DPI, facecolor=INK)
    plt.close(fig)
