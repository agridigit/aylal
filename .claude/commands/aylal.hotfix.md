---
description: Corrige un bug AYLAL en test first sur une branche hotfix/<slug>, puis publie une version PATCH locale. Aucun push.
argument-hint: <description du bug>
---
Bug : `$ARGUMENTS`. Ne pose aucune question. Git local uniquement, jamais de push.

1. Slug : description en minuscules ASCII, mots joints par `-`, 40 caractères max.
   `git switch main` (arbre propre requis, sinon `ÉCHEC : arbre de travail non propre`), puis `git switch -c hotfix/<slug>`.
2. RED : sous-agent `test-writer` — écrire un test automatisé qui reproduit le bug décrit, le lancer via `make test-*` et confirmer qu'il échoue pour la bonne raison.
   Commit `test(hotfix): reproduce <slug>`.
3. GREEN : sous-agent `implementer` — corriger avec le minimum de code, sans modifier le test.
   Commit `fix(<portée>): <sujet>` (portée = module concerné, ex. `domain`, `api`, `mobile`).
4. `make check` doit être vert ; sinon un second tour `implementer` avec la sortie d'erreur ; toujours rouge → `ÉCHEC : make check rouge` et arrête (branche conservée).
5. Sous-agent `git-keeper` avec `hotfix/<slug> hotfix "<description>"` (la branche ne contient que fix/test → version PATCH).
6. Renvoie uniquement sa ligne.
