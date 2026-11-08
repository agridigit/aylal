#!/usr/bin/env bash
# The PowerSync service must accept infra/powersync/sync-rules.yaml (no restart loop, healthy); F3 rules checks below.
source "$(dirname "$0")/lib.sh"

out="$(bash scripts/dc.sh up -d --build --wait db api powersync 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "$out" | tail -n 15; fail "powersync did not become healthy with the repository sync rules (rc=$rc)"; }
cid="$(bash scripts/dc.sh ps -q powersync 2>/dev/null)"
[ -n "$cid" ] || fail "powersync is not running"
if [ -n "$cid" ]; then
  st="$(docker inspect -f '{{.State.Health.Status}}' "$cid")"
  [ "$st" = "healthy" ] || fail "powersync is '$st', expected healthy"
  since="$(docker inspect -f '{{.State.StartedAt}}' "$cid")"
  bash scripts/dc.sh logs --since "$since" powersync 2>&1 | grep -Eqi 'not supported here|must cover all bucket parameters|must return an id' \
    && fail "powersync rejected the sync rules"
fi
# ---- F3 (T021, T027b): structure of the rules, executed without the stack ----

RULES=infra/powersync/sync-rules.yaml
live() { grep -v '^ *#' "$RULES"; }
block() { live | awk -v name="  $1:" '$0 == name {on=1; next} /^  [a-z_0-9]+:/ {on=0} on'; }

bash scripts/validate-sync-rules.sh >/dev/null 2>&1 || fail "$RULES is rejected by the PowerSync service"

for t in farm_weather alerts parcel_status parcel_status_items parcel_vigor_points vigor_maps attention_zones zone_observations daily_summaries; do
  live | grep -Eq "FROM $t WHERE" || fail "sync rules do not cover $t"
  live | grep -Eq "SELECT \* FROM $t\b" && fail "SELECT * on $t: columns must be explicit"
done
for t in alerts parcel_status parcel_status_items attention_zones zone_observations; do
  live | grep -E "FROM $t WHERE" | grep -vq "parcel_archived_at IS NULL" && fail "a $t query is not filtered on parcel_archived_at IS NULL"
done
live | grep -Eq "FROM parcel_vigor_points WHERE.*valid = true" || fail "only valid vigor points are synchronised"
F3_TABLES='farm_weather|alerts|parcel_status|parcel_status_items|parcel_vigor_points|vigor_maps|attention_zones|zone_observations|daily_summaries|notification_prefs|observation_uploads'
live | grep -E "FROM ($F3_TABLES) WHERE" | grep -Eiq '\b(photo_key|map_key|raster_key|push_token|object_key)\b' && fail "an F3 query synchronises a storage key or push token"
live | grep -Eiq '\bJOIN\b|\( *SELECT|\bIN *\(' && fail "a join, subquery or IN list is present"

block farm_worker_monitoring | grep -Eq '^ *parameters: SELECT parcel_id FROM worker_parcels WHERE user_id = request.user_id\(\)$' \
  || fail "farm_worker_monitoring must take ONE parameter column (parcel_id) from worker_parcels"
block farm_worker_monitoring | grep -q 'bucket.user_id' && fail "farm_worker_monitoring data must be bound to bucket.parcel_id only"
block farm_worker_monitoring | grep -Eq 'FROM alerts WHERE parcel_id = bucket.parcel_id' || fail "worker bucket does not serve alerts by bucket.parcel_id"
block farm_worker_weather | grep -Eq "role = 'worker' AND removed_at IS NULL" || fail "worker weather bucket needs an active worker membership"
block farm_worker_weather | grep -Eq 'FROM farm_weather WHERE farm_id = bucket.farm_id' || fail "worker weather bucket must serve farm_weather by farm_id"

# T027b: per-user buckets
block user_summaries | grep -Eq '^ *parameters: .*FROM farm_members .*removed_at IS NULL' || fail "user_summaries parameters need farm_members ... removed_at IS NULL"
block user_summaries | grep -Eq 'FROM daily_summaries WHERE farm_id = bucket.farm_id AND user_id = bucket.user_id' || fail "user_summaries data must filter on (farm_id, user_id) of the bucket"
block user_summaries | grep -v '^ *parameters:' | grep -q 'request.user_id()' && fail "user_summaries data must not rely on request.user_id()"
# no per-user bucket may rely on request.user_id() alone in its data
live | awk '/^  [a-z_0-9]+:/ {name=$1} /^ *- SELECT .*request\.user_id\(\)/ {print name}' | grep -q . && fail "a data query uses request.user_id()"
finish
