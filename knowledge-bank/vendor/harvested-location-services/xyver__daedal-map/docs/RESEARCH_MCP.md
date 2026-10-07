# Research With The Hosted MCP

The recommended research path is to connect DaedalMap's hosted Research MCP to
an MCP-capable client whose model access is already covered by the researcher's
normal subscription.

In this arrangement:

- the client model performs reasoning and writes the answer;
- DaedalMap provides deterministic source discovery and evidence queries;
- no OpenAI or Anthropic API key is needed in the local DaedalMap `.env`;
- the MCP does not hide a second server-side research model call.

## Hosted endpoint

```text
https://app.daedalmap.com/mcp-private/research
```

The transport is Streamable HTTP. The endpoint requires a DaedalMap bearer
token. This private-pilot token is not a model-provider API key.

The same token also authorizes read-only `published` and `staging` artifact
access through the [cloud artifact gateway](CLOUD_ARTIFACT_ACCESS.md).

Never commit a bearer token to Git, `.mcp.json`, documentation, notebooks, or
shared screenshots.

## Responsibility split

| Component | Responsibility |
|---|---|
| Researcher's MCP client | Reasoning, synthesis, conversation, and model subscription |
| Research MCP | Source discovery, bounded corpus preparation, query contracts, and evidence rows |
| DaedalMap runtime | Deterministic geography, time, metric, validation, and dataset execution |

Researchers use the model access they already have in their MCP client.
DaedalMap supplies source discovery, query contracts, and evidence rows.

## Research workflow

The MCP advertises six tools:

1. `how_research_mcp_works`
2. `search_research_sources`
3. `resolve_research_corpus_intent`
4. `get_research_pack`
5. `ask_research_sources`
6. `query_research_source_data`

A grounded workflow is:

1. Search or resolve relevant packs and sources.
2. Confirm an explicit source boundary.
3. Prepare the bounded research corpus.
4. Inspect source IDs and versions.
5. Read each selected pack's query contract.
6. Request deterministic evidence rows.
7. Let the client model reason over returned evidence.
8. Keep outside model knowledge distinct from MCP-returned facts.

Do not silently broaden from the selected corpus to the full catalog.

## Client setup

Each researcher needs an MCP-capable client, model access in that client, the
endpoint URL, and a valid DaedalMap bearer token.

For Claude Code, the connection shape is:

```powershell
claude.cmd mcp add --transport http --scope user research https://app.daedalmap.com/mcp-private/research --header "Authorization: Bearer YOUR_TOKEN"
```

Use the equivalent Streamable HTTP MCP configuration in another supported
client. Reconnect after a server update so the client refreshes its tool list.

## Relationship to the local runtime

The GitHub runtime remains useful for importing local data, authoring packs,
reproducing deterministic results, inspecting maps, and developing runtime
features.

Local data operations require no model key. Set an OpenAI or Anthropic key only
if you want the built-in local chat interface to perform reasoning.

The hosted Research MCP queries the hosted published source catalog. Local
sources in a researcher's `DATA_ROOT` need a self-hosted MCP path or secure
local bridge.

## Boundaries

- Access is token-gated rather than self-service.
- Evidence is limited to MCP-published packs and source contracts.
- Client quality and MCP support vary.
- Researchers must inspect provenance, versions, scope, and warnings.
- A subscription-client MCP workflow is not automatically offline.
