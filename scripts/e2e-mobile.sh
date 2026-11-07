#!/usr/bin/env bash
# Mobile E2E (Maestro) — builds the APK in Docker, installs it on an Android device and runs every flow.
#   Linux + /dev/kvm : the emulator runs inside the e2e container (historic path).
#   macOS (no KVM in Docker): the emulator runs NATIVELY on the Mac (approved exception, see
#   specs/001-foundations/decisions.md); adb, APK install and Maestro still run in Docker and reach the
#   host adb server through host.docker.internal (adb stays bound to 127.0.0.1).
# E2E_NO_BUILD=1 reuses apps/mobile/dist/app-release.apk. E2E_SKIP=1 skips with a loud warning (never in make check on a configured machine).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DC="bash scripts/dc.sh"
AVD="${AVD:-aylal-2go}"
FLOWS="${E2E_FLOWS:-apps/mobile/maestro}"
APK="${APK_PATH:-apps/mobile/dist/app-release.apk}"

if [ "${E2E_SKIP:-}" = "1" ]; then echo "AVERTISSEMENT : e2e mobile ignoré (E2E_SKIP=1)" >&2; exit 0; fi

case "$(uname -s)" in
  Linux)
    [ -e /dev/kvm ] || { echo "make e2e: KVM absent (/dev/kvm) : émulateur impossible. Machine Linux avec KVM requise, ou E2E_SKIP=1 (écart signalé)." >&2; exit 1; }
    make apk
    exec $DC --profile e2e run --rm --device /dev/kvm e2e e2e-run "$APK" "$FLOWS" ;;
  Darwin) ;;
  *) echo "make e2e: système non pris en charge" >&2; exit 1 ;;
esac

ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
ADB="$ANDROID_HOME/platform-tools/adb"; EMU="$ANDROID_HOME/emulator/emulator"
[ -x "$ADB" ] && [ -x "$EMU" ] || { echo "make e2e: émulateur Android absent ($ANDROID_HOME). Voir docs/modules/001-foundations/ingenieur.md § Émulateur macOS." >&2; exit 1; }
"$EMU" -list-avds | grep -qx "${AVD}" || { echo "make e2e: AVD « ${AVD} » introuvable (avdmanager create avd -n ${AVD} ...)." >&2; exit 1; }

"$ADB" start-server >/dev/null
if ! "$ADB" devices | grep -qE '^emulator-[0-9]+\s+device$'; then
  echo "e2e: démarrage de l'émulateur ${AVD}…"
  extra=(); [ "${E2E_HEADLESS:-}" = "1" ] && extra=(-no-window)
  nohup "$EMU" -avd "${AVD}" -no-snapshot-save -no-boot-anim -no-audio ${extra[@]+"${extra[@]}"} >/tmp/aylal-emulator.log 2>&1 &
fi
"$ADB" wait-for-device
for _ in $(seq 1 90); do
  [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] && break; sleep 2
done
[ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ] || { echo "make e2e: l'émulateur n'a pas démarré (voir /tmp/aylal-emulator.log)" >&2; exit 1; }

# The offline_sync flow needs the real stack (API + PowerSync) on the host: the emulator reaches it through 10.0.2.2.
# Dev token enabled and one shared JWT secret (API signs, PowerSync verifies); both for this test run only. Idempotent.
mkdir -p .aylal/e2e
SECRET_FILE=".aylal/e2e/jwt-secret"
[ -s "$SECRET_FILE" ] || { umask 077; head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' > "$SECRET_FILE"; }
export AYLAL_ENABLE_DEV_TOKEN=1 AYLAL_JWT_SECRET="$(cat "$SECRET_FILE")"
make up
$DC exec -T api python - <<'PY'
import asyncio
from app.db.seed import seed
from app.db.session import sessionmaker

async def main() -> None:
    async with sessionmaker() as session:
        await seed(session)

asyncio.run(main())
PY

# E2E_NO_BUILD=1 reuses an existing APK (local iteration only; make check always rebuilds).
if [ "${E2E_NO_BUILD:-}" = "1" ] && [ -f "$APK" ]; then echo "e2e: APK existant réutilisé ($APK)"; else make apk; fi
# Fresh logcat so the exported measures come from this run only (provisional emulator values, T110).
"$ADB" logcat -c || true
rc=0
$DC --profile e2e run --rm -e ADB_SERVER_HOST=host.docker.internal e2e e2e-run "$APK" "$FLOWS" || rc=$?
MEASURES_DIR="docs/modules/001-foundations/measures"
line="$({ "$ADB" logcat -d 2>/dev/null | grep 'AYLAL_MEASURES ' | tail -1 | sed 's/.*AYLAL_MEASURES //' | tr -d '\r'; } || true)"
if [ -n "$line" ]; then
  mkdir -p "$MEASURES_DIR"
  printf '%s\n' "$line" > "$MEASURES_DIR/emulator-aylal-2go.json" && echo "e2e: mesures provisoires -> $MEASURES_DIR/emulator-aylal-2go.json"
fi
exit "$rc"
