# Changelog

## 0.6.0

- **Save edits into a property.** The nine image-editing tools
  (`pedra_enhance` … `pedra_blur`) accept `propertyId`, `name` and
  `preserveAspectRatio`, with the same wording as Pedra's hosted MCP server.
  With `propertyId` the result is saved into that property's gallery; with
  `name` too, the original photo is saved there under that name in the same
  call. Results include `source` (`imageId`, `name`) when available.
- `pedra_add_images_to_property` accepts `names`, one per image.
- Requires `@pedra-ai/sdk` 0.5.0.

## 0.5.1

- **Security:** removed `src/remote.ts` (`dist/remote.js`, `npm run start:remote`), an unused prototype HTTP transport. It served the same tools as the local stdio server, including the ones that read local files, to any network caller, before the API key was checked. Reported by Syed Anas Mohiuddin. Pedra's hosted MCP server (`https://app.pedra.ai/mcp`) runs separately and was never affected. This package is now stdio only: local files are only read for the local user running it.

## 0.5.0

- **Virtual tours.** Six new tools with the same names, descriptions, input
  schemas and annotations as Pedra's hosted MCP server:
  `pedra_create_upload_link`, `pedra_create_virtual_tour`,
  `pedra_get_virtual_tour` (read-only), `pedra_list_virtual_tours`
  (read-only), `pedra_update_virtual_tour` (destructive), and
  `pedra_add_virtual_tour_scenes`. Deleting a tour stays API-only.
- **`pedra_add_local_panoramas`** (local server only): uploads 360° photo files
  from this computer's disk into a property, in order, batched under the API's
  10-per-call and 50 MB limits — the local alternative to an upload link.
- `pedra_list_property_images` and `pedra_add_images_to_property` accept
  `type: "photo" | "360"`.
- `pedra_generate_voice` accepts `voiceId`; `pedra_music_library` returns the
  narration voices per language.
- **Starts without `PEDRA_API_KEY`.** It used to exit; now it adds
  `pedra_request_access` ({ email, agentName? }) and `pedra_check_access`
  ({ requestId }) for agent signup: Pedra emails the user a link (new users
  create their account there). Once approved, the key is kept in memory for the
  session (never written to disk) and every tool works immediately; the result
  tells the user how to persist it as `PEDRA_API_KEY`. Until then, other tools
  return "No API key yet: call pedra_request_access with the user's email". The
  API key is now optional in `manifest.json`, `server.json` and `smithery.yaml`.
- `pedra_create_upload_link` takes `type: "any" | "360"` and now covers regular
  photos too (editing, videos, tours); its description, and those of
  `pedra_create_property`, `pedra_add_images_to_property` and the image tools'
  `imageUrl`, mirror the hosted server (minus ChatGPT's file attachments, which
  don't apply to a local server).
- API errors include the response `code` (e.g. `HTTP 429, upload_limit`).
- Requires `@pedra-ai/sdk` ^0.4.0. `manifest.json` now lists every tool.

## 0.2.1

- Add a bundle `icon.png` (512×512) and reference it from `manifest.json` so the
  server displays with the Pedra logo in Claude Desktop and the Anthropic MCP
  directory. Also ship the icon in the npm tarball (`files`) for registries that
  ingest the icon from npm. No runtime/tool changes.

## 0.2.0

- Image inputs now accept a **local file path**, not just a URL or `data:` URI.
  When `imageUrl`/`maskUrl` (and each `create_video` frame) is a local path, the
  server reads the file and inlines it as a base64 `data:` URI before calling the
  API — so you can point a tool at a file you dragged in without hosting it first.
  Handles `file://`, `~`, and quoted/space-escaped paths; supports common image
  types up to 40 MB; unsupported types and unreadable files surface as clear tool
  errors. (Pasting an image into the chat is unchanged — that's not a file path,
  so pass a path or URL.)

## 0.1.2

- Add behavioral annotations to every tool (`readOnlyHint`/`destructiveHint`/
  `openWorldHint` + `title`) — `pedra_credits` is read-only; the rest create
  new assets and are non-destructive. Required for the Claude connectors
  directory.
- Add `manifest.json` + `.mcpbignore` so the server can be packaged as a Claude
  Desktop Extension (`.mcpb`) — self-contained bundle, one-click install,
  `PEDRA_API_KEY` collected via `user_config`.
- README: Privacy Policy section + one-click `.mcpb` install instructions.

## 0.1.1

- Add MCP registry artifacts: `server.json` (official registry manifest) and
  `smithery.yaml` (Smithery stdio config).
- Add `mcpName` (`io.github.pedra-ai/pedra-mcp`) to `package.json` to prove npm
  package ownership to the official registry.
- Add `.github/workflows/release.yml`: a tagged release now publishes to npm
  (with provenance) and to the official MCP registry via GitHub OIDC.
- No runtime/tool changes.

## 0.1.0

- Initial release.
- MCP server exposing one tool per Pedra API endpoint: `pedra_enhance`,
  `pedra_enhance_and_correct_perspective`, `pedra_empty_room`, `pedra_furnish`,
  `pedra_renovation`, `pedra_edit_via_prompt`, `pedra_sky_blue`,
  `pedra_remove_object`, `pedra_blur`, `pedra_create_video`, `pedra_credits`,
  `pedra_feedback`.
- Thin wrapper over [`@pedra-ai/sdk`](https://www.npmjs.com/package/@pedra-ai/sdk):
  each tool is a single blocking call that returns the final asset URL(s).
- API key via the `PEDRA_API_KEY` environment variable; the API's 4xx errors
  (insufficient credits, bad image, …) surface as MCP tool errors.
- stdio transport; runs via `npx -y @pedra-ai/mcp`.
