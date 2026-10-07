# V8 dedicated owned C descriptor selfcheck

This separate CPU observation builds and runs one new, fixed C product. The
product opens a pidfd for its own current PID with flags zero, checks its
reported PID, polls without waiting, closes that descriptor once, and verifies
`F_GETFD` then fails with `EBADF`. It accepts no argument operands, sends no
signals and creates no child processes. It does not implement a controller,
descendant cleanup, queue restoration, model bridge or resource lease.

## Fixed compiler and runtime route

The observer captures the immutable compiler utility and pure identity helper
from exact file bytes. Their old observations, CLIs, requests, products and
attempts are not called. It executes the two captured standard-library-only
utility bodies under separate module names. Fresh declaration, source and host/bootstrap bindings
precede consumption of a new output directory and sibling marker. The file
entry uses `-B -I -S`; `--execute` remains rejected before request processing,
utility loading or compiler resolution. Ordinary standard-library startup
precedes that CLI guard.

The compiler role is `cc` through the controlled `/usr/bin:/bin` path. Version,
dependency discovery and preprocessing precede object compilation of the
captured preprocessed bytes. The fresh object is linked to one fresh product;
the emitted link map supplies a descriptive inventory of reported existing
link files. Object, product, compiler, headers and reported link files are
bound by regular-file identities and SHA256 values. The product ELF descriptor
is compared with the object descriptor. These observations do not authenticate
the complete compiler/linker dependency closure, mapped runtime code or every
file a tool accessed. No guessed compiler or provider filename is substituted.
The link map retains compiler-reported absolute lexical aliases containing
`..`; normalized and resolved virtual paths are refused. Reported link files
are hashed after linking, so this inventory does not prove their bytes during
the link operation.

The nested `compile_leg` remains the original object-only utility result: its
runtime and own-descriptor flags are false and its product link/execution count
is zero. Separate new aggregate `link` and `runtime` command receipts describe
the dedicated linked product. Narrow new C-runtime/own-descriptor success flags
are set only after the runtime chain and fresh rechecks succeed.

The C source requires Linux, `_GNU_SOURCE`, `sys/syscall.h`, `SYS_pidfd_open`
and declared compiler target builtins. System headers declare `syscall`,
`getpid`, `poll`, `close` and `fcntl`; `SYS_pidfd_open` remains symbolic in the
source. The original six compile marker declarations and target-size static
assertions are retained. The preprocessed constant is captured as opaque text;
the Python observer does not evaluate or replace it. The C compiler evaluates
the captured expression normally. Compiler target widths and the runtime
numeric header value describe this product, without identifying a host
architecture, libc version or kernel-wide capability.

## Own descriptor facts

Before the pidfd operation, the product reads a bounded `/proc/self/stat` and
requires its leading PID to equal `getpid()`. This supports the declared
same-process `/proc` PID namespace baseline. It then calls only
`syscall((long)SYS_pidfd_open, (long)getpid(), (unsigned long)0)` for the pidfd entry.
It reads a bounded `/proc/self/fdinfo/<own-fd>`, rejects duplicate `Pid` fields
and requires exactly one decimal `Pid` equal to its own PID. Other fdinfo fields
are not used to infer ownership. `poll` receives one descriptor, `POLLIN` and
timeout zero; both its result and returned events must be zero.
Descriptor inode metadata, `fstat` and acquired descriptor flags are unobserved.

On each normal handled path with a representable acquired descriptor, the
product attempts its close at most once, including after fdinfo or poll failure.
It captures the immediate close result and errno, with no retry on `EINTR`.
After a successful close, `fcntl(F_GETFD)` follows without an intervening
descriptor-opening operation and must return `-1` with `EBADF`. The separate
stdio stream descriptors used for `/proc` reads are outside the reported
pidfd `close_calls` count. The first failed operation and its errno remain
reported even if later close verification succeeds or fails.

The terminal C JSON records PID, parent PID, UID/EUID, `/proc` PID, header and
target values, acquired descriptor, fdinfo result, poll facts, once-close facts
and the `EBADF` check. Actual poll events are reported beside the header
`POLLIN` value; the immediate `fcntl` result and errno are reported beside the
header `EBADF` value. Verification is recomputed from those facts rather than
the returned verification booleans alone. Its schema has exact keys and strict value types. A
successful Python interpretation also binds the returned runtime PID to the
fresh direct child, its parent PID to the observer and UID/EUID to the current
declared user. A failed process, malformed JSON, foreign identity, false success
or postvalidation drift cannot become a successful observation.

## Evidence and lifecycle limits

Successful own-descriptor and C-runtime facts require fresh input, self, marker,
directory and output postvalidation. Returned controlled-process facts are
caller evidence; they are not an independent remote artifact retrieval,
durability guarantee or mapped-code authentication. `/proc`, parent and UID
consistency checks do not authenticate full ancestry, physical exclusion,
node-alias identity or a kernel-global property.
The production observer also rechecks its original input bytes, self identity
and marker before compilation and before the product invocation; detected drift
at either boundary stops that next operation. Compiler/product artifacts are
rechecked before the product invocation. Output parent and directory identities
are checked during postvalidation.

The Python backend bounds each directly created compiler or product process.
Its timeout handling may send one kill to that direct child and make one bounded
reap attempt, reporting errors or unknown outcomes. Compiler/linker descendants
and host loss have no complete cleanup guarantee. The fixed C product itself
has no signal or child operation. Async interruption, host loss or output
failure can leave no complete terminal receipt; normal handled facts do not
provide a blanket cleanup or recovery promise.

Every consumed failure remains consumed. There is no alternate interpreter,
provider fallback, retry, resume, old product execution, old PID use or shim of
the existing Python/native APIs. Own-pidfd success would still leave
`functional_containment_verified`, `containment_available`,
`execution_available`, `resource_authority` and `model_runtime_ABI_observed`
false. Model runtime packages, numerical tensors/gradients, GPU ownership,
foreign queue recovery and model quality are not observed here.

Portable fixtures exercise strict declarations, runtime and link parsing,
negative results, provenance drift and consumed attempts. Strict Linux fixtures
build/run the dedicated product and a fresh isolated file CLI; unsupported
compiler, headers or runtime produce failure after Linux prerequisites, not a
success or a capability skip. Their actual results require CI or host evidence.
