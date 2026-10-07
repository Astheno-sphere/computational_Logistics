# DaedalMap Public Technical Context

Public documentation router for the DaedalMap runtime.

Use it after cloning the repository to answer:

- What is this project?
- Where should I start?
- Which file owns the behavior I want to change?
- Which contracts must my data, mode, API, or map feature preserve?

The root [README](../README.md) is the quick start. This file is the working
map for contributors and researchers.

## Choose your path

| I want to... | Read |
|---|---|
| Run the application locally | [LOCAL_AND_HOSTED.md](LOCAL_AND_HOSTED.md) |
| Install or download data packs | [DATA_INSTALLATION.md](DATA_INSTALLATION.md) |
| Understand Explore, Research, Ops, and Tutorial | [RUNTIME_MODES.md](RUNTIME_MODES.md) |
| Understand shared versus mode-specific behavior | [RUNTIME_UNIFICATION.md](RUNTIME_UNIFICATION.md) |
| Learn where code lives | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Set up a development workflow | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Understand a request from chat to map | [QUERY_AND_DISPLAY.md](QUERY_AND_DISPLAY.md) |
| Use or extend HTTP and MCP surfaces | [API_AND_MCP.md](API_AND_MCP.md) |
| Research using my MCP-capable subscription | [RESEARCH_MCP.md](RESEARCH_MCP.md) |
| Download public or researcher cloud artifacts | [CLOUD_ARTIFACT_ACCESS.md](CLOUD_ARTIFACT_ACCESS.md) |
| Prepare my own dataset | [DATA_PREPARATION.md](DATA_PREPARATION.md) |
| Check exact source schemas | [DATA_SCHEMAS.md](DATA_SCHEMAS.md) |
| Build and share a pack | [PACK_AUTHORING.md](PACK_AUTHORING.md) |
| Self-host responsibly | [SECURITY_AND_SELF_HOSTING.md](SECURITY_AND_SELF_HOSTING.md) |
| Study climate or disaster display systems | [display/README.md](display/README.md) |
| Read domain data-program research | [data-programs/README.md](data-programs/README.md) |
| Review worked research projects and audits | [research-projects/README.md](research-projects/README.md) |

## System in one page

DaedalMap is a map-first geographic query runtime.

```text
user or machine request
        |
        v
mode or API route
        |
        v
intent/source/metric/geography/time resolution
        |
        v
deterministic validation and DuckDB/Parquet execution
        |
        v
shared post-processing, warnings, and provenance
        |
        v
map geometry + display state + response
```

The runtime can read a local data tree or object storage. Sources are described
by metadata and grouped into packs. Explore discovers broadly, Research works
inside a corpus, Ops starts from a watch/current-state posture, and machine
surfaces use structured HTTP or MCP requests.

For many academic users, the simplest reasoning path is the hosted
[Research MCP](RESEARCH_MCP.md): their subscription client supplies the model,
while DaedalMap supplies deterministic source-bound evidence.

## Repository map

| Path | Responsibility |
|---|---|
| `app.py` | FastAPI application creation, middleware, and router registration |
| `mapmover/routes/` | HTTP, chat, geometry, research, Ops, raster, MCP, and system endpoints |
| `mapmover/explore/` | Explore-specific request and response workflow |
| `mapmover/ops/` and `mapmover/ops_*.py` | Ops state, feeds, orchestration, and display behavior |
| `mapmover/runtime/` | Shared execution, geography, filtering, validation, warnings, and post-processing |
| `mapmover/execution/` | Deterministic data execution helpers |
| `mapmover/data_loading.py` | Catalog, source metadata, reference, and pack discovery |
| `mapmover/geometry_handlers.py` | Geometry loading and selection behavior |
| `mapmover/corpus_registry.py` | Local Research corpus state |
| `static/` | Browser JavaScript, CSS, icons, and vendored frontend assets |
| `templates/` | Server-rendered application templates |
| `converters/` | Minimal public catalog and geometry setup tools |
| `scripts/` | Small public data/geometry maintenance helpers |
| `tests/` | Runtime and contract regression tests |
| `examples/` | API and integration examples |
| `docs/` | Public runtime, data, and contributor documentation |

See [ARCHITECTURE.md](ARCHITECTURE.md) before making structural changes.

## Contracts that outrank implementation convenience

Keep these stable across features and modes:

1. `loc_id` is the geographic bridge.
2. `timestamp` is the canonical temporal field.
3. Source metadata and references define meaning and provenance.
4. Metric-level coverage and aggregation rules govern execution.
5. Shared runtime code owns data, geography, warning, and display semantics.
6. Modes own posture and workflow, not separate data truths.
7. Human interpretation may use an LLM; filtering and aggregation remain
   deterministic.
8. Local/self-host operation must not require DaedalMap's private control plane.

## Common change routes

### Add a source or pack

1. [DATA_INSTALLATION.md](DATA_INSTALLATION.md) if you need maintained packs
   or cloud artifacts first.
2. [DATA_SCHEMAS.md](DATA_SCHEMAS.md)
3. [DATA_PREPARATION.md](DATA_PREPARATION.md)
4. [PACK_AUTHORING.md](PACK_AUTHORING.md)
5. Build the catalog with `converters/catalog_builder.py`.
6. Test discovery in Explore and bounded use in Research.

### Add or change a mode

1. [RUNTIME_MODES.md](RUNTIME_MODES.md)
2. [RUNTIME_UNIFICATION.md](RUNTIME_UNIFICATION.md)
3. [QUERY_AND_DISPLAY.md](QUERY_AND_DISPLAY.md)
4. Reuse shared runtime and display seams before adding mode-specific code.

### Change query behavior

1. Identify whether the issue is intent, source selection, validation,
   execution, post-processing, or display.
2. Read [QUERY_AND_DISPLAY.md](QUERY_AND_DISPLAY.md).
3. Change the shared seam when the rule applies to more than one mode.
4. Add a regression test at the lowest deterministic layer possible.

### Add an endpoint or MCP tool

1. [API_AND_MCP.md](API_AND_MCP.md)
2. Reuse shared source, geography, time, and validation helpers.
3. Keep transport envelopes separate from data semantics.
4. Document authentication and failure behavior.

### Change the map

1. [QUERY_AND_DISPLAY.md](QUERY_AND_DISPLAY.md)
2. [RUNTIME_UNIFICATION.md](RUNTIME_UNIFICATION.md)
3. Preserve canonical feature identity and shared layer semantics.
4. Keep a future authored-map format declarative rather than embedding source
   data or duplicating rendering engines.

## Development loop

```powershell
cd county-map
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Run the relevant focused test while working, then the broader suite described
in [DEVELOPMENT.md](DEVELOPMENT.md). Before committing:

```powershell
git diff --check
git status --short
```

## Documentation ownership

| Document | Owns |
|---|---|
| `CONTEXT.md` | Navigation and system-level orientation |
| `ARCHITECTURE.md` | Code boundaries and ownership |
| `RUNTIME_UNIFICATION.md` | Shared-versus-mode-specific doctrine |
| `RUNTIME_MODES.md` | User-facing mode meanings |
| `QUERY_AND_DISPLAY.md` | Request lifecycle and map output |
| `DATA_INSTALLATION.md` | Local data folders, Pack Store installs, and researcher downloads |
| `DATA_SCHEMAS.md` | Source and metadata contract |
| `DATA_PREPARATION.md` | Reproducible conversion workflow |
| `PACK_AUTHORING.md` | Pack and corpus authoring |
| `API_AND_MCP.md` | Public machine surfaces |
| `LOCAL_AND_HOSTED.md` | Deployment configuration |
| `SECURITY_AND_SELF_HOSTING.md` | Trust boundaries and safe operation |
| `DEVELOPMENT.md` | Contributor workflow |

If two docs disagree, fix the owning contract rather than adding a third
explanation.

## What is intentionally absent

The public repository does not document or ship DaedalMap's private billing,
account administration, production data collectors, release-control systems,
operator secrets, or maintained proprietary pipeline estate.

Those systems are not required to run, study, extend, or self-host the public
runtime.
