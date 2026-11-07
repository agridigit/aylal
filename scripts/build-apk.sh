#!/usr/bin/env bash
# Builds the arm64 release APK of apps/mobile inside Docker -> apps/mobile/dist/app-release.apk.
# The repo is copied into a cached volume (/build) so the linux/amd64 node_modules never overwrite the
# arm64 ones used by the js-test container; Gradle and the Android SDK are cached in named volumes.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
docker compose --profile build build android-build >/dev/null
docker compose --profile build run --rm android-build bash /repo/scripts/in-container/build-apk.sh
ls -l apps/mobile/dist/app-release.apk
