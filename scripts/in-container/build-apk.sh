#!/usr/bin/env bash
# AYLAL_IN_CONTAINER — runs in the android-build image.
set -euo pipefail
yes | sdkmanager --sdk_root="$ANDROID_HOME" --licenses >/dev/null 2>&1 || true
rsync -a --delete --exclude node_modules --exclude .git --exclude 'apps/mobile/android' --exclude 'apps/mobile/dist' \
  --exclude .worktrees --exclude .aylal /repo/ /build/
cd /build
pnpm install --frozen-lockfile=false --config.confirmModulesPurge=false
cd apps/mobile
CI=1 npx expo prebuild --platform android --no-install --clean
# arm64-v8a only: ABI of the emulator and of real 2 GB phones; faster build, smaller APK (decisions.md).
sed -i 's/^reactNativeArchitectures=.*/reactNativeArchitectures=arm64-v8a/' android/gradle.properties
grep -q '^reactNativeArchitectures=' android/gradle.properties || echo 'reactNativeArchitectures=arm64-v8a' >> android/gradle.properties
(cd android && EXPO_PUBLIC_E2E="${EXPO_PUBLIC_E2E:-1}" ./gradlew --no-daemon assembleRelease)
mkdir -p /repo/apps/mobile/dist
cp android/app/build/outputs/apk/release/app-release.apk /repo/apps/mobile/dist/app-release.apk
