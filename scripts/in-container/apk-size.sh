#!/usr/bin/env bash
# Measures the APK size (plain bash/awk, no Android tooling needed).
# APK_PATH overrides the APK location; MEASURE_OUT receives the JSON measure (FR-028).
set -euo pipefail
limit_mb="${APK_LIMIT_MB:-40}"
apk="${APK_PATH:-apps/mobile/dist/app-release.apk}"
if [ ! -f "$apk" ]; then
  echo "apk-size: NON MESURE - APK absent ($apk) ; lancer make apk. Ce n'est pas un succes." >&2
  exit 1
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
