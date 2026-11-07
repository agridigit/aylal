#!/usr/bin/env bash
# Builds the release APK in a container and fails above the size limit (default 40 MB, R18).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker build -q -f infra/docker/android-build.Dockerfile -t aylal-android-build . >/dev/null
docker run --rm -v "$PWD":/repo -w /repo -e APK_LIMIT_MB="${APK_LIMIT_MB:-40}" \
  aylal-android-build bash scripts/in-container/apk-size.sh
