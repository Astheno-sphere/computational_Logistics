#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d jevbench ]; then
  git clone https://github.com/fstandhartinger/jevbench.git jevbench
  git -C jevbench checkout --detach f8ce71361165846101d02ebc83ad44e47ae44fc3
fi
if [ 16384 -ne 16384 ]; then
  echo 'Public reproduction requires --max-length 16384; prepare a separate bundle.' >&2
  exit 1
fi
EVAL_ROOT="$PWD"
cd loader
"$EVAL_ROOT/.venv/bin/python" -m scripts.jevbench_openjev prepare \
  --upstream "$EVAL_ROOT/jevbench" --output "$EVAL_ROOT/public-inputs"
REQUEST_SHA=$("$EVAL_ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["requests_sha256"])' "$EVAL_ROOT/public-inputs/manifest.json")
"$EVAL_ROOT/.venv/bin/python" -m scripts.jevbench_openjev collect \
  --requests "$EVAL_ROOT/public-inputs/requests.json" --input-sha256 "$REQUEST_SHA" \
  --endpoint http://127.0.0.1:8791/v1/systemone --identity "$EVAL_ROOT/identity.json" \
  --output "$EVAL_ROOT/public-run" --timeout 300 --max-seconds 14400
"$EVAL_ROOT/.venv/bin/python" -m scripts.jevbench_openjev summarize \
  --upstream "$EVAL_ROOT/jevbench" --run-dir "$EVAL_ROOT/public-run" \
  --output "$EVAL_ROOT/public-aggregate.json"
