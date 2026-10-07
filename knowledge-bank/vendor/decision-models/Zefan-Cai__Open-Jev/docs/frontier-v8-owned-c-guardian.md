# Owned C guardian and adoption CPU fixture

This protocol prepares two fixed, non-model CPU cases: `guard_loss` and
`coordinator_loss`. A surviving C guardian observes the reparenting and correct
parent reaping of its own fixed descendants. It does not establish production
containment, arbitrary descendant or exec control, model execution, GPU ownership,
or restoration of another user's work.

The independently accepted revision 2 design permits implementation of the four
new observer, C, test and documentation files. Its acceptance retains 37 earlier
passed design checks and adds 17 checks of the closed negative-action policy and
interface amendment. This is permission for minimum source implementation, not a
source freeze or a host declaration. This document supplies no compiler, kernel,
fixture-execution or MS-host observation. Those results require separate receipts
and their own acceptance gates.

The phase starts from actual main
`617340b3c4315b85f71d92fbcc326276c38c473d`, tree
`7782439cf7e445fe620ac7a60ff7ea70a0e9018d`. The inherited baseline contains
2,258 Git paths: the previous 2,209 paths and 49 published result paths. The
original 185 opaque preservation paths remain 150 tracked paths plus 35 nonGit
paths. Their accepted 229 checks plus 14 binding checks are inherited evidence;
this design does not rescan their bytes.

## Source and observer boundary

The seven selected source-closure files are:

- `scripts/frontier_v8_owned_c_guardian.py`
- `scripts/frontier_v8_owned_c_guardian.c`
- `tests/test_frontier_v8_owned_c_guardian.py`
- `docs/frontier-v8-owned-c-guardian.md`
- `scripts/frontier_v8_containment_capability.py`
- `scripts/frontier_v8_c_toolchain.py`
- `scripts/frontier_v8_owned_c_selfcheck.py`

The observer, C translation unit and three immutable utilities are the five
runtime/deployed source files. A later host case also needs a separate fresh
nonGit request. Tests and documentation are not runtime inputs. The new tests
reuse `FakeCompilerBackend` and `own_identity` from
`tests/test_frontier_v8_c_toolchain.py` (30,484 bytes, SHA256
`538ba287c4f27eae26ed794b844c015a679c147af0d0efc0a848868bed81f31d`),
and pure `product_bytes` from `tests/test_frontier_v8_owned_c_selfcheck.py`
(35,283 bytes, SHA256
`d25d8a31e5df465f144c5076fc35c7f928222897235ffb0432019f23f58d43c4`).
These are test-only fixture dependencies outside the five runtime/deployed
files. Their pins come from accepted prior source-context metadata; the new test
checks their exact bytes before importing their definitions. No old test method
or CLI is called.

The utility SHA256 identities remain, respectively:

| Utility | SHA256 |
| --- | --- |
| containment capability | `1bcda91a4ac9ab50fe051b140fd7ba0fae649c257b45674d1ab15c2bb9a69412` |
| C toolchain | `2175f96e939993db69eb14348fa3115ae583416a1d38307f38f23bd378d003c0` |
| owned C selfcheck | `3374d4ed4ef1bafa38d8f4340ffcc042ee396d966228a682adf890182108b47c` |

The new observer may use captured-byte pure build, link and verification helpers.
It must not invoke prior observe/CLI/execute entrypoints or reuse their requests,
products, roots, attempts, controllers or PIDs. The new entrypoint is
`--observe-owned-c-guardian`, with scope
`frontier_v8_owned_C_guardian_adoption_CPU_fixture`. Its returned guardian receipt
belongs under `guardian`; the two narrow success names are
`controlled_guard_loss_worker_adoption_reap_observed` and
`controlled_coordinator_loss_guard_worker_adoption_reap_observed`.

Build preparation retains the existing header/CPP, compile, link and verification
stages. The additional CPP markers bind `SYS_pidfd_send_signal`,
`PR_SET_CHILD_SUBREAPER` and `PR_GET_CHILD_SUBREAPER`. Their bounded expanded C
expressions are recognized as tokens, not evaluated as Python expressions or
replaced with guessed constants. The declared compiler evaluates symbolic header
constants. C machine widths, packet bounds, syscall options and emitted values
must agree with captured target/header evidence.

## Fixed roles, identities and arm barrier

The fixed C product creates `G → C → H → W`: guardian, coordinator, guard and fixed
worker. The outer Python observer and compiler/linker add process activity outside
these four C roles. G forks C once, C forks H once and H forks W once. No role execs, adds a
child, respawns, accepts an arbitrary command or performs model work. G must
survive on the same trusted host for the whole bounded case.

Before any fork, G observes its child-subreaper flag as 0, sets it to 1 and observes
1. Each child independently observes its own value 0 before READY. An unexpected
initial value, unavailable interface or failed/inconsistent call blocks deliberate
loss. These facts concern the processes in this fixture; they do not authenticate
the host or prove a sandbox.

G independently binds the original PID, PPID, start ticks, boot ID, UID/EUID and
product/stat identity for all four roles. Allowed adoption changes only PPID;
birth, boot, ownership and product identity remain equal to the initial binding.
Every pre-signal check must refer to the same original role and original handle.
Product identity projects stat fields as device, inode, size, mtime_ns and
ctime_ns. The first three use uint64 bounds; both timestamps must be nonnegative
signed64 values matching the captured C representation.

Private frames bind case, nonce, shared epoch, kind, role and stage. H forwards W
frames separately; C forwards H/W frames separately without rewriting the
original frame. Fixed frames are at most 512 bytes and satisfy both the compiled
`PIPE_BUF` bound and the observed pipe bound. Missing, partial, duplicate,
malformed, cross-case or out-of-order frames do not authorize an action.
The packet ledger records G's `ARM`, `COORDINATOR_EXIT23` and
`COORDINATOR_FINISH` commands as edge `C_from_G`, role `guardian`, with no
forwarding claim. Received reports use edge `G_from_C`; C's own reports are
direct, while H/W READY, ARM_ACK, handle and descriptor-close frames are forwarded
unchanged. No other command/report edge is accepted.

All READY identities, handle facts, ARM acknowledgements and ALL_ARM_ACK must be
complete before deliberate loss. Forwarded READY records occur once each in
W, H, C order before G's ARM command and W's ARM acknowledgement. The physical sequence is
`W_ARM_ACK < EOF_W < H_ARM_ACK < EOF_H < C_ARM_ACK < ALL_ARM_ACK`;
handle facts and explicit descriptor-close records may interleave.

W and H close their control/report pipe paths after acknowledgement and remain
parked to their fixed expiry. Pipe EOF does not cause their normal exit or worker
cleanup. H observes W's report EOF and C observes H's report EOF while each
child's original pidfd remains nonterminal. The `H_W_EOF` and `C_H_EOF` poll facts
have stage `EOF_child_live`, matching owner/target/descriptor, actual result,
revents and errno 0, and an observation time between `arm_sent` and
`all_arm_ack`. Parent-observed EOF does not invent a close-return receipt from a
child that already closed its sole writer.
The W EOF fact originates at H and is forwarded by C, so its forwarding marker
is true. The H EOF fact originates at C and is a direct report with a false
forwarding marker, even though its displayed target role is H.

## Case order and correct wait owners

G sends both planned signals: exactly one pidfd SIGKILL to H, then exactly one to
W, with null siginfo and flags 0. C, H and W issue no directed signals. C exits by
the declared case command rather than a third signal.

| Case | C exit/raw status | Successful wait owners | Required adoption |
| --- | --- | --- | --- |
| `guard_loss` | exit 0 / raw 0 | G waits C/W; C waits H | W changes PPID H→G while C remains alive |
| `coordinator_loss` | exit 23 / raw 5888 | G waits C/H/W | H changes PPID C→G while W remains H's child; after H dies, W changes H→G |

In `guard_loss`, after the full arm barrier G signals H. C polls and successfully
waits its original H once with raw status 9/SIGKILL, reports that fact and stays
alive. `C_H_exit` names C's terminal observation of H before that wait;
`H_exit` names G's later terminal observation after receiving the parent-wait
report. Thus `H_signal < C_H_exit < H_reaped < H_exit < W_adoption` records
the observation order. G independently observes W's same-identity adoption,
signals W, and polls/waits adopted W with raw status 9. Only then does G send
FINISH to C. C closes its H handle, reports FINISH_ACK and exits 0; G polls and
waits its direct C. The explicit FINISH command frame follows GUARD_WAIT_FACT
and precedes FINISH_ACK. G does not claim to wait H in this case.

In `coordinator_loss`, G sends EXIT23 only after the full arm barrier. C closes
its H handle, reports EXIT_ACK, closes its remaining pipes and exits 23 without
waiting H. G polls and waits its direct C/raw 5888, then observes H's adoption
while W's PPID is still H. G signals, polls and waits adopted H/raw 9. It then
independently observes W's adoption, signals W and polls/waits W/raw 9. C's death
alone does not imply immediate W adoption. `C_H_exit` remains null; C's terminal
H poll and wait are unattempted. Both cases keep dead roles null in fresh
pre-signal snapshots rather than presenting an initial identity as a new read.
The explicit EXIT23 command frame follows ALL_ARM_ACK and precedes EXIT_ACK.

A signal return of 0 is not death proof. A terminal pidfd is not adoption or
parent-wait proof. A matching raw wait status is not a missing PPID snapshot.
Each required observation, correct owner and ordered step remains explicit.
All `*_exit` timestamps name the particular pidfd terminal observations in this
receipt, not kernel death instants.

## Handle closure and terminal reset

The five separately opened handles are `G_C`, `G_H`, `G_W`, `C_H` and `H_W`.
They open after the relevant fork and are identity-bound before ARM, including
before/after identity checks, fdinfo, CLOEXEC and a nonterminal poll. Descriptor
0 is legal; source labels, not assumed descriptor numbers, determine meaning.

Successful cases have exactly four explicit pidfd closures: G closes its three
handles and C closes `C_H`. Each explicit close is followed immediately by an
observed `F_GETFD == -1` with EBADF. H retains `H_W` until the planned SIGKILL.
Its descriptor is then reclaimed by process teardown; its explicit close and
EBADF fields remain null. The fixture must not fabricate a fifth explicit close.

G resets its process-local subreaper value only after the exact case predicate,
all three correctly owned managed-role reaps and its own descriptor closure are
complete. Terminal SET 0 and observed GET 0 complete the five G facts. Missing or
failed reset facts prevent success. An incomplete or unknown membership/reap
state does not permit an unconditional reset or a cleanup claim.
A negative receipt may carry a completed reset gate and attempted reset only for
an explicit `terminal_reset` failure at `prctl_set_disabled` or
`prctl_get_disabled`, after the entire pre-reset case remains valid. Missing
enable/child facts, C's explicit handle close, adoption, packet, snapshot, poll or
deadline facts still block that gate. The actual failed setter or verification
call remains in the returned negative receipt; a derived parser predicate input
does not become an observed success record.

## One epoch, bounded actions and negative state

G captures `CLOCK_MONOTONIC` t0 before preparation and forks. All roles retain
that epoch. Absolute offsets are work +5 s, cleanup +8 s, terminal +10 s,
guardian total +12 s and C/H/W self-expiry +14 s. Additions must fit observed
machine bounds, clock observations must not move backwards, and each blocking
operation uses its remaining absolute budget. No branch resets t0 or extends a
relative timeout.

The first failed, missing or ambiguous required fact, operation or deadline
irreversibly enters negative state. G then issues no later planned H/W signal
and no new ARM, EXIT23 or FINISH command. The negative-cleanup signal ledger is
explicitly empty. Even an unused W budget or a later valid adoption observation
cannot resume the planned path or convert the case to success.

Each original `G_H`/`G_W` handle has at most one signal attempt across all paths.
The attempt is consumed before the syscall, including EINTR, ESRCH, failures or
ambiguous returns. `G_C`, `C_H` and `H_W` have signal budget 0. Reopening a handle,
reusing a descriptor number or substituting a fresh target cannot replenish a
budget.
Any attempted signal in a negative receipt requires an observed first-error
timestamp. A failed or ambiguous H signal permanently forbids W's signal and
terminal reset, even if a forged later cutoff would place W before that cutoff.

After error, only bounded reads/identity observations, polls of known original
members, correctly owned identity-verified waits and once-close of known own
descriptors are permitted. G waits an adopted H/W only after the corresponding
same-identity adoption observation. Created, bound, adopted, terminal, reaped
and unknown membership sets remain separate. Negative paths cannot silently
assume ownership of an unknown descendant, send rescue signals or respawn.
`known_created` records actual observed creation. `unknown_members` lists the
expected fixed roles C/H/W whose observed reap is not established, including a
role never created; it does not claim that an unknown actual fork or process
exists.

Child error/self-expiry may produce an early nonzero exit. The +14 s source
expiry is not a substitute for planned adoption/signal/poll/wait evidence. G's
ending at +12 s does not prove later child termination or reaping. Guardian,
Python-observer or host loss may prevent a complete error receipt and is not a
verified recovery path.

## Validation and later gates

The strict parser must reject forged adoption PPID/birth/UID/boot/product facts,
wrong wait owners or raw statuses, missing arm acknowledgements, premature loss,
extra signals, contradictory clocks/deadlines, invented success values for
unattempted operations and success-shaped negative-state records. Unattempted
facts retain false attempt markers and null results/errno/values. Runtime
`success`, `failed` and `unknown` preserve their distinct meanings.
If reset actually succeeds and a later final clock or error observation fails,
the C negative body may be conservatively refused by the decoder, whose
reset-bearing negative interface currently accepts only `terminal_reset`.
The wrapper preserves `runtime.stdout` bytes and metadata, reports failure and
keeps broad flags false. It does not invent a final timestamp or promote that
output to success.

Portable fixtures exercise meaningful parser/observer rejection paths without
turning synthetic packets into kernel evidence. Exactly two real Linux positive
cases exercise the fresh owned protocol, one per case. Only non-Linux platforms
skip them; a missing Linux prerequisite or an incorrect result must fail. Pure
fixture backend dependencies remain separate from the runtime closure. Source
verification records actual outcomes and does not imply MS-host observations.

Source freeze, independent source/committed/saved-CI review, commit/push, attached
PR, all latest exact-source CI results and actual main integration precede any
separately declared host case. A later host case needs a fresh scope, nonce,
request, root and exclusive attempt plus exact prelaunch review. Failed or partial
attempts remain consumed; prior requests, PIDs, argv and products cannot be
retried, resumed or used as fallback. Any returned host result needs independent
actual, preservation, publication and committed review and result integration.

All broad controls remain false: execution availability, resource authority,
functional containment, containment availability, model runtime ABI, production
controller-guard completion, GPU/foreign restore, arbitrary descendant/exec
containment, guardian/observer/host-loss recovery, physical exclusion and queue
restoration. Header/build/link snapshots and forked product/stat identity do not
prove full mapped-code authentication, continuous byte integrity or authenticated
whole ancestry.

The scientific source `d8eeb3d1f8e8d8751476f102ab456170c277e86a` and native
source `4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2` remain distinct frozen
identities. Data, training settings, calibration/heldout boundaries and plan/freeze
bytes are unchanged. Controlled model/native bridging, live GPU ownership,
independent full queue restoration and the production 4,500 s work plus 1,500 s
restore requirement remain separate prerequisites. This fixture performs no
Tensor/gradient/model work, training, heldout evaluation, installation, browser
action or natural external trial.
