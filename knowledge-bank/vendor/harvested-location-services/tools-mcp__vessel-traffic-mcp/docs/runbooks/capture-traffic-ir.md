# Capture traffic IR runbook (F5.AC2)

`vessel-capture-ir` derives an **endpoint fingerprint**, **traffic IR**,
and **schema summary** document from a sanitized capture fixture
produced by `vessel-capture-import` (F5.AC1). It is operator-only,
read-only, and does not call any live or paid provider — it only reads
the local sanitized fixture and writes a deterministic IR file.

## Hard rules

- The input MUST be a sanitized fixture (`version: 1`) emitted by
  `vessel-capture-import`. Raw HAR/JSON captures are rejected so the
  IR cannot be derived directly from a session that still contains
  credentials.
- **Cookies are dropped entirely from the IR.** Only the per-endpoint
  request cookie *count* is retained, never names or values. Cookie
  names are session-identifying in some providers and are therefore
  not safe to publish in IR diffs.
- Header and query *values* are NOT retained anywhere in the IR.
  Only name sets are emitted. Names already classified as
  credential-bearing (`Authorization`, `Cookie`, `X-Api-Key`, ...)
  are surfaced in a dedicated `redactedHeaderNames` list so reviewers
  can confirm they were stripped.
- Schema summaries describe **shape** only, never raw values.
  Surviving `[REDACTED]` placeholders are emitted as
  `{ "kind": "redacted" }` so downstream tooling cannot accidentally
  treat the placeholder as a real value.
- The IR is **bounded** by depth, breadth, and union caps so a
  pathological capture cannot blow up the output.
- Before the IR file is written, a defense-in-depth scan re-runs the
  AC1 token-pattern scrub on the rendered output. Any JWT, AWS,
  GitHub, or `sk-`-style value-shaped string discovered is replaced
  with `[REDACTED]` and a warning is added to the IR.

## Usage

```sh
npm run build
npx vessel-capture-import --in path/to/raw.har --label marinetraffic-search
npx vessel-capture-ir --in fixtures/captures/marinetraffic-search.fixture.json
```

Common options:

| Flag | Description |
| --- | --- |
| `--in <path>` | Path to a sanitized fixture (required). |
| `--out <path>` | Override IR path. Defaults to `fixtures/captures/<basename>.ir.json`. |
| `--max-depth N` | Max JSON nesting depth in schema. Default 6. |
| `--max-breadth N` | Max keys retained per object level. Default 32. |
| `--max-union N` | Max union variants retained per array. Default 8. |
| `--max-sample-paths N` | Max redacted sample paths retained per endpoint. Default 3. |
| `--force` | Overwrite an existing IR file. |
| `--help` | Show the full help text. |

## Output shape

```json
{
  "version": 1,
  "generatedAt": "2026-05-15T10:00:00.000Z",
  "source": {
    "fixtureVersion": 1,
    "fixtureLabel": "marinetraffic-search",
    "fixtureCreatedAt": "...",
    "entryCount": 2
  },
  "endpoints": [
    {
      "id": "GET https://api.example.test/v1/vessels",
      "method": "GET",
      "origin": "https://api.example.test",
      "pathTemplate": "/v1/vessels",
      "sampleCount": 1,
      "samplePaths": ["/v1/vessels"],
      "queryKeys": [
        { "name": "api_key", "redacted": true },
        { "name": "mmsi", "redacted": false }
      ],
      "requestHeaderNames": ["Accept", "Authorization", "Cookie", "X-Api-Key"],
      "redactedHeaderNames": ["Authorization", "Cookie", "X-Api-Key"],
      "requestCookieCount": 1,
      "requestBodyMimeTypes": [],
      "requestBodySchema": null,
      "statuses": [
        {
          "status": 200,
          "count": 1,
          "mimeTypes": ["application/json"],
          "schema": { "kind": "object", "properties": { "ok": { "kind": "primitive", "type": "boolean" }, "refresh_token": { "kind": "redacted" } } }
        }
      ]
    }
  ],
  "warnings": [],
  "notes": [...]
}
```

## Path template heuristics

The fingerprinter normalizes path segments to placeholders so a single
endpoint is not double-counted across vessels:

- `123456789` → `:mmsi` (9-digit numeric)
- `9123456` → `:imo` (7-digit numeric)
- 12–64 char hex strings → `:hex`
- UUIDs → `:uuid`
- Other numeric segments → `:id`
- `[REDACTED]` (or its URL-encoded form) → `:redacted`

## Reviewer checklist

Before promoting the IR file:

1. Confirm the input fixture passed F5.AC1 review (no raw credentials).
2. Confirm `redactedHeaderNames` contains every credential-bearing
   header observed in the capture.
3. Confirm `requestCookieCount` does not surface cookie *names*.
4. Confirm no `warnings` entry mentions the defense-in-depth scan.
5. Confirm the IR file lives under `fixtures/captures/` and the source
   fixture is also a committed sanitized fixture, not a raw capture.
