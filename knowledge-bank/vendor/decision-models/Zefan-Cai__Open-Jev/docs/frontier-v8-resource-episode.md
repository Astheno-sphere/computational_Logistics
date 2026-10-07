# V8 resource-control preparation

This change adds current resource capture, a separate Linux CPU episode guard,
an independent recovery auditor and a testable scientific-child contract. It
does **not** enable GPU training or control an existing queue. All production
execution entrypoints remain closed before reading a request or importing
Torch. The real optimizer-boundary adapter and host deployment remain pending.

The original scientific source is
`d8eeb3d1f8e8d8751476f102ab456170c277e86a`; native preparation is
`4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2`. Their 18 scientific and seven
native files, plan, freeze, data and old attempts remain unchanged. A future
operational source closure must be distinct from these two clean checkouts.
Report and merge commits cannot replace either frozen source.

## Current capture

`scripts.frontier_v8_resource_capture.capture_current` reads kernel identities,
full regular-file hashes, complete declared directory trees and two raw GPU
inventories. It records boot, UID, PID birth, ancestry, command hashes and
physical UUIDs. A no-compute H100 with an idle baseline in both samples can be
listed as a *candidate* vacancy; this is neither an exclusive reservation nor
permission to use the card. Protected physical GPU0/1 must remain consistent.
Low utilization with a compute process is occupied.

The reader accepts only N1-1, N1-3 and N4-1 through N4-4. Declared input paths
must exist on the selected host; symlinks and special inventory leaves are
refused. Expected source, data, runtime and weight hashes are reread as bytes.
This does not prove installed-package ABI, loaded tensors, or a complete usable
optimizer checkpoint. Borrowed-queue capture grants no signal authority.

The captured recovery baseline includes exact immutable directory inventories,
original identities, protected GPU state, loopback HTTP endpoints and explicit
integer progress extractors. The current progress extractor is a JSON integer;
an actual xiaofan queue adapter has not been implemented. Caller-provided
"ready", optimizer-boundary or restoration booleans cannot enable a launch.

## Separate CPU episode and live checks

`run_cpu_resource_episode` runs trusted CPU fixture code under a new independent
Linux pidfd/subreaper guard. It uses new paths, nonce and declaration, retains
exclusive cooperative `flock` descriptors, and stores persistent reservation
markers. It does not extend the old 60-second CPU helper. New limits are at
most 4,500 seconds of work and 1,500 seconds of recovery, measured with
same-boot monotonic clocks; fixture tests use short budgets.

The worker's `ResourceEpisodeOwner.assert_owned()` checks current identities,
the controller/guard relationship, bound pidfds, inherited lease descriptors,
retained path/inode and marker identity, lock contention, physical UUIDs,
protected GPUs, permitted compute ancestry and the work deadline before and
after its reads. The episode, auditor and unchanged process helper's exact
regular-file hashes and origins are checked by controller, guard and worker.
A concrete read-only
`nvidia-smi` backend is present for later integration. CPU episodes use explicit
injected GPU inventories, keep CUDA visibility empty and grant no physical
GPU authority. Cooperative locks do not exclude a nonparticipating host user.

Borrowed CPU fixtures require fresh nonce-bound descendants of that same
controller. Only pidfd `SIGSTOP` and `SIGCONT` are permitted for their original
tree, and every original fixture GPU must be reserved together. The guard never
kills, restarts or reloads these original processes. Existing foreign jobs
cannot qualify as fixture originals through a numeric PID or an owner string.

On completion, failed work, timeout, interruption, controller loss or ownership
loss, the independent guard first quiesces its new worker tree, then continues
the original fixture processes and obtains independent observations. Without
proof it preserves the failure and reservation marker. Guard SIGKILL, host
loss, privilege change or unreadable process state cannot promise recovery.
Persistent markers require an independently verified resolution; an exit code
alone does not justify removing them. If release is partial or exceeds its
deadline after successful recovery observations, the receipt records the exact
released UUIDs and overall failure; it cannot claim every marker was retained.

## Independent recovery audit

`scripts.frontier_v8_restoration_audit` does not import the capture or episode
algorithms. It independently rereads `/proc`, complete file trees and hashes,
raw GPU inventories, HTTP response bytes and two progress observations.
Borrowed fixtures require four ranks, one coordinator, three sampling services
and actual progress advancement. HTTP availability is not successful rollout
evidence or a proof that the declared PID owns the endpoint socket. PID reuse,
changed hashes, missing files, stopped originals, static
progress, failed endpoints, surviving worker identities or changed protected
GPU state fail the audit.

Its strongest successful status is
`same_process_resource_recovery_observed`. It never claims a proven real
queue optimizer boundary or a completed foreign-queue restoration. The auditor
checks the declared worker identity inventory and related process groups;
escaped-session completeness also requires the guard's subreaper/pidfd tree
proof. Mathematical replay and file hashes cannot establish live ownership.

## Scientific-child boundary

The separately named `run_cpu_fixture_pipeline` tests injected callbacks for
source checking, original driver preflight, native observation, training
completion binding and the unchanged comparator. Additional episode metadata
stays outside the scientific task. Injected source/runtime/training callbacks
are mocked provenance, not installed modules or measured training.

Production module loading and `execute_child` remain unavailable. A later
owned child must use the two exact clean source trees, current full runtime/data/
weight hashes and a separately integrated operational source. It must apply
and observe native dtype/settings/tensors/gradients, run the fixed 733 × 4
training pass, and preserve four comparison loads and both complete
496-row Calibration fits before any heldout forward. Earlier heldout
materialization in the frozen comparator is unchanged.

All four temperature cells and fixed inclusive .2/.8 safety gates retain the
[frozen scientific plan](../reports/frontier-v8-training-protocol-20261003/training-plan.json).
Failure never permits retry, resume, heldout tuning or automatic promotion.
CPU preparation establishes no model improvement, HTTP speedup, natural trial
or official JevBench result.
