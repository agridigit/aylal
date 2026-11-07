#!/usr/bin/env bash
# The PowerSync service must accept infra/powersync/sync-rules.yaml (no restart loop, healthy).
source "$(dirname "$0")/lib.sh"

out="$(bash scripts/dc.sh up -d --build --wait db api powersync 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "$out" | tail -n 15; fail "powersync did not become healthy with the repository sync rules (rc=$rc)"; }
cid="$(bash scripts/dc.sh ps -q powersync 2>/dev/null)"
[ -n "$cid" ] || fail "powersync is not running"
if [ -n "$cid" ]; then
  st="$(docker inspect -f '{{.State.Health.Status}}' "$cid")"
  [ "$st" = "healthy" ] || fail "powersync is '$st', expected healthy"
  bash scripts/dc.sh logs powersync 2>&1 | grep -Eqi 'not supported here|must cover all bucket parameters|must return an id' \
    && fail "powersync rejected the sync rules"
fi
finish
