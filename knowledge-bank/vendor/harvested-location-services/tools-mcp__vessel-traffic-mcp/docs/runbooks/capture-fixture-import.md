# Capture fixture import runbook (F5.AC1)

`vessel-capture-import` is an operator-only CLI that turns an authorized
HAR or JSON capture into a sanitized fixture suitable for tests and
adapter development. It does **not** call any live or paid provider — it
only reads the local input file, redacts sensitive material, and writes
a deterministic fixture under `fixtures/captures/`.

## Hard rules

- Run only against captures from sessions you are authorized to record
  (your own account, with terms-of-service approval).
- **Never commit raw HAR files, raw JSON captures, `.env`, cookies, or
  private session logs.** `*.har` and `captures/raw/` are already in
  `.gitignore`. Commit only the produced sanitized fixture.
- The CLI must not be wired into autodev/CI default verification, and
  the fixture-replay provider it produces is disabled for live use by
  default (see F5.AC3).

## Usage

```sh
npm run build
npx vessel-capture-import --in path/to/raw.har --label marinetraffic-search
```

Common options:

| Flag | Description |
| --- | --- |
| `--in <path>` | Path to the raw HAR or JSON capture (required). |
| `--out <path>` | Override output path. Defaults to `fixtures/captures/<label-or-basename>.fixture.json`. |
| `--format har\|json\|auto` | Force a specific parser. `auto` (default) inspects the JSON shape. |
| `--label <name>` | Human label stored in the fixture and used for the default filename. Sanitized to `[a-z0-9_-]`. |
| `--force` | Overwrite an existing output file. The default is to refuse so you cannot accidentally clobber a reviewed fixture. |
| `--help` | Show the full help text. |

## Redaction guarantees

The importer replaces credential-bearing material with the literal token
`[REDACTED]` before the fixture is written:

- **Headers:** `Authorization`, `Proxy-Authorization`, `Cookie`,
  `Set-Cookie`, `WWW-Authenticate`, `Authentication`, `X-Api-Key`,
  `Api-Key`, `X-Auth-Token`, `X-Access-Token`, `X-Csrf-Token`,
  `X-Xsrf-Token`, `X-Session-Id`, `X-Session-Token`, `X-Goog-Api-Key`,
  `X-Functions-Key`, `X-Mt-Api-Key`, `X-Vesselfinder-Key`,
  `X-Amz-Security-Token`, `Session-Id`, `Session-Token`. Matching is
  case-insensitive.
- **Cookies:** every cookie value (request and response) is collapsed to
  `[REDACTED]`. Cookie names are kept so test fixtures can still assert
  that a particular cookie was set.
- **Query parameters:** `token`, `access_token`, `refresh_token`,
  `id_token`, `bearer`, `bearer_token`, `api_key`, `apikey`, `app_key`,
  `key`, `subscription_key`, `client_secret`, `secret`, `session`,
  `sessionid`, `session_id`, `sid`, `auth`, `authentication`,
  `password`, `passwd`, `pwd`, `mt_key`, `userkey`. URL `userinfo`
  (`user:pass@host`) is stripped completely.
- **JSON body fields (recursive):** `password`, `passwd`, `pwd`,
  `token`, `access_token`, `refresh_token`, `id_token`, `bearer_token`,
  `session_token`, `session_id`, `sessionid`, `session`, `api_key`,
  `apikey`, `app_key`, `subscription_key`, `client_secret`, `secret`,
  `authorization`, `auth`, `cookie`, `set_cookie`, plus PII fields
  `credit_card`, `card_number`, `cvv`, `ssn`.
- **Form bodies (`application/x-www-form-urlencoded`):** the same name
  list as JSON body fields and query parameters, redacted in place.
- **Multipart and binary bodies (`image/*`, `audio/*`, `video/*`,
  `application/octet-stream`, `application/pdf`, `application/zip`):**
  the body is dropped entirely; only the MIME type is preserved.
- **Base64-encoded HAR response bodies:** dropped before redaction so
  binary blobs cannot smuggle credentials past the scanner; a warning
  is printed to stderr.
- **String value patterns:** any remaining string value (including
  surviving header values, query values, and free-text body content) is
  scanned for JWTs (`eyJ...`), AWS access-key IDs (`AKIA...`,
  `ASIA...`), `sk-` prefixed tokens, and GitHub `ghp_` tokens, which
  are also collapsed to `[REDACTED]`.

The fixture also includes a `redactionReport` summarizing how many
items of each category were redacted. Reviewers should diff this report
against the source capture before promoting a fixture.

## Output shape

```json
{
  "version": 1,
  "label": "marinetraffic-search",
  "createdAt": "2026-05-15T10:00:00.000Z",
  "source": { "format": "har", "sourceFile": "captures/raw/sample.har", "entryCount": 2 },
  "entries": [
    {
      "method": "GET",
      "url": "https://api.example.test/v1/vessels?api_key=%5BREDACTED%5D&mmsi=123456789",
      "queryParams": [
        { "name": "api_key", "value": "[REDACTED]" },
        { "name": "mmsi", "value": "123456789" }
      ],
      "request": { "headers": [...], "cookies": [...], "mimeType": "application/json", "body": "..." },
      "response": { "status": 200, "headers": [...], "cookies": [...], "mimeType": "application/json", "body": "..." }
    }
  ],
  "redactionReport": { "totalRedactions": 9, "redactedHeaders": [...], "redactedQueryParams": [...], "redactedBodyFields": [...], "redactedValuePatterns": [...] },
  "notes": [...]
}
```

## Reviewer checklist

Before committing a sanitized fixture:

1. Diff against the raw capture and confirm no remaining secrets, PII,
   account IDs, or billing identifiers appear in the fixture file.
2. Confirm `redactionReport.totalRedactions` is non-zero when the source
   contained credentials (it almost always should be).
3. Confirm the fixture lives under `fixtures/captures/` and the raw
   source is **not** staged for commit.
4. Run `npm test` — the capture-import tests must pass and the
   credential redaction guarantees must hold for the new fixture shape.
