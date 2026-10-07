#!/usr/bin/env python3
"""Assemble the vendored knowledge bank into a navigable catalog.

Reads knowledge-bank/vendor/ (built by kb_sync.py) and writes knowledge-bank/catalog/:
  skills.json        every skill, agent, command and plugin with source, path, domains, links
  README.md          counts and how to use the catalog
  domains/<d>.md     skills per domain, our core domains first
  interlinks.md      library/engine -> skills that mention it -> where its code lives in the bank
  plugins.md         Claude Code plugins and marketplaces found
  issues.md          broken frontmatter, duplicate names
Nothing in vendor/ is changed. Usage: python3 tools/kb_assemble.py
"""
import json, re
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge-bank"
VENDOR, OUT = KB / "vendor", KB / "catalog"

# Ordered: our core domains first. A skill can carry several. Only domain-specific phrases count:
# bare words like "routing", "architect", "building", "density" or "supply chain" mostly mean software here.
DOMAINS = [
    ("logistics", r"\b(vrp|vrptw|cvrp|tsp|vehicle routing|travell?ing salesman|route (planning|optimi[sz]\w*)|"
                  r"fleet (management|routing|planning)|logistics|warehous(e|es|ing) (operations|layout|management|picking)|inventory (optimi[sz]\w*|management|control|polic\w*)|freight|"
                  r"shipments?|last[- ]mile|depots?|couriers?|pickup and delivery|delivery routes?|"
                  r"(physical|global|retail|food) supply chains?|supply chain (planning|management|optimi[sz]\w*|network))\b"),
    ("urban", r"\b(urban\w*|city planning|cities|zoning|street ?scapes?|street design|complete streets|"
              r"neighbou?rhoods?|public transit|transit (network|planning)|walkab\w*|land[- ]use|masterplan\w*|"
              r"public spaces?|placemaking|urban mobility|density (bonus|framework)|floor area ratio|far\b)\b"),
    ("architecture-aec", r"\b(aec|bim|revit|ifc|fa[cç]ades?|building (codes?|regulations?|envelope|design|typolog\w*|"
                         r"services|physics|performance|information)|egress|structural (engineering|systems|design|analysis)|"
                         r"daylight\w*|hvac|construction (documents?|documentation|drawings?)|floor plans?|"
                         r"architectural (design|drawings?|practice|programming|codes?)|architecture, engineering|"
                         r"architects? (and|&) (urban|designers?|engineers)|accessibility design|fire (safety|protection))\b"),
    ("computational-design", r"\b(grasshopper|rhino\w*|parametric (design|model\w*)|generative design|nurbs|"
                             r"digital fabrication|computational design|mesh processing|topology optimi[sz]\w*|"
                             r"form[- ]finding|algorithmic design)\b"),
    ("geospatial", r"\b(gis|geospatial|openstreetmap|osm|geojson|shapefiles?|qgis|postgis|geocod\w*|"
                   r"isochrones?|coordinate reference|terrain|elevation model|lidar|spatial analysis|raster (data|analysis))\b"),
    ("optimisation", r"\b(linear programming|milp|mixed[- ]integer|metaheuristic\w*|constraint programming|or-tools|"
                     r"operations research|combinatorial optimi[sz]\w*|(lp|mip|sat|optimi[sz]ation) solvers?|"
                     r"scheduling problems?|vehicle routing|genetic algorithms?|simulated annealing|particle swarm|"
                     r"optimi[sz]ation methods|multi-objective optimi[sz]\w*|pareto (front|optimal\w*))\b"),
    ("simulation-ml", r"\b(agent-based|discrete[- ]event|traffic simulation|simulation model\w*|reinforcement learning|"
                      r"demand forecast\w*|time[- ]series forecast\w*)\b"),
    ("agent-engineering", r"\b(mcp|model context protocol|skills?|hooks?|subagents?|claude code|plugins?|"
                          r"prompt engineering|agentic)\b"),
]
NOT_DOMAIN = {   # software senses that the phrases above can still hit
    "logistics": re.compile(r"\b(software supply chain|supply chain (security|attack)|dependenc(y|ies)|data warehouses?)\b", re.I),
    "architecture-aec": re.compile(r"\b(facade pattern|design patterns?|laravel|react|django|rails|microservices?)\b", re.I),
}
DOMAIN_RE = [(d, re.compile(p, re.I)) for d, p in DOMAINS]

# Library or engine -> regex for a mention -> source id(s) in the bank holding its code.
LIBS = {
    "OSMnx": (r"\bosmnx\b", ["gboeing__osmnx"]),
    "NetworkX": (r"\bnetworkx\b", ["networkx__networkx"]),
    "GeoPandas": (r"\bgeopandas\b", ["geopandas__geopandas"]),
    "PySAL / momepy": (r"\b(pysal|momepy)\b", ["pysal__pysal", "pysal__momepy"]),
    "pyosmium": (r"\b(pyosmium|osmium)\b", ["osmcode__pyosmium"]),
    "OR-Tools": (r"\b(or-?tools|ortools)\b", ["google__or-tools"]),
    "PyVRP / HGS": (r"\b(pyvrp|hgs-?cvrp|hybrid genetic search)\b", ["pyvrp__pyvrp", "vidalt__HGS-CVRP"]),
    "VROOM": (r"\bvroom\b", ["VROOM-Project__vroom"]),
    "OSRM": (r"\bosrm\b", ["Project-OSRM__osrm-backend"]),
    "Valhalla": (r"\bvalhalla\b", ["valhalla__valhalla"]),
    "GraphHopper / jsprit": (r"\b(graphhopper|jsprit)\b", ["graphhopper__graphhopper", "graphhopper__jsprit"]),
    "OpenRouteService": (r"\b(openrouteservice|ors)\b", ["GIScience__openrouteservice"]),
    "OpenTripPlanner / r5": (r"\b(opentripplanner|r5py|conveyal)\b", ["opentripplanner__OpenTripPlanner", "conveyal__r5"]),
    "Timefold": (r"\b(timefold|optaplanner)\b", ["TimefoldAI__timefold-solver", "TimefoldAI__timefold-quickstarts"]),
    "LP/MIP (HiGHS, SCIP, Pyomo, PuLP)": (r"\b(highs|scip|pyomo|pulp)\b", ["ERGO-Code__HiGHS", "scipopt__scip", "Pyomo__pyomo", "coin-or__pulp"]),
    "ALNS": (r"\balns\b|large neighbou?rhood search", ["N-Wouda__ALNS"]),
    "RL4CO / RouteFinder": (r"\b(rl4co|routefinder)\b", ["ai4co__rl4co", "ai4co__routefinder"]),
    "SUMO": (r"\bsumo\b", ["eclipse-sumo__sumo"]),
    "GTFS": (r"\bgtfs\b", ["mrcagney__gtfs_kit"]),
    "H3": (r"\bh3\b", ["uber__h3-py"]),
    "Mesa (agent-based)": (r"\bmesa\b", ["projectmesa__mesa", "projectmesa__mesa-geo"]),
    "stockpyl / or-gym": (r"\b(stockpyl|or-gym|newsvendor|eoq)\b", ["LarrySnyder__stockpyl", "hubbs5__or-gym"]),
    "Rhino / RhinoCommon / rhino3dm": (r"\b(rhinocommon|rhino3dm|rhinoscript\w*|rhino ?8|rhino\.inside)\b",
                                        ["mcneel__rhino3dm", "mcneel__rhino-developer-samples"]),
    "Rhino Compute / Hops": (r"\b(rhino compute|compute\.rhino3d|hops)\b", ["mcneel__compute.rhino3d"]),
    "Grasshopper": (r"\bgrasshopper\b", ["mcneel__rhino-developer-samples", "alfredatnycu__grasshopper-mcp", "veoery__GH_mcp_server"]),
    "Ladybug Tools": (r"\b(ladybug|honeybee)\b", ["ladybug-tools__ladybug", "ladybug-tools__honeybee-core", "ladybug-tools__lbt-grasshopper"]),
    "COMPAS": (r"\bcompas\b", ["compas-dev__compas"]),
    "IFC / IfcOpenShell": (r"\b(ifcopenshell|ifc)\b", ["IfcOpenShell__IfcOpenShell", "JotaDeRodriguez__Bonsai_mcp"]),
    "Speckle": (r"\bspeckle\b", ["specklesystems__specklepy", "speckleworks__SpeckleCore"]),
    "QGIS": (r"\bqgis\b", []),
    "kepler.gl / deck.gl": (r"\b(kepler\.?gl|deck\.?gl)\b", ["keplergl__kepler.gl", "visgl__deck.gl"]),
    "MCP SDK": (r"\b(model context protocol|mcp sdk|fastmcp)\b", ["modelcontextprotocol__python-sdk", "modelcontextprotocol__typescript-sdk"]),
}
LIB_RE = {k: (re.compile(p, re.I), ids) for k, (p, ids) in LIBS.items()}
FM = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.S)


def frontmatter(text):
    m = FM.match(text)
    if not m:
        return None, "no frontmatter"
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        return None, "bad YAML: %s" % str(e).splitlines()[0]
    if not isinstance(data, dict):
        return None, "frontmatter is not a mapping"
    return data, None


def source_of(path):
    rel = path.relative_to(VENDOR)
    return rel.parts[0], rel.parts[1]          # category, source id


def kind_of(path):
    if path.name == "SKILL.md":
        return "skill"
    parts = {p.lower() for p in path.parts}
    if "agents" in parts:
        return "agent"
    if "commands" in parts:
        return "command"
    return None


def collect():
    items, issues = [], []
    vendored = {p.name for c in VENDOR.iterdir() if c.is_dir() for p in c.iterdir() if p.is_dir()}
    for path in sorted(VENDOR.rglob("*.md")):
        kind = kind_of(path)
        if not kind:
            continue
        text = path.read_text(errors="replace")
        fm, err = frontmatter(text)
        cat, src = source_of(path)
        rel = str(path.relative_to(KB))
        if kind in ("agent", "command") and not fm:
            continue                               # plain docs inside agents/ or commands/ folders
        if err:
            issues.append((rel, err))
            fm = {}
        name = str(fm.get("name") or (path.parent.name if kind == "skill" else path.stem))
        desc = " ".join(str(fm.get("description") or "").split())
        if kind == "skill" and not fm.get("description"):
            issues.append((rel, "skill has no description: Claude cannot know when to load it"))
        hay = "%s %s" % (name.replace("-", " "), desc)
        evidence = {}
        for d, rx in DOMAIN_RE:
            m = rx.search(hay)
            if m and not (d in NOT_DOMAIN and NOT_DOMAIN[d].search(hay)):
                evidence[d] = m.group(0).lower()
        doms = list(evidence) or ["other"]
        links = sorted(k for k, (rx, _) in LIB_RE.items() if rx.search(text))
        items.append({"kind": kind, "name": name, "description": desc, "domains": doms, "matched": evidence, "libs": links,
                      "source": src, "category": cat, "path": rel})
    for pj in sorted(VENDOR.rglob("plugin.json")) + sorted(VENDOR.rglob("marketplace.json")):
        if ".claude-plugin" not in pj.parts:
            continue
        try:
            data = json.loads(pj.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            issues.append((str(pj.relative_to(KB)), "bad JSON: %s" % e))
            continue
        cat, src = source_of(pj)
        n_plugins = len(data.get("plugins", [])) if pj.name == "marketplace.json" else None
        items.append({"kind": "marketplace" if n_plugins is not None else "plugin",
                      "name": str(data.get("name", pj.parent.parent.name)),
                      "description": " ".join(str(data.get("description", "")).split()),
                      "plugins": n_plugins, "domains": [], "libs": [], "source": src, "category": cat,
                      "path": str(pj.relative_to(KB))})
    return items, issues, vendored


MCP_SDK = re.compile(r"@modelcontextprotocol/sdk|from mcp\.server|import mcp\b|from fastmcp|FastMCP\(|mcp-go|rmcp|ModelContextProtocol")
MCP_TOOL = re.compile(r"@(?:mcp|server|app)\.tool\b|\.tool\(\s*[\"']|registerTool\(|server\.setRequestHandler\(\s*CallToolRequestSchema|"
                      r"name:\s*[\"'][a-z0-9_]+[\"'],\s*\n\s*description:")
CODE_EXT = {".py", ".ts", ".js", ".mjs", ".go", ".rs", ".cs", ".java"}


def mcp_servers(manifest):
    """Sources whose code uses an MCP SDK: language, rough tool count, how it would be launched."""
    out = []
    for m in manifest:
        if m["status"] != "vendored":
            continue
        root = VENDOR / m["category"] / m["id"]
        if not root.is_dir() or m["category"] in ("mcp-core", "frontier-model-tooling", "claude-skill-registries"):
            continue
        uses, tools, langs = False, 0, set()
        for f in root.rglob("*"):
            if f.suffix in CODE_EXT and f.is_file() and "test" not in f.parts and "node_modules" not in f.parts:
                t = f.read_text(errors="ignore")
                if MCP_SDK.search(t):
                    uses = True
                    langs.add(f.suffix.lstrip("."))
                tools += len(MCP_TOOL.findall(t))
        if not uses:
            continue
        launch = "npx / node" if (root / "package.json").exists() else \
                 "uvx / pip" if (root / "pyproject.toml").exists() or (root / "setup.py").exists() else \
                 "go run" if (root / "go.mod").exists() else "see README"
        out.append({"id": m["id"], "category": m["category"], "license": m["license"], "why": m["why"],
                    "languages": sorted(langs), "tools_approx": tools, "launch": launch,
                    "last_commit": m.get("last_commit", ""), "path": "vendor/%s/%s" % (m["category"], m["id"])})
    return out


def short(s, n=150):
    s = s.replace("|", "/")
    return s if len(s) <= n else s[:n - 1] + "…"


def write(items, issues, vendored):
    OUT.mkdir(exist_ok=True)
    (OUT / "domains").mkdir(exist_ok=True)
    for old in (OUT / "domains").glob("*.md"):
        old.unlink()
    (OUT / "skills.json").write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
    skills = [i for i in items if i["kind"] in ("skill", "agent", "command")]
    by_dom = defaultdict(list)
    for i in skills:
        for d in i["domains"]:
            by_dom[d].append(i)
    order = [d for d, _ in DOMAINS] + ["other"]
    for d in order:
        rows = sorted(by_dom.get(d, []), key=lambda i: ({"skill": 0, "agent": 1, "command": 2}[i["kind"]], i["name"].lower()))
        lines = ["# Domain: %s (%d entries)" % (d, len(rows)), "",
                 "Generated by `tools/kb_assemble.py`. Paths are relative to `knowledge-bank/`.", "",
                 "| Kind | Name | What it does | Libraries | Source | Path |", "|---|---|---|---|---|---|"]
        for i in rows:
            lines.append("| %s | %s | %s | %s | %s | `%s` |" % (i["kind"], short(i["name"], 50), short(i["description"]),
                                                            ", ".join(i["libs"]), i["source"], i["path"]))
        (OUT / "domains" / ("%s.md" % d)).write_text("\n".join(lines) + "\n")

    il = ["# Interlinks: libraries and engines -> skills -> code in the bank", "",
          "For each library, the skills/agents that mention it and where its own source lives here.",
          "Use it to go from \"a skill that does X\" to \"the engine that actually computes X\".", ""]
    for lib, (_, ids) in LIB_RE.items():
        users = [i for i in skills if lib in i["libs"]]
        here = [s for s in ids if s in vendored]
        il.append("## %s (%d)" % (lib, len(users)))
        il.append("Code in bank: " + (", ".join("`%s`" % s for s in here) if here else "not vendored (link-only or not added)"))
        for i in sorted(users, key=lambda i: (i["kind"], i["name"].lower()))[:40]:
            il.append("- %s **%s** (%s): `%s`" % (i["kind"], i["name"], i["source"], i["path"]))
        if len(users) > 40:
            il.append("- ... %d more in `skills.json`" % (len(users) - 40))
        il.append("")
    (OUT / "interlinks.md").write_text("\n".join(il))

    pl = ["# Plugins and marketplaces", "", "| Kind | Name | Plugins | What it is | Source | Path |", "|---|---|---|---|---|---|"]
    for i in sorted((i for i in items if i["kind"] in ("plugin", "marketplace")), key=lambda i: (i["source"], i["name"])):
        pl.append("| %s | %s | %s | %s | %s | `%s` |" % (i["kind"], i["name"], i["plugins"] or "", short(i["description"], 120), i["source"], i["path"]))
    (OUT / "plugins.md").write_text("\n".join(pl) + "\n")

    names = defaultdict(list)
    for i in skills:
        if i["kind"] == "skill":
            names[i["name"].lower()].append(i)
    dups = {n: v for n, v in names.items() if len({x["source"] for x in v}) > 1}
    iss = ["# Issues", "", "## Broken or incomplete entries (%d)" % len(issues), ""]
    iss += ["- `%s`: %s" % (p, e) for p, e in issues]
    iss += ["", "## Same skill name in several sources (%d)" % len(dups),
            "Installing two with the same name collides. Pick one, or rename on import.", ""]
    for n, v in sorted(dups.items()):
        iss.append("- **%s**: " % n + "; ".join("%s `%s`" % (x["source"], x["path"]) for x in v))
    (OUT / "issues.md").write_text("\n".join(iss) + "\n")

    count = lambda k: sum(1 for i in items if i["kind"] == k)
    rd = ["# Catalog", "",
          "Everything Claude-loadable in the bank, assembled by `tools/kb_assemble.py` from `vendor/`.", "",
          "| What | Count |", "|---|---|"]
    rd += ["| %s | %d |" % (k, count(k)) for k in ("skill", "agent", "command", "plugin", "marketplace")]
    rd += ["", "## By domain (one entry can be in several)", "", "| Domain | Entries |", "|---|---|"]
    rd += ["| [%s](domains/%s.md) | %d |" % (d, d, len(by_dom.get(d, []))) for d in order]
    rd += ["", "- [interlinks.md](interlinks.md): library -> skills -> code",
           "- [plugins.md](plugins.md): plugins and marketplaces",
           "- [mcp-servers.md](mcp-servers.md): MCP servers with language, tool count, launch method",
           "- [issues.md](issues.md): %d broken entries, %d duplicate names" % (len(issues), len(dups)),
           "- `skills.json`: the full machine-readable catalog", "",
           "## Before you install anything from here",
           "Skills, agents, hooks and MCP servers run with your permissions and their text steers Claude.",
           "Read a skill and any scripts it ships before enabling it. Never enable a whole marketplace blind.",
           "Install one at a time into a project (`.claude/skills/<name>/`), not globally."]
    (OUT / "README.md").write_text("\n".join(rd) + "\n")
    return by_dom, dups


def write_mcp(servers):
    (OUT / "mcp-servers.json").write_text(json.dumps(servers, indent=1, ensure_ascii=False) + "\n")
    lines = ["# MCP servers in the bank (%d)" % len(servers), "",
             "Detected by MCP SDK use in the code. Tool counts are approximate (pattern-matched).",
             "Read the server code before connecting it: it runs with your permissions.", "",
             "| Server | Category | License | Lang | Tools ~ | Launch | Last commit | What |", "|---|---|---|---|---|---|---|---|"]
    for x in sorted(servers, key=lambda x: (x["category"], x["id"].lower())):
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (x["id"], x["category"], x["license"], ",".join(x["languages"]),
                     x["tools_approx"] or "?", x["launch"], x["last_commit"], short(x["why"], 110)))
    (OUT / "mcp-servers.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    items, issues, vendored = collect()
    by_dom, dups = write(items, issues, vendored)
    servers = mcp_servers(json.loads((KB / "MANIFEST.json").read_text()))
    write_mcp(servers)
    print("mcp servers:", len(servers))
    print("entries:", len(items), "| issues:", len(issues), "| duplicate names:", len(dups))
    for d in [d for d, _ in DOMAINS] + ["other"]:
        print("  %-22s %d" % (d, len(by_dom.get(d, []))))
