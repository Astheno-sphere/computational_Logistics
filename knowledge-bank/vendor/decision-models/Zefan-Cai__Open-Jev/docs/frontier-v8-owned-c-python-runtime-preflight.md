# V8 fixed owned C to Python readonly preflight

This separate CPU fixture has one fixed direct-child boundary, `G → X/P`.
The new C guardian G forks X and retains its original G-to-P pidfd while one
`fexecve` changes X to the fixed Python P without changing its PID or birth
identity. P reads distribution metadata and six package source positions. It
creates no descendants and imports no runtime package. The closed cases are
`normal` and `worker_loss`.

This is a source contract. Successful tests, CI, compilation or a fresh host
observation need separate receipts. The tests/docs author is a source author
and cannot provide an independent source or actual-result review.

## Bound sources and readonly inputs

The ten-file closure contains six new paths: observer, guardian C, protocol
header, Python worker, tests and this document; three unchanged pure utilities;
and `requirements-linux-py311-cu128-20261002.lock`. The frozen lock SHA256 is
`d1f238a916dfdfbc8b89f3de4c28bb3b7220cdd97ecf609ebb726afab0ca8221`.
A future deployment contains eight Git runtime inputs and one fresh nonGit
request. Captured pinned utility bytes supply only reviewed pure identity,
compiler and linkage functions. Their old observers, native guards, installers,
CLI routes, products and receipts are never new runtime evidence.

Every real request binds fresh source hashes, case, nonce, attempt directory,
host identity, bootstrap, Python version and readonly runtime paths. Real input
requires the declared Python 3.11 version and binds the venv configuration,
site directory, `venv/bin/python` symlink relation and canonical backing ELF.
The old PR27 environment is a readonly input, not an installer or repair route.
Synthetic CI inputs use a separately labelled temporary tree and the current
CI Python version. They cannot enter the host observer's request route or be
described as PR27 package evidence.

The old scientific/native checkouts, data, weights, plan, freeze, training gates
and `--execute` refusal stay fixed. Receipt booleans do not grant execution or
resource authority. New compiler, header, CPP, object, product and postlink
linkage facts describe their newly observed inputs. Postlink snapshots do not
authenticate all bytes throughout linking or all mapped code.

The observer captures the entire declared Python interpreter file, at most
64 MiB, with its full byte count, SHA256 and file identity. Its ELF descriptor
adapter gives the unchanged pinned parser only the actual first
`min(full length, 8 MiB)` bytes. The returned `captured_bytes` and
`captured_sha256` describe the full capture; `header_view_bytes` and
`header_view_sha256` describe that actual prefix. The full hash must still match
the exact request before build/runtime, and full bytes/identity remain bound by
the input rechecks. A change after the prefix can retain its view hash while
failing the full binding. Headers, the complete program table and the single
PT_INTERP path must fit inside the actual view; there is no reconstructed
padding, clipped offset, second parser or fallback outside it.

The Python PT_INTERP pathname is descriptive. The guardian's separate canonical
loader and linkage observations do not independently authenticate that Python
loader or its mapped payload. Full captured file hashing and synthetic ELF
fixtures do not establish loading, complete segments/mapped code, Python
runtime ABI or fresh host applicability.

## Python handoff and startup

G opens the newly bound interpreter, worker and request as readonly inputs.
The one fixed C bootstrap uses `-B -I -S -c` with exact ordered arguments and
the controlled environment. It hashes the captured worker/request bytes,
records before/after `fstat`, closes those original inherited FDs once, and
immediately observes `F_GETFD` failure with EBADF before another FD acquisition.
Python's actual close return is `None`; it is never serialized as C return 0.
The immediate Python `fcntl` check raises an actual `OSError` with EBADF and
has no function return. Its return field stays null; a C return of -1 is not
invented from that exception.
Only captured worker bytes are compiled and executed, with separately labelled
logical `__file__` and arguments. A later pathname reopen is not the worker
source. The file itself is not called immutable; the captured bytes are.

The bootstrap literal/hash, composed exec argv, actual `/proc/P/cmdline`,
observed `sys.orig_argv` when available, initial `-c` argv and assigned logical
arguments are separate facts. `sys.executable` is preserved exactly, including
an empty string or FD-style pathname. It never selects an interpreter, proves
the venv alias, launches another process or repairs the environment. The
canonical ELF and actual `/proc/P/exe` jointly bind the interpreter separately.

`EXEC_ENTER` is prospective. A returned `fexecve` preserves actual result -1
and errno, then X exits 71 without fallback. Success records attempted true,
returned false and null return/errno; it does not invent a return of 0.
The transition needs original exec-error EOF, P READY, stable PID/birth/boot/
UID/parent, product change, declared version/flags and captured-source bindings.
EOF, READY or a native boolean alone is insufficient.
If bootstrap ERROR arrives before the joint READY/product observation,
exec attempted/returned remain unknown. Even an exec-error pipe EOF cannot
manufacture the missing transition or a syscall outcome. The bootstrap-hash
negative fixture preserves its ERROR and raw70 reap without claiming a
verified Python product transition.

CPython and its loader run before the bootstrap. Original CLOEXEC descriptor
numbers may already have been reused. Parent preexec CLOEXEC facts and exec
mechanisms describe those original handles; P does not claim continuous
numeric vacancy or borrow the old C leaf's first-operation EBADF rule. Original
stdin/stdout/stderr are closed only before exec. Later descriptors with those
numbers are tracked by semantic owner/label/generation.
Before opening new native descriptors, G requires its original three stdio
handles to be present. An absent original handle fails before those numeric
slots could become new interpreter, source or pipe descriptors.

P requires isolated, no-site and no-bytecode flags. Site is absent from
`sys.path`. It validates the standard builtin/frozen/path meta finders,
standard zip/FileFinder path hooks, loader suffixes and importer-cache roots.
The declared standard stdlib zip search entry is recorded even if absent.
Trusted stdlib/lib-dynload/CPython/native startup origins describe the baseline;
they do not authenticate every imported file or mapped instruction.
Python 3.11 `-S` can use the base prefix, so no synthetic venv-prefix equality
is imposed. No site/customization, `.pth`, runtime package, network, pip,
installer, repair or cache-write route belongs to this payload.

## Metadata observations

Two before/after snapshots each make one explicit capped `os.scandir(site)`
pass, at most 8192 entries. They reject symlink metadata directories,
`.egg-info`, missing or extra `.dist-info`, duplicate normalized names and
wrong versions. Each captured regular METADATA is at most 256 KiB and the
snapshot total at most 16 MiB. Captured bytes have exactly one nonempty Name
and Version and match all 76 frozen distribution versions.

A fresh source FileFinder resolves `torch`, `transformers`, `peft`, `triton`,
`safetensors` and `accelerate` without loading those modules. Each selected
in-site regular nonsymlink `__init__.py` is captured and hashed, at most 1 MiB.
These are six source entry positions, not 76 executed module origins or a full
installed-file audit. FileFinder's internal cache fill can enumerate the site
again; those internal scans are outside the explicit metadata-pass count.
Returned metadata, origins, configuration and alias facts must match before/
after. Filesystem races/blocking remain baseline limits, not an atomic snapshot
claim. Poison initializers, `.pth` and customization sentinels in tests must
remain unexecuted and absent from loaded runtime modules.

Pipcheck is explicitly deferred: performed count 0 and dependency consistency
false. Version equality does not substitute for it. A future owned pip process
requires its own reviewed closure with `PIP_CONFIG_FILE=/dev/null`, no inherited
configuration, install, repair or network before any Torch operation.

## Protocol, ownership and case order

Private nonblocking command/report pipes and a CLOEXEC exec-error pipe bind
role, nonce and strictly increasing writer sequences. Control records fit in
512 bytes and observed PIPE_BUF. DATA binds length (at most 256 KiB) and SHA256
to exact UTF8 body bytes. G drains DATA before ARM so a larger body does not
deadlock behind the pipe buffer. One logical write uses a monotone cursor:
positive partial progress sends only remaining bytes. EAGAIN waits and partial
reads keep the same absolute deadline. No bytes are retransmitted. EOF before
completion, malformed framing or an unexpected partial control write is
permanent failure. G validates framing/identity; the strict outer parser
independently hashes/parses the body and recomputes metadata success.

READY/product validation precedes CHECK, complete DATA precedes ARM, and
ARM_ACK/final ACK precede the primary action. Normal sends FINISH, observes
FINISH_ACK/report EOF and G's exact P reap with raw wait status 0, with no
directed signal. Worker loss consumes the original G-to-P signal budget before
one flags-0 pidfd SIGKILL, then requires terminal poll/report EOF and G's exact
P reap with raw status 9. There is no descendant/adoption or subreaper claim.

A failed, interrupted, ESRCH or unknown signal result remains consumed and
forbids later signals/new commands. Numeric FD reuse never resets a budget.
Expected immediate EBADF after a successful close and bounded nonblocking
EAGAIN progress are separate positive/wait facts. All unexpected errors preserve
partial evidence and withhold success. Negative cleanup sends no signal.

All times use G's one monotonic t0: work 20 s, cleanup 25 s, terminal 28 s,
G-total 30 s and P-expiry 35 s. Fresh strict identity/live/time predicates guard
each action and final acceptance. CPU limits are 20/21 s with core size 0.
Expiry intent is not observed recovery. The finite outer 40-second backend
owns only its direct G child and cannot guarantee all descendant, guardian,
observer or host-loss cleanup.

## Fixtures and remaining gates

Portable fixtures exercise 76-pin/header failures, six-origin/symlink/drift
checks, flags and request/hash bounds, framing/identity/order/budget failures
and incomplete/unknown results. Parser fixtures construct a clearly labelled
synthetic native row and mutate its DATA hash/length/header, writer sequences,
READY payload, same-PID transition, original handles, signal budget, exact reap,
terminal EOF/poll and absolute clocks. Rebinding a mutated DATA body's hash
isolates semantic failures from framing failures. These illustrative rows use
synthetic PIDs, calls, scalar values and clocks; only their temporary metadata
tree supplies filesystem observations. They are not native output or ABI
evidence and require no relaunch.
Additional synthetic descriptor fixtures cover all four declared ELF class/
endianness pairs, full/view hash separation, trailing full-file drift before
build, and malformed bounds/table/PT_INTERP cases without executing those bytes.
Negative parser fixtures also preserve an explicit failed close and the
subsequent actual-format badfd fact. A failed close is not rewritten as success
or discarded; its closed first-error record and partial evidence remain
available while success is withheld. Malformed negative call records still
fail schema validation.

Four strict Linux fixtures compile/link the new
guardian and exercise synthetic normal, worker loss, actual closed interpreter
FD `fexecve` failure (EBADF/raw71), and actual bootstrap worker-hash failure
after exec (raw70). Both faults forbid ARM, signal and narrow success.
Only non-Linux skips those native fixtures; missing Linux prerequisites fail.

The four narrow flags describe fixed Python transition, readonly 76 metadata/
six positions, normal reap and worker-loss reap. The seven broad authority
fields remain false. Fixed CPU success does not establish pip dependencies,
Torch/Tensor/grad/model ABI, training, quality, production containment, arbitrary
exec/descendant or host-loss recovery, complete installed/mapped payload,
physical exclusion, GPU lease or independent complete foreign restore.

Fresh host work requires independent source review, commit/push, new attached
PR, latest exact-head CI and main integration, then new scope/case/nonce/path/
attempt/ledger/request and independent exact prelaunch. Controlled returned
facts do not independently retrieve remote raw products/headers/markers or
prove fsync durability, whole ancestry or node-alias authenticity. All prior
and newly consumed episodes remain consumed: no retry, resume, old PID/argv,
alternate interpreter, old native guard relaxation or receipt unlock.
