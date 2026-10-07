#!/bin/bash
export NODE_OPTIONS="--max-old-space-size=4096"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

cd ${PROJECT_DIR}

# Due to the complexity of the frontend build process (especially in macOS),
# we leave the automation of the frontend build process to the future work.
# NOW, we just provide a simple script to rebuild the frontend manually.
# Please run the script after you have made changes to the frontend code.

rm -r packages/agentsociety/agentsociety/_dist || true
cd frontend
npm ci
npm run build
cd ..
cp -r frontend/dist/ packages/agentsociety/agentsociety/_dist/
