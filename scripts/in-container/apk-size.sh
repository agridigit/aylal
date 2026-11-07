#!/usr/bin/env bash
# AYLAL_IN_CONTAINER - runs inside aylal-android-build.
set -euo pipefail
limit_mb="${APK_LIMIT_MB:-40}"
apk="apps/mobile/android/app/build/outputs/apk/release/app-release.apk"
if [ ! -f "$apk" ]; then
  [ -f apps/mobile/package.json ] || { echo "apk-size: apps/mobile absent, no APK to measure" >&2; exit 1; }
  pnpm --filter mobile build:android:release
fi
size=$(stat -c %s "$apk")
limit=$((limit_mb * 1024 * 1024))
echo "APK: $size bytes (limit $limit)"
[ "$size" -le "$limit" ] || { echo "apk-size: over ${limit_mb} MB" >&2; exit 1; }
