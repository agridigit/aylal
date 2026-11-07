#!/usr/bin/env bash
# Régénère docs/README.md à partir de docs/modules/*
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
{
  echo "# Documentation AYLAL"; echo
  echo "| Module | Document ingénieur | Guide agriculteur (FR) | Guide agriculteur (AR) | Mis à jour |"
  echo "| --- | --- | --- | --- | --- |"
  for d in docs/modules/*/; do
    m="$(basename "$d")"
    date="$(git log -1 --format=%cs -- "$d" 2>/dev/null || echo '-')"
    echo "| $m | [ingénieur](modules/$m/ingenieur.md) | [FR](modules/$m/agriculteur.fr.md) | [AR](modules/$m/agriculteur.ar.md) | $date |"
  done
} > docs/README.md
echo "docs/README.md régénéré"
