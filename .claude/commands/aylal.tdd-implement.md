---
description: Implémente toutes les tâches de la fonctionnalité courante en test first (RED -> GREEN -> REFACTOR), en parallèle quand les tâches sont marquées [P].
---
Fonctionnalité : $ARGUMENTS (dossier `specs/<feature>/`). Travaille sans poser de question.

1. Lis `specs/<feature>/tasks.md` et regroupe les tâches non cochées par phase, dans l'ordre du fichier.
2. Pour chaque groupe :
   - Tâches marquées `[P]` (fichiers indépendants) : lance en parallèle, dans un seul message, au plus 4 sous-agents à la fois.
   - Autres tâches : une par une.
   - Pour chaque tâche : d'abord le sous-agent `test-writer` (RED confirmé par l'exécution), commit `test(<feature>): red - <Txxx>` ; puis le sous-agent `implementer` (GREEN), commit `feat(<feature>): green - <Txxx>`.
   - Les tâches de mise en place (Docker, configuration, squelette) n'ont pas de phase RED mais doivent laisser `make check` vert.
3. Coche chaque tâche terminée dans `tasks.md` (`- [x]`).
4. À la fin du groupe : sous-agent `reviewer`. Si `REJECTED`, relance `implementer` avec la raison (3 tentatives max), puis continue.
5. Quand toutes les tâches sont cochées et que `reviewer` répond `APPROVED`, écris `DONE` dans `specs/<feature>/.status`. Sinon écris `BLOCKED: <raison>` et arrête-toi.
Ne fais aucun résumé long : une ligne par groupe terminé.
