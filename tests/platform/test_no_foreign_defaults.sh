#!/usr/bin/env bash
# T027 - no external (non-Moroccan / third-party) host configured by default (FR-019, R17).
source "$(dirname "$0")/lib.sh"

files="docker-compose.yml .env.example infra apps/mobile/app.json apps/mobile/app.config.* packages/ui/.storybook"
for pat in 'firebase' 'googleapis' 'gstatic' 'fonts\.google' 'cdn\.jsdelivr' 'unpkg\.com' 'cdnjs' 'expo\.dev' 'eas\.json' 'EXPO_TOKEN' 'sentry\.io' 'amazonaws\.com'; do
  # shellcheck disable=SC2086
  hits="$(grep -RIliE "$pat" $files 2>/dev/null)"
  [ -z "$hits" ] || fail "foreign service '$pat' configured in: $hits"
done
[ ! -e eas.json ] && [ ! -e apps/mobile/eas.json ] || fail "eas.json present"
# Whitelist check: every URL host in compose/infra is localhost or a compose service name.
allowed='localhost|127\.0\.0\.1|db|redis|minio|powersync|api|worker|proxy|storybook|schemas\.|www\.w3\.org|json-schema\.org'
hosts="$(grep -RIhoE 'https?://[A-Za-z0-9.-]+' docker-compose.yml infra 2>/dev/null | sed -E 's#https?://##' | sort -u)"
for h in $hosts; do
  echo "$h" | grep -Eq "^($allowed)" || fail "non-whitelisted host by default: $h"
done
# The test only has value once the platform config exists.
[ -f docker-compose.yml ] && grep -q 'proxy:' docker-compose.yml || fail "platform compose (proxy service) not yet defined"
finish
