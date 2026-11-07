#!/usr/bin/env bash
# Measures the APK size (plain bash/awk, no Android tooling needed).
# APK_PATH overrides the APK location; MEASURE_OUT receives the JSON measure (FR-028).
set -euo pipefail
default_mb=40; max_mb=60
limit_mb="$default_mb"  # not overridable by env: only the documented budget file may raise it
derogation=""
# Documented override (constitution, governance): specs/<current branch>/apk-budget.env, branch-scoped, bounded.
branch="${APK_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)}"
budget_file="${SPECS_DIR:-specs}/$branch/apk-budget.env"
if [ -n "$branch" ] && [ -f "$budget_file" ]; then
  refuse() { echo "apk-size: DEROGATION REFUSEE - $1 ($budget_file)" >&2; exit 1; }
  APK_LIMIT_MB="" APK_BUDGET_REASON="" DECISION_REF=""
  # shellcheck disable=SC1090
  . "$budget_file"
  [[ "$APK_LIMIT_MB" =~ ^[0-9]+$ ]] || refuse "APK_LIMIT_MB absent ou non numerique"
  [ "$APK_LIMIT_MB" -gt "$default_mb" ] || refuse "APK_LIMIT_MB doit depasser $default_mb"
  [ "$APK_LIMIT_MB" -le "$max_mb" ] || refuse "APK_LIMIT_MB > $max_mb Mo"
  [ -n "$APK_BUDGET_REASON" ] || refuse "APK_BUDGET_REASON manquant"
  [ -n "$DECISION_REF" ] || refuse "DECISION_REF manquant"
  [ -f "$DECISION_REF" ] || refuse "DECISION_REF introuvable ($DECISION_REF)"
  grep -qiE '^#+ .*D[ée]rogation' "$DECISION_REF" || refuse "DECISION_REF sans section « Dérogation »"
  limit_mb="$APK_LIMIT_MB"
  derogation="DÉROGATION: limite $limit_mb Mo au lieu de $default_mb Mo — ${APK_BUDGET_REASON//\"/} — $DECISION_REF"
  echo "$derogation"
fi
apk="${APK_PATH:-apps/mobile/dist/app-release.apk}"
if [ ! -f "$apk" ]; then
  echo "apk-size: NON MESURE - APK absent ($apk) ; lancer make apk. Ce n'est pas un succes." >&2
  exit 1
fi
size=$(wc -c < "$apk" | tr -d ' ')
limit=$((limit_mb * 1024 * 1024))
verdict=met; [ "$size" -le "$limit" ] || verdict=not_met
echo "APK: $size bytes (limit $limit)"
if [ -n "${MEASURE_OUT:-}" ]; then
  mkdir -p "$(dirname "$MEASURE_OUT")"
  printf '{"metric": "apk_size_mb", "value": %s, "unit": "MB", "threshold": %s, "device": "%s", "date": "%s", "verdict": "%s", "build": "%s", "derogation": "%s"}\n' \
    "$(awk -v s="$size" 'BEGIN{printf "%.2f", s/1048576}')" "$limit_mb" "${MEASURE_DEVICE:-n/a}" "$(date +%F)" "$verdict" "${BUILD_ID:-local}" "$derogation" > "$MEASURE_OUT"
fi
[ "$verdict" = met ] || { echo "apk-size: over ${limit_mb} MB" >&2; exit 1; }
