#!/usr/bin/env bash
# Build and start the deployment environment (stand-in for specula: Ubuntu, systemd, nginx) on https://localhost:8443.
# Real data from Apollo with ./.db_env_deployement; gunicorn needs a few seconds after the start (502 until then).
# The certificate is a throwaway self-signed one for localhost: the browser warns, curl needs -k.
set -euo pipefail
cd "$(dirname "$0")"
# a missing file would be bind-mounted as an empty directory
[[ -f .db_env_deployement ]] || { echo "missing ./.db_env_deployement" >&2; exit 1; }
ssh-add -l >/dev/null || ssh-add --apple-load-keychain  # build fetches over SSH
docker compose --profile deploy up -d --build deployment-environment
docker compose --profile deploy ps deployment-environment
echo "https://localhost:8443"
