#!/usr/bin/env python
"""Named entry points into the test suite.

The full suite is one process and several hundred tests, and a few files
dominate its wall time, so "run the tests" after a small change usually means
waiting minutes for coverage that had nothing to do with the change. This
script does not change, skip, or reorder any test. It only selects which files
pytest is pointed at, so a targeted run is a named command instead of a
hand-written `-k` expression that is different every time.

    python run_tests.py                     # default lane: everything except slow
    python run_tests.py --list              # show groups, file counts, and timing
    python run_tests.py geometry            # one group
    python run_tests.py api chat            # several groups
    python run_tests.py --all               # everything, including the slow lane
    python run_tests.py --slow              # only the slow files
    python run_tests.py --changed           # only files git says you touched
    python run_tests.py --audit             # check every test file has a group

Anything after `--` is handed to pytest unchanged:

    python run_tests.py geometry -- -x -vv
    python run_tests.py --all -- --durations=25

Known-gap markers still work the way tests/conftest.py documents:

    python run_tests.py --all -- -m spine_gap
    python run_tests.py --all -- -m "not spine_gap and not fixture_drift"
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests"

# Group name -> filename globs, matched against the test file stem without the
# leading "test_". A file may appear in more than one group where it genuinely
# covers both; --audit is what guarantees none appear in zero.
GROUPS: dict[str, tuple[str, ...]] = {
    "geometry": (
        "admin_*", "canada_*", "country_geography*", "country_release_*", "foundation_geometry*",
        "external_reference_*", "geography_*", "geometry_*", "grid_*", "loc_id_*", "marine_*",
        "place_lookup*", "preprocessor_location_spine", "reference_*",
        "region_location_aliases", "sidechain_admin_*",
    ),
    "ops": (
        "event_query*", "exact_event*", "flood_*", "nws_*", "openaq_*",
        "ops_*", "tsunami_*",
    ),
    "api": (
        "access_policy*", "artifact_access*", "caller_identity", "mcp_*", "open_core_auth*",
        "public_discovery*", "published_artifacts", "repo_split_*",
        "research_tool_guards", "tool_access_*",
    ),
    "chat": (
        "chat_*", "llm_*", "orchestrator_*", "order_taker_*", "postprocess_*",
        "read_posture*",
    ),
    "catalog": (
        "catalog_*", "coverage_claim", "data_*", "default_load_*",
        "load_strategies*", "overlay_display_*", "public_catalog_*",
        "source_*",
    ),
    "account": (
        "confirmed_order_cap*", "hosted_*", "local_wrapper_*",
    ),
}

# Measured, not guessed. These two files are essentially the entire cost of the
# suite; everything else combined runs in about a minute and a half.
#
#   preprocessor_location_spine   ~450s, of which 435s is the single test
#                                 test_geometry_backed_query_location_samples
#   mcp_tool_universe_gates       ~500s, dominated by
#                                 test_trusted_token_lifts_the_cap_on_every_capped_tool
#
# Both walk real geometry across a broad sample rather than a fixture, which is
# what makes them valuable and what makes them slow. Nothing here changes or
# skips them: they run in --all and --slow, just not in a quick check.
#
# Re-measure after any change to either:
#   python run_tests.py --all -- --durations=25
SLOW: tuple[str, ...] = (
    "preprocessor_location_spine",
    "mcp_tool_universe_gates",
)


def stems() -> list[str]:
    return sorted(path.stem[len("test_"):] for path in TESTS.glob("test_*.py"))


def matches(stem: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(stem, pattern) for pattern in patterns)


def files_for(names: list[str], include_slow: bool) -> list[str]:
    selected: set[str] = set()
    for stem in stems():
        for name in names:
            if matches(stem, GROUPS[name]):
                selected.add(stem)
                break
    if not include_slow:
        selected -= set(SLOW)
    return sorted(selected)


def ungrouped() -> list[str]:
    covered = {stem for stem in stems()
               if any(matches(stem, patterns) for patterns in GROUPS.values())}
    return [stem for stem in stems() if stem not in covered]


def to_paths(names: list[str]) -> list[str]:
    # Forward slashes, not os.sep: git reports posix paths, and comparing these
    # against `git diff` output on Windows silently matched nothing otherwise.
    return [f"tests/test_{stem}.py" for stem in names]


def run(paths: list[str], extra: list[str]) -> int:
    if not paths:
        print("No test files selected.", file=sys.stderr)
        return 1
    command = [sys.executable, "-m", "pytest", *paths, *extra]
    print(f"[run_tests] {len(paths)} file(s)")
    print(f"[run_tests] {' '.join(command[1:6])} ... ({len(command)} args)")
    return subprocess.call(command, cwd=ROOT)


def show_list() -> int:
    slow = set(SLOW)
    print("Groups (default lane excludes the slow files marked *):\n")
    for name, patterns in GROUPS.items():
        selected = [stem for stem in stems() if matches(stem, patterns)]
        slow_here = [stem for stem in selected if stem in slow]
        note = f"  ({len(slow_here)} slow)" if slow_here else ""
        print(f"  {name:10} {len(selected):3} files{note}")
        for stem in selected:
            print(f"      {'*' if stem in slow else ' '} {stem}")
        print()
    print("Slow files, excluded unless --all/--slow:")
    for stem in SLOW:
        print(f"    * {stem}")
    orphans = ungrouped()
    if orphans:
        print("\nWARNING: test files in no group (they never run from a group):")
        for stem in orphans:
            print(f"    ! {stem}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # default=None, not []: argparse validates a non-None default against
    # `choices`, and an empty list is not a valid choice.
    parser.add_argument("groups", nargs="*", choices=sorted(GROUPS), default=None,
                        help="Group names to run. Omit for the default lane.")
    parser.add_argument("--all", action="store_true", help="Every test file, slow included.")
    parser.add_argument("--slow", action="store_true", help="Only the slow files.")
    parser.add_argument("--changed", action="store_true",
                        help="Only test files whose names relate to your uncommitted changes.")
    parser.add_argument("--list", action="store_true", help="Show groups and exit.")
    parser.add_argument("--audit", action="store_true",
                        help="Fail if any test file belongs to no group.")
    parser.add_argument("--include-slow", action="store_true",
                        help="Keep slow files in a group or default run.")
    # Split on "--" before argparse sees it. argparse strips the separator but
    # then tries to validate the pytest flags after it against `choices`, so
    # `run_tests.py api -- -q` would fail on "-q" as a group name.
    argv = sys.argv[1:]
    if "--" in argv:
        index = argv.index("--")
        argv, extra = argv[:index], argv[index + 1:]
    else:
        extra = []
    args = parser.parse_args(argv)

    if args.list:
        return show_list()

    if args.audit:
        orphans = ungrouped()
        if orphans:
            print("Test files in no group:", file=sys.stderr)
            for stem in orphans:
                print(f"  {stem}", file=sys.stderr)
            print("\nAdd them to GROUPS in run_tests.py so a group run cannot "
                  "silently skip them.", file=sys.stderr)
            return 1
        print(f"All {len(stems())} test files belong to a group.")
        return 0

    # An ungrouped file would silently vanish from every group run, which is the
    # one failure mode that makes a selective runner worse than no runner.
    orphans = ungrouped()
    if orphans and not args.all:
        print(f"[run_tests] WARNING: {len(orphans)} test file(s) belong to no group "
              f"and will not run from a group selection: {', '.join(orphans)}",
              file=sys.stderr)

    if args.all:
        return run(["tests"], extra)
    if args.slow:
        return run(to_paths(list(SLOW)), extra)
    if args.changed:
        return run_changed(extra)

    names = args.groups or sorted(GROUPS)
    include_slow = args.include_slow
    selected = files_for(names, include_slow)
    if not include_slow:
        skipped = sorted(set(SLOW) & set(files_for(names, True)))
        if skipped:
            print(f"[run_tests] skipping {len(skipped)} slow file(s): "
                  f"{', '.join(skipped)}  (add --include-slow to keep them)")
    return run(to_paths(selected), extra)


def run_changed(extra: list[str]) -> int:
    """Run test files whose stem appears in a changed source path.

    Deliberately crude: it matches on name overlap, so it is a fast first pass
    and not a dependency graph. Treat a green --changed run as "probably fine",
    then run the group before you commit.
    """
    try:
        output = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except Exception as exc:
        print(f"[run_tests] could not read git changes: {exc}", file=sys.stderr)
        return 1
    changed_paths = [line.strip() for line in output.splitlines() if line.strip()]
    if not changed_paths:
        print("[run_tests] no uncommitted changes; nothing to select.")
        return 0

    # Tokens from changed file names, e.g. mapmover/routes/geometry.py -> geometry
    tokens = {Path(path).stem for path in changed_paths}
    changed_set = set(changed_paths)
    selected = []
    for stem in stems():
        if f"tests/test_{stem}.py" in changed_set:
            selected.append(stem)
            continue
        if any(token and token in stem for token in tokens):
            selected.append(stem)

    if not selected:
        print("[run_tests] no test file names matched your changes. "
              "Run a group instead, e.g. python run_tests.py api")
        return 0
    print(f"[run_tests] changed-file heuristic matched: {', '.join(selected)}")
    return run(to_paths(selected), extra)


if __name__ == "__main__":
    raise SystemExit(main())
