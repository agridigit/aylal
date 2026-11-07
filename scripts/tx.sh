#!/usr/bin/env bash
# Runs a command in a warm (long-lived) test container instead of `docker compose run --rm`:
# no container creation nor dependency wait on each test run. Code is bind-mounted, so edits are
# seen immediately. The container is (re)created when missing, stopped, or older than its image.
# Usage: scripts/tx.sh [--no-deps] <service> <command...>
#        scripts/tx.sh stop      -> removes the warm containers of the current branch
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
root="$(git rev-parse --show-toplevel)"
DC=(bash "$here/dc.sh")
proj="$("${DC[@]}" --print-project)"

if [ "${1:-}" = "stop" ]; then
  ids="$(docker ps -aq --filter "name=^${proj}-warm-")"
  [ -n "$ids" ] && docker rm -f $ids >/dev/null
  exit 0
fi

nodeps=()
[ "${1:-}" = "--no-deps" ] && { nodeps=(--no-deps); shift; }
svc="$1"; shift
name="${proj}-warm-${svc}"

fresh() {  # running and built from the current image of the service
  local running img cur
  running="$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || echo false)"
  [ "$running" = true ] || return 1
  cur="$(docker image inspect -f '{{.Id}}' "${proj}-${svc}" 2>/dev/null || true)"
  img="$(docker inspect -f '{{.Image}}' "$name")"
  [ -z "$cur" ] || [ "$img" = "$cur" ]
}

if ! fresh; then
  # parallel sub-agents may arrive together: one creates, the others wait
  lock="$root/.aylal/tx-${svc}.lock"; mkdir -p "$root/.aylal"
  for _ in $(seq 1 240); do mkdir "$lock" 2>/dev/null && break; sleep 0.5; done
  trap 'rmdir "$lock" 2>/dev/null || true' EXIT
  if ! fresh; then
    docker rm -f "$name" >/dev/null 2>&1 || true
    "${DC[@]}" --profile test run -d --rm ${nodeps[@]+"${nodeps[@]}"} --name "$name" "$svc" sleep infinity >/dev/null
  fi
  rmdir "$lock" 2>/dev/null || true; trap - EXIT
fi

exec docker exec "$name" "$@"
