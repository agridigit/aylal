# Spécification de fonctionnalité : F8 — Dépenses, stocks, récoltes et prix du marché (serveur, domaine et écrans)

**Branche** : `010-farm-economics`
**Créé le** : 2026-11-08
**Statut** : Brouillon
**Entrée** : Fonctionnalité F8. Sources : `docs/cps/AYLAL-CPS.md` section 13 (contexte sections 1 à 3, données section 17, exigences sections 4 et 15, feuille de route de la section 5). Dépend de F1 (ferme, rôles), F2 (parcelles, campagnes) et F6 (journal : les opérations font baisser le stock). Alimente, plus tard, F7 (questions sur les coûts) et F9 (partage).

## Objectif

L'agriculteur connaît ce que lui coûte chaque parcelle, ce qu'elle lui rapporte, ce qu'il lui reste en stock d'intrants, et suit les prix de ses cultures pour mieux vendre.

## Scénarios utilisateur et tests *(obligatoire)*

### Récit 1 — Enregistrer une dépense avec la photo du ticket (Priorité : P1)

L'agriculteur enregistre une dépense (intrants, main-d'œuvre, carburant, électricité, eau, location de matériel) en prenant en photo le ticket ou la facture ; l'app propose le montant, la date et la catégorie, qu'il peut corriger avant d'enregistrer. Il peut aussi saisir une dépense sans photo.

**Pourquoi** : sans dépenses fiables, aucun coût ni aucune marge n'est calculable.
**Test indépendant** : enregistrer une dépense avec photo lisible, avec photo illisible, puis sans photo, avec et sans réseau, et vérifier le montant, la date et la catégorie conservés.

**Scénarios d'acceptation** :

1. **Étant donné** une photo de facture lisible, **Quand** l'agriculteur la joint à une nouvelle dépense, **Alors** le montant et la date sont proposés et modifiables avant enregistrement.
2. **Étant donné** une photo illisible ou une lecture indisponible, **Quand** l'agriculteur la joint, **Alors** aucune valeur n'est inventée : le formulaire reste vide, la photo reste jointe et il saisit à la main.
3. **Étant donné** une dépense saisie, **Quand** l'agriculteur choisit la catégorie (intrants, main-d'œuvre, carburant, électricité, eau, location de matériel, autre), **Alors** elle est enregistrée en dirhams (MAD) avec sa date.
4. **Étant donné** une dépense rattachée à une parcelle, **Quand** elle est enregistrée, **Alors** elle compte dans le coût de cette parcelle et de sa campagne.
5. **Étant donné** une dépense non rattachée à une parcelle, **Quand** l'agriculteur choisit « répartir », **Alors** elle est répartie au prorata des surfaces des parcelles concernées ; s'il choisit « charges générales », elle reste au niveau de la ferme.
6. **Étant donné** un agriculteur hors réseau, **Quand** il enregistre une dépense, **Alors** elle est conservée localement avec la mention « à envoyer », puis synchronisée sans perte.
7. **Étant donné** une dépense déjà enregistrée, **Quand** l'agriculteur découvre une erreur, **Alors** il la corrige par une écriture corrective visible ; le montant d'origine reste consultable et rien n'est effacé en silence.
8. **Étant donné** un montant nul, négatif ou une date dans le futur lointain, **Quand** l'agriculteur valide, **Alors** un message clair indique le champ à corriger.

---

### Récit 2 — Enregistrer une récolte et une vente (Priorité : P1)

L'agriculteur enregistre une récolte (quantité par parcelle) et une vente (quantité, prix, acheteur).

**Pourquoi** : les recettes et le rendement sont nécessaires à la marge et au coût par kilo.
**Test indépendant** : enregistrer une récolte sur une parcelle puis plusieurs ventes, avec et sans réseau, et comparer les totaux.

**Scénarios d'acceptation** :

1. **Étant donné** une parcelle avec une campagne active, **Quand** l'agriculteur saisit une quantité récoltée en kilos, **Alors** la récolte est enregistrée et rattachée à la parcelle et à la campagne.
2. **Étant donné** une récolte enregistrée, **Quand** l'agriculteur saisit une vente (quantité, prix unitaire, acheteur), **Alors** la recette est calculée en MAD et la vente est rattachée à la récolte et à la parcelle.
3. **Étant donné** une vente dont la quantité dépasse la quantité récoltée disponible, **Quand** l'agriculteur valide, **Alors** un message clair l'indique et propose de corriger la récolte ou la vente ; aucune quantité n'est inventée.
4. **Étant donné** un agriculteur hors réseau, **Quand** il enregistre une récolte ou une vente, **Alors** elle est conservée localement puis synchronisée sans perte.
5. **Étant donné** une vente enregistrée par erreur, **Quand** l'agriculteur la corrige, **Alors** une écriture corrective est ajoutée et l'historique reste consultable.
6. **Étant donné** un acheteur déjà utilisé, **Quand** l'agriculteur saisit une nouvelle vente, **Alors** le nom est proposé pour éviter la ressaisie ; la saisie libre reste possible.

---

### Récit 3 — Voir coûts, recettes et marge par parcelle et par campagne (Priorité : P1)

L'agriculteur voit, par parcelle et par campagne : total des dépenses, recettes, marge, coût par hectare et coût par kilo produit.

**Pourquoi** : c'est la valeur centrale : savoir ce que rapporte chaque parcelle.
**Test indépendant** : avec un jeu de dépenses, récoltes et ventes connu, vérifier chaque total, la marge, le coût par hectare et par kilo, et leur cohérence avec la somme des lignes.

**Scénarios d'acceptation** :

1. **Étant donné** une campagne avec dépenses et ventes, **Quand** l'agriculteur ouvre le bilan de la parcelle, **Alors** la marge par hectare est affichée et cohérente avec la somme des lignes.
2. **Étant donné** une campagne avec dépenses et récolte, **Quand** le bilan est calculé, **Alors** le coût par hectare vaut le total des dépenses divisé par la surface et le coût par kilo vaut le total des dépenses divisé par la quantité récoltée.
3. **Étant donné** une campagne sans récolte, **Quand** le bilan est calculé, **Alors** le coût par kilo n'est pas affiché (« non disponible ») et jamais remplacé par une valeur inventée.
4. **Étant donné** une dépense répartie au prorata, **Quand** le bilan de chaque parcelle est calculé, **Alors** la somme des parts répartie sur les parcelles égale exactement la dépense d'origine, centime compris.
5. **Étant donné** des charges générales, **Quand** l'agriculteur consulte le bilan de la ferme, **Alors** elles apparaissent séparément et sont incluses dans la marge de la ferme, pas dans celle des parcelles.
6. **Étant donné** un ouvrier, **Quand** il ouvre l'application ou interroge l'API, la synchronisation ou l'export, **Alors** il ne voit jamais de montant, de marge ni de coût, quel que soit le chemin.
7. **Étant donné** une parcelle archivée, **Quand** un propriétaire ou un gestionnaire consulte ses bilans passés, **Alors** ils restent consultables ; un ouvrier n'y a pas accès.
8. **Étant donné** un agriculteur hors réseau, **Quand** il consulte un bilan, **Alors** il est calculé sur les données locales avec leur date de dernière synchronisation.

---

### Récit 4 — Suivre mon stock d'intrants (Priorité : P2)

L'agriculteur suit son stock d'intrants : les achats l'augmentent, les opérations du journal (F6) le diminuent automatiquement ; une alerte prévient quand un produit est presque épuisé.

**Pourquoi** : éviter la rupture et connaître le coût réel d'un traitement.
**Test indépendant** : acheter un produit, enregistrer un traitement dans le journal, vérifier le stock, le coût du traitement et l'alerte de seuil.

**Scénarios d'acceptation** :

1. **Étant donné** un traitement de 2 L enregistré dans F6, **Quand** l'opération est validée, **Alors** le stock du produit diminue de 2 L.
2. **Étant donné** un achat d'intrant (quantité, prix), **Quand** il est enregistré, **Alors** le stock augmente et le prix d'achat moyen du produit est mis à jour.
3. **Étant donné** un traitement avec un produit en stock, **Quand** l'opération est enregistrée, **Alors** son coût est calculé à partir du prix d'achat moyen du produit en stock et compte dans le coût de la parcelle.
4. **Étant donné** un stock tombé sous le seuil défini, **Quand** le mouvement est enregistré, **Alors** une alerte « presque épuisé » est produite.
5. **Étant donné** un traitement dont la quantité dépasse le stock, **Quand** l'opération est enregistrée, **Alors** elle reste enregistrée (le journal prime), le stock affiche un écart signalé à régulariser, et il ne devient jamais négatif en silence.
6. **Étant donné** deux appareils qui enregistrent chacun un mouvement de stock sur le même produit, **Quand** ils se synchronisent, **Alors** les deux mouvements sont conservés et le stock vaut la somme exacte, sans perte ni double décompte.
7. **Étant donné** une opération annulée ou corrigée dans le journal, **Quand** la correction est enregistrée, **Alors** un mouvement correctif rétablit le stock ; l'historique des mouvements n'est jamais modifié.
8. **Étant donné** un produit retiré du catalogue des produits homologués, **Quand** l'agriculteur gère son stock, **Alors** il n'est plus proposé pour de nouveaux achats ; son historique et son stock existants restent consultables.
9. **Étant donné** un inventaire physique différent du stock calculé, **Quand** le gestionnaire saisit la quantité comptée, **Alors** un mouvement d'ajustement est ajouté avec son motif.

---

### Récit 5 — Consulter les prix du marché de mes cultures (Priorité : P2)

L'agriculteur consulte les prix de ses cultures sur les marchés de gros et leur évolution sur 3 mois.

**Pourquoi** : mieux choisir quand et à quel prix vendre.
**Test indépendant** : avec une source de prix disponible puis indisponible, vérifier l'affichage du prix, de sa source et de sa date, de l'évolution sur 3 mois et de l'état « non disponible ».

**Scénarios d'acceptation** :

1. **Étant donné** une culture de la ferme et une source de prix disponible, **Quand** l'agriculteur ouvre l'écran des prix, **Alors** il voit le dernier prix par marché, avec sa source et sa date, et l'évolution sur 3 mois.
2. **Étant donné** une source de prix non configurée ou indisponible, **Quand** l'agriculteur ouvre l'écran, **Alors** il voit « non disponible » avec le dernier prix connu et sa date s'il existe ; aucun prix n'est jamais inventé.
3. **Étant donné** n'importe quel prix affiché, **Quand** il apparaît, **Alors** il ne contient aucune promesse (« vous obtiendrez ») : il est présenté comme un relevé daté avec sa source.
4. **Étant donné** un agriculteur hors réseau, **Quand** il ouvre l'écran, **Alors** les derniers prix chargés s'affichent avec leur date.
5. **Étant donné** un prix du marché et un prix de vente de l'agriculteur pour la même culture, **Quand** il consulte l'évolution, **Alors** il peut les comparer sur la même période.

---

### Récit 6 — Me comparer à des fermes similaires (Priorité : P3, reporté)

Comparer ses coûts par hectare à la moyenne anonyme des fermes similaires de sa région. Reporté : exige l'accord explicite et révocable de partage (principe 4) et un seuil d'anonymat ; non planifié dans cette version.

## Cas limites

- Dépense en devise autre que le dirham : non gérée, le MAD est la seule monnaie.
- Dépense rattachée à une parcelle sans campagne active : rattachée à la parcelle, comptée dans la campagne couvrant sa date si elle existe, sinon en charges de la parcelle hors campagne.
- Parcelle fusionnée, scindée ou archivée après une dépense : les montants déjà enregistrés restent attribués ; la répartition au prorata enregistrée n'est pas recalculée en silence.
- Une dépense répartie dont les surfaces changent ensuite : la répartition de la date de saisie fait foi, tracée.
- Photo de ticket très lourde ou en rafale : compressée localement, plafonnée en taille et en nombre par ferme ; le dépassement donne un message clair.
- Reçu envoyé deux fois (mauvaise connexion) : une seule dépense, grâce à un identifiant d'idempotence.
- Deux fermes aux produits de même nom : aucun mélange de stocks ni de prix.
- Ouvrier retiré de la ferme : n'accède plus à rien ; ses saisies de récolte conservées sans montant visible pour lui.
- Quantité décimale en litres, kilos, unités : précision fixée, arrondis documentés, pas de dérive cumulée.
- Prix du marché obsolète (plus de 14 jours) : signalé comme ancien.

## Écrans et états *(obligatoire)*

Chaque écran a quatre états conçus.

| Écran | Chargement | Vide | Erreur | Hors ligne |
| --- | --- | --- | --- | --- |
| A Dépenses (liste et saisie, photo du ticket) | Squelette de la liste et du formulaire, jamais d'écran blanc | Illustration et action « ajouter ma première dépense » | Message clair sur le champ invalide, la photo ou l'échec d'enregistrement, avec solution ; saisie conservée | Saisie et photo conservées localement, mention « à envoyer », lecture automatique indiquée comme indisponible |
| B Récoltes et ventes | Squelette | Illustration et action « enregistrer une récolte » | Message clair sur la quantité ou le prix et action de correction | Enregistrement local, mention « à envoyer » |
| C Bilan parcelle et campagne (dépenses, recettes, marge, coût par ha et par kg) | Squelettes des totaux et du graphique | Illustration et action « ajouter une dépense ou une vente » | Message clair et action de nouvel essai | Totaux calculés sur les données locales avec leur date |
| D Stock d'intrants | Squelette de la liste | Illustration et action « ajouter un achat » | Message clair et action de nouvel essai | Mouvements locaux en attente d'envoi, stock calculé localement avec la mention « à envoyer » |
| E Prix du marché | Squelettes des cartes et de la courbe | Aucune culture suivie : illustration et action pour démarrer une campagne | « Non disponible » avec la raison et le dernier prix connu daté | Derniers prix chargés avec leur date |

**Exigences RTL et langues** :

- Chaque écran existe en darija (graphie arabe et latine), arabe standard (RTL complet) et français.
- En arabe, la mise en page, les icônes directionnelles et les graphiques sont en miroir parfait ; les montants (MAD), quantités et unités (kg, L, ha) restent lisibles et correctement ordonnés en RTL, avec des chiffres cohérents d'un écran à l'autre.
- Les textes longs et courts sont testés dans les trois langues ; aucun texte n'est en dur dans l'interface.
- Chaque écran est utilisable par un agriculteur qui lit peu : icônes, un seul objectif par écran, lecture vocale des totaux.
- Chaque écran est maquetté en arabe et en français avant développement ; aucun écran n'est codé sans validation de la maquette par le porteur du projet.

## Exigences *(obligatoire)*

### Exigences fonctionnelles

- **FR-001** : le système DOIT permettre d'enregistrer une dépense avec catégorie (intrants, main-d'œuvre, carburant, électricité, eau, location de matériel, autre), montant en MAD, date, note et rattachement optionnel à une parcelle et à une campagne.
- **FR-002** : le système DOIT permettre de joindre une photo de ticket ou de facture à une dépense, et proposer le montant, la date et la catégorie lorsque la photo est lisible, toujours modifiables avant enregistrement ; sans lecture possible, aucune valeur n'est proposée.
- **FR-003** : le système DOIT répartir une dépense non rattachée au prorata des surfaces des parcelles concernées (somme des parts exactement égale à la dépense) ou la laisser en charges générales, au choix de l'agriculteur.
- **FR-004** : le système DOIT permettre d'enregistrer une récolte (quantité par parcelle et campagne) et une vente (quantité, prix unitaire, acheteur, date).
- **FR-005** : le système DOIT refuser, avec un message clair, une vente dont la quantité dépasse la quantité récoltée non encore vendue.
- **FR-006** : le système DOIT calculer par parcelle et par campagne : total des dépenses, recettes, marge, coût par hectare et coût par kilo produit ; la marge par hectare DOIT être égale à la somme des lignes divisée par la surface.
- **FR-007** : le système DOIT tenir dépenses, récoltes, ventes et mouvements de stock comme un registre en ajout seul : toute correction est une écriture corrective liée à l'écriture d'origine, jamais une modification ni une suppression silencieuse.
- **FR-008** : le système DOIT tenir un stock d'intrants par produit : les achats l'augmentent, les opérations du journal (F6) le diminuent automatiquement de la quantité utilisée, les corrections et annulations l'ajustent par mouvements correctifs.
- **FR-009** : le système DOIT calculer le coût d'un traitement à partir du prix d'achat moyen du produit en stock et l'imputer à la parcelle traitée.
- **FR-010** : le système DOIT produire une alerte lorsque le stock d'un produit passe sous son seuil.
- **FR-011** : les mouvements de stock DOIVENT être exacts sous accès concurrent et sous synchronisation hors ligne multi-appareils : aucun mouvement perdu ni compté deux fois.
- **FR-012** : le système DOIT afficher les prix du marché des cultures de la ferme avec source et date, et l'évolution sur 3 mois, sans aucune promesse de prix.
- **FR-013** : le système DOIT afficher « non disponible » quand la source de prix n'est pas configurée ou ne répond pas, sans jamais inventer ni extrapoler de valeur.
- **FR-014** : les montants (dépenses, recettes, marges, coûts, prix d'achat, valeur du stock) DOIVENT n'être visibles que du propriétaire et des gestionnaires, jamais des ouvriers, quel que soit le chemin (API, synchronisation, export, agrégats, alertes, rappels, lecture vocale).
- **FR-015** : l'accès DOIT être contrôlé côté serveur par ferme et par rôle ; une ressource d'une autre ferme répond de façon identique à une ressource inexistante, et les identifiants d'objets ne sont pas devinables.
- **FR-016** : l'accès DOIT supposer une appartenance active à la ferme ; un membre retiré perd immédiatement tout accès, y compris via la synchronisation.
- **FR-017** : les parcelles archivées DOIVENT rester cachées aux ouvriers de façon identique dans l'API, la synchronisation, l'export et les agrégats ; propriétaires et gestionnaires conservent l'historique.
- **FR-018** : toute saisie et toute consultation de données déjà chargées DOIVENT fonctionner hors réseau pendant au moins 30 jours, avec synchronisation invisible, indicateur « à envoyer » et zéro perte.
- **FR-019** : l'envoi d'un même enregistrement plusieurs fois DOIT créer un seul enregistrement (idempotence).
- **FR-020** : les photos de tickets DOIVENT être plafonnées (taille, nombre) avant tout traitement coûteux et rester sur l'hébergement au Maroc ; un contrôle de type et de taille précède la lecture automatique.
- **FR-021** : toute règle de calcul (répartition, coût par hectare et par kilo, marge, prix moyen, stock) DOIT être partagée entre tous les fronts et testable sans interface ; l'horloge est injectée dans ces règles.
- **FR-022** : les données restent propres à la ferme ; rien n'est partagé sans accord explicite et révocable ; l'export et la suppression complets incluent dépenses, pièces jointes, récoltes, ventes, mouvements de stock et alertes.
- **FR-023** : les totaux DOIVENT pouvoir être lus à voix haute pour chaque écran concerné.
- **FR-024** : les produits retirés du catalogue homologué DOIVENT cesser d'être proposés pour de nouveaux achats ou traitements sans effacer l'historique.
- **FR-025** : le système DOIT limiter les volumes (nombre de lignes, taille des pièces jointes, fréquence des envois) par ferme pour protéger les coûts d'exploitation.

### Entités principales

- **Expense** : dépense : catégorie, montant MAD, date, parcelle ou charges générales, pièce jointe, écritures correctives.
- **Harvest** : récolte : parcelle, campagne, quantité, unité, date.
- **Sale** : vente : récolte, quantité, prix unitaire, acheteur, date.
- **StockItem** : produit d'intrant suivi : produit, unité, seuil, prix d'achat moyen.
- **StockMovement** : mouvement de stock : achat, consommation par une opération, correction, inventaire ; registre en ajout seul.
- **MarketPrice** : relevé de prix : culture, marché, prix, unité, date, source.
- **Référentiels utilisés** : cultures (F2), produits du catalogue (F6), parcelles et surfaces (F2).

## Hors périmètre

- Comptabilité légale, déclarations fiscales, paie.
- Comparaison anonyme avec les fermes similaires (P3, reporté).
- Paiements, facturation clients, devises autres que le MAD.
- Promesse, prévision ou recommandation de prix de vente.
- Commande d'intrants auprès de fournisseurs.

## Critères de réussite *(obligatoire)*

- **SC-001** : un agriculteur entraîné enregistre une dépense avec photo en moins de 30 secondes et une vente en moins de 20 secondes.
- **SC-002** : 100 % des bilans testés ont une marge égale à la somme exacte des lignes, et la somme des parts réparties égale la dépense d'origine au centime.
- **SC-003** : 100 % des traitements enregistrés dans le journal avec un produit suivi font baisser le stock de la quantité exacte, vérifié aussi sous concurrence.
- **SC-004** : après 30 jours hors réseau simulés, aucune dépense, récolte, vente ni mouvement de stock saisi n'est perdu ni dupliqué après synchronisation.
- **SC-005** : aucun montant n'est visible par un ouvrier sur 100 % des chemins testés (API, synchronisation, export, agrégats).
- **SC-006** : 100 % des prix affichés portent source et date ; sans source, « non disponible » s'affiche dans 100 % des cas testés.
- **SC-007** : chaque écran présente ses quatre états et un rendu RTL conforme en arabe, validés par la revue design.

## Hypothèses

- La monnaie est le dirham marocain (MAD), montants en centimes entiers.
- La lecture automatique de la photo du ticket est un service auto-hébergé au Maroc [NEEDS CLARIFICATION: moteur de lecture des tickets non précisé dans le CPS].
- La source des prix des marchés de gros est externe et optionnelle [NEEDS CLARIFICATION: source officielle des prix de gros non précisée dans le CPS].
- La répartition au prorata utilise les surfaces des parcelles sélectionnées par l'agriculteur [NEEDS CLARIFICATION: parcelles concernées par défaut (toutes ou celles à campagne active) non précisées dans le CPS].
- Une opération du journal (F6) est la seule source de consommation automatique de stock ; F8 ne crée pas de second registre d'opérations.
- Le seuil d'alerte de stock est fixé par l'agriculteur par produit ; sans seuil, aucune alerte n'est produite.
- La notification d'alerte de stock suit les préférences de notification de F3.
