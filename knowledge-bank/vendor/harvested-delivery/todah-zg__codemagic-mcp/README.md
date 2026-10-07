# codemagic-mcp

An MCP (Model Context Protocol) server that gives AI agents a unified surface over **Codemagic CI/CD** and **App Store Connect / Google Play**, enabling a complete mobile app delivery pipeline — from onboarding a repository through building, signing, and publishing — driven by conversation.

[![codemagic-mcp MCP server](https://glama.ai/mcp/servers/todah-zg/codemagic-mcp/badges/card.svg)](https://glama.ai/mcp/servers/todah-zg/codemagic-mcp)

[![codemagic-mcp MCP server](https://glama.ai/mcp/servers/todah-zg/codemagic-mcp/badges/score.svg)](https://glama.ai/mcp/servers/todah-zg/codemagic-mcp)

## What it does

The server exposes tools across five domains:

- **Codemagic** — list teams and apps, trigger builds, wait for results, retrieve artifacts, fetch build logs, manage variable groups, caches, and webhooks
- **App Store Connect** — manage TestFlight, upload and submit builds, set listing text and screenshots, validate, submit, and release to the App Store
- **Google Play** — publish AABs, promote releases, manage staged rollouts, set listing text and screenshots, read and reply to user reviews
- **Testing** — parse JUnit XML test results from any Codemagic build; get a pass/fail/error/skip summary with per-failure details
- **Cross-store** — validate localized release notes against platform char limits and BCP-47 locale codes

The intended end-to-end flows are:

**iOS:** `list_asc_builds` → `get_yaml_template` → `trigger_build` → `wait_for_build` → `upload_build_to_asc` → `set_version_metadata` → `validate_app_submission` → `submit_for_app_store_review` → `release_version`

**Android:** `get_latest_build_number` → `get_yaml_template` → `trigger_build` → `wait_for_build` → `upload_to_google_play` → `promote_google_play_release`

## Prerequisites

- **Node.js** 20 or 22 (LTS)
- **asc CLI** — [asccli.sh](https://asccli.sh) — required for App Store Connect tools
- **google-play CLI** — part of [codemagic-cli-tools](https://github.com/codemagic-ci-cd/cli-tools) — required for Google Play tools
  ```
  pip install codemagic-cli-tools
  ```

## Environment variables

### Required

| Variable | Description |
|----------|-------------|
| `CODEMAGIC_API_TOKEN` | Your Codemagic API token. Found in Codemagic → Account settings. |

### App Store Connect tools (iOS)

| Variable | Description |
|----------|-------------|
| `ASC_KEY_ID` | App Store Connect API key ID |
| `ASC_ISSUER_ID` | App Store Connect issuer ID |
| `ASC_PRIVATE_KEY_B64` | Base64-encoded `.p8` private key (`base64 -i AuthKey_XXXX.p8`) |
| `ASC_BYPASS_KEYCHAIN` | Set to `1` to force env var auth instead of the macOS keychain |

### Google Play tools (Android)

| Variable | Description |
|----------|-------------|
| `GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS` | Raw JSON content of your Google Play service account key file |

For the Google Play credentials you can use the `@file:` prefix to avoid pasting JSON inline:
```
GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS=@file:/path/to/service-account.json
```

## Installation

### Using npx (recommended)

No installation needed. Add the server to your MCP client config with `npx` and it downloads and runs automatically:

```json
"command": "npx",
"args": ["-y", "codemagic-mcp-server"]
```

See the Claude Desktop section below for the full config.

### Global install
If you prefer a permanent install instead of npx:

```bash
npm install -g codemagic-mcp-server
```

Then use codemagic-mcp as the command in your MCP client config:

```json
"command": "codemagic-mcp",
"args": []
```

### Development
To build from source:

```bash
git clone https://github.com/todah-zg/codemagic-mcp.git
cd codemagic-mcp
npm install
npm run build
```

Then use the local path in your MCP config — see [Running from a local clone](#running-from-a-local-clone) below.

## Running

### MCP Inspector (development / testing)

Set the required environment variables in your shell, then:

```
npx @modelcontextprotocol/inspector node dist/index.js
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

**If installed from npm**

```json
{
  "mcpServers": {
    "codemagic": {
      "command": "npx",
      "args": ["-y", "codemagic-mcp-server"],
      "env": {
        "CODEMAGIC_API_TOKEN": "your-token",
        "ASC_KEY_ID": "your-key-id",
        "ASC_ISSUER_ID": "your-issuer-id",
        "ASC_PRIVATE_KEY_B64": "base64-encoded-p8-key",
        "ASC_BYPASS_KEYCHAIN": "1",
        "GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS": "@file:/path/to/service-account.json"
      }
    }
  }
}
```

**If running from a local clone (development):**

```json
{
  "mcpServers": {
    "codemagic": {
      "command": "node",
      "args": ["/absolute/path/to/codemagic-mcp-server/dist/index.js"],
      "env": {
        "CODEMAGIC_API_TOKEN": "your-token",
        "ASC_KEY_ID": "your-key-id",
        "ASC_ISSUER_ID": "your-issuer-id",
        "ASC_PRIVATE_KEY_B64": "base64-encoded-p8-key",
        "ASC_BYPASS_KEYCHAIN": "1",
        "GOOGLE_PLAY_SERVICE_ACCOUNT_CREDENTIALS": "@file:/path/to/service-account.json"
      }
    }
  }
}
```

The config file is at:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

## Using with Claude Desktop

### Connecting the server

To verify the server is connected, open a new conversation and ask: *"ping the codemagic mcp server"*. If connected, Claude will call the `ping` tool and respond with "Codemagic MCP server is running." If not connected, check that the path in `args` is correct and that all required environment variables are set, then restart Claude Desktop with Cmd+Q (not just closing the window).

If the server does not appear, check that the `CODEMAGIC_API_TOKEN` environment variable is set correctly in the config and that the path to `dist/index.js` is absolute and correct.

### Workflow prompts

Once connected, type `/` in the Claude Desktop input field to open the command picker. You will see five workflow prompts from this server:

| Prompt | When to use |
|--------|-------------|
| `/onboarding` | Starting from scratch — connect a repo, get a first build passing |
| `/android_release` | Build a signed AAB and publish it to Google Play |
| `/ios_release` | Build a signed IPA and upload it to TestFlight |
| `/first_publish_ios` | One-time setup for first-time iOS App Store publishers — Apple Developer enrollment, app record, age rating, privacy labels |
| `/first_publish_android` | One-time setup for first-time Google Play publishers — Play account, content rating, closed testing period |

Select a prompt and Claude will receive a step-by-step playbook and begin executing the workflow using the available tools.

### Example conversations

You can also describe what you want in plain language — Claude will select the right tools automatically:

> "I have a Flutter app at github.com/example/myapp. Set it up on Codemagic and get a first build running."

> "Trigger a release build for my Android app, version 2.1.0. The last build number on Google Play was 41."

> "What is the current App Store review status for my iOS app?"

### Config file location

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

## Tools

### Codemagic

| Tool | Description |
|------|-------------|
| `ping` | Check that the server is running |
| `list_teams` | List teams the authenticated account belongs to |
| `list_applications` | List apps in your Codemagic account or team |
| `list_workflows` | List workflows for an app |
| `list_builds` | List builds with optional filters (app, status, branch, workflow) |
| `get_build` | Get full details for a single build including artifacts |
| `get_build_logs` | Fetch per-step log text for a build — by default returns failed steps only |
| `trigger_build` | Trigger a build; optionally supply an inline `codemagic.yaml` or override `instance_type` |
| `wait_for_build` | Single-check tool — returns status immediately; call again until terminal state |
| `cancel_build` | Cancel a running or queued build |
| `add_application` | Connect a Git repository to Codemagic; auto-generates SSH deploy keys for SSH URLs |
| `get_webhook_url` | Get the incoming webhook URL to paste into your Git provider settings |
| `list_webhooks` | List webhook subscriptions configured for an app |
| `delete_webhook` | Delete a webhook subscription from an app |
| `list_caches` | List build caches for an app |
| `delete_cache` | Delete all caches or a specific cache by ID |
| `create_public_artifact_url` | Create a time-limited public download URL for a build artifact |

### App Store Connect (iOS)

| Tool | Description |
|------|-------------|
| `list_asc_apps` | List apps in App Store Connect |
| `list_asc_builds` | List TestFlight builds for an app |
| `list_testflight_groups` | List TestFlight beta groups |
| `get_asc_review_status` | Get the App Store review state for an app |
| `get_asc_release_status` | Full release pipeline dashboard (builds, TestFlight, App Store) |
| `upload_to_testflight` | Download an IPA from Codemagic and upload to TestFlight |
| `submit_beta_review` | Submit a TestFlight build for external beta review (required before external groups) |
| `add_testflight_tester` | Add a tester by email to TestFlight, optionally to a group |
| `create_testflight_group` | Create an internal or external TestFlight beta group |
| `set_export_compliance` | Declare encryption usage for a build (required before App Store submission) |
| `set_version_metadata` | Set "What's New" text and other per-locale metadata for an App Store version |
| `validate_app_submission` | Preflight check — returns an ordered list of blockers before submission |
| `upload_build_to_asc` | Upload an IPA to App Store Connect (fast, non-blocking); poll `list_asc_builds` until VALID |
| `submit_for_app_store_review` | Attach a processed build to a version and submit for App Store review |
| `release_version` | Release an approved App Store version immediately |
| `set_phased_release` | Create, pause, resume, or complete a phased rollout |
| `get_ios_store_listing` | Pull current App Store listing text for all locales (name, description, keywords, etc.) |
| `set_ios_store_listing` | Update App Store listing text for a locale — only provided fields are changed |
| `list_ios_screenshot_types` | List supported screenshot device types and their required pixel dimensions |
| `upload_ios_screenshots` | Download screenshots from URLs and upload to App Store Connect for a device type and locale |

### Google Play (Android)

| Tool | Description |
|------|-------------|
| `list_google_play_tracks` | List tracks (internal, alpha, beta, production) with release info |
| `list_google_play_bundles` | List uploaded AABs by version code |
| `upload_to_google_play` | Download an AAB from Codemagic and publish to a Google Play track |
| `get_latest_build_number` | Get the highest version code across all (or specified) tracks |
| `promote_google_play_release` | Promote a release between tracks (internal → alpha → beta → production) |
| `set_rollout_fraction` | Expand, halt, or resume a staged rollout by setting the user fraction |
| `share_app_internally` | Upload an AAB to Internal App Sharing for instant QA install links |
| `get_android_store_listing` | Fetch current Google Play store listing for a language (title, descriptions) |
| `set_android_store_listing` | Update Google Play store listing for a language — only provided fields are changed |
| `upload_android_screenshots` | Download screenshots from URLs and upload to Google Play for a language and device type |
| `set_android_data_safety` | Submit the data safety declaration CSV (exported from Play Console) — re-upload when data practices change |
| `list_google_play_reviews` | List recent user reviews with optional star rating filter (e.g. 1–2 stars only); includes developer reply status and review IDs |
| `reply_to_google_play_review` | Post or update a developer reply to a user review (max 350 characters) |

### Testing

| Tool | Description |
|------|-------------|
| `get_test_results` | Fetch and parse JUnit XML test results from a Codemagic build — returns a pass/fail/error/skip summary with per-failure details and stack trace excerpts. Covers Flutter, Android instrumented tests, and iOS (via xcresult conversion). Pass `artifact_url` directly if you already have it from `wait_for_build`. |

### Cross-store

| Tool | Description |
|------|-------------|
| `prepare_release_notes` | Validate localized release notes — checks BCP-47 locale codes and char limits (Android: 500, iOS: 4000) |
| `check_publish_readiness` | Aggregate publish-readiness checks for iOS or Android. API-verifiable items (valid build, listing completeness, binary validation) run live; items with no API (age rating, privacy labels, legal agreements) are always listed as human-required. Each item is tagged as 'agent can fix' or 'human required'. |

### Variable Groups

| Tool | Description |
|------|-------------|
| `list_variable_groups` | List variable groups for a team or app |
| `create_variable_group` | Create a new variable group (team or app scoped) |
| `add_variable` | Add a non-secret variable to a group |
| `list_variables` | List variables in a group (required to get IDs before updating or deleting) |
| `update_variable` | Update the name or value of a variable by ID |
| `delete_variable` | Delete a variable from a group by ID |

### YAML

| Tool | Description |
|------|-------------|
| `validate_codemagic_yaml` | Validate a `codemagic.yaml` against the official Codemagic JSON schema |
| `get_yaml_template` | Get a starter `codemagic.yaml` for android, ios, flutter, flutter-native, react-native, ionic-capacitor, ionic-cordova, kmm, snap, unity, unity-oculus, dotnet-maui, ios-screenshots, android-screenshots, flutter-screenshots — plus android-debug, flutter-android-debug, react-native-android-debug for initial onboarding |
| `list_yaml_template_types` | List all supported project types for `get_yaml_template` |
| `detect_project_type` | Detect the project type from a repository file listing — returns the recommended template and debug template to start with |

### Prompts

| Prompt | Description |
|--------|-------------|
| `onboarding` | Zero to first debug build — add repo, get template, trigger build, configure webhook |
| `android_release` | Signed AAB from build to Google Play — build number, template, trigger, publish, promote |
| `ios_release` | Signed IPA from build to App Store — build number, template, trigger, TestFlight, metadata, validate, submit, release |
| `first_publish_ios` | One-time setup checklist for first-time iOS publishers — Apple Developer enrollment, app record, age rating, privacy labels, then hands off to /ios_release |
| `first_publish_android` | One-time setup checklist for first-time Android publishers — Play account, content rating, closed testing period, then hands off to /android_release |

Prompts are reusable workflow playbooks. In Claude Desktop they appear as slash commands. An agent can also invoke them by name to get step-by-step instructions for a complete workflow.

## Project structure

```
src/
  index.ts              — Server setup, env validation, transport
  codemagic.ts          — Codemagic API functions (v3 + v1)
  asc.ts                — App Store Connect CLI wrapper
  googleplay.ts         — Google Play CLI wrapper
  androidpublisher.ts   — Google Play androidpublisher REST API client (listings, screenshots, reviews)
  testing.ts            — JUnit XML parser (no external dependencies)
  ssh.ts                — SSH key generation and deploy key setup
  yaml.ts               — YAML validation logic
  templates.ts          — Static codemagic.yaml templates
  detection.ts          — Project type detection from repository file listings
  prompts.ts            — MCP prompt resources (workflow playbooks)
  tools/
    codemagic.ts        — Codemagic MCP tool registrations
    asc.ts              — App Store Connect MCP tool registrations
    googleplay.ts       — Google Play MCP tool registrations
    yaml.ts             — YAML MCP tool registrations
    releasenotes.ts     — Release notes validation tool
    readiness.ts        — Publish readiness check tool
    testing.ts          — Test results tool
```

The `src/` modules contain pure functions (API calls, CLI wrappers) with no MCP dependency.
The `src/tools/` modules wire those functions up as MCP tools — input schemas, formatting, error responses.

## Notes

- **Inline YAML:** `trigger_build` accepts an optional `yaml_content` parameter. When provided, the YAML is uploaded alongside the build request and does not need to exist in the repository. Useful for agent-generated configurations.
- **Build numbers:** Templates use `$BUILD_NUMBER` and `$VERSION_NAME` as plain variables — no store lookups happen inside the YAML. The agent determines the correct values via `list_asc_builds` or `list_google_play_tracks` before triggering, then passes them through the `variables` parameter of `trigger_build`.
- **Signing:** iOS signing happens on the Codemagic build machine (macOS + keychain). The MCP server never handles signing identities directly.
- **Team vs. personal account:** `list_applications` and `list_builds` accept an optional `team_id`. Without it, they operate on the authenticated user's personal account.
- **Variable groups and secrets:** `add_variable` only creates non-secret variables. Secret values (API keys, certificates, tokens) should be added directly in the Codemagic UI — secrets should never pass through the agent. Once set up, reference groups by name in `trigger_build` via the `groups` parameter.
