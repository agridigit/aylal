---
description: Construit AYLAL de bout en bout, sans intervention humaine — boucle Spec Kit test first sur toutes les fonctionnalités.
---
Tu es l'orchestrateur d'AYLAL. Tu travailles seul jusqu'au bout et tu ne me poses AUCUNE question.
Garde ton contexte minimal : tu ne lis jamais le code ni les specs en entier. Tu délègues tout aux sous-agents et tu ne consultes que les fichiers `.status`, `make check`, `make report` et git.

Périmètre : $ARGUMENTS si fourni (ex. « F0 F1 »), sinon toutes les lignes de prompts/features.tsv, dans l'ordre du fichier.

ÉTAPE 0 — une seule fois : si `.specify/memory/constitution.md` ne contient pas « Test first », lance le sous-agent `speckit-runner` avec l'étape `constitution` et, comme arguments, le contenu de prompts/00-constitution.md.

POUR CHAQUE FONCTIONNALITÉ (ID, SLUG, SECTION, TITRE) :
Numéro de branche : NNN = 1 + le plus grand préfixe à 3 chiffres parmi `git branch --list '[0-9][0-9][0-9]-*'` et `specs/` (001 si aucun). Branche = `NNN-<SLUG>` ; passe toujours `SPECIFY_FEATURE_DIRECTORY=specs/NNN-<SLUG>` et `GIT_BRANCH_NAME=NNN-<SLUG>` à `specify`.

A. Reprise : si une branche `*-<SLUG>` existe :
   - si elle est extraite dans `.worktrees/<branche>` (préparation anticipée) : attends la fin de son agent de préparation, vérifie `git -C .worktrees/<branche> status --porcelain` vide (sinon commit `spec(<ID>): prepare`), puis `git worktree remove .worktrees/<branche>` ;
   - place-toi dessus ; si son `specs/<branche>/.status` commence par MERGED, passe à la suivante ;
   - si `main` n'est pas ancêtre de la branche : `git merge main --no-edit -m "merge(<ID>): main into <branche>"` (récupère les fonctionnalités fusionnées depuis la préparation).
B. Sur `main`, si la branche n'existe pas : `speckit-runner` étape `specify`, avec les arguments de prompts/specify-F0.tpl pour F0, sinon prompts/specify.tpl où tu remplaces {ID} {TITRE} {SECTION} {SLUG}.
C. Lance successivement `speckit-runner`, en sautant toute étape dont le fichier de sortie existe déjà :
   - `clarify` avec prompts/clarify.txt (sortie : plus aucun [NEEDS CLARIFICATION] dans spec.md) ;
   - `plan` avec prompts/plan.txt (sortie : plan.md) ;
   - `tasks` avec prompts/tasks.txt (sortie : tasks.md) ;
   - `analyze` avec prompts/analyze.txt.
   `plan`, `tasks` et `analyze` dépendent du code existant : ils ne tournent JAMAIS en anticipation, toujours ici, après la fusion de la fonctionnalité précédente.
C'. Préparation anticipée (en parallèle de D) : si la fonctionnalité SUIVANTE du périmètre n'a pas de branche :
   `git worktree add -b NNN-<SLUG> .worktrees/NNN-<SLUG> main`, puis lance en ARRIÈRE-PLAN `speckit-runner` étape `specify` (mêmes arguments qu'en B) puis, à son retour, étape `clarify`.
   Dans le prompt de chaque agent : « Répertoire de travail : <chemin absolu>/.worktrees/NNN-<SLUG> — fais `cd` dedans pour toute commande et n'en sors jamais ; la branche existe déjà : ne crée ni ne change de branche ; ne lance ni Docker ni make. »
   Ne l'attends pas : continue D. Une seule préparation anticipée à la fois.D. Implémentation test first : exécute toi-même /aylal.tdd-implement <branche>. Cette commande délègue à test-writer, implementer et reviewer, en parallèle pour les tâches [P]. Répète jusqu'à ce que `.status` vaille DONE, 4 tours au maximum.
E. Contrôle + documentation EN PARALLÈLE, dans un seul message :
   - lance en arrière-plan `doc-engineer` et `doc-farmer` pour <branche> (ils écrivent seulement dans `docs/modules/<branche>/`, sans commit, sans `make`) ;
   - lance toi-même `make check-cached` (saute la vérification si le même commit est déjà vert, par exemple après le `reviewer`).
   Rouge : attends la fin des agents de documentation avant tout commit ; si l'échec ne porte que sur `diagrams` pendant que la doc s'écrivait, relance simplement `make check-cached`. Sinon un tour supplémentaire de /aylal.tdd-implement avec la sortie d'erreur ; toujours rouge, écris la raison dans `.aylal/blocked.md`, laisse la branche telle quelle et passe à la fonctionnalité suivante.
F. Fin de la documentation : quand les deux agents ont répondu, exécute les étapes 3 à 5 de /aylal.docs <branche> (`make diagrams`, vérification des images, commit `docs(<branche>): …`, `DOCS_DONE` dans `.status`), puis `make check-cached` (seules les docs ont changé : ne rend que les diagrammes).
G. Fusion : exécute /aylal.release <branche> <ID> (sous-agent git-keeper : SemVer, CHANGELOG, fusion locale, balises). Si la réponse commence par ÉCHEC, note-la dans `.aylal/blocked.md` et passe à la suivante.
H. Affiche une ligne : `<ID> fusionné — tâches x/y — docs OK`.

FIN : `make docs-index`, `make report`, puis un résumé de 10 lignes au plus : fonctionnalités fusionnées, bloquées (avec la raison), prochaines actions.

Règles : git local uniquement ; les dossiers `.worktrees/` servent uniquement à la préparation des specs ; aucun push (ni fetch, pull, remote, gh) ; jamais de modèle opus ; une étape qui échoue est relancée une fois, puis signalée dans `.aylal/blocked.md`, sans jamais arrêter la boucle.