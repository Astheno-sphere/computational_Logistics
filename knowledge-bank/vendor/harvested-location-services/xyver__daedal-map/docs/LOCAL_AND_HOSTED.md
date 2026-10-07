# Local And Hosted Deployment

DaedalMap can run locally or as a hosted application. Runtime data can live on
local storage or object storage. For Explore, Research, Ops, and Tutorial
behavior, see [RUNTIME_MODES.md](RUNTIME_MODES.md).

DaedalMap uses two environment settings:

- `INSTALL_MODE`: where the application is installed
- `RUNTIME_MODE`: where runtime data is read

## GitHub and wrapper installs

A GitHub clone and the downloadable wrapper are two entrances to the same local
runtime:

- GitHub is the direct developer/researcher installation path.
- The wrapper is the easier installation, update, storage, and pack-management
  front end.

Both use `INSTALL_MODE=local`. The wrapper is not a separate runtime
architecture. After installation, either path can use local data or explicitly
configured cloud-backed data.

For the simplest GitHub setup, copy the minimal template:

```powershell
Copy-Item .env.example .env
```

Edit `DATA_ROOT`. No model key, S3, R2, AWS, database, account, or
hosted-control-plane variables are needed for local data operations.

## Supported configurations

| Install | Data runtime | Use case |
|---|---|---|
| `local` | `local` | Research, development, and self-hosting with a local data tree |
| `local` | `cloud` | Local application testing against object storage |
| `cloud` | `cloud` | Hosted application with object-storage data |

`INSTALL_MODE=cloud` with `RUNTIME_MODE=local` is not a supported first-class
configuration.

## Local application and local data

Use:

```text
DEPLOYMENT=local
INSTALL_MODE=local
RUNTIME_MODE=local
DATA_ROOT=C:/path/to/your/data
```

Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` only when you want the built-in
local chat UI. Researchers using [Research MCP](RESEARCH_MCP.md) use the model
in their MCP-capable subscription client instead.

This is the clearest path for academic work:

- data stays on a machine or mounted volume you control;
- imported sources can be rebuilt and tested without cloud publication;
- local packs can be grouped into Research corpora;
- hosted account infrastructure is not required.

Local is not universally "better" than cloud-backed data. It is the natural
choice when privacy, reproducibility, offline control, custom imports, or
independence from hosted storage matter.

If `DATA_ROOT` is blank, the runtime uses the platform's default local
application-data folder. On Windows this is normally:

```text
%LOCALAPPDATA%\DaedalMap\data
```

The public source checkout does not include a full data tree, so a useful local
run needs data at that default location or an explicit `DATA_ROOT`.

### Local geography candidate

A server operator can test an unpublished geographic-reference graph through
the normal MCP surface without publishing or uploading it:

```text
DEPLOYMENT=local
STORAGE_MODE=local
DATA_ROOT=C:/path/to/data
GEOGRAPHY_REFERENCE_GRAPH_ROOT=geometry/countries/CAN/crosswalks/canada_reference_graph_candidate
```

Run the normal local server and connect the MCP client to its
`/mcp/geography` endpoint. No alternate geography server or tool contract is
used. Call `get_catalog` with `catalog="geometry"`, then call `get_pack` for the
selected family and country to inspect the admitted systems, releases, and
vintages before using the normal execution tools.

`GEOGRAPHY_REFERENCE_GRAPH_ROOT` is a process-launch setting, not an MCP tool
argument. A remote caller therefore cannot make a hosted server read an
arbitrary local path. The same pattern can support user-maintained compatible
bundles in a self-hosted runtime.

For the step-by-step data install flow, including the local Pack Store and
researcher artifact tokens, see [DATA_INSTALLATION.md](DATA_INSTALLATION.md).

## Local application and cloud data

Use:

```text
INSTALL_MODE=local
RUNTIME_MODE=cloud
```

Configure object storage using the variables documented in
[../.env.example](../.env.example).

In this configuration:

- metadata is hydrated or cached locally;
- Parquet can be queried remotely through DuckDB;
- local code exercises the same general data path as a cloud deployment.

Use storage and credentials you are authorized to access. A local installation
does not imply local data when `RUNTIME_MODE=cloud`.

## Cloud application and cloud data

Use:

```text
INSTALL_MODE=cloud
RUNTIME_MODE=cloud
```

This is the deployment shape for a hosted instance. The public runtime can be
deployed using infrastructure and object storage you control.

Hosted account, billing, admin, collector, and publication-control systems are
separate concerns and are not required to run the open runtime.

## Common local choices

Set:

- `DATA_ROOT` when your data is outside the default app-data folder;
- `INSTALL_MODE=local`;
- `RUNTIME_MODE=local` for local research data.

Optionally set one supported model-provider key for built-in local chat.

Leave `APP_URL` and `SITE_URL` unset unless the instance needs to advertise
specific external URLs.

Private hosted bridge variables are not needed for ordinary local operation.
Without them, `/settings` remains a local setup surface.

## Next steps

- [DATA_PREPARATION.md](DATA_PREPARATION.md) - prepare a source
- [PACK_AUTHORING.md](PACK_AUTHORING.md) - group sources into a pack
- [RESEARCH_MCP.md](RESEARCH_MCP.md) - use a subscription client for research
- [RUNTIME_MODES.md](RUNTIME_MODES.md) - choose Explore, Research, or Ops
- [DATA_SCHEMAS.md](DATA_SCHEMAS.md) - inspect the exact data contract
