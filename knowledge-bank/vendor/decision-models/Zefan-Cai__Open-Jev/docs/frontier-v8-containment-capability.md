# V8 native prerequisite presence observation

This separate observer records each presence predicate in pinned native A's
`_require_linux()`: `sys.platform == 'linux'`, `hasattr(os, 'pidfd_open')`,
`hasattr(signal, 'pidfd_send_signal')`, `hasattr(select, 'poll')`, and equal
real/effective UID. Native A is commit
`4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2`; its helper SHA256 is
`2d9edb599d48aa2c9e1e5971ce95ae833022622a9de3c8d1a1ca81f0f70debc2`.
These are reference inputs. The observer never imports or executes that body.

Presence and callability are reported separately. A present noncallable value
satisfies the frozen `hasattr` predicate. Even if all predicates pass,
`functional_containment_verified`, `containment_available`,
`execution_available`, and `resource_authority` remain false. No pidfd, signal,
poll object or operation, prctl, native helper, subprocess, Torch/CUDA, pip,
installation, model, Git, network or queue operation is performed.

Run the actual reviewed file only as
`PYTHON -B -I -S OBSERVER --observe-cpu --request PATH --expected-request-sha256 HASH`.
`--execute` refuses before parser, source, request or path handling. Standard
CPython and standard-library imports are trusted inputs; recorded module file
and spec origins describe that baseline and do not authenticate its payload.
There is no controlled loader or cache replacement.
The CLI prints the complete returned receipt as JSON on stdout; captured
stdout is evidence from that call, and does not by itself independently
retrieve or authenticate remote receipt-file bytes.

The request is bounded to 16 KiB and has exactly seven top-level fields:

- `schema_version`: integer 1.
- `scope`: `frontier_v8_native_prerequisite_presence_only`.
- `nonce`: a fresh 64-character lowercase hex value.
- `observer_sha256`: SHA256 of the actual lexical canonical `__file__` bytes.
- `attempt_directory`: a fresh normalized absolute owned output path.
- `host`: exactly `node_alias`, `hostname`, `boot_id`, `uid`; aliases are N1-1,
  N1-3, N4-1, N4-2, N4-3 or N4-4. The alias is declared transport context and
  is explicitly unauthenticated.
- `bootstrap`: exactly `executable`, `sha256`, `version`. `executable` is the
  resolved current `sys.executable` path, `sha256` its bytes, and `version` the
  actual three-element Python version. The original lexical interpreter path
  is also recorded. This phase offers no alternate interpreter selection.

The raw request SHA256 is passed separately. Duplicate JSON keys at any depth,
nonfinite JSON, malformed declarations, stale source/request/bootstrap bytes,
symlink inputs/ancestors, and changed input identities refuse. Source reads are
bounded to 1 MiB and executable reads to 64 MiB. The source is read and hashed
from its actual lexical file entry before observation; no immutable native
source is read to establish source proof.
Generic source/request/bootstrap/output paths under `/proc`, `/sys`, and `/dev`
refuse before any open or read. No malformed request can open an endpoint at
those paths before regular-file rejection. Proc access is reserved for the
dedicated fixed reader below.

Only the fixed kernel boot file and `/proc/self/stat` and `/proc/self/status`
are read for process identity, once before consumption and once during
postvalidation. The receipt includes current PID, boot, start ticks, real and
effective UID, the four proc UID values, ppid, process group and session. No
parent or foreign PID file is read. `parent_identity_verified` and
`ancestry_verified` remain false; a reported ppid is not an ancestry proof.

The real observer refuses unequal UID/eUID, a different request owner, a
different declared host/bootstrap, an existing root/consumed marker or unsafe
output before writes. The designated output parent must be owned by the
current UID. Standard root-owned ancestors are accepted, but every input and
output ancestor is opened with no-follow directory descriptors. Outputs must
be disjoint from the source, request and executable, and cannot descend from
the old `/data/zefan/open-jev-v8-runtime-abi-20261003` boundary.

After all preconsumption validation, an exclusive mode-0600 sibling
`ATTEMPT.consumed.json` consumes the attempt. A fresh mode-0700 `ATTEMPT` contains
the exclusive mode-0600 `receipt.json`. Missing attributes are a successful
presence observation with independently reported failed predicates; they do
not make containment available. Postvalidation rechecks original bytes and
file identities, own identity, privilege and output bindings. Ordinary caught
and postvalidation failures keep the consumed marker and write a failed receipt
while output writes remain usable. If the fresh directory cannot be
created/opened, the failed receipt is the exclusive sibling
`ATTEMPT.failed-receipt.json`. No retry, resume, overwrite, old-root reuse,
child process, runtime ABI observation or resource authority is authorized.
Receipt-write/fsync failure or abrupt process/host loss may leave only the
consumed marker and raw caller diagnostics; there is no completion or cleanup
proof in those cases.

Focused fixtures inject module facts and current-process identities. They
exercise missing and noncallable attributes, refusal and retained consumed
failures without invoking containment APIs. One Linux-only fixture reads its
own process identity without creating a child. A separate Linux GitHub CI
fixture starts the actual `-B -I -S` file entry with a fresh synthetic request
and output boundary under a 30-second test timeout. This subprocess belongs
only to the test; the observer itself creates no child. It exercises only
standard-library presence observation, and provides no MS host, model or
runtime ABI result. Both Linux fixtures are skipped on macOS.
