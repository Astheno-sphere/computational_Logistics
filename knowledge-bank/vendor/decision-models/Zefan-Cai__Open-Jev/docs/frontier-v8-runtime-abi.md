# V8 separate Linux CPU runtime observation

The observer can make one explicit CPU import/arithmetic observation in the
existing isolated Python 3.11 runtime. It creates no environment, downloads no
package or weights, loads no model and controls no GPU or queue. The scientific
and native commits, frozen plan/data, PR31 bridge and all previous consumed
outputs remain unchanged. `--execute` refuses before request or path handling.
Source review, push, exact-head CI and integration precede any real host run.

The entrypoint is `--observe-cpu --request PATH --expected-request-sha256 HASH`
under a fresh `-B -I -S` interpreter. A separately reviewed external request
has exactly these fields:

- `schema_version`: 1; `scope`: `frontier_v8_runtime_CPU_ABI_only`.
- `nonce`: fresh 64 lowercase hex characters; `observer_sha256`: exact new source.
- `source_context`: the unchanged source-loader's ten-field context, binding
  three separate sparse clean Git roots and external plan/freeze/declarations.
- `host`: `node_alias`, `hostname`, `boot_id`, `uid`. The alias is one of N1-1,
  N1-3 or N4-1 through N4-4; it is trusted transport input, not host authentication.
- `bootstrap`: `realpath`, `sha256`, `python_version` for the actual controller.
- `runtime`: canonical `venv`, `interpreter_realpath`, `interpreter_sha256`,
  `pyvenv_cfg_sha256`, and exact three-element `python_version` beginning 3,11.
- `data_root`: mapped exact copy of the frozen prepared 13 JSONL files plus
  `manifest.json`. Hash bytes only; do not parse heldout examples or change plan.
- `attempt_directory`: new absolute owned output directory, outside all source,
  data and runtime inputs; no symlink ancestors or existing consumed marker.
- `work_seconds`: positive finite number no larger than 60;
  `cleanup_seconds`: positive finite number no larger than 10.

The controller's separate 30-second total preflight binds request/source bytes,
current kernel host identity, bootstrap/venv configuration and interpreter, and
the exact SHA256 of captured native-A process code. It then consumes the new
attempt and writes an exact private `native-owned-process.py` copy, mode 0400.
That hash-bound helper imports before the full three-root proof. The transport
must independently validate its clean Git roots before entry. The copied helper
has its actual copy `__file__` so the unchanged watchdog re-executes those bytes;
the receipt distinguishes original native path/hash from execution copy.

The immutable primitive bounds the entire owned worker, including Git/source
and data verification, metadata, nested pipcheck, Torch import and arithmetic.
The worker verifies scientific A, native A and the newly declared operational
closure from pinned captured source-loader bytes before any package import.
Scientific/native model modules are not imported. Postflight independently
compares the same source/plan/data hashes and exact request again under its own
30-second total controller bound. Clone/transport bounds are separate inputs;
60 seconds is not a whole SSH episode or foreign-queue restoration guarantee.
`controller_observation_elapsed_seconds` includes guard cleanup, receipt parsing
and postflight; it is not a worker-only or model timing measurement.

Python 3.11 `-S` may leave `sys.prefix` at the base interpreter. Validate the
declared canonical venv, its `pyvenv.cfg` and lexical `venv/bin/python` against
the declared resolved executable/hash. Preserve the real prefix values; do not
forge venv prefixes. Select only that venv's canonical
`lib/python3.11/site-packages`. Never call `site.addsitedir` or process `.pth`,
`sitecustomize` or user-site configuration. Preloaded optional modules, foreign
startup paths/hooks/cache objects are rejected. Newly loaded `.py` bodies are
captured and compiled directly; no timestamp/hash `.pyc` or sourceless loader
is used. Existing CPython/stdlib/builtin state remains a trusted input.

Before Torch, enumerate distributions only from that site. Reject missing,
extra or normalized duplicate names; require all 76 exact locked versions,
isolated metadata directories/roots and six direct package origins. Record
metadata and entry-source hashes. A nested `-B -I -S` child runs only
`pip --isolated check` with the same explicit site and process nonce. Set
`PIP_CONFIG_FILE=/dev/null`, discard inherited loader/proxy/credential variables
and preserve the primitive nonce for descendant ownership. The check omits
`--require-virtualenv`, whose prefix test conflicts with genuine 3.11 `-S`;
independently validated venv/site inputs establish the scope. Pip raw stdout
and stderr stream directly into exclusive files opened before the subprocess.
Partial raw bytes remain if the check is interrupted; `pip.result.json` exists
only after the subprocess returns. A failed check stops before Torch.
Recheck metadata/positions before importing it. Offline HF flags and empty
`CUDA_VISIBLE_DEVICES` are explicit; they are not a network/syscall sandbox.

Import Torch only in the separate runtime child. Record its actual version,
compiled CUDA version metadata, Torch module origins and `_C` extension hash.
Compute `[[1,2],[3,4]] @ [[5,6],[7,8]]` as explicit CPU FP32 tensors with
`requires_grad=False`; the fixed result is `[[19,22],[43,50]]`. No backward,
optimizer, training, model, adapter or scientific comparison call occurs.
Call only the noninitializing `torch.cuda.is_initialized` before/after CPU
arithmetic, and inspect NVIDIA FD endpoints before import/around arithmetic.
Do not call CUDA init, availability, device count, device properties or loading.
False initialization state and empty FD snapshots cannot exclude transient
native device access. CPU arithmetic does not establish CUDA ABI, model tensor
values/gradients, GPU ownership, physical exclusion or restoration authority.
Metadata/pipcheck are not independent wheel or installed-payload rehash proofs.

The observer/pip/Torch child argv contains `-B -I -S`. The unchanged native
watchdog internally re-executes `-I -S` without `-B`; do not expand the no-package
bytecode claim to every standard-library import in that guard. Its pidfd,
subreaper, ancestry, boot/UID/birth and fresh nonce proof applies to the new CPU
tree only. Controller loss containment requires the guard/kernel to survive;
host loss, guard SIGKILL and opaque extension internals are outside the proof.

Outputs are the sibling `ATTEMPT.consumed.json`, `ATTEMPT/receipt.json`, private
native copy, `pip.stdout.log`, `pip.stderr.log`, `pip.result.json` (including
failure return code, raw lengths and hashes), and `process-r1/` containing
`declaration.json`, `watchdog-receipt.json`, worker stdout/stderr and watchdog
stderr. Failures retain consumed paths and raw streams; never retry, resume,
overwrite or reuse old PIDs. Successful receipts still set
`execution_available=false` and `resource_authority=false`.

Portable fixtures use 76 fake metadata bodies, injected fake Torch/tensors and
opaque fake extension metadata; they perform no actual Torch/ABI observation.
The Linux fixture runs a real fresh pidfd-owned CPU metadata worker with fake
distributions, not a real venv or model. Any actual CPU ABI result requires a
new host/request/attempt after integrated source and independent preflight.

The separate committed `frontier_v8_runtime_transport.py` owns capture, public
Git preparation, launch and exact raw retrieval. It requires captured original
source-review, four exact-head CI, code-integration and prelaunch receipt bytes;
their source hashes and equal source/main trees must match. These saved receipts
are trusted local review inputs, not a live GitHub query or cryptographic proof
of authorship. A capture-only prelaunch scope cannot authorize observation.
After a fresh capture, only the separately scoped launch-preflight receipt may
change. That receipt binds original capture bytes, exact request, nonce, remote
root and the payload digest excluding only its own receipt. Capture records a
256 MiB per-user scratch capacity check; it makes no disk reservation.

`remote_command` constructs a quoted argv from this exact committed source and
the declared payload hash. It makes no SSH call. The standard shell wrapper
waits for Python and returns its status; capture still verifies actual kernel
parent/UID/boot/birth identities. Before three Git roots exist, native bootstrap
copies are captured hash-bound inputs, not final Git proof. Source preparation
runs under its own immutable 60-second worker and 10-second cleanup, using a
fresh object store and three linked sparse roots at the separate declared
commits. Public Git has no inherited credentials, proxies or user configuration.
Every declared worktree body must match both its SHA256 and actual Git blob;
all declared blobs are local before disabling promisor fetch. Partial Git raw
output streams directly into owned logs and survives a failed preparation.
The hidden source-worker entry additionally checks its actual current native
controller/guard/direct-worker ancestry and deadline before any Git command;
a matching saved JSON declaration and environment nonce are insufficient.

Before calling the observer from a copied file entry, transport authenticates
its own bytes and removes only that exact file path's `None` importer-cache
entry. A positive entry or changed source is refused; foreign entries remain
for the observer to reject. The observer also requires each permitted stdlib
FileFinder's actual path and exact loader set to match its cache key.

Retrieval reads only a fixed allowlist, including both distinct owned guard
sets and raw pip stdout/stderr/result. It uses no-follow regular-file and owner
checks, bounded original binary bytes and before/after identities. Missing and
refused paths remain explicit. Local reception validates the complete packet
before exclusively creating a new directory. Retrieval never reruns workers
or claims observation success. Candidates derive from the original reviewed
payload, so a missing or corrupt remote declaration does not prevent failure
evidence retrieval. Current boot continuity and original declaration hash
matching are reported separately. Transport fixtures use artificial receipt/data
bodies and mocked Git commands; they test configuration, three-root handling,
byte/hash refusal and retained failed raw output without performing a clone,
host capture, ABI import, queue recovery or production launch.
