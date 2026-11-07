#!/usr/bin/env bash
# docker compose wrapper: one compose project per git branch (own database, MinIO and PowerSync
# volumes, so a branch never sees migrations or data of another one); build caches are shared
# (named volumes with a fixed name in docker-compose.yml).
# Host ports are shared, so before starting containers (up/run/start) the other AYLAL stacks are
# stopped — their volumes are kept. COMPOSE_PROJECT_NAME can be forced from the environment.
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
branch="$(git -C "$root" rev-parse --abbrev-ref HEAD)"
slug="$(printf '%s' "$branch" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | cut -c1-40 | sed 's/-*$//')"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-aylal-$slug}"

starts=false
for a in "$@"; do case "$a" in up|run|start) starts=true; break;; esac; done
if $starts; then
  for p in $(docker ps --format '{{.Label "com.docker.compose.project"}}' | sort -u | grep -E '^aylal($|-)' | grep -vx "$COMPOSE_PROJECT_NAME" || true); do
    echo "dc: arrêt de la pile $p (ports partagés ; volumes conservés)" >&2
    docker compose -p "$p" stop >/dev/null
  done
fi
cd "$root"
exec docker compose "$@"
