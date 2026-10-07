# V8 native preparation and owned CPU process containment

This change adds optional model observers and a separate source verifier. It
does not enable a training or comparison command. `--execute` still refuses
before reading declared paths or creating an attempt. A new live GPU lease and
borrowed-queue restoration protocol must be reviewed separately.

The scientific implementation remains the clean checkout at
`d8eeb3d1f8e8d8751476f102ab456170c277e86a`. Its 18 files and the frozen
[training plan](../reports/frontier-v8-training-protocol-20261003/training-plan.json)
are unchanged: published 2B initialization, 2,932 Train rows, 733 accumulated
steps, four comparison loads and both full Calibration fits before any heldout
forward. The frozen comparator materializes its fixed heldout rows before
those fits; this is not a claim that it never parses heldouts.

## Separate source declaration

`scripts/run_frontier_native_v8.py --verify-declaration` verifies an external
CPU declaration, the exact native commit and seven-file inventory, and the
separate clean scientific checkout. The declaration, plan and freeze must
live outside both checkouts. The verifier must run from the declared native
checkout. Inherited Git overrides are excluded from these local Git checks.

The declaration references the completed PR27 installation by its receipt
and independent review hashes. These references do not refresh the host,
installed environment, data or weights. Successful verification retains
`execution_available=false`, `resource_authority=false`, and
`borrowed_queue_restoration_available=false`; numerical settings, real model
loads and gradients remain unobserved.

The native modules live under `scripts/`, outside the scientific `jev` package.
A future child must import the scientific package from Source A and bind its
runtime, source, full data/weight inventories and live ownership independently.
The source declaration has no executable model argv.

## Optional native model observers

`scripts/frontier_v8_native_model.py` imports only standard-library modules at
module load. Its `make_loader` returns the context manager consumed by the
existing comparator. The required `assert_owned` callback runs before optional
imports, allocation and each row. The callback is an external dependency;
calling it does not itself establish ownership.

Given a valid future stage, the loader checks full checkpoint/snapshot hashes,
applies the declared CUDA numerical settings, checks the physical device UUID,
and compares retained base, adapter and head tensors against their saved
values. It requires frozen BF16 base parameters, FP32 LoRA/head parameters and
an active, unmerged adapter. It retains comparison loading time separately
from row time. Row time includes tokenization, forward, CPU logits and CUDA
synchronization; it excludes HTTP, journal writes and probability aggregation.
Allocated/reserved peaks include resident weights and allocator caching and
are not physical total or minimum VRAM.

`observe_training` wraps the original child-local `initialize_model` and
original AdamW factory, attaches a pre-step hook to the returned original
optimizer, and restores both bindings and the hook on exit. It adds no
forward, backward, optimizer step, retry or training row. The first hook sees
the original accumulated and clipped gradients immediately before the first
step. The unchanged trainer journal still needs separate completion validation.

The gradient policy is declared before any real batch:

- Every present trainable gradient must be finite and FP32.
- Missing gradients are counted without imputation or another backward pass.
- Each pooled group, LoRA-A, LoRA-B and head, must contain at least one nonzero
  gradient element. Per-group missing, zero and nonzero coverage is recorded.
- All frozen base gradients must be absent.

This does not require every trainable parameter to receive a gradient. A scalar
head bias can have zero gradient for an all-Choice batch. The first batch is
not inspected or changed to make this check pass.

CPU tests inject fake tensors and dependencies. They test rejection and
observation contracts, not actual published weights, Torch ABI, CUDA, gradient
coverage or model quality. Optional imports and allocation have not run in
this preparation workflow.

## Owned CPU watchdog

`run_owned_cpu_worker(argv, *, attempt_directory, timeout_seconds,
cleanup_seconds=5.0)` runs a trusted CPU fixture with an absolute executable,
no shell and an exclusive output directory. Its work limit is 60 seconds and
cleanup limit is 10 seconds. It retains the declaration, logs and watchdog
receipt. The controller registers its independent watchdog before sending the
start handshake; the watchdog is the worker's parent and a Linux subreaper.

The watchdog binds current boot, UID, process birth, ancestry, session and
fresh nonce, and opens pidfds. It walks only its own kernel child lists.
Timeout, catchable interruption or controller loss triggers pidfd cleanup of
its newly owned worker tree, including adopted descendants that changed
session. It returns success only after the worker exited successfully, bound
members exited and the subreaper has no remaining children. An interrupted or
expired fixture remains consumed even when its tree was fully cleaned up.

This primitive does not inspect or signal shared jobs. It does not pause or
restore another queue, optimizer checkpoint or sampling service and does not
issue a GPU reservation. CUDA visibility restrictions are not access control.
Controller-loss containment requires the watchdog and kernel to remain alive;
watchdog SIGKILL, host loss, privilege changes or unreadable ancestry cannot
produce a successful cleanup proof.

Portable fixtures cover process identity, PID reuse and signal races. Live
Linux fixtures exercise completion, timeout, escaped descendants and
controller loss; they skip on macOS. Their execution in CI is separate from
any MS host staging or borrowed-queue recovery.
