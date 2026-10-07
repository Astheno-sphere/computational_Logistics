# V8 source loading and no-borrow preallocation

This CPU preparation separates source verification and import provenance from
live resource checks. It does not launch a model, consume a training attempt,
or operate an existing queue. Production execution remains unavailable.

The scientific checkout stays at
`d8eeb3d1f8e8d8751476f102ab456170c277e86a`; the native checkout stays at
`4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2`. The operational checkout has its
own declaration and commit. These are three separate actual clean Git roots;
a report or merge commit cannot replace either frozen source. The scientific
18-file closure, native seven-file closure, data, plan and freeze are unchanged.

## Source verification and CPU imports

`scripts/frontier_v8_source_loader.py` checks exact checkout roots, commits,
regular Git blobs and their hashes against external declarations. It rejects
overlapping roots, symlinked paths, dirty or extra checkout files, and changed
declarations. Verification is a source identity check, not a runtime, data,
weights, GPU or optimizer attestation.

The CPU import context loads the unchanged scientific driver, comparator and
trainer, and the native observer. It checks the actual source and import
origins and rejects conflicting cached modules, paths and import hooks. Native
modules use a separate alias so the two source trees cannot compete for the
scientific `scripts` namespace. Source loading must not execute ignored cached
bytecode. Temporary import state is restored on success and failure.

These are real imports of the verified source modules. They do not call the
trainer, comparator or native model loader. Optional model packages, tensors,
CUDA and gradients are still unobserved. The original driver/comparator/native
execution refusals remain intact. A returned CPU bundle or receipt supplies
no resource authority. This source-only context is not a Python sandbox;
calling optional model functions falls outside its verification scope.

Portable fixtures use temporary real Git repositories and fresh Python
processes. They exercise wrong commits, dirty files, blob/hash mismatch,
source mutation, shadowing and import contamination. A separate committed
source check uses the actual two fixed source commits and the newly pushed
operational commit. Neither kind of check proves model behavior.

## No-borrow live-host checks

`scripts/frontier_v8_live_host.py` provides a separate preallocation check. Its
live path reads current Linux process identities and physical GPU observations;
it does not accept a prior CPU fixture owner as live authority. Only N1-1,
N1-3 and N4-1 through N4-4 are eligible. The selected physical H100 must be
outside protected GPU0/1 and have no unrelated compute process. The kernel
hostname and local address must match the declared node.

The owner checks boot, UID, PID birth, ancestry and nonce, retained controller
and guard pidfds, cooperative lock descriptors, exact marker/inode identity,
source receipt and declared CPU stage marker bytes, and monotonic deadline
boundaries. The stage marker is not a verified runtime/data/weight stage. The work and
recovery ceilings remain 4,500 and 1,500 seconds. A passed check means only that
these observations currently match. Cooperative locks cannot exclude another
host user; no physical GPU exclusion or model execution authority is granted.

The adapter's existing process/parser dependencies come from the operational
checkout. Their recorded paths and disk hashes do not authenticate a module
already forged inside a Python interpreter. Its caller must use a trusted clean
interpreter, suppress bytecode writes before importing the adapter (for example
with `-B`), and reject pre-existing caches. Ordinary imports that dirty a source
checkout cause subsequent strict source verification to refuse. A deployed
controlled adapter import bridge remains pending.

CPU fixtures label injected GPU observations explicitly. Linux pidfd tests
contain a fresh owned CPU tree through the existing native CPU watchdog.
They do not pause a foreign job, free CUDA memory, run a 4,500-second GPU
episode, or prove a 1,500-second original-queue restoration. A production
guard-to-model-worker bridge and independent real restoration evidence remain
required before any GPU phase. No foreign process can qualify merely through
a numeric PID, owner string, snapshot or boolean receipt.

## Remaining execution requirements

A later separately declared phase needs current full runtime versions and
package positions, pip check, data and weight hashes, actual Torch/ABI/CUDA
observations, native numerical settings and tensor/gradient evidence. It also
needs an integrated launcher and live resource ownership protocol with
independent recovery. Existing installation attempts and all previous model
attempts remain consumed; this preparation does not retry them.

The fixed 733-step training pass, two complete 496-row Calibration fits before
heldout forwards, four comparison loads, four temperature cells and inclusive
.2/.8 safety gates remain in the
[scientific plan](../reports/frontier-v8-training-protocol-20261003/training-plan.json).
CPU provenance and lifecycle checks establish no model improvement, natural
trial, business action, official JevBench result or HTTP speedup.
