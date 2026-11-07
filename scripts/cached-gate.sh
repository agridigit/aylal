#!/usr/bin/env bash
# Runs a quality gate only if it has not already passed on the same code.
# Usage: scripts/cached-gate.sh <name> <make-target> [docs-only-target]
#   - clean tree and HEAD already green for <name>            -> skip (cached)
#   - only docs/, specs/, CHANGELOG.md changed since last green -> run [docs-only-target] (or skip if empty)
#   - otherwise                                               -> run full <make-target>
# On success, stamps HEAD in .aylal/green-<name>. A dirty code tree (outside docs/, specs/) is never cached.
set -euo pipefail
name="$1"; target="$2"; docs_target="${3:-}"
cd "$(git rev-parse --show-toplevel)"
stamp=".aylal/green-$name"; mkdir -p .aylal
head="$(git rev-parse HEAD)"
# docs/ and specs/ edits (e.g. docs written in parallel) do not make the code tree dirty.
clean=false
[ -z "$(git status --porcelain --untracked-files=normal | grep -vE '^.. (docs/|specs/|CHANGELOG\.md$)' || true)" ] && clean=true

if $clean && [ -f "$stamp" ]; then
  last="$(cat "$stamp")"
  if [ "$last" = "$head" ]; then echo "[$name] déjà vert sur ${head:0:7} (cache)"; exit 0; fi
  if git merge-base --is-ancestor "$last" "$head" 2>/dev/null &&
     [ -z "$(git diff --name-only "$last" "$head" | grep -vE '^(docs/|specs/|CHANGELOG\.md$)' || true)" ]; then
    echo "[$name] seuls docs/specs ont changé depuis ${last:0:7}"
    [ -n "$docs_target" ] && make "$docs_target"
    echo "$head" > "$stamp"; exit 0
  fi
fi

make "$target"
$clean && echo "$head" > "$stamp" || true
