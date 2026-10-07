# Security

This page is the prose version of
[SECURITY.md](https://github.com/ni-c/osm-mcp/blob/main/SECURITY.md).

The short version: there is no credential to steal by default, nothing this
server can write, and the one thing worth thinking about is that your location
queries travel to public services.

## Trust model

This server holds **no credentials by default** — it talks to public, read-only
OpenStreetMap services. All 11 tools are read-only; the server cannot modify
OpenStreetMap data, because the editing API is simply not wired up. There is no
write mode to switch off.

Every tool declares all four MCP annotations rather than leaving three to the
defaults: `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`
and — uniquely in this family — **`openWorldHint: true`**. The specification's own
example draws that line where this server sits: a tool whose world is one
configured instance is closed, and one that queries public services on the open
internet is not. Every other server in this family is `false` throughout; this is
the one where `true` is the honest answer.

There is no approval dialog and no `ELICITATION` variable here, because there is
nothing to ask about: no tool of this server changes anything, anywhere. The
servers that do have one — see, for instance,
[imap-mcp's](https://imap-mcp.ni-c.de/guide/approval) — and a variable that did
nothing would be worse than none at all.

The only optional secret is `ORS_API_KEY`, an OpenRouteService key.
Compromising it lets an attacker consume the key owner's free-tier request
quota — nothing more. It grants no access to any data of yours.

## Where your data goes

The one real consideration: **location queries are sent to the configured
public services.** A geocode of your home address, a route from your hotel, a
POI search around where you are right now — each is an HTTPS request to
Nominatim, OSRM, Overpass, Valhalla, Photon or OpenRouteService, subject to
those operators' logging and privacy practices.

Do not use this server for locations you would not put in a third-party web
request. For sensitive use, self-host the services and point the `*_BASE_URL`
variables at your instances — every backend supports it, and the
[configuration page](/guide/configuration) covers the details.

## API-key handling

`ORS_API_KEY` is treated as radioactive from the moment it is read:

- It is **deleted from `process.env` before anything else happens** — before
  any configuration validation can throw — so a caller that catches a
  `ConfigError` and keeps running does not keep the key readable in
  `/proc/<pid>/environ` or inherited by child processes.
- It is **redacted from error messages** before they reach the model context.
- The server **refuses to start** with a key set and a cleartext non-loopback
  `ORS_BASE_URL`, because the key travels in an `Authorization` header.
- Invalid configuration values are **not echoed** in error messages — a key
  pasted into the wrong variable would otherwise land verbatim in the MCP
  host's log.

## Untrusted content

OpenStreetMap data is user-contributed: place names, addresses and tags are
written by millions of mappers, and a tag value can contain anything — including
text that reads like instructions to a model. Every tool result carrying
OSM-sourced content is therefore explicitly **marked as untrusted data, not
instructions**, so the model treats a POI named "ignore all previous
instructions" as a badly named POI.

Upstream error bodies get the same caution: they are truncated, and HTML error
pages are dropped entirely before anything reaches the model context. The HTTP
status is decided before a body is read at all, and a non-2xx body is read
under its own 64 KiB ceiling — so an error page of any size is still the
status it came with, which is what the Overpass failover and the rate-limit
hint are keyed on. Text a service writes about a failure (OSRM's `code` and
`message`) is quoted cut to 200 characters, stripped of control characters and
labelled as untrusted.

Everything else a service answers is shaped before it reaches a result: a
number is taken only when it is finite (JSON `1e999` parses to `Infinity`), a
distance or duration only when it is non-negative and within a ceiling, a
string only when it is one, and names, labels, road summaries, turn
instructions and tag keys are cut to a fixed length. An element the shaper
refuses is dropped from a listing rather than failing the whole call; a route
without a usable distance is answered with a sentence.

## Network posture

- The server speaks stdio and **never listens on a port**.
- **Redirects are never followed** — a redirect would replay request headers
  (including the ORS `Authorization` header) at whatever host it names.
- Every request **times out** (30 s; 40 s for Overpass, whose queries also
  carry their own server-side 25 s budget).
- Responses are size-capped before they are buffered.

## Being a good citizen is also a security property

The client-side rate limits, the Overpass concurrency cap, the identifying
User-Agent and the response cache exist to honor the published usage policies
of shared community infrastructure — but they double as protection for you:
they make it impossible for a confused or manipulated model to turn this server
into a request cannon fired from your IP address.

## Reporting a vulnerability

Use [private vulnerability reporting](https://github.com/ni-c/osm-mcp/security/advisories/new).
Do not open a public issue for an unpatched vulnerability, and do not include
real credentials, tokens, hostnames or private configuration in a report. You
can expect an initial response within a week; fixes ship as a new release with
a CHANGELOG note. Only the latest release and the current `main` branch receive
security fixes.
