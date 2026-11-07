# Spécification de fonctionnalité : F2 — Parcelles et cultures

**Branche** : `003-fields-crops`
**Créé le** : 2026-11-07
**Statut** : Brouillon
**Entrée** : Fonctionnalité F2. Sources : `docs/cps/AYLAL-CPS.md` section 7 (contexte sections 1 à 3, données section 17). Dépend de F1 (compte, ferme). Base de F3 à F8.

## Objectif

L'agriculteur décrit sa ferme parcelle par parcelle : où elle est, ce qui y pousse, comment elle est irriguée. C'est la base de toutes les autres fonctions.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Dessiner une parcelle (Priorité : P1)

L'agriculteur dessine une parcelle en touchant ses coins sur l'image satellite, ou en faisant le tour à pied avec le GPS du téléphone.

**Pourquoi** : sans géométrie, aucune surface, imagerie ni météo par parcelle.
**Test indépendant** : créer une parcelle par chaque méthode, avec et sans réseau, et vérifier sa surface.

**Scénarios d'acceptation** :

1. **Étant donné** un agriculteur hors réseau, **Quand** il dessine une parcelle par GPS, **Alors** elle est enregistrée localement et synchronisée au retour du réseau.
2. **Étant donné** une parcelle dessinée, **Quand** elle est enregistrée, **Alors** sa surface en hectares s'affiche avec deux décimales.
3. **Étant donné** un dessin qui se croise lui-même, **Quand** l'agriculteur valide, **Alors** l'app le corrige ou lui demande de recommencer, avec une explication visuelle.
4. **Étant donné** un dessin par touches de coins sur l'image satellite, **Quand** l'agriculteur valide le contour, **Alors** la parcelle est créée avec la surface calculée.
5. **Étant donné** une surface calculée, **Quand** l'agriculteur saisit une surface déclarée différente, **Alors** les deux surfaces sont conservées et affichées distinctement.

---

### Récit 2 — Nommer la parcelle et choisir sa culture (Priorité : P1)

L'agriculteur donne un nom à la parcelle, choisit sa culture dans une liste illustrée (photos), sa variété s'il la connaît, et l'année de plantation ou la date de semis.

**Pourquoi** : la culture conditionne stades, besoins en eau et alertes des autres fonctions.
**Test indépendant** : créer une parcelle pour chacune des cultures du référentiel et une culture libre.

**Scénarios d'acceptation** :

1. **Étant donné** la liste des cultures, **Quand** elle s'affiche, **Alors** chaque culture du référentiel de lancement apparaît avec sa photo : olivier, agrumes, blé dur, blé tendre, orge, tomate, pomme de terre, oignon, fruits rouges, avocatier, palmier dattier, amandier, vigne, betterave, luzerne, maïs fourrager.
2. **Étant donné** une culture absente de la liste, **Quand** l'agriculteur ajoute une culture libre, **Alors** elle est utilisable sur la parcelle.
3. **Étant donné** une culture choisie, **Quand** l'agriculteur ne connaît pas la variété, **Alors** il peut continuer sans la renseigner.
4. **Étant donné** une culture pérenne ou annuelle, **Quand** l'agriculteur renseigne la date, **Alors** il saisit l'année de plantation (pérenne) ou la date de semis (annuelle).
5. **Étant donné** une campagne avec date de plantation, **Quand** le stade est estimé automatiquement, **Alors** l'agriculteur peut le corriger et sa correction est conservée.

---

### Récit 3 — Indiquer l'irrigation et la serre (Priorité : P1)

L'agriculteur indique le mode d'irrigation (pluvial, gravitaire, aspersion, goutte-à-goutte, pivot) et si la parcelle est sous serre.

**Pourquoi** : ces informations déterminent les conseils d'irrigation et la fiabilité de l'imagerie.
**Test indépendant** : enregistrer une parcelle pour chaque mode, avec et sans serre.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle en création ou en modification, **Quand** l'agriculteur choisit un mode d'irrigation parmi les cinq, **Alors** il est enregistré et affiché sur la fiche.
2. **Étant donné** une parcelle, **Quand** l'agriculteur indique qu'elle est sous serre, **Alors** l'information est enregistrée et visible sur la fiche.

---

### Récit 4 — Voir toutes mes parcelles sur une carte (Priorité : P1)

L'agriculteur voit toutes ses parcelles sur une carte, colorées selon leur état (vert, orange, rouge, défini en F3).

**Pourquoi** : vue d'ensemble de la ferme, point d'entrée vers chaque parcelle.
**Test indépendant** : afficher une ferme de 50 parcelles, hors réseau.

**Scénarios d'acceptation** :

1. **Étant donné** une ferme avec plusieurs parcelles, **Quand** l'agriculteur ouvre la carte, **Alors** toutes les parcelles sont visibles, colorées selon leur état.
2. **Étant donné** une parcelle dont l'état n'est pas encore calculé, **Quand** la carte s'affiche, **Alors** elle apparaît dans une couleur neutre distincte.
3. **Étant donné** la carte, **Quand** l'agriculteur touche une parcelle, **Alors** sa fiche s'ouvre.
4. **Étant donné** l'appareil hors réseau, **Quand** l'agriculteur ouvre la carte, **Alors** les parcelles déjà chargées s'affichent.

---

### Récit 5 — Découper ou fusionner des parcelles (Priorité : P2)

L'agriculteur découpe une parcelle en blocs ou secteurs d'irrigation, ou fusionne deux parcelles.

**Pourquoi** : la réalité du terrain évolue (secteurs d'irrigation, regroupement).
**Test indépendant** : découper puis fusionner et vérifier surfaces et rattachements.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle, **Quand** l'agriculteur la découpe en blocs, **Alors** chaque bloc a sa géométrie et sa surface, rattachés à la parcelle d'origine.
2. **Étant donné** deux parcelles de la même ferme, **Quand** l'agriculteur les fusionne, **Alors** une seule parcelle les remplace, avec la surface cumulée, sans perte de l'historique des campagnes.

---

### Récit 6 — Démarrer une nouvelle campagne (Priorité : P2)

L'agriculteur démarre une nouvelle campagne sur une parcelle (nouvelle culture, rotation) ; l'historique des campagnes précédentes reste consultable.

**Pourquoi** : suivre rotations et comparer les années.
**Test indépendant** : enchaîner deux campagnes et consulter la première.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle avec une campagne active, **Quand** l'agriculteur démarre une nouvelle campagne d'une autre culture, **Alors** la précédente est clôturée et reste consultable.
2. **Étant donné** une parcelle avec une campagne active pour une culture, **Quand** l'agriculteur tente d'en démarrer une seconde pour la même culture, **Alors** l'app l'en empêche et l'explique.
3. **Étant donné** des cultures associées (ex. olivier et céréales), **Quand** l'agriculteur ajoute une campagne d'une culture différente, **Alors** les deux campagnes sont actives en même temps.

---

### Récit 7 — Importer des parcelles depuis un fichier (Priorité : P3)

L'agriculteur importe des parcelles depuis un fichier (KML, Shapefile) envoyé par un technicien.

**Pourquoi** : gagner du temps quand un technicien a déjà cartographié.
**Test indépendant** : importer un KML puis un Shapefile valides et un fichier invalide.

**Scénarios d'acceptation** :

1. **Étant donné** un fichier KML ou Shapefile valide, **Quand** l'agriculteur l'importe, **Alors** les parcelles proposées sont listées pour confirmation, avec leur surface.
2. **Étant donné** un fichier illisible, **Quand** l'agriculteur l'importe, **Alors** un message clair explique le problème et la solution.

---

### Cas limites

- Dessin de moins de trois points, ou de surface nulle : refusé avec explication.
- Signal GPS faible pendant le tour de parcelle : l'app indique la précision et laisse reprendre ou corriger.
- Parcelle qui chevauche une autre parcelle de la même ferme : l'agriculteur est averti.
- Même modification faite hors ligne sur deux appareils : aucune donnée perdue, conflit résolu sans intervention.
- Parcelle supprimée : archivée 90 jours, restaurable pendant ce délai, puis supprimée définitivement.
- Ouvrier invité (F1) : ne voit que les parcelles qui lui sont attribuées.
- Parcelle de moins de 0,3 ha ou sous serre : signalée comme peu adaptée à l'imagerie (utilisé par F3).

## États et RTL des écrans *(obligatoire)*

Pour chaque écran, les quatre états sont conçus : chargement (squelettes, jamais d'écran blanc), vide (illustration et action proposée), erreur (message clair et solution), hors ligne (indicateur de ce qui n'est pas encore envoyé). Toute mise en page est en miroir complet en arabe et darija en graphie arabe (sens de lecture, icônes directionnelles, alignements, saisie de nombres).

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| Carte des parcelles | Squelette de carte et de liste | Illustration, action « Ajouter ma première parcelle » | Message et bouton « Réessayer » | Parcelles déjà chargées affichées, fond de carte indisponible signalé, date des données |
| Dessin de la parcelle (touches ou GPS) | Recherche de position avec indicateur de précision | Contour vide avec consigne illustrée | Croisement, signal GPS insuffisant : explication visuelle et reprise | Dessin possible, enregistrement local, mention « à envoyer » |
| Fiche et formulaire de parcelle | Squelette des champs | Aucune culture ou campagne : action « Choisir une culture » | Champ invalide signalé près du champ, avec solution | Saisie possible, indicateur de synchronisation en attente |
| Liste illustrée des cultures | Squelettes de vignettes | Aucun résultat de recherche : proposition d'ajouter une culture libre | Message et « Réessayer » | Photos déjà en cache, sinon icônes de remplacement |
| Découpage et fusion | Squelette | Aucune parcelle à fusionner : explication | Découpage invalide expliqué visuellement | Opération locale, envoyée au retour du réseau |
| Campagnes et historique | Squelette de la liste | Aucune campagne passée : action « Démarrer une campagne » | Message et « Réessayer » | Historique local consultable |
| Import de fichier | Indicateur d'analyse | Aucun fichier choisi : consigne illustrée | Format ou contenu non reconnu : cause et solution | Import possible depuis un fichier local, confirmation locale |
| Parcelles archivées | Squelette | Aucune parcelle archivée | Message et « Réessayer » | Liste locale, restauration enregistrée localement |

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : L'agriculteur MUST pouvoir dessiner une parcelle en touchant ses coins sur l'image satellite ou en faisant le tour à pied avec le GPS du téléphone.
- **FR-002** : Le système MUST calculer automatiquement la surface à partir du dessin et l'afficher en hectares avec deux décimales.
- **FR-003** : L'agriculteur MUST pouvoir saisir une surface déclarée différente ; la surface calculée et la surface déclarée MUST être conservées toutes deux.
- **FR-004** : Un dessin qui se croise MUST être corrigé automatiquement ou refusé, avec une explication visuelle.
- **FR-005** : Toute création, modification, découpage, fusion, archivage et restauration MUST fonctionner sans réseau, être enregistré localement et synchronisé au retour du réseau sans perte.
- **FR-006** : L'agriculteur MUST pouvoir nommer la parcelle et choisir sa culture dans une liste illustrée de photos.
- **FR-007** : Le référentiel de lancement MUST contenir : olivier, agrumes, blé dur, blé tendre, orge, tomate, pomme de terre, oignon, fruits rouges, avocatier, palmier dattier, amandier, vigne, betterave, luzerne, maïs fourrager.
- **FR-008** : L'agriculteur MUST pouvoir ajouter une culture libre.
- **FR-009** : L'agriculteur MUST pouvoir renseigner une variété (facultative) et l'année de plantation ou la date de semis.
- **FR-010** : L'agriculteur MUST pouvoir indiquer le mode d'irrigation (pluvial, gravitaire, aspersion, goutte-à-goutte, pivot) et si la parcelle est sous serre.
- **FR-011** : Le système MUST afficher toutes les parcelles de la ferme sur une carte, colorées selon leur état résumé (vert, orange, rouge, défini en F3).
- **FR-012** : Une campagne MUST être l'association d'une parcelle, d'une culture et d'une période.
- **FR-013** : Une parcelle MUST avoir au plus une campagne active par culture ; plusieurs cultures associées MUST pouvoir être actives ensemble.
- **FR-014** : Le système MUST estimer automatiquement le stade de la culture (date de plantation, cumul de température) et l'agriculteur MUST pouvoir le corriger.
- **FR-015** : L'agriculteur MUST pouvoir démarrer une nouvelle campagne (nouvelle culture, rotation) ; l'historique des campagnes précédentes MUST rester consultable.
- **FR-016** : L'agriculteur MUST pouvoir découper une parcelle en blocs ou secteurs d'irrigation, et fusionner deux parcelles (P2).
- **FR-017** : L'agriculteur MUST pouvoir importer des parcelles depuis un fichier KML ou Shapefile après confirmation (P3).
- **FR-018** : Une parcelle supprimée MUST être archivée 90 jours, restaurable pendant ce délai, puis supprimée définitivement.
- **FR-019** : Chaque écran MUST avoir les quatre états conçus et une mise en page RTL complète ; aucun texte ne doit être en dur, tout est traduit en darija, arabe et français.
- **FR-020** : Un ouvrier MUST ne voir que les parcelles qui lui sont attribuées (règle F1) ; la gestion des parcelles MUST être réservée au propriétaire et aux gestionnaires.
- **FR-021** : Les données de parcelles MUST appartenir à l'agriculteur, être incluses dans son export et supprimées avec son compte (loi 09-08).

### Entités principales

- **Field (parcelle)** : géométrie, surface calculée, surface déclarée, nom, mode d'irrigation, serre, sol ; rattachée à une ferme (n-1).
- **Season (campagne)** : culture, variété, dates (plantation ou semis, début, fin), stade estimé et corrigé, destination ; rattachée à une parcelle (n-1).
- **Culture (référentiel)** : nom, photo, variétés, stades ; référentiel partagé, culture libre possible.
- **Bloc ou secteur** : sous-partie d'une parcelle avec sa géométrie et sa surface.

## Hors périmètre

- Cadastre et limites légales.
- Conception du réseau d'irrigation (relève d'une autre application de l'écosystème).
- Calcul de l'état en couleur, imagerie et météo (F3), bilan hydrique (F4).

## Critères de réussite *(obligatoire)*

- **SC-001** : Un agriculteur crée sa première parcelle (dessin, nom, culture, irrigation) en moins de 3 minutes.
- **SC-002** : 100 % des parcelles créées hors réseau sont retrouvées après synchronisation, après au moins 30 jours hors ligne simulés.
- **SC-003** : La surface affichée correspond à la surface réelle du dessin à 1 % près.
- **SC-004** : La carte de 50 parcelles s'affiche en moins de 2 secondes sur un Android d'entrée de gamme.
- **SC-005** : 100 % des dessins qui se croisent sont détectés avant l'enregistrement.
- **SC-006** : Chaque écran est vérifié dans les trois langues et dans ses quatre états, sans texte en dur ni mise en page cassée en RTL.

## Hypothèses

- La ferme et le compte existent déjà (F1) ; l'état en couleur des parcelles est fourni par F3, avec une couleur neutre en attendant.
- Les fonds de carte et images satellite sont téléchargés en Wi-Fi ou à la demande ; hors réseau, seules les zones déjà vues sont disponibles.
- La précision du GPS du téléphone est jugée suffisante pour un contour agricole ; l'app affiche la précision.
- Le type de sol est facultatif et proposé avec une valeur par défaut prudente.
- Aucune question ouverte : le CPS section 7 couvre le périmètre.
