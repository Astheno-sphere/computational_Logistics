# V8 resource-control CPU preparation

This phase adds current resource capture, an independent Linux episode guard,
live lease checks, a separate recovery auditor and an injected scientific-child
contract. **Production GPU/model execution and foreign-queue restoration remain
unavailable.** No v8 training, inference, installation, borrowing, browser action
or external trial took place.

Initial operational source: `4b82f353d6278cc75033f4deefd2b3f98eaa8390`.
Corrected operational Source C: `86af19ed223323d937020fedf5cc3ef29c01ece0`; its separate
[inventory](deadline-fix-source-manifest.json) preserves the historical Source A manifest.
[Source manifest](source-manifest.json) binds ten Git blobs and explicitly grants
no launch authority. The [implementation documentation](../../docs/frontier-v8-resource-episode.md)
describes the interfaces and remaining deployment boundary. The original
scientific SourceA, native SourceA, 18 scientific files, seven native files,
plan and freeze remain byte-identical; see [27 integrity checks](original-integrity-r1.json).
No old controller, PID, consumed attempt, install or replay was restarted.

## Validation and limits

The [initial Source A local regression](local-regression-final-r2.json) ran 93 focused
checks: 78 passed and 15 Linux cases were skipped on macOS. The full repository
ran 1,328 tests: 1,224 passed and 104 skipped, with no failures/errors. All ten
source hashes matched before and after these tests. The intermediate 92/1,327
run remains [preserved](local-regression-intermediate-r1.json); the
[amendment](root-regression-r1-history-amendment.json) explains the later backend
fix and added test. These local results do not claim Linux lifecycle execution.

Both initial Source A Ubuntu CI jobs, Python 3.10 and 3.14, succeeded: each ran
1,328 tests with 1,238 passed and 90 skipped. All **15 named Linux lifecycle
cases passed in each job**, including controller SIGKILL, catchable interruption,
timeout, failed work, escaped descendants, owner loss and eight-process original
recovery. The [raw-log binding](source-A-CI-named-Linux-proof-r2.json) records
each exact named line and log hash; [3.10](python-3.10.raw.log) and
[3.14](python-3.14.raw.log) logs are retained. These are owned simulated CPU
queues on GitHub, not MS GPU or xiaofan recovery.

The first log checker assumed Python 3.14's method display inside parentheses.
Python 3.10 prints only module/class there. That [checker finding](source-A-CI-log-checker-finding-r1.json)
is preserved; the revised reader accepts both standard formats from the same
once-downloaded logs. Source and CI were not rerun. All latest corrected report-head CI must succeed before integration.
The subsequent first-report PR failure and its correction are recorded below.

[Capture/recon review](independent-capture-recon-review-r2.json) passed 126 checks.
[Episode review](independent-episode-review-r1.json) passed 82 checks. Independent
[science/auditor review](independent-science-restoration-review-r3.json) confirms
11 scientific-child and 30 auditor CPU tests, plus retained repair reproducers.
[Root child review](root-independent-scientific-child-review-r1.json) records
20 source/sequence checks. These reviews have distinct scopes; their counts are
not summed into a model or gold-label score.

Directory scan errors and replacement races, a known worker changing ancestry/
session, parent-zombie interpretation, incomplete lease-marker hashing, missing
owner deadline/source binding and delayed release were found and repaired.
Original findings and author receipts remain in this directory. A prior capture
review binds the documentation that existed then; the final episode review
binds the updated documentation. Scientific/data bytes were not changed.

## What the CPU fixtures establish

The new guard has separate maximum budgets of 4,500 seconds work and 1,500
seconds recovery, using same-boot monotonic clocks. The old 60/10-second CPU
helper is unchanged. The new guard/worker reread three source files, kernel
birth identities, bound pidfds, live ancestry, retained lease descriptors,
exact marker bytes, physical identities and deadlines. A concrete bounded
read-only `nvidia-smi` backend is implemented but mocked in its tests.

GPU records in the lifecycle fixtures are injected. Original fixtures must be
new descendants of that controller and carry its dedicated nonce. They receive
only pidfd STOP/CONT, never checkpoint reload or process restart. All original
fixture GPUs are reserved together. The independent auditor rereads complete
trees/full hashes, processes, protected GPU0/1, loopback HTTP response bytes and
actual integer progress. Queue recovery requires four ranks, a coordinator,
three services and progress advancement in the simulation. HTTP200 means
endpoint availability, not socket ownership or successful rollout counts.

The strongest result is `same_process_resource_recovery_observed`, with
`queue_restore_proven: false` and `optimizer_boundary_proven: false`. Independent
known-process/group observations do not replace the guard's whole-tree pidfd/
subreaper quiescence proof. Cooperative locks do not exclude nonparticipants.
Unproven recovery retains markers; partial or late release records exact released
UUIDs and overall failure. Guard/host loss cannot promise recovery.

The scientific-child tests inject source, stage, training, observation and
completion callbacks. They call the unchanged comparator on 4,784 invented
oracle-logit rows: four loads, two complete Cal fits, 20 heldout and two Cal
journals. These are **CPU fixtures, not model predictions**. No real native
tensors, gradients, ABI or runtime settings were observed. The production
module factory and execution entrypoints still refuse before request reads.

## Deadline classification correction

The first report B's two push jobs passed, but its Python 3.14 PR job failed:
[raw log](python-3.14-report-B-PR-failed.raw.log) records an expected
`work_deadline` reason becoming `ownership_lost`. Python 3.10 was then
[cancelled](python-3.10-report-B-PR-cancelled.raw.log). The exact
[snapshot](report-B-CI-snapshot-r4.json), [finding](report-B-PR-CI-finding-r1.json)
and original bytes are retained. No manual CI retry was requested.

A [deterministic counterexample](deadline-classification-finding-r1.json)
reproduced expiry between the guard's outer clock check and the owner's first
or final clock check, plus expiry before launch. Source C changes only the
episode and its tests: a typed expiry retains `work_deadline`; reversed/nonfinite
clocks and genuine identity/source errors keep their original classifications.
The 4,500/1,500-second bounds and cleanup, restoration and release algorithms
are unchanged. [Independent delta review](independent-deadline-classification-review-r1.json)
passed 82 checks. One new unittest covers six boundary subtests, using mocked
process/tree/auditor inputs; it establishes classification, not live recovery.

The existing 0.15-second Linux timeout begins before guard startup. A legitimate
prelaunch expiry now requires exact `worker_not_started`, no worker identity
and no stdout/stderr launch artifacts. An already launched worker still requires
nonempty members and every pidfd exit before independent recovery/release.
The renamed case's pass alone does not prove that job launched a worker.
[The amendment](deadline-classification-amendment-r1.json) lists its current name
and preserves this limitation. Other lifecycle cases retain their separate scope.

[Corrected local regression](local-regression-deadline-fix-r3.json) passed
79 of 94 focused tests (15 Linux skips) and 1,225 of 1,329 full tests
(104 skips), with no failure/error. All ten source hashes were stable through
that run. All four corrected Source C push/PR CI checks succeeded. Both
push jobs, Python 3.10 and 3.14, ran 1,329 tests with 1,239 passed and 90 skipped;
each passed all 15 currently named Linux lifecycle cases. The new deterministic
unit method also passed; its six subcases are a source-derived count, not six
separately named raw-log results. [Source C log proof](source-C-CI-named-Linux-proof-r2.json)
binds [3.10](python-3.10-source-C.raw.log) and [3.14](python-3.14-source-C.raw.log).
The renamed timeout case retains the prelaunch limitation stated above.

The new unit method has a docstring, so verbose unittest prints its method name
and docstring/result on separate lines. A [first checker finding](source-C-CI-log-checker-finding-r1.json)
is preserved; the revised reader uses those original lines. No source/CI rerun
or log redownload was performed. All latest final report-head CI checks must
succeed before integration.

## Current node observations and next boundary

One [six-node read-only observation](readonly-recon-summary-r1.json), at
approximately 12:40 UTC, reached N1-1, N1-3 and N4-2 through N4-4. All 40 H100s
had compute processes in both samples; candidate vacancies were zero. N4-1
returned SSH255 and remains unknown. Exact raw stdout/stderr stays in private
run evidence; its hashes are retained. Single-point PID metadata does not prove
live ownership, checkpoint recoverability or a reservation. No public-IP retry,
excluded-node scan or repeated R-KV grant request followed.

Future host work needs a separately integrated operational loader, three exact
source checkouts, current 76 package versions/positions/pipcheck, full data and
weight hashes, live physical GPU rights and actual native runtime/tensor/gradient
observations. A real xiaofan loan additionally needs a fresh task-owner scope,
recoverable optimizer boundary, service/config/socket evidence, every original
GPU reserved and independent complete recovery. This fixture STOP/CONT path
does not provide a checkpoint/restart adapter for an exited job. Existing pause
authorization persists; these are technical evidence requirements.

The fixed 733 × 4 training and comparison protocol is unchanged. No capability,
HTTP speedup, natural pilot or official JevBench result is claimed. The candidate
cannot be promoted automatically. Social drafts remain unposted while the
previous Chrome availability response is pending.
