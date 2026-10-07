# V8 CPU runtime prerequisite failure — 2026-10-03

[PR32](https://github.com/Zefan-Cai/Open-Jev/pull/32) integrated the CPU observer and transport, but the one declared N1-1 launch failed at the immutable native containment prerequisite before any worker, Git source preparation, pip check or Torch import. The attempt is consumed. No actual CPU ABI arithmetic result or model improvement was obtained.

Source E `e6b02497953b50c06abe4a33d38e467dbaafa7fd` merged as `47e26a67a476703cec85bced8ddaa78720e92078`, with equal source/main trees and all four latest exact-head Python 3.10/3.14 push/PR checks successful. The two inspected push raw logs each show 1,430 tests: 1,340 passed and 90 skipped, plus a wheel build. These CPU fixtures include fake runtime metadata; they establish no N1-1 runtime ABI or resource rights.

| Actual operation | Result | SSH elapsed |
|---|---|---:|
| Read-only host capture | exit 0; N1-1, UID 1000, Python 3.11.15 and recorded bootstrap hash | 2.118640 s |
| Once-only CPU transport launch | exit 1; prerequisite refusal; consumed | 24.666314 s |
| Read-only failure retrieval | exit 0; 35 files received, 48 missing, 0 refused | 23.432375 s |

The exact [stderr](evidence/actual-CPU-ABI-launch-r1.stderr.log) ends with `Linux pidfd process containment is unavailable`. `_require_linux()` is the first executable statement in `run_owned_cpu_worker()`, before kernel/controller setup, its process declaration or watchdog spawn. The individual unavailable API was not probed. The [retained transport result](evidence/transport-completion-or-failure.json) remains `transport_failed_consumed_no_retry`.

All 18 scientific, 7 native and 5 operational source leaves are absent. Source/ABI process receipts and pip streams are absent. The received declaration matches the original hash; retrieval recorded the same boot ID. The transport manifest has 34 files/82 candidates because it excludes its own 18,631 bytes; retrieval has 35 files/83 candidates and 30,099,771 raw bytes. The independent actual-evidence audit passed 104 checks. These absences are preserved, with no invented worker cleanup receipt.

The capture's 1,292,715,347,968 available scratch bytes are capacity evidence, not a reservation. The existing venv was a declared input. Fresh 76-version metadata, package positions, venv configuration, pip check and Torch ABI remain unobserved in this episode. No model, GPU, installation or queue action occurred; no retry, resume or alternative-interpreter probe followed.

Earlier source A CI failed because a mocked Git fixture declared Linux's root-owned temporary parent as its user root; C corrected only that fixture. C then exposed an inherited controller-loss reason race. E rechecks the original bound controller pidfd after the generic owner error, retaining failure and the live-controller `ownership_lost` path. Its eight unit subcases execute inside one named method, not eight named CI log cases. The initial local full run timed out at 240 seconds without a final unittest summary; it is not a full-suite pass.

[Structured result](result.json) and [evidence inventory](evidence-inventory.json) distinguish copied originals, explicit local-home-path redacted derivatives and omitted private originals. The 17 MB final payload, 40 MB packet, 23 MB retrieval input and 14 prepared-data bodies remain private and hash-bound. Derivatives replace only local home paths, including captured review bodies where needed; their recalculated derivative bindings do not represent original launch inputs. Raw remote-scoped failure stdout/stderr remain exact. This report publishes a selected evidence subset.

[Next prerequisite feasibility note](evidence/next-prerequisite-capability-feasibility-note-r1.json) is a proposal for a separately reviewed future CPU capability phase. It grants no diagnostic, launch or current-attempt retry authority. Scientific/native sources and frozen data remain unchanged. Social propagation is unposted.
