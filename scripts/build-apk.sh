#!/usr/bin/env bash
# Builds the arm64 release APK of apps/mobile inside Docker -> apps/mobile/dist/app-release.apk.
# The repo is copied into a cached volume (/build) so the linux/amd64 node_modules never overwrite the
# arm64 ones used by the js-test container; Gradle and the Android SDK are cached in named volumes.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
APK=apps/mobile/dist/app-release.apk; STAMP=apps/mobile/dist/.inputs
# Skip the (slow) build when the APK already matches the current inputs (committed + uncommitted).
inputs="$( { git ls-files -s apps/mobile packages pnpm-lock.yaml scripts/in-container/build-apk.sh infra/docker/android-build.Dockerfile;
             git diff HEAD -- apps/mobile packages pnpm-lock.yaml scripts/in-container/build-apk.sh;
             git ls-files --others --exclude-standard apps/mobile packages | xargs -I{} git hash-object {} 2>/dev/null;
             echo "E2E=${EXPO_PUBLIC_E2E:-1}"; } | git hash-object --stdin)"
if [ -f "$APK" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$inputs" ]; then echo "apk: à jour ($APK)"; exit 0; fi
bash "$(git rev-parse --show-toplevel)/scripts/dc.sh" --profile build build android-build >/dev/null
bash "$(git rev-parse --show-toplevel)/scripts/dc.sh" --profile build run --rm android-build bash /repo/scripts/in-container/build-apk.sh
echo "$inputs" > "$STAMP"
ls -l "$APK"
