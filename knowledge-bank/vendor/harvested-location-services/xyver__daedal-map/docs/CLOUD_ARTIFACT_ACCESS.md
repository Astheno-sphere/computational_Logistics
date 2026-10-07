# Cloud Artifact Access

DaedalMap uses one artifact access model across Research MCP, trusted dataset
queries, and researcher cloud downloads.

For local pack installation, start with
[DATA_INSTALLATION.md](DATA_INSTALLATION.md). Cloud artifact access covers
direct object reads.

For broad public discovery, start with the catalog endpoints instead of probing
object storage:

```text
GET https://app.daedalmap.com/api/v1/historical/catalog
GET https://app.daedalmap.com/api/v1/geometry/catalog
GET https://app.daedalmap.com/api/v1/feeds/catalog
GET https://app.daedalmap.com/api/v1/agent/catalog
```

Use artifact `HEAD`/`GET` only after discovery names a specific downloadable,
published, or staging object to inspect.

## Lane policy

| Lane | Access |
|---|---|
| `downloadable` | Anonymous, curated public artifacts |
| `published` | `ARTIFACT_ACCESS_TOKENS` bearer token |
| `staging` | `ARTIFACT_ACCESS_TOKENS` bearer token |
| `control` | Operator-only; never available through the researcher gateway |

Give researchers DaedalMap bearer tokens, not Cloudflare R2 access keys. R2
credentials stay on the hosted DaedalMap runtime.

## Gateway

The read-only gateway is:

```text
GET|HEAD https://app.daedalmap.com/api/artifacts/{lane}/{object_path}
```

Anonymous example:

```text
GET /api/artifacts/downloadable/packs/index.json
```

Protected example:

```http
GET /api/artifacts/published/catalog.json
Authorization: Bearer RESEARCHER_TOKEN
```

The same researcher token connects to Research MCP:

```text
https://app.daedalmap.com/mcp-private/research
```

The gateway supports `HEAD` and byte-range requests for large files. Protected
responses are marked private/no-store. Downloaded pack artifacts must still be
verified against the SHA-256 in their manifest.

## Token configuration

The hosted public runtime and private Research MCP service use the same Railway
variable:

```text
ARTIFACT_ACCESS_TOKENS=alice=long-random-token,bob=another-random-token
```

Labeled and unlabeled entries are supported. Labels appear in server-side audit
logs; raw token values do not.

Leave `RESEARCH_MCP_ACCESS_TOKENS` unset when Research MCP and cloud artifacts
share credentials. That optional override creates a separate token rail.

## Researcher handling

Give each researcher a distinct random token. The same token works in their
MCP client and artifact-download requests.

Rotating or removing that token revokes both Research MCP access and protected
`published`/`staging` reads.

Do not put tokens in Git, notebooks, screenshots, URLs, or downloadable
manifests. Send them only in the `Authorization` header.

## Pack install status

The anonymous downloadable installer uses the curated pack-level
`downloadable/packs/...` manifest contract. The Pack Store is the visual
version of the same flow. GitHub users can use a text assistant or script to
read the manifest, choose a pack, download the archive, verify it, and install
it into the local runtime.

The gateway gives authorized researchers read-only access to objects that
exist in `published/` and `staging/`. Installable protected channels need a
channel-specific pack index, current/version manifests, and verified pack
archives.

Use pack manifests and archives for installs. Raw catalogs are discovery
documents, not installable pack archives.

Future storefront note: `download.daedalmap.com` may become the browseable
storefront over the same pack registry/manifests. It should not define a
separate inventory from the downloadable pack manifest contract.

## Storage isolation

Put the `downloadable` lane behind a dedicated public bucket or production
custom domain. Keep `published`, `staging`, and `control` storage private and
reachable only through server-side credentials.

The gateway intentionally refuses `control` even when a valid researcher token
is supplied.
