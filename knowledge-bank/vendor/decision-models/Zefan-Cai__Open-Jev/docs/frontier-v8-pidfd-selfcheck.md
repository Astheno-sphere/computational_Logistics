# V8 own-process pidfd self-check

This observer is a separate, bounded observation of a named C export opening a
descriptor for the observer's own live process, followed by fdinfo inspection,
one zero-time poll, and close verification. The design does not assert that any
current host, kernel, provider, or interpreter has passed these operations.

## Fixed route and inputs

The sole route is `ctypes.CDLL(None, use_errno=True).pidfd_open`, resolved from the
process-global symbol namespace. Its prototype is exactly
`(ctypes.c_int, ctypes.c_uint) -> ctypes.c_int`. The provider is discovered from
the actual function address; it is not presumed to be libc. The call uses only
the current positive own PID, within the declared scalar range, and flags `0`.
Missing symbols and call failures are consumed negative observations. There is
no raw syscall fallback, interpreter switch, native shim, or mutation of
`os.pidfd_open`.

The required platform is Linux with four-byte C `int` and `unsigned int`.
The pointer width is observed and reported; no architecture is inferred. Each
observation requires scope `frontier_v8_own_pidfd_functional_selfcheck`, a new
nonce, attempt directory, and request.
The request has exactly these eight fields:

- `schema_version`
- `scope`
- `nonce`
- `observer_sha256`
- `identity_helper_sha256`
- `attempt_directory`
- `host`
- `bootstrap`

The primary source, raw request, original bootstrap, and own boot ID, UID, PID,
and birth identity are checked before consuming the fresh sibling marker and
output directory. The adjacent presence helper is loaded from immutable
captured bytes with SHA256
`1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412`,
for pure helper functions only. The old presence observation is not rerun.

The file CLI uses `-B -I -S`. `--execute` rejects before parser construction,
source/helper/request/path processing, or C-export resolution. Standard module
imports, including `ctypes`, occur before that CLI guard.

## Provider and descriptor observations

The actual function address must belong to one executable, file-backed interval
in `/proc/self/maps`. Anonymous, deleted, or ambiguous mappings are rejected.
The canonical provider file must be regular; its device, inode, and SHA256 are
captured and checked again after the probe. These describe the trusted loader
baseline and current disk file. They do not authenticate mapped payload bytes,
symbol implementation, or a pre-pinned libc provider. No
`ctypes.util.find_library` lookup is used.

The named export is called once. A negative result captures errno immediately
in `open_errno` and ends the attempt without another route. A missing export
is also recorded as a consumed failure after the output marker is written.
Every descriptor `>= 0`, including descriptor `0`, receives exactly one close
attempt in `finally` once its return value is assigned to the tracked descriptor.
Asynchronous interruption during the C-call/return handoff is outside that
Python cleanup guarantee.

Only `/proc/self/fdinfo/<returned-fd>` is inspected. It must contain a unique
`Pid` equal to the current own PID; `NSpid` is descriptive. The returned
descriptor alone is registered for `POLLIN`, and `poll(0)` is called once. A
live own-process descriptor is expected to return an empty event list;
unexpected events or errors fail the observation and still enter close cleanup.

Close is followed immediately by an `fstat` check requiring `EBADF`, before any
other file is opened. Close is never retried after `EINTR`. Source, helper,
request, bootstrap, provider mapping/file identity, and own-process identity
are rechecked after the descriptor probe.

No signal operation, child, worker, foreign PID or descriptor, process control,
controller, guard, or queue operation is part of this phase. Signal delivery,
exited-process readiness, descendant cleanup, and recovery remain untested.

## Evidence and limits

A successful result can report only the observed own-process C call,
descriptor identity, zero-time poll, and close check. This observer does not
enable or bypass the unchanged native `os.pidfd_open` guard. All containment,
execution, resource authority, and model-runtime ABI flags remain false when this narrow C call is
actually exercised. There is no model, Torch, CUDA, installation, or
model capability-gain claim.

The complete stdout receipt is returned-call evidence. It is not independently
retrieved remote receipt or marker evidence, a persistence or durability proof,
or a host-loss controller/queue guard. Once the marker is written, a failed or
interrupted attempt is consumed and cannot be retried or resumed. Precondition,
request, and bootstrap rejection precede consumption. `BaseException` or host
loss may leave a consumed marker without a complete receipt or stdout.

Fixtures should cover the typed named-export route, missing symbol and errno
failures, descriptor `0`, own-PID restriction, provider/fdinfo rejection,
unexpected poll events, and exactly-once close on failures. Two Linux fixtures
exercise only their own process and a fresh file CLI. They depend on the
declared Ubuntu CI environment and skip on local macOS; their execution must
be established from actual CI evidence before reporting success. Fixtures do
not establish any MS host, GPU lease, foreign queue recovery, or model result.
