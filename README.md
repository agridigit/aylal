# AYLAL — kit d'implémentation Spec Kit + Claude Code

Ce kit transforme le CPS (`docs/cps/AYLAL-CPS.md`) en application, fonctionnalité par fonctionnalité, sans intervention : Spec Kit en boucle, test first obligatoire, sous-agents en parallèle sur des modèles économes, tout dans Docker, et deux documentations (ingénieur + agriculteur) avec diagrammes Mermaid rendus en images à la fin de chaque module.

## Contenu

| Élément | Rôle |
| --- | --- |
| `CLAUDE.md` | Règles permanentes : test first, Docker, architecture, documentation, économie de tokens |
| `.claude/agents/` | 5 sous-agents : `test-writer` (sonnet), `implementer` (sonnet), `reviewer` (haiku), `doc-engineer` (sonnet), `doc-farmer` (haiku) |
| `.claude/commands/aylal.tdd-implement.md` | Remplace `/speckit.implement` : RED → GREEN → REFACTOR, tâches `[P]` en parallèle (4 agents max) |
| `.claude/commands/aylal.docs.md` | Documentation de fin de module, deux agents en parallèle, rendu des diagrammes |
| `.claude/settings.json` | Permissions : tout ce qui est utile est autorisé, `git push`, `sudo`, `curl` et `.env` sont interdits |
| `prompts/` | Constitution, liste ordonnée des fonctionnalités, prompts de chaque étape Spec Kit |
| `scripts/speckit-loop.sh` | La boucle autonome |
| `docker-compose.yml`, `Makefile`, `.env.example` | Socle Docker (complété par F0) |
| `docs/templates/` | Gabarits des documents et thème Mermaid AYLAL |

## 1. Installation (une fois)

```bash
unzip aylal-speckit-kit.zip && cd aylal
bash scripts/bootstrap.sh      # vérifie git, docker, node, claude ; installe uv + specify ; specify init --here --ai claude
claude                         # une première fois en interactif pour vous connecter, puis /exit
```

## 2. Lancement autonome

```bash
make loop                                  # toutes les fonctionnalités : F0 F1 F2 F6 F3 F4 F5 F7 F8 F9
scripts/speckit-loop.sh F0                 # seulement les fondations (recommandé pour démarrer)
scripts/speckit-loop.sh F1 F2              # une sélection
ONLY_STEP=implement scripts/speckit-loop.sh F3   # reprendre une étape : specify|clarify|plan|tasks|analyze|implement|docs
make report                                # avancement : statut, tâches cochées, docs présentes
```

Pour une nuit entière sans surveillance, lancez-le dans `tmux` ou `screen`. La boucle est reprenable : relancée, elle saute ce qui est fusionné et reprend la branche en cours.

Variables utiles : `MODEL=sonnet` (défaut), `LIGHT_MODEL=haiku`, `MAX_IMPL_ROUNDS=4`, `BUDGET_USD=5` (plafond par session si votre version de Claude Code propose `--max-budget-usd`), `PARALLEL_DOCS=1`, `YOLO=1` (saute toutes les permissions — uniquement dans un conteneur jetable).

## 3. Ce que fait la boucle pour chaque fonctionnalité

1. `/speckit.specify` avec le prompt de `prompts/specify.tpl` (crée la branche `NNN-slug`).
2. `/speckit.clarify` en mode autonome (haiku) : l'agent répond lui-même à partir du CPS et des décisions de la section 19.
3. `/speckit.plan` avec la stack imposée (`prompts/plan.txt`).
4. `/speckit.tasks` en test first strict (`prompts/tasks.txt`) : tests avant code, `[P]` pour le parallèle.
5. `/speckit.analyze` (haiku) + auto-correction des incohérences graves.
6. `/aylal.tdd-implement` en boucle jusqu'à `DONE` (4 tours max) : pour chaque tâche, `test-writer` prouve le RED, `implementer` passe au GREEN, `reviewer` valide ; commits séparés `test(...)` puis `feat(...)`.
7. `make check` (lint, typage, tests, couverture ≥ 80 %, diagrammes) doit être vert.
8. `/aylal.docs` dans un worktree séparé, en arrière-plan, pendant que la fonctionnalité suivante démarre.
9. Fusion dans `main` et tag `aylal-Fx`. Les docs sont fusionnées à la fin.

Chaque étape est une session `claude -p` neuve : le contexte ne grossit pas, l'état passe par les fichiers `specs/` et git. C'est le principal levier d'économie de tokens, avec sonnet par défaut, haiku pour les étapes légères et aucun opus.

## 4. Mode manuel (mêmes prompts, dans `claude` interactif)

```text
/speckit.constitution <contenu de prompts/00-constitution.md>
/speckit.specify <contenu de prompts/specify-F0.tpl>
/speckit.clarify <contenu de prompts/clarify.txt>
/speckit.plan <contenu de prompts/plan.txt>
/speckit.tasks <contenu de prompts/tasks.txt>
/speckit.analyze <contenu de prompts/analyze.txt>
/aylal.tdd-implement 001-foundations
/aylal.docs 001-foundations
```

Pour les fonctionnalités suivantes, remplacez dans `prompts/specify.tpl` : `{ID}`, `{TITRE}`, `{SECTION}`, `{SLUG}` par la ligne correspondante de `prompts/features.tsv`.

## 5. Documentation produite

```text
docs/
  README.md                       index (make docs-index)
  cps/AYLAL-CPS.md                cahier des charges
  modules/001-foundations/
    ingenieur.md                  document expert ingénieur logiciel
    agriculteur.fr.md             guide agriculteur (français)
    agriculteur.ar.md             guide agriculteur (arabe)
    diagrams/*.mmd                diagrammes en code (flowchart, sequence, er, state)
    img/*.svg, img/*.png          rendus par make diagrams (Mermaid CLI dans Docker)
```

Chaque document affiche l'image du diagramme, suivie de son code source Mermaid.

## 6. Points d'attention

- La reconnaissance vocale darija et le diagnostic photo nécessitent des modèles et des données : la boucle produit le code et les interfaces, avec des tests sur des jeux d'essai ; les bancs d'essai réels (section 19 du CPS) restent à mener.
- L'E2E mobile (émulateur Android + Maestro dans Docker) est défini par F0 ; s'il est trop lourd pour votre machine, la porte de qualité `make check` reste valable sans lui.
- Surveillez les premiers tours de F0 (`tail -f .aylal/logs/*`) avant de laisser la boucle tourner seule toute une nuit.
