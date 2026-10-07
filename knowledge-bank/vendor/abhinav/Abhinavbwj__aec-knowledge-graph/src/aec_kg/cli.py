"""Command-line interface: `aec-kg <subcommand> ...`."""
from __future__ import annotations

import argparse
import json
import sys

# Reconfigure stdout to UTF-8 so non-ASCII names (Sjöstad, Pompéia) render correctly.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from . import __version__
from . import load as loader
from . import query as q


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("(no results)")
        return
    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}
    print(" | ".join(h.ljust(widths[h]) for h in headers))
    print("-+-".join("-" * widths[h] for h in headers))
    for r in rows:
        print(" | ".join(str(r.get(h, "")).ljust(widths[h]) for h in headers))


def cmd_build(args):
    loader.build(reset=not args.no_reset)


def cmd_etl(args):
    from .etl import from_trinity
    n_skills, n_mentions = from_trinity.run_etl(verbose=True)
    print(f"\nETL complete: {n_skills} skills, {n_mentions} mentions written to data/auto/")
    print("Run `aec-kg build` to merge them into the graph.")


def cmd_stats(args):
    s = q.stats()
    nodes = {k: v for k, v in s.items() if k[0].isupper() and not k.isupper()}
    edges = {k: v for k, v in s.items() if k.isupper()}
    print("Nodes:")
    for k, v in nodes.items():
        print(f"  {k:12} {v}")
    print("Edges:")
    for k, v in edges.items():
        print(f"  {k:14} {v}")


def cmd_query(args):
    rows: list[dict] | dict
    if args.kind == "influenced-by":
        rows = q.influenced_by(args.id, depth=args.depth)
    elif args.kind == "projects-for-pattern":
        rows = q.projects_for_pattern(args.id)
    elif args.kind == "projects-for-movement":
        rows = q.projects_for_movement(args.id)
    elif args.kind == "lineage":
        rows = q.lineage(args.id)
    elif args.kind == "standard-lineage":
        rows = q.standard_lineage()
    elif args.kind == "project":
        rows = q.project_full_profile(args.id)
    elif args.kind == "find-projects":
        rows = q.find_projects(
            movement=args.movement,
            standard=args.standard,
            pattern=args.pattern,
            typology=args.typology,
        )
    elif args.kind == "skills-mentioning":
        rows = q.skills_mentioning(args.id)
    elif args.kind == "skill-citations":
        rows = q.skill_citations(args.id)
    elif args.kind == "most-cited":
        rows = q.most_cited(label=args.label or "Theorist", top=args.top or 10)
    else:
        print(f"unknown query: {args.kind}", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    elif isinstance(rows, dict):
        if not rows:
            print("(not found)")
        else:
            for k, v in rows.items():
                print(f"{k}: {v}")
    else:
        _print_table(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aec-kg", description="AEC Knowledge Graph CLI")
    p.add_argument("--version", action="version", version=f"aec-kg {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="Rebuild the graph DB from JSONL seeds")
    pb.add_argument("--no-reset", action="store_true", help="Append instead of wipe")
    pb.set_defaults(func=cmd_build)

    pe = sub.add_parser("etl", help="Extract Skill nodes + MENTIONS edges from sibling plugins")
    pe.set_defaults(func=cmd_etl)

    ps = sub.add_parser("stats", help="Print node/edge counts")
    ps.set_defaults(func=cmd_stats)

    pq = sub.add_parser("query", help="Run a canonical query")
    pq.add_argument(
        "kind",
        choices=[
            "influenced-by",
            "projects-for-pattern",
            "projects-for-movement",
            "lineage",
            "standard-lineage",
            "project",
            "find-projects",
            "skills-mentioning",
            "skill-citations",
            "most-cited",
        ],
    )
    pq.add_argument("--id", help="Subject id (e.g. theorist:jane-jacobs)")
    pq.add_argument("--depth", type=int, default=2, help="For influenced-by")
    pq.add_argument("--movement", help="For find-projects")
    pq.add_argument("--standard", help="For find-projects")
    pq.add_argument("--pattern", help="For find-projects")
    pq.add_argument("--typology", help="For find-projects")
    pq.add_argument("--label", help="For most-cited (Theorist | Standard | Tool | ...)")
    pq.add_argument("--top", type=int, help="For most-cited (default 10)")
    pq.add_argument("--json", action="store_true")
    pq.set_defaults(func=cmd_query)

    args = p.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
