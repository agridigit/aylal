# Plan d'implémentation : F8 — Dépenses, stocks, récoltes et prix du marché

**Branche** : `010-farm-economics` | **Date** : 2026-11-08 | **Spec** : [spec.md](spec.md)
**Entrée** : spec F8 + CPS sections 4, 13, 15, 16, 17, 19 + constitution + livrables F0/F1/F2/F3/F4/F6 fusionnés (`farm_context`/`require`, `app/domain/roles.py` et `MATRIX` avec `finance.read`, `worker_parcels`, `parcels.archived_at`, `seasons`, `operations`/`operation_parcels`/`operation_corrections`/`registry_entries` (F6), `phyto_products.expired_at`, `label_uploads` + `app/operations/storage.py` (MinIO, clés nommées par le serveur), `app/operations/body_limit.py`, `app/monitoring/access.py` (`visible_parcels`), `app/monitoring/gateways.py` (passerelles à URL vide), `app/auth/client_ip.py`, verrou `pg_advisory_xact_lock`, `applied_ops`, `infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`, `accounts/export.py`/`purge.py`, horloge `Clock`).

## Résumé

F8 ajoute quatre registres **en ajout seul** (dépenses, récoltes, ventes, mouvements de stock), un **bilan économique** par parcelle et par campagne (dépenses, recettes, marge, coût par ha et par kg), le **suivi de stock** alimenté par les opérations F6, la **lecture facultative des tickets** et les **prix du marché**. Approche :
- **toute règle** (arrondi et répartition au plus fort reste, coût par ha / kg, marge, prix moyen pondéré, solde de stock, coût d'un traitement, tendance 3 mois, plafonds) dans `packages/domain` (TS, source de vérité, Zod -> JSON Schema -> Pydantic) avec miroir `services/api/app/domain/` et **vecteurs JSON partagés TS/Python** (`f8_*.json`) ; le serveur fait foi, le mobile **recalcule localement** les bilans depuis SQLite (FR-018) ;
- **montants en centimes entiers (MAD)**, quantités en millièmes d'unité entiers : aucun flottant dans les totaux ;
- **registres append-only** : une correction = une ligne `reversal` (montants opposés) + éventuellement une nouvelle ligne liée (`replaces_id`), dans la même transaction ; vues `*_current` pour les lectures ; triggers qui refusent UPDATE/DELETE (patron `registry_entries` F6) ;
- **stock** : la source de vérité est `stock_movements` (signé, immuable) ; `stock_items` n'est qu'un cache (quantité, prix moyen) recalculable ; toute écriture de mouvement prend le **verrou consultatif par ferme** et se fait dans la transaction qui valide l'opération F6 (REST et synchro) ; idempotence par `(operation_id, line_no, kind)` ;
- **lecture des tickets** : tâche de fond appelant une passerelle OCR auto-hébergée (`AYLAL_OCR_URL`, vide = « non disponible ») ; **elle propose seulement**, l'agriculteur valide ; plafonds de taille/nombre et contrôle du type **avant** tout appel ;
- **prix du marché** : référentiel global `market_prices` alimenté par `refresh_market_prices` via `AYLAL_MARKET_PRICES_URL` (vide par défaut = « non disponible », jamais de valeur inventée) ; source et date obligatoires ;
- **un seul module d'accès** `app/economics/access.py` : rôle financier (owner/manager) + `visible_parcels(ctx)` de F3 pour le seul chemin de l'ouvrier (récolte en quantité). Détails : [research.md](research.md).

## Contexte technique

**Langages** : TypeScript 5.x strict, Python 3.13.
**Dépendances** : celles de F0-F4/F6. **Aucune nouvelle dépendance serveur** (HTTP via client existant des passerelles) ; mobile : aucune bibliothèque de graphes (courbes SVG/Skia), caméra/galerie déjà présentes (F6). Aucun moteur OCR dans l'API : il vit derrière la passerelle auto-hébergée.
**Stockage** : PostgreSQL 16, **11 tables nouvelles** (`expenses`, `expense_allocations`, `receipts`, `harvests`, `sales`, `stock_items`, `stock_movements`, `stock_alerts`, `market_prices`, `market_sources`, `economics_notification_log`) ; migration `0013_farm_economics` (numéro provisoire, à recaler à la fusion) ; SQLite local PowerSync ; Redis/Arq ; MinIO (pièces jointes).
**Tests** : pytest (unit, integration, contrat, e2e), Vitest (domain + vecteurs), Jest + RNTL, Maestro (tâches d'écran bloquées par la porte design).
**Plateforme** : Android 9+, 2 Go RAM ; API Linux conteneurisée.
**Performance** : bilan d'une campagne (<= 5000 lignes) calculé < 100 ms (domaine) ; écran bilan < 2 s depuis SQLite ; enregistrement d'une dépense < 30 s et d'une vente < 20 s (SC-001) ; sync initiale F8 <= 400 Ko par ferme de 50 parcelles ; budget APK : voir G9.
**Contraintes** : hors ligne complet (30 jours simulés, SC-004) ; hébergement Maroc (photos incluses) ; gratuit ; 4 états + RTL par écran.
**Échelle** : 5 écrans (F8-E1 à F8-E5), ~22 routes, 11 tables, 1 migration, 4 tâches workers.

## Vérification de la constitution (avant recherche)

| Principe | Statut | Réponse du plan |
| --- | --- | --- |
| I Agriculteur d'abord | OK | Saisie guidée par photo, icônes, lecture vocale des totaux |
| II Hors ligne | OK | Registres locaux, id client = idempotence, bilan recalculé sur SQLite |
| III Gratuit/sobre | OK | OCR auto-hébergé, plafonds par ferme, aucune dépendance payante |
| IV Données à l'utilisateur | OK | Export et purge incluent tout (G1), partage seulement sur accord (P3 reporté) |
| V Conseil prudent | OK | Aucune promesse de prix, source + date, « non disponible » (G5) |
| VI Logique unique | OK | `packages/domain` + vecteurs partagés |
| VII Petits téléphones | OK | Séries bornées, photo compressée localement, pas de nouvelle lib |
| VIII/XI Test first | OK | RED -> GREEN -> REFACTOR ; un test par critère P1 aux 3 niveaux |
| IX i18n | OK | Clés `ary/ar/fr` : `expenses`, `harvests`, `economics`, `stock`, `marketprices` |
| X Design | OK sous condition | Porte design (G8) : maquettes/stories seulement tant que `VALIDATION.md` manque |
| XII Docker | OK | Aucun service permanent nouveau ; worker existant |
| XIII Maroc | OK | G5 : passerelles configurables, rien ne sort sans validation de portée |
| XIV Documentation | OK | `docs/modules/010-farm-economics/` en fin de fonctionnalité |
| XV Seuils | OK | SC-001 à SC-007 mesurés en recette ; couverture domaine >= 80 % |

## Garde-fous obligatoires (leçons F0–F5)

Chaque point = **une tâche RED puis une tâche GREEN** dans `tasks.md` (`G<n>-RED` / `G<n>-GREEN`, avant les tâches de récit qui en dépendent).

### G1 — Accès scopé, rôles, parité de tous les chemins
- **404 inter-ferme identique** : toutes les routes `/v1/farms/{farm_id}/…` passent par `farm_context`/`require(action)` ; non-membre, membre retiré (`removed_at IS NOT NULL`), ferme inexistante ou supprimée -> **404** de corps identique `{"detail":"not_found"}`. Toute lecture filtre `farm_id` dans le WHERE ; clés étrangères composites `(farm_id, id)`. Un identifiant d'une autre ferme (dépense, vente, produit, parcelle, pièce jointe) se comporte comme un identifiant inexistant.
- **403 par rôle** (`roles.py` + `roles.ts`, vecteur `f8_roles.json`) :

| Action | owner | manager | worker |
| --- | --- | --- | --- |
| `expense.read` / `expense.write` / `expense.correct` | oui | oui | **403** |
| `sale.read` / `sale.write` / `sale.correct` | oui | oui | **403** |
| `harvest.read` | toutes | toutes | **les siennes**, parcelles attribuées non archivées, **sans aucun champ monétaire** |
| `harvest.write` | oui | oui | oui, parcelles attribuées non archivées seulement |
| `harvest.correct` | oui | oui | **403** |
| `economics.read` (bilans, marges, coûts) | oui | oui | **403** |
| `stock.read` / `stock.write` / `stock.adjust` | oui | oui | **403** (ses opérations F6 consomment le stock sans qu'il le voie) |
| `market_price.read` | oui | oui | **403** (écran de gestion ; donnée publique, mais hors usage de l'ouvrier) |
| `receipt.upload` / `receipt.read` | oui | oui | **403** |

  Ouvrier sur ressource d'une autre ferme ou parcelle non attribuée/archivée : **404** identique ; ressource de sa ferme mais action interdite : **403**. L'ouvrier ne voit ni dépenses, ni ventes, ni marges, ni stock, ni prix d'achat, ni valeur de stock, par aucun chemin.
- **Archivée masquée PARTOUT pour l'ouvrier** : un seul prédicat `visible_parcels(ctx)` (F3) appelé par REST (récoltes), `sync/economics.py`, règles PowerSync (`parcel_archived_at IS NULL` pour le seau ouvrier), `accounts/export.py` (l'ouvrier n'exporte que ses récoltes visibles), agrégats. Propriétaire/gestionnaire gardent l'historique des archivées. **Test de parité paramétré** : rôle × ferme {propre, autre, inconnue, supprimée} × parcelle {attribuée, non attribuée, archivée, inconnue} × chemin {REST, sync upload, sync download, export, agrégat} exigeant statuts et contenu identiques entre chemins, plus un contrôle « aucune clé monétaire dans la sortie ouvrier » sur chaque chemin.
- **Appartenance ACTIVE** : tout seau paramétré, rappel, alerte de stock ou calcul par destinataire exige `farm_members.removed_at IS NULL` (rejoué à chaque lecture et à chaque génération). **Purge** à la sortie d'un membre et au changement de rôle : `purge_member_economics` (journal de notifications, préférences). Un ouvrier promu ou rétrogradé change de seau au prochain échange.
- **Synchro** : le lot `/v1/sync/upload` est refusé entier (403) si une écriture viole le rôle ; non-membre -> 404 ; champs serveur (`farm_id` d'un enregistrement existant, `author_id`, montants dérivés, parts de répartition, `unit_cost`, `server_version`, `parcel_archived_at`) ignorés ou rejetés. Un rejeu du même `id` est idempotent.

### G2 — Agrégats et bilans sans fuite, cache scopé
- Tout total (dépenses, recettes, marge, coût par ha/kg, valeur du stock) est calculé **sur la portée de l'appelant** (owner/manager : toute la ferme, archivées incluses ; ouvrier : aucun total, 403). Aucune somme n'est lue d'une colonne de ferme ni d'un cache partagé entre rôles.
- **Clé de cache** : `eco:{farm_id}:{role}:{season_or_all}:{data_version}` (module `app/economics/cache.py`) ; ETag dérivé du contenu ; invalidation à chaque écriture de registre. Test : un changement de rôle ou une correction change la clé.
- **Cohérence** : la marge affichée est toujours égale à la somme des lignes courantes (vérifié par test de propriété sur lignes aléatoires, parts de répartition incluses).

### G3 — PowerSync : ni jointure ni sous-requête
Le service refuse jointures et sous-requêtes (`infra/powersync/sync-rules.yaml`, `scripts/validate-sync-rules.sh`, `make sync-rules`). Chaque table synchronisée porte **dénormalisés** : `farm_id`, `parcel_id`, `parcel_archived_at` (posé par triggers serveur à l'archivage/restauration, comme `operation_parcels`), `season_id`, `crop_slug`, `product_name` (stock) et les clés i18n utiles ; **chaque ligne a un `id` requis**.
- Seau financier `farm_finance` : paramètre `SELECT farm_id FROM farm_members WHERE user_id = request.user_id() AND role IN ('owner','manager') AND removed_at IS NULL` ; sert `expenses`, `expense_allocations`, `sales`, `harvests`, `stock_items`, `stock_movements`, `stock_alerts`, `receipts` (métadonnées). **Chaque requête de données couvre TOUS les paramètres du seau** (leçon F3 « Query must cover all bucket parameters »).
- Seau ouvrier `farm_worker_harvests_own` : `SELECT parcel_id, request.user_id() AS user_id FROM worker_parcels WHERE user_id = request.user_id()` (plus appartenance active côté seau) ; table `harvests` filtrée `author_id = bucket.user_id AND parcel_id = bucket.parcel_id AND parcel_archived_at IS NULL` ; **la table `harvests` ne porte aucune colonne monétaire** (le montant d'une vente vit dans `sales`, jamais servi à l'ouvrier) ; `stock_*`, `expenses`, `sales` jamais servis à l'ouvrier.
- `market_prices` : seau global sans paramètre (donnée publique, <= 500 lignes retenues par le worker), avec `source` et `observed_on` ; les écrans restent réservés à owner/manager.
- Tests : `validate-sync-rules` (aucun JOIN/IN-sous-requête), requêtes de seaux exécutées telles quelles sur PostgreSQL, contrat exigeant que chaque requête de `farm_worker_harvests_own` référence `bucket.parcel_id` ET `bucket.user_id`.

### G4 — Plafonds avant tout travail coûteux, verrou par ferme
Contrôles **avant** décodage d'image, appel OCR, calcul de bilan ou I/O (taille de corps lue d'abord : 413/422 immédiat, `body_limit.py`). Constantes dans `app/domain/economics_limits.py` + `economics-limits.ts` (vecteur `f8_limits.json`). Bornes de **robustesse**, pas de valeurs métier ; valeurs proposées, à confirmer (decisions).

| Ressource | Plafond |
| --- | --- |
| Photo de ticket | <= 6 Mo, types JPEG/PNG/WebP vérifiés par signature, <= 4000 px côté ; <= 3 pièces par dépense |
| Pièces jointes par ferme | <= 2000 ; rafale : <= 20 envois / 10 min / ferme (429 `Retry-After`) |
| Lectures OCR | <= 1 en cours par ferme, <= 100 par jour et par ferme ; refus **avant** appel sortant |
| Dépenses / ventes / récoltes / mouvements | <= 20 000 lignes par ferme et par registre ; montant <= 100 000 000,00 MAD ; quantité <= 1 000 000 |
| Antidatage / futur | <= 800 jours dans le passé ; futur <= 1 jour |
| Parcelles d'une répartition | <= 200 |
| Lot `/v1/sync/upload` | <= 100 opérations (413 `batch_too_large` avant toute écriture) |
| Historique / bilans | fenêtre <= 36 mois ; `limit` <= 100 (défaut 50), curseur ; <= 400 points de courbe |
| Prix du marché | <= 500 lignes retenues ; courbe 92 jours |
| Débit | limiteur Redis par IP/utilisateur/ferme (G6) ; 429 `Retry-After` |

**Verrous** : création de dépense/vente/récolte/mouvement/inventaire, validation d'une opération F6 qui consomme du stock, quotas et contrôle « vente <= récolte non vendue » -> `SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` (même clé que `fields/service.py`, F3, F4, F6), comptage des quotas et écriture dans la **même transaction, y compris sur le chemin synchro**. Le stock ne peut pas subir de course : deux mouvements concurrents se sérialisent, le solde est la somme exacte (test concurrent à N tâches).

### G5 — Passerelles externes, hébergement Maroc, validation avant envoi
- **OCR** (`AYLAL_OCR_URL`) et **prix du marché** (`AYLAL_MARKET_PRICES_URL`) : passerelles configurables (patron `monitoring/gateways.py`, liste blanche `AYLAL_EXTERNAL_ALLOWED_HOSTS`). **URL vide = « non disponible »** : OCR -> reçu `unavailable`, aucune proposition ; prix -> écran « non disponible » avec le dernier relevé daté, jamais de valeur inventée ni extrapolée. Réponse mal formée, hors bornes (montant négatif, date future, catégorie inconnue) : proposition **rejetée** et reçu `failed`, saisie manuelle intacte.
- **Validation du destinataire/portée avant tout envoi externe** : l'OCR n'est appelé que pour un reçu de la ferme de l'appelant, de statut `uploaded`, déjà plafonné et typé ; le worker revérifie `farm_id` et appartenance active ; les prix du marché ne sortent aucune donnée de la ferme (requête = cultures du référentiel + marchés configurés, sans identifiant de ferme, utilisateur ou parcelle). L'image de ticket est envoyée **uniquement** à la passerelle hébergée au Maroc dans la liste blanche ; aucun envoi si l'hôte n'est pas listé. Tests : adaptateurs espions vérifiant les clés exactes ; test d'inventaire des imports (aucun SDK étranger).
- Les valeurs proposées par l'OCR ne sont **jamais** écrites dans un registre : elles vivent dans `receipts.proposal` jusqu'à validation par l'agriculteur.
- **Cas où le CPS est muet** (source des prix, moteur OCR, parcelles du prorata, unités de stock, arrondis, plafonds) : consignés dans `decisions.md`, section **« À confirmer »**.

### G6 — Identifiants d'objet opaques, URL signées, X-Forwarded-For
- Le client **n'envoie jamais** de clé de stockage ni d'URL : `object_key` est nommée par le serveur (UUID aléatoire + préfixe ferme), l'envoi se fait par `POST` du fichier à l'API (patron `label_uploads` F6) ou par URL pré-signée <= 15 min générée à la demande ; toute clé reçue (`file_key`, `object_key`, `url`…) rejette l'opération (`invalid_object_ref`). Lecture d'une pièce : URL pré-signée courte après contrôle de rôle et de ferme ; une pièce d'une autre ferme = 404. Les identifiants (`expense_id`, `sale_id`, `receipt_id`…) sont générés par le client pour l'idempotence mais **validés et rattachés à la ferme côté serveur** ; réutiliser un id d'une autre ferme répond comme un id inexistant (aucune fuite par collision).
- **X-Forwarded-For** : `client_ip()` uniquement ; en-tête lu seulement si le pair appartient à `AYLAL_TRUSTED_PROXIES`. Limiteur Redis sur les routes F8 (envoi de pièces, écritures, historique, bilans). Tests : en-tête falsifié depuis un pair non fiable ignoré ; 429 + `Retry-After`.

### G7 — Horloge injectée, tests déterministes, hygiène e2e
- Toute logique dépendant de l'heure (date locale de la ferme, antidatage, futur toléré, tendance 3 mois, ancienneté d'un prix, fenêtre de campagne, planification des workers) reçoit une **`Clock`** (`packages/domain/src/clock.ts`, `app/domain/clock.py`, existantes). Aucun `now()` direct dans les règles.
- **Jamais de `FLUSHDB`** (Redis par worker de test, clés préfixées) ; **numéros de téléphone e2e uniques** par test ; **aucun DELETE** sur les registres protégés (`expenses`, `sales`, `harvests`, `stock_movements`) y compris dans les nettoyages de tests (isolation par ferme unique).

### G8 — Écrans et porte design
Les écrans suivent `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, >= 48 dp, plein soleil ; une couleur n'est jamais seule : icône + phrase). **Porte design** (CLAUDE.md, constitution X) : un écran (F8-E1 dépenses + ticket, F8-E2 récoltes et ventes, F8-E3 bilan parcelle/campagne, F8-E4 stock, F8-E5 prix du marché) n'est codé **que si** `docs/design/010-farm-economics/VALIDATION.md` existe et liste cet écran ; ce fichier n'est **jamais** écrit par un agent. Tant qu'il manque : seulement maquettes/stories Storybook et captures PNG FR/AR dans `docs/design/010-farm-economics/` ; les tâches d'écran, de parcours Maestro et de captures de régression restent **bloquées** (marquées `[BLOQUÉ-DESIGN]` dans `tasks.md`).

### G9 — Mesure APK
Mesure `make apk-size` en fin d'implémentation et avant fusion. F8 n'ajoute **aucune dépendance native** (caméra/galerie : F6). Un dépassement n'est accepté que via `specs/010-farm-economics/apk-budget.env` (`APK_LIMIT_MB` <= 52, `APK_BUDGET_REASON`, `DECISION_REF`) ET une section **« Dérogation »** dans `specs/010-farm-economics/decisions.md` ; la dérogation d'une autre fonctionnalité n'est pas héritée.

### G10 — Registre append-only et écritures correctives
- Triggers `BEFORE UPDATE OR DELETE` refusant toute modification de `expenses`, `sales`, `harvests`, `stock_movements` (sauf colonnes de recopie dénormalisée `parcel_archived_at`, posées par trigger serveur) ; **aucun chemin de code ne supprime**.
- Correction : `POST …/{id}/reverse` ou `…/{id}/replace` crée dans la même transaction une ligne `reversal` (montants/quantités opposés, `reverses_id`) et, pour `replace`, une ligne neuve (`replaces_id`) ; l'original reste lisible avec son historique. Une ligne déjà inversée ne peut pas l'être deux fois (409 `already_reversed`, contrainte unique sur `reverses_id`).
- Opération F6 annulée ou corrigée : mouvement de stock `reversal` de la consommation d'origine (clé d'idempotence `(operation_id, line_no, 'reversal', correction_no)`), jamais de modification.
- Conformité export/purge : le registre est exporté intégralement (original + corrections) ; la suppression de ferme purge l'ensemble sous contrôle du module de purge (seule exception documentée à l'ajout seul).

## Structure du projet

### Documentation

```text
specs/010-farm-economics/
├── plan.md  research.md  data-model.md  quickstart.md  decisions.md
├── contracts/ (openapi.yaml, powersync-sync-rules.yaml, external-gateways.md)
└── tasks.md   # produit par /speckit-tasks
docs/design/010-farm-economics/   # maquettes HD ar + fr, stories (porte design) ; VALIDATION.md écrit par l'humain uniquement
```

### Code source (réutilise F0-F6, ajoute seulement ce qui est requis)

```text
packages/domain/src/{money,expense-allocation,farm-economics,stock-ledger,weighted-average-cost,price-trend,receipt-proposal,economics-limits}.ts
packages/domain/src/roles.ts (étendu)
packages/domain/vectors/f8_{roles,limits,money,allocation,economics,stock,wac,trend,receipt}.json   # partagés TS/Python
packages/i18n/locales/{ary,ar,fr}/{expenses,harvests,economics,stock,marketprices}.json
services/api/app/domain/{money.py,expense_allocation.py,farm_economics.py,stock_ledger.py,weighted_average_cost.py,price_trend.py,receipt_proposal.py,economics_limits.py}   # miroirs Python
services/api/app/economics/{access.py,ledger.py,expenses.py,harvests.py,sales.py,stock.py,operation_hook.py,receipts.py,market_prices.py,reading.py,cache.py,lifecycle.py,limits.py,schemas.py}
services/api/app/routers/{expenses.py,harvests.py,sales.py,economics.py,stock.py,receipts.py,market_prices.py}
services/api/app/sync/economics.py                   # authorize + apply, même access.py
services/api/app/operations/service.py (hook minimal : appel à economics.operation_hook dans la transaction de validation/annulation ; tracé dans decisions.md)
services/api/app/db/models.py (+ modèles)
services/api/alembic/versions/0013_farm_economics.py # tables, triggers append-only, recopie parcel_archived_at
services/api/app/accounts/{export.py,purge.py} (étendus)
services/workers/tasks/{read_receipt.py,refresh_market_prices.py,evaluate_stock_alerts.py,send_stock_alerts.py}
infra/powersync/sync-rules.yaml (étendu) ; scripts/validate-sync-rules.* (cas F8)
apps/mobile/src/screens/{Expenses,HarvestsSales,Economics,Stock,MarketPrices}/      # [BLOQUÉ-DESIGN]
apps/mobile/src/economics/{viewModels,localEconomics.ts,pendingBadge.ts,totalsVoice.ts}
apps/mobile/maestro/{expense_receipt,harvest_sale,economics_margin,stock_consumption,market_prices,worker_no_amounts}.yaml   # [BLOQUÉ-DESIGN]
```

**Décision de structure** : pas de nouveau service Docker permanent ; le worker existant exécute les tâches ; `make` inchangé (nouveaux tests découverts par les cibles actuelles).

## Ordre de livraison (pour `tasks`)

1. Fondations non-écran : G1-G7 et G10 (RED puis GREEN), migration, domaine + vecteurs, rôles, référentiel de prix vide.
2. Récits P1 non-écran : R1 (dépenses, répartition, ticket/OCR, corrections), R2 (récoltes, ventes, contrôle quantité), R3 (bilans, marge, coût par ha/kg, cohérence).
3. Récits P2 non-écran : R4 (stock, hook F6, prix moyen, alertes, concurrence), R5 (prix du marché, passerelle, tendance).
4. Maquettes/stories (autorisées) ; écrans, Maestro, captures **bloqués** jusqu'à `docs/design/010-farm-economics/VALIDATION.md`.
5. G9 mesure APK, puis documentation `docs/modules/010-farm-economics/`.

## Vérification de la constitution (après conception)

Aucune violation. Risques résiduels consignés : source des prix et moteur OCR non désignés (passerelles vides = fonctionnalités dégradées proprement) ; hook F6 dans `operations/service.py` (extension minimale tracée) ; porte design bloquant les écrans ; migration `0013` provisoire (F7 et 009 en parallèle).
