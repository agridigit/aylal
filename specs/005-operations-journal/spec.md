# Spécification de fonctionnalité : F6 — Journal des opérations et registre phyto

**Branche** : `005-operations-journal`
**Créé le** : 2026-11-07
**Statut** : Brouillon
**Entrée** : Fonctionnalité F6. Sources : `docs/cps/AYLAL-CPS.md` section 11 (contexte sections 1 à 3, données section 17, exigences sections 4 et 15). Dépend de F1 (compte, ferme, rôles) et F2 (parcelles, cultures, campagnes). Alimente F4 (bilan hydrique) et F8 (coûts).

## Objectif

Tout ce qui se fait sur la ferme est noté en quelques secondes, et l'agriculteur peut produire à tout moment un registre de traitements présentable à une coopérative, un exportateur ou un auditeur.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Enregistrer une opération par son icône (Priorité : P1)

L'agriculteur enregistre une opération en choisissant son icône : traitement phyto, fertilisation, irrigation, travail du sol, semis ou plantation, taille, désherbage, récolte, autre.

**Pourquoi** : un journal complet n'existe que si la saisie est plus rapide que de ne rien noter.
**Test indépendant** : enregistrer une opération de chaque type, avec et sans réseau, et chronométrer la saisie.

**Scénarios d'acceptation** :

1. **Étant donné** l'écran de saisie, **Quand** l'agriculteur choisit une icône de type puis une parcelle et une date, **Alors** l'opération est enregistrée sans autre champ obligatoire.
2. **Étant donné** un agriculteur hors réseau, **Quand** il enregistre une opération, **Alors** elle est conservée localement, marquée « à envoyer », puis synchronisée au retour du réseau sans perte.
3. **Étant donné** une opération couvrant plusieurs parcelles, **Quand** une quantité est saisie, **Alors** elle est répartie entre les parcelles au prorata de leur surface et la répartition est affichée.
4. **Étant donné** un utilisateur entraîné, **Quand** il enregistre une opération, **Alors** l'enregistrement prend moins de 15 secondes.
5. **Étant donné** une opération enregistrée, **Quand** l'agriculteur ouvre le journal, **Alors** elle apparaît dans l'ordre chronologique avec son icône, sa parcelle et sa date.

---

### Récit 2 — Traitement phyto avec contrôles (Priorité : P1)

Pour un traitement, l'agriculteur choisit le produit dans le catalogue (recherche par nom ou par photo de l'étiquette), la dose, la parcelle et la date. L'app le prévient si la dose dépasse l'homologation ou si le produit n'est pas autorisé sur cette culture.

**Pourquoi** : éviter les infractions et les résidus, et garder un registre complet.
**Test indépendant** : enregistrer des traitements conformes et non conformes (dose, culture, nombre d'applications) et vérifier les avertissements.

**Scénarios d'acceptation** :

1. **Étant donné** le catalogue des produits homologués, **Quand** l'agriculteur cherche par nom, **Alors** les produits correspondants s'affichent avec leur matière active.
2. **Étant donné** la photo d'une étiquette, **Quand** l'app reconnaît le produit, **Alors** il est proposé à la confirmation de l'agriculteur ; sinon la recherche par nom reste disponible.
3. **Étant donné** une dose supérieure à la dose maximale homologuée, **Quand** l'agriculteur valide, **Alors** un avertissement s'affiche et l'enregistrement reste possible.
4. **Étant donné** un produit non autorisé sur la culture de la parcelle, **Quand** l'agriculteur le sélectionne, **Alors** un avertissement s'affiche et l'enregistrement reste possible.
5. **Étant donné** un produit dont le nombre maximal d'applications est atteint sur la campagne, **Quand** l'agriculteur enregistre une nouvelle application, **Alors** un avertissement s'affiche sans blocage.
6. **Étant donné** un traitement enregistré malgré un avertissement, **Quand** le registre est consulté, **Alors** l'avertissement figure sur la ligne du traitement.
7. **Étant donné** un traitement phyto, **Quand** produit ou dose manquent, **Alors** l'app les demande mais n'empêche pas l'enregistrement.

---

### Récit 3 — Voir la date de récolte au plus tôt (Priorité : P1)

L'agriculteur voit, pour chaque parcelle, la date à partir de laquelle il peut récolter : le délai avant récolte (DAR) le plus long restant.

**Pourquoi** : récolter trop tôt expose à des résidus non conformes.
**Test indépendant** : enregistrer plusieurs traitements aux DAR différents et vérifier la date affichée.

**Scénarios d'acceptation** :

1. **Étant donné** un traitement enregistré avec un produit au DAR de 21 jours, **Quand** l'agriculteur consulte la parcelle, **Alors** la date de récolte au plus tôt passe à J+21.
2. **Étant donné** plusieurs traitements récents aux DAR différents, **Quand** la date est calculée, **Alors** c'est le délai le plus long restant qui s'applique.
3. **Étant donné** une parcelle sans traitement dont le délai court encore, **Quand** elle est consultée, **Alors** elle est indiquée récoltable dès maintenant.
4. **Étant donné** un traitement corrigé ou supprimé, **Quand** la date est recalculée, **Alors** elle reflète la situation à jour.

---

### Récit 4 — Planifier une opération et être rappelé (Priorité : P1)

L'agriculteur planifie une opération à venir et reçoit un rappel le jour venu.

**Pourquoi** : ne pas oublier les interventions et préparer le travail.
**Test indépendant** : planifier une opération pour demain, vérifier le rappel et le passage au statut « faite ».

**Scénarios d'acceptation** :

1. **Étant donné** une date future, **Quand** l'agriculteur enregistre une opération, **Alors** son statut est « planifiée ».
2. **Étant donné** une opération planifiée, **Quand** le jour venu arrive, **Alors** l'agriculteur reçoit un rappel, y compris si l'app était hors réseau au moment de la planification.
3. **Étant donné** un rappel reçu, **Quand** l'agriculteur confirme que l'opération est faite, **Alors** son statut passe à « faite » et elle compte dans le journal, le calcul du délai avant récolte et les coûts.
4. **Étant donné** une opération planifiée non réalisée, **Quand** sa date est dépassée, **Alors** elle reste visible comme en retard, avec le choix de la reporter, la réaliser ou l'annuler.

---

### Récit 5 — Dicter une opération à voix haute (Priorité : P1)

L'agriculteur dicte une opération (« j'ai traité les oliviers du bas avec du cuivre ce matin ») et l'app remplit le formulaire, qu'il confirme.

**Pourquoi** : saisir sans lire ni écrire, les mains occupées.
**Test indépendant** : dicter des phrases en darija, arabe et français et vérifier le pré-remplissage.

**Scénarios d'acceptation** :

1. **Étant donné** une phrase dictée en darija, **Quand** l'app la comprend, **Alors** le formulaire est pré-rempli et l'agriculteur confirme avant enregistrement.
2. **Étant donné** une phrase dont une partie est ambiguë (parcelle, produit), **Quand** l'app l'analyse, **Alors** les champs incertains sont signalés et proposés au choix, sans être devinés en silence.
3. **Étant donné** une phrase non comprise, **Quand** l'analyse échoue, **Alors** le formulaire vide s'ouvre avec un message clair, la saisie par icônes restant possible.
4. **Étant donné** une dictée, **Quand** l'agriculteur ne confirme pas, **Alors** aucune opération n'est enregistrée.

---

### Récit 6 — Exporter le registre des traitements (Priorité : P2)

L'agriculteur exporte le registre des traitements d'une parcelle ou de la ferme en PDF et Excel, et l'envoie par WhatsApp.

**Pourquoi** : répondre à une coopérative, un exportateur ou un auditeur sans ressaisie.
**Test indépendant** : exporter le registre d'une parcelle puis de la ferme, ouvrir les fichiers et vérifier les colonnes.

**Scénarios d'acceptation** :

1. **Étant donné** une demande d'export du registre, **Quand** le PDF est généré, **Alors** il contient pour chaque traitement : date, parcelle, culture, produit, matière active, dose, surface, opérateur.
2. **Étant donné** un traitement enregistré avec avertissement, **Quand** le registre est exporté, **Alors** l'avertissement y figure.
3. **Étant donné** un export généré, **Quand** l'agriculteur choisit WhatsApp, **Alors** le fichier est proposé au partage.
4. **Étant donné** le même registre, **Quand** il est exporté en Excel, **Alors** il contient les mêmes lignes et colonnes que le PDF.
5. **Étant donné** une période ou une parcelle choisie, **Quand** l'export est demandé, **Alors** seuls les traitements concernés y figurent.

---

### Récit 7 — Opération d'un ouvrier validée par le gestionnaire (Priorité : P2)

Un ouvrier enregistre une opération ; le gestionnaire la voit et peut la valider.

**Pourquoi** : déléguer la saisie en gardant un journal fiable.
**Test indépendant** : un ouvrier saisit, un gestionnaire valide ou corrige.

**Scénarios d'acceptation** :

1. **Étant donné** un ouvrier membre de la ferme, **Quand** il enregistre une opération, **Alors** elle apparaît chez le gestionnaire comme « à valider », avec l'ouvrier comme opérateur.
2. **Étant donné** une opération à valider, **Quand** le gestionnaire la valide, **Alors** son statut devient « validée ».
3. **Étant donné** une opération validée, **Quand** elle est corrigée, **Alors** la correction est enregistrée et l'historique des corrections (qui, quand, valeur avant et après) reste consultable.
4. **Étant donné** un ouvrier, **Quand** il consulte le journal, **Alors** il n'accède qu'à ce que son rôle autorise.

---

### Cas limites

- Produit absent du catalogue : saisie d'un produit libre, enregistrée sans contrôle d'homologation et signalée comme telle dans le registre.
- Opération couvrant des parcelles de cultures différentes : les contrôles s'appliquent parcelle par parcelle.
- Date dans le passé lointain ou le futur : acceptée (saisie tardive, planification) ; la date future crée une opération planifiée.
- Conflit entre deux appareils modifiant la même opération hors ligne : aucune donnée perdue, les deux versions apparaissent dans l'historique.
- Catalogue de produits non à jour hors ligne : la date de dernière mise à jour est affichée avec les contrôles.
- Parcelle archivée ou fusionnée après une opération : l'opération reste lisible dans le journal et le registre.
- Dose saisie dans une unité différente de celle du catalogue : conversion affichée avant validation.

## Clarifications

### Session 2026-11-07

- Aucune question ouverte : le CPS section 11 couvre le périmètre. Les choix par défaut sont consignés dans les hypothèses.

## États et RTL des écrans *(obligatoire)*

Pour chaque écran, les quatre états sont conçus : chargement (squelettes, jamais d'écran blanc), vide (illustration et action proposée), erreur (message clair et solution), hors ligne (indicateur de ce qui n'est pas encore envoyé). Toute mise en page est en miroir complet en arabe et darija en graphie arabe (sens de lecture, icônes directionnelles, alignements, saisie de nombres et de dates).

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| Journal des opérations | Squelette de liste | Illustration, action « Noter ma première opération » | Message et « Réessayer » | Opérations locales affichées, badge « à envoyer » par ligne |
| Choix du type (icônes) | Squelette de grille d'icônes | Non applicable : les types sont toujours présents | Message et « Réessayer » | Identique en ligne, aucune dépendance au réseau |
| Formulaire d'opération | Squelette des champs | Aucune parcelle : action « Ajouter une parcelle » | Champ invalide signalé près du champ, avec solution | Saisie possible, enregistrement local, indicateur d'attente |
| Traitement phyto (produit, dose, contrôles) | Indicateur de recherche | Aucun produit trouvé : proposition de produit libre ou de photo | Contrôle impossible : message clair, enregistrement possible | Catalogue local avec date de mise à jour ; reconnaissance de photo indisponible signalée, recherche par nom disponible |
| Reconnaissance de l'étiquette | Indicateur d'analyse | Consigne illustrée de prise de photo | Photo illisible : conseil et reprise | Photo conservée, reconnaissance reportée au retour du réseau |
| Date de récolte au plus tôt (fiche parcelle) | Squelette | Aucun traitement : « Récoltable dès maintenant » | Message et « Réessayer » | Date calculée sur les données locales |
| Opérations planifiées et rappels | Squelette | Aucune opération planifiée : action « Planifier » | Message et « Réessayer » | Planification et rappels locaux fonctionnels |
| Dictée vocale | Indicateur d'écoute puis d'analyse | Consigne illustrée « Dis ce que tu as fait » | Phrase non comprise : message et formulaire vide | Dictée enregistrée et analysée au retour du réseau, saisie par icônes proposée en attendant |
| Validation par le gestionnaire | Squelette | Aucune opération à valider | Message et « Réessayer » | Liste locale, validation enregistrée localement |
| Historique des corrections | Squelette | Aucune correction | Message et « Réessayer » | Historique local consultable |
| Export du registre | Indicateur de génération | Aucun traitement sur la période : explication | Échec de génération : cause et « Réessayer » | Génération sur données locales si possible, sinon mise en attente et mention claire |

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : Le système DOIT permettre d'enregistrer une opération des types : traitement phyto, fertilisation, irrigation, travail du sol, semis ou plantation, taille, désherbage, récolte, autre, choisis par icône.
- **FR-002** : Les seuls champs obligatoires DOIVENT être le type, la parcelle et la date ; tous les autres sont optionnels.
- **FR-003** : Pour un traitement phyto, le système DOIT demander le produit et la dose sans les rendre obligatoires.
- **FR-004** : Une opération DOIT pouvoir couvrir plusieurs parcelles ; les quantités sont réparties au prorata de la surface.
- **FR-005** : Le système DOIT proposer la recherche de produit par nom et par photo de l'étiquette dans le catalogue des produits homologués.
- **FR-006** : Le système DOIT contrôler, pour chaque traitement et chaque parcelle : homologation au Maroc pour la culture, dose maximale, nombre maximal d'applications, délai avant récolte.
- **FR-007** : Les contrôles phyto DOIVENT n'émettre que des avertissements, jamais un blocage ; chaque avertissement ignoré DOIT être conservé dans le registre.
- **FR-008** : Le système DOIT calculer et afficher pour chaque parcelle la date de récolte au plus tôt, selon le délai avant récolte le plus long restant.
- **FR-009** : Une date future DOIT créer une opération « planifiée » ; le système DOIT envoyer un rappel le jour venu et permettre de la marquer « faite ».
- **FR-010** : Le système DOIT permettre de dicter une opération en darija, arabe ou français, pré-remplir le formulaire et exiger la confirmation avant enregistrement.
- **FR-011** : Le système DOIT permettre d'exporter le registre des traitements d'une parcelle ou de la ferme en PDF et en Excel, et de les partager par WhatsApp.
- **FR-012** : Chaque ligne exportée DOIT contenir : date, parcelle, culture, produit, matière active, dose, surface, opérateur, ainsi que les éventuels avertissements.
- **FR-013** : Un ouvrier DOIT pouvoir enregistrer une opération ; le gestionnaire DOIT la voir et pouvoir la valider.
- **FR-014** : Une opération validée DOIT rester corrigeable ; chaque correction DOIT être historisée (auteur, date, valeurs avant et après).
- **FR-015** : Le journal DOIT fournir les opérations « faites » au calcul des coûts (F8) et au bilan hydrique (F4).
- **FR-016** : Toute saisie et consultation du journal DOIT fonctionner sans réseau, sans perte de donnée à la synchronisation, avec un indicateur de ce qui n'est pas encore envoyé.
- **FR-017** : Aucune recommandation de produit non homologué au Maroc pour l'usage ne DOIT être faite ; un produit libre est signalé comme non contrôlé.
- **FR-018** : L'accès aux opérations DOIT respecter la ferme et le rôle de l'utilisateur, côté serveur ; les données ne sont partagées qu'avec accord explicite et révocable.
- **FR-019** : Aucun texte d'interface en dur ; les trois langues (darija, arabe, français) et le RTL complet sont requis, avec lecture vocale des écrans.
- **FR-020** : Chaque écran DOIT avoir ses quatre états conçus, des boutons d'au moins 48 dp et un contraste lisible en plein soleil.

### Entités principales

- **Operation** : type, date, parcelles, produits, quantités, opérateur, statut (planifiée, faite, à valider, validée), avertissements ; rattachée à une ferme, n-n avec les parcelles.
- **Produit phyto (référentiel)** : nom, matière active, usages culture × cible, dose maximale, DAR, nombre maximal d'applications ; maintenu par l'équipe AYLAL, source Index ONSSA (catalogue PhytoIndex).
- **Correction** : opération concernée, auteur, date, valeurs avant et après.
- **Rappel** : opération planifiée, jour de déclenchement, état.
- **Registre** : vue exportable des traitements d'une parcelle ou de la ferme.

## Hors périmètre

- Certification officielle.
- Gestion de la paie des ouvriers.
- Calcul des coûts (F8) et du bilan hydrique (F4) : seule la fourniture des opérations est ici.
- Recommandation de traitement (relève du diagnostic F5).

## Critères de réussite *(obligatoire)*

- **SC-001** : Un utilisateur entraîné enregistre une opération en moins de 15 secondes.
- **SC-002** : 100 % des traitements dépassant dose, homologation ou nombre d'applications déclenchent un avertissement, et 100 % de ces avertissements figurent dans le registre.
- **SC-003** : La date de récolte au plus tôt est exacte dans 100 % des cas de test de délais avant récolte, y compris plusieurs produits.
- **SC-004** : Aucune opération saisie hors ligne pendant 30 jours n'est perdue à la synchronisation.
- **SC-005** : Le PDF et l'Excel contiennent 100 % des colonnes exigées pour chaque traitement.
- **SC-006** : Au moins 4 agriculteurs sur 5 réussissent à enregistrer un traitement sans aide lors du test de prototype.
- **SC-007** : Chaque écran est vérifié dans les trois langues et dans ses quatre états, sans texte en dur ni mise en page cassée en RTL.

## Hypothèses

- La ferme, les rôles (propriétaire, gestionnaire, ouvrier) et les parcelles existent déjà (F1, F2).
- Le catalogue de produits est le référentiel AYLAL issu de l'Index ONSSA ; il est disponible hors ligne avec sa date de mise à jour.
- L'opérateur par défaut est l'utilisateur qui saisit ; il peut être remplacé par un autre membre ou un nom libre.
- Une opération saisie par un propriétaire ou un gestionnaire est considérée validée d'emblée ; seule celle d'un ouvrier passe par « à valider ».
- Le décompte des applications se fait par campagne et par produit.
- La dictée et la reconnaissance d'étiquette réutilisent l'assistant vocal et la vision de F7/F5 lorsqu'ils existent ; en leur absence la saisie par icônes reste complète.
- Aucune question ouverte : le CPS section 11 couvre le périmètre.
