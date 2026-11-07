# Constitution AYLAL

Source fonctionnelle : `docs/cps/AYLAL-CPS.md`. Toute spécification ou tout plan qui contredit un article ci-dessous est refusé.

## Principes non négociables (CPS section 4)

### I. L'agriculteur d'abord
Chaque écran doit être utilisable par un agriculteur qui lit peu : icônes, photos, voix, trois langues, un seul objectif par écran.

### II. Hors ligne par défaut
Toute saisie et toute consultation des données déjà chargées fonctionnent sans réseau ; la synchronisation est invisible et ne perd jamais une donnée.

### III. Gratuit et sobre
Aucune fonction de suivi n'est payante pour l'agriculteur ; chaque fonctionnalité justifie son coût d'exploitation par utilisateur.

### IV. Ses données lui appartiennent
Rien n'est partagé sans accord explicite et révocable ; export et suppression complets à la demande ; conformité à la loi 09-08.

### V. Conseil prudent et traçable
Toute recommandation (IA ou règle) indique sa source, son niveau de confiance et ses limites ; aucun produit phyto non homologué au Maroc pour l'usage n'est jamais proposé.

### VI. Une seule logique métier, plusieurs fronts
Mobile, web et desktop partagent le même modèle de données et les mêmes règles ; aucune règle métier n'est codée uniquement dans une interface.

### VII. Petits téléphones, petits forfaits
Performances et consommation de données mesurées sur un Android d'entrée de gamme et une connexion 3G.

### VIII. Testé avant livré
Chaque récit P1 a des tests automatisés de ses critères d'acceptation ; chaque version mobile est testée sur le terrain avec au moins 5 agriculteurs.

### IX. Code et types en anglais, interface traduite
Aucun texte d'interface en dur dans le code.

### X. Design extrêmement soigné
AYLAL vise le niveau des meilleures applications grand public : aucun écran n'est développé sans maquette haute fidélité validée, et aucun écran n'est livré sans revue design (article XV).

## Articles complémentaires

### XI. Test first (NON NÉGOCIABLE)
- Aucune ligne de code de production sans un test qui échoue d'abord : RED, puis GREEN, puis REFACTOR.
- Chaque critère d'acceptation P1 (« Étant donné / Quand / Alors ») a au moins un test automatisé.
- Couverture du code métier >= 80 %.
- Interdit de modifier un test pour le faire passer ; seule exception, un test qui contredit la spec, noté dans `specs/<feature>/decisions.md`.

### XII. Tout dans Docker
Chaque service, chaque test et chaque outil (y compris le rendu des diagrammes) tourne dans Docker Compose. Aucun prérequis sur la machine hôte hormis Docker, git, et Node pour Claude Code.

### XIII. Hébergement au Maroc
Données et traitements (y compris IA : photos, audio, inférence) sont hébergés au Maroc. Aucun service tiers hors Maroc ne reçoit de donnée personnelle.

### XIV. Documentation de fin de module
Une fonctionnalité n'est terminée que si `docs/modules/<feature>/` contient `ingenieur.md`, `agriculteur.fr.md`, `agriculteur.ar.md`, des diagrammes Mermaid en code (`diagrams/*.mmd`) et leurs images rendues (`img/*.svg`, `img/*.png`) intégrées dans les documents avec le bloc de code source.

### XV. Seuils de qualité (CPS section 15)
Ces seuils sont les critères de recette de toute fonctionnalité.

| Domaine | Exigence mesurable |
| --- | --- |
| Appareils | Android 9 et plus ; fluide sur un téléphone de 2 Go de RAM ; iOS 15 et plus en phase 2 |
| Taille et données | Application installée < 40 Mo ; usage quotidien type < 5 Mo de données mobiles ; images satellite téléchargées seulement en Wi-Fi ou à la demande |
| Performance | Démarrage < 3 s ; tableau de bord affiché < 2 s depuis le cache local ; enregistrement d'une opération < 15 s pour un utilisateur entraîné |
| Hors ligne | Saisie et consultation sans réseau pendant au moins 30 jours ; zéro perte de donnée à la synchronisation ; indicateur clair de ce qui n'est pas encore envoyé |
| Langues | Darija (graphie arabe et latine), arabe standard (RTL complet), français ; amazighe envisagé en phase 3 ; lecture vocale de chaque écran |
| Accessibilité | Boutons d'au moins 48 dp ; contraste lisible en plein soleil ; tout parcours principal réalisable sans lire (icônes + voix) |
| Sécurité | Authentification par téléphone et code à usage unique ; données chiffrées en transit et au repos, y compris sur le téléphone ; contrôle d'accès par ferme et par rôle côté serveur |
| Vie privée | Loi 09-08 et déclaration CNDP ; hébergement et traitement de toutes les données au Maroc, y compris photos, audio et inférence IA ; export complet et suppression sur demande |
| Disponibilité | 99,5 % mensuel pour l'API ; sauvegardes quotidiennes, rétention 30 jours |
| Coût | Coût d'infrastructure cible < 1 MAD par utilisateur actif et par mois, suivi chaque mois |
| Qualité | Tests automatisés des critères d'acceptation P1 ; taux de plantage < 0,5 % des sessions ; télémétrie anonyme et désactivable |

**Exigences de design** (direction artistique : calme, chaleureuse, ancrée dans la terre marocaine ; olivier, terre, eau ; pas d'esthétique « tableau de bord industriel »).

| Domaine | Exigence |
| --- | --- |
| Design system | Complet avant le premier écran : couleurs (clair, sombre, plein soleil à fort contraste), typographie IBM Plex Sans et IBM Plex Sans Arabic, espacement sur grille de 4 px, rayons, ombres, états ; chaque composant documenté avec ses variantes |
| Iconographie | Icônes sur mesure (cultures, opérations, météo, alertes) ; illustrations de cultures cohérentes ; photos réelles pour maladies et ravageurs |
| Bilingue et RTL | Miroir RTL parfait en arabe (mise en page, icônes directionnelles, graphiques) ; chaque écran maquetté en arabe et en français ; textes longs et courts testés |
| Mouvement | Transitions de 200 à 300 ms, micro-interactions et retour haptique sur les actions clés ; respect de « réduire les animations » ; 60 images/s sur Android d'entrée de gamme |
| États | Quatre états conçus par écran : chargement (squelettes), vide (illustration + action), erreur (message clair + solution), hors ligne |
| Cartes et graphiques | Palettes lisibles par les daltoniens, légendes en mots simples, un seul message par graphique |
| Voix et ton | Textes courts, tutoiement ou vouvoiement fixé par langue, vocabulaire de l'agriculteur ; relecture par un locuteur natif de la darija |

Processus de qualité design : (1) maquettes haute fidélité de chaque écran P1 en arabe et français validées avant développement ; (2) prototype testé avec au moins 5 agriculteurs, 4 sur 5 réussissent la tâche principale sans aide ; (3) catalogue de composants vivant, source unique ; (4) revue design de chaque écran implémenté face à la maquette avant fusion ; (5) captures de référence automatisées contre les régressions visuelles.

## Gouvernance

La constitution prime sur tout autre document (CPS, spec, plan, tâches). Tout écart doit être justifié dans `specs/<feature>/decisions.md`. Un amendement exige une mise à jour de version (semver : MAJOR pour suppression ou redéfinition d'un article, MINOR pour ajout, PATCH pour clarification) et la vérification de la cohérence des modèles dépendants.

**Version**: 1.0.0 | **Ratified**: 2026-11-07 | **Last Amended**: 2026-11-07
