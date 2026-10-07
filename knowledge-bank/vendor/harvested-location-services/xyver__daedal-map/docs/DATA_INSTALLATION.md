# Installing Data

Install maintained packs into a local DaedalMap runtime.

The GitHub checkout gives you the engine. Data lives in a local storage folder
or in a cloud artifact lane.

## Local install path

For a local GitHub install:

1. Choose a local storage folder.
2. Point `DATA_ROOT` at that folder, or set the storage root from `/settings`.
3. Install public packs from the downloadable pack manifest. A text assistant,
   helper script, or visual Pack Store can use the same manifest contract.
4. If you have a DaedalMap researcher token, use it for protected
   `published`/`staging` artifact downloads and Research MCP access.

You do not need Cloudflare R2, S3, AWS, database, or model-provider keys just
to install and use local data packs.

## Choose the local data folder

Copy the local environment template:

```powershell
cd county-map
Copy-Item .env.example .env
```

Set the local data path:

```text
DEPLOYMENT=local
INSTALL_MODE=local
RUNTIME_MODE=local
DATA_ROOT=C:/path/to/your/daedalmap-data
```

Use any folder you control. Large packs can be many gigabytes; choose a disk
with enough free space.

If `DATA_ROOT` is blank, DaedalMap uses the platform default application-data
folder. On Windows, that is normally:

```text
%LOCALAPPDATA%\DaedalMap\data
```

The related managed pack folder is normally:

```text
%LOCALAPPDATA%\DaedalMap\packs
```

## Install public packs

Packs install from manifests. A manifest tells DaedalMap what to download,
where it belongs, how large it is, and which checksums to verify.

The Pack Store is the visual version of this flow. A GitHub user can work
through the same manifest with an LLM or helper script:

1. list available packs from the manifest;
2. choose the pack and storage folder;
3. download the pack archive;
4. verify the manifest checksum;
5. install/activate it into the local runtime.

After starting the app:

```powershell
python app.py
```

Open:

```text
http://localhost:7000/settings
```

Use the local setup page to:

- confirm the current storage root;
- choose a future storage root if needed;
- review packs available from the downloadable pack manifest;
- install public downloadable packs.

The public downloadable flow uses the anonymous `downloadable` lane. Curated
public packs require no token.

After changing the storage root from `/settings`, restart the runtime. New
downloads then use the new folder.

## Use a researcher token

Some researchers receive a DaedalMap bearer token from the operator. Use it as
a DaedalMap access token. Ordinary local pack installation does not need it in
`.env`.

The same token is used for:

- hosted [Research MCP](RESEARCH_MCP.md);
- trusted dataset-query access;
- protected cloud artifact reads from the `published` and `staging` lanes.

Protected artifact requests use:

```http
Authorization: Bearer YOUR_RESEARCHER_TOKEN
```

Example:

```powershell
Invoke-WebRequest `
  -Uri "https://app.daedalmap.com/api/artifacts/published/catalog.json" `
  -Headers @{ Authorization = "Bearer YOUR_RESEARCHER_TOKEN" } `
  -OutFile "catalog.json"
```

Keep tokens out of Git, notebooks, screenshots, command history you plan to
share, and URLs. Send them only in the `Authorization` header.

## Install surfaces

DaedalMap has two download surfaces:

| Surface | What it is for | Token needed? |
|---|---|---|
| Downloadable pack manifest / Pack Store | Installing curated public packs into the local runtime | No |
| Cloud artifact gateway | Reading specific `downloadable`, `published`, or `staging` objects | Only for `published` and `staging` |

The Pack Store is the visual form of the manifest install path. Text-based
assistants and scripts use the same manifests.

The first Pack Store contract installs complete curated packs. It is not a
geography/time/metric custom-extract builder. Future custom dataset exports may
reuse the same metadata, provenance, checksum, and artifact-install primitives,
but they remain derived user artifacts rather than a second pack registry or a
replacement for complete pack downloads.

The cloud artifact gateway reads specific objects. Protected `published` and
`staging` pack channels need their own pack index, current/version manifests,
and verified archives before they behave like the anonymous Pack Store.

## If you want to import your own data

Custom research data enters through the same pack model:

1. Read [DATA_PREPARATION.md](DATA_PREPARATION.md).
2. Match the contracts in [DATA_SCHEMAS.md](DATA_SCHEMAS.md).
3. Group sources with [PACK_AUTHORING.md](PACK_AUTHORING.md).
4. Point `DATA_ROOT` at your local data tree and rebuild the catalog.

Local data authoring does not require DaedalMap cloud access.

## Related docs

- [LOCAL_AND_HOSTED.md](LOCAL_AND_HOSTED.md) - local versus cloud runtime setup
- [CLOUD_ARTIFACT_ACCESS.md](CLOUD_ARTIFACT_ACCESS.md) - artifact lanes and token policy
- [RESEARCH_MCP.md](RESEARCH_MCP.md) - subscription-client research workflow
- [PACK_AUTHORING.md](PACK_AUTHORING.md) - build/share your own packs
