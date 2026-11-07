#!/usr/bin/env bash
# F6 sync rules (G2): accepted by the PowerSync service parser (no join, no subquery, no IN list),
# worker bucket parameterised on (parcel_id, user_id), global catalog bucket, no registry for workers.
source "$(dirname "$0")/lib.sh"

img="$(sed -n 's/^ *image: \(journeyapps\/powersync-service:.*\)$/\1/p' docker-compose.yml | head -1)"
validate() { docker run --rm --entrypoint node -v "$ROOT/scripts/validate-sync-rules.mjs:/v.mjs:ro" -v "$1:/rules.yaml:ro" "$img" /v.mjs /rules.yaml >/dev/null 2>&1; }
rules=infra/powersync/sync-rules.yaml
code="$(grep -v '^ *#' "$rules")"

validate "$ROOT/$rules" || fail "$rules is rejected by the PowerSync service"
for t in operations operation_parcels operation_reminders operation_corrections registry_entries phyto_products phyto_product_uses catalog_versions; do
  grep -Eq "FROM $t( |$)" <<<"$code" || fail "sync rules do not cover $t"
done
grep -Eiq '\bJOIN\b|\( *SELECT|\bIN *\(' <<<"$code" && fail "sync rules contain a join, subquery or IN list"
# worker bucket: two-column parameter query (parcel_id, user_id)
worker="$(awk '/^  farm_worker_ops:/{f=1;next} /^  [a-z_]+:/{f=0} f' <<<"$code")"
[ -n "$worker" ] || fail "bucket farm_worker_ops is missing"
grep -Eq 'parameters: SELECT parcel_id, request.user_id\(\) AS user_id FROM worker_parcels' <<<"$worker" || fail "worker bucket is not parameterised by (parcel_id, user_id)"
grep -q 'parcel_archived_at IS NULL' <<<"$worker" || fail "worker bucket does not filter on parcel_archived_at IS NULL"
grep -q 'author_id = bucket.user_id' <<<"$worker" || fail "worker bucket does not restrict to the author"
grep -q 'registry_entries' <<<"$worker" && fail "registry_entries is present in the worker bucket"
# global catalog bucket: no parameters
catalog="$(awk '/^  phyto_catalog:/{f=1;next} /^  [a-z_]+:/{f=0} f' <<<"$code")"
[ -n "$catalog" ] || fail "bucket phyto_catalog is missing"
grep -q 'parameters:' <<<"$catalog" && fail "phyto_catalog must not take parameters"
# storage keys never replicated
grep -Eq 'label_photo_key|file_keys|object_key' <<<"$code" && fail "a storage key column is synchronised"
finish
