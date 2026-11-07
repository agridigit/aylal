#!/usr/bin/env bash
# Guard: the PowerSync service image must accept infra/powersync/sync-rules.yaml (no stack needed).
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
img="$(sed -n 's/^ *image: \(journeyapps\/powersync-service:.*\)$/\1/p' "$root/docker-compose.yml" | head -1)"
docker run --rm --entrypoint node -v "$root/scripts/validate-sync-rules.mjs:/v.mjs:ro" \
  -v "$root/infra/powersync/sync-rules.yaml:/rules.yaml:ro" "$img" /v.mjs /rules.yaml \
  || { echo "validate-sync-rules: règles PowerSync rejetées par le service" >&2; exit 1; }
echo "sync rules OK"
