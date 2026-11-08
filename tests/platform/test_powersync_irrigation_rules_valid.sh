#!/usr/bin/env bash
# F4 sync rules (T025, T034b): the contract and infra/powersync/sync-rules.yaml are both accepted by the PowerSync service parser
# (validated through scripts/validate-sync-rules.sh), have no join/subquery, expose worker-safe columns only, and carry the F4 buckets.
source "$(dirname "$0")/lib.sh"

img="$(sed -n 's/^ *image: \(journeyapps\/powersync-service:.*\)$/\1/p' docker-compose.yml | head -1)"
validate() { docker run --rm --entrypoint node -v "$ROOT/scripts/validate-sync-rules.mjs:/v.mjs:ro" -v "$1:/rules.yaml:ro" "$img" /v.mjs /rules.yaml >/dev/null 2>&1; }
contract="$ROOT/specs/007-irrigation-water-balance/contracts/powersync-sync-rules.yaml"
infra="$ROOT/infra/powersync/sync-rules.yaml"

validate "$contract" || fail "the F4 contract rules are rejected by the PowerSync service"
AYLAL_VALIDATE_F4=1 bash scripts/validate-sync-rules.sh >/dev/null 2>&1 || fail "infra/powersync/sync-rules.yaml is rejected through scripts/validate-sync-rules.sh"
for f in "$contract" "$infra"; do
  grep -v '^ *#' "$f" | grep -Eiq '\bJOIN\b|\( *SELECT|\bIN *\(' && fail "$(basename "$(dirname "$f")")/$(basename "$f") contains a join, subquery or IN list"
done
for b in farm_irrigation farm_worker_irrigation farm_worker_irrigation_own irrigation_reference; do
  grep -Eq "^  $b:" "$infra" || fail "infra sync rules do not define the bucket $b"
done
for t in irrigation_systems irrigation_events irrigation_applied water_analyses water_balance_days irrigation_plans; do
  grep -Eq "FROM $t WHERE" "$infra" || fail "infra sync rules do not cover $t"
done
# worker-safe view: the worker bucket never names the raw analysis/soil/leaching columns nor water_analyses
worker_block="$(awk '/^  farm_worker_irrigation:/{f=1;next} /^  [a-z_]+:/{f=0} f' "$infra" | grep -v '^ *#')"
echo "$worker_block" | grep -Eq '\b(assumptions|leaching_fraction|taw_mm|raw_mm|moisture_source)\b' && fail "farm_worker_irrigation exposes a non worker-safe column"
echo "$worker_block" | grep -Eq 'water_analyses' && fail "farm_worker_irrigation serves water_analyses"
echo "$worker_block" | grep -Eq 'worker_assumptions' || fail "farm_worker_irrigation does not serve worker_assumptions"
own_block="$(awk '/^  farm_worker_irrigation_own:/{f=1;next} /^  [a-z_]+:/{f=0} f' "$infra" | grep -v '^ *#')"
[ -n "$own_block" ] || fail "farm_worker_irrigation_own is empty"
echo "$own_block" | grep -E 'FROM ' | grep -Eq 'bucket\.parcel_id.*bucket\.user_id|bucket\.user_id.*bucket\.parcel_id' || fail "the own bucket does not reference both parameters"
grep -Eq "parcel_archived_at IS NULL" "$infra" || fail "worker children are not filtered on parcel_archived_at"
finish
