#!/usr/bin/env bash
# Builds the nnedbtools wheel that the Docker image installs (vendor/ is git-ignored).
# Run in the nne-container-status-webpage environment; rebuild after a new nnedbtools release.
# Usage: scripts/build_wheel.sh [nnedbtools checkout, default ../nnedbtools]
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf vendor
pip wheel --no-deps --wheel-dir vendor "${1:-../nnedbtools}"
ls vendor
