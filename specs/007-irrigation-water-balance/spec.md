# Spécification de fonctionnalité : F4 — Irrigation et bilan hydrique

**Branche** : `007-irrigation-water-balance`
**Créé le** : 2026-11-08
**Statut** : Brouillon
**Entrée** : Fonctionnalité F4. Sources : `docs/cps/AYLAL-CPS.md` section 9 (contexte sections 1 à 3, données section 17, exigences sections 4 et 15). Dépend de F1 (ferme, rôles), F2 (parcelles, cultures, campagnes), F3 (météo) et F6 (journal : une irrigation est une opération). Alimente l'état de parcelle de F3 et, plus tard, F9 (capteurs).

## Objectif

L'agriculteur sait chaque jour si une parcelle irriguée a besoin d'eau, combien, et pendant combien de temps faire tourner son installation.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Décrire mon installation d'irrigation (Priorité : P1)

L'agriculteur décrit une fois l'installation d'une parcelle : type (goutte-à-goutte, aspersion, gravitaire), débit des goutteurs et écartements (ou débit de la pompe), nombre de secteurs.

**Pourquoi** : sans description de l'installation, aucune durée d'irrigation ne peut être calculée.
**Test indépendant** : décrire une installation par type, la modifier, puis vérifier que les valeurs servent au calcul de durée.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle irriguée, **Quand** l'agriculteur saisit le type, le débit des goutteurs, les écartements et le nombre de secteurs, **Alors** l'installation est enregistrée et rattachée à la parcelle.
2. **Étant donné** une installation décrite par le débit de la pompe, **Quand** l'agriculteur l'enregistre, **Alors** elle est acceptée sans débit de goutteurs ni écartements.
3. **Étant donné** un type d'installation choisi, **Quand** l'agriculteur ne précise pas l'efficience, **Alors** l'efficience par défaut du type s'applique (goutte-à-goutte 90 %, aspersion 75 %, gravitaire 60 %) et reste visible.
4. **Étant donné** un agriculteur hors réseau, **Quand** il décrit son installation, **Alors** elle est conservée localement puis synchronisée sans perte.
5. **Étant donné** une valeur incohérente (débit nul ou négatif, écartement nul), **Quand** l'agriculteur valide, **Alors** un message clair indique le champ à corriger.

---

### Récit 2 — Voir chaque jour le conseil d'irrigation (Priorité : P1)

Chaque jour, l'agriculteur voit pour chaque parcelle irriguée un conseil simple : « irriguer 2 h 30 aujourd'hui » ou « pas besoin, pluie prévue ». Le conseil affiche son niveau de confiance et les hypothèses utilisées, accessibles en un clic.

**Pourquoi** : c'est la valeur centrale de la fonctionnalité : économiser l'eau et protéger la culture sans calcul.
**Test indépendant** : avec une parcelle, une installation et une météo données, vérifier la durée conseillée, le report en cas de pluie et l'affichage des hypothèses.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle en goutte-à-goutte dont l'installation est décrite, **Quand** la météo du jour est disponible, **Alors** un conseil de durée s'affiche avant 7 h.
2. **Étant donné** une pluie de plus de 10 mm prévue dans les 24 h, **Quand** le conseil du jour est calculé, **Alors** il recommande de reporter l'irrigation.
3. **Étant donné** un conseil affiché, **Quand** l'agriculteur l'ouvre en un clic, **Alors** il voit le niveau de confiance et les hypothèses (évapotranspiration, coefficient cultural, pluie efficace, type de sol, efficience).
4. **Étant donné** un besoin net calculé, **Quand** la durée est déterminée, **Alors** elle vaut le besoin net divisé par (efficience du système × débit apporté par m²).
5. **Étant donné** un type de sol inconnu, **Quand** le bilan est calculé, **Alors** une réserve utile par défaut prudente s'applique et le conseil le signale dans ses hypothèses.
6. **Étant donné** une météo du jour indisponible, **Quand** l'agriculteur ouvre le conseil, **Alors** le dernier conseil connu s'affiche avec sa date et un niveau de confiance abaissé.
7. **Étant donné** une parcelle en pluvial, **Quand** l'agriculteur consulte ses conseils, **Alors** aucun conseil d'irrigation n'est produit et un indicateur de stress hydrique s'affiche à la place.

---

### Récit 3 — Enregistrer une irrigation en un geste (Priorité : P1)

L'agriculteur enregistre une irrigation faite en un geste, par sa durée ou son volume, ce qui met à jour le bilan hydrique.

**Pourquoi** : le bilan n'est juste que si les apports réels sont connus.
**Test indépendant** : enregistrer une irrigation par durée puis par volume, avec et sans réseau, et comparer le conseil du lendemain.

**Scénarios d'acceptation** :

1. **Étant donné** un conseil du jour affiché, **Quand** l'agriculteur confirme « fait » avec la durée conseillée, **Alors** l'irrigation est enregistrée en un geste.
2. **Étant donné** l'écran d'enregistrement, **Quand** l'agriculteur saisit une durée, **Alors** le volume apporté est calculé à partir de l'installation, et inversement pour un volume saisi.
3. **Étant donné** une irrigation enregistrée, **Quand** le bilan est recalculé, **Alors** le bilan et le conseil du lendemain en tiennent compte.
4. **Étant donné** un agriculteur hors réseau, **Quand** il enregistre une irrigation, **Alors** elle est conservée localement, marquée « à envoyer », et prise en compte immédiatement dans le bilan local.
5. **Étant donné** une irrigation enregistrée, **Quand** l'agriculteur ouvre le journal des opérations (F6), **Alors** elle y apparaît comme opération d'irrigation de la parcelle, sans double saisie.

---

### Récit 4 — Suivre l'eau consommée (Priorité : P2)

L'agriculteur voit le volume d'eau consommé par parcelle et sur la campagne, en m³ et en m³/ha.

**Pourquoi** : maîtriser le coût et la ressource en eau, comparer ses parcelles.
**Test indépendant** : enregistrer plusieurs irrigations sur deux parcelles de surfaces différentes et vérifier les totaux et les ratios.

**Scénarios d'acceptation** :

1. **Étant donné** des irrigations enregistrées sur une parcelle, **Quand** l'agriculteur ouvre le suivi, **Alors** il voit le volume total en m³ et le volume par hectare en m³/ha pour la campagne.
2. **Étant donné** plusieurs parcelles, **Quand** l'agriculteur compare, **Alors** chaque parcelle affiche son volume et son ratio par hectare.
3. **Étant donné** une campagne sans irrigation enregistrée, **Quand** l'agriculteur ouvre le suivi, **Alors** un état vide propose d'enregistrer une irrigation.

---

### Récit 5 — Enregistrer l'analyse d'eau du puits (Priorité : P2)

L'agriculteur enregistre l'analyse d'eau de son puits (salinité) et l'app adapte le conseil en ajoutant une fraction de lessivage.

**Pourquoi** : une eau salée dégrade le sol et la culture si elle n'est pas compensée.
**Test indépendant** : enregistrer une analyse de salinité faible puis élevée et comparer les durées conseillées.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle irriguée, **Quand** l'agriculteur saisit la salinité de l'eau avec la date de l'analyse, **Alors** l'analyse est enregistrée et rattachée à la parcelle ou à la source d'eau.
2. **Étant donné** une salinité supérieure au seuil de tolérance de la culture, **Quand** le conseil est calculé, **Alors** la durée intègre une fraction de lessivage et les hypothèses l'indiquent.
3. **Étant donné** une salinité inférieure au seuil de tolérance, **Quand** le conseil est calculé, **Alors** aucune fraction de lessivage n'est ajoutée.
4. **Étant donné** une analyse ancienne, **Quand** le conseil est affiché, **Alors** l'âge de l'analyse est signalé dans les hypothèses.

---

### Récit 6 — Correction par capteur ou compteur connecté (Priorité : P3)

Un capteur d'humidité du sol ou un compteur connecté corrige le conseil automatiquement (voir F9).

**Pourquoi** : une mesure réelle affine le bilan calculé.
**Test indépendant** : hors de cette version ; seul le point d'accueil d'une mesure externe dans le bilan est vérifié.

**Scénarios d'acceptation** :

1. **Étant donné** une mesure externe d'humidité du sol fournie par F9, **Quand** le conseil est calculé, **Alors** la mesure corrige le bilan et les hypothèses indiquent sa source.

---

### Cas limites

- Aucune installation décrite : la parcelle irriguée affiche un conseil indisponible et invite à décrire l'installation.
- Culture ou stade sans coefficient cultural : le conseil est indisponible avec une explication, jamais une valeur inventée.
- Plusieurs secteurs : la durée est donnée par secteur et le total indiqué.
- Pluie prévue mais non tombée, ou pluie réelle différente de la prévision : le bilan du lendemain utilise la pluie observée.
- Irrigation enregistrée avec une date passée : le bilan est recalculé depuis cette date.
- Même irrigation saisie deux fois (hors réseau puis après synchronisation) : une seule irrigation est conservée.
- Parcelle sous serre : la pluie n'entre pas dans le bilan.
- Changement de campagne ou de culture : le bilan repart de la nouvelle campagne.
- Plusieurs utilisateurs de la ferme modifient la même installation hors réseau : aucune donnée perdue, la dernière modification est conservée et l'historique reste consultable.

## Clarifications

### Session 2026-11-08

- Aucune clarification ouverte à ce stade ; les points sont tranchés par le CPS section 9 et les décisions de la section 19.

## États et RTL des écrans *(obligatoire)*

Écrans : (A) installation d'irrigation, (B) conseil du jour par parcelle et détail des hypothèses, (C) enregistrement d'une irrigation, (D) suivi de la consommation d'eau, (E) analyse d'eau.

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| A Installation | Squelette du formulaire | Illustration et action « décrire mon installation » | Message clair sur le champ invalide ou l'échec d'enregistrement, avec solution | Saisie possible, mention « à envoyer », valeurs déjà chargées affichées |
| B Conseil du jour | Squelettes des cartes de parcelles, jamais d'écran blanc | Aucune parcelle irriguée : illustration et action pour décrire une installation ; parcelle en pluvial : indicateur de stress hydrique | Conseil indisponible avec la raison (météo, culture, installation) et l'action pour corriger | Dernier conseil connu affiché avec sa date et une confiance abaissée |
| C Enregistrement | Squelette | Aucune irrigation passée : proposition d'enregistrer la première | Message clair et conservation de la saisie | Enregistrement local, mention « à envoyer », bilan local mis à jour |
| D Suivi consommation | Squelettes des totaux et du graphique | Illustration et action « enregistrer une irrigation » | Message clair et action de nouvel essai | Totaux calculés sur les données locales, avec leur date |
| E Analyse d'eau | Squelette | Illustration et action « ajouter une analyse » | Message clair sur la valeur ou l'échec | Saisie locale, mention « à envoyer » |

**Exigences RTL et langues** :

- Chaque écran existe en darija (graphie arabe et latine), arabe standard (RTL complet) et français.
- En arabe, la mise en page, les icônes directionnelles et les graphiques sont en miroir parfait ; les durées, volumes et unités (h, min, m³, m³/ha, mm) restent lisibles et correctement ordonnés en RTL.
- Les textes longs et courts sont testés dans les trois langues ; aucun texte n'est en dur dans l'interface.
- Chaque écran est utilisable par un agriculteur qui lit peu : icônes, un seul objectif par écran, lecture vocale du conseil.
- Chaque écran est maquetté en arabe et en français avant développement.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : le système DOIT permettre de décrire, modifier et consulter l'installation d'irrigation d'une parcelle irriguée : type, débit des goutteurs et écartements ou débit de la pompe, nombre de secteurs, efficience.
- **FR-002** : le système DOIT appliquer par défaut l'efficience du type d'installation : goutte-à-goutte 90 %, aspersion 75 %, gravitaire 60 %.
- **FR-003** : le système DOIT calculer le besoin en eau de la culture selon la méthode FAO-56 : évapotranspiration de référence issue de la météo multipliée par le coefficient cultural de la culture et du stade, moins la pluie efficace.
- **FR-004** : le système DOIT tenir un bilan hydrique journalier du sol par parcelle, avec une réserve utile selon la texture du sol et un défaut prudent si la texture est inconnue.
- **FR-005** : le système DOIT calculer la durée d'irrigation comme le besoin net divisé par (efficience du système × débit apporté par m²).
- **FR-006** : le système DOIT afficher chaque jour, pour chaque parcelle irriguée, un conseil simple (durée à irriguer ou « pas besoin ») disponible avant 7 h dès que la météo du jour est disponible.
- **FR-007** : le système DOIT recommander de reporter l'irrigation lorsqu'une pluie de plus de 10 mm est prévue dans les 24 h.
- **FR-008** : le système DOIT afficher avec chaque conseil son niveau de confiance et les hypothèses utilisées, accessibles en un clic.
- **FR-009** : le système NE DOIT PAS produire de conseil d'irrigation pour une parcelle en pluvial et DOIT afficher à la place un indicateur de stress hydrique.
- **FR-010** : le système DOIT permettre d'enregistrer une irrigation faite, par durée ou par volume, en un geste, y compris depuis le conseil du jour.
- **FR-011** : le système DOIT intégrer toute irrigation enregistrée au bilan et au conseil du lendemain, et recalculer le bilan si la date est passée.
- **FR-012** : l'irrigation enregistrée DOIT apparaître dans le journal des opérations (F6) comme opération d'irrigation, sans double saisie.
- **FR-013** : le système DOIT afficher le volume d'eau consommé par parcelle et sur la campagne, en m³ et en m³/ha.
- **FR-014** : le système DOIT permettre d'enregistrer une analyse d'eau (salinité, date) et ajouter une fraction de lessivage au conseil lorsque la salinité dépasse la tolérance de la culture.
- **FR-015** : le système DOIT prévoir l'intégration d'une mesure externe d'humidité du sol ou de volume (capteur, compteur connecté, F9) comme correction du bilan, sans la rendre obligatoire.
- **FR-016** : toutes les fonctions de saisie et de consultation DOIVENT fonctionner hors réseau, avec synchronisation invisible et sans perte ; le bilan est recalculable avec les données locales.
- **FR-017** : le conseil DOIT indiquer sa source, son niveau de confiance et ses limites ; aucune valeur inventée n'est affichée lorsqu'une donnée essentielle manque.
- **FR-018** : le résumé du conseil (besoin d'irrigation, stress hydrique) DOIT être disponible pour l'état de la parcelle du tableau de bord (F3).
- **FR-019** : toute règle de calcul (besoin, bilan, durée, lessivage, report pour pluie) DOIT être partagée entre tous les fronts et testable sans interface.
- **FR-020** : le conseil DOIT être lisible à voix haute pour chaque écran concerné.
- **FR-021** : les données restent propres à la ferme de l'agriculteur ; rien n'est partagé sans accord explicite, et l'export et la suppression complets incluent installations, irrigations et analyses d'eau.

### Entités principales

- **IrrigationSystem** : installation d'une parcelle : type, débits, écartements, secteurs, efficience.
- **WaterBalance** : bilan journalier d'une campagne : ET0, Kc, pluie, réserve du sol, conseil, confiance, hypothèses.
- **Irrigation (opération)** : apport réel : parcelle, date, durée ou volume, secteur ; lié au journal (F6).
- **WaterAnalysis** : analyse d'eau : salinité, date, source d'eau.
- **Référentiels utilisés** : cultures (Kc par stade, tolérance à la salinité), sols (texture, réserve utile par défaut).

## Hors périmètre

- Commande à distance des vannes et pompes.
- Conception et dimensionnement du réseau.
- Fertigation détaillée.
- Branchement effectif des capteurs et compteurs connectés (F9, phase 2).

## Critères de réussite *(obligatoire)*

- **SC-001** : pour 100 % des parcelles irriguées dont l'installation est décrite et dont la météo du jour est disponible, le conseil est visible avant 7 h.
- **SC-002** : un agriculteur entraîné décrit une installation en moins de 2 minutes et enregistre une irrigation en moins de 15 secondes.
- **SC-003** : 100 % des cas de pluie prévue de plus de 10 mm dans les 24 h produisent une recommandation de report.
- **SC-004** : les durées calculées s'écartent de moins de 5 % des valeurs de référence du jeu de cas de test agronomique validé.
- **SC-005** : après 30 jours hors réseau simulés, aucune irrigation ni installation saisie n'est perdue après synchronisation.
- **SC-006** : chaque conseil affiche confiance et hypothèses en un clic, vérifié sur 100 % des conseils testés.
- **SC-007** : chaque écran présente ses quatre états et un rendu RTL conforme en arabe, validés par la revue design.

## Hypothèses

- La météo et l'évapotranspiration de référence viennent de la source météo de F3 ; sans météo du jour, le dernier conseil est conservé avec une confiance abaissée.
- Les coefficients culturaux par stade et les tolérances à la salinité viennent du référentiel cultures (FAO-56, validation agronomique) ; les textures et réserves utiles par défaut viennent du référentiel sols.
- Le « défaut prudent » de réserve utile est la valeur de réserve la plus faible du référentiel sols, afin de ne pas sous-irriguer.
- La parcelle est irriguée ou en pluvial selon son attribut d'irrigation défini en F2.
- Une irrigation est une opération du journal (F6) ; F4 ne crée pas de second registre.
- Les seuils exacts de fraction de lessivage et de confiance sont fixés par validation agronomique et consignés dans le plan.
- La notification du conseil du matin suit les préférences de notification de F3.
