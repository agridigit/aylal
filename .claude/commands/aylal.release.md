---
description: Clôt une fonctionnalité AYLAL — fusion locale dans main, SemVer, CHANGELOG, balises. Aucun push.
argument-hint: <branche> <Fx>
---
Arguments : `$ARGUMENTS` = `<branche> <Fx>`. Ne pose aucune question. Git local uniquement, jamais de push.

1. Si `specs/<branche>/.status` n'existe pas ou ne commence pas par `DONE` ou `DOCS_DONE` → réponds `ÉCHEC : statut <valeur> (attendu DONE ou DOCS_DONE)` et arrête.
2. `git switch <branche>` puis `make check`. Rouge → réponds `ÉCHEC : make check rouge` avec les 5 dernières lignes d'erreur, et arrête.
3. Écris `MERGED <date ISO 8601, ex. $(date -u +%Y-%m-%dT%H:%M:%SZ)>` dans `specs/<branche>/.status`, puis
   `git add specs/<branche>/.status` et `git commit -m "chore(<Fx>): mark <branche> as merged"`.
4. Lance le sous-agent `git-keeper` avec `<branche> <Fx>`.
5. Renvoie uniquement sa ligne (`vX.Y.Z (local)` ou `ÉCHEC : …`).
