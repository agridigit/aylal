# AYLAL — règles du projet pour Claude Code

Source de vérité fonctionnelle : `docs/cps/AYLAL-CPS.md`. Constitution : `.specify/memory/constitution.md`.
En cas de conflit : constitution > CPS > spec de la fonctionnalité > plan > tâches.

## Langue
- Code, types, noms de fichiers, commits : anglais.
- Specs, docs, messages à l'utilisateur : français. Textes d'interface : clés i18n (darija, arabe, français), jamais en dur.

## Test first (obligatoire, sans exception)
1. RED : écrire les tests à partir des critères d'acceptation (« Étant donné / Quand / Alors ») de la spec. Les lancer. Ils DOIVENT échouer. Commit `test(<feature>): red - <sujet>`.
2. GREEN : écrire le minimum de code pour faire passer ces tests. Commit `feat(<feature>): green - <sujet>`.
3. REFACTOR : nettoyer sans changer le comportement, tests toujours verts. Commit `refactor(<feature>): ...`.
- Interdit : modifier un test pour le faire passer, sauf si le test contredit la spec (le noter dans `specs/<feature>/decisions.md`).
- Chaque critère d'acceptation P1 a au moins un test automatisé. Couverture minimale du code métier : 80 %.
- **Trois niveaux de tests obligatoires pour chaque module** (`packages/*`, `services/*`, `apps/*`) et pour chaque fonctionnalité :
  - unitaires : `<module>/tests/unit/` — une règle ou une fonction isolée, sans réseau ni base ;
  - intégration : `<module>/tests/integration/` (et `tests/contract/` pour les contrats) — plusieurs composants réels ensemble (API + PostgreSQL, synchronisation SQLite/PowerSync, workers + Redis/MinIO, domaine TS ↔ API Python) ;
  - bout en bout : `services/<s>/tests/e2e/` (parcours HTTP complet sur la pile Docker), `apps/mobile/e2e/` (Maestro), `apps/web|desktop/e2e/` (Playwright) — parcours utilisateur d'un critère d'acceptation P1.
- Chaque critère d'acceptation P1 est couvert aux trois niveaux quand c'est applicable ; sinon la raison est notée dans `specs/<feature>/decisions.md`.
- Garde automatique : `make test-pyramid` (inclus dans `make check`) refuse un module sans les trois niveaux, ou une branche qui change du code sans ajouter de tests aux trois niveaux. `make e2e` doit être vert avant `/aylal.release`.

## Docker (obligatoire)
- Tout tourne dans Docker : API, workers, base, synchronisation, stockage, tests, rendu des diagrammes.
- Commandes autorisées pour tester : `make test`, `make test-api`, `make test-domain`, `make test-mobile`, `make test-unit`, `make test-integration`, `make e2e`, `make check`, `make check-cached`, ou `docker compose ...`.
- Vitesse sans compromis : pendant une tâche, ne lancer que les tests concernés (`ARGS=<fichiers>`) ; `make check` complet par `reviewer` en fin de groupe ; `make check-cached` ne saute la vérification que si le même commit est déjà vert.
- Ne jamais installer de dépendance sur la machine hôte ; ajouter au Dockerfile concerné.

## Architecture (voir CPS section 16)
- Monorepo pnpm : `apps/mobile` (Expo React Native), `apps/web`, `apps/desktop`, `packages/domain` (types et règles métier TS, sans dépendance UI), `packages/ui`, `packages/i18n`, `services/api` (FastAPI, Python 3.13), `services/workers`.
- Toute règle métier vit dans `packages/domain` (TS) ou `services/api/app/domain` (Python), jamais dans un écran.
- Hors ligne d'abord : SQLite local + PowerSync. Aucune donnée perdue.
- Design : composants de `packages/ui` uniquement, jetons du design system AYLAL, RTL vérifié, 4 états par écran (chargement, vide, erreur, hors ligne).
- Design de référence de l'app mobile : `docs/design/aylal-design-system.md` (Olivier, cartes élevées, icônes trait arrondi, jetons à deux niveaux, Unistyles). Tout écran ou composant s'y conforme.

## Documentation (à chaque fin de fonctionnalité)
Dossier `docs/modules/<NNN-feature>/` :
- `ingenieur.md` : document expert ingénieur logiciel.
- `agriculteur.fr.md` et `agriculteur.ar.md` : guide utilisateur agriculteur.
- `diagrams/*.mmd` : diagrammes en code Mermaid (`flowchart`, `sequenceDiagram`, `erDiagram`, `stateDiagram-v2`).
- `img/*.svg` et `img/*.png` : rendus générés par `make diagrams` ; chaque doc intègre l'image ET le bloc de code source.

## Économie de tokens
- Lire seulement les fichiers utiles ; préférer `grep`/`glob` à la lecture complète.
- Déléguer aux sous-agents définis dans `.claude/agents/` (modèles sonnet ou haiku). Jamais opus.
- Réponses courtes ; pas de récapitulatif de ce qui vient d'être fait.
- Une session = une étape Spec Kit. L'état passe par les fichiers (`specs/`, git), pas par la conversation.

## Versionnement git (100 % Claude, local uniquement)
- Une branche par fonctionnalité (`NNN-slug`) ; `hotfix/<slug>` pour les bugs ; `main` toujours vert.
- Un commit Conventional Commits par étape TDD : `test(<Fx>)` → RED, `feat(<Fx>)` → GREEN, `refactor(<Fx>)` → REFACTOR (types : feat, fix, test, refactor, docs, chore, ci, build).
- SemVer depuis la dernière balise `vX.Y.Z` (aucune → v0.0.0) : fonctionnalité = MINOR+1, uniquement des correctifs = PATCH+1, v1.0.0 quand F0 à F7 sont fusionnées. Version reportée dans tous les `package.json` et `services/*/pyproject.toml`.
- `CHANGELOG.md` tenu par le sous-agent `git-keeper` (Ajouts / Corrections / Documentation / Technique).
- Fin de fonctionnalité = `/aylal.release <branche> <Fx>` ; bug = `/aylal.hotfix <description>`.
- Aucun push, fetch, pull, remote ni `gh` ; jamais `reset --hard` ni réécriture d'historique (garde : `scripts/guard-git.sh`).
