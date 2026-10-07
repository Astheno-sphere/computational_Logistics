# V8 native preparation: source checks and owned CPU watchdog

V8 training needs to verify the actual loaded adapter/head/base tensors and
first original optimizer step, and to contain its own processes if a controller
exits. This change prepares those checks while model execution remains closed.
It adds no new training, prediction, GPU reservation or borrowed-queue recovery.

The separate native source is `4b55c6e3f025fd92ec4396d5c61bb4dfe13cbda2`. The unchanged scientific source
is `d8eeb3d1f8e8d8751476f102ab456170c277e86a`; its frozen 18 files, training
plan and prepared data hashes all match. A new external CPU declaration was
created only after the native source push matched the remote ref. One actual
local check verified both clean Git checkouts and their exact source blobs.
The independent actual-source audit passed 95 checks. Original argv and push
output buffers were not retained; their digests are recorded assertions. The
verifier stdout/empty stderr and actual committed source blobs were retained
and checked. These are source checks, not fresh runtime/data/weight staging.

## What is implemented and what was exercised

| Component | Implemented contract | Evidence in this local snapshot |
| --- | --- | --- |
| Native model helper | Exact saved tensor dtype/shape/value checks, active unmerged adapter, declared numerical settings, row timing and scoped allocator peaks | Injected CPU fakes; no real tensors, Torch import, ABI or CUDA validation |
| Original training observer | Original initializer and original AdamW instance pre-step hook; bindings restored; weak model reference | CPU fakes; no additional forward/backward/step; no real gradients observed |
| Owned CPU watchdog | Fresh boot/UID/birth/ancestry/nonce, pidfds, start handshake, subreaper, exclusive atomic receipts | Portable process fixtures and real local file-publication tests; four live Linux fixtures skipped on macOS and passed in source-A Ubuntu CI |
| Source verifier | Separate exact clean native/science checkouts, native seven-file and scientific 18-file closure, frozen plan/freeze references | One actual local stdlib verification, all execution/resource/model-observation flags remain false |

The local focused suite ran **50 tests: 46 passed, four Linux-only tests
skipped**. The full repository ran **1,235 tests: 1,146 passed, 89 skipped**, with
zero failures/errors. The whole-source independent review passed 84 checks;
separate cross-reviews passed 73 and 23 checks, with each author excluding their
own implementation from independent review. Linux completion/timeout/escaped
descendant/controller-loss fixtures execute in GitHub CI; its current head
checks are a separate integration gate, not part of these local test counts.
The saved source-A Python 3.14 CI log reports 1,235 tests, 1,145 passed and
90 skipped. Its four live pidfd cases map to successful progress dots in
unchanged discovery order. Case names are inferred from that order because
the runner uses verbosity 1. This proves GitHub CPU containment, not MS GPU
or original-queue recovery; the optional data/dependency skips differ locally.

The first-gradient policy requires every present trainable gradient to be
finite FP32, reports missing gradients without imputation, requires at least
one pooled nonzero element in each LoRA-A/LoRA-B/head group, and requires absent
base gradients. It does not require every trainable parameter to receive a
gradient; a scalar head bias can have zero gradient for a Choice batch. No batch
is changed to make this audit pass.

## Boundaries and retained findings

`--execute` refuses before any declared-path checks or attempt creation. The
native ownership callback is a future external dependency. The CPU watchdog
only controls its newly owned worker tree, within a 60-second work deadline
and up to 10 seconds cleanup. It does not pause or restore another queue,
optimizer checkpoint, sampling service or GPU lease. Controller-loss cleanup
requires its watchdog and kernel to survive; watchdog SIGKILL, host loss,
privilege changes or unreadable ancestry cannot yield a successful proof.

Both comparison Calibration fits must precede every heldout forward. The
unchanged comparator materializes fixed heldout rows before fitting, so this
is not a claim that it never parses them. Original 2932-row/733-step science,
four loads, fixed temperatures, safety gates and no retry/resume/promotion
remain unchanged. No natural trial, official JevBench result or model gain is
claimed. External completed trials remain zero.

Retained findings cover the original mocked-Git fixture error, saved-tensor
casts and cached scientific imports, observer model retention, and partial
JSON visibility. The source was corrected before its commit; the failed review
r1 was a reviewer text-match defect and r2 used AST validation without changing
source bytes. The original records are retained rather than overwritten.

See [the implementation protocol](../../docs/frontier-v8-native-runtime.md),
[native declaration](native-declaration.json), [source verification](actual-source-verification-r1.json),
[local regression](root-full-tests-r1.json), and
[independent source review](independent-native-runtime-source-review-r2.json).
The next model phase requires a separately reviewed live staging, GPU lease and
complete original-queue restoration protocol; this snapshot grants none.
