#!/usr/bin/env bash
# Builds the release APK (arm64-v8a, see decisions.md) in Docker and fails above the size limit (default 40 MB, R18).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash scripts/build-apk.sh
APK_PATH="${APK_PATH:-apps/mobile/dist/app-release.apk}" APK_LIMIT_MB="${APK_LIMIT_MB:-40}" bash scripts/in-container/apk-size.sh
