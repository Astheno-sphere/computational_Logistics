# Maintenance

Everything here exists because it broke once. The theme is narrow: **this project's
failure mode is not crashing, it is going quietly out of date.** A stale catalog, a
stale count, a stale install instruction — none of them throw, none of them turn a
build red, and all of them are read by strangers deciding whether to trust the thing.

## The one rule

**A number that describes this project must be derived, never typed.** Counts have
rotted through 95 → 109 → 114 → 116 in prose while every test stayed green. If you
find yourself writing a digit into a description, a README sentence, or a comment,
put it behind a generator and a test instead. `test/agent-surface.test.js` now fails
on any README count that disagrees with the catalog, and on any digit in
`package.json.description`.

## Before every release

Run in this order. Each one has caught a real defect.

```bash
npm test                      # the offline suite (it prints its own count)
node tools/mutate.cjs         # every mutation must be caught; it prints "N caught, 0 missed"
npm run catalog -- <token>    # regenerate from the live Apify account
npm run readme                # regenerate coverage + every derived count
npm run check:catalog         # diff the catalog against live; exits 1 on drift
```

`check:catalog` is the gate that matters, and it runs in `publish.yml` before
`npm publish`. **It fails when `APIFY_TOKEN` is absent rather than skipping**, because
shipping an unverified catalog is the exact defect it exists to prevent.

Note that `npm run readme` **fails loudly** if a sentence it rewrites has been
reworded, rather than silently leaving a hand-maintained count behind. If it stops
with "rewrite target not found", fix the pattern — do not delete the check.

## Triggered by an event, not a calendar

| When | Do | Why |
|---|---|---|
| A new Actor is published to the portfolio | Regenerate the catalog, `npm run readme`, cut a release | Until then the server tells agents a real, published tool does not exist. Age is not the signal: the catalog that shipped wrong was **eight days old** |
| An Actor's input schema changes (a field becomes required) | Same | An agent builds a call from the bundled schema, gets an HTTP 400 it could not have predicted, and cannot tell the schema moved |
| An Actor is unpublished or renamed | Same, and check `FEATURED` in `src/tools.js` | `indexCatalog` reports missing featured tools on stderr at startup — that warning is the tripwire. A rename also renames the MCP tool, since the name IS the slug |
| **An Actor's price changes** | Regenerate the catalog and cut a release | Pricing moves independently of any build, so the catalog can be schema-perfect and still quote a rate the caller is not charged. `check:catalog` now diffs price per actor and fails on drift |
| A featured tool is added or removed | `npm run readme` | The exposed-count prose is derived from `FEATURED.length`, but only when the generator runs |
| A preset in `src/presets.js` changes (tool added/removed, title, description, server name) | `npm run readme`, then `npm test` | The README's "Vertical presets" block is generated from that module and `test/agent-surface.test.js` fails when the two disagree. `test/presets.test.js` also refuses any preset slug that is not in the bundled catalog and any preset over the tool cap — so an actor being unpublished breaks the build here, on purpose, rather than shipping a preset that advertises it |

## Quarterly, or when something feels stale

- **Glama score page** — <https://glama.ai/mcp/servers/malonestar/gov-data-mcp/score>.
  Free third-party audit of the tool surface. It found the missing annotations and the
  overlapping-screener ambiguity before we did. Re-read it after any tool-surface change.
- **Registry version** — `curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=gov-data-mcp"`.
  Must match `package.json` and the newest git tag.
- **npm description** — what npm prints under the package name is also what directories
  scrape. It is now digit-free by test, but re-read it after any rewrite.
- **GitHub repo description / topics / homepage** — settings, not code, so no test can
  reach them. The description once said the server was "callable through mcp.apify.com"
  long after it became an `npx` stdio server, contradicting our own directory listings.

## What has no automated guard

Be honest about these rather than assuming a green build covers them.

1. **Anything in a hosting provider's settings** — GitHub repo metadata, the Glama
   listing, the awesome-mcp-servers entry. Code gates cannot see them.
2. **Whether a published Actor still works.** This server reports failures faithfully,
   but it does not monitor them. That is the portfolio's own health sweep's job.
3. **Whether a price is the *right* price.** The catalog now carries each tool's real
   rate and `check:catalog` diffs it against live, so it cannot silently drift. What no
   gate can tell you is whether the rate you set on Apify is the one you meant. The
   $0.50–$200 per-1,000 band in `gen-catalog.cjs` catches the 1000x-overprice defect,
   not a deliberate mispricing.
4. **Tool naming, going forward.** Resolved in v1.1.0 — every tool is hyphen-case, and
   for catalog tools the name **is** the Apify slug, which is also the `tool` argument
   and the Store URL tail. Two tests pin that invariant. Renaming an Actor on Apify
   therefore renames its MCP tool; the pre-1.1 meta names are answered with an explicit
   rename notice rather than aliased, and that map should be kept, not tidied away.

## Releasing

Releases are tag-driven. Pushing `vX.Y.Z` runs tests, the mutation harness, the live
catalog diff, then publishes to npm with provenance and registers with the MCP registry
over GitHub OIDC. Two things to remember:

- **`npm publish` is irreversible.** v1.0.1 published to npm and *then* failed the
  registry's 100-character description cap, and the only fix was a new version.
- **Create the GitHub Release too.** Tags alone are invisible to anything reading the
  API — Glama grades maintenance partly on published Releases, and three existing tags
  scored "No stable releases found" until they were turned into Release objects.
