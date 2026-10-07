#!/usr/bin/env bash
set -euo pipefail
: "${RUN_ROOT:?Set a new empty reproduction directory}"
: "${BASE_PYTHON:?Set a Python 3.11 interpreter}"
export CUDA_VISIBLE_DEVICES=''
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
export PIP_CONFIG_FILE=/dev/null
export PIP_CACHE_DIR="$RUN_ROOT/pip-cache"
export TORCH_EXTENSIONS_DIR="$RUN_ROOT/extensions"
export TRITON_CACHE_DIR="$RUN_ROOT/triton-cache"
export CUDA_HOME=/usr/local/cuda-12.8
export TORCH_CUDA_ARCH_LIST=9.0
export MAX_JOBS=2
cd "$RUN_ROOT"
test ! -e venv
sha256sum -c wheel.sha256 > wheel-check.log
"$BASE_PYTHON" -m venv venv
venv/bin/python -I -m pip --version > pip-before.log
timeout 1200 venv/bin/python -I -m pip --isolated install --index-url https://download.pytorch.org/whl/cu128 --report torch-install.json 'torch==2.8.0+cu128' > torch-install.log 2>&1
timeout 1200 venv/bin/python -I -m pip --isolated install --index-url https://pypi.org/simple --constraint constraints.txt --report extras-install.json './open_jev-0.1.0.dev0-py3-none-any.whl[train,fast]' > extras-install.log 2>&1
venv/bin/python -I -m pip check > pip-check.log 2>&1
venv/bin/python -I -m pip freeze --all > full-freeze-private.txt
timeout 300 venv/bin/open-jev-serve --help > serve-help.log 2>&1
timeout 300 venv/bin/open-jev-train --help > train-help.log 2>&1
timeout 300 venv/bin/python -I verify.py > verify.log 2>&1
timeout 600 venv/bin/python -I compile.py > compile.log 2>&1
date -u +%Y-%m-%dT%H:%M:%SZ > complete.utc
