# Spécification de fonctionnalité : F0 — Fondations techniques d'AYLAL

**Branche** : `001-foundations`
**Créé le** : 2026-11-07
**Statut** : Brouillon
**Entrée** : Fonctionnalité F0, préalable à toutes les autres. Sources : `docs/cps/AYLAL-CPS.md` sections 15, 16, 17, 18 (phase 0) et `CLAUDE.md`.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Le développeur lance toute la plateforme et tous les tests avec Docker (Priorité : P1)

Un développeur qui arrive sur le dépôt, avec pour seul prérequis Docker, démarre toute la plateforme (API, tâches de fond, base de données, synchronisation, stockage) avec `make up` et exécute l'ensemble des vérifications avec `make check`. Rien n'est installé sur sa machine.

**Pourquoi cette priorité** : sans environnement reproductible, aucune autre fonctionnalité ne peut être construite ni testée de façon fiable (principe 8, « Testé avant livré »).

**Test indépendant** : sur une machine vierge disposant seulement de Docker, `make up` puis `make check` se terminent avec succès.

**Scénarios d'acceptation** :

1. **Étant donné** une machine disposant uniquement de Docker, **Quand** le développeur lance `make up`, **Alors** tous les services de la plateforme démarrent et chacun signale qu'il est en bonne santé.
2. **Étant donné** la plateforme démarrée, **Quand** le développeur lance `make check`, **Alors** tous les tests (domaine, API, mobile, bout en bout) et les contrôles de qualité s'exécutent dans des conteneurs et le résultat global est un succès ou un échec explicite.
3. **Étant donné** un test volontairement en échec, **Quand** `make check` est lancé, **Alors** la commande se termine en échec et indique quel test a échoué.
4. **Étant donné** un dépôt fraîchement cloné, **Quand** on cherche une dépendance installée sur l'hôte, **Alors** aucune n'est nécessaire hormis Docker.

---

### Récit 2 — L'application mobile démarre et accueille l'agriculteur dans sa langue (Priorité : P1)

L'agriculteur ouvre l'application AYLAL et voit un écran d'accueil en darija, en arabe standard (mise en page RTL complète) ou en français, au choix. L'écran a les quatre états conçus : chargement, vide, erreur, hors ligne.

**Pourquoi cette priorité** : c'est la première preuve que le socle (application, langues, RTL, design) fonctionne de bout en bout sur le terrain cible.

**Test indépendant** : lancer l'application sur un Android d'entrée de gamme (2 Go de RAM), basculer entre les trois langues et vérifier l'écran d'accueil et ses quatre états.

**Scénarios d'acceptation** :

1. **Étant donné** l'application installée, **Quand** l'agriculteur l'ouvre, **Alors** l'écran d'accueil AYLAL s'affiche en moins de 3 secondes.
2. **Étant donné** l'écran d'accueil, **Quand** la langue est la darija, l'arabe ou le français, **Alors** tous les textes s'affichent dans cette langue, sans aucun texte en dur ni clé manquante.
3. **Étant donné** la langue arabe ou darija en graphie arabe, **Quand** l'écran s'affiche, **Alors** la mise en page est en miroir complet (sens de lecture, icônes directionnelles, alignements).
4. **Étant donné** l'écran d'accueil, **Quand** les données sont en cours de chargement, vides, en erreur ou que le réseau est absent, **Alors** un état dédié et lisible est affiché (squelette, illustration avec action, message avec solution, indicateur hors ligne), jamais un écran blanc.
5. **Étant donné** n'importe quel bouton, **Quand** on mesure sa zone tactile, **Alors** elle fait au moins 48 dp.

---

### Récit 3 — Une donnée créée hors ligne est synchronisée sans perte (Priorité : P1)

L'agriculteur saisit une donnée sans réseau. Elle est conservée sur le téléphone, un indicateur montre qu'elle n'est pas encore envoyée, et elle rejoint le serveur sans perte dès que le réseau revient. Le même modèle de données et les mêmes règles sont partagés par tous les fronts.

**Pourquoi cette priorité** : « hors ligne par défaut » et « aucune donnée perdue » sont des principes non négociables (principe 2).

**Test indépendant** : créer des données en mode avion, les modifier, rétablir le réseau, comparer les données du téléphone et du serveur.

**Scénarios d'acceptation** :

1. **Étant donné** un téléphone sans réseau, **Quand** l'agriculteur crée une donnée d'essai, **Alors** elle est enregistrée localement et marquée « non envoyée ».
2. **Étant donné** des données en attente d'envoi, **Quand** le réseau revient, **Alors** elles sont envoyées au serveur automatiquement, sans action de l'utilisateur, et l'indicateur « non envoyé » disparaît.
3. **Étant donné** un téléphone resté 30 jours simulés hors ligne avec des créations et des modifications, **Quand** le réseau revient, **Alors** zéro donnée n'est perdue ou dupliquée.
4. **Étant donné** une même donnée modifiée hors ligne sur deux appareils, **Quand** les deux se synchronisent, **Alors** le conflit est résolu selon une règle documentée et déterministe, et aucune des deux modifications n'est perdue silencieusement.
5. **Étant donné** une règle métier d'essai (par exemple une validation de saisie), **Quand** elle est évaluée côté mobile et côté serveur, **Alors** les deux donnent le même résultat car elles reposent sur la même définition.
6. **Étant donné** des données stockées sur le téléphone ou transmises, **Quand** on les inspecte, **Alors** elles sont chiffrées au repos et en transit.

---

### Récit 4 — Le design system est visible dans un catalogue de composants (Priorité : P1)

L'équipe consulte un catalogue vivant qui présente les jetons de design (couleurs, typographies IBM Plex Sans et IBM Plex Sans Arabic, espacements sur grille de 4 px, rayons, ombres, états) et chaque composant avec ses variantes, dans les thèmes clair, sombre et plein soleil, en LTR et en RTL.

**Pourquoi cette priorité** : le CPS exige un design system complet avant le premier écran (principe 10) ; il est la source unique des composants.

**Test indépendant** : ouvrir le catalogue, parcourir chaque composant dans chaque thème et chaque sens de lecture.

**Scénarios d'acceptation** :

1. **Étant donné** le catalogue ouvert, **Quand** on choisit un thème (clair, sombre, plein soleil), **Alors** tous les composants adoptent ce thème sans élément illisible.
2. **Étant donné** le thème plein soleil, **Quand** on mesure les contrastes texte/fond, **Alors** ils respectent un ratio élevé fixé par le design system (au moins 7:1 pour le texte courant).
3. **Étant donné** un composant du catalogue, **Quand** on l'affiche, **Alors** toutes ses variantes et tous ses états (par défaut, actif, désactivé, chargement, erreur) sont présentés et documentés.
4. **Étant donné** le catalogue, **Quand** on bascule en RTL, **Alors** chaque composant est en miroir correct.
5. **Étant donné** un changement visuel involontaire d'un composant, **Quand** les tests de captures d'écran de référence sont lancés, **Alors** la régression est détectée et signalée.
6. **Étant donné** l'option système « réduire les animations », **Quand** elle est active, **Alors** les transitions de 200 à 300 ms sont supprimées ou réduites.

---

### Récit 5 — Les diagrammes se génèrent avec `make diagrams` (Priorité : P2)

Un développeur ou rédacteur écrit des diagrammes en code Mermaid et obtient leurs rendus SVG et PNG avec `make diagrams`, pour les intégrer à la documentation de chaque fonctionnalité.

**Pourquoi cette priorité** : la documentation par fonctionnalité en dépend, mais elle ne bloque pas le socle exécutable.

**Test indépendant** : placer un diagramme valide et un diagramme invalide, lancer `make diagrams`.

**Scénarios d'acceptation** :

1. **Étant donné** des fichiers `.mmd` dans le dossier de diagrammes d'un module, **Quand** `make diagrams` est lancé, **Alors** un SVG et un PNG sont produits pour chacun dans le dossier d'images du module.
2. **Étant donné** un diagramme à la syntaxe invalide, **Quand** `make diagrams` est lancé, **Alors** la commande échoue en nommant le fichier fautif.
3. **Étant donné** un rendu déjà à jour, **Quand** `make diagrams` est relancé, **Alors** le résultat est identique (reproductible).

---

### Récit 6 — Le prototype de validation confirme les seuils sur un Android d'entrée de gamme (Priorité : P2)

Un prototype couvre : une carte de 50 parcelles, une saisie hors ligne puis synchronisée, et un écran du design system animé. Il est mesuré sur un vrai Android d'entrée de gamme (2 Go de RAM) pour valider ou réexaminer les choix techniques.

**Pourquoi cette priorité** : il tranche le risque principal de la phase 0, mais le socle logiciel des récits 1 à 4 peut exister sans lui.

**Test indépendant** : exécuter le protocole de mesure sur l'appareil de référence et consigner les résultats.

**Scénarios d'acceptation** :

1. **Étant donné** l'appareil de référence, **Quand** on lance l'application à froid, **Alors** le démarrage prend moins de 3 secondes.
2. **Étant donné** une carte de 50 parcelles en cache local, **Quand** on l'ouvre, **Alors** elle s'affiche en moins de 2 secondes.
3. **Étant donné** l'écran animé du design system, **Quand** on le fait défiler et animer, **Alors** le rythme reste de 60 images par seconde.
4. **Étant donné** un seuil non tenu, **Quand** le rapport est établi, **Alors** il le signale et déclenche le réexamen du choix technique correspondant.

---

### Cas limites

- Le réseau coupe en plein envoi : l'envoi reprend sans doublon ni perte.
- Le stockage du téléphone est presque plein : l'utilisateur est averti avant toute perte de saisie.
- La langue de l'appareil n'est pas l'une des trois langues prises en charge : repli sur le français, changement possible à tout moment.
- Une clé de traduction manque dans une langue : le test de langues échoue avant livraison, aucun texte vide n'est affiché.
- Un conteneur du socle tombe ou démarre dans le mauvais ordre : `make up` le signale clairement et les autres services attendent sa disponibilité.
- Horloge du téléphone décalée pendant 30 jours hors ligne : la résolution des conflits n'en dépend pas de façon à perdre des données.
- Texte long (français) ou court (arabe) dans un composant : pas de débordement ni de troncature illisible.
- Perte ou changement de téléphone avant synchronisation : l'état « non envoyé » reste visible tant que la donnée n'a pas atteint le serveur.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

**Environnement et qualité**

- **FR-001** : Toute la plateforme (API, tâches de fond, base de données, synchronisation, stockage, tests, rendu des diagrammes) MUST s'exécuter dans des conteneurs, sans autre prérequis sur l'hôte que Docker.
- **FR-002** : La commande `make up` MUST démarrer tous les services et attendre qu'ils soient en bonne santé ; `make down` MUST les arrêter.
- **FR-003** : La commande `make check` MUST exécuter tous les tests et contrôles de qualité et retourner un code d'échec si l'un d'eux échoue ; `make test`, `make test-api`, `make test-mobile` et `make e2e` MUST exister pour les sous-ensembles.
- **FR-004** : Le système MUST mesurer la couverture du code métier et faire échouer `make check` sous 80 %.
- **FR-005** : Le dépôt MUST être organisé en espaces distincts pour mobile, web, desktop, règles métier partagées, composants d'interface, traductions, API et tâches de fond, tel que décrit en section 16 du CPS ; les espaces web et desktop peuvent n'être que des squelettes en phase 0.

**Application mobile, langues et accessibilité**

- **FR-006** : L'application mobile MUST démarrer et afficher un écran d'accueil AYLAL.
- **FR-007** : L'application MUST proposer la darija (graphies arabe et latine), l'arabe standard et le français, et permettre de changer de langue à tout moment ; aucun texte d'interface ne doit être en dur.
- **FR-008** : En arabe et en darija en graphie arabe, la mise en page MUST être en miroir RTL complet.
- **FR-009** : Chaque écran MUST concevoir les quatre états : chargement, vide, erreur, hors ligne.
- **FR-010** : Chaque élément interactif MUST avoir une zone tactile d'au moins 48 dp.
- **FR-011** : L'écran d'accueil MUST proposer la lecture vocale de son contenu dans la langue choisie.

**Hors ligne et synchronisation**

- **FR-012** : Toute saisie et toute consultation de données déjà chargées MUST fonctionner sans réseau pendant au moins 30 jours.
- **FR-013** : Le système MUST synchroniser automatiquement les données locales avec le serveur au retour du réseau, sans perte et sans doublon.
- **FR-014** : L'application MUST indiquer clairement quelles données ne sont pas encore envoyées.
- **FR-015** : Les conflits de modification MUST être résolus par une règle documentée, déterministe et sans perte silencieuse.
- **FR-016** : Le modèle de données et les règles de validation MUST être définis une seule fois et partagés par le mobile et le serveur ; aucune règle métier ne peut vivre uniquement dans un écran.

**Sécurité et vie privée**

- **FR-017** : Les données MUST être chiffrées en transit et au repos, y compris sur le téléphone.
- **FR-018** : Le serveur MUST appliquer le contrôle d'accès par ferme et par rôle sur toute donnée synchronisée.
- **FR-019** : Les environnements, jeux de données et services du socle MUST respecter l'exigence d'hébergement et de traitement des données au Maroc (aucune dépendance obligatoire à un service hors Maroc pour les données des utilisateurs).
- **FR-020** : La télémétrie MUST être anonyme et désactivable.

**Design system**

- **FR-021** : Le design system MUST définir les jetons de couleurs en trois thèmes (clair, sombre, plein soleil à fort contraste), la typographie IBM Plex Sans et IBM Plex Sans Arabic, une échelle d'espacement sur grille de 4 px, les rayons, les ombres et les états.
- **FR-022** : Un catalogue de composants consultable MUST présenter chaque composant avec ses variantes, ses états, ses thèmes et ses deux sens de lecture, et être la source unique des composants.
- **FR-023** : Des captures d'écran de référence automatisées MUST détecter toute régression visuelle des composants.
- **FR-024** : Les transitions MUST durer de 200 à 300 ms et respecter le réglage système « réduire les animations ».

**Documentation**

- **FR-025** : `make diagrams` MUST produire un SVG et un PNG pour chaque diagramme Mermaid (`flowchart`, `sequenceDiagram`, `erDiagram`, `stateDiagram-v2`) et échouer en nommant tout diagramme invalide.
- **FR-026** : La documentation de F0 MUST suivre le gabarit de `docs/modules/<NNN-feature>/` (document ingénieur, guides agriculteur en français et en arabe, diagrammes avec rendu et code source).

**Prototype de validation**

- **FR-027** : Un prototype MUST permettre de mesurer, sur un Android d'entrée de gamme de 2 Go de RAM, le démarrage, l'affichage de 50 parcelles avec vigueur, une saisie hors ligne suivie d'une synchronisation, et la fluidité d'un écran animé du design system.
- **FR-028** : Les résultats de mesure MUST être consignés dans un rapport comparant chaque résultat au seuil de la section 15 du CPS.

### Entités clés

- **Ferme** : unité propriétaire des données et du contrôle d'accès ; regroupe des parcelles et des membres.
- **Parcelle** : zone cultivée d'une ferme, avec contour géographique ; sert à la carte de 50 parcelles du prototype.
- **Enregistrement d'essai** : donnée simple créée par l'utilisateur, avec identifiant stable, auteur, ferme, date de modification et état de synchronisation (en attente, envoyé, en conflit).
- **État de synchronisation** : suivi, par donnée, de ce qui est local, en attente ou confirmé par le serveur.
- **Jeton de design** : valeur nommée (couleur, espacement, rayon, ombre, typographie) variable selon le thème.
- **Composant** : élément d'interface documenté avec variantes, états et thèmes.
- **Clé de traduction** : texte d'interface identifié, avec une valeur en darija, en arabe et en français.
- **Rapport de mesure** : résultat daté d'un seuil mesuré (valeur, seuil, appareil, verdict).

## Critères de réussite *(obligatoire)*

### Résultats mesurables

- **SC-001** : Un nouveau développeur disposant uniquement de Docker obtient une plateforme fonctionnelle avec une seule commande (`make up`) et un résultat de tests complet avec une seule commande (`make check`), sans installer d'outil sur sa machine.
- **SC-002** : L'application démarre en moins de 3 secondes sur un Android d'entrée de gamme de 2 Go de RAM.
- **SC-003** : Un écran affiché depuis les données locales prend moins de 2 secondes ; l'application installée pèse moins de 40 Mo.
- **SC-004** : 100 % des textes de l'écran d'accueil et du catalogue existent dans les trois langues ; 0 texte en dur.
- **SC-005** : Après 30 jours simulés hors ligne, 100 % des données créées ou modifiées sont retrouvées sur le serveur à la reconnexion : 0 perte, 0 doublon, sur au moins 1 000 enregistrements d'essai.
- **SC-006** : Le trafic de données mobiles d'une session type du prototype reste sous 5 Mo par jour d'usage.
- **SC-007** : Tous les composants du catalogue sont validés dans les 3 thèmes et les 2 sens de lecture ; 0 régression visuelle non revue au moment de la fusion.
- **SC-008** : Les animations tiennent 60 images par seconde sur l'appareil de référence.
- **SC-009** : Chaque critère d'acceptation P1 de cette spécification est couvert par au moins un test automatisé, et la couverture du code métier atteint au moins 80 %.
- **SC-010** : `make diagrams` produit 100 % des rendus attendus (SVG et PNG) en moins de 2 minutes pour un module standard.
- **SC-011** : Le rapport du prototype indique, pour chaque seuil de la section 15 testé, un verdict « tenu » ou « non tenu » ; tout « non tenu » ouvre un réexamen du choix technique.

## Hypothèses

- Les choix techniques détaillés (Expo, PowerSync, FastAPI, PostgreSQL, Unistyles, Storybook, etc.) sont déjà arrêtés en sections 16 et 19 du CPS et sont repris dans le plan, pas dans cette spécification.
- F0 ne contient aucune fonctionnalité métier agricole (comptes, parcelles réelles, irrigation, etc.) ; les « données d'essai » et les « parcelles » du prototype servent uniquement à valider le socle.
- L'authentification par téléphone et code à usage unique est livrée par F1 ; en F0, un compte d'essai suffit pour valider le contrôle d'accès par ferme et par rôle.
- Android 9 et plus est la seule cible de F0 ; iOS, web et desktop sont des squelettes ou reportés (phases 2 et 3).
- Le choix final de l'hébergeur au Maroc est pris avant la fin de la phase 0 ; F0 garantit seulement l'absence de dépendance obligatoire hors Maroc pour les données des utilisateurs.
- Les maquettes haute fidélité des écrans P1 et leur test avec 5 agriculteurs relèvent de la phase 0 mais d'un travail de design séparé ; F0 livre le design system et le catalogue qui les accueilleront.
- La relecture des textes par un locuteur natif de la darija est planifiée ; en F0, les textes sont provisoires mais complets dans les trois langues.
- Un Android d'entrée de gamme de 2 Go de RAM est disponible pour les mesures du prototype.
- La lecture vocale s'appuie sur les capacités de synthèse vocale de l'appareil en F0 ; les modèles vocaux darija hébergés au Maroc relèvent de F7.
