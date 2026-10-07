# Knowledge bank: what we have, what we missed, what comes next

Written after the first build. Figures are from `MANIFEST.json` and `catalog/skills.json`.

## What exists

- **219 sources** in `sources.yaml`: 188 vendored (13 of them copyleft, isolated), 31 link-only.
- **Catalog** (`catalog/`): 1,567 skills, 698 agents, 311 commands, 203 plugins, 13 marketplaces,
  81 MCP servers. Every entry is tagged by domain, with the phrase that triggered the tag, and is
  linked to the libraries/engines it mentions (`interlinks.md`).
- **Tools**: `kb_sync.py` clones, gates on license and vendors. `kb_harvest.py` pulls candidates
  from curated lists already in the bank. `kb_assemble.py` builds the catalog. Tests in `tests/`.

## The main finding: our domain has almost no skills to collect

| Domain | Entries | Who wrote them |
|---|---|---|
| computational design | 18 | Abhinav, all 18 |
| architecture / AEC | 87 | almost all Abhinav (plus AEC-Scholar agents) |
| urban | 28 | Abhinav, plus a few urban/geo MCP projects |
| logistics | 6 | 2 genuine (Abhinav: mobility-and-transport, tod-design); 4 false positives |
| optimisation | 5 | general, none about routing |

The engines are all here (OR-Tools, PyVRP, HGS-CVRP, VROOM, OSRM, Valhalla, OSMnx, Timefold,
HiGHS, SUMO), and the urban/AEC side is covered by Abhinav. **No one has published skills that
drive those engines for logistics.** Collecting more will not fill that; writing them will. That is
also the honest route to "Abhinav level": he is known for authoring the skills, not for owning a
copy of other people's.

## What we missed, and what was done about it

| Gap | Status |
|---|---|
| Repos were copied but not **assembled**: nothing said which skills exist or how they connect | Fixed: `catalog/` with domains, interlinks, plugins, MCP servers, issues |
| Repos without a root license were skipped whole, though subfolders had their own (e.g. `anthropics/skills`) | Fixed: `per_folder` mode; 14 Apache-2.0 Anthropic skills now in, 5 proprietary left out |
| Discovery came from memory and a few web searches | Improved: `kb_harvest.py` mines curated lists in the bank (+97 MCP servers). GitHub search/topics need the API, which is blocked here |
| No quality signal (activity, maintenance) | Partly: `last_commit` recorded per source. Stars/issues need the GitHub API |
| Skills/agents can steer Claude and hooks/MCP servers run code; nothing reviewed them | Open: catalog warns. Next: a scanner that flags hooks, `curl \| sh`, network and shell calls per entry |
| 64 skill names exist in several sources and would collide if installed together | Listed in `catalog/issues.md`; pick one or rename on import |
| Snapshots make this repo ~800 MB and grow it on every refresh | Open: see "Repository layout" |
| No refresh: snapshots go stale | Open: a scheduled job running sync -> assemble -> pull request |
| "72 ways" list and the Scribd PDFs were never seen at source | Open: Instagram and Scribd are blocked here, and Scribd copies are often unauthorised. Paste the captions/outline, or get the PDF from the author |
| Models and datasets | Open: Hugging Face is blocked here; OSM data is ODbL (fetch at use time); VRP benchmark files (CVRPLIB, Solomon, Gehring-Homberger) to be fetched by script, not vendored |
| This repo's README described code that did not exist | Fixed: marked as planned |

## Repository layout (decision needed)

Today the bank lives inside this project repo. Recommended:

1. **A separate repo for the bank** (e.g. `computational-logistics-bank`), private unless you want
   it public; copyleft folders are fine in either if the licenses stay with them.
2. In it, keep **vendored copies only for small, text-heavy sources** (skills, plugins, MCP servers),
   and turn large engines (OR-Tools, Valhalla, transformers, ...) into pinned pointers that
   `kb_sync.py --materialize` clones on demand. That cuts the size several-fold.
3. **This repo** keeps only our own skills, code and tests, and points at the bank.

Creating the repo needs your choice of name, owner and visibility; this session can only push here.

## Next, in order

1. **Write the logistics skills** with Anthropic's `skill-creator` (in the bank) and Abhinav's
   router-and-foundation pattern:
   `cl-foundations` (router), `osm-network` (OSMnx graph + terrain grade), `vrp-solve` (PyVRP /
   OR-Tools with time windows and capacity), `route-energy` (grade-aware EV/diesel energy),
   `isochrone-access` (r5/OSMnx accessibility), `fleet-scenarios` (compare runs), `rhino-bake`
   (via Rhino MCP), each with tests against the synthetic Molde grid.
2. `docs/abhinav-patterns.md` from his five repos (structure, frontmatter, routers, calculators).
3. Safety scanner for hooks/scripts/MCP servers in the catalog.
4. Bank repo split and scheduled refresh.
