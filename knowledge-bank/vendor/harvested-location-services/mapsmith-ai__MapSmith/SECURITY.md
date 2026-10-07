# Security policy

> Published advisories:
> [GHSA-g95f-6vxv-mgv7](https://github.com/mapsmith-ai/MapSmith/security/advisories/GHSA-g95f-6vxv-mgv7) — `run_sql` could install and load arbitrary DuckDB extensions, disclosing host credentials. Affects >= 0.1.0 < 0.4.0, fixed in 0.4.0.
> [GHSA-3rcc-xpw3-r4xh](https://github.com/mapsmith-ai/MapSmith/security/advisories/GHSA-3rcc-xpw3-r4xh) — a plain local file could make MapSmith fetch attacker-chosen URLs. Affects <= 0.2.1, fixed in 0.2.2.

MapSmith executes tool calls written by LLM agents against local data. Its
security promises are precise, and we treat any break of them as a
vulnerability. Whether a break also gets a published advisory is a separate
question with a criterion of its own, under *When a break becomes an advisory*
below:

- **Workspace containment**: with `MAPSMITH_WORKSPACE` set, no path an agent
  can name — no tool argument, no `run_sql` statement — may read or write
  outside the workspace (path jail at the MCP boundary + sandboxed DuckDB
  connection). Any escape by a caller-reachable path — traversal, symlink
  trick under the documented threat model, GDAL virtual filesystem, SQL —
  is a vulnerability.

  **Two paths are written that no agent names, and they are stated here
  rather than left to be found.** MapSmith's one-time install of the DuckDB
  `spatial` extension lands in DuckDB's own extension directory
  (`~/.duckdb/extensions`, about 15 MB, once per environment); and engine
  scratch files go in a temporary directory inside the workspace when there
  is one. An engine that drops a working file anywhere else — the process
  working directory included — is a bug in that engine binding, and
  `tests/test_path_containment.py` fails when one does, by running every
  writing operation with the working directory forced outside the
  workspace. Until 2026-09-06 this bullet said *no tool call* may write
  outside, without reservation, and `contour_lines` had been writing four
  files into the process working directory since 0.4.0. A sentence with its
  exceptions written down can be checked; an absolute one about a process
  that loads five third-party engines will be wrong again.
- **Provenance integrity**: a `<output>.provenance.json` manifest must
  faithfully record what produced the dataset. A way to make MapSmith write
  a misleading manifest is a vulnerability.

  Broken in 0.5.1 and earlier, fixed in 0.6.0, found by our own reviews: five
  operations recorded a round trip or a reprojection before it happened, so a
  failure in between left a manifest asserting a move that never finished;
  28 of 58 writers could leave a dataset with no manifest beside it when the write
  or a check raised after bytes reached the disk; and
  `count_in_polygons(predicate="contains")` returned zero for every polygon
  under `verified: true`. None got an advisory under the criterion below: the
  first two occur only on a path where the tool call has already returned an
  error, and the third returned zeros, which a caller sees before trusting the
  record. A misleading record is still the defect this bullet names, so it is
  written here and in the CHANGELOG, and `tests/test_failure_manifest.py`
  injects both failures into every writer the catalogue lists.
- **No credentials in a manifest.** Manifests are meant to be shared — attached
  to a review, a bug report, a paper — so a credential must never reach one.
  Since 0.2.2 that is enforced in two layers, in this order:

  1. **SQL that configures a credential is refused before it runs.**
     `CREATE SECRET` in any of its spellings, `SET`/`PRAGMA` of a
     credential-bearing setting, and `ATTACH` carrying a password or URI
     userinfo are rejected with a message pointing at where credentials belong:
     the environment of the process that starts the server, out of reach of a
     tool call. Comments are stripped first, so `CREATE /*x*/ SECRET` does not
     slip past. Honest work is untouched — a column named `secret_count`, a
     literal mentioning a password, `SET memory_limit`, and
     `CALL load_aws_credentials()` (which names no secret) all still run.
  2. **Whatever is recorded is still redacted**, for the credentials that reach
     a manifest without being SQL: a signed URL as an input path, a connection
     string as a tool argument. The value after a credential-bearing name
     becomes `<redacted>` — quoted, so the recorded statement still parses —
     while the name and the rest of the statement stay readable. It covers
     `parameters`, `crs_decisions`, `notes` and input paths, and the same
     redaction is applied to job-ledger rows including the `error` column, since
     an engine error quotes the statement that failed. `parameters_redacted:
     true` says it happened, because a manifest that quietly differs from what
     ran would be worse than the leak.

  Why refusal came first: redaction alone was shipped in 0.2.1 and an
  adversarial audit escaped it in minutes with `MAP{'Authorization': 'Bearer …'}`,
  an `E'…'` literal, dollar quoting, and a comment between the name and the
  value — and the `E'…'` case desynchronised the quote pairing, so the matcher
  masked a *different* argument and kept the secret. A text scan without a SQL
  parser will keep losing that race; refusing the statement removes the class.
  Each of those four is now a regression test.

  A credential that survives into a manifest or a ledger row is a
  vulnerability. Two limits are known and are not: detection is name-based, so
  a secret passed as a bare positional value with no recognisable name is not
  detected, and neither is a URI that percent-encodes the colon of its own
  userinfo (`user%3Apass@host`).

  Related, same leak by another route: persistent DuckDB secrets are written to
  `~/.duckdb/stored_secrets`, outside any workspace and beyond the session.
  Under a workspace the sandbox already refused that write; the connection now
  sets `allow_persistent_secrets = false` in both modes, before locking the
  configuration.
- **No network egress in sandbox mode** — with `MAPSMITH_WORKSPACE` set —
  beyond MapSmith's own one-time install of the `spatial` extension, which it
  does through DuckDB's Python API and no statement can ask for. Any way to
  make SQL, GDAL or a tool argument reach the network from a
  workspace-confined server is a vulnerability.

  This is why the catalogue's embedding engine does **not** download its model
  under a workspace. 0.3.0 made that engine the default, and the model weights
  are a first-use fetch; left alone it would have put an outbound request on
  the first tool an agent calls, in the mode this section says makes no
  requests. Under a workspace the model is used only if it is already cached,
  and otherwise discovery falls back to BM25 and reports `engine: "lexical"`.
  To have embeddings there, warm the cache once outside sandbox mode or use the
  container image, which ships the weights. `HF_HUB_OFFLINE=1` refuses the
  fetch in every mode.

**The HTTP transport has no authentication in this release.** Anyone who can
reach the endpoint can run every tool against everything the process can see,
so it belongs on loopback or a trusted network until authenticated remote mode
ships — the shipped examples bind to loopback and set a workspace for that
reason. Host and Origin validation (DNS rebinding protection) is enabled
explicitly, including when the server binds to a non-loopback address, and
`MAPSMITH_ALLOWED_HOSTS` / `MAPSMITH_ALLOWED_ORIGINS` extend the allow-list for
reverse proxies. A way past that validation *is* a vulnerability; the absence
of authentication is a documented limitation, not one.

Also worth knowing rather than reporting: with `MAPSMITH_WORKSPACE` unset,
`run_sql` can read and write any path the process can reach — deliberate, and
documented in the README. Escalation from there is closed, and since 0.4.0 by
the layer that actually closes it: a statement saying `INSTALL` or `LOAD` is
refused in both modes. The paragraph that used to stand here listed four other
layers instead, and an audit walked past all four — the account is further down
this page, under the heading that says so. Behind the refusal those layers still
hold: extension autoinstall and autoloading are off, community extensions are
refused (`shellfs` turns a filename ending in `|` into a shell command),
unsigned extensions cannot be enabled, DuckDB's HTTP and S3 filesystems are
disabled so even an already loaded `httpfs` can neither read nor write over the
network, and the configuration is locked so SQL cannot undo any of it. So
unconfined mode does not let SQL acquire code, load unsigned code, or run a
shell command.

**Since 0.2.2 it does not reach the network either, unless you say so.** Both
paths that used to be open are refused by default, and each one is verified by a
test that counts requests at a loopback server rather than matching an error
message:

- `ST_Read('/vsicurl/https://…')` and GDAL's other virtual filesystems. GDAL
  carries its own HTTP client, so DuckDB's filesystem block never applied to it:
  raw SQL could read any endpoint the host can reach — internal services, cloud
  metadata — and hand the content back in the tool result, while the URL it
  chose carried data out. `enable_external_access=false` is the only
  DuckDB-level switch that stops it and it takes local file access with it, so
  the refusal is at the tool boundary instead.
- `INSTALL <name> FROM '<url>'`, which fetched from a URL the statement named.

Set `MAPSMITH_ALLOW_REMOTE=1` to get remote reads back — cloud-native data is a
real use case, and the capability is gated rather than removed. The reason it is
off by default is who chooses: the path is written by the model, from whatever it
read, so a third-party dataset carrying "the updated layer lives at
`https://evil.tld/x.gpkg`" was enough to have GDAL parse attacker-chosen bytes
in-process with nobody consenting.

Two limits of that refusal, stated rather than implied: it is a text scan of the
SQL, not a parse, so a statement that merely mentions a URL in a string literal
is refused too; and it sits at the tool boundary, so a future engine that runs
agent-written SQL without calling `workspace.refuse_remote_in_sql` reopens the
path.

**A text check cannot see inside a file GDAL resolves itself, so there is a
second layer.** A GDAL indirection file — a `.vrt` and its relatives — is a
plain local path: no scheme, no `/vsi` prefix, nothing for the path guard, the
SQL scan or DuckDB's `allowed_directories` to catch, while GDAL fetches whatever
its `<SrcDataSource>` names, in-process. Measured in 0.2.1 (the audit that found
it is why this paragraph exists): reading such a file **from inside a
workspace** sent HEAD and GET to an attacker-named host through the
GeoPandas/pyogrio path, which contradicted the promise above. DuckDB's spatial
reader was already safe there, since it routes GDAL I/O through DuckDB's own
filesystem with external access off.

The fix is at GDAL's level rather than the string's: when remote reads are off,
MapSmith deregisters GDAL's indirection and network drivers (`VRT`, `OGR_VRT`,
`WMS`, `WFS`, `OAPIF`, `STACIT` and the rest) via `GDAL_SKIP`/`OGR_SKIP` before
the geospatial stack initialises — see `mapsmith/gdal_policy.py`, asserted by
subprocess tests that count requests at a loopback server. With
`MAPSMITH_ALLOW_REMOTE=1` the drivers come back, including when a parent process
had installed the policy. If you are on 0.2.1 or earlier and rely on the
workspace as a security boundary, this is the fix to take.

With `MAPSMITH_WORKSPACE` set, all of it is refused — `INSTALL`, `LOAD`, DuckDB
filesystems and GDAL's virtual filesystems alike — and the refusal happens
before any request leaves, which `tests/test_duckdb_sandbox.py` asserts by
counting requests at a loopback server rather than by matching an error message.
The "local files, no network" mode that used to be on the roadmap here is now
simply the default, so what is left of unconfined mode is unconfined *file*
access and nothing else. Reports about that are welcome as hardening ideas;
reports about a server reaching the network without `MAPSMITH_ALLOW_REMOTE`, in
either mode, are vulnerabilities.

**Since 0.4.0, `INSTALL` and `LOAD` are refused in both modes.** Until then the
last sentence above — *what is left of unconfined mode is unconfined file access
and nothing else* — was true of the confined mode and false of the unconfined
one, in a file whose whole job is to be exact about which is which: an audit
before the 0.4.0 tag used `run_sql` in the default mode to install
DuckDB's `aws` extension and read the host's real cloud credentials back through
a tool result. None of the layers that existed saw it —
`autoinstall_known_extensions` and `autoload_known_extensions` being false stops
the *implicit* forms and says nothing about a statement that asks outright,
`lock_configuration=true` does not stop an explicit `INSTALL`, and the
remote-path scan looks for `://` and `/vsi`, which `INSTALL postgres` does not
contain. An `INSTALL` is an HTTPS fetch of a native binary executed in the
server's process, on a statement written by a model, which is not a thing to do
by default in either mode.

Extensions **already loaded keep working**, `spatial` included: MapSmith loads
it through the Python API before the configuration is locked, so no statement
has to ask for it. To acquire others, name them where the agent cannot reach:
`MAPSMITH_ALLOW_EXTENSIONS=postgres,azure` in the environment of the process
that starts the server. Named extensions rather than a switch, because "allow
everything" is how a geoprocessing server ends up holding a credential reader.

**Who this affects.** Versions up to and including 0.3.0, run *without*
`MAPSMITH_WORKSPACE` — which is the plain `uvx mapsmith` setup, though not the
container image, which sets a workspace itself. On such a machine, SQL reaching
`run_sql` could acquire an extension and hand back credentials the process could
already see (cloud credential files, environment variables). It needed the model
to write that statement, so the realistic route is prompt injection from data the
agent read; nothing here says it happened to anyone. If you run the unconfined
setup on a machine that holds credentials, upgrade to 0.4.0 — and either way, a
workspace has always been the stronger configuration.

This has an advisory: **[GHSA-g95f-6vxv-mgv7](https://github.com/mapsmith-ai/MapSmith/security/advisories/GHSA-g95f-6vxv-mgv7)**,
so a dependency scanner tells you rather than leaving it to whoever reads this
page. It is filed against `>= 0.1.0, < 0.4.0` — the lower bound is where
`run_sql` first shipped, checked by downloading the packages rather than by
reading the tags.

This is the second promise in this file that the code contradicted — the first
was a path list escaping the workspace jail through `run_operation`, fixed in
0.3.0. Both were found by auditing before a release rather than reported from
outside, and both are recorded here rather than quietly corrected, because a
security document whose history is invisible is asking to be believed rather
than checked.

## How much work one call may ask for

An agent chooses the arguments, and some of them decide how much memory and
time a call takes before anything is computed. `elevation_profile` and
`points_along_lines` place a point every `spacing` along each line, so a spacing
of `1e-6` on a 90 m line is ninety million points — over HTTP, a denial of
service within reach of anyone who can call a tool. Both count the points from
the line lengths first and refuse above **`MAPSMITH_MAX_SAMPLES`** (default
1 000 000, about two minutes of sampling), before allocating any. It is an
environment variable of the server, like `MAPSMITH_ALLOW_EXTENSIONS`, so no
tool argument can move it.

The same limit, counted in **pairs**, bounds `cluster_points_by_distance` and
`hot_spots` with distance-band weights: the
pairs of points within the distance grow with the square of the points when the
distance is large, and the distance is the agent's argument. The query runs in
blocks and is refused once the pairs pass the limit, before the next block is
allocated (0.8.0 audit: 6,000 points at a distance of 1e9 took two minutes and
2.3 GB without it).

That is all there is, and it is not a general resource policy: other operations
are bounded only by their inputs, and a server exposed over
HTTP should also run under the memory and CPU limits of its container or pod
(`deploy/` has a Kubernetes example). The sampling limit was found in the
pre-release audit of 0.7.0; it was there in every earlier release.

## What MapSmith records, when you ask it to

MapSmith writes nothing about your usage by default and sends nothing anywhere,
ever — there is no telemetry in this product and no endpoint to disable.

One opt-in feature writes a local file: `MAPSMITH_DISCOVERY_LOG=<path>` records
each catalog search and the operation run after it, so that a deployment can
turn its own requests into benchmark cases (README, *Finding the right
operation*). It holds the query text, the facets declared, and operation names.
It does **not** hold dataset paths or operation arguments — a deliberate limit,
because a file quietly accumulating every path a caller touched is a different
product with a different conversation attached. The path goes through the same
guard as a tool argument, so under `MAPSMITH_WORKSPACE` it must be inside it.

The queries are your users' words and can name real projects and real places.
The file stays where it was written; nothing in MapSmith reads it back or
uploads it. Read it before you copy any of it anywhere.

Out of scope: issues requiring a hostile local process on the same machine
(the jail assumes a single trusted writer of the workspace filesystem —
documented in the README), and anything reachable only by running MapSmith
without a workspace, which is deliberately unconfined.

**A manifest is an unsigned file, and `get_lineage` reads whatever it finds.**
The walk recovers a chain by scanning the workspace for `*.provenance.json` and
matching digests, so a record is evidence only in the sense that it exists.
Anything able to write in the workspace can leave one claiming bytes it never
produced — and in the usual deployment that includes the calling agent, which
is the component everything else on this page treats as untrusted. Nothing can
close this: the format has no signatures and does not claim to. What the walk
does instead is check the cheap thing and say the answer. A manifest sits
beside the output it describes, so each step reports under `claim` whether that
output is on disk and hashes to what the record says; only `reverified` means
this walk confirmed it, and a chain containing anything else is not reported as
verified. Strings copied out of a record — operation names, notes, parameters —
are truncated and stripped of control characters before they reach a reply,
because they are quoted from files nobody named and one of them is interpolated
into a sentence an agent reads. Treat a recovered chain as testimony to be
checked, not as an attestation.

The walk reads data, not only JSON: each step it reports re-hashes the output
beside its record (capped per file), and a hop that misses on a shapefile hashes
the shapefile at the path its consumer read, to match a record written under the
digest rule before draft.9. A shapefile that is not on the chain is not read
(until 0.8.0 every shapefile record in the workspace was hashed on every call).
A directory container (`.gdb`) is hashed in full, without following symbolic
links or Windows junctions inside it.

**A third containment exception, and it is the filesystem's.** A workspace on a
cloud-synced folder (OneDrive, Dropbox) may hold placeholder files that the
provider downloads on read. Reading every manifest under the scan root can
therefore cause network traffic in a mode this page describes as having no
egress. It is not reachable by an attacker and it is not ours to switch off;
it is listed because the other two exceptions are.

## When a break becomes an advisory

Every break of the promises above is a vulnerability. Not every one gets a
GitHub advisory, and keeping the two apart is deliberate: the first statement is
about the defect, the second about the channel.

We open a GHSA advisory when a reader would **do something different** after
reading it -- upgrade in a hurry, rotate a secret, close a port, go looking for
signs it was used. When the answer is no, the defect is still written in two
public places: the CHANGELOG entry of the release that fixes it, and this file,
in the paragraph of the promise it broke. There is no third option where a break
is neither advised nor mentioned.

The criterion exists because the alternative spends the signal. Both advisories
listed at the top are ones a reader acts on -- GHSA-g95f-6vxv-mgv7 asks you to
rotate a credential, GHSA-3rcc-xpw3-r4xh to upgrade off a version that fetches
URLs an attacker chose. A third advisory of much smaller weight, filed next to
those, teaches a reader to skip the next one.

A worked example, so the criterion can be checked instead of trusted. On
2026-09-06 `contour_lines` was found writing four files into the process working
directory, outside the workspace: a break of the first promise, shipped since
0.4.0. It did not get an advisory, on four grounds that were measured rather
than argued -- the working directory is chosen by whoever starts the server and
not by the caller; the four basenames are fixed and do not derive from the input
(checked with hostile names); what lands outside is a derivative of the caller's
own data, not a credential; and the HTTP transport carries no authentication, so
anyone who can reach the endpoint already holds more than the leak grants. It is
recorded in the containment bullet above and in the CHANGELOG.

The criterion is re-applied, never inherited. If a defect of that shape becomes
influenced by the input -- the caller picking the directory or the basename --
it gets the other answer, and that call is made again from the measurements
rather than by citing this paragraph.

## Reporting

Please report vulnerabilities **privately**:

- GitHub: [private vulnerability report](https://github.com/mapsmith-ai/MapSmith/security/advisories/new) (preferred)
- Email: mapsmith@proton.me

You will get an acknowledgment within **48 hours**. We coordinate disclosure
with you; absent agreement otherwise, we consider 90 days a reasonable
deadline. Please do not open public issues for suspected vulnerabilities.

## Supported versions

Only the latest release on PyPI / `ghcr.io/mapsmith-ai/mapsmith` receives
security fixes.
