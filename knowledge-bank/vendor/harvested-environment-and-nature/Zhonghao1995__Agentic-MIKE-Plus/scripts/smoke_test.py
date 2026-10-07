"""Smoke test: discover tools and exercise the read path on the Sirius_RTC copy.

Run:  .venv\\Scripts\\python.exe scripts\\smoke_test.py
Exits nonzero if discovery fails or a live read tool errors.
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from mikeplus_mcp.registry import discover_tools  # noqa: E402


def main() -> int:
    tools = {t.name: t for t in discover_tools()}
    print("discovered tools:", ", ".join(sorted(tools)))
    expected = {
        "mike_model_info", "mike_get_values", "mike_set_values", "mike_run",
        "mike_set_scenario", "mike_import_swmm",
        "mike_results_list", "mike_results_summary", "mike_results_read",
        "mike_results_compare", "mike_results_flooding",
        "mike_plot_rain_flow", "mike_plot_timeseries", "mike_plot_network",
        "mike_plot_compare", "mike_plot_profile",
        "mike_rain_to_dfs0", "mike_manifest_write",
    }
    missing = expected - set(tools)
    if missing:
        print("MISSING tools:", missing)
        return 1

    # live read-path check against the bundled sample copy, if present
    sample_dir = os.path.join(ROOT, "_scratch", "sirius_rtc")
    res1ds = glob.glob(os.path.join(sample_dir, "**", "*.res1d"), recursive=True)
    if not res1ds:
        print("no sample .res1d found under _scratch/sirius_rtc — skipping live check.")
        print("SMOKE OK (discovery only)")
        return 0

    res = next((r for r in res1ds if "HD" in os.path.basename(r)), res1ds[0])
    out = tools["mike_results_list"].handler({"res1d": res})
    if not out.get("ok"):
        print("mike_results_list FAILED:", out)
        return 1
    print(f"mike_results_list OK on {os.path.basename(res)}: quantities={out['quantities']}")
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
