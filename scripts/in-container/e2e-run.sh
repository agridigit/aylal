#!/usr/bin/env bash
# AYLAL_IN_CONTAINER — runs in the e2e image: install the APK and run the Maestro flows.
# ADB_SERVER_HOST set => use the adb server of that host (macOS native emulator), proxied on localhost:5037
# because Maestro only talks to a local adb server.
set -euo pipefail
apk="$1"; flows="$2"
if [ -n "${ADB_SERVER_HOST:-}" ]; then
  # adb client -> remote server directly (never spawns a local server); Maestro -> localhost:5037 proxy.
  export ADB_SERVER_SOCKET="tcp:${ADB_SERVER_HOST}:5037"
  socat TCP-LISTEN:5037,bind=127.0.0.1,fork,reuseaddr "TCP:${ADB_SERVER_HOST}:5037" &
  for _ in $(seq 1 20); do (exec 3<>/dev/tcp/127.0.0.1/5037) 2>/dev/null && break; sleep 0.25; done
fi
[ -f "$apk" ] || { echo "e2e: APK introuvable ($apk) — lancer make apk" >&2; exit 1; }
adb devices | grep -qE '\sdevice$' || { echo "e2e: aucun appareil Android connecté" >&2; exit 1; }
adb install -r -t "$apk"
mkdir -p .aylal/e2e
maestro test --format junit --output .aylal/e2e/report.xml "$flows"
