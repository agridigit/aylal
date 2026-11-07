#!/usr/bin/env bash
# Builds the release APK (arm64-v8a, see decisions.md) in Docker and fails above the size limit (default 40 MB, R18; documented per-branch override in specs/<branch>/apk-budget.env, max 60 MB).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash scripts/build-apk.sh
APK_PATH="${APK_PATH:-apps/mobile/dist/app-release.apk}" APK_BRANCH="${APK_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)}" bash scripts/in-container/apk-size.sh
