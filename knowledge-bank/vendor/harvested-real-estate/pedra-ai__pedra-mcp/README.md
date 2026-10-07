# Pedra MCP Server

Official [Model Context Protocol](https://modelcontextprotocol.io) server for the [Pedra API](https://pedra.ai/api-documentation) — use Pedra's AI real-estate photo editing (virtual staging, renovation, room emptying, enhancement, sky replacement, object removal/blur, property videos, and hosted 360° virtual tours) directly from **Claude, ChatGPT, Cursor**, and any other MCP client.

[![npm version](https://img.shields.io/npm/v/@pedra-ai/mcp.svg)](https://www.npmjs.com/package/@pedra-ai/mcp)
[![Official MCP registry](https://img.shields.io/badge/MCP%20registry-pedra--mcp-blue)](https://registry.modelcontextprotocol.io)

[![Add to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](cursor://anysphere.cursor-deeplink/mcp/install?name=pedra&config=eyJjb21tYW5kIjoibnB4IiwiYXJncyI6WyIteSIsIkBwZWRyYS1haS9tY3AiXSwiZW52Ijp7IlBFRFJBX0FQSV9LRVkiOiJZT1VSX1BFRFJBX0FQSV9LRVkifX0=)

It exposes **one tool per API endpoint**. Each photo and video tool is a single blocking call that returns the final asset URL(s) — there are no job IDs to poll. Virtual tours build in the background: `pedra_create_virtual_tour` returns a `tourId`, and `pedra_get_virtual_tour` is polled until it's ready.

## Quick start

The server reads your Pedra API key (Settings in your [Pedra account](https://app.pedra.ai)) from the `PEDRA_API_KEY` environment variable. No account yet? Start it without a key — see [No Pedra account yet?](#no-pedra-account-yet).

The server runs over stdio and is published to npm, so most clients just run it with `npx` — no global install needed.

### Claude Desktop (one-click)

Download the latest **`pedra-mcp.mcpb`** from [Releases](https://github.com/pedra-ai/pedra-mcp/releases) and double-click it (or drag it into Claude Desktop → Settings → Extensions). Claude installs the bundled server and prompts for your `PEDRA_API_KEY` — no JSON editing.

### Claude Desktop (manual)

Or add this to your `claude_desktop_config.json` (Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "pedra": {
      "command": "npx",
      "args": ["-y", "@pedra-ai/mcp"],
      "env": { "PEDRA_API_KEY": "your-api-key" }
    }
  }
}
```

### Cursor

In `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project):

```json
{
  "mcpServers": {
    "pedra": {
      "command": "npx",
      "args": ["-y", "@pedra-ai/mcp"],
      "env": { "PEDRA_API_KEY": "your-api-key" }
    }
  }
}
```

### Any MCP client

Run the binary directly with the key in the environment:

```bash
PEDRA_API_KEY=your-api-key npx -y @pedra-ai/mcp
```

Or install it:

```bash
npm install -g @pedra-ai/mcp
PEDRA_API_KEY=your-api-key pedra-mcp
```

### Smithery

You can also install and configure Pedra automatically via [Smithery](https://smithery.ai/server/@pedra-ai/mcp):

```bash
npx -y @smithery/cli install @pedra-ai/mcp --client claude
```

(swap `claude` for `cursor`, `windsurf`, etc.) Smithery prompts for your `PEDRA_API_KEY` and writes the client config for you.

### No Pedra account yet?

Start the server without `PEDRA_API_KEY`, for example in Claude Code:

```bash
claude mcp add pedra -- npx -y @pedra-ai/mcp
```

Then just ask for something ("stage this photo with Pedra"). Without a key the server adds two tools, and the assistant does the rest:

1. `pedra_request_access` with your email. Pedra emails you a link (valid 30 minutes): a new account chooses a password there, an existing one clicks **Allow**. Nothing is created until you click, and you can decline.
2. `pedra_check_access` until you've confirmed. Once approved, every Pedra tool works for the rest of the session. The key is kept in memory only, never written to disk; the tool result shows it along with how to keep it: add it as `PEDRA_API_KEY` to the server's `env` (e.g. `claude mcp add pedra -e PEDRA_API_KEY=<key> -- npx -y @pedra-ai/mcp`, or paste it into the extension's settings in Claude Desktop).

Until then, the other tools answer "No API key yet: call pedra_request_access with the user's email". Inbox confirmation is required, disposable email domains are refused, and requests are rate-limited. New accounts start with Pedra's free trial credits.

(In ChatGPT and claude.ai, use Pedra's hosted connector instead: connecting it runs a sign-in where new users can create an account.)

## Tools

The nine image-editing tools (enhance through blur) also take `propertyId`, to save the result into that property's gallery, and `name`, to save the original photo there under that name in the same call. The result then includes `source` (`imageId`, `name`) of the original. `preserveAspectRatio` returns the result at the input's exact size.

| Tool | Endpoint | What it does |
|------|----------|--------------|
| `pedra_enhance` | `/enhance` | Improve lighting, color, sharpness |
| `pedra_enhance_and_correct_perspective` | `/enhance_and_correct_perspective` | Enhance + straighten perspective |
| `pedra_empty_room` | `/empty_room` | Remove all furniture/objects |
| `pedra_furnish` | `/furnish` | Virtually stage a room |
| `pedra_renovation` | `/renovation` | Renovate walls/floors/finishes |
| `pedra_edit_via_prompt` | `/edit_via_prompt` | Edit from a natural-language prompt |
| `pedra_sky_blue` | `/sky_blue` | Replace a dull sky with clear blue |
| `pedra_remove_object` | `/remove_object` | Remove an object using a mask |
| `pedra_blur` | `/blur` | Blur faces, license plates, etc. |
| `pedra_create_video` | `/create_video` | Render a property video from images |
| `pedra_update_video` | `/update_video` | Edit a video without re-rendering unchanged clips |
| `pedra_generate_voice_script` | `/generate_voice_script` | Write a voiceover script from property photos |
| `pedra_generate_voice` | `/generate_voice` | Turn a script into a voiceover audio track |
| `pedra_music_library` | `/music_library` | List background-music tracks, voice languages + narration voices |
| `pedra_list_properties` | `/list_properties` | List the account's properties |
| `pedra_list_property_images` | `/list_property_images` | List a property's photos (or, with `type: "360"`, its 360° photos) as URLs |
| `pedra_create_property` | `/create_property` | Create a property |
| `pedra_add_images_to_property` | `/add_images_to_property` | Add photos (or, with `type: "360"`, 360° photos) to a property by URL, optionally with `names` |
| `pedra_add_local_panoramas` | `/add_images_to_property` (batched) | **Local only:** upload 360° photo files from this computer into a property |
| `pedra_create_upload_link` | `/create_upload_link` | No-login page to upload photos or 360° photos from a phone or computer (`type: "360"` for tours only) |
| `pedra_create_virtual_tour` | `/create_virtual_tour` | Build a hosted 360° virtual tour (AI names and links the rooms) |
| `pedra_get_virtual_tour` | `/get_virtual_tour` | Tour status, share link, embed code, scenes, links |
| `pedra_list_virtual_tours` | `/list_virtual_tours` | List the account's virtual tours |
| `pedra_update_virtual_tour` | `/update_virtual_tour` | Rename, reorder, remove rooms, re-link, restyle (free) |
| `pedra_add_virtual_tour_scenes` | `/add_virtual_tour_scenes` | Add rooms to the end of a tour |
| `pedra_credits` | `/credits` | Read plan + remaining credits |
| `pedra_feedback` | `/feedback` | Thumbs up/down + optional credit-back |
| `pedra_request_access` | `/agent_signup` | **Only without an API key:** email the user a link to create/allow their account |
| `pedra_check_access` | `/agent_signup_status` | **Only without an API key:** check the request; once approved, every tool works for the session |

Most image tools take an `imageUrl` plus a few optional parameters; see each tool's input schema in your MCP client. The `imageUrl` (and `maskUrl`, and each `create_video` frame) accepts any of:

- a public `https://` URL,
- a `data:` URI, or
- an **absolute path to a local image file** — the server reads it off disk and inlines it as base64 for you, so you can point a tool at a file you just dragged in without hosting it first (`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.tif/.tiff`, `.heic/.heif`, `.avif`; up to 40 MB).

> Note: an image **pasted into the chat** is not a file path, so it can't be forwarded to the tool — drag in a file, or save the paste and pass its path. Photos on the user's phone go through `pedra_create_upload_link`: they upload on a no-login page (up to 100 files, 24 h), then `pedra_list_property_images` returns their URLs for editing, `pedra_create_video` or `pedra_create_virtual_tour`.

Uploads are limited per day: 30 images on the free plan, 500 on paid plans (reset at midnight UTC), counting every image stored from outside the app (`pedra_add_images_to_property`, `pedra_add_local_panoramas`, URL scenes in tours, upload-link files); over it the call fails with `HTTP 429, upload_limit` and nothing is stored. Upload links: 5 a day free, 50 paid (`upload_link_limit`).

Example prompts once connected:

> "Use Pedra to virtually stage https://example.com/empty-living-room.jpg as a minimalist living room."

> "Virtually stage /Users/me/Desktop/empty-living-room.jpg as a minimalist living room."

> "How many Pedra credits do I have left?"

## Virtual tours

POST your 360° photos, get back a hosted, linked, shareable virtual tour: AI names the rooms and places the door-to-door navigation points. The tour tools have the same names, descriptions and input schemas as Pedra's hosted MCP server (`https://app.pedra.ai/mcp`), so an agent behaves the same on either.

A typical flow:

1. **Get the 360° photos into a property.**
   - Files on this computer → `pedra_add_local_panoramas` with the paths in walking order. This tool exists only in this local server: it reads the files off disk and sends them base64-encoded, 10 per call under the API's 50 MB request limit. Files over ~33 MB can't go this way.
   - Photos on someone's phone (or big files) → `pedra_create_upload_link` with `type: "360"`, and hand over the `uploadUrl` (no login, valid 24 h).
   - Photos already online → skip this step and pass the URLs as `scenes`.
2. **Build it:** `pedra_create_virtual_tour` with the `propertyId` (uses every 360° photo in upload order) or with `scenes`. It returns a `tourId` straight away.
3. **Wait:** poll `pedra_get_virtual_tour` until `status` is `"ready"` (about 10 s per room) — then share `tourUrl` or embed `embedCode`. A `"failed"` build says why and costs nothing.
4. **Adjust** with `pedra_update_virtual_tour` (free, instant) or append rooms with `pedra_add_virtual_tour_scenes`.

Linking costs `max(3, ceil(rooms/3))` credits for `"sequential"` (default; each room to the next), 5–160 for `"smart"` (AI works out which rooms connect), and nothing for `"none"`. Deleting a tour is API-only (not exposed as a tool).

> "Make a Pedra virtual tour of Calle Mayor 12 from /Users/me/360/entrance.jpg, /Users/me/360/living.jpg and /Users/me/360/kitchen.jpg, in that order, and give me the link."

## How it works

This server is a thin wrapper over [`@pedra-ai/sdk`](https://www.npmjs.com/package/@pedra-ai/sdk), which encodes the API's contract details:

- **Synchronous by design (except virtual tours).** Every photo and video endpoint blocks and returns the final URL(s) in the response body. Even `pedra_create_video` polls server-side and returns the finished `videoUrl` inline (it can take up to ~10 minutes; the API keeps the connection alive with a heartbeat).
- **Errors are tool errors.** The API's 4xx responses (insufficient credits, bad image, …) come back as MCP tool errors with a readable message, not crashes.

## Privacy Policy

This server sends the image/video URLs and parameters you pass to the [Pedra API](https://pedra.ai) to perform the requested edit, authenticated with your `PEDRA_API_KEY`. Without a key, `pedra_request_access` sends the email address you give it to Pedra so Pedra can email you a confirmation link; a key obtained that way is held in memory for the session only. It stores no data itself. Data collection, usage, storage, retention, third-party sharing, and contact information are covered by Pedra's privacy policy: **https://pedra.ai/privacy**.

## License

MIT © Pedra
