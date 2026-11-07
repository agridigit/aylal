#!/usr/bin/env bash
# AYLAL — boucle Spec Kit autonome : specify -> clarify -> plan -> tasks -> analyze -> implement (TDD) -> docs -> merge
# Usage :
#   scripts/speckit-loop.sh                 # toutes les fonctionnalités de prompts/features.tsv, dans l'ordre
#   scripts/speckit-loop.sh F1 F2           # seulement celles-ci
#   ONLY_STEP=implement scripts/speckit-loop.sh F3   # reprendre une étape précise
# Variables :
#   MODEL=sonnet            modèle des sessions principales (sonnet par défaut ; haiku possible pour clarify/analyze)
#   LIGHT_MODEL=haiku       modèle des étapes légères (clarify, analyze)
#   MAX_IMPL_ROUNDS=4       relances max de l'implémentation par fonctionnalité
#   BUDGET_USD=             plafond en dollars par session si votre version de claude supporte --max-budget-usd
#   PARALLEL_DOCS=1         génère la doc d'une fonctionnalité en arrière-plan (worktree) pendant que la suivante démarre
#   YOLO=1                  --dangerously-skip-permissions (UNIQUEMENT dans un conteneur jetable)
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
MODEL="${MODEL:-sonnet}"
LIGHT_MODEL="${LIGHT_MODEL:-haiku}"
MAX_IMPL_ROUNDS="${MAX_IMPL_ROUNDS:-4}"
PARALLEL_DOCS="${PARALLEL_DOCS:-1}"
MAIN_BRANCH="${MAIN_BRANCH:-main}"
LOG_DIR="$ROOT/.aylal/logs"; mkdir -p "$LOG_DIR"
DOC_PIDS=()

log() { printf '\n\033[1;32m[%s] %s\033[0m\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\n\033[1;31m[ERREUR] %s\033[0m\n' "$*"; exit 1; }

# --- options communes de claude -p ---
PERM=(--permission-mode acceptEdits)
[[ "${YOLO:-0}" == "1" ]] && PERM=(--dangerously-skip-permissions)
EXTRA=()
if [[ -n "${BUDGET_USD:-}" ]] && claude --help 2>/dev/null | grep -q -- '--max-budget-usd'; then
  EXTRA+=(--max-budget-usd "$BUDGET_USD")
fi

# run_claude <nom_log> <modèle> <max_turns> <prompt>
run_claude() {
  local name="$1" model="$2" turns="$3" prompt="$4"
  local logfile="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-$name.jsonl"
  log "claude [$model] $name"
  claude -p "$prompt" --model "$model" "${PERM[@]}" "${EXTRA[@]}" \
    --max-turns "$turns" --output-format stream-json --verbose >"$logfile" 2>&1 \
    || { echo "  (session terminée avec code $? — voir $logfile)"; return 1; }
}

feature_dir() { echo "$ROOT/specs/$(git rev-parse --abbrev-ref HEAD)"; }
status_of() { [[ -f "$1/.status" ]] && cat "$1/.status" || echo ""; }

# --- étape 0 : constitution (une seule fois) ---
if ! grep -q "Test first" .specify/memory/constitution.md 2>/dev/null; then
  run_claude constitution "$MODEL" 30 "/speckit.constitution $(cat prompts/00-constitution.md)"
  git add -A && git commit -qm "docs: AYLAL constitution v1.0.0" || true
fi

# --- liste des fonctionnalités ---
mapfile -t ROWS < <(grep -v '^#' prompts/features.tsv | grep -v '^\s*$')
WANTED=("$@")

for row in "${ROWS[@]}"; do
  IFS=$'\t' read -r ID SLUG SECTION TITRE <<<"$row"
  if (( ${#WANTED[@]} )) && [[ ! " ${WANTED[*]} " =~ " $ID " ]]; then continue; fi

  # Reprise : si une branche NNN-<slug> existe déjà, on s'y place
  EXISTING="$(git branch --list "*-$SLUG" | tr -d ' *' | head -n1 || true)"
  if [[ -n "$EXISTING" ]]; then
    git switch -q "$EXISTING"
  else
    git switch -q "$MAIN_BRANCH"
  fi
  if [[ -n "$EXISTING" && "$(status_of "specs/$EXISTING")" == MERGED* ]]; then
    log "$ID déjà terminé — ignoré"; continue
  fi

  log "===== $ID — $TITRE ====="
  step() { [[ -z "${ONLY_STEP:-}" || "${ONLY_STEP}" == "$1" ]]; }

  # 1. specify (crée la branche NNN-slug et specs/NNN-slug/spec.md)
  if [[ -z "$EXISTING" ]] && step specify; then
    if [[ "$ID" == "F0" ]]; then P="$(cat prompts/specify-F0.tpl)"; else
      P="$(sed -e "s/{ID}/$ID/g" -e "s/{TITRE}/$TITRE/g" -e "s/{SECTION}/$SECTION/g" -e "s/{SLUG}/$SLUG/g" prompts/specify.tpl)"; fi
    run_claude "$ID-specify" "$MODEL" 40 "/speckit.specify $P"
  fi
  FD="$(feature_dir)"; [[ -f "$FD/spec.md" ]] || die "$ID : spec.md introuvable dans $FD"

  # 2. clarify (réponses automatiques depuis le CPS)
  if step clarify && [[ ! -f "$FD/plan.md" ]]; then
    run_claude "$ID-clarify" "$LIGHT_MODEL" 25 "/speckit.clarify $(cat prompts/clarify.txt)"
    grep -q 'NEEDS CLARIFICATION' "$FD/spec.md" && \
      run_claude "$ID-clarify-2" "$MODEL" 25 "/speckit.clarify $(cat prompts/clarify.txt)"
  fi

  # 3. plan
  if step plan && [[ ! -f "$FD/plan.md" ]]; then
    run_claude "$ID-plan" "$MODEL" 60 "/speckit.plan $(cat prompts/plan.txt)"
  fi

  # 4. tasks
  if step tasks && [[ ! -f "$FD/tasks.md" ]]; then
    run_claude "$ID-tasks" "$MODEL" 40 "/speckit.tasks $(cat prompts/tasks.txt)"
  fi

  # 5. analyze + auto-correction
  if step analyze && [[ "$(status_of "$FD")" == "" ]]; then
    run_claude "$ID-analyze" "$LIGHT_MODEL" 30 "/speckit.analyze $(cat prompts/analyze.txt)"
    git add -A && git commit -qm "spec($ID): spec, plan, tasks" || true
  fi

  # 6. implémentation test first, en boucle jusqu'à DONE
  if step implement; then
    round=1
    until [[ "$(status_of "$FD")" == DONE* || "$(status_of "$FD")" == DOCS_DONE* ]]; do
      (( round > MAX_IMPL_ROUNDS )) && die "$ID bloqué après $MAX_IMPL_ROUNDS tours : $(status_of "$FD")"
      [[ "$(status_of "$FD")" == BLOCKED* ]] && rm -f "$FD/.status"
      run_claude "$ID-implement-$round" "$MODEL" 200 "/aylal.tdd-implement $(basename "$FD")" || true
      round=$((round + 1))
    done
    make check || die "$ID : make check rouge après implémentation"
  fi

  # 7. documentation de fin de module
  BR="$(git rev-parse --abbrev-ref HEAD)"
  if step docs; then
    if [[ "$PARALLEL_DOCS" == "1" ]]; then
      WT="$ROOT/../aylal-docs-$BR"
      git worktree add -q -f "$WT" -b "docs/$BR" "$BR" 2>/dev/null || git worktree add -q -f "$WT" "docs/$BR"
      log "$ID : documentation lancée en arrière-plan dans $WT"
      ( cd "$WT" && claude -p "/aylal.docs $BR" --model "$MODEL" "${PERM[@]}" "${EXTRA[@]}" --max-turns 80 \
          --output-format stream-json --verbose >"$LOG_DIR/$(date +%Y%m%d-%H%M%S)-$ID-docs.jsonl" 2>&1 ) &
      DOC_PIDS+=("$!:$BR:$WT")
    else
      run_claude "$ID-docs" "$MODEL" 80 "/aylal.docs $BR"
    fi
  fi

  # 8. merge du code dans main
  echo "MERGED $(date -Iseconds)" >"$FD/.status"
  git add -A && git commit -qm "chore($ID): ready to merge" || true
  git switch -q "$MAIN_BRANCH" && git merge -q --no-ff "$BR" -m "merge($ID): $TITRE" || die "conflit de merge sur $ID"
  git tag -f "aylal-$ID" >/dev/null
  log "$ID fusionné dans $MAIN_BRANCH"
done

# --- attendre les documentations en arrière-plan et les fusionner ---
for entry in "${DOC_PIDS[@]}"; do
  IFS=: read -r pid br wt <<<"$entry"
  wait "$pid" || echo "documentation de $br : session en erreur, voir les logs"
  git switch -q "$MAIN_BRANCH"
  git merge -q --no-ff "docs/$br" -m "merge(docs): $br" || die "conflit de merge docs/$br"
  git worktree remove -f "$wt" || true
done
log "Terminé. Rapport : make report"
