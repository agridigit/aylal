#!/usr/bin/env bash
# AYLAL_IN_CONTAINER - runs inside aylal-android-build.
# APK_PATH overrides the APK location; MEASURE_OUT receives the JSON measure (FR-028).
set -euo pipefail
limit_mb="${APK_LIMIT_MB:-40}"
apk="${APK_PATH:-apps/mobile/android/app/build/outputs/apk/release/app-release.apk}"
if [ ! -f "$apk" ]; then
  [ -f apps/mobile/package.json ] || { echo "apk-size: apps/mobile absent, no APK to measure" >&2; exit 1; }
  if ! grep -q '"build:android:release"' apps/mobile/package.json; then
    echo "apk-size: NON MESURE - apps/mobile n'a pas de projet natif ni de script build:android:release (voir specs/001-foundations/decisions.md). Ce n'est pas un succes." >&2
    exit 1
  fi
  pnpm --filter mobile build:android:release
fi
size=$(wc -c < "$apk" | tr -d ' ')
limit=$((limit_mb * 1024 * 1024))
verdict=met; [ "$size" -le "$limit" ] || verdict=not_met
echo "APK: $size bytes (limit $limit)"
if [ -n "${MEASURE_OUT:-}" ]; then
  mkdir -p "$(dirname "$MEASURE_OUT")"
  printf '{"metric": "apk_size_mb", "value": %s, "unit": "MB", "threshold": %s, "device": "%s", "date": "%s", "verdict": "%s", "build": "%s"}\n' \
    "$(awk -v s="$size" 'BEGIN{printf "%.2f", s/1048576}')" "$limit_mb" "${MEASURE_DEVICE:-n/a}" "$(date +%F)" "$verdict" "${BUILD_ID:-local}" > "$MEASURE_OUT"
fi
[ "$verdict" = met ] || { echo "apk-size: over ${limit_mb} MB" >&2; exit 1; }
