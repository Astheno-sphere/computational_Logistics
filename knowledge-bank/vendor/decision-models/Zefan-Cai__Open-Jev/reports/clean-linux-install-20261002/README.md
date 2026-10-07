# Fresh Linux package installation: October 2, 2026

A fresh Python 3.11.15 venv installed the final Open-Jev wheel with both
`train` and `fast` extras, Torch 2.8.0+cu128 and all ten selected version pins.
All 77 installed distributions and checked module files resolve inside the new
venv. System site packages, user site packages and `PYTHONPATH` were disabled.
The existing interpreter, OS, compiler and CUDA toolkit were reused. Pip reused
its download cache; cache freshness is not claimed. No shared runtime packages
were modified.

The [receipt](receipt.json), [public package origins and archive hashes](origins.json),
[complete freeze](full-freeze.txt), [selected constraints](constraints.txt) and
[installed dependency lock](../../requirements-linux-py311-cu128-20261002.lock)
retain the result. The lock records this Linux x86-64 / Python 3.11 environment;
it is not a cross-platform lock or a separate completed lock-replay experiment.
Pip and setuptools were supplied by venv bootstrap; their bytes were not
independently hashed. Every other installed distribution is matched to a
public HTTPS package archive or the local Open-Jev wheel in the origin manifest.

The installed wheel is 383,608 bytes with SHA-256
`45ac71f6376a41fdbfcf7e05afe544bca66d40a0a19e31b1e55473400b1e8862`.
The [source identity](wheel-source-identity.json) independently compares all
67 packaged code/resource files with pushed commit
`42e46481da6dd8191d6f510fc3680c70fd4f051d`: zero mismatches. Distribution
metadata, source scripts and documentation are excluded from that comparison.
Rebuilding from source creates another wheel artifact whose own hash must be
recorded; the published digest identifies the wheel actually installed here.

## Passed checks

- `pip check`: no broken requirements.
- Installed `open-jev-serve --help` and `open-jev-train --help`.
- Torch CPU matrix multiplication and the installed final-score CPU reference.
- Required FLA 0.5.2 modules and symbols used by the vendored backbone.
- Packaged CUDA sources, provenance, attribution and license resources.
- Attributed CUDA extension compiled and loaded for explicit sm90 in 60.18
  seconds, with `MAX_JOBS=2` and a task-local build cache.

The [verification](verification.json), [compile receipt](compilation.json),
[compile log](compile.log) and command logs preserve these checks. The extension
artifact SHA-256 is
`04246ef92c8f56d0229303423742ee91ba55be299c15a064f2e992523c73a638`.
Compilation used CUDA 12.8.93. The `No CUDA runtime is found` and FLA CPU fallback
warnings are expected with no visible CUDA devices and remain in the logs.

`CUDA_VISIBLE_DEVICES=''` was set for installation and every check. Verification
and compilation reject Torch CUDA initialization, and both final receipts
record `cuda_initialized: false`. No model weights were loaded. CUDA kernel
execution, full-model parity, inference latency and independent sealed scoring
remain outside this installation result.

## Recorded commands

The [installer](install-clean.sh), [CPU verifier](verify.py) and
[compile-only verifier](compile.py) are the scripts actually run. The installer
requires the named wheel, `wheel.sha256`, constraints and verification scripts
in a new working directory; it rejects an existing venv. Set `RUN_ROOT` to that
directory and `BASE_PYTHON` to a Python 3.11 interpreter, then run it with bash.
Each package installation is bounded to 20 minutes, CPU verification to five
minutes and compilation to ten minutes.

The two installation commands inside it were:

```bash
venv/bin/python -I -m pip --isolated install \
  --index-url https://download.pytorch.org/whl/cu128 \
  --report torch-install.json 'torch==2.8.0+cu128'
venv/bin/python -I -m pip --isolated install \
  --index-url https://pypi.org/simple --constraint constraints.txt \
  --report extras-install.json \
  './open_jev-0.1.0.dev0-py3-none-any.whl[train,fast]'
```

`--isolated` ignores the installer's `PIP_CACHE_DIR`; the normal pip download
cache was consequently reused. Set the explicit `--cache-dir` option in a new
run if an independent download cache is required. This has no bearing on the
verified isolation of the installed runtime packages.

Private account paths in public logs are replaced with hashed markers. The
receipt retains separate raw/private and public artifact hashes. Package source
URLs have no credentials or query parameters; private originals are excluded
from version control.
