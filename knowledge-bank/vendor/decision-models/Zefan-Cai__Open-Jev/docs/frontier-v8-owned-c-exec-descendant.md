# V8 fixed owned C exec and descendant fixture

This separate CPU fixture has the fixed tree `G → X/E → D`. Guardian G forks
one X, whose one `fexecve` changes its product to E without changing its PID or
birth identity. E forks one fixed descendant D only after G validates the
postexec identity and sends `CREATE_D`. Two fresh ELF products, guardian and
leaf, implement the closed `normal` and `worker_loss` cases. They accept no
external PID, arbitrary command, respawn, model or foreign process action.

This document describes the source contract. Actual verification requires
separate test, CI or host receipts; this document asserts no successful test,
compiler, host or model result. The tests/docs author previously
cross-reviewed the design, then changed role to source author and cannot serve
as a later independent source or actual-result reviewer.

The Python observer recomputes `fixed_exec_transition_observed`,
`fixed_normal_descendant_reap_observed` and
`fixed_worker_loss_descendant_adoption_reap_observed` from the complete facts for
the declared case. A returned C success boolean alone cannot set these flags.

## Source and execution boundaries

The new source closure has nine files: the new Python observer, guardian and
leaf C translation units, protocol header, tests and this document, plus three
unchanged pinned utilities. Their SHA256 pins are:

| Utility | SHA256 |
| --- | --- |
| `frontier_v8_containment_capability.py` | `1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412` |
| `frontier_v8_c_toolchain.py` | `2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0` |
| `frontier_v8_owned_c_selfcheck.py` | `3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c` |

A future file deployment has seven Git runtime sources and one fresh nonGit
request, eight files total. The request binds the closed scope
`frontier_v8_owned_C_fixed_exec_descendant_CPU_fixture`, source hashes, case,
fresh nonce, attempt directory, host/bootstrap identities and seven false
authority fields. Captured pinned utility bytes supply only pure identity,
compiler, ELF and link-map functionality; their old observations and CLI routes
are not called. `--execute` stays rejected before request/utility processing.
Science/native/data/plan/freeze inputs and all old consumed outputs remain
unchanged. A request or receipt boolean does not confer execution authority.

Fresh dependency discovery, preprocessing, object compilation and linking bind
both new products and their common header. C uses reviewed symbolic system
headers and signatures for pidfd and child-subreaper operations, without a
guessed syscall number or provider. Postlink file snapshots describe that
instant, rather than all bytes seen throughout linking or every mapped runtime
file. Trusted compiler, linker, dynamic loader, libc, filesystem and `/proc`
behavior remain baseline dependencies. Python/bootstrap/compiler activity is
additional to the three fixed runtime roles and preexec state.

## Exec and descriptor identities

G opens the exact fixed leaf once with `O_RDONLY|O_CLOEXEC|O_NOFOLLOW` and creates
one witness with `F_DUPFD_CLOEXEC`. X has a finite fixed argv, an empty environment
and a CLOEXEC exec-error writer. Its original inherited standard streams are
closed before the one `fexecve`. A return from `fexecve` is a permanent negative;
X can report an error frame and exits 71 without fallback or retry.

Exactly two X `PRODUCT_CHECK` packets with aux 1 and 2 must precede
`PRE_EXEC_READY`; their metadata does not independently reverify the unreturned
fstat payload tuples.

`EXEC_ENTER` is a prospective private marker. A before-call flag or clock error
keeps exec attempted/returned facts false/null. Confirmation comes from an
actual fexecve return, or from the complete postexec product/identity gate.
Startup facts and EOF from the witness fault remain useful negative evidence
without completing that joint gate.

E's first application FD operations require the old leaf descriptor, witness
and exec-error writer numbers to return `-1/EBADF`. Its retained command reader
and report writer remain live without CLOEXEC. An exec-error EOF alone cannot
authorize descendant creation: G also requires `POST_EXEC_READY`, startup FD
facts and its independent exact product/live identity transition checks.
The PID, start ticks, boot ID, UID/EUID and PPID must remain bound across exec.
The dynamic loader runs before `main`; these checks do not establish
uninterrupted numeric FD vacancy or a complete loader closure.

The FD ledger keys each acquired handle by owner, semantic label and acquisition
epoch. Closing an old handle consumes its once-close budget; a reused number
does not reset that budget. D's original standard-stream entries are
`original_absent`: close/result/errno/EBADF facts are null and unattempted,
because X already closed those original handles. E's newly acquired child pipes
may legally occupy FD 0, 1 or 2. D retains its exact child command reader and
report writer and closes only the actual other endpoint labels in their child
generation. There is no bare `close(0/1/2)`, close-range sweep or inference from
the number alone. A claimed stdio close of a retained child endpoint or duplicate
provenance must be rejected.

Private pipes are CLOEXEC and nonblocking. Fixed wire frames fit within both
512 bytes and the observed compiled/runtime `PIPE_BUF` bound. Writes are one
bounded atomic attempt under the absolute deadline: EAGAIN, EPIPE, EINTR or a
short write is negative, without retry. Positive partial reads may accumulate
under that same deadline. Each writing role installs/rechecks local SIGPIPE
ignore using reviewed `sigaction` facts; this is distinct from a directed signal.
Forwarded D packets retain D's role, nonce and source sequence; forwarding
transport does not change the source edge. After expected loss EOF, D parks
without trying to write an ERROR to killed E.

## Case order, ownership and deadlines

The three managed pidfds are G-to-E, G-to-D and E-to-D. G first binds the live
preexec X identity and G-to-E handle. Exec and joint postexec verification precede
`CREATE_D`; D identity/readiness and all fresh parent/handle checks precede ARM.
In normal, E reaps its own D with raw wait status 0, and G reaps only E with raw
status 0. Normal sends no directed signal and G never waits for D.

In worker loss, G attempts G-to-E `SIGKILL` once with flags 0, observes the
matching E pidfd terminal event and reaps E with raw status 9. It must then
observe D's PPID change from E to G with all other identity/product fields stable
before one G-to-D `SIGKILL` and the adopted D reap with raw status 9. The E-to-D
handle's killed-owner teardown fields remain null; no explicit close is invented.
Any failed, ambiguous, interrupted or ESRCH E signal consumes the attempt and
permanently forbids D signaling. Its attempted planned action remains recorded;
negative cleanup adds no directed signal. There is no PID-kill fallback, handle
budget reset or signal retry. WNOHANG
`waitpid` invocation attempts are distinct from the one successful reap.

Every role shares one monotonic `t0`:

| Absolute bound | Purpose |
| --- | --- |
| `t0 + 5 s` | Work, EXEC/CREATE_D/ARM/FINISH and immediate G-to-E signal check |
| `t0 + 8 s` | E reap, D adoption and immediate G-to-D signal check |
| `t0 + 10 s` | Positive reaps, private FD completion, reset and final clock |
| `t0 + 12 s` | G's negative observation limit |
| `t0 + 14 s` | Child self-expiry code path |

Fresh finite, nonreverse clock checks occur after identity/live validation and
immediately before each action. New I/O and polling do not reset these bounds.
The child expiry intent is not an observed cleanup result. Post-D errors may
park until child expiry; G's earlier limit cannot claim their later recovery.
If G's actual final clock reaches or exceeds its 12-second bound, the strict
parser refuses complete parsing; raw/error/unknown evidence remains without
inventing an earlier time or claiming complete cleanup.
A terminal error after an actual reset preserves its attempted reset/final-get
facts and the first error while withholding success. An earlier failure cannot
authorize a reset by copying those facts from a successful case.
A writer cannot report its own postclose over that writer. Separate EOF/exit
evidence has its own limits. G stdout stays open through final JSON and has no
invented close/EBADF or stdout-closure success gate.

The `exec_fd_closed` fixture closes only the newly owned exec descriptor before
one fexecve. The actual EBADF/error and X exit 71 must leave D absent and directed
signals zero. The `witness_cloexec_cleared` fixture leaks only the new owned
witness. E reports its actual startup live-witness fact, once-close/immediate
EBADF, ERROR when possible, then exits 70 immediately. G may observe raw E wait
17920 before its terminal deadline; an incomplete return remains failed/unknown.
That saved startup error forbids CREATE_D, ARM, FINISH, signals, reset and narrow
success, even if the direct E reap completes.

## Fixtures and evidence limits

Portable synthetic fixtures exercise request/hash/type bounds, combined
exec/product/EOF gates, packet order, action deadlines, provenance and FD number
reuse, wrong wait ownership/adoption, signal failure budgets and incomplete
negative preservation. Four strict Linux cases build/link/run fresh
normal, worker-loss and the two faults. They skip only on non-Linux; missing
Linux compiler/header/runtime prerequisites or incomplete facts fail. Synthetic
constructors are illustrative inputs, not observed syscall or remote receipts.

All broad fields stay false: `functional_containment_verified`,
`containment_available`, `execution_available`, `resource_authority`,
`model_runtime_ABI_observed`, `production_controller_guard_completed` and
`GPU_or_foreign_restore`. Fixed CPU success is not production containment,
arbitrary exec/descendant recovery, guard/coordinator/observer/host-loss recovery,
model ABI, tensors/gradients, model quality, resource lease or foreign restore.
No Torch, model, training, install, GPU, queue, browser or external trial action
belongs to this fixture.

Controlled returned facts do not independently retrieve remote raw stdout,
headers/products/markers or prove fsync durability, complete mapped code,
ancestry, node-alias authenticity or physical exclusion. The outer backend owns
only its direct runtime/compiler child; toolchain descendants lie outside that
cleanup guarantee. Every new host case needs independent source review,
commit/push, attached PR, latest exact-head CI and main integration, then its own
fresh scope/nonce/path/attempt/declaration and exact prelaunch. All old and newly
consumed cases remain permanently consumed, with no retry, resume, old PID or
argv reuse, alternate interpreter, native guard relaxation or receipt unlock.
