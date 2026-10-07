# V8 C toolchain, header and compile-target observation

This separate observation binds the current compiler driver, source/header
dependencies, expanded `SYS_pidfd_open` expression and compiler-declared target
ABI. It preprocesses a fixed translation unit and compiles the captured
preprocessed bytes to an object. The object is never linked, loaded or executed;
no pidfd call or other kernel-entry probe is part of this phase.

## Fixed inputs and route

The sole compiler role is `cc`, resolved through the explicitly controlled
`/usr/bin:/bin` path after the fresh attempt is consumed. Its canonical bounded
regular ELF file, identity and SHA256 are observed. Missing compiler, headers or
macros produce a terminal negative result, with no alternate compiler, guessed
provider filename, syscall number, interpreter switch or fallback.

The request has exactly nine fields: `schema_version`, `scope`, `nonce`,
`observer_sha256`, `c_probe_sha256`, `identity_helper_sha256`,
`attempt_directory`, `host` and `bootstrap`. Its scope is
`frontier_v8_C_toolchain_header_target_observation`. Source, fixed C probe, raw
request, original bootstrap and current own host/boot/UID/PID/birth are checked
before consuming the fresh output directory and sibling marker. The immutable
presence helper is executed from captured bytes only for pure helper functions;
its old observation and CLI are not called.

The observer uses a fresh `-B -I -S` file entry. `--execute` rejects before
parser construction, helper/source/request processing or compiler resolution.
Ordinary standard-library startup precedes that CLI guard. Original Python,
scientific and native source bytes and their existing guards remain unchanged.

## Compiler and target evidence

The finite compiler pipeline observes version output, dependency-only discovery,
expanded preprocessing and object-only compilation. Dependency discovery uses
the fixed make target `frontier_v8_source_dependencies`; paths must be absolute,
safe source/header paths. Unsupported escapes, virtual paths and ambiguous
dependencies are rejected. The discovered dependency set is captured before
expanded preprocessing, compared with its emitted dependency file, and rechecked
afterward. These compiler-reported dependencies describe logical provenance;
they do not authenticate every file the compiler or its descendants accessed.

The fixed C translation unit includes `sys/syscall.h`, `sys/types.h`, `unistd.h`
and `limits.h`. It requires Linux, `_GNU_SOURCE`, `SYS_pidfd_open` and the
declared compiler builtins. It contains only constant declarations and static
assertions, with no functions or `main`. The expanded header expression is
recorded as opaque text. The observer neither evaluates it nor substitutes a
number. Ordinary C compilation evaluates constants and checks target-size
static assertions.

The builtin integer/long/pointer widths, character width and byte order describe
the compiler target. The ELF object must be a bounded regular relocatable
object, whose class, data encoding and machine descriptor are recorded. These
are compile-target facts, without architecture, kernel pidfd support, mapped
provider authenticity, C runtime ABI or model-runtime ABI inference.

Only successful postvalidation may set `toolchain_invocation_observed`,
`header_dependency_closure_observed`, `SYS_pidfd_open_header_constant_observed`
and `compiler_target_ABI_observed`. Inputs, self identity, output-directory
identity and consumed marker bytes/identity are rechecked. The marker check is
returned-process evidence, without an independent remote retrieval.
`native_C_runtime_ABI_observed`, `own_pidfd_operations_verified`,
`functional_containment_verified`, `containment_available`,
`execution_available`, `resource_authority` and `model_runtime_ABI_observed`
remain false.

## Lifecycle and evidence limits

Compiler output streams are exclusive regular files. Each fresh direct child
has a 30-second foreground wait. A timeout permits at most one kill attempt on
that directly created child and one two-second reap wait; the receipt records
actual attempts, errors and unknown outcomes. It does not claim that every
signal count is zero, or that compiler descendants were cleaned up. The
compiler may invoke frontend or assembler processes. Driver and header hashes
do not form a complete toolchain execution closure or host-loss guard.

Once the marker is written, failed, timed-out or interrupted attempts remain
consumed. Precondition failures can precede consumption; `BaseException` or
host loss can leave incomplete evidence. No retry or resume is authorized by a
failed receipt. A complete returned stdout receipt is caller evidence, without
independent remote marker retrieval, persistence or durability proof.

Portable fixtures cover strict parsing, failed compilation, provenance drift,
consumption and bounded direct-child timeout facts. Two strict Linux fixtures
exercise the declared source/header/object pipeline and a fresh isolated CLI;
their results need actual CI evidence. They never link or execute a generated
product. This CPU preparation establishes no model progress, GPU lease, queue
recovery, external trial or business action.
