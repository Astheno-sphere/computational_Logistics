# V8 fixed owned C worker lifecycle fixture

This separate CPU observation builds and runs one new C product for exactly one
declared case: `normal` or `controller_loss`. The product accepts only that
closed case and a fresh 64-hex nonce. It accepts no external PID, executable or
command. Its four C roles are a coordinator, controller, guard and one fixed
worker. The Python observer/bootstrap and compiler/linker processes are
additional activity outside those four roles. The worker does not exec another
product or create descendants, services or model workloads.

The narrow observation flags are
`normal_owned_direct_worker_lifecycle_observed` and
`controlled_controller_loss_worker_reaped_observed`. Each is conditional on
actual returned facts and fresh postvalidation for its own case. This document
does not assert that CI or a host episode has already succeeded.

## Source, compiler and runtime boundaries

The seven-file source closure consists of the new observer, C translation unit,
tests and this document, plus three immutable standard-library utilities:
`frontier_v8_containment_capability.py`, `frontier_v8_c_toolchain.py` and
`frontier_v8_owned_c_selfcheck.py`. The observer captures their exact pinned
bytes and executes those bodies in distinct non-main namespaces. It uses pure
identity utilities, the compiler backend and pure ELF/link-map parsers; their
old observations, CLI routes, products, requests and attempts are not called.
Science and native module bodies are not imported.

A future declared file route has six deployed inputs: the five source files
needed by the observer and one fresh request. The request binds the observer,
C source and three utility hashes, case, nonce, attempt directory and expected
host/bootstrap. The bootstrap executable is separately read and bound. The
file entry requires Linux, equal UID/EUID and `-B -I -S`.
`--execute` is rejected before request processing, captured-utility loading or
compiler resolution. Ordinary Python and standard-library startup precede
that CLI guard; it grants no production execution route.

The compiler role is `cc` through the controlled `/usr/bin:/bin` path. Version,
dependency discovery and preprocessing precede object compilation of captured
preprocessed bytes. The new object is linked to one fresh `lifecycle` product;
only that product is invoked with the declared case and nonce. The compiler,
headers, object, product, reported link files and product interpreter are bound
by regular-file identities and SHA256 values. The object and product ELF
descriptors must agree. Link-map files are inventoried after linking, so their
hashes do not authenticate their bytes throughout the link operation or every
file the tools accessed.

The nested `compile_leg` remains the unchanged object-only utility result. Its
C-runtime and own-pidfd flags remain false, and its product link/execution count
is zero. Separate new aggregate `link` and `runtime` command receipts describe
this lifecycle product; the nested result is not rewritten as a runtime proof.

The C source requires Linux/GNU system headers and symbolic `SYS_pidfd_open`
and `SYS_pidfd_send_signal`, with declared target-size and representability
checks. Calls use the reviewed signatures
`syscall((long)SYS_pidfd_open, (long)owned_fork_pid, (unsigned long)0)` and
`syscall((long)SYS_pidfd_send_signal, (long)owned_fd, (long)SIGKILL, (void *)NULL, (unsigned long)0)`.
The source never substitutes a guessed syscall number, provider filename or
architecture. The captured preprocessor expression remains opaque to Python;
the C compiler evaluates it. Header values and ELF descriptors describe the
fresh product, without proving a host architecture or kernel-global capability.

Inputs, marker, observer identity and output parent/directory are rechecked
before compilation, before product invocation and during postvalidation.
Compiler/header/link/interpreter/output bindings are also rechecked before and
after runtime. Detected drift blocks success. These boundary checks do not
continuously authenticate mapped code or provide a sandbox for trusted tools.

## Fixed roles and handshake order

The coordinator captures its boot ID, PID/PPID, UID/EUID and process start ticks,
plus an inherited product descriptor's device, inode, mode, owner, size and
mtime/ctime baseline. It creates bounded private nonblocking pipes, then forks
the controller first. The controller sends a nonce-bound ready packet and
parks on its sole coordinator command pipe. The coordinator compares that
packet with its own fork return and fresh `/proc` identity, then opens a
controller pidfd and checks its reported PID.

The coordinator next forks the guard. The guard inherits the anchored
controller pidfd, product identity and common time epoch. It closes unrelated
pipe ends, including the inherited controller command writer, sends its ready
packet and waits. The coordinator independently binds the guard fork identity
and product, opens its matching pidfd, then sends `GUARD_START`. The guard forks
the single worker only after validating that start packet. Thus worker creation
does not precede the coordinator's guard binding.

The worker closes unused inherited pipe ends, the controller pidfd copy and
guard report writer before sending its ready packet. It retains only its ready
writer, guard command reader and the product descriptor needed for its identity
baseline. The guard binds its own worker fork PID, parent, birth, boot, UID/EUID,
nonce and product, opens a worker pidfd, and forwards complete readiness to the
coordinator. Controller pidfd readiness is checked during setup/progress waits;
early controller loss is a negative setup result.

Packets have fixed size no greater than `PIPE_BUF`, exact magic, kind, role,
case and nonce bindings. Short reads/writes accumulate only to that fixed size
under the absolute deadline; a partial packet cannot release a role. Only after
complete guard and worker readiness may the coordinator send the case ARM
packet. The guard then rechecks its own and worker identities, inherited
product and deadline, verifies the controller is still live, records arming and
sends the matching ACK. The coordinator validates that ACK before issuing the
fixed controller exit command. The returned packet ledger calls these
case-bound actions `case_arm` and `case_ack`; they implement the normal and loss
ARM/ACK routes without accepting an arbitrary action.

For `normal`, the armed guard expects the controller's orderly exit, sends the
fixed worker completion command and observes worker pidfd exit. The guard is
the worker's sole `waitpid` parent and must reap that exact worker with exit
code zero. The coordinator separately observes and reaps its controller and
guard children with exit code zero. A successful normal case sends no process
signal.

For `controller_loss`, the coordinator's fixed command makes the controller
exit with code 23 only after the loss ACK. The guard requires the exact
controller pidfd exit event, then rechecks its own/worker identity, product and
cleanup deadline before one symbolic pidfd `SIGKILL` attempt to its worker.
There is no PID-kill fallback or signal retry. The guard observes worker pidfd
exit and reaps that exact child with `WIFSIGNALED` and `SIGKILL`. The coordinator
reaps only its controller and guard; the guard never reaps the controller.
The product installs `SIGPIPE` ignore for its own inherited signal disposition
so pipe failure can be reported as `EPIPE`; this is separate from the one
worker-directed signal in a successful loss case.

The guard returns a terminal facts packet before exiting. The coordinator
drains it within its deadline, then matches its own controller/guard pidfd and
`waitpid` results. Python recomputes wait classifications, identities, packet
order, deadlines, signals and close outcomes from the facts. A returned success
label or boolean cannot replace actual poll, syscall and wait results.

## Absolute deadlines and descriptor facts

The coordinator captures monotonic `t0` before any pipe or fork. Every forked
role inherits that same epoch and these absolute deadlines:

| Deadline | Bound |
| --- | --- |
| `t0 + 5 s` | Setup, readiness, arming, ACK and controller command |
| `t0 + 8 s` | Owned worker action, pidfd exit and worker reap; latest signal window |
| `t0 + 10 s` | Guard terminal packet and coordinator drain |
| `t0 + 12 s` | Worker's bounded self-expiry route |
| `t0 + 14 s` | Coordinator final controller/guard reap and report |

Waits use nonblocking operations with repeated finite, nonreverse monotonic
checks against those absolute bounds. A new read does not reset the epoch.
The worker's later self-expiry is a bounded code path, not proof that cleanup
was observed. The outer backend separately allows 30 seconds for each direct
compiler/link/runtime child and a two-second direct-child kill/reap window.

Four managed pidfd records cover coordinator-to-controller,
coordinator-to-guard, guard's inherited controller copy and guard-to-worker.
Each acquired handle gets at most one close attempt, immediate result/errno,
and, after successful close, an immediate `F_GETFD` check for `-1/EBADF` with no
intervening descriptor opening. The worker's additional inherited controller
pidfd copy is recorded in its inherited-close ledger rather than counted as a
fifth managed pidfd. Per-role ledgers also record unused pipe-end closes and
their immediate `EBADF` checks before readiness.

Controller and guard close inherited standard streams before the guard creates
worker pipes. Those private pipes may reuse descriptor numbers 0, 1 or 2. The
worker closes descriptors by their current pipe role; it does not blindly
close those numbers as standard streams. Ledger kind plus descriptor number
distinguishes reused slots. These ledgers cover the declared inherited
descriptors, rather than authenticating every descriptor a process could hold.

Handled failures retain the first typed error beside separate unknown or
observed operation outcomes. If an acquired worker pidfd and fresh owned
identity/product are still valid before the cleanup deadline, the guard may
attempt at most one owned cleanup signal. Failed revalidation forbids that
signal. Coordinator cleanup covers only its anchored controller/guard children;
their cleanup signal outcomes remain separate. Early exit, missing readiness,
partial report, identity drift or expired deadlines remain negative even if a
later close or reap succeeds.

## Scope and evidence limits

Even a successful fixed case leaves `functional_containment_verified`,
`containment_available`, `execution_available`, `resource_authority`,
`model_runtime_ABI_observed`, `production_controller_guard_completed` and
`GPU_or_foreign_restore` false. This is a direct owned worker fixture, with no
foreign PID, SIGSTOP/SIGCONT, GPU, queue, installation or model action. It does
not validate a production controller/guard, resource lease, numerical
tensors/gradients, model quality or foreign queue restoration.

Returned controlled-process facts are caller evidence. They do not provide
independent remote artifact retrieval, durability, continuous source-byte or
mapped-code authentication, complete ancestry, node-alias authentication or
physical exclusion. `/proc`, compiler, linker, loader, libc and filesystem
behavior remain trusted baseline dependencies. A product `fstat`/ctime check
does not authenticate the complete runtime mapping.

The four-role topology does not establish whole-tree containment. Guard,
coordinator, observer or host loss, async interruption and failed terminal
writes can leave unknown cleanup or no complete receipt. The outer backend
handles only the direct child it created; compiler/linker descendants are
outside its cleanup guarantee. No full descendant cleanup, controller-loss
recovery for arbitrary workloads or host-loss recovery is claimed.

Portable fixtures exercise strict declarations, partial/forged reports,
foreign identities, wrong reap ownership/status, close outcomes, drift and
deadline/order failures. Separate strict Linux fixtures require fresh normal
and loss cases with actual compile/link/runtime and authoritative outcomes;
missing compiler/header/runtime prerequisites on Linux are failures. Injected
backend seams remain CPU fixture evidence. Actual test results require saved
CI or host evidence.

Each case uses a separate fresh attempt/source binding and nonce. Host cases
require their own declaration and exact prelaunch after source review,
commit/push, attached PR, latest exact-head CI and main integration. Every
consumed failure remains consumed. There is no retry, resume, alternate
interpreter, old product/PID/request reuse, native guard relaxation, OS API shim
or receipt-boolean unlock. Existing science, native, data, plan and freeze
bytes remain unchanged.
