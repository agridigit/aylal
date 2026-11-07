#!/usr/bin/env bash
# apk-size logic without Android build: APK_PATH override, 40 MB limit, JSON measure output (SC-008, FR-028).
source "$(dirname "$0")/../platform/lib.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
S=scripts/in-container/apk-size.sh
grep -q 'APK_PATH' "$S" || fail "apk-size.sh does not support APK_PATH"
truncate -s 30M "$T/ok.apk"; truncate -s 41M "$T/big.apk"
APK_PATH="$T/ok.apk" MEASURE_OUT="$T/m.json" bash "$S" >"$T/out" 2>&1 || fail "30 MB APK must pass"
grep -q '"metric": *"apk_size_mb"' "$T/m.json" 2>/dev/null || fail "measure JSON missing apk_size_mb"
grep -q '"verdict": *"met"' "$T/m.json" 2>/dev/null || fail "verdict must be met"
APK_PATH="$T/big.apk" MEASURE_OUT="$T/m2.json" bash "$S" >"$T/out2" 2>&1 && fail "41 MB APK must fail"
grep -q '"verdict": *"not_met"' "$T/m2.json" 2>/dev/null || fail "verdict must be not_met"
finish
