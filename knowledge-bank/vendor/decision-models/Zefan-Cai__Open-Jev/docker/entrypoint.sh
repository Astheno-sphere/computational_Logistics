#!/bin/sh
# Start the Open-Jev HTTP service on the baked checkpoint. The port is bound only
# after the model is loaded, so a reachable port means the model is ready.
set -eu

: "${JEV_MODEL_ROOT:=/opt/open-jev/models}"
: "${JEV_CHECKPOINT:=}"
: "${JEV_DEVICE:=auto}"
: "${JEV_HOST:=0.0.0.0}"
: "${JEV_PORT:=8791}"
: "${JEV_MAX_LENGTH:=4096}"
: "${JEV_BATCH_SIZE:=32}"
: "${JEV_PREFIX_CACHE:=off}"

# Anything else (a shell, the test suite, a benchmark script) runs instead.
if [ "$#" -gt 0 ] && [ "${1#-}" = "$1" ]; then
    exec "$@"
fi

# Whichever package was baked in at build time; one image holds one model.
if [ -z "${JEV_CHECKPOINT}" ]; then
    found="$(find "${JEV_MODEL_ROOT}" -type f -path '*/package/checkpoint/model.json' | sort | head -1)"
    if [ -n "${found}" ]; then
        JEV_CHECKPOINT="$(dirname "${found}")"
    fi
fi

if [ -z "${JEV_CHECKPOINT}" ] || [ ! -f "${JEV_CHECKPOINT}/model.json" ]; then
    echo "open-jev: no checkpoint found under ${JEV_MODEL_ROOT}; set JEV_CHECKPOINT" >&2
    exit 1
fi

if [ "${JEV_DEVICE}" = "auto" ]; then
    JEV_DEVICE="$(python -c 'import torch; print("cuda:0" if torch.cuda.is_available() else "cpu")')"
    if [ "${JEV_DEVICE}" = "cpu" ]; then
        echo "open-jev: no CUDA device visible; serving on CPU (slow). Set JEV_DEVICE=cuda:0 to require a GPU." >&2
    fi
fi

case "${JEV_PREFIX_CACHE}" in
    1|on|true|yes) cache_flag="--prefix-cache" ;;
    *) cache_flag="--no-prefix-cache" ;;
esac

echo "open-jev: checkpoint=${JEV_CHECKPOINT} device=${JEV_DEVICE} bind=${JEV_HOST}:${JEV_PORT}" >&2
echo "open-jev: max_length=${JEV_MAX_LENGTH} batch_size=${JEV_BATCH_SIZE} prefix_cache=${JEV_PREFIX_CACHE}" >&2

set -- --checkpoint "${JEV_CHECKPOINT}" \
       --device "${JEV_DEVICE}" \
       --host "${JEV_HOST}" \
       --port "${JEV_PORT}" \
       --max-length "${JEV_MAX_LENGTH}" \
       --batch-size "${JEV_BATCH_SIZE}" \
       "${cache_flag}" "$@"

exec python -m jev.server "$@"
