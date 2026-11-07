#!/usr/bin/env bash
# Rend chaque docs/**/diagrams/*.mmd en img/<nom>.svg et img/<nom>.png, via Mermaid CLI dans Docker.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
IMAGE="${MERMAID_IMAGE:-minlag/mermaid-cli:latest}"
count=0
while IFS= read -r -d '' mmd; do
  dir="$(dirname "$(dirname "$mmd")")"; name="$(basename "$mmd" .mmd)"
  mkdir -p "$dir/img"
  for ext in svg png; do
    out="$dir/img/$name.$ext"
    if [[ ! -f "$out" || "$mmd" -nt "$out" ]]; then
      extra=(); [[ "$ext" == png ]] && extra=(-b white -s 2)
      docker run --rm -u "$(id -u):$(id -g)" -v "$ROOT":/data "$IMAGE" \
        -i "/data/$mmd" -o "/data/$out" -c /data/docs/templates/mermaid-config.json "${extra[@]}" >/dev/null
      count=$((count + 1))
    fi
  done
done < <(find docs -path '*/diagrams/*.mmd' -print0)
echo "diagrammes rendus : $count fichier(s)"
# Contrôle : toute image référencée dans un .md doit exister
missing=0
while IFS= read -r md; do
  d="$(dirname "$md")"
  grep -oE '\]\(img/[^)]+\)' "$md" | sed -E 's/\]\((.*)\)/\1/' | while read -r img; do
    [[ -f "$d/$img" ]] || { echo "image manquante : $d/$img (référencée dans $md)"; exit 1; }
  done || missing=1
done < <(find docs/modules -name '*.md' 2>/dev/null)
exit $missing
