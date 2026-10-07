"""Render saved deployment latency results; no inference or network requests.

Requires matplotlib==3.10.8. Run from any directory with Python 3.12:
    python render_latency.py
The PNG is exactly 1800 x 1150 pixels. A JSON manifest binds the public reports,
individual samples, values, script and rendered image to their SHA-256 hashes.
"""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import math
import platform

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


DIRECTORY = Path(__file__).resolve().parent
ROOT = DIRECTORY.parents[2]
PROVIDERS = [
    ("Open-Jev-2B", "2b-h100-20260920", "#167366"),
    ("Jev 1.13.0", "jev-api-20260920", "#BB8A32"),
    ("GPT-5.6 Luna", "openai-gpt-5.6-luna-20260920", "#426CA6"),
    ("GPT-6 Astra", "openai-gpt-6-astra-20260920", "#79608F"),
]
PANELS = [
    ("customer_service", "Customer service", "8 Boolean questions"),
    ("context-1024-choice-32", "Larger candidate set", "1,024 state tokens / 32 candidates"),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high] - values[low]) * (position - low)


def load_values():
    values, sources, workload_hashes = {}, {}, set()
    for label, folder, _ in PROVIDERS:
        directory = ROOT / "reports/inference-latency/public" / folder
        report = json.loads((directory / "report.json").read_text())
        samples = [json.loads(line) for line in (directory / "samples.jsonl").read_text().splitlines()]
        publication = json.loads((directory / "publication.json").read_text())
        for filename in ("report.json", "samples.jsonl", "requests.json", "publication.json"):
            path = directory / filename
            sources[str(path.relative_to(ROOT))] = sha(path)
            if filename in publication["files"]:
                assert sha(path) == publication["files"][filename]["public_sha256"]
        workload_hashes.add(report["workload_manifest_sha256"])
        assert report["configuration"]["warmup"] == 3
        assert report["configuration"]["repetitions"] == 20
        for request_id, _, _ in PANELS:
            rows = [row for row in samples if row["request_id"] == request_id
                    and row["phase"] == "measured"
                    and (label != "Open-Jev-2B" or
                         row["transport"] == "http_loopback" and row["mode"] == "uncached")]
            assert len(rows) == 20 and all(row["success"] for row in rows)
            assert {row["repetition"] for row in rows} == set(range(20))
            timings = [row["wall_ms"] for row in rows]
            assert all(math.isfinite(value) and value > 0 for value in timings)
            summary = next(row for row in report["summaries"] if row["request_id"] == request_id
                           and (label != "Open-Jev-2B" or
                                row["transport"] == "http_loopback" and row["mode"] == "uncached"))
            pair = {"p50_ms": percentile(timings, .5), "p95_ms": percentile(timings, .95)}
            assert all(math.isclose(value, summary[key], rel_tol=0, abs_tol=1e-9)
                       for key, value in pair.items())
            values.setdefault(request_id, {})[label] = pair
    assert len(workload_hashes) == 1
    return values, sources, workload_hashes.pop()


def main():
    values, sources, workload_hash = load_values()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                         "axes.unicode_minus": False, "figure.dpi": 150,
                         "savefig.dpi": 150, "text.color": "#233744"})
    background, muted, grid = "#F5F7F8", "#52646F", "#DCE3E7"
    fig = plt.figure(figsize=(12, 1150 / 150), facecolor=background)
    fig.text(.055, .947, "Measured decision latency", fontsize=29, fontweight="bold", va="top")
    fig.text(.055, .882, "Full response, milliseconds  ·  Lower is better  ·  Two examples from 11 saved workloads",
             fontsize=12.5, color=muted, va="top")
    fig.legend(handles=[Patch(facecolor="#536775", label="Bar = P50"),
                        Line2D([0], [0], marker="o", color="#536775", linewidth=1.2,
                               markersize=5, label="Dot = P95")],
               loc="upper right", bbox_to_anchor=(.956, .949), ncol=2,
               frameon=False, fontsize=11.5, handlelength=1.3, columnspacing=1.5)
    fig.add_artist(Line2D([.514, .514], [.278, .817], transform=fig.transFigure,
                          color=grid, linewidth=1))
    axis_labels, callouts = [], []

    for index, (request_id, title, subtitle) in enumerate(PANELS):
        title_x, axes_x = (.055, .182) if index == 0 else (.55, .678)
        fig.text(title_x, .814, title, fontsize=19, fontweight="bold", va="top")
        fig.text(title_x, .772, subtitle, fontsize=12.5, color=muted, va="top")
        ax = fig.add_axes([axes_x, .323, .27, .405], facecolor=background)
        for row, (label, _, color) in enumerate(PROVIDERS):
            y = 3 - row
            p50, p95 = values[request_id][label]["p50_ms"], values[request_id][label]["p95_ms"]
            ax.barh(y, p50, height=.23, color=color, zorder=3)
            ax.plot([p50, p95], [y, y], color=color, linewidth=1.4, alpha=.75, zorder=4)
            ax.scatter([p95], [y], color=color, s=30, zorder=5)
            ax.text(0, y + .24, f"{p50:,.1f}  /  {p95:,.1f}", fontsize=11.6,
                    color="#243844", va="center", fontweight="medium")
        ax.set_yticks([3, 2, 1, 0], [label for label, _, _ in PROVIDERS])
        ax.tick_params(axis="y", length=0, pad=12, labelsize=11.6)
        ax.tick_params(axis="x", length=0, pad=9, labelsize=10, colors=muted)
        ax.set_xlim(0, 2600)
        ax.set_ylim(-.48, 3.66)
        ax.set_xticks([0, 500, 1000, 1500, 2000, 2500], ["0", "500", "1,000", "1,500", "2,000", "2,500"])
        ax.set_xlabel("Full-response latency (ms)", fontsize=10.5, color=muted, labelpad=10)
        axis_labels.append(ax.xaxis.label)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color=grid, linewidth=.65)
        for spine in ax.spines.values():
            spine.set_visible(False)
        callout = ("2B has the lowest P50 in this example." if index == 0 else
                   "2B is slower than Jev and Luna here.")
        callouts.append(fig.text(title_x, .226, callout, fontsize=11.8,
                                 color="#167366" if index == 0 else "#76553E"))

    fig.add_artist(Line2D([.055, .948], [.208, .208], transform=fig.transFigure,
                          color=grid, linewidth=1))
    notes = [
        "20 measured calls + 3 excluded warmups per workload/path · Concurrency 1 · Fresh connections · P95 is descriptive.",
        "2B: warm single H100, loopback HTTP, cache off. Jev / GPT: remote HTTPS; hosted hardware, including Jev's, undisclosed.",
        "Luna reasoning: none · Astra: low. Server prompt caching may apply: each GPT run reports cached inputs in 100/220 calls.",
        "Different deployment timings; no hardware-controlled speedup, throughput or energy claim. No new 9B latency measured.",
    ]
    for y, note in zip([.171, .139, .107, .075], notes):
        fig.text(.055, y, note, fontsize=10.6, color=muted)
    fig.text(.055, .033, "Source: published reports + individual samples · Measured September 20, 2026", fontsize=9.8, color=muted)
    fig.text(.948, .033, "github.com/Zefan-Cai/Open-Jev", fontsize=9.8, color=muted, ha="right")

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    width, height = fig.canvas.get_width_height()
    assert (width, height) == (1800, 1150)
    for text in fig.texts:
        bounds = text.get_window_extent(renderer)
        assert bounds.x0 >= 0 and bounds.y0 >= 0 and bounds.x1 <= width and bounds.y1 <= height
    for label, callout in zip(axis_labels, callouts):
        assert not label.get_window_extent(renderer).overlaps(callout.get_window_extent(renderer))
    output = DIRECTORY / "latency-comparison.png"
    fig.savefig(output, facecolor=background, metadata={"Title": "Measured decision latency"})
    plt.close(fig)
    manifest = {
        "schema_version": 1, "status": "rendered_from_verified_public_samples",
        "image": output.name, "image_sha256": sha(output), "image_size_pixels": [width, height],
        "render_script": Path(__file__).name, "render_script_sha256": sha(Path(__file__)),
        "runtime": {"python": platform.python_version(), "matplotlib": matplotlib.__version__,
                    "numpy": importlib.metadata.version("numpy"), "pillow": importlib.metadata.version("Pillow"),
                    "font": "DejaVu Sans", "font_sha256": sha(Path(font_manager.findfont("DejaVu Sans"))),
                    "backend": "Agg"},
        "source_sha256": sources, "canonical_workload_sha256": workload_hash,
        "values": values, "axes": {"shared_x_limits_ms": [0, 2600], "bar": "P50", "dot": "P95",
                                    "numeric_label": "P50 / P95 in milliseconds"},
        "selection": {"open_jev_2b": "warm loopback HTTP, cache off", "hosted": "fresh remote HTTPS"},
        "new_inference_calls": 0, "network_requests": 0,
    }
    (DIRECTORY / "latency-chart-source.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"png": str(output), "sha256": manifest["image_sha256"], "pixels": [width, height]}))


if __name__ == "__main__":
    main()
