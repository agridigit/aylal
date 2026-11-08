#!/usr/bin/env bash
# Guard: the PowerSync service image must accept infra/powersync/sync-rules.yaml (no stack needed).
set -euo pipefail
root="$(git rev-parse --show-toplevel)"
img="$(sed -n 's/^ *image: \(journeyapps\/powersync-service:.*\)$/\1/p' "$root/docker-compose.yml" | head -1)"
docker run --rm --entrypoint node -v "$root/scripts/validate-sync-rules.mjs:/v.mjs:ro" \
  -v "$root/infra/powersync/sync-rules.yaml:/rules.yaml:ro" "$img" /v.mjs /rules.yaml \
  || { echo "validate-sync-rules: règles PowerSync rejetées par le service" >&2; exit 1; }
# F4 cases (specs/007-irrigation-water-balance): buckets present, no join/subquery, worker-safe columns only (static, on the host file).
rules="$root/infra/powersync/sync-rules.yaml"
for b in farm_irrigation farm_worker_irrigation farm_worker_irrigation_own irrigation_reference; do
  grep -Eq "^  $b:" "$rules" || { echo "validate-sync-rules: bucket F4 manquant: $b" >&2; exit 1; }
done
block="$(awk '/^  farm_worker_irrigation:/{f=1;next} /^  [a-z_]+:/{f=0} f' "$rules" | grep -v '^ *#' || true)"
if echo "$block" | grep -Eq '\b(assumptions|leaching_fraction|taw_mm|raw_mm|moisture_source)\b|water_analyses'; then
  echo "validate-sync-rules: farm_worker_irrigation expose une colonne non expurgee ou water_analyses" >&2; exit 1
fi
if grep -v '^ *#' "$rules" | grep -Eiq '\bJOIN\b|\( *SELECT|\bIN *\('; then
  echo "validate-sync-rules: jointure, sous-requete ou liste IN interdites" >&2; exit 1
fi
echo "sync rules OK"
