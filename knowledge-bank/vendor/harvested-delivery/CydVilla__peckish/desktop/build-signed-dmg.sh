#!/bin/bash
#
# Build a Gatekeeper-valid, ad-hoc-signed Peckish .dmg.
#
# electron-builder + afterPack.js already ad-hoc-sign the .app, but on some
# machines (notably when the checkout lives under ~/Desktop) macOS re-tags files
# with resource-fork/provenance detritus every time they are *copied* onto the
# volume — including electron-builder's own copy of the app into the dmg — which
# silently re-breaks the signature inside the shipped image.
#
# This script sidesteps that: it stages the signed app in a tmp dir (a `ditto`
# there strips the detritus), re-signs, and assembles the dmg with hdiutil from
# that clean copy, then verifies the signature *inside the finished dmg*. The
# result is a plain (no custom background) but correctly-signed dmg.
#
# Usage:  cd desktop && ./build-signed-dmg.sh
set -euo pipefail
cd "$(dirname "$0")"

VERSION="$(node -p "require('./package.json').version")"
APP_SRC="dist/mac-arm64/Peckish.app"
DMG="dist/Peckish-${VERSION}-arm64.dmg"

echo "▸ building the app bundle (electron-builder + afterPack ad-hoc signing)…"
npm run dist >/dev/null

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"; hdiutil detach -quiet /tmp/_peckish_dmg 2>/dev/null || true' EXIT

echo "▸ staging a detritus-free, signed copy in tmp…"
ditto --norsrc --noextattr --noacl "$APP_SRC" "$STAGE/Peckish.app"
codesign --force --deep --sign - "$STAGE/Peckish.app"
codesign --verify --deep --strict "$STAGE/Peckish.app"
ln -s /Applications "$STAGE/Applications"

echo "▸ assembling the dmg…"
rm -f "$DMG"
hdiutil create -volname "Peckish" -srcfolder "$STAGE" -format UDZO -ov "$DMG" >/dev/null

echo "▸ verifying the signature inside the finished dmg…"
hdiutil attach -nobrowse -quiet "$DMG" -mountpoint /tmp/_peckish_dmg
if codesign --verify --deep --strict "/tmp/_peckish_dmg/Peckish.app"; then
  echo "✓ $DMG — app signature valid on disk"
else
  echo "✗ signature invalid inside the dmg" >&2
  exit 1
fi
