# Readonly installed pip source capture

This source candidate captures a bounded subset of the already installed
`site/pip` tree as opaque bytes. It prepares exact installed implementation
bytes for later independent static review. It does not run pip, evaluate
dependency requirements, establish dependency consistency, or import any
installed package. Source freeze, integration, and an actual host observation
require their own accepted receipts.

The scope is
`frontier_v8_readonly_installed_pip_source_capture_CPU_fixture`. Its source
closure consists of the new collector, tests, this document, and the unchanged
76-version lock. A future deployment has two exact Git inputs (collector and
lock) and one fresh non-Git request. Each scope, nonce, root, request, ledger,
and attempt is fresh and consumed once. Failure does not permit a retry,
resume, repair, alternate interpreter, or additional retrieval.

## Process and input boundary

One foreground Python collector performs the file reads. It creates no child
process and directs no signal. Caller, SSH, interpreter, loader, and trusted
stdlib startup are additional activities. There is no new C product,
compiler, linker, guardian, package loader, pip subprocess, model, or GPU
operation in this source-only scope.

The declared command uses an empty environment with
`PIP_CONFIG_FILE=/dev/null`, the independently bound interpreter, `-B -I -S`,
and the exact literal `BOOTSTRAP` from the reviewed collector source. Bootstrap
arguments independently bind the observer path and SHA, request path and SHA,
and exact request byte count. The request cannot certify its own digest.
Bootstrap captures and checks observer and request bytes before compiling and
executing the same captured observer bytes. The original files remain mutable.
Directly running the script is not an alternate interface.

Absolute paths are traversed from `/` using anchored directory descriptors and
`O_DIRECTORY`, `O_NOFOLLOW`, and `O_CLOEXEC`. Regular inputs use
`O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC`. Empty, dot, dot-dot,
ambiguous, non-ASCII source names, symlinks, special entries, and cross-device
pip descendants are rejected. Before-entry, opened-file, post-read, and final
entry tuples are compared using dev, inode, mode, UID, GID, link count, size,
mtime, and ctime; atime is excluded. Actual read count must match observed size.

The collector requires the declared Linux boot/hostname/UID and actual process
identity, checks its interpreter and inputs, and keeps the installed site out
of `sys.path`. Already imported pip/vendor or any of torch, transformers,
peft, triton, safetensors, and accelerate causes rejection. No `.pth` or
customize hook executes. Interpreter hash, `/proc/self/exe`, `sys.executable`,
and stdlib origin observations describe a trusted baseline; they do not
authenticate all loaded code, ancestry, physical exclusion, or a model ABI.

## What is captured

Before and after source traversal, two fresh synthetic-or-installed site
snapshots must contain exactly the frozen 76 METADATA names and versions.
Only distribution-name case/hyphen normalization is applied. Missing, extra,
duplicate, symlinked, escaped, or drifting metadata rejects the capture. No
`Requires-Dist`, PEP 508, installed payload, or importability interpretation is
performed. The actual pip METADATA location and `site/pip` root are bound
separately; `pip==24.0` is a metadata observation, not an assumed private API.

Only `.py` and `.pyi` regular-file bodies are selected. Each selected file
returns its pip-root-relative path, actual byte count, SHA-256, `raw_hex`, and
observed stat tuple. Source bodies are not decoded, parsed, compiled, imported,
or executed on the host. `pip/__init__.py`, `pip/__main__.py`,
`pip/_internal/commands/check.py`, and the `pip/_vendor` directory must be
ordinary observed entries for a later independent review.

Every enumerated child counts, including ignored entries. Regular data,
licenses, native files, and `.pyc` files are excluded with metadata only.
`__pycache__` directories are excluded without traversal; their contents are
unobserved and unauthenticated. Rejection of symlinks and special files covers
actually enumerated entries. The manifest is a source subset, never a claim
that the full pip/vendor package or all resources and mappings were captured.

## Bounds and failure evidence

The pip root has depth 0 and starts the traversed-directory count at 1. The
root is excluded from first-pass unique entries. Incremental FD-anchored
`scandir` charges each yield before processing; cap+1 closes the iterator and
fails without sorting or processing an over-limit batch. Iterator descriptors
are charged with other owned input descriptors. Before/after enumeration
yields are reported separately from unique entries.

| Bound | Limit |
| --- | ---: |
| First-pass pip children | 4,096 |
| Actual source enumeration yields | 8,192 |
| Traversed directories, including root | 512 |
| Maximum depth | 16 |
| Simultaneously owned input and iterator FDs | 24 |
| Each selected file | 2 MiB |
| Selected source bodies combined | 8 MiB |
| Each site scan / all four scans | 8,192 / 32,768 yields |
| Each METADATA / one snapshot total | 256 KiB / 2 MiB |
| Serialized stdout UTF-8 body | 32 MiB |

One finite monotonic `t0` starts after bootstrap/source/request validation and
before marker or site work. Interpreter startup is outside that measured
interval. Work must finish strictly before `t0 + 30s`; closure and bounded
failure output may continue only before `t0 + 40s`. Reverse, nonfinite, or
expired clocks fail permanently. Individual filesystem or stdlib calls can
block beyond cooperative checks; caller timeout does not prove remote or
descendant cleanup.

A failure records `status="failed"`, bounded stage/type/message, a list of
successfully checked complete files, and at most one current partial file.
Retained partial bytes carry their actual count/hash/raw_hex and
`complete=false`, `partial=true`, even if a later drift occurred after the
full bytes had been read. Pre-open failures have a null current partial.
Global failure certifies no complete tree. No new input work follows failure;
only owned-descriptor closure and bounded failure emission may follow.

## Candidate output and caller acceptance

The producer can report `status="source_capture_candidate_ready"` and
`source_capture_complete=true`. It always keeps
`source_capture_verified=false` and `output_completion_claimed=false` because
its payload cannot certify its own later complete transmission.

Stdout must be the declared private caller-controlled pipe/FIFO. Before the
first payload write, the collector observes its flags, enables `O_NONBLOCK`,
and rereads the flags. One write cursor advances only by positive actual
returned counts. Short writes continue with the unwritten suffix; EAGAIN may
wait only to the same total deadline. Zero, invalid, unknown, or failed writes
fail. Written bytes are never retransmitted. This assumes exclusive use of
the declared open-file description and does not authenticate arbitrary sinks.

The caller and independent actual review may accept the narrow flag only
jointly from rc0, no timeout or cap overflow, complete strict bounded JSON,
actual stream count/hash, expected scope/nonce/source/request/self/input
bindings, returned body hashes/counts, and finite emission/transport facts.
A partial stream remains its original failed/unparsed bytes; missing JSON
cannot be repaired or reconstructed as a receipt. A producer marker or saved
candidate copy is not independent remote durability or transmission evidence.

## Fixtures and remaining gates

Tests use fresh temporary synthetic pip trees and METADATA generated from the
unchanged lock. They never load the workstation's installed pip/vendor.
Opaque invalid UTF-8 and top-level failure sentinels exercise byte-only
capture. Filesystem drift, small cap, clock, and write-cursor mocks are
synthetic tests, not MS observations. Strict Linux literal-bootstrap fixtures
cover five fresh cases: normal, wrong observer SHA, wrong independent request
SHA, wrong independently declared request byte count, and metadata mismatch.
The count case keeps the actual request bytes and SHA correct, declares one
extra byte, and requires nonzero return, empty stdout, and no attempt marker
before temporary-root cleanup. Unsupported platforms skip Linux FD fixtures and do
not select an alternate host or provider. The test harness's foreground
subprocess is distinct from collector-created children.

Before a host case, the four-file closure needs bound focused validation,
independent source and preservation review, freeze, commit/push, independent
committed review, attached source PR, latest exact-head push/PR CI, saved CI
review, and actual source/main integration. Only then may a fresh declaration
and independent exact prelaunch authorize one capture case. Captured installed
bytes then need independent API/import review before a separately reviewed
dependency-checking implementation or any pip entry.

`dependency_consistency_verified=false` and `pipcheck=0` throughout this scope.
The seven broad fields remain false: `functional_containment_verified`,
`containment_available`, `execution_available`, `resource_authority`,
`model_runtime_ABI_observed`, `production_controller_guard_completed`, and
`GPU_or_foreign_restore`. Model/Tensor/gradient/training/install/CUDA/GPU/queue,
browser, and external trials remain outside this work. Scientific, data,
weights, plan, and freeze pins are unchanged. CPU source capture is not a
model gain or a social-publication milestone.
