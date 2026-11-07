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
# STRICT=1 : un seuil « non tenu » dans un mesures.md fait échouer
if [[ "${STRICT:-0}" == "1" ]] && grep -qsi 'non tenu' docs/modules/*/mesures.md; then
  echo "STRICT : au moins un seuil non tenu" >&2; exit 1
fi
