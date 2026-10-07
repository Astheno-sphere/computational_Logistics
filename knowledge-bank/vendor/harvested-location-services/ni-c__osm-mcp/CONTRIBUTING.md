# Contributing

Thanks for taking the time. Small, focused changes with tests land fastest.

## Development setup

```sh
git clone https://github.com/ni-c/osm-mcp.git && cd osm-mcp
npm install
npm test          # unit tests, all upstream APIs mocked — no network needed
npm run build
```

A minimal dev environment:

```sh
npm run build && node dist/index.js   # starts the stdio server with public defaults
npm run smoke                         # opt-in LIVE test against the real services
```

## The live smoke test, which is this server's integration suite

Every other server in this family has a `test/integration/` that brings up its
backend in Docker and calls every tool against it. This one keeps a script
instead, and the reason is the backend: Nominatim, OSRM, Overpass, Valhalla and
Photon are somebody else's public services. There is no image to bring up that
would be worth the run, and their usage policies are written for people rather
than for a job that fires on every push.

So the script stays a script, and it runs **on the weekly schedule in CI, never
in the pull-request gate**. That is the same question the weekly run asks in the
other repositories — has the backend moved underneath the server — with the
difference that here a failure may also mean somebody edited a building. It is
allowed to fail without blocking anybody's work, and it is not in `needs:` of
`publish`.

Run it by hand after changing anything that talks to a service. The check at the
end is the one that matters: foot routes must come out much slower than car
routes. With the wrong OSRM URL layout the server silently returns car routes
for every profile, and nothing else in the output looks wrong.

## Expectations

- **Tests.** Behaviour changes come with a test that fails without the change.
  CI runs lint, build and the mocked test suite on the two current Node LTS
  lines, and the live smoke test once a week.
- **Comments** explain constraints the code cannot show — not what the next line does.
- **Security-sensitive areas** (config parsing, Overpass QL construction, anything
  that builds a request URL): please describe the attack you are defending against,
  or the one your change might open, in the PR text.
- **Respect the public services.** Changes must not weaken the rate limiting,
  caching or the identifying User-Agent — these keep the server inside the
  usage policies of Nominatim, OSRM, Overpass, Valhalla and Photon.
- **No new runtime dependencies** without a very good reason; the small tree is a
  feature.
- Run `npm run lint` before pushing — it checks both oxlint and prettier, and prettier
  also validates the YAML, JSON and Markdown files.

## Questions and bugs

- Questions and ideas → [Discussions](https://github.com/ni-c/osm-mcp/discussions)
- Reproducible problems → [Issues](https://github.com/ni-c/osm-mcp/issues)
- Vulnerabilities → [private reporting](https://github.com/ni-c/osm-mcp/security/advisories/new)
