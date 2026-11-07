# Spécification de fonctionnalité : F1 — Compte, onboarding et ferme

**Branche** : `002-account-onboarding-farm`
**Créé le** : 2026-11-07
**Statut** : Brouillon
**Entrée** : Fonctionnalité F1. Source de vérité : `docs/cps/AYLAL-CPS.md` section 6 ; contexte sections 1 à 3 ; données section 17 (entités User, Farm, Membership) ; exigences transverses section 15. Dépend de F0 (fondations).

## Objectif

Un agriculteur installe AYLAL et a créé son compte et sa ferme en moins de 2 minutes, sans e-mail ni mot de passe. Cette fonctionnalité est la porte d'entrée de toutes les autres (F2 à F9) : sans compte vérifié et sans ferme, aucune parcelle ni opération ne peut exister.

## Clarifications

### Session 2026-11-07 (mode autonome, réponses tirées du CPS sections 4, 15, 16, 19 et de la constitution)

- Q : Canal d'envoi du code ? -> R : SMS par défaut, WhatsApp en alternative si disponible ; aucun mot de passe ni e-mail (gratuité et simplicité).
- Q : Comportement hors ligne à l'inscription ? -> R : la vérification du code exige le réseau ; une fois connecté, la session et la création de ferme fonctionnent hors ligne (SQLite local, synchronisation ensuite).
- Q : Durée de session ? -> R : persistante jusqu'à déconnexion volontaire ; le code local à 4 chiffres est optionnel et stocké uniquement sur l'appareil.
- Q : Langue par défaut ? -> R : choix explicite au premier écran (darija, arabe, français), modifiable ensuite ; aucune langue imposée.
- Aucun marqueur [NEEDS CLARIFICATION] ne subsiste dans cette spécification.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Je m'inscris avec mon numéro de téléphone et un code (Priorité : P1)

En tant qu'agriculteur, je m'inscris avec mon numéro de téléphone et un code reçu par SMS ou WhatsApp, pour ne pas avoir à retenir de mot de passe.

**Pourquoi cette priorité** : sans compte vérifié, rien d'autre n'est possible ; l'absence de mot de passe est la condition pour servir un agriculteur qui lit peu.

**Test indépendant** : sur un téléphone neuf, saisir un numéro puis le code reçu et vérifier qu'un compte existe et que l'écran de création de ferme s'affiche.

**Scénarios d'acceptation** :

1. **Étant donné** un nouvel utilisateur, **Quand** il saisit son numéro et le code reçu, **Alors** son compte est créé et il arrive sur la création de ferme.
2. **Étant donné** un code erroné trois fois, **Quand** il réessaie, **Alors** un délai d'attente de 5 minutes s'applique.
3. **Étant donné** un utilisateur déjà inscrit, **Quand** il saisit son numéro et le bon code, **Alors** il retrouve son compte existant (aucun doublon n'est créé) et arrive sur ses fermes.
4. **Étant donné** une session ouverte, **Quand** l'application est fermée puis rouverte, ou le téléphone redémarré, **Alors** l'utilisateur reste connecté jusqu'à déconnexion volontaire.
5. **Étant donné** un utilisateur connecté, **Quand** il active un code d'accès local à 4 chiffres, **Alors** ce code lui est demandé à l'ouverture de l'application ; l'activer reste optionnel.

---

### Récit 2 — Je choisis ma langue au premier écran, avec une voix (Priorité : P1)

En tant qu'agriculteur, je choisis ma langue (darija, arabe, français) au premier écran, avec une voix qui lit les options.

**Pourquoi cette priorité** : principe « l'agriculteur d'abord » ; la langue conditionne la compréhension de tous les écrans suivants.

**Test indépendant** : ouvrir l'application pour la première fois, écouter les options, choisir chaque langue et vérifier que l'écran suivant est dans cette langue et le bon sens de lecture.

**Scénarios d'acceptation** :

1. **Étant donné** la première ouverture de l'application, **Quand** le premier écran s'affiche, **Alors** il propose darija, arabe et français, chaque option étant lisible à voix haute.
2. **Étant donné** le choix de la darija, de l'arabe ou du français, **Quand** l'utilisateur valide, **Alors** tous les écrans suivants s'affichent dans cette langue, en miroir RTL complet pour l'arabe et la darija en graphie arabe.
3. **Étant donné** un utilisateur connecté, **Quand** il change de langue dans son profil, **Alors** la nouvelle langue s'applique immédiatement et est conservée sur son compte.

---

### Récit 3 — Je donne mon consentement et mon profil minimal (Priorité : P1)

En tant qu'agriculteur, je lis (ou j'écoute) la politique de données et je donne mon consentement explicite ; je renseigne seulement un nom ou un surnom.

**Pourquoi cette priorité** : la conformité à la loi 09-08 et le principe « ses données lui appartiennent » interdisent de créer un compte sans consentement explicite.

**Test indépendant** : refuser le consentement et vérifier que le compte n'est pas finalisé ; l'accepter, saisir un surnom et vérifier que le profil est créé avec les consentements horodatés.

**Scénarios d'acceptation** :

1. **Étant donné** un nouvel utilisateur ayant vérifié son numéro, **Quand** l'écran de consentement s'affiche, **Alors** la politique de données est affichée dans sa langue et peut être lue à voix haute sur demande.
2. **Étant donné** l'écran de consentement, **Quand** l'utilisateur ne donne pas son consentement, **Alors** il ne peut pas poursuivre et aucune donnée personnelle au-delà du numéro vérifié n'est conservée.
3. **Étant donné** le consentement donné, **Quand** l'utilisateur saisit un nom ou un surnom, **Alors** le profil est créé ; âge, statut foncier et toute autre information ne sont jamais exigés.

---

### Récit 4 — Je crée ma ferme (Priorité : P1)

En tant qu'agriculteur, je crée ma ferme : nom, commune ou douar (choisi sur la carte ou par ma position), surface approximative.

**Pourquoi cette priorité** : la ferme est le rattachement de toutes les données (section 17) ; l'objectif de 2 minutes et l'indicateur « parcelle créée en moins de 10 minutes » en dépendent.

**Test indépendant** : depuis un compte neuf, créer une ferme par la position puis une autre en choisissant un point sur la carte ; vérifier que l'utilisateur en est propriétaire.

**Scénarios d'acceptation** :

1. **Étant donné** un utilisateur sans ferme, **Quand** il saisit un nom, choisit sa commune ou son douar par sa position et indique une surface approximative, **Alors** la ferme est créée et il en est le propriétaire unique.
2. **Étant donné** la création de ferme, **Quand** l'utilisateur choisit son emplacement sur la carte au lieu de sa position, **Alors** la commune correspondante est identifiée et enregistrée avec la ferme.
3. **Étant donné** un appareil sans réseau, **Quand** l'utilisateur crée sa ferme, **Alors** elle est enregistrée localement, utilisable immédiatement, et indiquée comme non encore envoyée jusqu'à la synchronisation.
4. **Étant donné** un nouvel utilisateur, **Quand** il parcourt le parcours complet (langue, numéro, code, consentement, surnom, ferme), **Alors** il le termine en moins de 2 minutes.
5. **Étant donné** que la surface est approximative, **Quand** l'utilisateur ne la renseigne pas, **Alors** la ferme peut être créée quand même (seuls le nom et l'emplacement sont requis).

---

### Récit 5 — Je gère plusieurs fermes (Priorité : P2)

En tant qu'agriculteur, je peux gérer plusieurs fermes et passer de l'une à l'autre.

**Pourquoi cette priorité** : utile aux exploitants à plusieurs sites, mais le lancement fonctionne avec une seule ferme.

**Test indépendant** : créer deux fermes, basculer de l'une à l'autre et vérifier que seules les données de la ferme active sont affichées.

**Scénarios d'acceptation** :

1. **Étant donné** un utilisateur propriétaire d'une ferme, **Quand** il ajoute une deuxième ferme, **Alors** il en est le propriétaire et peut choisir laquelle est active.
2. **Étant donné** plusieurs fermes, **Quand** il passe de l'une à l'autre, **Alors** l'application affiche uniquement les données de la ferme choisie, y compris hors ligne.
3. **Étant donné** un utilisateur membre d'une ferme dont il n'est pas propriétaire, **Quand** il ouvre le sélecteur de fermes, **Alors** la ferme apparaît avec son rôle.

---

### Récit 6 — J'invite un membre de mon équipe avec un rôle (Priorité : P2)

En tant que propriétaire, j'invite un membre de mon équipe par son numéro, avec un rôle : gestionnaire (tout voir, tout modifier) ou ouvrier (enregistrer des opérations sur les parcelles qui lui sont confiées).

**Pourquoi cette priorité** : nécessaire pour Youssef et Rachid (section 2), mais pas pour l'agriculteur seul du lancement.

**Test indépendant** : inviter un numéro comme ouvrier, se connecter avec ce numéro et vérifier la portée de ses droits.

**Scénarios d'acceptation** :

1. **Étant donné** un ouvrier invité, **Quand** il se connecte, **Alors** il ne voit que les parcelles qui lui sont attribuées et ne voit aucun montant financier.
2. **Étant donné** un propriétaire, **Quand** il invite un numéro comme gestionnaire, **Alors** cette personne peut tout voir et tout modifier dans la ferme, sans pouvoir ni supprimer la ferme ni changer son propriétaire.
3. **Étant donné** une invitation envoyée à un numéro sans compte, **Quand** la personne s'inscrit avec ce numéro, **Alors** elle rejoint la ferme avec le rôle prévu.
4. **Étant donné** un membre de la ferme, **Quand** le propriétaire retire son accès, **Alors** il ne voit plus aucune donnée de cette ferme dès sa prochaine synchronisation.
5. **Étant donné** un propriétaire, **Quand** il change le rôle d'un membre, **Alors** les nouveaux droits s'appliquent à la prochaine synchronisation de ce membre.

---

### Récit 7 — Je change de téléphone et retrouve mes données (Priorité : P3)

En tant qu'agriculteur, je change de téléphone et retrouve toutes mes données avec mon numéro.

**Pourquoi cette priorité** : confort et réassurance (« aucune donnée perdue »), non bloquant pour le lancement.

**Test indépendant** : se connecter avec le même numéro sur un second appareil et vérifier que fermes et profil sont restaurés.

**Scénarios d'acceptation** :

1. **Étant donné** un compte dont les données ont été synchronisées, **Quand** l'utilisateur se connecte avec son numéro et le code sur un nouvel appareil, **Alors** son profil, ses fermes et ses rôles sont restaurés.
2. **Étant donné** des données créées hors ligne et jamais synchronisées sur l'ancien appareil, **Quand** l'utilisateur change d'appareil, **Alors** l'application l'avertit que ces données ne sont pas encore envoyées.

---

### Récit 8 — Je supprime mon compte (Priorité : P1)

En tant qu'agriculteur, je demande la suppression de mon compte et de mes données (principe « ses données lui appartiennent », loi 09-08).

**Pourquoi cette priorité** : obligation légale et constitutionnelle ; critère d'acceptation P1 de la section 6.

**Test indépendant** : demander la suppression, confirmer, puis vérifier la déconnexion immédiate et la disparition des données personnelles dans le délai.

**Scénarios d'acceptation** :

1. **Étant donné** un utilisateur qui demande la suppression de son compte, **Quand** il confirme, **Alors** toutes ses données personnelles sont supprimées sous 30 jours.
2. **Étant donné** une demande de suppression confirmée, **Quand** elle est enregistrée, **Alors** l'utilisateur est déconnecté et informé de la date limite de suppression effective.
3. **Étant donné** un propriétaire de ferme avec d'autres membres, **Quand** il demande la suppression, **Alors** il est averti des conséquences pour la ferme et les membres avant de confirmer.

---

### Cas limites

- Numéro saisi invalide ou non marocain : refus avec message clair ; format local (06…, 07…) et international acceptés pour un numéro marocain.
- Code expiré ou jamais reçu : l'utilisateur peut demander un nouveau code (par SMS ou WhatsApp), avec un délai minimal entre deux envois.
- Trois codes erronés : délai de 5 minutes, y compris si l'application est fermée et rouverte ; le délai est appliqué par le serveur, pas seulement par l'interface.
- Premier code demandé sans réseau : l'inscription exige le réseau pour vérifier le numéro ; un message l'explique et propose de réessayer.
- Géolocalisation refusée ou indisponible : l'utilisateur choisit sur la carte ou par liste de régions, provinces, communes.
- Carte indisponible hors ligne : repli sur la liste hiérarchique (région, province, commune).
- Deux appareils connectés au même compte : les deux fonctionnent ; les modifications se synchronisent sans perte.
- Ouvrier sans aucune parcelle attribuée : il voit un état vide expliquant qu'il doit demander au propriétaire ou au gestionnaire.
- Invitation d'un numéro déjà membre de la ferme : refusée avec un message clair.
- Utilisateur qui quitte l'onboarding en cours de route : il reprend là où il s'était arrêté.
- Code d'accès local oublié : l'utilisateur peut se reconnecter par son numéro et un nouveau code ; ses données ne sont pas perdues.
- Nom de ferme en arabe, en latin ou mixte : accepté et affiché correctement dans tous les sens de lecture.

## Écrans, quatre états et exigences RTL *(obligatoire)*

Pour chaque écran : **Chargement** = squelette, jamais d'écran blanc ; **Vide** = illustration et action proposée ; **Erreur** = message clair et solution ; **Hors ligne** = indicateur lisible de ce qui est possible et de ce qui est en attente d'envoi. Tous les écrans sont maquettés en arabe et en français, avec boutons d'au moins 48 dp, textes lisibles à voix haute, parcours réalisable sans lire (icônes et voix).

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| E1 Choix de la langue | Squelette des trois options pendant la lecture des préférences | Si la langue de l'appareil est inconnue, les trois options sont proposées sans présélection | Voix indisponible : options toujours lisibles, message discret | Fonctionne entièrement ; aucun réseau requis |
| E2 Saisie du numéro | Squelette du champ et du bouton pendant l'envoi du code | Champ vide avec exemple de numéro et icône explicative | Numéro invalide, code non envoyé ou trop de demandes : message et action (corriger, réessayer plus tard) | Message « réseau requis pour vérifier votre numéro » avec bouton Réessayer ; saisie conservée |
| E3 Saisie du code | Indicateur de vérification, saisie bloquée brièvement | Cases vides, minuteur de renvoi, bouton Renvoyer | Code erroné (compteur d'essais), code expiré, délai de 5 minutes avec compte à rebours | Message « réseau requis » ; saisie conservée jusqu'au retour du réseau |
| E4 Consentement | Squelette du texte de la politique | Sans objet : la politique est toujours affichée (texte intégré à l'application) | Lecture vocale en échec : texte lisible, bouton Réessayer | Texte et lecture vocale disponibles sans réseau ; le consentement est enregistré localement puis envoyé |
| E5 Profil minimal | Squelette du champ nom ou surnom | Champ vide avec invitation et possibilité d'utiliser un surnom | Nom trop long ou caractères refusés : message précis | Fonctionne ; enregistrement local puis synchronisation |
| E6 Création de ferme | Squelette de la carte et des champs ; position en cours de recherche | Carte centrée sur le pays, champs vides, choix « ma position » ou « la carte » | Position refusée ou introuvable, commune non identifiée : repli sur la liste région, province, commune | Carte non disponible : liste hiérarchique ; ferme créée localement avec mention « en attente d'envoi » |
| E7 Sélecteur de fermes | Squelette de la liste de fermes | Aucune ferme : illustration et bouton « Créer ma ferme » | Liste non chargée : message et bouton Réessayer, fermes locales toujours affichées | Fermes déjà chargées affichées avec l'indicateur d'envoi en attente |
| E8 Équipe de la ferme | Squelette de la liste des membres | Aucun membre invité : illustration et bouton « Inviter » | Numéro invalide, déjà membre, invitation non envoyée : message et solution | Consultation possible ; invitation et changement de rôle mis en attente et clairement indiqués |
| E9 Invitation (numéro et rôle) | Indicateur d'envoi | Champs vides, choix du rôle gestionnaire ou ouvrier expliqués par icône et voix | Échec d'envoi ou rôle manquant : message et action | Invitation conservée en attente d'envoi |
| E10 Accès des ouvriers aux parcelles | Squelette de la liste des parcelles | Aucune parcelle disponible (F2 non encore utilisé) : message expliquant que l'attribution viendra avec les parcelles | Échec d'enregistrement de l'attribution : message et nouvelle tentative | Attribution enregistrée localement, en attente d'envoi |
| E11 Profil et paramètres (langue, code d'accès, déconnexion) | Squelette du profil | Profil minimal affiché ; code d'accès « désactivé » proposé | Échec de mise à jour : message et nouvelle tentative | Fonctionne ; modifications synchronisées au retour du réseau |
| E12 Suppression du compte | Indicateur pendant l'enregistrement de la demande | Explication de ce qui sera supprimé et du délai de 30 jours | Échec de la demande : message et solution, rien n'est supprimé à moitié | Demande mise en attente et clairement indiquée ; elle prend effet dès l'envoi |
| E13 Accueil après connexion sur un nouvel appareil | Squelette pendant la restauration des fermes | Aucune ferme associée au numéro : proposition de créer sa ferme | Restauration en échec : message et nouvelle tentative, aucune donnée perdue | Sans réseau, message expliquant que les données seront restaurées à la reconnexion |

**Exigences RTL (communes à tous les écrans)**

- En arabe et en darija (graphie arabe), mise en page en miroir complet : sens de lecture, alignements, ordre des cases du code, icônes directionnelles (retour, suivant).
- Les numéros de téléphone, chiffres et noms en lettres latines restent lisibles et correctement orientés dans un texte RTL.
- Le sélecteur de langue lui-même respecte le sens de lecture de la langue courante et affiche chaque langue dans sa propre graphie.
- Les textes longs (politique de données, noms de communes) et courts sont testés dans les trois langues ; aucun texte tronqué ni chevauchement.
- La carte et ses commandes (position, zoom, confirmation) sont placées selon le sens de lecture.
- Chaque écran est vérifié en arabe et en français par une capture de référence.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

**Compte et connexion**

- **FR-001** : Le système DOIT identifier un compte par un numéro de téléphone vérifié ; un numéro correspond à un seul compte.
- **FR-002** : Le système DOIT vérifier le numéro par un code à usage unique envoyé par SMS ou WhatsApp, sans e-mail ni mot de passe.
- **FR-003** : Le système DOIT limiter les tentatives : après trois codes erronés, un délai d'attente de 5 minutes s'applique, appliqué côté serveur.
- **FR-004** : Le système DOIT maintenir la session ouverte sur l'appareil jusqu'à déconnexion volontaire.
- **FR-005** : Le système DOIT proposer un code d'accès local à 4 chiffres, strictement optionnel, activable et désactivable par l'utilisateur.
- **FR-006** : Le système DOIT créer le compte à la première vérification réussie et orienter le nouvel utilisateur vers la création de ferme.
- **FR-007** : Le système DOIT permettre de se déconnecter volontairement, et d'effacer alors les données locales de l'appareil après avertissement sur ce qui n'est pas encore envoyé.

**Langue, profil et consentement**

- **FR-008** : Le système DOIT proposer au premier écran le choix entre darija, arabe et français, avec lecture vocale des options.
- **FR-009** : Le système DOIT enregistrer la langue dans le profil et permettre de la modifier à tout moment.
- **FR-010** : Le système DOIT exiger un consentement explicite à la politique de données avant de finaliser le compte, avec lecture vocale sur demande, et enregistrer ce consentement avec sa date et la version du texte.
- **FR-011** : Le profil minimal DOIT se limiter à un nom ou surnom et à la langue ; aucune autre information n'est obligatoire.
- **FR-012** : Le système DOIT permettre de retirer un consentement à tout moment (principe « accord révocable »).

**Ferme**

- **FR-013** : Le système DOIT permettre de créer une ferme avec un nom, un emplacement (commune ou douar choisi sur la carte ou par la position) et une surface approximative facultative.
- **FR-014** : Le système DOIT rattacher chaque ferme à un propriétaire unique et à zéro ou plusieurs membres, chacun avec un rôle.
- **FR-015** : Le système DOIT identifier la commune d'une ferme à partir de la position ou du point choisi, ou, à défaut, via la liste région, province, commune du référentiel géographique.
- **FR-016** : Le système DOIT permettre à un utilisateur d'avoir plusieurs fermes et de choisir la ferme active.
- **FR-017** : Le système DOIT permettre la création de ferme sans réseau et signaler clairement qu'elle est en attente d'envoi.

**Équipe et rôles**

- **FR-018** : Le propriétaire DOIT pouvoir inviter un membre par son numéro avec le rôle gestionnaire ou ouvrier.
- **FR-019** : Le rôle gestionnaire DOIT permettre de tout voir et tout modifier dans la ferme, sauf supprimer la ferme et changer son propriétaire.
- **FR-020** : Le rôle ouvrier DOIT permettre uniquement d'enregistrer des opérations sur les parcelles qui lui sont attribuées ; il ne voit que ces parcelles et aucun montant financier.
- **FR-021** : Le contrôle d'accès par ferme et par rôle DOIT être appliqué côté serveur, indépendamment de l'interface.
- **FR-022** : Le propriétaire DOIT pouvoir modifier le rôle d'un membre, lui attribuer ou retirer des parcelles et retirer son accès ; les changements s'appliquent à la prochaine synchronisation.
- **FR-023** : Une invitation destinée à un numéro sans compte DOIT être honorée à l'inscription de cette personne.

**Données, vie privée et appareils**

- **FR-024** : Le système DOIT restaurer profil, fermes et rôles lorsqu'un utilisateur se connecte avec son numéro sur un nouvel appareil.
- **FR-025** : Le système DOIT permettre la suppression du compte sur demande ; après confirmation, toutes les données personnelles sont supprimées sous 30 jours.
- **FR-026** : Le système DOIT permettre l'export complet des données personnelles de l'utilisateur à sa demande.
- **FR-027** : Le système DOIT chiffrer les données en transit et au repos, y compris sur le téléphone, et héberger et traiter les données au Maroc.
- **FR-028** : Le système DOIT fonctionner hors ligne pour tout sauf la vérification initiale du numéro, et ne jamais perdre une donnée à la synchronisation ; ce qui n'est pas encore envoyé est signalé.
- **FR-029** : Chaque écran DOIT disposer des quatre états (chargement, vide, erreur, hors ligne) et respecter les exigences RTL ci-dessus ; aucun texte d'interface n'est en dur.
- **FR-030** : Le système DOIT rester gratuit pour l'agriculteur : aucune fonction de F1 n'est soumise à paiement.

### Entités clés

- **User** : numéro de téléphone vérifié, nom ou surnom, langue, consentements (date, version), état de la demande de suppression.
- **Farm** : nom, emplacement (point, commune), surface approximative, propriétaire unique.
- **Membership** : lien entre un utilisateur et une ferme avec un rôle (propriétaire, gestionnaire, ouvrier) et, pour un ouvrier, la liste des parcelles attribuées.
- **Invitation** : numéro invité, rôle prévu, ferme, état (en attente, acceptée, annulée).
- **Géographie (référentiel)** : régions, provinces, communes, découpage administratif officiel.

## Critères de réussite *(obligatoire)*

### Résultats mesurables

- **SC-001** : Un nouvel utilisateur termine langue, numéro, code, consentement, surnom et création de ferme en moins de 2 minutes (cible : 90 % des essais de recette).
- **SC-002** : 80 % des inscrits créent une parcelle en moins de 10 minutes après l'inscription (indicateur du CPS section 1, F1 en est le premier tronçon).
- **SC-003** : Au moins 4 agriculteurs sur 5 réussissent le parcours d'inscription et de création de ferme sans aide lors du test du prototype.
- **SC-004** : 100 % des critères d'acceptation P1 ci-dessus sont couverts par au moins un test automatisé.
- **SC-005** : Aucun ouvrier ne voit de parcelle non attribuée ni de montant financier : 0 cas dans les tests d'accès.
- **SC-006** : Après trois codes erronés, 100 % des nouvelles tentatives sont refusées pendant 5 minutes.
- **SC-007** : 100 % des données de compte supprimées dans les 30 jours suivant la confirmation.
- **SC-008** : Aucune donnée créée hors ligne n'est perdue après synchronisation (0 perte dans les tests de reprise réseau).
- **SC-009** : Les écrans s'affichent dans les trois langues sans clé manquante ni texte en dur, avec miroir RTL correct en arabe.

## Hors périmètre

- Connexion par e-mail ou réseaux sociaux.
- Vérification d'identité (CIN) et titres fonciers.
- Création des parcelles et des cultures (F2) ; l'attribution fine des parcelles aux ouvriers s'appuie sur F2 et n'a de contenu qu'une fois des parcelles créées.
- Partage avec conseillers, coopératives et capteurs (F9).
- Montants financiers, dépenses et stocks (F8) : F1 garantit seulement qu'un ouvrier n'y a pas accès.
- Amazighe (envisagé en phase 3).

## Hypothèses

- Le code à usage unique est numérique, valable quelques minutes ; le canal (SMS ou WhatsApp) est choisi par l'utilisateur, avec repli sur l'autre canal si l'un échoue.
- Le numéro de téléphone est marocain pour le lancement ; les autres pays ne sont pas pris en charge.
- La vérification initiale du numéro exige le réseau ; tout le reste fonctionne hors ligne (principe 2).
- Un propriétaire ne peut pas être retiré de sa ferme ; le transfert de propriété n'est pas dans F1.
- Une invitation non acceptée expire au bout de 30 jours (valeur par défaut prudente, le CPS est muet).
- La politique de données et son texte sont fournis par l'équipe AYLAL et validés juridiquement (loi 09-08, déclaration CNDP) avant le lancement.
- Le tutoiement ou le vouvoiement est fixé par langue lors de la relecture par un locuteur natif de la darija.
- Les maquettes haute fidélité arabe et français de chaque écran P1 sont validées avant tout développement (principe 10).
- Dépendance : fondations F0 (design system, i18n, synchronisation hors ligne) disponibles.
