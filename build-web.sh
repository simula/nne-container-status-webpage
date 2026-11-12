#!/usr/bin/env bash
# Build and start the dashboard on http://localhost:8050.
#   ./build-web.sh            real data from Apollo (read-only nne-reader, ./.db_env_test)
#   ./build-web.sh synthetic  synthetic data, no database
set -euo pipefail
cd "$(dirname "$0")"
ssh-add -l >/dev/null || ssh-add --apple-load-keychain  # build fetches over SSH
if [[ "${1:-database}" == synthetic ]]; then
    DB_ENV_FILE=/dev/null docker compose up -d --build
else
    DB_ENV_FILE=./.db_env_test DATA_SOURCE=database docker compose up -d --build
fi
docker compose ps
echo "http://localhost:8050"
