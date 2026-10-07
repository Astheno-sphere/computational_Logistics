# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- The release workflow extracts the section of the version being tagged with awk,
     matching "## [x.y.z]". Keep that heading shape exactly. -->

<!-- The docs site includes everything between these markers. Keep the end marker
     last in the file so the link definitions come along. -->
<!-- #region changelog -->

## [Unreleased]

### Fixed

- A tag or any other key named `__proto__` is dropped from every result, at every
  depth. It used to be kept as an own property, but the client parses
  `structuredContent` against the output schema, which loses that one key, so
  the two channels of one answer could disagree. Both now omit it.
- An Overpass endpoint that never answers now hands over to the next one. A
  timeout carries no HTTP status, so the mirror walk, which keyed on 429/5xx,
  gave up on the spot. And the default mirror `overpass.private.coffee` had
  stopped answering, so whenever `overpass-api.de` was busy,
  `find_nearby_pois` failed after 40 seconds. The weekly smoke run had been
  red since 2026-09-14. The default list is now `overpass-api.de` followed by
  `lz4.overpass-api.de`.

- `haversineMeters` uses the `atan2` form instead of `asin(sqrt(h))`. `asin`
  is infinitely sensitive where its argument approaches 1, so at antipodal
  distances the rounding error grew to a tenth of a metre — enough for the
  triangle-inequality property test to see a detour that was _shorter_ than
  the direct distance, once in a few thousand runs, and to turn the release
  build of 0.3.1 red on its first try. The worst violation over 200 000
  antipodal triangles is now below a micrometre; distances change by
  fractions of a metre and are rounded before they are shown.

[Unreleased]: https://github.com/ni-c/osm-mcp/compare/v0.3.1...HEAD

## [0.3.1] - 2026-09-07

### Security

- Every value a service answers is shaped before it reaches an output schema
  (`src/shape.ts`). A number is taken only when it is finite — JSON `1e999`
  parses to `Infinity` — a distance or duration only when it is non-negative
  and within a ceiling, a string only when it is one; names, labels, road
  summaries, turn instructions and tag keys are cut to 500, 500, 500, 300 and
  255 characters. Before this, a route whose `distance` was missing or
  `1e999`, a POI whose `lat` was `"abc"` or whose `name` was an object, a
  geocoding hit whose `display_name` was a number, a matrix cell that was text,
  a contour point at `1e999` and a leg `summary` that was a number each failed
  the SDK's output validation — and one such element in a listing took every
  other element down with it. A `null` tag value threw a `TypeError`. Each of
  the six public services this server talks to, including the community
  Overpass mirror in the default list, could send any of them. An element the
  shaper refuses is now dropped from a listing; a route without a usable
  distance is answered with a sentence; `optimize_route` refuses a visiting
  order that does not cover the stops. A property test feeds arbitrary JSON —
  and envelopes with the right shape and random leaves — to every tool and
  asserts that none answers with a validation error.
- The HTTP status is decided before the body is read. A non-2xx answer's body
  is read under its own 64 KiB ceiling that cuts rather than refuses. A 5xx
  with a body past the 8 MB data cap used to surface as a size error — a plain
  `Error` with no status — so the Overpass mirror failover and the 429 hint,
  both keyed on the status, never saw it.
- Text a service writes about a failure — OSRM's `code` and `message` — is
  quoted into the error result cut to 40 and 200 characters, stripped of
  control characters and labelled as untrusted text. It used to be
  concatenated as it arrived; a hundred thousand characters were a hundred
  thousand characters in the model context, with nothing saying whose words
  they were.
- `ORS_API_KEY` must be 8 to 256 visible ASCII characters. The key travels in
  an `Authorization` header, and undici quotes a header value it refuses in its
  own `TypeError` — the redaction caught it, but only the redaction. The server
  now refuses the shape at startup without echoing it.
- A refused URL scheme is quoted with at most 40 visible characters. A
  hexadecimal key with a colon after it is a valid URL whose scheme is the key,
  and the error message printed the scheme in full.
- `OVERPASS_BASE_URL` accepts at least one and at most eight endpoints. Each
  entry is a growing back-off plus a 40-second timeout when the mirrors are
  down; five hundred were accepted.
- Trailing slashes on a base URL are trimmed by a counted scan. `/\/+$/` was
  tried from every slash of a run and consumed the run each time: 80 000 of
  them followed by one letter cost almost two seconds at startup.
- A tag named `__proto__` — legal JSON, and a name any mapper can type — is
  kept as an own property. `out[key] = value` in the result cleaner set the
  prototype instead and dropped the tag in silence.
- CI: `actions/dependency-review-action` on pull requests (`fail-on-severity:
high`); the publish job installs with `npm ci --ignore-scripts` so no
  dependency's install hook runs beside the OIDC token; `gh release create
--verify-tag`; the weekly smoke job's checkout no longer persists
  credentials. The runtime image drops yarn and corepack next to npm.

### Fixed

- `boundingBoxOf` folds `-0` into `0`. A contour on the equator or the
  meridian can carry both spellings, and `-0` serialises as `0` in the text
  block while `structuredContent` kept the sign.
- Contour points off the globe are left out of the bounding box instead of
  failing the isochrone.
- The test harness lists the tools before calling them, so every success
  path is checked against its output schema on the client side as well.

### Added

- The server introduces itself in full. `title`, `description`, `websiteUrl` and
  `icons` now travel with `name` and `version`, so a client that shows a server
  to a person has something to show. All four were already in `server.json` for
  the registry and reached no client at all; a test compares the two so they
  cannot drift.
- Server `instructions`. Results carry an `untrusted` marker, but that is read
  after the fact — this is the channel a model sees before it calls anything.
- An OpenSSF Scorecard run, weekly and on every push to `main`, reporting into
  the Security tab next to CodeQL and Trivy. The badge is the second in the row.

### Changed

- oxlint's `suspicious` category is on; 34 findings fixed (mostly
  `Array#toSorted()` over copy-and-sort and un-shadowed names). No runtime
  behaviour changed.
- The tool reference marks the `essential` preset and the tools that ask a
  person before they act, per tool rather than only in the introduction. A test
  keeps both sets in step with the code.
- Source maps are no longer published in the npm tarball. Node reads them only
  under `--enable-source-maps`, which nothing here sets, and the maps pointed at
  a `src/` this package does not ship — so a stack trace under that flag named a
  file nobody could open. `dist/**/*.js` is unchanged; the package is about a
  fifth smaller.

[0.3.1]: https://github.com/ni-c/osm-mcp/compare/v0.3.0...v0.3.1

## [0.3.0] - 2026-09-03

### Added

- Every tool declares an `outputSchema` and answers with `structuredContent`
  beside the text block. A client no longer has to parse prose to use a result.

  All eleven carry `untrusted: true` and `source: "openstreetmap"` as fields —
  there is no exception list, because OpenStreetMap is editable by anyone on
  earth and no tool here answers with anything else. A client that reads only
  the structured half would otherwise get a mapper's free text with no framing
  at all.

  What this server computes is described exactly; what comes out of OSM is
  described but left open. The tag namespace has no schema, and the SDK
  validates every result against the advertised one before it goes out — so a
  stricter shape would turn a mapper adding `payment:bitcoin` into a
  `poi_details` that fails outright.

### Changed

- The advertised schemas avoid spellings that are legal JSON Schema and still
  get a tool refused, or its constraint silently dropped, by some MCP clients:
  an open object now writes `"additionalProperties": true` rather than the
  empty schema `{}` zod emits for it; a value that was left untyped is declared
  as what it really is; and a nullable field is written as `anyOf` branches
  rather than `"type": ["string", "null"]`, which several clients read as a
  single type and then drop. What the tools accept and return is unchanged;
  only the way the schema says so is.

- Runs on **MCP SDK 2.0**. Existing clients see the same protocol revision they
  always did; the change is the package layout behind it.

- The linter is **oxlint** instead of eslint plus typescript-eslint, which
  lifts the TypeScript ceiling: typescript-eslint pins `typescript` below 6.1,
  so this repository was held on TypeScript 6 by its linter rather than by its
  code.

- The tool filter, the host classifier and the documentation-asset generator
  now come from **`mcp-tool-allowlist`**, **`mcp-internal-hosts`** and
  **`svg-asset-set`** rather than from copies kept here — 674 fewer lines, and
  one place to fix each. None of them has a runtime dependency of its own.

- stdio is served through `serveStdio`, so the connection's era is negotiated
  on the opening exchange rather than assumed. A client that pins the
  `2026-07-28` era is served it; until now its `server/discover` probe was
  answered with "Method not found" and only `2025-11-25` was on offer. A client
  that speaks the older era sees no change — it is still pinned to one instance
  for the life of the connection, exactly as a hand-wired
  `StdioServerTransport` served it.

### Fixed

- The control-character and BiDi stripping now runs over the structured value
  as well, key by key. It used to happen on the serialized JSON, which reached
  every string in it for free; a value handed over as `structuredContent` is
  not text, so the same pass has to walk the tree. Without it the two channels
  of one answer would have differed in exactly the characters this server
  strips on purpose, and the machine-readable one would have been the dirty
  half.

- **Control characters and BiDi overrides are stripped from every result.**
  OpenStreetMap is editable by anyone on earth, and a POI's `name`, Nominatim's
  `display_name` and the street names inside OSRM turn instructions are whatever
  a mapper typed. `JSON.stringify` escapes everything below U+0020 and nothing
  above it, so U+007F, the C1 block — which contains CSI at U+009B — and the
  BiDi overrides U+202A-U+202E reached the model verbatim. The error path had no
  JSON encoding at all: an upstream body is concatenated straight into the text
  block, and none of the default endpoints is run by this project.

  The filter sits in `textResult` and `errorResult`, the two funnels every
  result passes through, rather than at each field. U+200E and U+200F are
  deliberately **kept** in data: a right-to-left mark is legitimate in an OSM
  name and cannot reorder the text around it, so stripping it would corrupt the
  name of a real place. An upstream error body has no such name to protect and
  takes the full set, in `sanitizeErrorBody` as well as on the way out.

- **`isochrone` no longer fails with `Maximum call stack size exceeded`.** The
  bounding box was built with `Math.max(...lats)`, and argument spread puts every
  element on the call stack: about 125 000 points still work, 150 000 already
  throw. A 120-minute car isochrone from a Valhalla instance that does not
  generalize carries several hundred thousand points, well inside the 8 MB
  response cap — so the tool failed on a perfectly ordinary answer, with a
  message that told the model nothing and invited it to retry, each retry being
  another rate-limited upstream request. The box is now folded rather than
  spread, which makes the response size irrelevant to this path.

  The contour geometry also has an explicit ceiling now, like everything else
  unbounded here (100 route steps, 60 detail tags, 500 characters per tag value).
  It is set above what the response cap can carry at realistic coordinate
  precision, so a legitimate contour still comes back whole, and reaching it is
  an error naming a smaller budget rather than a silent truncation — a bounding
  box computed from the first half of a ring would be a wrong answer, which is
  worse than the error it replaced.

- An entry in `OSM_ALLOW_TOOLS` that is not tool-name-shaped is now
  **redacted** in the error rather than quoted back. a value pasted into the
  wrong variable is no longer echoed into the client's log.

## [0.2.0] - 2026-08-27

### Added

- `OSM_ALLOW_TOOLS` and `OSM_DENY_TOOLS` choose which of the 11
  tools are registered. Both take comma-separated tool names or a prefix with a
  trailing `*`, the allow list decides what is in and the deny list is subtracted
  from it, and `OSM_ALLOW_TOOLS=essential` selects a curated six —
  `geocode`, `reverse_geocode`, `find_nearby_pois`, `poi_details`, `route`, `map_link`. A model picks the right tool far more reliably from six than
  from eleven, and every visible tool costs context on every request. Nothing
  changes for an installation that sets neither.

  A filtered tool is not registered at all, so it is absent from `tools/list`
  and answers `tools/call` with "tool not found".

  An entry that matches no tool **stops the server at startup**, naming the
  entry and listing the real names, rather than being ignored: an ignored typo
  leaves a tool missing from `tools/list` with nothing pointing at the cause.

### Changed

- The README now carries the same eight badges, in the same order, as every other
  MCP server in this family, all of them reading from npm rather than hard-coded;
  the opening follows one shape; and the standalone "Full documentation" line is
  gone, because the docs badge three lines above it points at the same page.

### Fixed

- The container image no longer ships OpenSSL 3.5.7-r0, which carries
  **CVE-2026-14456** (denial of service via unbounded memory growth). The pinned
  `node:24-alpine` digest is already the newest one; Alpine's fixed 3.5.8-r0 has
  simply not been rebuilt into it yet, so the runtime stage now upgrades
  `libcrypto3` and `libssl3` by name. Upgrading those two rather than running a
  blanket `apk upgrade` keeps the rest of the image exactly as the digest pins
  it. The step can go once the base image ships the fix.

## [0.1.2] - 2026-08-26

### Changed

- The check that decides whether a configured endpoint is local — and therefore
  whether sending an API key over plain `http` is worth warning about — now uses
  the same host classifier as the other MCP servers in this family, in
  `src/hosts.ts`. The string comparison it replaces missed several spellings of
  the same address: `http://[::ffff:127.0.0.1]`, which `URL` canonicalises to
  `[::ffff:7f00:1]` before any check sees it, and `localhost.` with its root
  label. It also treated `127.example.com` as loopback, because it matched on the
  `127.` prefix, and so stayed quiet about a plain-http URL to a public host.

Nothing else changes: every endpoint this server talks to comes from the
environment, and no tool takes a URL, so there is no request whose target a
caller can choose.

## [0.1.1] - 2026-08-18

### Added

- Documentation site at <https://osm-mcp.ni-c.de>: guides, a complete tool
  reference generated from the actual schemas, FAQ and this changelog.
- Architecture diagram and demo recording, each generated from a single
  source (`npm run assets`, `docs/demo.tape`) and verified in CI.
- Fully automated release pipeline: npm publishing with provenance via
  Trusted Publishing, GitHub releases from the changelog, MCP Registry and
  multi-arch GHCR publishing on tag push.

## [0.1.0] - 2026-08-18

### Security

- The optional `ORS_API_KEY` is now stripped from every tool result as a last
  line of defense: it travels in an `Authorization` header, so an upstream (or
  a misconfigured `ORS_BASE_URL` host) echoing the request could previously
  have leaked it into the model context through an error body. URL-style key
  parameters are additionally redacted from sanitized error bodies.
- The `mcp-publisher` binary in the release workflows is now version-pinned and
  checksum-verified instead of floating on `releases/latest` — it runs with the
  job's OIDC identity, which proves registry ownership.
- The npm/registry publish in `release.yml` now waits for its own Trivy
  container scan instead of racing the scan in `ci.yml`.
- The response cache now has an aggregate 32 MB byte budget on top of the entry
  cap; the caps alone allowed ~500 MB of retained upstream JSON.
- Every tool call gets a 120 s wall-clock deadline: many-waypoint requests
  behind the 1 req/s geocoding limiter could previously occupy the queue for
  minutes past any client timeout.
- POI core tags are truncated with the same 500-char value budget as
  `poi_details` tags, and `countrycodes` input length is bounded.

### Fixed

- Validated base URLs are returned in their WHATWG-normalized form instead of
  the raw input string.
- The container now exits promptly on SIGTERM/SIGINT — as PID 1, Node gets no
  default signal handling, so `docker stop` used to wait out its grace period
  and SIGKILL.

- The optional `ORS_API_KEY` is now removed from the environment before any
  configuration validation can throw. Previously a caller that caught the
  `ConfigError` (e.g. for an invalid `OSM_CACHE_TTL`) would keep running with
  the key still in `process.env` — readable in `/proc/<pid>/environ` and
  inherited by child processes. (Same finding as audiobookshelf-mcp PR #2.)
- Invalid base-URL and `OSM_CACHE_TTL` values are no longer echoed in error
  messages — an API key pasted into the wrong environment variable would have
  been printed verbatim into the MCP host's log.
- `isLoopbackHost` now strips IPv6 brackets generically instead of matching
  only the literal `[::1]`.

### Added

- Initial implementation: 11 read-only OpenStreetMap tools — geocoding
  (Nominatim + Photon), routing/matrix/trip optimization via the FOSSGIS OSRM
  instance with correct `routed-{car,bike,foot}` profile prefixes, isochrones
  via Valhalla (OpenRouteService optional via `ORS_API_KEY`), POI search and
  details via Overpass with mirror failover, plus offline straight-line
  distance and openstreetmap.org link tools.
- Per-service rate limiting, in-memory response caching and a mandatory
  identifying User-Agent, keeping the server inside the published usage
  policies of the public OSM services.

<!-- #endregion changelog -->
