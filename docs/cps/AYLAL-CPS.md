# CPS — AYLAL, application gratuite de suivi de ferme pour les agriculteurs marocains

Nov 7, 2026 · @Amine

## 0. Mode d'emploi avec Spec Kit

Ce CPS est écrit pour être découpé directement dans le flux Spec Kit : les principes vont dans la constitution, chaque fonctionnalité F1 à F9 devient une spécification séparée, et seule la section 16 parle de technique.

| Commande Spec Kit | Ce qu'elle attend | Section du CPS à utiliser |
| --- | --- | --- |
| `specify init aylal --ai claude` | Initialiser le dépôt | — |
| `/speckit.constitution` | Principes non négociables du projet | Section 4 (et 15 pour les seuils de qualité) |
| `/speckit.specify` | Le quoi et le pourquoi d'une fonctionnalité, sans technique | Une fonctionnalité à la fois : sections 6 à 14 (F1 … F9), avec 1 à 3 pour le contexte |
| `/speckit.clarify` | Lever les ambiguïtés | Points ouverts de la section 19 |
| `/speckit.plan` | Stack et architecture | Section 16 (multi-front, orientations techniques) et 17 (données) |
| `/speckit.tasks` puis `/speckit.implement` | Découpage et code | Ordre donné par la feuille de route, section 18 |

**Règles d'écriture suivies dans ce document.** Chaque fonctionnalité contient : son objectif, ses récits utilisateur avec priorité (P1 = indispensable au lancement, P2 = lancement si possible, P3 = plus tard), ses règles métier, ses critères d'acceptation au format « Étant donné / Quand / Alors » et ce qui est hors périmètre. C'est la forme que `/speckit.specify` produit et attend.

## 1. Vision, contexte et objectifs

AYLAL est une application gratuite qui permet à chaque agriculteur marocain de suivre sa ferme depuis son téléphone : ses parcelles, ses cultures, l'eau, la santé des plantes, ses opérations et ses dépenses, avec un assistant qui lui parle dans sa langue.

**Problème.** La plupart des exploitations marocaines sont gérées de mémoire ou sur papier. L'agriculteur découvre souvent trop tard un stress hydrique ou une maladie, connaît mal ses coûts réels et ne peut pas prouver ses traitements quand un exportateur ou un auditeur le demande. Les outils existants sont payants, en français ou en anglais, pensés pour des conseillers et non pour l'exploitant.

**Vision.** Une ferme, un téléphone, un tableau de bord : l'agriculteur ouvre AYLAL le matin et sait en 30 secondes quelles parcelles ont besoin de lui aujourd'hui et pourquoi.

**Périmètre des fronts.**

1. Mobile Android en premier (lancement), puis iOS.
2. Web ensuite, pour les grandes exploitations et les gestionnaires de bureau.
3. Desktop en dernier, pour les usages de bureau hors ligne (bureaux de ferme, coopératives).

**Objectifs mesurables à 12 mois après le lancement (hypothèses à valider)**

| Indicateur | Cible |
| --- | --- |
| Agriculteurs inscrits | 20 000 |
| Utilisateurs actifs par mois | 40 % des inscrits |
| Surface suivie | 100 000 ha |
| Parcelle créée après inscription | 80 % des inscrits en moins de 10 minutes |
| Opérations enregistrées par exploitation active | au moins 4 par mois |
| Satisfaction (note store) | ≥ 4,3 / 5 |

## 2. Utilisateurs cibles et personas

La cible principale est l'exploitant lui-même, du petit agriculteur peu lettré au gestionnaire d'une ferme d'export : l'interface doit servir les deux sans mode « expert » séparé.

| Persona | Profil | Ferme | Ce qu'il attend d'AYLAL | Contraintes |
| --- | --- | --- | --- | --- |
| Ahmed, petit agriculteur | 55 ans, lit peu, parle darija | 4 ha, olivier et céréales en pluvial, région de Meknès | Savoir quand traiter et irriguer, comprendre une maladie à partir d'une photo | Smartphone Android d'entrée de gamme, 3G intermittente, préfère la voix au texte |
| Fatima, agricultrice moyenne | 38 ans, bac, arabe et français | 15 ha, agrumes en goutte-à-goutte, Souss | Piloter l'irrigation, suivre ses dépenses, garder la trace des traitements pour la coopérative | Pas de temps pour une saisie longue |
| Youssef, gestionnaire de ferme d'export | 32 ans, ingénieur | 80 ha, tomate sous serre et fruits rouges, Chtouka | Registre phyto conforme pour les audits, vue sur toutes les parcelles, équipe de chefs de culture | A besoin du web et d'exports Excel/PDF |
| Rachid, chef d'équipe | 45 ans, employé de Youssef | — | Enregistrer vite ce qui a été fait dans la journée | Accès limité aux parcelles qui lui sont confiées |

**Utilisateurs secondaires (phase 2).** Conseiller agricole ou technicien de distributeur invité par l'agriculteur ; coopérative qui suit ses adhérents avec leur accord.

**Conséquences de conception.** Icônes et photos plutôt que texte, saisie vocale partout, trois langues (darija écrite en arabe et en lettres latines, arabe standard, français), nombre minimal de champs obligatoires, tout fonctionne sans réseau.

## 3. Modèle économique : comment l'app reste gratuite

Toutes les fonctions de suivi de ferme sont gratuites pour l'agriculteur, sans limite de temps ; le revenu vient d'acteurs tiers et de services optionnels, jamais de la revente de données personnelles.

| Source de revenu | Principe | Phase |
| --- | --- | --- |
| Partenaires professionnels | Distributeurs, coopératives et conseillers paient un abonnement pour suivre les fermes qui les invitent et leur envoyer des conseils | Phase 2 |
| Mise en relation commerciale | Commission sur les achats d'intrants, de matériel d'irrigation ou de prestations passés via l'app | Phase 3 |
| Services premium optionnels | Imagerie haute résolution, expertise humaine à la demande, étude d'irrigation | Phase 2-3 |
| Programmes publics et bailleurs | Projets de digitalisation agricole, assurance, crédit agricole (données agrégées et anonymisées, ou partagées avec accord explicite) | Phase 2-3 |

**Règle de produit.** Une fonction gratuite au lancement ne devient jamais payante pour l'agriculteur. Aucune publicité intrusive dans l'app ; les offres commerciales sont clairement étiquetées et désactivables.

**Contrainte de coût.** La gratuité impose un coût d'exploitation faible par utilisateur : imagerie gratuite (Sentinel-2), météo à faible coût, appels IA limités par utilisateur et par jour, traitements mutualisés. Cible à valider : moins de 1 MAD par utilisateur actif et par mois.

## 4. Principes non négociables (base de la constitution)

Ces principes sont à donner tels quels à `/speckit.constitution` ; toute spécification ou tout plan qui les contredit est refusé.

1. **L'agriculteur d'abord.** Chaque écran doit être utilisable par un agriculteur qui lit peu : icônes, photos, voix, trois langues, un seul objectif par écran.
2. **Hors ligne par défaut.** Toute saisie et toute consultation des données déjà chargées fonctionnent sans réseau ; la synchronisation est invisible et ne perd jamais une donnée.
3. **Gratuit et sobre.** Aucune fonction de suivi n'est payante pour l'agriculteur ; chaque fonctionnalité justifie son coût d'exploitation par utilisateur.
4. **Ses données lui appartiennent.** Rien n'est partagé sans accord explicite et révocable ; export et suppression complets à la demande ; conformité à la loi 09-08.
5. **Conseil prudent et traçable.** Toute recommandation (IA ou règle) indique sa source, son niveau de confiance et ses limites ; aucun produit phyto non homologué au Maroc pour l'usage n'est jamais proposé.
6. **Une seule logique métier, plusieurs fronts.** Mobile, web et desktop partagent le même modèle de données et les mêmes règles ; aucune règle métier n'est codée uniquement dans une interface.
7. **Petits téléphones, petits forfaits.** Performances et consommation de données mesurées sur un Android d'entrée de gamme et une connexion 3G.
8. **Testé avant livré.** Chaque récit P1 a des tests automatisés de ses critères d'acceptation ; chaque version mobile est testée sur le terrain avec au moins 5 agriculteurs.
9. **Code et types en anglais, interface traduite.** Aucun texte d'interface en dur dans le code.
10. **Design extrêmement soigné.** AYLAL vise le niveau des meilleures applications grand public, pas celui d'un logiciel agricole : aucun écran n'est développé sans maquette haute fidélité validée, et aucun écran n'est livré sans revue design (section 15, exigences de design).

## 5. Carte des fonctionnalités et priorités

Neuf fonctionnalités, chacune destinée à une spécification Spec Kit ; le lancement mobile (MVP) contient F1 à F6 et le cœur de F7.

| Code | Fonctionnalité | Valeur pour l'agriculteur | Phase | Dépend de |
| --- | --- | --- | --- | --- |
| F1 | Compte, onboarding et ferme | Entrer dans l'app en 2 minutes avec son numéro de téléphone | MVP | — |
| F2 | Parcelles et cultures | Dessiner ses parcelles et dire ce qui y pousse | MVP | F1 |
| F3 | Tableau de bord et monitoring | Voir chaque matin l'état de chaque parcelle : météo, vigueur satellite, alertes | MVP | F2 |
| F4 | Irrigation et bilan hydrique | Savoir quand et combien irriguer | MVP (conseil simple), Phase 2 (pilotage avancé) | F2, F3 |
| F5 | Santé des cultures | Identifier une maladie ou un ravageur par photo, recevoir les alertes de risque | MVP (alertes), Phase 2 (diagnostic photo) | F2, F3 |
| F6 | Journal des opérations et registre phyto | Noter ce qui est fait sur la ferme et prouver ses traitements | MVP | F2 |
| F7 | Assistant IA vocal | Poser une question à voix haute en darija et obtenir une réponse sur sa ferme | MVP (questions-réponses), Phase 2 (actions) | F2, F6 |
| F8 | Dépenses, stocks, récoltes et prix | Connaître ses coûts et sa marge, suivre les prix | Phase 2 | F6 |
| F9 | Partage, conseillers et capteurs | Inviter son conseiller ou sa coopérative, brancher des capteurs | Phase 2-3 | F1 à F6 |

### Feuille de route décidée le 2026-11-08 (remplace la répartition MVP ci-dessus)

Décision du porteur du projet : livrer d'abord une application mobile utilisable de bout en bout, plutôt que d'ajouter des fonctionnalités sans écran.

- **Version 1** (v1.0.0), dans cet ordre : F0, F1, F2, F6, F3, F4 (serveur et domaine déjà fusionnés) → **design system** (`docs/design/aylal-design-system.md`) → **application mobile v1** : écrans, parcours Maestro et APK ≤ 40 Mo pour F1, F2, F6, F3 et F4 → **F8** (serveur, domaine et écrans).
- **Version 2** : F5 (santé des cultures), F7 (assistant vocal), F9 (partage, conseillers, capteurs), ainsi que les parties « phase 2 » de F4. Les travaux déjà commencés sur F5 et F7 sont conservés sur leurs branches, en pause.
- Tant que F5 n'est pas livrée, l'état d'une parcelle (F3) ne contient pas de composante « risque sanitaire » et le dit sans erreur ; le registre phyto (F6) fonctionne sans F5.
- Données de référence à fournir par une source validée avant la v1 (aucune valeur inventée) : coefficients culturaux et paramètres de sol (F4, FAO-56), catalogue des produits phytosanitaires homologués ONSSA (F6), référentiel des cultures et variétés (F2).

## 6. F1 — Compte, onboarding et ferme

**Objectif.** Un agriculteur installe AYLAL et a créé son compte et sa ferme en moins de 2 minutes, sans e-mail ni mot de passe.

**Récits utilisateur**

- **P1** — En tant qu'agriculteur, je m'inscris avec mon numéro de téléphone et un code reçu par SMS ou WhatsApp, pour ne pas avoir à retenir de mot de passe.
- **P1** — Je choisis ma langue (darija, arabe, français) au premier écran, avec une voix qui lit les options.
- **P1** — Je crée ma ferme : nom, commune ou douar (choisi sur la carte ou par ma position), surface approximative.
- **P2** — Je peux gérer plusieurs fermes et passer de l'une à l'autre.
- **P2** — J'invite un membre de mon équipe par son numéro, avec un rôle : gestionnaire (tout voir, tout modifier) ou ouvrier (enregistrer des opérations sur les parcelles qui lui sont confiées).
- **P3** — Je change de téléphone et retrouve toutes mes données avec mon numéro.

**Règles métier**

- Un compte = un numéro de téléphone vérifié. Une ferme a un propriétaire unique et peut avoir plusieurs membres.
- Une session reste ouverte sur l'appareil jusqu'à déconnexion volontaire ; un code d'accès local à 4 chiffres est optionnel.
- Profil minimal : nom ou surnom, langue. Les autres informations (âge, statut foncier, etc.) ne sont jamais obligatoires.
- Consentement explicite à la politique de données, lu à voix haute si demandé.

**Critères d'acceptation**

- Étant donné un nouvel utilisateur, quand il saisit son numéro et le code reçu, alors son compte est créé et il arrive sur la création de ferme.
- Étant donné un code erroné trois fois, quand il réessaie, alors un délai d'attente de 5 minutes s'applique.
- Étant donné un ouvrier invité, quand il se connecte, alors il ne voit que les parcelles qui lui sont attribuées et ne voit aucun montant financier.
- Étant donné un utilisateur qui demande la suppression de son compte, quand il confirme, alors toutes ses données personnelles sont supprimées sous 30 jours.

**Hors périmètre.** Connexion par e-mail ou réseaux sociaux, vérification d'identité (CIN), titres fonciers.

## 7. F2 — Parcelles et cultures

**Objectif.** L'agriculteur décrit sa ferme parcelle par parcelle : où elle est, ce qui y pousse, comment elle est irriguée. C'est la base de toutes les autres fonctions.

**Récits utilisateur**

- **P1** — Je dessine une parcelle en touchant ses coins sur l'image satellite, ou je fais le tour à pied avec le GPS du téléphone.
- **P1** — Je donne un nom à la parcelle et choisis sa culture dans une liste illustrée (photos des cultures), sa variété si je la connais, et l'année de plantation ou la date de semis.
- **P1** — J'indique le mode d'irrigation : pluvial, gravitaire, aspersion, goutte-à-goutte, pivot ; et si la parcelle est sous serre.
- **P1** — Je vois toutes mes parcelles sur une carte, colorées selon leur état (section 8).
- **P2** — Je découpe une parcelle en blocs ou secteurs d'irrigation, ou je fusionne deux parcelles.
- **P2** — Je démarre une nouvelle campagne sur une parcelle (nouvelle culture, rotation) ; l'historique des campagnes précédentes reste consultable.
- **P3** — J'importe des parcelles depuis un fichier (KML, Shapefile) envoyé par un technicien.

**Règles métier**

- La surface est calculée automatiquement à partir du dessin ; l'agriculteur peut saisir une surface déclarée différente, les deux sont conservées.
- Une campagne = une parcelle × une culture × une période. Une parcelle a au plus une campagne active par culture (cultures associées possibles, ex. olivier + céréales).
- Cultures du référentiel au lancement : olivier, agrumes, céréales (blé dur, blé tendre, orge), tomate, pomme de terre, oignon, fruits rouges, avocatier, palmier dattier, amandier, vigne, betterave, luzerne, maïs fourrager. Ajout d'une culture libre possible.
- Le stade de la culture est estimé automatiquement (date de plantation, cumul de température) et corrigeable par l'agriculteur.
- Une parcelle supprimée est archivée 90 jours avant suppression définitive.

**Critères d'acceptation**

- Étant donné un agriculteur hors réseau, quand il dessine une parcelle par GPS, alors elle est enregistrée localement et synchronisée au retour du réseau.
- Étant donné une parcelle dessinée, quand elle est enregistrée, alors sa surface en hectares s'affiche avec deux décimales.
- Étant donné un dessin qui se croise lui-même, quand l'agriculteur valide, alors l'app le corrige ou lui demande de recommencer, avec une explication visuelle.

**Hors périmètre.** Cadastre et limites légales, conception du réseau d'irrigation (relève d'une autre application de l'écosystème).

## 8. F3 — Tableau de bord et monitoring

**Objectif.** En ouvrant l'app, l'agriculteur voit en 30 secondes quelles parcelles demandent son attention aujourd'hui et pourquoi.

**Récits utilisateur**

- **P1** — Je vois la météo de ma ferme : aujourd'hui et 7 jours (température, pluie, vent, humidité), avec des icônes simples.
- **P1** — Je reçois des alertes météo qui concernent mes cultures : gel, chergui (vent chaud et sec), forte pluie, vent fort déconseillant un traitement.
- **P1** — Pour chaque parcelle, je vois une carte de vigueur satellite et une courbe d'évolution depuis le début de la campagne.
- **P1** — L'app me signale une zone de parcelle dont la vigueur baisse anormalement et me propose d'aller voir (avec guidage GPS jusqu'à la zone).
- **P1** — Chaque parcelle a un état résumé en couleur : vert (rien à faire), orange (à surveiller), rouge (action conseillée), avec la raison en une phrase.
- **P2** — Je compare la vigueur de cette campagne à celle de l'an dernier sur la même parcelle.
- **P2** — Je reçois un résumé vocal de la journée (notification que je peux écouter).

**Règles métier**

- Source satellite par défaut : Sentinel-2 (gratuit, 10 m, environ tous les 5 jours). Une image n'est affichée que si au moins 80 % de la parcelle est sans nuage.
- Indices affichés : vigueur (NDVI), humidité de la végétation (NDMI) ; les noms techniques sont cachés derrière des mots simples (« vigueur », « humidité des plantes »).
- Parcelles de moins de 0,3 ha ou sous serre : l'imagerie est signalée comme peu fiable et l'état repose sur la météo et les observations.
- Seuils d'alerte météo par culture et par stade (ex. gel critique pour l'amandier en floraison).
- L'état d'une parcelle combine : alertes météo, anomalie de vigueur, besoin d'irrigation (F4), risque sanitaire (F5), opérations en retard (F6). Chaque élément explique sa source.

**Critères d'acceptation**

- Étant donné une parcelle créée, quand le traitement initial est terminé, alors l'historique de vigueur des 12 derniers mois s'affiche en moins de 10 minutes.
- Étant donné une prévision de gel à 48 heures sur une culture sensible au stade courant, alors l'agriculteur reçoit une notification la veille avant 18 h.
- Étant donné l'app ouverte hors réseau, alors le tableau de bord affiche les dernières données chargées avec leur date.

**Hors périmètre.** Imagerie drone, thermique ou haute résolution (premium, phase 2), prévision de rendement.

## 9. F4 — Irrigation et bilan hydrique

**Objectif.** L'agriculteur sait chaque jour si une parcelle irriguée a besoin d'eau, combien, et pendant combien de temps faire tourner son installation.

**Récits utilisateur**

- **P1** — Je décris mon installation une fois : débit des goutteurs et écartements (ou débit de la pompe), nombre de secteurs.
- **P1** — Chaque jour, je vois pour chaque parcelle irriguée un conseil simple : « irriguer 2 h 30 aujourd'hui » ou « pas besoin, pluie prévue ».
- **P1** — J'enregistre une irrigation faite en un geste (durée ou volume), ce qui met à jour le bilan.
- **P2** — Je vois le volume d'eau consommé par parcelle et sur la campagne, en m³ et en m³/ha.
- **P2** — J'enregistre l'analyse d'eau de mon puits (salinité) et l'app adapte le conseil (fraction de lessivage).
- **P3** — Un capteur d'humidité du sol ou un compteur connecté corrige le conseil automatiquement (voir F9).

**Règles métier**

- Besoin de la culture calculé par la méthode FAO-56 : évapotranspiration de référence (ET0) issue de la météo × coefficient cultural (Kc) selon la culture et le stade, moins la pluie efficace.
- Bilan hydrique journalier du sol par parcelle (réserve utile selon la texture du sol, défaut prudent si inconnue).
- Durée d'irrigation = besoin net / (efficience du système × débit apporté par m²). Efficience par défaut : goutte-à-goutte 90 %, aspersion 75 %, gravitaire 60 %.
- Le conseil affiche toujours son niveau de confiance et les hypothèses utilisées (détail accessible en un clic).
- Pas de conseil d'irrigation pour les parcelles en pluvial ; à la place, un indicateur de stress hydrique.

**Critères d'acceptation**

- Étant donné une parcelle en goutte-à-goutte dont l'installation est décrite, quand la météo du jour est disponible, alors un conseil de durée s'affiche avant 7 h.
- Étant donné une pluie de plus de 10 mm prévue dans les 24 h, alors le conseil recommande de reporter l'irrigation.
- Étant donné une irrigation enregistrée, alors le bilan et le conseil du lendemain en tiennent compte.

**Hors périmètre.** Commande à distance des vannes et pompes, conception et dimensionnement du réseau, fertigation détaillée.

## 10. F5 — Santé des cultures : diagnostic photo et alertes

**Objectif.** L'agriculteur est prévenu des risques de maladies et de ravageurs avant qu'ils ne frappent, et peut identifier un problème à partir d'une photo.

**Récits utilisateur**

- **P1** — Je reçois une alerte de risque quand la météo favorise une maladie sur ma culture (ex. tavelure et œil de paon sur olivier, mildiou sur tomate et pomme de terre, rouille sur blé).
- **P1** — J'enregistre une observation : je prends une photo, je choisis le problème dans une liste illustrée ou je le décris à la voix ; l'observation est placée sur la carte.
- **P2** — Je prends une photo d'une feuille ou d'un fruit malade et l'app me propose les problèmes les plus probables avec un pourcentage de confiance et des photos de comparaison.
- **P2** — Pour un problème identifié, je vois les moyens de lutte : pratiques culturales, lutte biologique, et produits homologués ONSSA pour cette culture et cette cible, avec dose et délai avant récolte.
- **P2** — Si l'app n'est pas sûre, elle me propose d'envoyer la photo à un expert (service premium ou conseiller invité).
- **P3** — Je vois les signalements anonymes des fermes voisines (ex. « mildiou signalé à moins de 10 km »).

**Règles métier**

- Modèles de risque basés sur la météo (température, humectation, humidité) et le stade de la culture ; chaque modèle documente sa source scientifique.
- Diagnostic photo par modèle de vision entraîné sur des photos prises au Maroc et validées par des experts ; trois niveaux de confiance : ≥ 85 % diagnostic affiché, 60 à 85 % « probable » sans produit proposé, < 60 % « je ne sais pas » (seuils recalés sur le jeu de test).
- Seuls les produits homologués au Maroc pour la culture et la cible sont proposés ; l'app ne recommande jamais de dose supérieure à l'homologation.
- Toutes les photos sont stockées avec position, date et culture ; avec l'accord de l'agriculteur, elles servent à améliorer le modèle.
- Signalements de voisinage strictement anonymes et agrégés (aucune ferme identifiable).

**Critères d'acceptation**

- Étant donné une observation saisie hors réseau avec photo, alors elle est conservée et synchronisée au retour du réseau, photo comprise.
- Étant donné un diagnostic photo sous le seuil de confiance, alors aucun produit n'est proposé et l'option « demander à un expert » est affichée.
- Étant donné un produit dont l'homologation a expiré, alors il n'apparaît plus dans les moyens de lutte.

**Hors périmètre.** Prescription engageant la responsabilité d'un professionnel, vente directe de produits.

## 11. F6 — Journal des opérations et registre phyto

**Objectif.** Tout ce qui se fait sur la ferme est noté en quelques secondes, et l'agriculteur peut produire à tout moment un registre de traitements présentable à une coopérative, un exportateur ou un auditeur.

**Récits utilisateur**

- **P1** — J'enregistre une opération en choisissant son icône : traitement phyto, fertilisation, irrigation, travail du sol, semis ou plantation, taille, désherbage, récolte, autre.
- **P1** — Pour un traitement, je choisis le produit dans le catalogue (recherche par nom ou par photo de l'étiquette), la dose, la parcelle et la date ; l'app me prévient si la dose dépasse l'homologation ou si le produit n'est pas autorisé sur cette culture.
- **P1** — Je vois la date à partir de laquelle je peux récolter chaque parcelle (délai avant récolte le plus long restant).
- **P1** — Je planifie une opération à venir et reçois un rappel le jour venu.
- **P1** — Je dicte une opération à voix haute (« j'ai traité les oliviers du bas avec du cuivre ce matin ») et l'app remplit le formulaire, que je confirme.
- **P2** — J'exporte le registre des traitements d'une parcelle ou de la ferme en PDF et Excel, et je l'envoie par WhatsApp.
- **P2** — Un ouvrier enregistre une opération ; le gestionnaire la voit et peut la valider.

**Règles métier**

- Champs obligatoires réduits au minimum : type, parcelle, date. Les autres sont optionnels mais demandés pour un traitement phyto (produit, dose) afin que le registre soit complet.
- Une opération peut couvrir plusieurs parcelles ; les quantités sont réparties au prorata de la surface.
- Contrôles phyto : homologation au Maroc pour la culture, dose maximale, nombre maximal d'applications, délai avant récolte. Avertissement, jamais blocage (l'agriculteur reste maître de son journal), mais l'avertissement est conservé dans le registre.
- Une opération validée peut être corrigée ; l'historique des corrections est conservé.
- Le journal alimente le calcul des coûts (F8) et le bilan hydrique (F4).

**Critères d'acceptation**

- Étant donné un traitement enregistré avec un produit au DAR de 21 jours, alors la date de récolte au plus tôt de la parcelle passe à J+21.
- Étant donné une phrase dictée en darija, quand l'app la comprend, alors le formulaire est pré-rempli et l'agriculteur confirme avant enregistrement.
- Étant donné une demande d'export du registre, alors le PDF contient pour chaque traitement : date, parcelle, culture, produit, matière active, dose, surface, opérateur.

**Hors périmètre.** Certification officielle, gestion de la paie des ouvriers.

## 12. F7 — Assistant IA vocal

**Objectif.** L'agriculteur pose une question à voix haute, en darija, en arabe ou en français, et obtient une réponse courte, écrite et lue, fondée sur les données de sa propre ferme.

**Récits utilisateur**

- **P1** — J'appuie sur le micro et je demande « est-ce que je dois irriguer les agrumes aujourd'hui ? » ; l'assistant répond en s'appuyant sur le bilan hydrique (F4) et la météo.
- **P1** — Je demande « quand est-ce que je peux récolter la parcelle 3 ? » ou « qu'est-ce que j'ai dépensé ce mois-ci ? » ; il répond à partir de mon journal.
- **P1** — Je pose une question générale d'agronomie (« comment tailler l'olivier ? ») ; il répond simplement et indique ses sources.
- **P2** — Je lui demande d'agir : « note que j'ai irrigué 3 heures », « rappelle-moi de traiter samedi » ; il prépare l'action et me demande de confirmer.
- **P2** — J'envoie une photo dans la conversation et il l'analyse avec le diagnostic de F5.
- **P3** — Je lui parle depuis WhatsApp sans ouvrir l'app.

**Règles métier**

- Réponses fondées sur trois sources hiérarchisées : données de la ferme, référentiels validés (catalogue phyto ONSSA, fiches cultures), connaissances générales du modèle. La source est indiquée.
- L'assistant ne recommande jamais un produit non homologué, une dose supérieure à l'homologation, ni une pratique dangereuse ; en cas de doute, il le dit et propose un expert.
- Toute action qui modifie les données est confirmée par l'agriculteur avant exécution.
- Limite d'usage gratuite de 20 questions par jour pour maîtriser les coûts ; au-delà, message clair.
- Hors réseau : l'assistant n'est pas disponible, mais la saisie vocale d'opérations est mise en file et traitée au retour du réseau.

**Critères d'acceptation**

- Étant donné une question vocale en darija sur une parcelle existante, alors la réponse cite la parcelle et ses données, est lue à voix haute et arrive en moins de 8 secondes en 4G.
- Étant donné une demande de traitement pour une cible sans produit homologué sur la culture, alors l'assistant le dit et ne propose aucun produit.
- Étant donné une action demandée, alors rien n'est enregistré sans confirmation explicite.

**Hors périmètre.** Conversation libre sans lien avec l'agriculture, conseil juridique ou financier.

## 13. F8 — Dépenses, stocks, récoltes et prix du marché

**Objectif.** L'agriculteur connaît ce que lui coûte chaque parcelle, ce qu'elle lui rapporte, et suit les prix pour mieux vendre.

**Récits utilisateur**

- **P1** — J'enregistre une dépense (intrants, main-d'œuvre, carburant, électricité, eau, location de matériel) en prenant en photo le ticket ou la facture ; l'app propose le montant et la catégorie.
- **P1** — J'enregistre une récolte (quantité par parcelle) et une vente (quantité, prix, acheteur).
- **P1** — Je vois par parcelle et par campagne : total des dépenses, recettes, marge, coût par hectare et par kilo produit.
- **P2** — Je suis mon stock d'intrants : les achats l'augmentent, les opérations du journal (F6) le diminuent automatiquement ; alerte quand un produit est presque épuisé.
- **P2** — Je consulte les prix de mes cultures sur les marchés de gros et leur évolution sur 3 mois.
- **P3** — Je compare mes coûts par hectare à la moyenne anonyme des fermes similaires de ma région.

**Règles métier**

- Monnaie : dirham (MAD). Une dépense non rattachée à une parcelle est répartie au prorata des surfaces, ou laissée en charges générales.
- Le coût d'un traitement est calculé à partir du prix d'achat moyen du produit en stock.
- Les montants ne sont visibles que par le propriétaire et les gestionnaires, jamais par les ouvriers.
- Les prix du marché affichent leur source et leur date ; aucune promesse de prix.

**Critères d'acceptation**

- Étant donné une photo de facture lisible, alors le montant et la date sont proposés et modifiables avant enregistrement.
- Étant donné un traitement de 2 L enregistré dans F6, alors le stock du produit diminue de 2 L.
- Étant donné une campagne avec dépenses et ventes, alors la marge par hectare est affichée et cohérente avec la somme des lignes.

**Hors périmètre.** Comptabilité légale, déclarations fiscales, paie.

## 14. F9 — Partage, conseillers et capteurs (phase 2)

**Objectif.** L'agriculteur choisit avec qui il partage sa ferme (conseiller, coopérative, distributeur) et peut brancher des capteurs pour un suivi plus précis. Cette fonctionnalité ouvre aussi le modèle économique (section 3).

**Récits utilisateur**

- **P2** — J'invite mon conseiller ou le technicien de mon distributeur par son numéro ; je choisis les parcelles partagées et ce qu'il peut voir (opérations, dépenses ou non).
- **P2** — Mon conseiller m'envoie une recommandation dans l'app ; je la vois, je l'accepte, et elle devient une opération planifiée dans mon journal.
- **P2** — Je retire un partage à tout moment ; l'accès est coupé immédiatement.
- **P2** — Ma coopérative, avec mon accord, voit mes surfaces, mes prévisions de récolte et mon registre phyto.
- **P3** — Je connecte une station météo, une sonde d'humidité du sol ou un compteur d'eau ; leurs mesures remplacent les estimations dans F3 et F4.

**Règles métier**

- Partage granulaire par parcelle et par type de donnée, avec date de début et de fin optionnelle ; journal des accès consultable par l'agriculteur.
- Les professionnels utilisent une interface dédiée (web), objet d'un abonnement ; l'agriculteur ne paie rien.
- Capteurs : protocole ouvert, rattachement à une parcelle, détection des valeurs aberrantes et des capteurs muets.

**Critères d'acceptation**

- Étant donné un partage retiré, alors le professionnel ne peut plus lire aucune donnée de la ferme dès la requête suivante.
- Étant donné une recommandation acceptée, alors elle apparaît dans le journal comme opération planifiée avec son auteur.

**Hors périmètre en V1.** Commande à distance d'équipements, marketplace d'achat.

## 15. Exigences non fonctionnelles

Ces seuils complètent la constitution et servent de critères de recette pour toutes les fonctionnalités.

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

### Exigences de design

Le design est une exigence de premier rang : l'app doit inspirer confiance à un agriculteur qui n'a jamais utilisé de logiciel, et donner envie d'être ouverte chaque matin.

**Direction artistique.** Calme, chaleureuse, ancrée dans la terre marocaine : palette inspirée de l'olivier, de la terre et de l'eau, beaucoup d'espace, peu d'éléments par écran, une information principale par carte. Pas d'esthétique « tableau de bord industriel » gris et dense.

| Domaine | Exigence |
| --- | --- |
| Design system | Design system AYLAL complet avant le premier écran : couleurs (clair, sombre, plein soleil à fort contraste), typographie IBM Plex Sans et IBM Plex Sans Arabic, échelle d'espacement sur une grille de 4 px, rayons, ombres, états ; chaque composant documenté avec ses variantes |
| Iconographie | Jeu d'icônes dessiné sur mesure pour les cultures, opérations, météo et alertes (pas d'icônes génériques) ; illustrations de cultures cohérentes entre elles ; photos réelles pour les maladies et ravageurs |
| Bilingue et RTL | Miroir RTL parfait en arabe (mise en page, icônes directionnelles, graphiques) ; chaque écran maquetté en arabe et en français ; textes longs et courts testés |
| Mouvement | Transitions de 200 à 300 ms, micro-interactions et retour haptique sur les actions clés (opération enregistrée, alerte) ; respect du réglage « réduire les animations » ; 60 images/s sur un Android d'entrée de gamme |
| États | Chaque écran a quatre états conçus : chargement (squelettes, jamais d'écran blanc), vide (illustration + action proposée), erreur (message clair + solution), hors ligne |
| Cartes et graphiques | Palettes d'indices lisibles par les daltoniens, légendes en mots simples, un seul message par graphique |
| Voix et ton | Textes courts, tutoiement ou vouvoiement fixé par langue, vocabulaire de l'agriculteur et non de l'ingénieur ; chaque texte relu par un locuteur natif de la darija |

**Processus de qualité design**

1. Maquettes haute fidélité de chaque écran P1, en arabe et en français, validées avant développement.
2. Prototype cliquable testé avec au moins 5 agriculteurs ; critère : 4 sur 5 réussissent la tâche principale de l'écran sans aide.
3. Catalogue de composants vivant, consultable par l'équipe, source unique des composants.
4. Revue design obligatoire de chaque écran implémenté, comparé à la maquette (espacements, typographie, états, RTL) avant fusion.
5. Captures d'écran de référence automatisées pour détecter toute régression visuelle.

## 16. Multi-front et orientations techniques (pour `/speckit.plan`)

Cette section est la seule à parler de technologie : elle ne va pas dans `/speckit.specify`, elle sert d'entrée à `/speckit.plan`. Les choix marqués « à trancher » sont à décider au moment du plan.

**Stratégie multi-front.** Un seul code d'interface pour mobile, web et desktop, et une logique métier partagée en TypeScript, pour respecter le principe 6.

| Couche | Orientation proposée | Alternative à évaluer |
| --- | --- | --- |
| Mobile (phase 1) | React Native avec Expo, Android d'abord — retenu le 7 novembre 2026 | Flutter, écarté (deux langages d'interface) ; solution de repli seulement si le prototype de validation échoue |
| Web (phase 2) | Même code via React Native Web dans Expo, ou application React dédiée qui partage les paquets métier | — |
| Desktop (phase 3) | Application web empaquetée avec Tauri | Electron |
| Logique métier partagée | Paquet TypeScript commun : types, règles (contrôles phyto, bilan hydrique, état de parcelle), validation | — |
| Hors ligne et synchronisation | Base SQLite locale + moteur de synchronisation avec le serveur | Retenu : PowerSync auto-hébergé au Maroc ; repli WatermelonDB |
| Cartographie | MapLibre (natif et web), fonds de carte mis en cache par zone | — |
| API | Python 3.13, FastAPI, Pydantic | — |
| Base serveur | PostgreSQL + PostGIS | — |
| Tâches de fond | File de tâches (Celery ou Arq) + Redis : imagerie, météo, alertes, notifications | — |
| Imagerie | Sentinel-2 via catalogues STAC, calcul des indices par parcelle, stockage en COG | — |
| Météo | Fournisseur de prévisions à la parcelle (ex. Open-Meteo) et calcul de l'ET0 | Fournisseur commercial si précision insuffisante |
| IA vocale et texte | Reconnaissance vocale adaptée à la darija, modèle de langage avec accès outils aux données de la ferme, synthèse vocale | Retenu : modèles open source auto-hébergés au Maroc (Voxtral darija ou MoulSot pour la voix, après banc d'essai) |
| Diagnostic photo | Modèle de vision fine-tuné sur des photos marocaines validées | — |
| Notifications | Push (Firebase Cloud Messaging), WhatsApp Business, SMS de secours | — |
| Déploiement | Conteneurs Docker, environnements recette et production séparés, CI avec tests | — |

**Organisation du dépôt proposée (monorepo).** `apps/mobile`, `apps/web`, `apps/desktop`, `packages/domain` (types et règles métier), `packages/ui` (composants et design system AYLAL), `packages/i18n`, `services/api`, `services/workers`.

**Design et interface (React Native).** Composants maison sur une base de primitives et de jetons de design (Unistyles recommandé, Tamagui en alternative, à confirmer dans le prototype), pas de kit d'interface générique visible ; animations avec Reanimated, graphiques et cartes de vigueur avec Skia et SVG, retour haptique avec Expo Haptics ; catalogue de composants avec Storybook ; tests de régression visuelle sur captures d'écran. Le design system AYLAL déjà rédigé (IBM Plex Sans et IBM Plex Sans Arabic, RTL) est la base des jetons.

**Prototype de validation (phase 0, 2 semaines).** Sur un vrai Android d'entrée de gamme (2 Go de RAM) : carte de 50 parcelles avec vigueur, saisie hors ligne puis synchronisation, micro et photo, un écran du design system avec ses animations. Validé si les seuils de la section 15 sont tenus (démarrage < 3 s, tableau de bord < 2 s, 60 images/s) ; sinon, réexamen du choix technique.

## 17. Données et référentiels

Toutes les données de l'agriculteur se rattachent à une ferme, puis à une parcelle et à une campagne ; les référentiels sont maintenus par l'équipe AYLAL et partagés par tous.

**Entités principales (noms techniques en anglais)**

| Entité | Contenu | Rattachement |
| --- | --- | --- |
| User | Téléphone, nom, langue, consentements | — |
| Farm | Nom, localisation, propriétaire | 1-n Membership (rôles) |
| Field | Géométrie, surface, irrigation, serre, sol | n-1 Farm |
| Season | Culture, variété, dates, stade, destination | n-1 Field |
| IrrigationSystem | Type, débits, écartements, secteurs, efficience | n-1 Field |
| Operation | Type, date, parcelles, produits, quantités, opérateur, statut (planifiée, faite) | n-1 Farm, n-n Field |
| Observation | Point, photo, problème, gravité | n-1 Season |
| Diagnosis | Résultat du modèle, confiance, validation | n-1 Observation |
| WaterBalance | Bilan journalier, ET0, Kc, pluie, conseil | n-1 Season |
| ImageryScene | Date, couverture nuageuse, indices | n-1 Field |
| Alert | Type, gravité, source, statut | n-1 Field |
| Expense / Harvest / Sale / StockItem | Montants, quantités, pièces jointes | n-1 Farm (Season optionnelle) |
| Share | Professionnel, parcelles, périmètre, dates | n-1 Farm |

**Référentiels**

| Référentiel | Contenu | Source |
| --- | --- | --- |
| Cultures | Liste, variétés, stades, coefficients culturaux (Kc), seuils météo, photos | FAO-56, littérature, validation agronomique |
| Produits phyto | Produits homologués, usages culture × cible, doses, DAR, nombre d'applications | Index ONSSA (réutiliser le catalogue PhytoIndex) |
| Ravageurs et maladies | Noms locaux et scientifiques, photos, symptômes, modèles de risque | À constituer avec des experts |
| Sols | Textures et réserve utile par défaut | Cartes pédologiques disponibles, valeurs par défaut prudentes |
| Géographie | Régions, provinces, communes | Découpage administratif officiel |

## 18. Feuille de route par phases

Trois phases, chacune livrable : le mobile Android sort seul en phase 1, le web et iOS suivent en phase 2, le desktop et les partenaires en phase 3. Les durées sont des estimations à confirmer au moment de `/speckit.plan`.

1. **Phase 0 — Fondations (environ 4 semaines).** Constitution Spec Kit, monorepo, paquet métier partagé, API, base de données, synchronisation hors ligne, design system, internationalisation trois langues, design system AYLAL et maquettes des écrans P1, prototype de validation React Native sur Android d'entrée de gamme.
2. **Phase 1 — Lancement mobile Android (environ 16 semaines).** F1, F2, F3, F4 (conseil simple), F5 (alertes et observations), F6, F7 (questions-réponses). Pilote terrain avec 50 agriculteurs dans 3 régions avant publication sur le Play Store.
3. **Phase 2 — Web, iOS et approfondissement (environ 16 semaines).** Application web, iOS, diagnostic photo (F5), actions de l'assistant (F7), F8, partage avec conseillers et coopératives (F9).
4. **Phase 3 — Desktop et écosystème.** Application desktop, capteurs connectés, prix du marché et comparaisons régionales, intégration avec les autres applications AYLAL (catalogue, irrigation, marketplace).

**Ordre conseillé des spécifications Spec Kit.** F1 → F2 → F6 → F3 → F4 → F5 → F7 → F8 → F9. F6 passe avant F3 parce que le journal alimente l'état des parcelles, le bilan hydrique et l'assistant.

## 19. Points ouverts et sources

Les points ouverts ont été tranchés ; il reste à valider chaque décision par la mesure, avant ou pendant `/speckit.clarify` :

**Décisions prises le 7 novembre 2026**

| Sujet | Décision | Validation restante |
| --- | --- | --- |
| Mobile | React Native avec Expo | Prototype de validation de la phase 0 (section 16) |
| Hébergement | Toutes les données et tous les traitements (API, base, photos, audio, modèles IA) hébergés au Maroc. Présélection : région Oracle Cloud de Casablanca, zone locale OVHcloud avec Maroc Datacenter, Sovereign Cloud de Maroc Telecom | Comparer prix, Kubernetes et PostgreSQL managés, disponibilité de GPU pour l'IA ; choisir avant la fin de la phase 0 |
| Synchronisation hors ligne | PowerSync en édition auto-hébergée (au Maroc), branché sur PostgreSQL, SQLite sur le téléphone. Repli : WatermelonDB avec un protocole de synchronisation maison | Test dans le prototype : 30 jours hors ligne simulés, zéro perte, conflits résolus |
| Reconnaissance vocale darija | Modèle open source auto-hébergé au Maroc. Candidats : modèle Voxtral darija publié par le ministère de la Transition numérique avec Mistral AI, et MoulSot v0.3 d'Atlasia (Apache 2.0) | Banc d'essai sur 300 enregistrements d'agriculteurs (régions, âges, bruit de terrain, vocabulaire agricole) ; retenir le meilleur taux d'erreur sur les mots agricoles ; cible : moins de 15 % d'erreurs sur les termes métier, coût mesuré en MAD par minute ; vérifier la licence du modèle Voxtral |
| Diagnostic photo | Trois niveaux de confiance : ≥ 85 % diagnostic affiché avec moyens de lutte ; 60 à 85 % « probable », 3 hypothèses, aucun produit, expert proposé ; < 60 % « je ne sais pas » | Jeu de données : au moins 300 photos validées par couple culture × problème, pour les 30 couples prioritaires ; double validation par deux experts ; 20 % des photos réservées au test, réparties par région ; seuils recalés pour atteindre au moins 90 % de diagnostics justes au niveau « affiché » |
| Index ONSSA | Le catalogue PhytoIndex est la source unique ; mise à jour mensuelle ; produits dont l'homologation expire retirés automatiquement des propositions | Procédure d'import et de contrôle à documenter |
| Prix des marchés | Reporté en phase 2 ; sources officielles publiées en priorité, sinon relevés de partenaires (coopératives, distributeurs), toujours datés et sourcés | Identifier les sources disponibles |
| Limites gratuites | Assistant : 20 questions par jour ; diagnostic photo : 10 par jour ; imagerie Sentinel-2 et météo sans limite ; imagerie haute résolution en premium | Ajuster selon les coûts réels du pilote |
| Pilote | 50 agriculteurs dans 3 régions : Souss-Massa (agrumes, maraîchage sous serre), Fès-Meknès (olivier, céréales), Béni Mellal-Khénifra (agrumes, olivier, betterave) ; partenaires visés : une coopérative par région, un ORMVA, un distributeur d'intrants | Signer les partenaires avant le début de la phase 1 |
| Marque | AYLAL est le nom de l'application pour l'agriculteur et de l'écosystème ; les autres briques (Catalog, Studio, Market…) restent des modules ou services internes, invisibles pour l'agriculteur | — |
| Bibliothèque d'interface | Unistyles pour les thèmes et jetons, composants maison | Confirmée ou remplacée (Tamagui) dans le prototype |
