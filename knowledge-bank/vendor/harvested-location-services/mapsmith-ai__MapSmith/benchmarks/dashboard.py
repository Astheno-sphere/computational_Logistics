"""One page to watch MapSmith by, and to tune it from.

    python benchmarks/dashboard.py
    python benchmarks/dashboard.py --log /data/discovery.jsonl --argleton ../argleton
    python benchmarks/dashboard.py --out /tmp/mapsmith.html

Everything this project knows about itself is already computed somewhere: the
catalog counts itself, `discovery_report.py` recomputes the retrieval figures,
the degradation test measures the curve, and Argleton scores five engines
against traps with a truth derived by hand. It is all in different places and
most of it is printed once and lost, which is how a number ages into a claim.

This gathers it into one self-contained HTML file — no CDN, no fonts, no
analytics, works with the network off — with six panels:

* **Overview** — what exists right now, in numbers.
* **Operations** — every operation, by family and by whether a caller can
  actually find it. The tuning list: an operation nothing reaches does not
  exist, and this says which ones and at what rank.
* **Search quality** — the facet ablation, both rankers, and the degradation
  curve as the catalog grows.
* **Traps** — Argleton's families and what each engine does with them, MapSmith
  included and not flattered.
* **Answer the open questions** — the requests where the two model labellers
  disagree, and the cases the discovery log recorded, answered by clicking. The
  percentages recompute against your answers as you give them.
* **Trend** — every generation of this page appends a row, so the numbers become
  a series instead of a snapshot.

It is a snapshot: adding an operation or a trap does not change a file that has
already been written. Regenerating is one command, costs about ten seconds, and
keeps every answer you have given — answers are stored against the text of the
question, never its position.

`--argleton <path>` points at a checkout of the suite (a separate repository in
a separate organisation, deliberately). Without it the traps panel falls back to
the vendored citation in `docs/argleton-run.json`, which carries the run's
headline numbers but not the per-family detail.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "tests"))

import discovery_report  # noqa: E402

from mapsmith import __version__, catalog  # noqa: E402

# The caller-phrased queries live with the degradation test, which is where they
# are kept honest (a test asserts they stay far from the catalog's own words).
# Importing them beats keeping a second copy that drifts.
from test_retrieval_degradation import (  # noqa: E402
    CALLER_QUERIES,
    _lexical_top,
    _subset,
)


def commit() -> str:
    """The checkout this page describes, or '' outside a git tree."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=10, check=False,
        )
        return out.stdout.strip()
    except OSError:
        return ""


def tool_names() -> list[str]:
    """The tools an agent actually chooses between — the count with a ceiling."""
    source = (ROOT / "src" / "mapsmith" / "server.py").read_text(encoding="utf-8")
    names = []
    for block in source.split("@mcp.tool(")[1:]:
        head = block.split("def ", 1)
        if len(head) > 1:
            names.append(head[1].split("(", 1)[0].strip())
    return names


#: What a caller who describes their own situation accurately would declare.
#: Not the family: that one is a guess about our taxonomy and only orders.
DECLARED = ("input_kind", "produces", "dataset_inputs")


def _probe(query: str, engine: str, facets: dict[str, Any], name: str) -> dict[str, Any]:
    """Ask for one operation and report what came back, not just whether.

    Three outcomes, and collapsing them was the first thing this dashboard got
    wrong about itself: ranked at a position, absent from an answer that was
    given, and no answer at all because the two engines shared nothing and the
    search declined (`unsure`). The third is not a discoverability failure of
    the entry — it is the refusal gate firing — and a page that draws it as "not
    found" invents ten broken operations.
    """
    answer = catalog.search(query, limit=len(catalog.OPERATIONS), engine=engine, **facets)
    shape = (
        answer[0]["status"]
        if len(answer) == 1 and answer[0].get("status") in ("choose", "unsure", "none_apply")
        else "ranked"
    )
    names = [entry["name"] for entry in catalog.entries(answer)]
    return {
        "rank": names.index(name) + 1 if name in names else None,
        "shape": shape,
        "pool": len(names),
    }


def operations(engines: tuple[str, ...]) -> list[dict[str, Any]]:
    """Every operation with the numbers that matter for tuning: can it be found.

    Asked twice, because both answers are needed to know what to fix. **Words
    alone** is the hardest case and the one that says whether the entry's text
    carries its own meaning. **With the facets a caller knows** is the case that
    actually happens, and the one the design promises: narrowing, not ranking,
    is what guarantees delivery.

    The query is the caller-phrased one where the degradation test has written
    it, and the entry's own advertised example otherwise — found only by its own
    wording is not found, so the row says which was used.
    """
    exposed = set(tool_names())
    rows = []
    for op in catalog.OPERATIONS:
        query = CALLER_QUERIES.get(op["name"])
        source = "caller's words"
        if not query:
            examples = op.get("examples") or []
            query = examples[0]["goal"] if examples else op["summary"]
            source = "its own example" if examples else "its own summary"
        facets = discovery_report.facets_for(op["name"], DECLARED)
        probes = {
            engine: {
                "bare": _probe(query, engine, {}, op["name"]),
                "faceted": _probe(query, engine, facets, op["name"]),
            }
            for engine in engines
        }
        rows.append(
            {
                "name": op["name"],
                "category": op["category"],
                "produces": op["produces"],
                "status": op["status"],
                "inputs": op["applicability"]["inputs"],
                "dataset_inputs": op["applicability"].get("dataset_inputs"),
                "exposed": op.get("tool") in exposed,
                "summary": op["summary"],
                "distinguishes": op.get("distinguishes", ""),
                "query": query,
                "query_source": source,
                "declared": facets,
                "probes": probes,
            }
        )
    return rows


def degradation(sizes: tuple[int, ...]) -> list[dict[str, Any]]:
    """found@1 and found@3 against catalog size, BM25, in the caller's words.

    The same measurement the degradation test prints and nobody reads, drawn as
    a curve. Three seeds per query per size, deterministic.
    """
    curve = []
    for size in sizes:
        hits = at_three = trials = 0
        for expected, query in CALLER_QUERIES.items():
            for seed in (1, 2, 3):
                top = _lexical_top(query, _subset(expected, size, seed))
                trials += 1
                hits += bool(top) and top[0] == expected
                at_three += expected in top
        curve.append(
            {
                "size": size,
                "found_at_1": round(100 * hits / trials),
                "found_at_3": round(100 * at_three / trials),
            }
        )
    return curve


def quality() -> dict[str, Any]:
    """Everything `discovery_report` computes, plus the curve."""
    queries = discovery_report.load()
    answerable = discovery_report.answerable(queries)
    agree = discovery_report.agreement(queries)
    lexical = discovery_report.ablation(answerable, engine="lexical")
    try:
        vector = discovery_report.ablation(answerable, engine="vector")
    except Exception as failure:  # noqa: BLE001 - no model, no column, said so
        vector = []
        print(f"note: the embedding engine could not be loaded ({failure}); the page "
              "will carry the BM25 column alone", file=sys.stderr)
    return {
        "requests": len(queries),
        "answerable": len(answerable),
        "agreement_all": list(agree["all"]),
        "agreement_answerable": list(agree["answerable"]),
        "ablation_lexical": lexical,
        "ablation_vector": vector,
        "degradation": degradation((10, 20, 30, 40, len(catalog.OPERATIONS))),
    }


def argleton(path: Path | None) -> dict[str, Any]:
    """The suite's traps and what each engine does with them.

    From a checkout when one is given, because the interesting part — which
    family an engine fails and how loudly — is per-probe and does not fit in a
    citation. Without a checkout, the vendored summary, and the page says which
    of the two it is showing rather than quietly degrading.
    """
    vendored = json.loads(
        (ROOT / "docs" / "argleton-run.json").read_text(encoding="utf-8")
    )
    out: dict[str, Any] = {
        "source": "vendored citation",
        "run": vendored["run"],
        "spec_commit": vendored["spec_commit"],
        "traps_run": vendored["traps_run"],
        "families": vendored["families"],
        "url": vendored["url"],
        "headline": {
            "mapsmith_silent_error_rate": vendored["mapsmith_silent_error_rate"],
            "mapsmith_completion_rate": vendored["mapsmith_completion_rate"],
            "naive_silent_error_rate": vendored["naive_silent_error_rate"],
        },
        "traps": [],
        "adapters": [],
    }
    if path is None or not (path / "traps").is_dir():
        return out

    for probe in sorted((path / "traps").glob("*/probe.toml")):
        spec = tomllib.loads(probe.read_text(encoding="utf-8"))
        out["traps"].append(
            {
                "id": spec.get("id", probe.parent.name),
                "family": spec.get("family", ""),
                "title": spec.get("title", ""),
                "surface": spec.get("surface", []),
                "truth_kind": spec.get("truth", {}).get("kind", ""),
            }
        )

    latest = path / "results" / "LATEST"
    run_dir = None
    if latest.exists():
        run_dir = path / "results" / latest.read_text(encoding="utf-8").strip()
    if run_dir and run_dir.is_dir():
        out["source"] = "checkout"
        out["run"] = run_dir.name
        for result in sorted(run_dir.glob("adapters-*.json")):
            data = json.loads(result.read_text(encoding="utf-8"))
            out["adapters"].append(
                {
                    "name": result.stem.replace("adapters-", ""),
                    "adapter": data["adapter"],
                    "system": data["system"],
                    "silent_error_rate": data["silent_error_rate"],
                    "completion_rate": data["completion_rate"],
                    "traps_run": data["traps_run"],
                    "unsupported": data["unsupported"],
                    "verdict_counts": data["verdict_counts"],
                    "by_family": data["by_family"],
                    "per_probe": [
                        {
                            "probe_id": probe["probe_id"],
                            "population": probe["population"],
                            "family": probe["family"],
                            "verdict": probe["verdict"],
                        }
                        for probe in data.get("per_probe", [])
                    ],
                }
            )
    return out


def recorded_cases(path: Path | None) -> list[dict[str, Any]]:
    """The discovery log, one entry per search, unattributed searches included.

    A search nothing followed is kept rather than dropped: it is a request the
    catalog did not serve, which is the more interesting half.
    """
    if path is None or not path.exists():
        return []
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        cases.append(
            {
                "at": record.get("at"),
                "query": record.get("query", ""),
                "declared": record.get("declared", {}),
                "engine": record.get("engine"),
                "status": record.get("status"),
                "delivered": record.get("delivered", []),
                "chose": record.get("chose"),
                "position": record.get("position_of_choice"),
                "searches_ago": record.get("searches_ago"),
            }
        )
    return cases


#: Labellers whose answers are history rather than a proposal: the two the
#: benchmark was built with, and the human, whose answer is the measurement.
_NOT_A_PROPOSAL = {"label_claude", "label_gemini", "label_human", "label"}


def _proposer(query: dict[str, Any]) -> str | None:
    """The name of a third labeller who answered this request, if there is one.

    Discovered from the keys rather than hard-coded, so adding a fourth opinion
    needs no change here — and so that nothing has to remember which model was
    used on which day.
    """
    for key in sorted(query):
        if (
            key.startswith("label_")
            and key not in _NOT_A_PROPOSAL
            and not key.endswith(("_also", "_note", "_model"))
            and query[key]
        ):
            return key[len("label_") :]
    return None


def disagreements(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The requests the two labellers answered differently.

    Both-unanswerable pairs are excluded (agreement on "no" is agreement) and so
    are pairs where they named the same operation. What is left is the 30% that
    D-054 says needs somebody who has done the job: either one of them is wrong,
    or both answers are defensible and the request has no single right answer —
    and those two cases look identical from here.
    """
    names = {op["name"] for op in catalog.OPERATIONS}
    split = []
    for q in queries:
        claude, gemini = q.get("label_claude"), q.get("label_gemini")
        if not claude or not gemini or claude == gemini:
            continue
        stale = [
            name
            for name in (claude, gemini)
            if name not in names and name not in discovery_report.NOT_AN_OPERATION
        ]
        answer = catalog.search(q["query"], limit=10, engine="lexical")
        split.append(
            {
                "query": q["query"],
                "scenario": q.get("scenario", ""),
                "claude": claude,
                "gemini": gemini,
                "stale": stale,
                # The answer already recorded in the repository, if somebody has
                # given one. Without this the loop is one-way: answers go from
                # the browser into `discovery_queries.json` through
                # `ingest_answers.py`, and the next page generated asked the same
                # questions again as though nobody had ever answered — on a
                # different browser, or after clearing site data, the work looked
                # undone because the page had no way to know it was not.
                "human": q.get("label_human"),
                # A third labeller's proposal, with its reasoning. Not an answer:
                # `label_human` stays the only thing any figure is measured
                # against. It is here because reading somebody's reasoning turns
                # "think about this request from scratch" into "confirm or
                # correct", and fifty questions is the difference between half an
                # hour and an afternoon.
                "proposed": {
                    "by": name,
                    "label": q[f"label_{name}"],
                    "also": q.get(f"label_{name}_also") or [],
                    "note": q.get(f"label_{name}_note") or "",
                }
                if (name := _proposer(q))
                else None,
                "ranked": [entry["name"] for entry in catalog.entries(answer)][:10],
            }
        )
    return split


def history(path: Path, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Append this generation to the series and return the whole series.

    A dashboard that only shows now cannot answer the question worth asking —
    did the change help. Identical consecutive rows are dropped so that
    regenerating the page five times does not manufacture a trend.
    """
    series: list[dict[str, Any]] = []
    if path.exists():
        try:
            series = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            series = []
    comparable = {k: v for k, v in snapshot.items() if k != "at"}
    if not series or {k: v for k, v in series[-1].items() if k != "at"} != comparable:
        series.append(snapshot)
        path.write_text(json.dumps(series, indent=1) + "\n", encoding="utf-8")
    return series


def collect(log: Path | None, suite: Path | None, history_path: Path) -> dict[str, Any]:
    engines = ("lexical", "vector")
    try:
        catalog.search("warm up the ranker", limit=1, engine="vector")
    except Exception:  # noqa: BLE001 - no model, one engine
        engines = ("lexical",)
    queries = discovery_report.load()
    ops = operations(engines)
    measured = quality()
    suite_data = argleton(suite)
    best = engines[-1]
    reachable = [row for row in ops if row["probes"][best]["faceted"]["rank"]]
    top3 = [row for row in reachable if row["probes"][best]["faceted"]["rank"] <= 3]
    snapshot = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit(),
        "version": __version__,
        "tools": len(tool_names()),
        "operations": len(ops),
        "reachable": len(reachable),
        "top3": len(top3),
        "traps": suite_data["traps_run"],
        "families": suite_data["families"],
        "found_at_3_bare": measured["ablation_lexical"][0]["found_at_3"],
        "found_at_3_faceted": measured["ablation_lexical"][-2]["found_at_3"],
        "delivered": measured["ablation_lexical"][-2]["delivered"],
        "mapsmith_silent_error_rate": suite_data["headline"][
            "mapsmith_silent_error_rate"
        ],
    }
    return {
        "generated": snapshot["at"],
        "version": __version__,
        "commit": snapshot["commit"],
        "engines": list(engines),
        "tools": tool_names(),
        "operations": ops,
        "quality": measured,
        "argleton": suite_data,
        "recorded": recorded_cases(log),
        "disagreements": disagreements(queries),
        "catalog": [
            {"name": op["name"], "summary": op["summary"]} for op in catalog.OPERATIONS
        ],
        "history": history(history_path, snapshot),
        "log_path": str(log) if log else None,
        "suite_path": str(suite) if suite else None,
    }


def build(log: Path | None, suite: Path | None, history_path: Path) -> str:
    blob = json.dumps(collect(log, suite, history_path), ensure_ascii=False)
    # `</script>` inside a JSON string would close the tag early. Escaping the
    # angle bracket is enough and keeps the JSON valid.
    return TEMPLATE.replace("__DATA__", blob.replace("<", "\\u003c"))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Build the MapSmith dashboard as one self-contained HTML file."
    )
    parser.add_argument("--log", type=Path, default=None,
                        help="a file written by MAPSMITH_DISCOVERY_LOG")
    parser.add_argument("--argleton", type=Path, default=None,
                        help="a checkout of github.com/argleton/argleton")
    parser.add_argument("--out", type=Path, default=Path("dashboard.html"))
    parser.add_argument("--history", type=Path, default=None,
                        help="where the series lives (default: <out>.history.json)")
    args = parser.parse_args(argv)

    if args.log and not args.log.exists():
        print(f"no log at {args.log}", file=sys.stderr)
        return 1
    if args.argleton and not (args.argleton / "traps").is_dir():
        print(f"{args.argleton} does not look like an Argleton checkout "
              "(no traps/ directory); falling back to the vendored citation",
              file=sys.stderr)
        args.argleton = None
    history_path = args.history or args.out.with_suffix(".history.json")
    args.out.write_text(build(args.log, args.argleton, history_path), encoding="utf-8")
    print(f"{args.out} ({args.out.stat().st_size // 1024} KB) — open it in a browser")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MapSmith — dashboard</title>
<style>
:root {
  --bg: #fbfaf8; --panel: #ffffff; --ink: #1a1a1a; --quiet: #6b6b6b;
  --line: #e2ded8; --accent: #1f6f5c; --accent2: #4a6fa5; --warn: #a8541b;
  --bad: #a33; --good: #2e7d4f; --third: #8a5a9e; --grid: #efece7;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16181a; --panel: #1e2124; --ink: #e8e6e3; --quiet: #9a9a9a;
    --line: #33383d; --accent: #63b39c; --accent2: #7fa3d8; --warn: #d9925c;
    --bad: #e07a7a; --good: #6fc08f; --third: #c194d8; --grid: #272b2f;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15.5px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
nav {
  position: sticky; top: 0; z-index: 5; background: var(--bg);
  border-bottom: 1px solid var(--line); padding: .6rem 1.25rem;
  display: flex; gap: 1rem; flex-wrap: wrap; font-size: .88rem;
}
nav a { color: var(--quiet); text-decoration: none; }
nav a:hover { color: var(--accent); }
nav .who { margin-left: auto; color: var(--quiet); font-size: .8rem; }
main { max-width: 64rem; margin: 0 auto; padding: 1.5rem 1.25rem 6rem; }
h1 { font-size: 1.55rem; margin: .5rem 0 .3rem; letter-spacing: -.01em; }
h2 { font-size: 1.2rem; margin: 3rem 0 .4rem; scroll-margin-top: 4rem; }
h3 { font-size: .95rem; margin: 1.6rem 0 .4rem; }
p { margin: .5rem 0; }
.quiet { color: var(--quiet); font-size: .88rem; }
code, .mono { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: .86em; }
.panel {
  background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 1rem 1.15rem; margin: 1rem 0;
}
table { border-collapse: collapse; width: 100%; font-size: .88rem; }
th, td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { font-weight: 600; color: var(--quiet); font-size: .76rem; text-transform: uppercase;
     letter-spacing: .04em; cursor: pointer; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.bad td { background: color-mix(in srgb, var(--bad) 9%, transparent); }
.scroll { overflow-x: auto; }
.tally { display: flex; flex-wrap: wrap; gap: 1.4rem; margin: .5rem 0; }
.tally div { min-width: 6.5rem; }
.tally .big { font-size: 1.6rem; font-variant-numeric: tabular-nums; line-height: 1.15; }
.tally .cap { font-size: .76rem; color: var(--quiet); }
.case { border-top: 1px solid var(--line); padding: .9rem 0; }
.q { font-size: 1rem; margin: 0 0 .3rem; }
.meta { font-size: .78rem; color: var(--quiet); margin-bottom: .45rem; }
.chips { display: flex; flex-wrap: wrap; gap: .3rem; margin: .35rem 0; }
.chip {
  border: 1px solid var(--line); background: transparent; color: var(--ink);
  border-radius: 999px; padding: .18rem .55rem; font-size: .8rem; cursor: pointer;
  font-family: ui-monospace, Consolas, monospace;
}
.chip:hover { border-color: var(--accent); }
.chip.ran { border-color: var(--warn); }
.chip.picked { background: var(--accent); border-color: var(--accent); color: #fff; }
.chip.claude::after, .chip.gemini::after, .chip.recorded::after {
  content: "claude"; font-size: .72em; color: var(--quiet); margin-left: .3rem; }
.chip.gemini::after { content: "gemini"; }
/* An answer a person already gave and that is now in the repository, so the
   page stops asking as though nobody had. */
.chip.recorded::after { content: "recorded"; }
.chip.recorded { border-color: var(--accent); }
.chip.proposed::after { content: "proposed"; font-size: .72em; color: var(--quiet); margin-left: .3rem; }
details.proposed { margin: .35rem 0 .1rem; font-size: .92em; }
details.proposed summary { cursor: pointer; color: var(--quiet); }
details.proposed .reason { margin: .3rem 0 0; padding-left: .8rem;
  border-left: 2px solid var(--line); color: var(--quiet); }
/* A second answer somebody accepts, not the one they would choose. */
.chip.also { border-style: dashed; border-color: var(--accent); }
.chip.also::after { content: "also"; font-size: .72em; color: var(--quiet); margin-left: .3rem; }
textarea.why { width: 100%; margin-top: .4rem; font-size: .9em; }
textarea.why.missing { border-color: var(--warn); }
.case.answered { opacity: .72; }
.case.answered:hover, .case.answered:focus-within { opacity: 1; }
.chip.picked::after { color: rgba(255,255,255,.8); }
select, input, textarea {
  font: inherit; background: var(--panel); color: var(--ink);
  border: 1px solid var(--line); border-radius: 6px; padding: .28rem .45rem;
}
textarea { width: 100%; min-height: 10rem; font-family: ui-monospace, Consolas, monospace;
  font-size: .78rem; }
button.action { font: inherit; background: var(--accent); color: #fff; border: 0;
  border-radius: 6px; padding: .35rem .85rem; cursor: pointer; }
button.ghost { background: transparent; color: var(--quiet); border: 1px solid var(--line); }
.bar { display: flex; gap: .55rem; align-items: center; flex-wrap: wrap; margin: .7rem 0; }
.legend { display: flex; gap: 1rem; flex-wrap: wrap; font-size: .8rem; color: var(--quiet);
  margin: .3rem 0 .6rem; }
.legend i { display: inline-block; width: .7rem; height: .7rem; border-radius: 2px;
  margin-right: .3rem; }
.pill { font-size: .74rem; border: 1px solid var(--line); border-radius: 999px;
  padding: .05rem .45rem; color: var(--quiet); white-space: nowrap; }
.pill.no { border-color: var(--bad); color: var(--bad); }
.pill.yes { border-color: var(--good); color: var(--good); }
svg text { fill: var(--quiet); font-size: 11px; }
svg .grid { stroke: var(--grid); }
.empty { color: var(--quiet); font-style: italic; }
</style>
</head>
<body>
<nav>
  <a href="#overview">Overview</a>
  <a href="#operations">Operations</a>
  <a href="#quality">Search quality</a>
  <a href="#traps">Traps</a>
  <a href="#answer">Answer</a>
  <a href="#trend">Trend</a>
  <span class="who" id="who"></span>
</nav>
<main>

<h1>MapSmith — what it is, how well it is found, what it gets wrong</h1>
<p class="quiet" id="subtitle"></p>

<div class="panel">
  <p><strong>A snapshot, and answering it is not wasted when it ages.</strong> Built from
  this checkout at the moment above; new operations, new traps and newly recorded searches
  appear when it is generated again. Regenerating keeps every answer you have given —
  answers are stored against the text of each question, never its position.</p>
  <p class="mono" id="regen"></p>
  <p class="quiet">Everything is local: your queries are in this file, nothing is uploaded,
  no script is fetched, and it works offline.</p>
</div>

<h2 id="overview">Overview</h2>
<div class="panel">
  <div class="tally" id="overview-tally"></div>
  <p class="quiet" id="overview-note"></p>
</div>

<h2 id="operations">Operations</h2>
<p>Capability has no ceiling; the list an agent chooses between does. What matters per entry
is not that it exists but that a caller reaches it — an operation nothing finds does not
exist. The query used is the caller-phrased one where the degradation test has written it,
and the entry's own advertised example otherwise; found only by its own wording is not
found, so the column says which. Two columns because both answers are needed: <em>words
alone</em> says whether the entry's text carries its own meaning, <em>with facets</em> is the
case that actually happens and the one the design promises. <em>Declined</em> is neither
— it is the refusal gate firing because the two rankers shared nothing, and drawing it as
a miss would invent broken operations.</p>
<div class="panel">
  <div class="tally" id="ops-tally"></div>
  <div id="ops-by-category"></div>
</div>
<div class="panel">
  <div class="bar">
    <input type="search" id="ops-filter" placeholder="filter by name, family, summary…"
           style="flex:1; min-width:14rem">
    <label class="quiet"><input type="checkbox" id="ops-only-bad"> only the unreachable</label>
  </div>
  <div class="scroll"><table id="ops-table"></table></div>
</div>

<h2 id="quality">Search quality</h2>
<p>Over the <span id="q-answerable">–</span> requests both model labellers placed on an
operation that still exists. <em>Delivered</em> is not an accuracy figure: below the choose
threshold every survivor is handed over, so it measures whether narrowing ever drops the
answer — which is the property the design rests on, and the only one at 100%.</p>
<div class="panel">
  <div class="legend" id="ablation-legend"></div>
  <div id="ablation-chart"></div>
  <div class="scroll"><table id="ablation-table"></table></div>
</div>
<div class="panel">
  <h3 style="margin-top:0">What happens as the catalog grows</h3>
  <p class="quiet">BM25 alone, in the caller's words, against a catalog subsampled to each
  size — three deterministic draws per query. This is the curve the embedding engine became
  a dependency for, and the reason the facets rather than the ranker carry the guarantee.</p>
  <div class="legend" id="degradation-legend"></div>
  <div id="degradation-chart"></div>
</div>

<h2 id="traps">Traps</h2>
<p id="traps-intro"></p>
<div class="panel">
  <div class="tally" id="traps-tally"></div>
  <div class="legend" id="adapters-legend"></div>
  <div id="adapters-chart"></div>
</div>
<div class="panel" id="family-panel">
  <h3 style="margin-top:0">Which family each engine walks into</h3>
  <p class="quiet">One column per family, one row per engine. A filled cell is a silent
  error: a plausible, well-formed, confidently wrong answer that nothing raised.</p>
  <div class="scroll"><table id="family-table"></table></div>
</div>
<div class="panel" id="trap-panel">
  <div class="scroll"><table id="traps-table"></table></div>
</div>

<h2 id="answer">Answer the open questions</h2>
<p>Every published percentage rests on 155 requests labelled by two language models. Where
they name the same operation the row is as good as it gets without users. Where they do not,
one is wrong <em>or</em> both are defensible — and those look identical from here. This is
the part no machine in this repository can do.</p>
<div class="panel">
  <div class="tally">
    <div><div class="big" id="d-total">–</div><div class="cap">split rows</div></div>
    <div><div class="big" id="d-done">–</div><div class="cap">you answered</div></div>
    <div><div class="big" id="d-claude">–</div><div class="cap">you agree with claude</div></div>
    <div><div class="big" id="d-gemini">–</div><div class="cap">you agree with gemini</div></div>
    <div><div class="big" id="d-neither">–</div><div class="cap">neither of them</div></div>
  </div>
  <p class="quiet" id="d-note"></p>
</div>
<div id="disagreements"></div>

<h3>Recorded from use</h3>
<p id="rec-intro"></p>
<div class="panel" id="rec-panel">
  <div class="tally">
    <div><div class="big" id="r-total">–</div><div class="cap">searches</div></div>
    <div><div class="big" id="r-ran">–</div><div class="cap">a run followed</div></div>
    <div><div class="big" id="r-first">–</div><div class="cap">chosen was ranked 1st</div></div>
    <div><div class="big" id="r-three">–</div><div class="cap">in the top three</div></div>
    <div><div class="big" id="r-labelled">–</div><div class="cap">you answered</div></div>
  </div>
  <p class="quiet" id="r-note"></p>
</div>
<div id="recorded"></div>

<h3>Take your answers out</h3>
<div class="bar">
  <button class="action" id="export">Show the JSON</button>
  <button class="ghost" id="copy">Copy</button>
  <button class="ghost" id="forget">Forget my answers</button>
  <span id="saved" class="quiet"></span>
</div>
<textarea id="out" spellcheck="false" placeholder="nothing answered yet"></textarea>

<h2 id="trend">Trend</h2>
<p class="quiet">One row per generation of this page, kept beside it. Identical consecutive
rows are dropped, so regenerating five times does not manufacture a trend.</p>
<div class="panel">
  <div class="legend" id="trend-legend"></div>
  <div id="trend-chart"></div>
  <div class="scroll"><table id="trend-table"></table></div>
</div>

</main>

<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const KEY = "mapsmith-discovery-labels-v1";
const ENGINE = DATA.engines[DATA.engines.length - 1];

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
function pct(part, whole) { return whole ? Math.round(100 * part / whole) + "%" : "–"; }
function probe(op, kind) { return op.probes[ENGINE][kind]; }
/* Three outcomes, kept apart on purpose: a position, an answer that did not
   contain this entry, and no answer at all because the two rankers shared
   nothing and the search declined. Only the middle one is the entry's fault. */
function rankCell(result) {
  const cell = el("td", "num");
  if (result.rank) {
    cell.appendChild(el("span", "pill " + (result.rank <= 3 ? "yes" : ""), "#" + result.rank));
  } else if (result.shape === "unsure") {
    cell.appendChild(el("span", "pill", "declined"));
    cell.title = "the two rankers shared nothing, so the search asked a question "
      + "instead of answering — the refusal gate, not this entry";
  } else if (result.shape === "none_apply") {
    cell.appendChild(el("span", "pill no", "no candidates"));
  } else {
    cell.appendChild(el("span", "pill no", "not found"));
    cell.title = "the answer was given and this entry was not in it — " + result.pool
      + " candidates came back";
  }
  return cell;
}
function tally(host, items) {
  host.innerHTML = "";
  for (const [value, caption, title] of items) {
    const box = el("div");
    if (title) box.title = title;
    box.appendChild(el("div", "big", value));
    box.appendChild(el("div", "cap", caption));
    host.appendChild(box);
  }
}
function legend(host, series) {
  host.innerHTML = "";
  for (const s of series) {
    const item = el("span");
    const swatch = el("i");
    swatch.style.background = s.color;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(s.name));
    host.appendChild(item);
  }
}

/* ---- charts, hand-drawn: no library reaches this page ---- */
const NS = "http://www.w3.org/2000/svg";
function svg(width, height) {
  const node = document.createElementNS(NS, "svg");
  node.setAttribute("viewBox", "0 0 " + width + " " + height);
  node.setAttribute("width", "100%");
  node.style.maxHeight = height + "px";
  return node;
}
function node(name, attrs, text) {
  const n = document.createElementNS(NS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text !== undefined) n.textContent = text;
  return n;
}
function barChart(host, groups, series, opts) {
  opts = opts || {};
  const W = 880, H = opts.height || 240, L = 44, R = 12, T = 12, B = 46;
  const max = opts.max || Math.max(1, ...series.flatMap(s => s.values));
  const chart = svg(W, H);
  for (let i = 0; i <= 4; i++) {
    const y = T + (H - T - B) * i / 4;
    chart.appendChild(node("line", {x1: L, x2: W - R, y1: y, y2: y, class: "grid"}));
    chart.appendChild(node("text", {x: 4, y: y + 4},
      Math.round(max * (1 - i / 4)) + (opts.suffix || "")));
  }
  const slot = (W - L - R) / groups.length;
  const bw = Math.min(28, (slot - 10) / series.length);
  groups.forEach((label, gi) => {
    series.forEach((s, si) => {
      const value = s.values[gi];
      if (value === null || value === undefined) return;
      const h = (H - T - B) * value / max;
      const x = L + gi * slot + (slot - bw * series.length) / 2 + si * bw;
      const rect = node("rect", {x: x, y: H - B - h, width: bw - 2, height: Math.max(1, h),
                                 fill: s.color, rx: 2});
      rect.appendChild(node("title", {}, s.name + ": " + value + (opts.suffix || "")));
      chart.appendChild(rect);
      if (opts.values !== false && bw > 16) {
        chart.appendChild(node("text",
          {x: x + bw / 2 - 1, y: H - B - h - 4, "text-anchor": "middle"}, value));
      }
    });
    for (const [li, line] of String(label).split("\n").entries()) {
      chart.appendChild(node("text",
        {x: L + gi * slot + slot / 2, y: H - B + 16 + li * 12, "text-anchor": "middle"}, line));
    }
  });
  host.innerHTML = "";
  host.appendChild(chart);
}
function lineChart(host, xs, series, opts) {
  opts = opts || {};
  const W = 880, H = opts.height || 220, L = 44, R = 12, T = 12, B = 34;
  const max = opts.max || Math.max(1, ...series.flatMap(s => s.values.filter(v => v != null)));
  const chart = svg(W, H);
  for (let i = 0; i <= 4; i++) {
    const y = T + (H - T - B) * i / 4;
    chart.appendChild(node("line", {x1: L, x2: W - R, y1: y, y2: y, class: "grid"}));
    chart.appendChild(node("text", {x: 4, y: y + 4},
      Math.round(max * (1 - i / 4)) + (opts.suffix || "")));
  }
  const step = xs.length > 1 ? (W - L - R) / (xs.length - 1) : 0;
  const px = i => L + i * step + (xs.length > 1 ? 0 : (W - L - R) / 2);
  const py = v => H - B - (H - T - B) * v / max;
  for (const s of series) {
    const points = s.values.map((v, i) => v == null ? null : px(i) + "," + py(v))
                           .filter(Boolean).join(" ");
    chart.appendChild(node("polyline",
      {points: points, fill: "none", stroke: s.color, "stroke-width": 2}));
    s.values.forEach((v, i) => {
      if (v == null) return;
      const dot = node("circle", {cx: px(i), cy: py(v), r: 3, fill: s.color});
      dot.appendChild(node("title", {}, s.name + " " + xs[i] + ": " + v + (opts.suffix || "")));
      chart.appendChild(dot);
    });
  }
  xs.forEach((label, i) => {
    if (xs.length > 12 && i % Math.ceil(xs.length / 12) !== 0 && i !== xs.length - 1) return;
    chart.appendChild(node("text", {x: px(i), y: H - B + 16, "text-anchor": "middle"},
      String(label)));
  });
  host.innerHTML = "";
  host.appendChild(chart);
}

/* ---- overview ---- */
function drawOverview() {
  const q = DATA.quality, a = DATA.argleton;
  const reachable = DATA.operations.filter(o => probe(o, "faceted").rank);
  document.getElementById("who").textContent =
    "v" + DATA.version + (DATA.commit ? " · " + DATA.commit : "");
  document.getElementById("subtitle").textContent =
    "generated " + DATA.generated + " · ranked by " + DATA.engines.join(" and ")
    + " · " + DATA.recorded.length + " recorded searches";
  document.getElementById("regen").textContent =
    "python benchmarks/dashboard.py"
    + (DATA.log_path ? " --log " + DATA.log_path : "")
    + (DATA.suite_path ? " --argleton " + DATA.suite_path : "");
  tally(document.getElementById("overview-tally"), [
    [DATA.tools.length, "tools exposed", "what an agent chooses between — this is the count with a ceiling"],
    [DATA.operations.length, "operations in the catalog", "capability count, which has no ceiling"],
    [pct(reachable.length, DATA.operations.length), "reachable",
     "in the answer for their own request, with the facets a caller would declare"],
    [a.traps_run, "traps in the suite"],
    [a.families, "failure families"],
    [Math.round(100 * a.headline.mapsmith_silent_error_rate) + "%", "MapSmith silent errors"],
    [Math.round(100 * a.headline.naive_silent_error_rate) + "%", "naive engine silent errors"],
    [Math.round(100 * q.agreement_answerable[0] / q.agreement_answerable[1]) + "%",
     "the two labellers agree", "the ceiling: this is what a right answer is worth arguing about"],
  ]);
  document.getElementById("overview-note").textContent =
    "The last figure is the one to read the others against. Two independent labellers agree "
    + "with each other on " + Math.round(100 * q.agreement_answerable[0] / q.agreement_answerable[1])
    + "% of the answerable requests, so a ranking that agrees with one of them more than that "
    + "is not more correct — it is fitting a preference.";
}

/* ---- operations ---- */
function drawOperations() {
  const ops = DATA.operations;
  const reachable = ops.filter(o => probe(o, "faceted").rank);
  const top3 = reachable.filter(o => probe(o, "faceted").rank <= 3);
  const bareOk = ops.filter(o => probe(o, "bare").rank);
  const declined = ops.filter(o => probe(o, "bare").shape === "unsure");
  const exposed = ops.filter(o => o.exposed);
  tally(document.getElementById("ops-tally"), [
    [ops.length, "operations"],
    [exposed.length, "with a tool of their own"],
    [ops.filter(o => o.status !== "available").length, "planned, not built"],
    [bareOk.length, "found by words alone",
     "the hardest case: no facets declared, phrased the way a caller phrases it"],
    [declined.length, "where the search declined",
     "words alone, the two rankers shared nothing, so it asked a question instead of "
     + "answering — the refusal gate firing, not a broken entry"],
    [top3.length, "top three once facets are declared"],
    [ops.length - reachable.length, "unreachable even with facets",
     "the tuning list: nothing a caller can say brings these back"],
  ]);

  const families = {};
  for (const op of ops) families[op.category] = (families[op.category] || 0) + 1;
  const names = Object.keys(families).sort((a, b) => families[b] - families[a]);
  const unreachableBy = {};
  for (const op of ops) {
    if (!probe(op, "faceted").rank) {
      unreachableBy[op.category] = (unreachableBy[op.category] || 0) + 1;
    }
  }
  const opsLegend = el("div", "legend");
  document.getElementById("ops-by-category").before(opsLegend);
  legend(opsLegend, [{name: "operations", color: "var(--accent)"},
                     {name: "unreachable even with facets", color: "var(--bad)"}]);
  barChart(document.getElementById("ops-by-category"), names,
    [{name: "operations", color: "var(--accent)", values: names.map(n => families[n])},
     {name: "not found", color: "var(--bad)", values: names.map(n => unreachableBy[n] || 0)}],
    {height: 210});

  const table = document.getElementById("ops-table");
  const filter = document.getElementById("ops-filter");
  const onlyBad = document.getElementById("ops-only-bad");
  let sortBy = "faceted", ascending = false;
  const columns = [
    ["name", "operation", o => o.name],
    ["category", "family", o => o.category],
    ["produces", "produces", o => o.produces],
    ["exposed", "tool", o => o.exposed ? 1 : 0],
    ["bare", "words alone", o => probe(o, "bare").rank || 999],
    ["faceted", "with facets", o => probe(o, "faceted").rank || 999],
    ["query_source", "asked as", o => o.query_source],
  ];
  function draw() {
    const needle = filter.value.trim().toLowerCase();
    let rows = ops.filter(o =>
      !needle || (o.name + " " + o.category + " " + o.summary).toLowerCase().includes(needle));
    if (onlyBad.checked) {
      rows = rows.filter(o => !probe(o, "faceted").rank || probe(o, "faceted").rank > 3);
    }
    const key = columns.find(c => c[0] === sortBy)[2];
    rows = rows.slice().sort((a, b) => {
      const x = key(a), y = key(b);
      return (x > y ? 1 : x < y ? -1 : 0) * (ascending ? 1 : -1);
    });
    table.innerHTML = "";
    const head = el("tr");
    for (const [id, label] of columns) {
      const th = el("th", ["bare", "faceted", "exposed"].includes(id) ? "num" : "", label);
      th.onclick = () => { ascending = sortBy === id ? !ascending : true; sortBy = id; draw(); };
      head.appendChild(th);
    }
    table.appendChild(head);
    for (const op of rows) {
      const tr = el("tr", probe(op, "faceted").rank ? "" : "bad");
      const first = el("td");
      first.appendChild(el("div", "mono", op.name));
      first.appendChild(el("div", "quiet", op.summary));
      tr.appendChild(first);
      tr.appendChild(el("td", "", op.category));
      tr.appendChild(el("td", "", op.produces));
      const tool = el("td", "num");
      tool.appendChild(el("span", "pill " + (op.exposed ? "yes" : ""),
        op.exposed ? "exposed" : "catalog only"));
      tr.appendChild(tool);
      const bare = rankCell(probe(op, "bare"));
      bare.title = (bare.title ? bare.title + " · " : "") + op.query;
      tr.appendChild(bare);
      const faceted = rankCell(probe(op, "faceted"));
      faceted.title = (faceted.title ? faceted.title + " · " : "") + "declared "
        + JSON.stringify(op.declared);
      tr.appendChild(faceted);
      tr.appendChild(el("td", "quiet", op.query_source));
      table.appendChild(tr);
    }
  }
  filter.oninput = draw;
  onlyBad.onchange = draw;
  draw();
}

/* ---- search quality ---- */
function drawQuality() {
  const q = DATA.quality;
  document.getElementById("q-answerable").textContent = q.answerable;
  const groups = q.ablation_lexical.map(r => r.declared.replace(/^\+ /, "+\n"));
  const series = [
    {name: "BM25, found@3", color: "var(--accent2)",
     values: q.ablation_lexical.map(r => r.found_at_3)},
  ];
  if (q.ablation_vector.length) {
    series.push({name: "embeddings, found@3", color: "var(--accent)",
                 values: q.ablation_vector.map(r => r.found_at_3)});
  }
  series.push({name: "right answer delivered", color: "var(--third)",
               values: q.ablation_lexical.map(r => r.delivered)});
  legend(document.getElementById("ablation-legend"), series);
  barChart(document.getElementById("ablation-chart"), groups, series,
           {max: 100, suffix: "%", height: 260});

  const table = document.getElementById("ablation-table");
  table.innerHTML = "";
  const head = el("tr");
  for (const label of ["what the caller declares", "candidates left", "BM25 @3",
                       "embeddings @3", "delivered"]) {
    head.appendChild(el("th", label === "what the caller declares" ? "" : "num", label));
  }
  table.appendChild(head);
  q.ablation_lexical.forEach((row, i) => {
    const vector = q.ablation_vector[i];
    const tr = el("tr");
    tr.appendChild(el("td", "", row.declared));
    tr.appendChild(el("td", "num", String(row.candidates)));
    tr.appendChild(el("td", "num", row.found_at_3 + "%"));
    tr.appendChild(el("td", "num", vector ? vector.found_at_3 + "%" : "–"));
    tr.appendChild(el("td", "num", row.delivered + "%"));
    table.appendChild(tr);
  });

  const curve = q.degradation;
  const dseries = [
    {name: "found@1", color: "var(--warn)", values: curve.map(p => p.found_at_1)},
    {name: "found@3", color: "var(--accent2)", values: curve.map(p => p.found_at_3)},
  ];
  legend(document.getElementById("degradation-legend"), dseries);
  lineChart(document.getElementById("degradation-chart"),
            curve.map(p => p.size + " ops"), dseries, {max: 100, suffix: "%"});
}

/* ---- traps ---- */
function drawTraps() {
  const a = DATA.argleton;
  document.getElementById("traps-intro").innerHTML =
    "Argleton plants a trap with a truth derived by hand and watches who walks in. A "
    + "<em>silent error</em> is a plausible, well-formed, confidently wrong answer that "
    + "nothing raised — the failure mode this whole project is about. Run <code>"
    + a.run + "</code>, spec <code>" + a.spec_commit + "</code>"
    + (a.source === "checkout" ? "." : ", from the vendored citation: pass <code>--argleton "
      + "&lt;path&gt;</code> for the per-family detail.");
  tally(document.getElementById("traps-tally"), [
    [a.traps_run, "traps"],
    [a.families, "families"],
    [Math.round(100 * a.headline.mapsmith_silent_error_rate) + "%", "MapSmith silent errors"],
    [Math.round(100 * a.headline.mapsmith_completion_rate) + "%", "MapSmith completion"],
    [Math.round(100 * a.headline.naive_silent_error_rate) + "%", "naive engine silent errors"],
  ]);

  if (!a.adapters.length) {
    document.getElementById("adapters-chart").innerHTML =
      "<p class='empty'>per-engine detail needs a checkout of the suite</p>";
    document.getElementById("family-panel").style.display = "none";
    document.getElementById("trap-panel").style.display = "none";
    return;
  }
  const labels = a.adapters.map(x => x.name);
  const series = [
    {name: "silent error rate", color: "var(--bad)",
     values: a.adapters.map(x => Math.round(100 * x.silent_error_rate))},
    {name: "completion rate", color: "var(--good)",
     values: a.adapters.map(x => Math.round(100 * x.completion_rate))},
    {name: "probes it cannot run", color: "var(--quiet)",
     values: a.adapters.map(x => x.unsupported)},
  ];
  legend(document.getElementById("adapters-legend"), series);
  barChart(document.getElementById("adapters-chart"), labels, series, {height: 240});

  const families = [...new Set(a.traps.map(t => t.family))].sort();
  const table = document.getElementById("family-table");
  table.innerHTML = "";
  const head = el("tr");
  head.appendChild(el("th", "", "engine"));
  for (const family of families) head.appendChild(el("th", "num", family));
  table.appendChild(head);
  for (const adapter of a.adapters) {
    const tr = el("tr");
    tr.appendChild(el("td", "mono", adapter.name));
    for (const family of families) {
      const info = adapter.by_family[family];
      const cell = el("td", "num");
      if (!info) { cell.appendChild(el("span", "quiet", "–")); }
      else {
        const bad = info.silent_errors > 0;
        cell.appendChild(el("span", "pill " + (bad ? "no" : "yes"),
          bad ? info.silent_errors + "/" + info.probes : "0"));
      }
      tr.appendChild(cell);
    }
    table.appendChild(tr);
  }

  const traps = document.getElementById("traps-table");
  traps.innerHTML = "";
  const th = el("tr");
  for (const label of ["trap", "family", "what it plants", "MapSmith"]) {
    th.appendChild(el("th", "", label));
  }
  traps.appendChild(th);
  const mapsmith = a.adapters.find(x => x.name === "mapsmith");
  for (const trap of a.traps) {
    const tr = el("tr");
    tr.appendChild(el("td", "mono", trap.id));
    tr.appendChild(el("td", "", trap.family));
    tr.appendChild(el("td", "", trap.title));
    const verdict = el("td");
    const probe = mapsmith && mapsmith.per_probe.find(p => p.probe_id === trap.id);
    verdict.appendChild(el("span",
      "pill " + (!probe ? "" : probe.verdict.startsWith("correct") ? "yes" : "no"),
      probe ? probe.verdict : "not run"));
    tr.appendChild(verdict);
    traps.appendChild(tr);
  }
}

/* ---- answering ---- */
function loadLabels() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; }
}
function saveLabels() {
  try { localStorage.setItem(KEY, JSON.stringify(LABELS)); }
  catch (e) { note("this browser refused to store the answers — export before you leave"); }
}
function note(text) { document.getElementById("saved").textContent = text; }
let LABELS = loadLabels();

/* An answer is stored against the TEXT of the question, never its position.
   This page is a snapshot: adding operations or traps means generating it
   again, and a key made of an index would then move every answer onto a
   different question - silently, which is the failure mode this project exists
   to measure. Keyed by text, regenerating keeps what you answered. */
function keyFor(kind, row) { return kind + ":" + row.query; }

function pick(key, label) {
  if (LABELS[key] && LABELS[key].label === label) delete LABELS[key];
  else LABELS[key] = {label: label};
  saveLabels();
  note("saved in this browser");
}
/* A second acceptable answer, and the reason. D-062: two experienced analysts
   reach the same result with different tools, so storing one answer makes the
   measurement wrong in both directions. The reason is required wherever there is
   more than one — without it a reader cannot tell "both are right" from "I could
   not decide", and `ingest_answers.py` refuses the row. */
function toggleAlso(key, label) {
  const entry = LABELS[key];
  if (!entry || entry.label === label) return;
  const also = new Set(entry.also || []);
  if (also.has(label)) also.delete(label); else also.add(label);
  entry.also = [...also];
  saveLabels();
}
function setNote(key, text) {
  const entry = LABELS[key];
  if (!entry) return;
  entry.note = text;
  saveLabels();
}
function picker(key, suggested, marks, onPick) {
  const wrap = el("div");
  const chips = el("div", "chips");
  let redrawWhy = () => {};
  const draw = () => {
    redrawWhy();
    chips.innerHTML = "";
    const chosen = LABELS[key] ? LABELS[key].label : null;
    const shown = suggested.slice();
    if (chosen && !shown.includes(chosen) && chosen !== "none" && chosen !== "ambiguous") {
      shown.push(chosen);
    }
    for (const name of shown) {
      const chip = el("button", "chip " + (marks[name] || ""), name);
      if (chosen === name) chip.classList.add("picked");
      const op = DATA.catalog.find(o => o.name === name);
      const entry = LABELS[key];
      const alsoSet = new Set((entry && entry.also) || []);
      if (alsoSet.has(name)) chip.classList.add("also");
      chip.title = (op ? op.summary + " — " : "")
        + "click to choose, shift-click to add as also acceptable";
      chip.onclick = (event) => {
        if (event.shiftKey && chosen) toggleAlso(key, name);
        else pick(key, name);
        draw(); onPick();
      };
      chips.appendChild(chip);
    }
    for (const special of ["none", "ambiguous"]) {
      const chip = el("button", "chip", special);
      if (chosen === special) chip.classList.add("picked");
      chip.title = special === "none"
        ? "MapSmith has no operation for this request"
        : "two answers are equally defensible";
      chip.onclick = () => { pick(key, special); draw(); onPick(); };
      chips.appendChild(chip);
    }
  };
  const all = el("select");
  all.appendChild(new Option("something else…", ""));
  for (const op of DATA.catalog) {
    all.appendChild(new Option(op.name + " — " + op.summary.slice(0, 70), op.name));
  }
  all.onchange = () => { if (all.value) { pick(key, all.value); draw(); onPick(); all.value = ""; } };
  const why = el("textarea");
  why.className = "why";
  why.rows = 2;
  why.placeholder = "why more than one answer is defensible — required when you "
    + "shift-click a second one";
  why.oninput = () => { setNote(key, why.value); };
  const refreshWhy = () => {
    const entry = LABELS[key];
    const many = entry && (entry.also || []).length;
    why.value = (entry && entry.note) || "";
    why.hidden = !many;
    why.classList.toggle("missing", !!many && !why.value.trim());
  };
  wrap.appendChild(chips);
  wrap.appendChild(all);
  wrap.appendChild(why);
  // `draw` already runs on every pick, so hanging the box's refresh off it keeps
  // one path instead of reassigning the callback the chips closed over — which
  // worked and was the kind of cleverness that breaks at the next edit.
  redrawWhy = refreshWhy;
  draw();
  return wrap;
}

function drawDisagreements() {
  const host = document.getElementById("disagreements");
  host.innerHTML = "";
  if (!DATA.disagreements.length) {
    host.appendChild(el("p", "empty", "the two labellers agreed on everything"));
    return;
  }
  for (const row of DATA.disagreements) {
    const box = el("div", "case");
    box.appendChild(el("p", "q", row.query));
    const meta = el("p", "meta");
    meta.textContent = row.scenario ? "scenario: " + row.scenario : "";
    if (row.stale.length) {
      meta.textContent += (meta.textContent ? " · " : "")
        + "names an operation that no longer exists: " + row.stale.join(", ");
    }
    if (row.human) {
      meta.textContent += (meta.textContent ? " · " : "")
        + "already answered in the repository: " + row.human;
      box.classList.add("answered");
    }
    box.appendChild(meta);
    if (row.proposed) {
      /* A proposal to confirm or correct, never an answer. Collapsed by default:
         reading somebody else's reasoning first is a help on a hard request and
         an anchor on an easy one, so opening it is a choice. */
      const why = el("details", "proposed");
      const head = el("summary");
      head.textContent = row.proposed.by + " would choose " + row.proposed.label
        + (row.proposed.also.length
             ? " (also defensible: " + row.proposed.also.join(", ") + ")"
             : "")
        + " — why";
      why.appendChild(head);
      why.appendChild(el("p", "reason", row.proposed.note || "no reason given"));
      box.appendChild(why);
    }
    const marks = {};
    marks[row.claude] = "claude";
    marks[row.gemini] = "gemini";
    if (row.human) marks[row.human] = "recorded";
    if (row.proposed) marks[row.proposed.label] = "proposed";
    const suggested = [
      row.human, row.proposed && row.proposed.label, row.claude, row.gemini,
      ...((row.proposed && row.proposed.also) || []),
    ].filter(n => n && DATA.catalog.some(o => o.name === n));
    for (const name of row.ranked) {
      if (!suggested.includes(name) && suggested.length < 8) suggested.push(name);
    }
    box.appendChild(picker(keyFor("d", row), suggested, marks, tallyDisagreements));
    host.appendChild(box);
  }
}
function tallyDisagreements() {
  const rows = DATA.disagreements;
  let done = 0, claude = 0, gemini = 0, neither = 0;
  for (const row of rows) {
    const answer = LABELS[keyFor("d", row)];
    if (!answer) continue;
    done++;
    if (answer.label === row.claude) claude++;
    else if (answer.label === row.gemini) gemini++;
    else neither++;
  }
  document.getElementById("d-total").textContent = rows.length;
  document.getElementById("d-done").textContent = done;
  document.getElementById("d-claude").textContent = done ? pct(claude, done) : "–";
  document.getElementById("d-gemini").textContent = done ? pct(gemini, done) : "–";
  document.getElementById("d-neither").textContent = done ? pct(neither, done) : "–";
  const q = DATA.quality;
  const ceiling = Math.round(100 * q.agreement_answerable[0] / q.agreement_answerable[1]);
  document.getElementById("d-note").textContent = done
    ? ("Over the " + done + " you have answered, the two models had it between them "
       + pct(claude + gemini, done) + " of the time and neither had it "
       + pct(neither, done) + ". The published ceiling — how often they agree with EACH "
       + "OTHER over the answerable set — is " + ceiling + "%.")
    : ("Nothing answered yet. The published ceiling — how often the two models agree with "
       + "each other — is " + ceiling + "%, and these are the rows that number is missing.");
}

function drawRecorded() {
  const host = document.getElementById("recorded");
  const intro = document.getElementById("rec-intro");
  host.innerHTML = "";
  if (!DATA.recorded.length) {
    intro.innerHTML = "Nothing recorded yet. Set <code>MAPSMITH_DISCOVERY_LOG</code> to a file "
      + "path, work normally, then regenerate this page with <code>--log</code>. Every search "
      + "is written with the operation run after it, so these become cases written by use "
      + "rather than by a model.";
    document.getElementById("rec-panel").style.display = "none";
    return;
  }
  intro.textContent = "One row per catalog search, with the operation run after it. A choice "
    + "the ranking did not put first is the cheapest correction available — but it can also be "
    + "the caller's mistake, so the flag is a question, not a verdict.";
  for (const row of DATA.recorded) {
    const box = el("div", "case");
    box.appendChild(el("p", "q", row.query));
    const bits = [];
    if (row.at) bits.push(row.at.replace("T", " ").replace("+00:00", "Z"));
    const declared = Object.entries(row.declared || {}).map(([k, v]) => k + "=" + v).join(", ");
    bits.push(declared ? "declared " + declared : "declared nothing");
    bits.push(row.delivered.length + " delivered");
    if (row.engine) bits.push("ranked by " + row.engine);
    if (row.chose) {
      bits.push("ran " + row.chose + (row.position ? " (position " + row.position + ")" : ""));
      if (row.position > 3) bits.push("NOT in the top three");
    } else {
      bits.push("nothing was run");
    }
    if (row.searches_ago) bits.push("attributed " + row.searches_ago + " searches back");
    box.appendChild(el("p", "meta", bits.join(" · ")));
    const marks = {};
    if (row.chose) marks[row.chose] = "ran";
    box.appendChild(picker(keyFor("r", row), row.delivered.slice(0, 12), marks, tallyRecorded));
    host.appendChild(box);
  }
}
function tallyRecorded() {
  const rows = DATA.recorded;
  const ran = rows.filter(r => r.chose);
  const first = ran.filter(r => r.position === 1).length;
  const three = ran.filter(r => r.position && r.position <= 3).length;
  let labelled = 0, agreeFirst = 0, agreeThree = 0, delivered = 0;
  for (const row of rows) {
    const answer = LABELS[keyFor("r", row)];
    if (!answer) continue;
    labelled++;
    const at = row.delivered.indexOf(answer.label) + 1;
    if (at === 1) agreeFirst++;
    if (at >= 1 && at <= 3) agreeThree++;
    if (at >= 1) delivered++;
  }
  document.getElementById("r-total").textContent = rows.length;
  document.getElementById("r-ran").textContent = ran.length;
  document.getElementById("r-first").textContent = ran.length ? pct(first, ran.length) : "–";
  document.getElementById("r-three").textContent = ran.length ? pct(three, ran.length) : "–";
  document.getElementById("r-labelled").textContent = labelled;
  document.getElementById("r-note").textContent = labelled
    ? ("Against YOUR answers on those " + labelled + ": the ranking had it first "
       + pct(agreeFirst, labelled) + ", in the top three " + pct(agreeThree, labelled)
       + ", and delivered it at all " + pct(delivered, labelled) + ". The first two are the "
       + "ranking; the third is the narrowing, and it is the one the design promises.")
    : ("The percentages above are about what was RUN, which is a choice somebody made and not "
       + "necessarily the right one. Answer a few and the same three numbers appear against "
       + "your answers instead.");
}

/* ---- trend ---- */
function drawTrend() {
  const series = DATA.history;
  const xs = series.map(row => (row.at || "").slice(5, 16).replace("T", " "));
  const lines = [
    {name: "operations", color: "var(--accent)", values: series.map(r => r.operations)},
    {name: "tools", color: "var(--accent2)", values: series.map(r => r.tools)},
    {name: "traps", color: "var(--warn)", values: series.map(r => r.traps)},
    {name: "found@3 with facets", color: "var(--good)",
     values: series.map(r => r.found_at_3_faceted)},
    {name: "delivered", color: "var(--bad)", values: series.map(r => r.delivered)},
  ];
  legend(document.getElementById("trend-legend"), lines);
  lineChart(document.getElementById("trend-chart"), xs, lines, {height: 240});

  const table = document.getElementById("trend-table");
  table.innerHTML = "";
  const head = el("tr");
  for (const label of ["generated", "commit", "version", "tools", "operations", "reachable",
                       "top 3", "traps", "found@3", "delivered"]) {
    head.appendChild(el("th", label === "generated" || label === "commit"
      || label === "version" ? "" : "num", label));
  }
  table.appendChild(head);
  for (const row of series.slice().reverse()) {
    const tr = el("tr");
    tr.appendChild(el("td", "quiet", (row.at || "").replace("T", " ").replace("+00:00", "")));
    tr.appendChild(el("td", "mono", row.commit || "–"));
    tr.appendChild(el("td", "mono", row.version || "–"));
    for (const value of [row.tools, row.operations, row.reachable, row.top3, row.traps,
                         row.found_at_3_faceted + "%", row.delivered + "%"]) {
      tr.appendChild(el("td", "num", String(value)));
    }
    table.appendChild(tr);
  }
}

/* ---- export ---- */
function rows() {
  const out = [];
  for (const row of DATA.disagreements) {
    const answer = LABELS[keyFor("d", row)];
    if (!answer) continue;
    out.push({query: row.query, scenario: row.scenario,
              generated_by: "dashboard, answered by hand", split: "tune",
              label_human: answer.label,
              label_human_also: answer.also || [],
              label_human_note: answer.note || "",
              label_claude: row.claude, label_gemini: row.gemini});
  }
  for (const row of DATA.recorded) {
    const answer = LABELS[keyFor("r", row)];
    if (!answer) continue;
    out.push({query: row.query, scenario: "recorded from use",
              generated_by: "discovery log, answered by hand", split: "tune",
              label_human: answer.label, ran: row.chose, declared: row.declared,
              delivered_position: row.delivered.indexOf(answer.label) + 1 || null});
  }
  return out;
}
document.getElementById("export").onclick = () => {
  const list = rows();
  document.getElementById("out").value = list.length
    ? list.map(r => JSON.stringify(r)).join(",\n") : "nothing answered yet";
};
document.getElementById("copy").onclick = async () => {
  const text = document.getElementById("out").value;
  if (!text) return;
  try { await navigator.clipboard.writeText(text); note("copied"); }
  catch (e) { document.getElementById("out").select(); note("select and copy"); }
};
document.getElementById("forget").onclick = () => {
  if (!confirm("Delete every answer stored in this browser?")) return;
  LABELS = {};
  saveLabels();
  drawDisagreements(); drawRecorded(); tallyDisagreements(); tallyRecorded();
  document.getElementById("out").value = "";
  note("forgotten");
};

drawOverview();
drawOperations();
drawQuality();
drawTraps();
drawDisagreements();
drawRecorded();
tallyDisagreements();
tallyRecorded();
drawTrend();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
