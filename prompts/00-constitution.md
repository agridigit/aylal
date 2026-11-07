Crée la constitution du projet AYLAL à partir de docs/cps/AYLAL-CPS.md : reprends les 10 principes de la section 4 comme articles non négociables, et ajoute ces articles :
- Article « Test first » : aucune ligne de code de production sans test qui échoue d'abord (RED -> GREEN -> REFACTOR) ; chaque critère d'acceptation P1 a un test automatisé ; couverture du code métier >= 80 % ; interdit de modifier un test pour le faire passer.
- Article « Tout dans Docker » : chaque service, chaque test et chaque outil (y compris le rendu des diagrammes) tourne dans Docker Compose ; aucun prérequis sur la machine hôte hormis Docker, git, Node pour Claude Code.
- Article « Hébergement au Maroc » : données et traitements (y compris IA) hébergés au Maroc ; aucun service tiers hors Maroc ne reçoit de donnée personnelle.
- Article « Documentation de fin de module » : une fonctionnalité n'est terminée que si docs/modules/<feature>/ contient ingenieur.md, agriculteur.fr.md, agriculteur.ar.md, des diagrammes Mermaid en code (.mmd) et leurs images rendues (.svg, .png) intégrées dans les documents.
- Article « Seuils de qualité » : reprends le tableau de la section 15 (exigences non fonctionnelles et exigences de design) comme critères de recette.
- Gouvernance : la constitution prime sur tout ; un écart doit être justifié dans specs/<feature>/decisions.md.
Version 1.0.0, date de ratification 2026-11-07. Ne pose aucune question.
