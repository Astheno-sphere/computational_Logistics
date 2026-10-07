# BYOK credential profiles runbook (F2B.AC1, F2B.AC3)

Vessel Traffic MCP supports Bring-Your-Own-Key (BYOK) credentials for paid
or rate-limited vessel data providers. Credentials live entirely on the
operator's machine; the MCP surface only exposes labels, declared field
names, provider hints, and status — never the raw secret material.

## Sources

The credential profile loader reads from two sources and merges them:

1. **Environment variables** matching the pattern:

   ```
   VESSEL_MCP_PROFILE_<LABEL>__<FIELD>=<value>
   ```

   - `<LABEL>` is uppercased in the env var name; the loader normalizes it
     to lowercase and replaces underscores with dashes for the profile
     label (e.g. `MARINETRAFFIC_PROD` becomes `marinetraffic-prod`).
   - `<FIELD>` is one of: `provider`, `api_key`, `username`, `password`,
     `bearer_token`, `client_id`, `client_secret`, `subscription_key`.
   - Unknown field names are silently ignored to prevent typos from
     becoming visible signals.
   - Empty string values are treated as "not set".

2. **Local gitignored JSON config** at `config/credential-profiles.local.json`:

   ```json
   {
     "profiles": [
       {
         "label": "marinetraffic-prod",
         "provider": "marinetraffic",
         "fields": { "api_key": "..." }
       },
       {
         "label": "aisstream-dev",
         "provider": "aisstream",
         "fields": { "bearer_token": "..." }
       }
     ]
   }
   ```

   This file is in `.gitignore`. Do not commit it.

When the same label appears in both sources, the **environment value wins**.
Operators can override a local profile temporarily by exporting the env
form without editing the file.

## What MCP clients see

The read-only `credential_profiles` MCP tool returns a payload of the form:

```json
{
  "profiles": [
    {
      "label": "marinetraffic-prod",
      "provider": "marinetraffic",
      "source": "env",
      "fieldsPresent": ["api_key"],
      "status": "configured"
    }
  ],
  "summary": { "total": 1, "configured": 1, "incomplete": 0, "fromEnv": 1, "fromLocalConfig": 0 },
  "notes": [
    "Profile values are redacted; only labels, provider hints, declared fields, and status are exposed.",
    "..."
  ]
}
```

The tool is annotated `readOnlyHint: true`, `destructiveHint: false`. It
accepts no arguments and performs no network I/O.

For setup guidance, call the read-only `provider_onboarding` MCP tool.
It returns provider signup/API-doc URLs, required env vars, default
profile labels, configured status, missing fields, and validation
steps. It intentionally does not create accounts, accept terms, solve
CAPTCHA, complete email verification, set payment details, or issue API
keys.

## Hard rules

- **Never log raw secrets.** Internal log messages route through
  `src/util/redact.ts`, which scrubs `VESSEL_MCP_PROFILE_*` values along
  with `authorization: bearer ...`, cookies, and `api_key=...` style
  fragments.
- **MCP tool output is the labels-only contract.** The
  `CredentialProfileSummary` type has no `fields`/`value` member. Raw
  secrets are reachable only via `CredentialStore.resolveSecret(label, field)`
  inside provider adapters and are never serialized to JSON.
- **Local config stays local.** `config/credential-profiles.local.json` is
  gitignored; do not commit it. The `.env.example` template documents the
  env form but contains no real values.
- **MCP tools must remain read-only.** This tool only reads the loaded
  store. It cannot register, mutate, or delete a profile, and it never
  triggers a provider call.

## Verifying

Run from the project root:

```
npm run lint
npm test
npm run build
```

The `test/credential-profiles.test.js` suite covers:

- env-only and local-config-only loading,
- env-wins-on-label-collision merging,
- unknown field rejection and empty value handling,
- malformed JSON rejection,
- MCP tool payload shape and absence of secrets in `content[0].text`,
- `redactForLog` scrubbing of `VESSEL_MCP_PROFILE_*` log fragments.

The test suite does not call any live or paid provider; verification is
deterministic and fixture-only.

## One-time request credential path (F2B.AC3)

In addition to env vars and the gitignored local config, the routing layer
supports a **disabled-by-default, in-memory-only** one-time credential
overlay. This is intended for ad-hoc operator sessions where pasting a
short-lived key into a single MCP request is preferable to writing it to
disk.

### How it is gated

The path is **off by default**. To enable it for the lifetime of the
current process, set:

```
export VESSEL_MCP_ONE_TIME_CREDENTIALS=enabled
```

Accepted opt-in tokens (case-insensitive, trimmed): `1`, `true`, `on`,
`enabled`, `yes`. Any other value — including unset, empty string, `0`,
`no`, `off`, `disabled` — leaves the path refused.

When the gate is off and a request includes `oneTimeCredential`, the
routing layer returns a structured `no_credential_profile` result and the
raw key is never inspected, logged, or echoed.

### How the overlay behaves

When enabled and supplied, a request can include:

```jsonc
{
  "provider": "marinetraffic",
  "fallbackPolicy": "strict",
  "oneTimeCredential": {
    "providerId": "marinetraffic",
    "label": "one-time-request",
    "fields": { "api_key": "<redacted-in-logs>" }
  }
}
```

The router wraps the persistent `CredentialStore` in an in-memory overlay
for that single resolution:

- `list()` on the overlay returns **only** the persistent profiles — the
  one-time entry is intentionally invisible to the `credential_profiles`
  MCP tool and to anything that calls `list()`.
- `get(label)` returns a summary marked `source: "one-time"` for the
  overlay label, and falls through to the base store for other labels.
- `resolveSecret(label, field)` returns the overlay value for the
  one-time label, and falls through to the base store otherwise.

The overlay is created for the duration of a single `resolveProvider`
call. It is not persisted to disk, not written back to the base store,
and not exposed by any MCP tool. Repeated calls without the
`oneTimeCredential` input do not see it.

### Redaction guarantees

- `redactForLog` scrubs `api_key=`, `password=`, `token=`, `Authorization:
  Bearer ...`, `subscription_key=`, and `VESSEL_MCP_PROFILE_*` fragments
  from any string the logger touches.
- The structured `createJsonLogger` redacts fields named after any of the
  `sensitiveKeyPatterns` (e.g. `api_key`, `bearer_token`, `password`,
  `subscription_key`, `credential`, `Authorization`, `cookie`) — both
  top-level and nested.
- Error messages constructed with template strings must be passed
  through `redactForLog` before being surfaced. Adapter authors should
  treat any string built from `resolveSecret(...)` as toxic until
  redacted.

### Hard rules for the one-time path

- **In-memory only.** Never write the one-time fields to disk, never echo
  them back through MCP responses, never include them in the
  `credential_profiles` payload.
- **No silent persistence.** The overlay must not mutate the base store
  and must not survive across requests.
- **Refusal is the default.** Treat `oneTimeCredential` as ignored unless
  `VESSEL_MCP_ONE_TIME_CREDENTIALS` is set to an opt-in token.

## Paid BYOK REST adapters (F4.AC4)

Paid commercial providers (MarineTraffic, VesselFinder, Spire,
ORBCOMM/CommTrace, VesselAPI, Data Docked, Poseidon AIS, …) must use a
redacted BYOK credential profile. Simple REST providers can share the
template at `src/providers/paid-byok-rest.ts`; richer providers may use
custom modules as long as they keep the same credential, throttle, and
redaction guarantees.

Implemented adapters ship behind credential profiles:

| Provider | Module | Credential profile field | Env var slot | Auth style |
| --- | --- | --- | --- | --- |
| MarineTraffic | `src/providers/marinetraffic.ts` | `api_key` | `VESSEL_MCP_PROFILE_MARINETRAFFIC__API_KEY` | Path segment in `/api/{product}/{version}/{api_key}` |
| VesselFinder  | `src/providers/vesselfinder.ts`  | `api_key` | `VESSEL_MCP_PROFILE_VESSELFINDER__API_KEY`  | Query parameter `?userkey=…` |
| SeaRates Ship Schedules | `src/providers/searates.ts` | `api_key` | `VESSEL_MCP_PROFILE_SEARATES_SCHEDULES__API_KEY` | Header `X-API-KEY` |
| Routescanner Connect | `src/providers/routescanner.ts` | `api_key` | `VESSEL_MCP_PROFILE_ROUTESCANNER_CONNECT__API_KEY` | Header `x-api-key` |
| VesselAPI | `src/providers/vesselapi.ts` | `api_key` | `VESSEL_MCP_PROFILE_VESSELAPI__API_KEY` | Header `Authorization: Bearer …` |
| Data Docked | `src/providers/datadocked.ts` | `api_key` | `VESSEL_MCP_PROFILE_DATADOCKED__API_KEY` | Header `x-api-key` |
| Datalastic | `src/providers/datalastic.ts` | `api_key` | `VESSEL_MCP_PROFILE_DATALASTIC__API_KEY` | Query parameter `api-key=…` on live requests |
| Global Fishing Watch | `src/providers/globalfishingwatch.ts` | `bearer_token` | `VESSEL_MCP_PROFILE_GLOBALFISHINGWATCH__BEARER_TOKEN` | Header `Authorization: Bearer …` |

These adapters:

- Resolve the secret on demand from `CredentialStore.resolveSecret(label, "api_key")`;
  the secret never appears in the MCP `credential_profiles` payload.
- Apply per-credential token-bucket throttling (conservative ~1 RPS with
  a small burst) before any network I/O.
- Return structured `{ ok: false, reason: "auth_missing" | "auth_failed"
  | "rate_limited" | "provider_error" | "network_error" |
  "invalid_response" | "unsupported_query" }` results — never throw an
  unredacted message that contains the credential.
- Surface a diagnostic `endpointUrlFor(...)` that substitutes the literal
  `REDACTED` for the api_key (path-segment auth) or omits it entirely
  (query auth), so the URL is safe to log and to surface in catalog
  tooling.

The default `npm test` run never reaches a paid provider. Live calls
require both the credential profile and the corresponding
`VESSEL_MCP_LIVE_TEST_*` flag (declared `defaultDisabled: true` in
`config/provider-catalog.example.json`). The catalog's
`implementationStatus` for the rows above is now `implemented`.

Adapter authors adding simple paid REST providers should reuse the
`createPaidByokProvider(template, options)` factory where possible
rather than copying the surrounding auth/throttle/error code. Custom
provider modules must still keep all secrets out of URLs, logs, errors,
and MCP tool payloads.

### Verifying

The `test/credential-one-time.test.js` suite covers, deterministically
and without any live provider call:

- env-gate semantics (default-off, canonical opt-in tokens, rejected
  values),
- overlay `list()` exclusion (`credential_profiles` MCP payload never
  emits the one-time entry),
- overlay `get()` / `resolveSecret()` returning the in-memory value,
- non-persistence across repeated `resolveProvider` calls,
- empty/whitespace field values dropped with an `incomplete` status,
- `redactForLog` and `createJsonLogger` scrubbing one-time secrets,
- the credential profile output schema accepts `one-time` as a source
  enum (for future deliberate emission), but the production tool never
  emits it.
