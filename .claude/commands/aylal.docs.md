---
description: Génère la documentation de fin de module (document ingénieur, document métier, guide agriculteur FR/AR) avec diagrammes Mermaid rendus en images.
---
Fonctionnalité : $ARGUMENTS. Travaille sans poser de question.
1. Crée `docs/modules/<feature>/{diagrams,img}` si absent.
2. Lance en parallèle, dans un seul message, les sous-agents `doc-engineer`, `doc-business` et `doc-farmer` pour cette fonctionnalité.
3. Lance `make diagrams`, puis vérifie : chaque `.mmd` a son `.svg` et son `.png` dans `img/`, chaque image référencée dans les documents existe.
4. Ne modifie pas `docs/README.md` : l'index est régénéré par `make docs-index` (évite les conflits quand plusieurs docs sont produites en parallèle).
5. Commit `docs(<feature>): engineer, business and farmer documentation`. Écris `DOCS_DONE` dans `specs/<feature>/.status`.
