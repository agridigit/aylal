# Spécification de fonctionnalité : F3 — Tableau de bord et monitoring

**Branche** : `006-dashboard-monitoring`
**Créé le** : 2026-11-07
**Statut** : Brouillon
**Entrée** : Fonctionnalité F3. Sources : `docs/cps/AYLAL-CPS.md` section 8 (contexte sections 1 à 3, données section 17). Dépend de F1 (compte, ferme) et F2 (parcelles, cultures). Reçoit des signaux de F4, F5 et F6.

## Objectif

En ouvrant l'app, l'agriculteur voit en 30 secondes quelles parcelles demandent son attention aujourd'hui et pourquoi.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Voir la météo de ma ferme (Priorité : P1)

L'agriculteur voit la météo de sa ferme : aujourd'hui et les 7 prochains jours (température, pluie, vent, humidité), avec des icônes simples.

**Pourquoi** : la météo conditionne toutes les décisions du jour.
**Test indépendant** : ouvrir le tableau de bord d'une ferme localisée et vérifier aujourd'hui + 7 jours, avec et sans réseau.

**Scénarios d'acceptation** :

1. **Étant donné** une ferme localisée, **Quand** l'agriculteur ouvre le tableau de bord, **Alors** la météo du jour et des 7 jours suivants s'affiche avec température, pluie, vent et humidité, chacun avec une icône simple.
2. **Étant donné** l'app ouverte hors réseau, **Quand** le tableau de bord s'affiche, **Alors** il montre les dernières données chargées avec leur date.

---

### Récit 2 — Recevoir des alertes météo pour mes cultures (Priorité : P1)

L'agriculteur reçoit des alertes météo qui concernent ses cultures : gel, chergui (vent chaud et sec), forte pluie, vent fort déconseillant un traitement.

**Pourquoi** : une alerte à temps évite des pertes (gel en floraison) ou un traitement inutile.
**Test indépendant** : simuler chaque type de prévision sur une culture sensible à son stade courant et vérifier la notification.

**Scénarios d'acceptation** :

1. **Étant donné** une prévision de gel à 48 heures sur une culture sensible au stade courant, **Quand** la veille arrive, **Alors** l'agriculteur reçoit une notification avant 18 h.
2. **Étant donné** une culture dont le seuil de gel n'est pas dépassé à son stade courant, **Quand** le même gel est prévu, **Alors** aucune alerte de gel n'est émise pour cette culture.
3. **Étant donné** une prévision de chergui, de forte pluie ou de vent fort, **Quand** une culture est concernée selon ses seuils par stade, **Alors** une alerte du type correspondant est créée, avec la parcelle, la gravité et la raison.
4. **Étant donné** un vent fort prévu, **Quand** l'agriculteur prépare un traitement, **Alors** l'alerte lui déconseille de traiter ce jour-là.

---

### Récit 3 — Suivre la vigueur de chaque parcelle par satellite (Priorité : P1)

Pour chaque parcelle, l'agriculteur voit une carte de vigueur issue du satellite et une courbe d'évolution depuis le début de la campagne.

**Pourquoi** : voir de loin ce qui se passe dans la parcelle, sans y aller.
**Test indépendant** : créer une parcelle et vérifier l'historique, la carte et la courbe, y compris pour une parcelle nuageuse ou petite.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle créée, **Quand** le traitement initial est terminé, **Alors** l'historique de vigueur des 12 derniers mois s'affiche en moins de 10 minutes.
2. **Étant donné** une image satellite récente, **Quand** moins de 80 % de la parcelle est sans nuage, **Alors** l'image n'est pas affichée et la dernière image valide reste affichée avec sa date.
3. **Étant donné** une parcelle de moins de 0,3 ha ou sous serre, **Quand** sa fiche s'affiche, **Alors** l'imagerie est signalée comme peu fiable et l'état repose sur la météo et les observations.
4. **Étant donné** la fiche d'une parcelle, **Quand** elle s'affiche, **Alors** la vigueur et l'humidité de la végétation sont nommées « vigueur » et « humidité des plantes », jamais par leur nom technique.

---

### Récit 4 — Être guidé vers une zone qui décroche (Priorité : P1)

L'app signale une zone de parcelle dont la vigueur baisse anormalement et propose d'aller voir, avec un guidage GPS jusqu'à la zone.

**Pourquoi** : détecter tôt un problème localisé (maladie, panne d'irrigation) et s'y rendre vite.
**Test indépendant** : fournir une série d'images avec une zone en baisse et vérifier signalement et guidage.

**Scénarios d'acceptation** :

1. **Étant donné** une zone de parcelle dont la vigueur baisse anormalement, **Quand** la nouvelle image est traitée, **Alors** la zone est délimitée sur la carte et l'app propose d'aller voir.
2. **Étant donné** une zone signalée, **Quand** l'agriculteur accepte, **Alors** l'app le guide par GPS jusqu'à la zone, y compris hors réseau avec les fonds de carte déjà vus.
3. **Étant donné** une zone signalée, **Quand** l'agriculteur est sur place, **Alors** il peut enregistrer une observation rattachée à la zone.

---

### Récit 5 — Voir l'état résumé en couleur de chaque parcelle (Priorité : P1)

Chaque parcelle a un état en couleur : vert (rien à faire), orange (à surveiller), rouge (action conseillée), avec la raison en une phrase.

**Pourquoi** : c'est le cœur du « 30 secondes » : une vue d'ensemble sans lire de chiffres.
**Test indépendant** : combiner chaque source d'état et vérifier la couleur, la phrase et l'explication de source.

**Scénarios d'acceptation** :

1. **Étant donné** plusieurs parcelles, **Quand** l'agriculteur ouvre le tableau de bord, **Alors** chacune affiche sa couleur et sa raison en une phrase, les parcelles rouges puis orange en premier.
2. **Étant donné** une parcelle, **Quand** l'état est calculé, **Alors** il combine alertes météo, anomalie de vigueur, besoin d'irrigation (F4), risque sanitaire (F5) et opérations en retard (F6).
3. **Étant donné** un état orange ou rouge, **Quand** l'agriculteur ouvre le détail, **Alors** chaque élément qui contribue explique sa source.
4. **Étant donné** une source d'état encore indisponible (F4, F5 ou F6 non livrée), **Quand** l'état est calculé, **Alors** il repose sur les sources disponibles sans erreur ni blocage.
5. **Étant donné** une parcelle sans signal, **Quand** l'état est calculé, **Alors** elle est verte avec la phrase « rien à faire ».

---

### Récit 6 — Comparer avec la campagne de l'an dernier (Priorité : P2)

L'agriculteur compare la vigueur de la campagne en cours à celle de l'an dernier sur la même parcelle.

**Pourquoi** : situer la campagne en cours par rapport à une référence connue de l'agriculteur.
**Test indépendant** : parcelle avec deux ans d'historique, superposition des deux courbes.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle avec au moins 12 mois d'historique, **Quand** l'agriculteur active la comparaison, **Alors** les courbes de cette campagne et de l'an dernier s'affichent ensemble, alignées sur les mêmes dates.
2. **Étant donné** une parcelle sans historique de l'an dernier, **Quand** l'agriculteur ouvre la comparaison, **Alors** un message explique l'absence de référence.

---

### Récit 7 — Écouter le résumé vocal de la journée (Priorité : P2)

L'agriculteur reçoit un résumé vocal de la journée sous forme de notification qu'il peut écouter.

**Pourquoi** : accessible à un agriculteur peu lecteur, mains occupées.
**Test indépendant** : déclencher le résumé et l'écouter dans chaque langue.

**Scénarios d'acceptation** :

1. **Étant donné** un tableau de bord à jour, **Quand** l'heure du résumé arrive, **Alors** l'agriculteur reçoit une notification et peut écouter un résumé vocal des parcelles à surveiller et de la météo du jour.
2. **Étant donné** un résumé reçu, **Quand** l'agriculteur l'écoute, **Alors** il est dans sa langue (darija, arabe ou français) et mentionne d'abord les parcelles rouges.
3. **Étant donné** un appareil hors réseau, **Quand** un résumé déjà reçu est réouvert, **Alors** il reste écoutable.

---

### Cas limites

- Ferme sans parcelle : le tableau de bord montre la météo et invite à créer une première parcelle.
- Ferme non localisée : la météo est impossible ; l'app demande de préciser la localisation.
- Parcelle récente sans image valide pendant longtemps (nuages) : dernière valeur connue avec sa date, état fondé sur les autres sources.
- Plusieurs cultures actives sur une parcelle : les seuils d'alerte s'appliquent à chaque culture ; l'état retient la plus grave.
- Parcelle archivée : elle disparaît du tableau de bord et ne génère plus d'alerte ni de notification.
- Ouvrier : ne voit que les parcelles qui lui sont attribuées (règle F1), y compris pour alertes et résumé vocal.
- Notification de gel déjà envoyée : pas de doublon pour la même prévision ; mise à jour si la prévision change.
- Données hors ligne anciennes : l'âge des données est toujours visible.

## Clarifications

### Session 2026-11-07

- Q : Qui reçoit les alertes et le résumé vocal ? → R : Propriétaire et gestionnaires pour toutes les parcelles ; un ouvrier seulement pour ses parcelles attribuées (CPS section 6, critère F1 ; section 8 reste muette, choix le plus simple et le plus sûr).
- Q : Quels canaux de notification ? → R : Notification poussée sur le téléphone en premier ; les autres canaux de la section 16 (WhatsApp, SMS de secours) ne sont pas exigés par cette fonctionnalité (CPS section 8 ne cite que « notification »), gratuité préservée.
- Q : Valeurs chiffrées des seuils météo et de l'« anomalie » de vigueur ? → R : Le CPS section 8 les définit « par culture et par stade » dans le référentiel des cultures (section 17), validé par l'agronomie ; les valeurs sont des données de référentiel fixées au plan, pas des règles de la spec. Par défaut prudent : en cas de doute, l'état est orange et non vert.
- Q : Que fait l'app quand une image est trop nuageuse ? → R : Elle garde la dernière image valide, affichée avec sa date (règle des 80 % de la section 8 ; pas de nouveau calcul de substitution).
- Q : Résumé vocal : heure et langue ? → R : Une fois par jour, le matin par défaut, dans la langue du compte (darija, arabe, français, section 4) ; l'heure exacte est un paramètre fixé au plan. Texte affiché en repli si la lecture est impossible.
- Q : Comparaison avec l'an dernier sans historique ? → R : Message explicatif, sans courbe vide (section 8, récit P2).

## États et RTL des écrans *(obligatoire)*

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| Tableau de bord (météo + liste des parcelles par état) | Squelettes de la météo et des cartes de parcelles | Aucune parcelle : invitation à en créer une, météo visible | Message clair avec bouton « Réessayer », sans perdre les données déjà affichées | Dernières données chargées avec leur date ; bandeau hors ligne |
| Météo 7 jours | Squelette des 7 jours | Ferme non localisée : invitation à préciser la localisation | Météo indisponible : dernière prévision datée, si elle existe | Dernière prévision chargée avec sa date |
| Alertes météo | Squelette de liste | « Aucune alerte pour vos cultures » | Message avec réessai | Alertes déjà reçues, datées |
| Fiche vigueur d'une parcelle (carte + courbe) | Squelette de la carte et de la courbe | Pas encore d'image valide : traitement initial en cours ou nuages, avec explication | Message avec réessai | Dernière carte et courbe, datées |
| Détail de l'état d'une parcelle | Squelette des raisons | Vert : « rien à faire » | Message avec réessai | Dernier état calculé, daté |
| Zone à vérifier + guidage GPS | Calcul de l'itinéraire | Aucune zone signalée | Position ou itinéraire indisponible, avec solution de repli | Guidage sur les fonds de carte déjà vus |
| Comparaison avec l'an dernier | Squelette des deux courbes | Aucune référence de l'an dernier, expliquée | Message avec réessai | Dernières courbes chargées, datées |
| Résumé vocal | Préparation du résumé | Aucun résumé reçu pour le moment | Lecture impossible, texte du résumé affiché | Résumés déjà reçus écoutables |

**Exigences RTL** : en arabe et en darija, tout le tableau de bord est en miroir (ordre des jours de la météo, sens de la courbe temporelle, placement des icônes et des boutons, flèches de navigation) ; les nombres, unités et dates restent lisibles ; la carte, les couleurs d'état et les icônes météo ne dépendent pas du sens de lecture ; aucun texte n'est en dur, tout est traduit en darija, arabe et français.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : Le système MUST afficher la météo de la ferme pour aujourd'hui et les 7 jours suivants (température, pluie, vent, humidité) avec des icônes simples.
- **FR-002** : Le système MUST émettre des alertes météo concernant les cultures : gel, chergui, forte pluie, vent fort déconseillant un traitement.
- **FR-003** : Les seuils d'alerte MUST être définis par culture et par stade (ex. gel critique pour l'amandier en floraison) ; une alerte n'est émise que si le seuil de la culture au stade courant est atteint.
- **FR-004** : Pour une prévision de gel à 48 heures sur une culture sensible au stade courant, l'agriculteur MUST recevoir une notification la veille avant 18 h.
- **FR-005** : Chaque alerte MUST indiquer sa parcelle, son type, sa gravité, sa source et son statut.
- **FR-006** : Le système MUST fournir, pour chaque parcelle, une carte de vigueur satellite et une courbe d'évolution depuis le début de la campagne.
- **FR-007** : La source satellite par défaut MUST être Sentinel-2 (gratuite, 10 m, environ tous les 5 jours) ; une image MUST n'être affichée que si au moins 80 % de la parcelle est sans nuage.
- **FR-008** : Les indices affichés MUST être la vigueur et l'humidité de la végétation, nommés « vigueur » et « humidité des plantes » ; les noms techniques MUST rester cachés.
- **FR-009** : Pour une parcelle de moins de 0,3 ha ou sous serre, l'imagerie MUST être signalée comme peu fiable et l'état MUST reposer sur la météo et les observations.
- **FR-010** : Après la création d'une parcelle, l'historique de vigueur des 12 derniers mois MUST s'afficher en moins de 10 minutes à la fin du traitement initial.
- **FR-011** : Le système MUST détecter une zone de parcelle dont la vigueur baisse anormalement, la délimiter, proposer d'aller voir et guider par GPS jusqu'à la zone.
- **FR-012** : Chaque parcelle MUST avoir un état résumé : vert (rien à faire), orange (à surveiller), rouge (action conseillée), avec la raison en une phrase.
- **FR-013** : L'état MUST combiner alertes météo, anomalie de vigueur, besoin d'irrigation (F4), risque sanitaire (F5) et opérations en retard (F6) ; chaque élément MUST expliquer sa source. Les sources non encore disponibles MUST être ignorées sans erreur.
- **FR-014** : Le tableau de bord MUST classer les parcelles avec les rouges d'abord, puis les orange, puis les vertes.
- **FR-015** : L'agriculteur MUST pouvoir comparer la vigueur de la campagne en cours à celle de l'an dernier sur la même parcelle (P2).
- **FR-016** : L'agriculteur MUST pouvoir recevoir un résumé vocal de la journée sous forme de notification écoutable, dans sa langue (P2).
- **FR-017** : Hors réseau, le tableau de bord MUST afficher les dernières données chargées avec leur date.
- **FR-018** : Chaque écran MUST avoir les quatre états conçus (chargement, vide, erreur, hors ligne) et une mise en page RTL complète ; aucun texte en dur, tout traduit en darija, arabe et français.
- **FR-019** : Un ouvrier MUST ne voir (tableau de bord, alertes, résumé vocal) que les parcelles qui lui sont attribuées ; une parcelle archivée ou supprimée MUST disparaître du tableau de bord et ne plus générer d'alerte.
- **FR-020** : Les données de monitoring MUST appartenir à l'agriculteur, être incluses dans son export et supprimées avec son compte (loi 09-08).

### Entités principales

- **ImageryScene (image satellite)** : date, couverture nuageuse, indices (vigueur, humidité des plantes) ; rattachée à une parcelle (n-1).
- **Alert (alerte)** : type, gravité, source, statut ; rattachée à une parcelle (n-1).
- **Seuils météo (référentiel Cultures)** : seuils par culture et par stade.
- **État de parcelle** : couleur, phrase de raison, éléments contributeurs avec leur source ; rattaché à une parcelle.
- **Zone à vérifier** : délimitation, parcelle, position pour le guidage.

## Hors périmètre

- Imagerie drone, thermique ou haute résolution (premium, phase 2).
- Prévision de rendement.
- Calcul du besoin d'irrigation (F4), du risque sanitaire (F5) et des opérations en retard (F6) : F3 les consomme seulement.

## Critères de réussite *(obligatoire)*

- **SC-001** : Un agriculteur identifie les parcelles qui demandent son attention, et pourquoi, en moins de 30 secondes après l'ouverture de l'app.
- **SC-002** : L'historique de vigueur sur 12 mois d'une nouvelle parcelle s'affiche en moins de 10 minutes dans 95 % des cas.
- **SC-003** : 100 % des prévisions de gel à 48 heures sur une culture sensible au stade courant déclenchent une notification avant 18 h la veille.
- **SC-004** : Aucune image affichée n'a moins de 80 % de sa parcelle sans nuage.
- **SC-005** : Hors réseau, 100 % des écrans du tableau de bord affichent les dernières données avec leur date.
- **SC-006** : Chaque écran est vérifié dans les trois langues et dans ses quatre états, sans texte en dur ni mise en page cassée en RTL.
- **SC-007** : Chaque état orange ou rouge affiche sa raison en une phrase et la source de chaque élément contributeur.

## Hypothèses

- La ferme, ses parcelles et leurs campagnes existent (F1, F2) ; le stade de la culture vient de F2.
- F4, F5 et F6 fournissent leurs signaux plus tard ; en attendant, l'état repose sur les sources disponibles.
- Les seuils météo par culture et par stade sont maintenus dans le référentiel des cultures par l'équipe AYLAL, avec validation agronomique.
- L'heure du résumé vocal a une valeur par défaut le matin, modifiable ; l'heure exacte est fixée au plan.
- Imagerie Sentinel-2 et météo sans limite d'usage (CPS section 19).
- Aucune question ouverte : le CPS section 8 couvre le périmètre ; les points muets sont tranchés dans les clarifications.
