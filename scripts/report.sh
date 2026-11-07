#!/usr/bin/env bash
# État de la boucle : statut par fonctionnalité, tâches cochées, docs présentes
cd "$(git rev-parse --show-toplevel)"
printf "%-32s %-22s %-10s %-6s\n" "FONCTIONNALITÉ" "STATUT" "TÂCHES" "DOCS"
for d in specs/*/; do
  f="$(basename "$d")"; st="$(cat "$d/.status" 2>/dev/null || echo '-')"
  total=$(grep -cE '^- \[( |x)\]' "$d/tasks.md" 2>/dev/null || echo 0)
  done_=$(grep -cE '^- \[x\]' "$d/tasks.md" 2>/dev/null || echo 0)
  docs=$([[ -f "docs/modules/$f/ingenieur.md" && -f "docs/modules/$f/agriculteur.fr.md" ]] && echo oui || echo non)
  printf "%-32s %-22s %-10s %-6s\n" "$f" "${st:0:22}" "$done_/$total" "$docs"
done
# Agrégation des mesures : docs/modules/<MODULE>/measures/*.json -> mesures.md (AC6.4, SC-011).
# Sans MODULE, tous les modules ayant un dossier measures/. Aucune mesure inventée : absente = « non mesuré ».
module_report() {
  local dir="docs/modules/$1" out="docs/modules/$1/mesures.md"
  [[ -d "$dir/measures" ]] || return 0
  {
    echo "# Mesures — $1"; echo
    echo "| Mesure | Valeur | Seuil | Appareil | Date | Build | Verdict |"
    echo "|---|---|---|---|---|---|---|"
    for m in startup_ms map_open_ms fps apk_size_mb daily_traffic_mb; do
      f="$dir/measures/$m.json"
      if [[ -f "$f" ]]; then
        g() { sed -n "s/.*\"$1\": *\"\{0,1\}\([^\",}]*\)\"\{0,1\}[,}].*/\1/p" "$f" | head -1; }
        v="$(g verdict)"; lbl="tenu"; [[ "$v" == "met" ]] || lbl="non tenu"
        echo "| $m | $(g value) $(g unit) | $(g threshold) | $(g device) | $(g date) | $(g build) | $lbl |"
      else
        echo "| $m | - | - | - | - | - | non mesuré |"
      fi
    done
  } > "$out"
  if grep -qE '\| non tenu \|$' "$out"; then
    printf '\nUn seuil non tenu ouvre un réexamen du choix technique (noté dans decisions.md).\n' >> "$out"
  fi
}
if [[ -n "${MODULE:-}" ]]; then module_report "$MODULE"
else for d in docs/modules/*/; do module_report "$(basename "$d")"; done; fi

# STRICT=1 : un seuil « non tenu » dans un mesures.md fait échouer
if [[ "${STRICT:-0}" == "1" ]]; then
  files=(docs/modules/${MODULE:-*}/mesures.md)
  if grep -qs -E '\| non tenu \|$' "${files[@]}"; then
    echo "STRICT : au moins un seuil non tenu" >&2; exit 1
  fi
fi
