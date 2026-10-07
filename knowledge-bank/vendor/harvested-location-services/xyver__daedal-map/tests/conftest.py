"""Test session hooks.

Separates registered known-gap failures from unexpected ones in the terminal
summary, so a real regression does not get lost among the known gaps, and so a
run after the spine rebuild immediately shows which gaps have closed.

Run just the known gaps:

    python -m pytest tests/ -m spine_gap
    python -m pytest tests/ -m fixture_drift

Run everything except them:

    python -m pytest tests/ -m "not spine_gap and not fixture_drift"
"""

from __future__ import annotations

import os
import pytest

# Public-runtime tests must never inherit a developer machine's private
# control-plane token and enqueue real HTTP telemetry. Individual telemetry
# unit tests call the sink directly with their own patched environment.
os.environ["QA_DISABLE_RUNTIME_ANALYTICS"] = "1"

KNOWN_GAP_MARKERS = ("spine_gap", "fixture_drift")


def _known_gap(item) -> tuple[str, str] | None:
    for marker_name in KNOWN_GAP_MARKERS:
        marker = item.get_closest_marker(marker_name)
        if marker is None:
            continue
        reason = ""
        if marker.args:
            reason = str(marker.args[0])
        elif marker.kwargs.get("reason"):
            reason = str(marker.kwargs["reason"])
        return marker_name, reason
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    gap = _known_gap(item)
    if gap is not None:
        report.known_gap = gap


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    failed = terminalreporter.stats.get("failed", []) or []
    if not failed:
        return

    known: dict[str, list[tuple[str, str]]] = {name: [] for name in KNOWN_GAP_MARKERS}
    unexpected: list[str] = []

    for report in failed:
        gap = getattr(report, "known_gap", None)
        if gap is None:
            unexpected.append(report.nodeid)
        else:
            known[gap[0]].append((report.nodeid, gap[1]))

    terminalreporter.write_sep("=", "KNOWN GAPS vs UNEXPECTED FAILURES", bold=True)

    for marker_name in KNOWN_GAP_MARKERS:
        entries = known.get(marker_name) or []
        if not entries:
            continue
        terminalreporter.write_line("")
        terminalreporter.write_line(f"[{marker_name}] {len(entries)} known failing:", bold=True)
        for node_id, reason in entries:
            terminalreporter.write_line(f"  - {node_id}")
            if reason:
                terminalreporter.write_line(f"      reason: {reason}")

    terminalreporter.write_line("")
    if unexpected:
        terminalreporter.write_line(
            f"UNEXPECTED failures ({len(unexpected)}) - these are NOT known gaps:",
            bold=True,
            red=True,
        )
        for node_id in unexpected:
            terminalreporter.write_line(f"  - {node_id}", red=True)
    else:
        terminalreporter.write_line(
            "No unexpected failures. Every failure above is a registered known gap.",
            bold=True,
            green=True,
        )
    terminalreporter.write_line("")
