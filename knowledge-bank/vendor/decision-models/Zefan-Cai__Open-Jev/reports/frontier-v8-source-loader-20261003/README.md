# V8 source provenance and no-borrow checks

Three real, separate clean Git checkouts were verified once on macOS against
the fixed scientific and native commits and the pushed operational source
`2571666656e5b470a6198f9abe6e37591c8a445e`. They use sparse inventories to
preserve disk space. Every declared file was materialized and checked against
its actual regular Git blob and SHA256; the whole repository was not copied.

The CPU context imported five scientific source modules and one native source
module directly from captured, verified bytes, plus an empty synthetic
`scripts` namespace. It checked origins, module and callable identities,
optional-package absence and restored import state. No trainer, model loader
or comparator scoring function was called. Raw stdout/stderr and external
declarations are included; this is source provenance, not model execution.
Recorded `compiled_code_sha256` values are post-execution fingerprints within
that interpreter. CPython reference state affects marshal encoding, so they
are not canonical digests or an independently reproduced compile-only proof.
Canonical source SHA256 values bind the actual captured bytes.

Local regression passed 39 of 40 focused tests with one Linux skip, and 1,264
of 1,369 full tests with 105 skips. Independent source review passed 48
mechanical checks and 14 manual checks. Root independently preserved the bytes
of 63 original source/data/declaration/history files; the source reviewer did
not independently open or hash data bodies. Counts are CPU checks, not gold
evaluation scores. Both source-head Ubuntu CI jobs, Python 3.10 and 3.14,
passed all 40 new named cases and 1,279 of 1,369 full tests with 90 skips.
Their raw logs include the new Linux pidfd case as `ok`: it checks a real,
nonempty owned CPU worker tree with injected host/GPU/source observations.
The independent actual-source proof passed 80 checks. Its initial inspector
error compared two textual Homebrew paths for the same interpreter binary;
the additive review resolves both paths and preserves the original finding.

The separate no-borrow adapter checks current process identities, protected
physical GPU0/1, selected H100 observations, source and CPU stage-marker bytes,
cooperative flock/inodes and deadlines. Its tests inject host/GPU/source
observations; the default live-host path has not executed on MS. Neither a
passed check nor a CPU stage marker grants physical exclusion, runtime/weight
attestation, model authority, queue restoration or a complete resource episode.
Canonical helper imports require a trusted clean interpreter with `-B -I -S`
and no existing cache or foreign modules; disk attributes cannot authenticate
forged Python modules. A production guard-to-model-worker bridge remains pending.

The forged `.pyc` test first demonstrates a genuinely accepted timestamp cache,
then confirms the adapter uses the bound source bytes instead. Earlier fixture
errors and their fixes are preserved. Initial loader r1/r2 output was available
only in the author's tool transcript; no raw files were recreated. Files named
`tool-transcript` or `tool-chunk` are labelled transcript copies, not original
split streams. Later r3/r4/r5 and final root regression are saved raw outputs.

Local source proof and MS preparation made zero model calls, training runs,
Torch imports, model/runtime installations, SSH connections, GPU or foreign
queue actions, browser actions or external trials. Both source-head GitHub CI
jobs installed build tooling with pip for packaging and ran owned CPU fixtures.
Frozen
scientific/native sources and data are unchanged. Production execution remains
closed; no capability, natural-use, official JevBench or HTTP-speed claim follows.

The [implementation boundaries](../../docs/frontier-v8-source-loader.md) and
[frozen scientific plan](../frontier-v8-training-protocol-20261003/training-plan.json)
remain applicable. Historical model attempts, replays, installations and
declarations retain their consumed state.
