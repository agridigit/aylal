---
description: Construit AYLAL de bout en bout, sans intervention humaine — boucle Spec Kit test first sur toutes les fonctionnalités.
---
Tu es l'orchestrateur d'AYLAL. Tu travailles seul jusqu'au bout et tu ne me poses AUCUNE question.
Garde ton contexte minimal : tu ne lis jamais le code ni les specs en entier. Tu délègues tout aux sous-agents et tu ne consultes que les fichiers `.status`, `make check`, `make report` et git.

Périmètre : $ARGUMENTS si fourni (ex. « F0 F1 »), sinon toutes les lignes de prompts/features.tsv, dans l'ordre du fichier.

ÉTAPE 0 — une seule fois : si `.specify/memory/constitution.md` ne contient pas « Test first », lance le sous-agent `speckit-runner` avec l'étape `constitution` et, comme arguments, le contenu de prompts/00-constitution.md.

POUR CHAQUE FONCTIONNALITÉ (ID, SLUG, SECTION, TITRE) :
A. Reprise : si une branche `*-<SLUG>` existe, place-toi dessus. Si son `specs/<branche>/.status` commence par MERGED, passe à la suivante.
B. Sur `main`, si la branche n'existe pas : `speckit-runner` étape `specify`, avec les arguments de prompts/specify-F0.tpl pour F0, sinon prompts/specify.tpl où tu remplaces {ID} {TITRE} {SECTION} {SLUG}.
C. Lance successivement `speckit-runner`, en sautant toute étape dont le fichier de sortie existe déjà :
   - `clarify` avec prompts/clarify.txt (sortie : plus aucun [NEEDS CLARIFICATION] dans spec.md) ;
   - `plan` avec prompts/plan.txt (sortie : plan.md) ;
   - `tasks` avec prompts/tasks.txt (sortie : tasks.md) ;
   - `analyze` avec prompts/analyze.txt.
D. Implémentation test first : exécute toi-même /aylal.tdd-implement <branche>. Cette commande délègue à test-writer, implementer et reviewer, en parallèle pour les tâches [P]. Répète jusqu'à ce que `.status` vaille DONE, 4 tours au maximum.
E. Lance `make check`. S'il est rouge : un tour supplémentaire de /aylal.tdd-implement avec la sortie d'erreur ; toujours rouge, écris la raison dans `.aylal/blocked.md`, laisse la branche telle quelle et passe à la fonctionnalité suivante.
F. Documentation : exécute /aylal.docs <branche> (doc-engineer et doc-farmer en parallèle, diagrammes rendus).
G. Fusion : exécute /aylal.release <branche> <ID> (sous-agent git-keeper : SemVer, CHANGELOG, fusion locale, balises). Si la réponse commence par ÉCHEC, note-la dans `.aylal/blocked.md` et passe à la suivante.
H. Affiche une ligne : `<ID> fusionné — tâches x/y — docs OK`.

FIN : `make docs-index`, `make report`, puis un résumé de 10 lignes au plus : fonctionnalités fusionnées, bloquées (avec la raison), prochaines actions.

Règles : git local uniquement, aucun push (ni fetch, pull, remote, gh) ; jamais de modèle opus ; une étape qui échoue est relancée une fois, puis signalée dans `.aylal/blocked.md`, sans jamais arrêter la boucle.