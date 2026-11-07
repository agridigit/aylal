#!/usr/bin/env bash
# F2 sync rules: the contract and infra/powersync/sync-rules.yaml are both accepted by the PowerSync service
# parser (no join, no subquery), and the infra rules actually carry the F2 tables (T018).
source "$(dirname "$0")/lib.sh"

img="$(sed -n 's/^ *image: \(journeyapps\/powersync-service:.*\)$/\1/p' docker-compose.yml | head -1)"
validate() { docker run --rm --entrypoint node -v "$ROOT/scripts/validate-sync-rules.mjs:/v.mjs:ro" -v "$1:/rules.yaml:ro" "$img" /v.mjs /rules.yaml >/dev/null 2>&1; }

validate "$ROOT/specs/003-fields-crops/contracts/powersync-sync-rules.yaml" || fail "the F2 contract rules are rejected by the PowerSync service"
bash scripts/validate-sync-rules.sh >/dev/null 2>&1 || fail "infra/powersync/sync-rules.yaml is rejected by the PowerSync service"
for t in seasons field_blocks; do
  grep -Eq "FROM $t WHERE" infra/powersync/sync-rules.yaml || fail "infra sync rules do not cover $t"
done
grep -Eq "parcel_archived_at IS NULL" infra/powersync/sync-rules.yaml || fail "worker children are not filtered on parcel_archived_at"
grep -v '^ *#' infra/powersync/sync-rules.yaml | grep -Eiq '\bJOIN\b|\( *SELECT|\bIN *\(' && fail "infra sync rules contain a join, subquery or IN list"
finish
