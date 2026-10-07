#!/usr/bin/env bash
#
# Checks that the base image pin is still on the active LTS major.
#
# Every Dockerfile passed in is treated as one unit, because they are: a repo's
# build stage, runtime stage and sidecar image all sit on the same base, and a
# bump that moves one and not the others is itself the bug. So:
#
#   1. All of them pin the same image. A build stage that has drifted from the
#      runtime stage compiles against a Node the image will not run.
#   2. `node:lts-<variant>` and `node:<major>-<variant>` resolve to the same
#      digest. That is what makes "this is the ACTIVE LTS line" checkable
#      rather than a version number somebody wrote down once. It is about the
#      live tags, not the pin, and it fails the day the major leaves LTS.
#   3. The pinned digest is an image of the major its own tag names. That is
#      the half a hand-edited pin breaks: `node:24-alpine@<digest of 26>` reads
#      as LTS and is not.
#
# Deliberately checked against the major and nothing finer. A patch version is
# a fact with a shelf life of about a week — writing one into a comment means
# every digest bump arrives red, which teaches everyone to merge past this
# check rather than read it. The major is what carries the LTS claim, and it
# survives every bump that is not a decision.
#
# Reads the registry over HTTP rather than pulling: the config blob carries
# NODE_VERSION, and fetching a few hundred MB to run `node -v` is the same
# answer for more money.
#
# Usage: check-base-image-pin.sh Dockerfile [Dockerfile.other ...]

set -euo pipefail

[ $# -gt 0 ] || {
    printf 'usage: %s Dockerfile [Dockerfile.other ...]\n' "${0##*/}" >&2
    exit 2
}

fail=0
unreachable=0
note() { printf '%s\n' "$*"; }
bad() {
    printf 'FAIL  %s\n' "$*"
    fail=1
}

body=$(mktemp)
headers=$(mktemp)
trap 'rm -f "$body" "$headers"' EXIT

# Docker Hub rate-limits anonymous callers per IP, and CI runners share those
# IPs with the rest of the world. "I could not ask" and "the answer is wrong"
# are different results and must not land in the same bucket: a 429 reported as
# a finding trains everyone to ignore this check, and it would fire on pull
# requests that changed nothing.
#
# So the exit status carries the difference all the way up, through the command
# substitutions the callers use — 1 for "ask again later", 2 for an answer that
# is definitive and bad. Only the second is a finding.
registry_get() {
    local code attempt=0
    while :; do
        attempt=$((attempt + 1))
        code=$(curl -sS --max-time 30 -o "$body" -D "$headers" -w '%{http_code}' "$@" 2>/dev/null) || code=000
        case "$code" in
        200) return 0 ;;
        429 | 408 | 425 | 500 | 502 | 503 | 504 | 000)
            [ "$attempt" -lt 4 ] || return 1
            sleep $((attempt * attempt * 2))
            ;;
        *) return 2 ;;
        esac
    done
}

rc=0
registry_get "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/node:pull" || rc=$?
if [ "$rc" -ne 0 ]; then
    note "SKIP  Docker Hub is not answering (rate limit or outage). Nothing was"
    note "      checked. Re-run this job."
    exit 0
fi
token=$(jq -r .token <"$body")

accept='application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json'

# Digest a tag currently resolves to.
tag_digest() {
    local rc=0
    registry_get -o /dev/null -H "Authorization: Bearer $token" -H "Accept: $accept" \
        "https://registry-1.docker.io/v2/library/node/manifests/$1" || rc=$?
    [ "$rc" -eq 0 ] || return "$rc"
    tr -d '\r' <"$headers" | awk 'tolower($1) == "docker-content-digest:" { print $2 }'
}

# NODE_VERSION out of the linux/amd64 image behind a digest.
node_version() {
    local amd64 config rc=0
    registry_get -H "Authorization: Bearer $token" -H "Accept: $accept" \
        "https://registry-1.docker.io/v2/library/node/manifests/$1" || rc=$?
    [ "$rc" -eq 0 ] || return "$rc"
    amd64=$(jq -r '.manifests[]? | select(.platform.architecture == "amd64" and .platform.os == "linux") | .digest' <"$body" | head -1)
    # A single-platform manifest has no .manifests and is already the image.
    [ -n "$amd64" ] || amd64=$1

    registry_get -H "Authorization: Bearer $token" -H "Accept: $accept" \
        "https://registry-1.docker.io/v2/library/node/manifests/$amd64" || rc=$?
    [ "$rc" -eq 0 ] || return "$rc"
    config=$(jq -r .config.digest <"$body")

    registry_get -L -H "Authorization: Bearer $token" \
        "https://registry-1.docker.io/v2/library/node/blobs/$config" || rc=$?
    [ "$rc" -eq 0 ] || return "$rc"
    jq -r '.config.Env[]? // .container_config.Env[]?' <"$body" |
        sed -n 's/^NODE_VERSION=//p' | head -1
}

# `|| true` on every grep: a missing match is a finding to report, and under
# `set -e -o pipefail` grep's exit 1 would end the run before we could.
mapfile -t pins < <(grep -hoE '^FROM node:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}' "$@" | sed 's/^FROM //' | sort -u || true)

if [ ${#pins[@]} -eq 0 ]; then
    bad "no 'FROM node:<tag>@sha256:<digest>' line in: $*"
    exit 1
fi

# Claim 1: one image across every stage and every file.
if [ ${#pins[@]} -ne 1 ]; then
    bad "these files do not pin the same image:"
    printf '%s\n' "${pins[@]}" | sed 's/^/        /'
    note "        A bump moved one stage and not the others. They share a base on"
    note "        purpose: the build stage compiles for the runtime stage."
    exit 1
fi
note "  ok  one pin across $*: ${pins[0]}"

pin=${pins[0]}
tag=${pin%@*}
tag=${tag#node:}
digest=${pin#*@}

# 24-alpine -> major 24, variant alpine.
major=${tag%%-*}
variant=${tag#*-}
if [ "$variant" = "$tag" ]; then
    bad "cannot read a variant out of tag '$tag'"
    exit 1
fi

# Claim 2: the major tag is still the LTS tag.
rc=0
live_major=$(tag_digest "$major-$variant") || rc=$?
if [ "$rc" -eq 0 ]; then
    live_lts=$(tag_digest "lts-$variant") || rc=$?
fi
case "$rc" in
1) unreachable=1 ;;
2)
    bad "node:$major-$variant or node:lts-$variant is gone from the registry."
    note "        A withdrawn tag is not something to bump past."
    ;;
*)
    if [ "$live_major" != "$live_lts" ]; then
        bad "node:$major-$variant and node:lts-$variant have diverged."
        note "        node:$major-$variant -> $live_major"
        note "        node:lts-$variant    -> $live_lts"
        note "        Node $major is no longer the active LTS line. Moving the base image"
        note "        is a decision, not a bump: read the note above the FROM line."
    else
        note "  ok  node:$major-$variant == node:lts-$variant ($live_major)"
    fi
    ;;
esac

# Claim 3: the digest is an image of the major the tag names.
rc=0
actual=$(node_version "$digest") || rc=$?
case "$rc" in
1) unreachable=1 ;;
2) bad "the pinned digest $digest is gone from the registry." ;;
*)
    if [ -z "$actual" ]; then
        bad "the pinned image carries no NODE_VERSION — is $digest a node image?"
    elif [ "${actual%%.*}" != "$major" ]; then
        bad "the tag says node:$tag, the pinned digest is Node $actual."
        note "        Pin and tag name different majors, so the tag is no longer"
        note "        evidence of anything: claim 2 above checked node:$tag, and"
        note "        that is not what this image is. Resolve the tag again."
    else
        note "  ok  pinned digest is Node $actual, matching node:$tag"
    fi
    ;;
esac

if [ "$unreachable" = 1 ]; then
    note "SKIP  Docker Hub stopped answering part-way through (rate limit or outage)."
    note "      What is reported above was checked; the rest was not. Re-run this job."
fi

exit $fail
