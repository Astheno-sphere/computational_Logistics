# Current Linux prerequisite presence: observed, guard blocked

One fresh N1-1 CPU observation completed under the original, hash-bound
CPython 3.11.15 executable. The current `env -i`, `-B -I -S` process lacks the
`os.pidfd_open` attribute. `signal.pidfd_send_signal` and `select.poll` are
present and callable. Linux and equal UID/eUID predicates pass, but the
immutable native guard's presence predicate is false. No containment API was
called. This is a prerequisite diagnostic, not ABI or model success.

The process returned `presence_observed` with input and own-process
postvalidation passed. All functional containment, containment availability,
execution and resource-authority flags remain false. See [result.json](result.json)
and the exact [process stdout](actual-CPU-presence-launch-r1.stdout.txt).

## Source and execution separation

[PR34](https://github.com/Zefan-Cai/Open-Jev/pull/34) introduced only the
observer, its tests and documentation. Source A is
`8a4889f3136a5f3a4f541228dc2053577a05c7a1`; merge is
`98ff09158568044dd8268816ad7198b531dc5008`. The integrated tree equals source A.
Independent source and committed reviews passed 45 and 18 checks. All four
latest exact-A CI jobs passed on attempt 1.

The two already saved push logs each contain 1449 tests, `OK (skipped=90)`,
hence 1359 derived passes, plus successful wheel builds. Independent raw-log
review passed 65 checks, including all 19 new named methods and both Linux
cases. Those cases exercise GitHub CPU fixtures, not N1-1 capability,
functional APIs, GPU ownership or queue restoration. The local focused run
passed 17 methods and skipped the two Linux cases. Raw logs remain private;
the public proof binds their hashes and limits rather than reproducing them.

A separate exact prelaunch review passed 75 checks before any host operation.
The standard transport reserved a fresh private staging directory, copied
exactly the committed observer and a fresh seven-field request, then invoked
that file once in the foreground with the original executable and an empty
CUDA visibility environment. Two explicit SSH calls and one SCP call used
three transport invocations. Underlying socket/SSH connection counts and
inherited SSH-config multiplexing were not independently measured. All three stages returned zero; raw launch
stdout is 4114 bytes and stderr is empty. Independent actual saved-evidence review passed 56 checks, binding all three
reviewed argument lists, the once-only ledger and complete streams. No further
host calls or artifact retrieval occurred in this phase. Every declaration, staging path and attempt
is consumed; no retry, resume, overwrite or interpreter substitution is allowed.

## Evidence limits

The full stdout is process-emitted returned-call evidence. It is not an
independently retrieved remote receipt or consumed-marker file, nor a proof of
crash durability. Boot, UID/eUID and own PID birth were checked before and after
observation. Parent identity, ancestry and node-alias authentication remain
unverified. CPython and standard-library imports are trusted inputs; module
origins describe this baseline rather than authenticate library payloads.

Plain exclusive `mkdir` and `scp -p` rely on trusted SSH, ancestors and private
staging. They do not provide per-file transport `O_EXCL`/`O_NOFOLLOW`, hostile
same-UID race protection or physical resource exclusion. The observer applies
its own no-follow input walks and postvalidation. The local caller's timeout
is not an independent host-loss guard; none occurred. A spawn, write, interrupt
or host-loss failure could leave partial streams or an incomplete final receipt.

The earlier [PR33 negative ABI report](../frontier-v8-runtime-abi-20261003/README.md)
remains unchanged and permanently consumed. This new process's missing
attribute does **not** retrospectively identify which predicate failed in that
old launch context. It also says nothing about functional kernel support.

There were zero Torch imports, runtime ABI observations, model calls, training,
GPU actions, foreign-queue actions, installations, browser actions and completed
external trials. No package metadata, 76-pin check, pip check, CUDA initialization,
weight, tensor or gradient was examined. Science A, native A, prior data and
plan/freeze bytes remain fixed; no old campaign, controller or replay restarted.
The [next note](next-owned-controller-adapter-feasibility-note-r1.json) is only a
proposal for separately reviewed owned CPU prerequisite work, not a launch,
source declaration, API shim or readiness grant. No social post or new draft
was made for this diagnostic.

Original source-review findings concerned generic foreign-proc and device
paths reaching an open before refusal. The committed observer now rejects
`/proc`, `/sys` and `/dev` generic paths before open; its negative fixtures use
mocks and did not access those endpoints. Original preview bytes and findings
remain preserved. The initial result draft also overstated transport calls as
network connections; the corrected text reports invocations and retains that
finding and original draft bytes. These amendments changed no source or
actual-observation evidence. The initial index also repeated a literal local-home
prefix in two redaction-rule descriptions. Its original bytes and independent
finding are retained privately; the rule wording is now generic.

## Public subset

[evidence-index.json](evidence-index.json) records exact copies and explicit
local-home redacted derivatives, each with separate original and public hashes.
Local-home replacements preserve the remaining bytes; a derivative is not an
original receipt. Private source inputs, full saved CI logs and local caller
bytes remain hash-bound. The actual observation is supported by stdout rather
than an independent remote-file retrieval.
