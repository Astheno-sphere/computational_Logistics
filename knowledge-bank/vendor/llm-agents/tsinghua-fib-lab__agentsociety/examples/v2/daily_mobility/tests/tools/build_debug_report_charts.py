#!/usr/bin/env python3
"""Build comparison charts for Daily Mobility debug report (Feishu)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import image as mpimg

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "feishu_report_figures"
OUT.mkdir(parents=True, exist_ok=True)

RUNS_LIVE = [
    ("eo20", "eo20"),
    ("eo21", "eo21"),
    ("eo22", "eo22"),
    ("eo23", "eo23"),
    ("eo24", "eo24"),
    ("eo25", "eo25"),
]

# Agent1 问卷意图 slots（来自各轮 questionnaire.md / live_verify summary）
METRICS_A1 = {
    "eo17": {"eating_out": 3, "work": 24, "moving": 13, "at_work_aoi": 15},
    "eo18": {"eating_out": 7, "work": 14, "moving": 2, "at_work_aoi": 16},
    "eo19": {"eating_out": 8, "work": 7, "moving": 0, "at_work_aoi": 0},
    "eo20": {"eating_out": 0, "work": 0, "moving": 0, "at_work_aoi": 0},
    "eo24": {"eating_out": 7, "work": 15, "moving": 13, "at_work_aoi": 2},
    "eo25": {"eating_out": 0, "work": 0, "moving": 0, "at_work_aoi": 0},
}

METRICS_A2 = {
    "eo17": {"eating_out": 4, "work": 0, "moving": 16, "at_work_aoi": 13},
    "eo18": {"eating_out": 9, "work": 0, "moving": 16, "at_work_aoi": 6},
    "eo19": {"eating_out": 14, "work": 10, "moving": 0, "at_work_aoi": 0},
    "eo24": {"eating_out": 0, "work": 0, "moving": 3, "at_work_aoi": 0},
}

COPY_TO_OUT = [
    ("multi2_eo17_agent1_detail.png", "eo17_agent1_detail.png"),
    ("multi2_eo18_agent1_detail.png", "eo18_agent1_detail.png"),
    ("multi2_eo19_agent1_detail.png", "eo19_agent1_detail.png"),
    ("multi2_eo19_agent2_detail.png", "eo19_agent2_detail.png"),
    ("multi2_eo17_agent1_aoi_timeline.png", "eo17_agent1_aoi_timeline.png"),
    ("multi2_eo18_agent1_aoi_timeline.png", "eo18_agent1_aoi_timeline.png"),
    ("multi2_eo19_agent1_aoi_timeline.png", "eo19_agent1_aoi_timeline.png"),
    ("multi2_eo18_agent2_aoi_timeline.png", "eo18_agent2_aoi_timeline.png"),
    ("multi2_eo19_agent2_aoi_timeline.png", "eo19_agent2_aoi_timeline.png"),
    ("multi2_eo19_agent1_actions.png", "eo19_agent1_actions.png"),
    ("multi2_eo19_agent2_actions.png", "eo19_agent2_actions.png"),
]


def load_summary(bench: str) -> dict | None:
    p = ROOT / f"live_verify_{bench}" / "summary.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def fill_metrics_from_summary() -> None:
    for bid in ("eo20", "eo23", "eo24", "eo25"):
        s = load_summary(bid)
        if not s:
            continue
        intents = s.get("intent_mix") or {}
        loc = s.get("location_mix") or {}
        METRICS_A1[bid] = {
            "eating_out": intents.get("eating out", 0),
            "work": intents.get("work", 0),
            "moving": loc.get("moving", 0),
            "at_work_aoi": METRICS_A1.get(bid, {}).get("at_work_aoi", 0),
        }


def count_moving_from_artifacts(bench: str, agent_id: int = 1) -> tuple[int, int]:
    art = Path(f"/tmp/multi2_{bench}/artifacts")
    if not art.is_dir():
        return 0, 0
    moving = total = 0
    work_aoi = 500041984 if agent_id == 1 else 500026935
    at_work = 0
    for f in art.glob("questionnaire_*.json"):
        d = json.loads(f.read_text())
        for snap in d.get("mobility_snapshots", []):
            if snap.get("agent_id") != agent_id:
                continue
            total += 1
            if snap.get("status") == "moving":
                moving += 1
            if snap.get("aoi_id") == work_aoi:
                at_work += 1
    return moving, total, at_work


def stage_copies() -> None:
    for src_name, dst_name in COPY_TO_OUT:
        src = ROOT / src_name
        if src.is_file():
            shutil.copy2(src, OUT / dst_name)


def _panel(images: list[tuple[Path, str]], out_name: str, ncols: int = 1) -> None:
    paths = [(p, t) for p, t in images if p.is_file()]
    if not paths:
        return
    n = len(paths)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 3.8 * nrows))
    axes_flat = np.atleast_1d(axes).flatten()
    for ax, (p, title) in zip(axes_flat, paths):
        ax.imshow(mpimg.imread(p))
        ax.set_title(title, fontsize=10)
        ax.axis("off")
    for ax in axes_flat[len(paths) :]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / out_name, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_panels() -> None:
    _panel(
        [
            (OUT / "eo18_agent1_aoi_timeline.png", "eo18 · Agent1 AOI×意图"),
            (
                OUT / "eo19_agent1_aoi_timeline.png",
                "eo19 · Agent1（就餐补丁 · routing 困在家）",
            ),
            (
                ROOT / "live_verify_eo24/intention_real_aoi.png",
                "eo24 · live 意图×真实 AOI",
            ),
        ],
        "panel_aoi_agent1_eo18_19_24.png",
        ncols=1,
    )
    _panel(
        [
            (OUT / "eo18_agent2_aoi_timeline.png", "eo18 · Agent2（午餐窗全程 work）"),
            (
                OUT / "eo19_agent2_aoi_timeline.png",
                "eo19 · Agent2（午餐窗连续 eating out）",
            ),
        ],
        "panel_aoi_agent2_eo18_vs_eo19.png",
        ncols=1,
    )
    _panel(
        [
            (OUT / "eo17_agent1_detail.png", "eo17 · 需求+意图"),
            (OUT / "eo18_agent1_detail.png", "eo18"),
            (OUT / "eo19_agent1_detail.png", "eo19 · v19 基线"),
            (ROOT / "live_verify_eo24/live_state_curves.png", "eo24 · live 需求曲线"),
        ],
        "panel_needs_agent1_eo17_19_24.png",
        ncols=2,
    )
    live_row = []
    for bid, label in [("eo20", "eo20"), ("eo23", "eo23"), ("eo24", "eo24")]:
        p = ROOT / f"live_verify_{bid}" / "intention_real_aoi.png"
        if p.is_file():
            live_row.append((p, f"{label} · live 意图×AOI"))
    if live_row:
        _panel(live_row, "panel_live_intention_aoi_eo20_23_24.png", ncols=1)


def plot_baseline_vs_eo24_metrics() -> None:
    fill_metrics_from_summary()
    for bid in ("eo20", "eo24"):
        mv, tot, at_w = count_moving_from_artifacts(bid, 1)
        if tot:
            METRICS_A1[bid]["moving"] = mv
            METRICS_A1[bid]["at_work_aoi"] = at_w

    labels = ["eo17", "eo18", "eo19", "eo24"]
    x = np.arange(len(labels))
    _w = 0.2

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    keys = [
        ("eating_out", "eating out intent (slots)", "#e74c3c"),
        ("work", "work intent (slots)", "#5dade2"),
        ("moving", "status=moving (slots)", "#95a5a6"),
        ("at_work_aoi", "at profile work AOI (slots)", "#27ae60"),
    ]
    for ax, (key, title, color) in zip(axes.flat, keys):
        vals = [METRICS_A1[b].get(key, 0) for b in labels]
        bars = ax.bar(x, vals, color=color, width=0.55)
        ax.set_xticks(x, labels)
        ax.set_ylabel("slots / 48")
        ax.set_title(f"Agent 1 · {title}")
        ax.set_ylim(0, max(max(vals) * 1.15, 4))
        for bar, v in zip(bars, vals):
            if v:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    str(v),
                    ha="center",
                    fontsize=9,
                )
    fig.suptitle(
        "Agent1: eo17-19 (v19 meal patch) vs eo24 (mobility fix)",
        fontsize=12,
        weight="bold",
    )
    fig.tight_layout()
    fig.savefig(OUT / "compare_metrics_agent1_eo17_24.png", dpi=150)
    plt.close(fig)

    labels2 = ["eo18", "eo19"]
    fig, ax = plt.subplots(figsize=(8, 4))
    x2 = np.arange(2)
    for i, (key, lbl, c) in enumerate(
        [
            ("eating_out", "eating out", "#e74c3c"),
            ("moving", "moving", "#95a5a6"),
        ]
    ):
        vals = [METRICS_A2[b].get(key, 0) for b in labels2]
        ax.bar(x2 + (i - 0.5) * 0.35, vals, width=0.32, label=lbl, color=c)
    ax.set_xticks(x2, labels2)
    ax.set_title("Agent2 lunch: eo18 (no eat) vs eo19 (meal patch)")
    ax.legend()
    ax.set_ylabel("slots")
    fig.tight_layout()
    fig.savefig(OUT / "compare_metrics_agent2_eo18_19.png", dpi=150)
    plt.close(fig)


def plot_run_comparison() -> None:
    labels = []
    moving_pct = []
    work_pct = []
    errors = []
    meta = {
        "eo20": {"errors": 0},
        "eo21": {"errors": 33},
        "eo22": {"errors": 0},
        "eo23": {"errors": 0},
        "eo24": {"errors": 0},
        "eo25": {"errors": 0},
    }

    for bid, _ in RUNS_LIVE:
        s = load_summary(bid)
        mv, tot, _ = count_moving_from_artifacts(bid, 1)
        labels.append(bid)
        if s:
            intents = s.get("intent_mix") or {}
            total_i = sum(intents.values()) or max(tot, 1)
            work_pct.append(100 * intents.get("work", 0) / total_i)
            if tot == 0:
                loc = s.get("location_mix") or {}
                tot = sum(loc.values()) or 48
                mv = loc.get("moving", 0)
        else:
            work_pct.append(0)
        moving_pct.append(100 * mv / max(tot, 1))
        errors.append(meta.get(bid, {}).get("errors", 0))

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    x = np.arange(len(labels))
    axes[0].bar(x, moving_pct, color="#95a5a6")
    axes[0].set_xticks(x, labels, rotation=30, ha="right")
    axes[0].set_ylabel("% slots")
    axes[0].set_title("Agent1 moving %")
    axes[0].set_ylim(0, 100)
    axes[0].axhline(20, color="#c0392b", ls="--", lw=1, alpha=0.6)

    axes[1].bar(x, work_pct, color="#5dade2")
    axes[1].set_xticks(x, labels, rotation=30, ha="right")
    axes[1].set_title("Agent1 work intent %")

    axes[2].bar(x, errors, color="#e74c3c")
    axes[2].set_xticks(x, labels, rotation=30, ha="right")
    axes[2].set_title("engine step errors")

    fig.suptitle("eo20-eo25 live runs", fontsize=13, weight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "run_comparison_bars.png", dpi=150)
    plt.close(fig)


def plot_eo24_timeline() -> None:
    src = ROOT / "live_verify_eo24"
    for name, out_name in [
        ("live_timeline.png", "eo24_intention_location_timeline.png"),
        ("intention_real_aoi.png", "eo24_intention_aoi.png"),
        ("live_state_curves.png", "eo24_needs_curves.png"),
    ]:
        p = src / name
        if p.is_file():
            shutil.copy2(p, OUT / out_name)


def plot_moving_streak_eo24() -> None:
    art = Path("/tmp/multi2_eo24/artifacts")
    if not art.is_dir():
        return
    slots, status = [], []
    files = sorted(
        art.glob("questionnaire_*.json"),
        key=lambda p: json.loads(p.read_text()).get("step_count", 0),
    )
    for f in files:
        d = json.loads(f.read_text())
        slot = d.get("step_count", 0)
        snap = next((x for x in d["mobility_snapshots"] if x["agent_id"] == 1), None)
        if not snap:
            continue
        slots.append(slot)
        status.append(1 if snap.get("status") == "moving" else 0)

    fig, ax = plt.subplots(figsize=(14, 2.2))
    colors = ["#95a5a6" if s else "#5dade2" for s in status]
    ax.bar(slots, [1] * len(slots), color=colors, width=0.9)
    ax.set_xlim(-0.5, max(slots, default=47) + 0.5)
    ax.set_yticks([])
    ax.set_xlabel("slot (30min)")
    ax.set_title("eo24 Agent1 mobility status (gray=moving)")
    fig.tight_layout()
    fig.savefig(OUT / "eo24_moving_streak.png", dpi=150)
    plt.close(fig)


def main() -> None:
    stage_copies()
    plot_baseline_vs_eo24_metrics()
    plot_panels()
    plot_run_comparison()
    plot_eo24_timeline()
    plot_moving_streak_eo24()
    print(f"Wrote figures to {OUT} ({len(list(OUT.glob('*.png')))} files)")


if __name__ == "__main__":
    main()
