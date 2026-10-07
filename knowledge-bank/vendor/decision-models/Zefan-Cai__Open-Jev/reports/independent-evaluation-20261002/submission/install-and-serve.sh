#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
git clone https://github.com/Zefan-Cai/Open-Jev.git loader
git -C loader checkout --detach 1c4347841ce942b8009d9187735fe5686adbbb1b
python3 -m venv .venv
.venv/bin/python -m pip install -e './loader[train]'
.venv/bin/hf download ZefanCai/Open-Jev-27B-v1.1 --revision 28cf73067d5b337860bbef3c85b8b82ba8730956 --local-dir model
.venv/bin/python verify_and_record.py
cd loader
exec ../.venv/bin/python -m jev.server --checkpoint ../model/package/checkpoint \
  --device cuda:0 --max-length 16384 --batch-size 1 --no-prefix-cache \
  --host 127.0.0.1 --port 8791
