#!/usr/bin/env bash
# T021 - after make up, all services are healthy; otherwise the unhealthy one is named (AC1.1, FR-002).
source "$(dirname "$0")/lib.sh"

out="$(make up 2>&1)"; rc=$?
if [ $rc -ne 0 ]; then
  echo "$out" | tail -n 20
  fail "make up failed (rc=$rc)"
  # Contract: a failure must name the unhealthy service.
  echo "$out" | grep -Eqi 'db|redis|minio|powersync|api|worker|proxy' || fail "make up failure does not name a service"
fi
for svc in db redis minio powersync api worker proxy; do
  cid="$(docker compose ps -q "$svc" 2>/dev/null)"
  [ -n "$cid" ] || { fail "service '$svc' is not running"; continue; }
  st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}nohealthcheck{{end}}' "$cid")"
  [ "$st" = "healthy" ] || fail "service '$svc' is '$st', expected healthy"
done
finish
