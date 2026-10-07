# Development Guide

## Prerequisites

- Python 3.12 or newer
- Git
- a supported model API key only for the built-in local chat UI
- Node.js only for the JavaScript examples or package scripts
- a compatible local data tree, unless testing cloud-data mode

## Setup

```powershell
git clone https://github.com/xyver/daedal-map.git
cd daedal-map
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set the local runtime and data path:

```text
INSTALL_MODE=local
RUNTIME_MODE=local
DATA_ROOT=C:/path/to/your/data
```

No model key is required for local data operations. Set OpenAI or Anthropic
only when exercising the built-in local chat UI. Researchers using
[Research MCP](RESEARCH_MCP.md) reason through their MCP-capable subscription
client instead. See [LOCAL_AND_HOSTED.md](LOCAL_AND_HOSTED.md).

This template has no cloud-storage or hosted-service dependency.

## Run

```powershell
python app.py
```

Or use the package development script:

```powershell
npm run dev:server
```

The package script starts Uvicorn on port `7000` with reload enabled.

## Testing

`run_tests.py` is the entry point. It selects which test files pytest runs; it
does not change, skip, or reorder any test, and the known-gap markers behave
exactly as `tests/conftest.py` documents.

```powershell
python run_tests.py                  # default lane, ~50s, 74 of 76 files
python run_tests.py geometry         # one group
python run_tests.py api chat         # several groups
python run_tests.py --changed        # files related to your uncommitted work
python run_tests.py --list           # groups, contents, and which are slow
python run_tests.py --all            # everything, ~10 min
```

Anything after `--` goes to pytest unchanged:

```powershell
python run_tests.py geometry -- -x -vv
python run_tests.py --all -- --durations=25
python run_tests.py --all -- -m "not spine_gap and not fixture_drift"
```

Groups are `geometry`, `ops`, `api`, `chat`, `catalog`, and `account`.

### Why there is a default lane

Two files are effectively the whole cost of the suite:

| File | Time | Dominated by |
|---|---|---|
| `test_mcp_tool_universe_gates.py` | ~500s | `test_trusted_token_lifts_the_cap_on_every_capped_tool` |
| `test_preprocessor_location_spine.py` | ~450s | `test_geometry_backed_query_location_samples` (435s alone) |

Everything else combined runs in about 50 seconds. Both slow files walk real
geometry over a broad sample rather than a fixture, which is what makes them
worth having and what makes them slow, so they are excluded from the default
lane rather than trimmed. They still run under `--all` and `--slow`, and they
should run before anything touching geometry resolution, the tool universe, or
access caps ships.

`run_tests.py --audit` fails if a test file belongs to no group, so a new file
cannot silently drop out of every group run. Run it if you add a test file.

Run one file or one test directly when you want no selection logic at all:

```powershell
python -m pytest tests/test_public_catalog_builder.py -q
python -m pytest tests/test_caller_identity.py::CallerIdentityTests -vv
```

Some repository tests may require optional data, provider credentials, or
runtime services. A focused deterministic unit test should accompany a local
contract change even when an integration environment is unavailable.

Before committing:

```powershell
git diff --check
git status --short
```

For JavaScript syntax checks, use Node's check mode on the changed module:

```powershell
node --experimental-default-type=module --check static/modules/auth.js
```

## Working with data

Do not commit local datasets, raw downloads, secrets, or generated caches to
the runtime repository.

Point `DATA_ROOT` to a separate data tree. Build its catalog with:

```powershell
python converters/catalog_builder.py "C:\path\to\your\data"
```

See [DATA_PREPARATION.md](DATA_PREPARATION.md).

## Change discipline

1. Identify the owning contract in [CONTEXT.md](CONTEXT.md).
2. Add a focused test that fails for the current behavior.
3. Make the smallest change at the shared owner.
4. Exercise the affected mode or route.
5. Run relevant unit tests and link/diff checks.
6. Update the owning public document when a contract changes.

Do not solve a shared source, geography, time, warning, or display problem with
mode-specific branching.

## Environment files

- `.env.example` is the single minimal GitHub/local starting point.
- local `.env` values must remain untracked.

Treat tokens, provider keys, storage credentials, and internal bridge secrets
as server-side secrets.

## Useful entry points

| Task | Start |
|---|---|
| Application startup | `app.py` |
| Route behavior | `mapmover/routes/` |
| Explore workflow | `mapmover/explore/` |
| Research workflow | `mapmover/research_service.py` and Research runtime modules |
| Ops workflow | `mapmover/ops/` and `mapmover/ops_*` |
| Shared execution | `mapmover/runtime/` and `mapmover/execution/` |
| Catalog loading | `mapmover/data_loading.py` |
| Geometry | `mapmover/geometry_handlers.py` and geography helpers |
| Browser behavior | `static/modules/` |
