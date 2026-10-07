# One CPU compiler/header/compile-target observation

A fresh isolated N1-1 process completed the declared compiler pipeline once.
All four compiler invocations returned 0 and were reaped; input/self, compiler,
dependency and output postvalidation passed. The generated object was never
linked, loaded or executed. Native runtime ABI, own-pidfd operations, functional
containment, model-runtime ABI, execution and resource authority remain false.

Source [PR38](https://github.com/Zefan-Cai/Open-Jev/pull/38) was integrated before
this episode. Exact source A is `ee3f6001f07881d8ec5b6b5d96f6ec8cea50f556`;
code merge is `000656e164dd0c8d1fd1f10d6962c7360e50d640`. See the fixed
[source documentation](https://github.com/Zefan-Cai/Open-Jev/blob/ee3f6001f07881d8ec5b6b5d96f6ec8cea50f556/docs/frontier-v8-c-toolchain.md).
The original scientific/native sources, data, plan and freezes were unchanged.

## Observed compile target

These are controlled-observer returned build metadata, not independently
retrieved remote compiler/header/CPP/object payloads or a kernel-capability test.

| Field | Returned value |
| --- | --- |
| Standard compiler role | `cc` via controlled `/usr/bin:/bin` |
| Canonical driver | `/usr/bin/x86_64-linux-gnu-gcc-11` |
| Driver SHA256 | `821af3c74506283c179ca413bb33e6b528805a4dd8a5c09df125e5ad560a9e89` |
| Dependencies | 60 entries: fixed C TU + 59 headers; 60 distinct reported canonical paths |
| Dependency bytes | 296779, including the C TU |
| Expanded `SYS_pidfd_open` expression | Opaque text `434`, from headers; never guessed or executed |
| Target int / long / pointer size | 4 / 8 / 8 C bytes |
| Target character width / byte order builtin | 8 / 1234 |
| Object descriptor | ELF relocatable, class 2, data 1, machine 62; 1368 bytes |
| Object SHA256 | `6ac4f8c0a65615a9c086013aee8e13979c25a3468fb22362b3f4307dde5eece9` |

The ELF descriptors and driver filename do not establish the live host's runtime
architecture or ABI. Driver/dependency hashes are descriptive under the trusted
compiler/filesystem baseline; they do not authenticate the complete frontend,
assembler, loader or mapped-code execution closure. Compiler/CPython native
startup and ordinary OS syscalls occurred. Zero direct pidfd/syscall probes
means none in the generated translation unit, not zero OS syscalls globally.

## Evidence and limits

The caller preserved complete stdout: 28985 bytes, SHA256
`c0d4e0fe7ee9af2c508f1288cfb444e30ebd2466f4cce3456c3bcb81070e56b7`;
stderr was empty. `actual-process-stdout.txt` is that returned process evidence;
`result.json` is a separately authored root summary, copied exactly. Neither is
an independently retrieved remote receipt. The observer reported consumed-marker
postvalidation, without independent marker retrieval or durability proof.

Only 2 SSH + 1 SCP transport invocations occurred, all returncode 0. Distinct
underlying connections were not measured. Parent/ancestry, compiler child birth,
process groups, descendants, node-alias authentication and physical exclusion
were not verified. No compiler kill or timeout occurred here; the implementation
only offers a bounded direct-child kill/reap attempt on timeout, without
compiler-descendant or host-loss cleanup guarantees.

Local new focused checks were 18 pass + 2 Linux skips. Two source-head Ubuntu
push logs each recorded 1493 tests: 1403 named `ok`, 90 skips, wheel success; all
20 new named methods, including both strict Linux cases, were `ok`. All four
latest source-head push/PR checks on Python 3.10/3.14 succeeded, attempt 1.
GitHub temporary object/receipt bodies were not independently preserved. These
are CPU fixtures, not MS kernel-global, model, GPU-lease or queue-restoration proof.
Independent reviews accepted design32, source54, committed70, savedCI91,
prelaunch82 and actual111 checks, each within its stated scope. Actual reviewer
authored the C TU/tests/docs, not observer/dispatcher/raw; that role is disclosed.

The post-episode 149 opaque paths remain byte-identical: 114 tracked + 35 non-Git
paths (26 data + 9 run evidence). This is byte preservation, without dataset
parsing or an all-Git-blob claim. Reviewer context/schema/ancestry-reader mistakes
and their corrected receipts remain private and are disclosed in the code gate;
they did not change source, original evidence or scientific pins.

No Torch import, model call, training, pipcheck, runtime installation, CUDA
initialization, GPU action, foreign-queue action, browser posting or external
trial occurred in this host phase. CI build-tool installation is separate from
an MS/model-runtime installation. This prerequisite result is not a model
capability or performance improvement. Earlier negative Python/C-export episodes
remain consumed history and are not retroactively explained by these target facts.

This indexed subset excludes the private saved raw CI logs, other API/Git
buffers, staging proof copies and unreceived remote compiler/header/object bytes.
Only actual caller-home substrings are redacted in marked derivatives; original
and derivative hashes are distinct. Exact copies, including no-op redactions,
are labelled exact. The index excludes itself. All current requests, nonce,
paths and attempt are permanently consumed. Any future owned-C runtime/self-FD
adapter needs separately reviewed/integrated source, fresh compilation/header
bindings and a new declared episode; current outputs or receipt booleans cannot
unlock the old production execution guard or grant GPU rights.
