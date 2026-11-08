# Tâches : F8 — Dépenses, stocks, récoltes et prix du marché

**Branche** : `010-farm-economics` | **Entrées** : spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md, decisions.md
**Règle** : test first strict. Dans chaque bloc, les tests RED (unitaire `tests/unit/`, intégration `tests/integration/`, contrat `tests/contract/`, bout en bout `services/api/tests/e2e/` ou `apps/mobile/maestro/`) viennent AVANT l'implémentation, sont lancés et DOIVENT échouer (commit `test(010-farm-economics): red - <sujet>`), puis GREEN (`feat(...)`), puis REFACTOR (`refactor(...)`). Aucun test modifié pour passer sauf contradiction avec la spec (à noter dans `decisions.md`).
**Notation** : `[P]` = fichiers différents, aucune dépendance en cours. `[USn]` = récit n. Critères cités `Rn-Am` = récit n, scénario d'acceptation m de spec.md ; `CL` = cas limite ; `FR-xxx`/`SC-xxx` ; `G1`..`G10` = garde-fous de plan.md (`G<n>-RED` / `G<n>-GREEN`).
**Séparation** : les tâches **non-écran** (domaine, API, base, synchro, workers, view models) ne dépendent PAS de la porte design. Les tâches **`[écran]`** (écrans, parcours Maestro, captures de régression) sont `[BLOQUÉ-DESIGN]` : elles ne démarrent que si `docs/design/010-farm-economics/VALIDATION.md` existe et liste l'écran ; ce fichier n'est **jamais** écrit par un agent (CLAUDE.md, constitution X). Les maquettes et stories Storybook (T087-T089) sont autorisées sans validation.
**Chemins** : API = `services/api/`, domaine = `packages/domain/`, mobile = `apps/mobile/`, workers = `services/workers/`. Tests : `services/api/tests/{unit,integration,contract,e2e}/`, `services/workers/tests/`, `packages/domain/tests/`, `apps/mobile/src/**/__tests__/`.
**Interdits transverses** : aucun montant en flottant ; aucune valeur de prix, de montant OCR ou de source inventée ni semée par migration (fixtures de test seulement) ; aucun `now()` / `Date.now()` / `current_date` dans les règles (horloge injectée) ; aucun DELETE/UPDATE sur les registres ; aucun texte d'interface en dur.

## Phase 1 : Mise en place

- [x] T001 Vérifier qu'aucune dépendance nouvelle n'est requise (HTTP via client des passerelles, caméra F6) ; ajouter aux fichiers de configuration `services/api/app/config.py`, `docker-compose.yml`, `.env.example` les variables `AYLAL_OCR_URL` et `AYLAL_MARKET_PRICES_URL` **vides par défaut** (`${VAR:-}`) et l'hôte à la liste `AYLAL_EXTERNAL_ALLOWED_HOSTS`.
- [x] T002 [P] Créer les clés i18n vides `packages/i18n/locales/{ary,ar,fr}/{expenses,harvests,economics,stock,marketprices}.json` et étendre `packages/i18n/tests/parity.test.ts`.
- [ ] T003 [P] Créer les squelettes vides sans logique : `services/api/app/economics/`, `services/api/app/routers/{expenses,harvests,sales,economics,stock,receipts,market_prices}.py`, `services/api/app/sync/economics.py`, `services/workers/tasks/{read_receipt,refresh_market_prices,evaluate_stock_alerts,send_stock_alerts}.py`, `packages/domain/src/{money,expense-allocation,farm-economics,stock-ledger,weighted-average-cost,price-trend,receipt-proposal,economics-limits}.ts`.
- [ ] T004 **T-DESIGN-GATE (humain, bloquante pour tout `[écran]`, G8)** : validation humaine des maquettes haute fidélité arabe + français de F8-E1 à F8-E5 ; se matérialise par `docs/design/010-farm-economics/VALIDATION.md`, **écrit uniquement par l'utilisateur, jamais par un agent** ; la boucle ne fait que constater son absence et laisse les tâches `[écran]` bloquées.
- [x] T005 [P] Ajouter en fin de `specs/010-farm-economics/decisions.md` (sans écraser les points 1 à 13 ni la section « Poids de l'APK ») une section « Journal d'exécution » : tâches `[écran]` bloquées, écarts de test, dérogation éventuelle.

## Phase 2 : Fondations non-écran G1 à G10 (bloquent tous les récits)

### Tests RED d'abord

#### Unitaire

- [ ] T006 [P] **G7-RED horloge injectée (unitaire)** `packages/domain/tests/unit/clock-economics.test.ts` + `services/api/tests/unit/test_f8_clock.py` : date locale `Africa/Casablanca`, antidatage <= 800 jours, futur <= 1 jour, fenêtre de 13 semaines, prix « ancien » > 14 jours ; aucune lecture d'horloge système dans les règles F8 (FR-021).
- [ ] T007 [P] **G1-RED matrice de rôles (unitaire)** vecteur `packages/domain/vectors/f8_roles.json` + `packages/domain/tests/unit/roles.test.ts` (étendu) + `services/api/tests/unit/test_f8_roles_matrix.py` : owner/manager/worker pour chaque action du tableau G1 de plan.md ; ouvrier 403 sur tout le financier, `harvest.write` autorisé (FR-014, R3-A6).
- [ ] T008 [P] **G4-RED plafonds (unitaire)** vecteur `packages/domain/vectors/f8_limits.json` + `packages/domain/tests/unit/economics-limits.test.ts` + `services/api/tests/unit/test_f8_economics_limits.py` : taille de photo, nombre de pièces, quotas par ferme, montant et quantité max, antidatage, parcelles par répartition, lot <= 100 (FR-020, FR-025).
- [ ] T009 [P] **G2-RED clé de cache et portée (unitaire)** `services/api/tests/unit/test_f8_cache_key.py` : clé `eco:{farm_id}:{role}:{season_or_all}:{data_version}` ; changement de rôle ou de version change la clé.
- [ ] T010 [P] **G5-RED configuration et passerelles vides (unitaire)** `services/api/tests/unit/test_f8_gateways_unavailable.py` : `AYLAL_OCR_URL` et `AYLAL_MARKET_PRICES_URL` vides par défaut ; URL vide, hôte hors liste, réponse mal formée ou hors bornes -> `availability: "unavailable"` avec `reason`, aucune valeur inventée (R1-A2, R5-A2, FR-013).
- [ ] T011 [P] **G5-RED minimisation sortante et validation de portée (unitaire)** `services/api/tests/unit/test_f8_outbound_scope.py` : adaptateurs espions, clés exactes (image seule pour l'OCR ; cultures et fenêtre de dates pour les prix) ; aucun id de ferme, utilisateur ou parcelle ; envoi refusé si reçu d'une autre ferme, statut ≠ `uploaded`, appartenance inactive, plafond quotidien atteint ou hôte non listé.
- [ ] T012 [P] **G6-RED IP de confiance (unitaire)** `services/api/tests/unit/test_f8_client_ip.py` : `X-Forwarded-For` ignoré hors `AYLAL_TRUSTED_PROXIES`.
- [ ] T013 [P] **G6-RED objets opaques (unitaire)** `services/api/tests/unit/test_f8_opaque_refs.py` : schémas `extra=forbid` rejettent `file_key`, `object_key`, `url`, `author_id`, `farm_id` d'un enregistrement existant, `share_cents`, `total_cents` dérivés, `unit_cost_cents` ; clé de stockage nommée par le serveur (UUID).
- [ ] T014 [P] **Règles de domaine RED** vecteurs `packages/domain/vectors/f8_{money,allocation,economics,stock,wac,trend,receipt}.json`, tests `packages/domain/tests/unit/{money,expense-allocation,farm-economics,stock-ledger,weighted-average-cost,price-trend,receipt-proposal}.test.ts` et miroirs `services/api/tests/unit/test_f8_{money,allocation,economics,stock,wac,trend,receipt}.py` : arrondi, plus fort reste (somme = dépense au centime), coût par ha et par kg (« non disponible » sans récolte), marge = somme des lignes, prix moyen pondéré, solde de stock, stock insuffisant -> écart, coût inconnu, tendance 13 semaines, validation des bornes d'une proposition OCR (R1-A5, R3-A1..A4, R4-A2/A3/A5, R5-A1/A2, FR-006, FR-009).
- [ ] T015 [P] **G10-RED registre append-only (unitaire)** `services/api/tests/unit/test_f8_ledger_rules.py` : règle `reverse`/`replace` (montants opposés, double inversion refusée, original conservé) pour dépenses, ventes, récoltes, mouvements (R1-A7, R2-A5, R4-A7, FR-007).

#### Intégration

- [ ] T016 [P] **G1-RED 404 inter-ferme** `services/api/tests/integration/test_f8_farm_isolation.py` : pour CHAQUE route F8, non-membre, membre retiré, ferme inconnue ou supprimée, id d'une autre ferme (dépense, vente, produit, parcelle, pièce) -> 404 de corps identique `not_found` (FR-015).
- [ ] T017 [P] **G1-RED 403 par rôle** `services/api/tests/integration/test_f8_role_authz.py` : ouvrier 403 sur dépenses, ventes, bilans, stock, prix, reçus ; `harvest.write` OK sur parcelle attribuée non archivée ; ouvrier sur parcelle non attribuée, archivée ou inconnue -> 404 identique ; gestionnaire autorisé (R3-A6).
- [ ] T018 [P] **G1-RED synchro scopée** `services/api/tests/integration/test_f8_sync_authz.py` : `/v1/sync/upload` -> lot entier refusé 403 si une écriture viole le rôle (rien d'écrit) ; non-membre 404 ; champs serveur ignorés ou rejetés ; rejeu d'un même `id` idempotent (FR-019).
- [ ] T019 **G1-RED parité de tous les chemins** `services/api/tests/integration/test_f8_path_parity.py` : matrice paramétrée rôle × ferme {propre, autre, inconnue, supprimée} × parcelle {attribuée, non attribuée, archivée, inconnue} × chemin {REST, sync upload, sync download, export, agrégat} : statuts et contenus identiques ; aucune clé monétaire dans la sortie ouvrier sur chaque chemin (FR-014, FR-017, SC-005).
- [ ] T020 [P] **G1-RED parcelle archivée cachée à l'ouvrier PARTOUT** `services/api/tests/integration/test_f8_archived_parcel_hidden.py` : un seul prédicat `visible_parcels(ctx)` ; récoltes de l'ouvrier masquées sur parcelle archivée en REST, synchro, export et agrégats ; owner/manager gardent l'historique des archivées (R3-A7).
- [ ] T021 [P] **G1-RED appartenance active et purge par utilisateur** `services/api/tests/integration/test_f8_member_removal.py` : seaux, `economics_notification_log`, alertes de stock et rappels exigent `removed_at IS NULL` à chaque lecture et génération ; sortie ou changement de rôle -> accès immédiatement coupé, journal purgé (FR-016).
- [ ] T022 [P] **G2-RED agrégats sans fuite et cache scopé** `services/api/tests/integration/test_f8_aggregate_no_leak.py` : bilan ferme/parcelle/campagne calculé sur les lignes courantes ; aucun total pour l'ouvrier ; cache jamais partagé entre rôles ; propriété « marge = somme des lignes » sur lignes aléatoires, parts de répartition incluses (R3-A1, SC-002).
- [ ] T023 [P] **G3-RED règles PowerSync valides** `tests/platform/test_powersync_economics_rules_valid.sh` + cas F8 dans `scripts/validate-sync-rules.sh` et `scripts/validate-sync-rules.mjs` : `infra/powersync/sync-rules.yaml` accepté via `scripts/validate-sync-rules.sh` ; aucune jointure ni sous-requête ; `id` requis sur chaque requête ; chaque requête de données couvre TOUS les paramètres du seau (`farm_worker_harvests_own` référence `bucket.parcel_id` ET `bucket.user_id`) ; `harvests` sans colonne monétaire ; seau `farm_finance` restreint owner/manager actifs.
- [ ] T024 [P] **G4-RED plafonds avant travail coûteux** `services/api/tests/integration/test_f8_limits_enforced.py` : taille de corps lue d'abord (413/422 immédiat) ; photo > 6 Mo ou type faux refusée **avant** décodage et avant appel OCR (l'espion OCR n'est pas appelé) ; lot sync > 100 -> 413 avant toute écriture ; quotas de lignes et de pièces ; `limit` > 100 (FR-020, FR-025).
- [ ] T025 [P] **G4-RED verrou par ferme : stock et quotas** `services/api/tests/integration/test_f8_stock_race.py` : N tâches concurrentes de mouvements sur le même produit (achats + consommations REST et synchro) -> solde = somme exacte, aucun double décompte ; deux ventes concurrentes dépassant la récolte -> une seule passe ; quotas concurrents (R4-A6, FR-011, SC-003).
- [ ] T026 [P] **G5-RED passerelles absentes en intégration** `services/api/tests/integration/test_f8_gateways_degraded.py` : sans URL, reçu `unavailable`, saisie manuelle intacte ; prix `available=false` avec dernier relevé daté ; jamais de valeur extrapolée ; réponse hors bornes rejetée (R1-A2, R5-A2, SC-006).
- [ ] T027 [P] **G6-RED objets opaques côté API** `services/api/tests/integration/test_f8_opaque_objects.py` : clé de stockage ou URL reçue -> `invalid_object_ref` (REST et sync) ; pièce d'une autre ferme -> 404 ; URL pré-signée <= 15 min après contrôle de rôle et de ferme ; id client réutilisé d'une autre ferme répond comme inexistant.
- [ ] T028 [P] **G6-RED limiteur Redis et X-Forwarded-For** `services/api/tests/integration/test_f8_rate_limit.py` : envoi de pièces, écritures, historique, bilans -> 429 + `Retry-After` ; en-tête falsifié depuis un pair non fiable ignoré.
- [ ] T029 [P] **G1-RED export, purge, migration** `services/api/tests/integration/test_f8_export_purge.py` : toutes les tables F8 incluses dans `accounts/export.py` (original + corrections, pièces ; ouvrier : ses récoltes visibles seulement) et `accounts/purge.py` ; migration `0013_farm_economics` appliquée à blanc et rejouée ; triggers append-only actifs ; aucune donnée de référence semée (FR-022).
- [ ] T030 [P] **G10-RED registre append-only (intégration)** `services/api/tests/integration/test_f8_append_only.py` : UPDATE/DELETE directs refusés par trigger sur `expenses`, `sales`, `harvests`, `stock_movements` ; `reverse` deux fois -> 409 `already_reversed` ; correction visible avec original (R1-A7).
- [ ] T031 [P] **G7-RED hygiène e2e et déterminisme** `services/api/tests/integration/test_f8_test_hygiene.py` : numéros de téléphone **uniques** par test ; Redis par worker de test sans `FLUSHDB` ; isolation par ferme unique ; aucun DELETE sur registres protégés dans les nettoyages.

#### Contrat

- [ ] T032 [P] Contrat REST : `services/api/tests/contract/test_f8_openapi_contract.py` valide toutes les routes F8 contre `specs/010-farm-economics/contracts/openapi.yaml` (statuts 404/403/409/413/422/429, `extra=forbid`, harvests sans champ monétaire).
- [ ] T033 [P] Contrat synchronisation : `services/api/tests/contract/test_f8_sync_rules_contract.py` valide `contracts/powersync-sync-rules.yaml` contre `infra/powersync/sync-rules.yaml` (colonnes dénormalisées, aucune colonne monétaire dans le seau ouvrier).
- [ ] T034 [P] Contrat domaine TS <-> API Python : `services/api/tests/contract/test_f8_domain_vectors.py` rejoue les vecteurs partagés `f8_*.json` des deux côtés (FR-021).

#### Bout en bout (service)

- [ ] T035 [P] **E2E fondation** `services/api/tests/e2e/test_f8_foundation_e2e.py` : pile Docker, ferme + owner + manager + ouvrier : 404 inter-ferme, 403 ouvrier, lot de synchro refusé, passerelles vides « non disponible » (G1, G5).

### Implémentation GREEN (après les tests ci-dessus)

- [ ] T036 **G10-GREEN migration** `services/api/alembic/versions/0013_farm_economics.py` + modèles `services/api/app/db/models.py` : 11 tables du data-model, FK composites, triggers append-only, contrainte de somme des parts, recopie `parcel_archived_at`, unicité d'idempotence ; aucun référentiel semé (T029, T030).
- [ ] T037 [P] **Domaine TS** `packages/domain/src/{money,expense-allocation,farm-economics,stock-ledger,weighted-average-cost,price-trend,receipt-proposal,economics-limits}.ts` + Zod -> JSON Schema (`scripts/gen-pydantic.sh`) (T006, T008, T014, T015).
- [ ] T038 [P] **Miroir Python** `services/api/app/domain/{money,expense_allocation,farm_economics,stock_ledger,weighted_average_cost,price_trend,receipt_proposal,economics_limits}.py` (mêmes vecteurs, horloge injectée) (T014, T034).
- [ ] T039 **G1-GREEN rôles et accès** `packages/domain/src/roles.ts` + `services/api/app/domain/roles.py` + `services/api/app/economics/access.py` (rôle financier + `visible_parcels` pour l'ouvrier) + `services/api/app/economics/{ledger,limits,cache,schemas}.py` (T007, T009, T016..T022, T024, T027).
- [ ] T040 **G3-GREEN synchronisation** `infra/powersync/sync-rules.yaml` (seaux `farm_finance`, `farm_worker_harvests_own`, `market_prices_recent`) + `services/api/app/sync/economics.py` (authorize + apply, même `access.py`, idempotence `applied_ops`) (T018, T023, T033).
- [ ] T041 **G4/G6-GREEN plafonds, verrou, limiteur** `services/api/app/economics/limits.py`, verrou `pg_advisory_xact_lock(hashtextextended(farm,0))` dans `ledger.py`, limiteur Redis, `client_ip()` (T008, T024, T025, T028).
- [ ] T042 **G5-GREEN passerelles** `services/api/app/economics/gateways.py` (OCR, prix ; URL vide = `unavailable`, liste blanche, validation de portée avant envoi, bornes de réponse) + `contracts/external-gateways.md` à jour (T010, T011, T026).
- [ ] T043 **G1/G10-GREEN export, purge, cycle de vie** `services/api/app/accounts/{export,purge}.py` + `services/api/app/economics/lifecycle.py` (`purge_member_economics`) (T021, T029).
- [ ] T044 Refactor des fondations (tests verts) et commit `refactor(010-farm-economics): foundations`.

## Phase 3 : Récit 1 — Dépense avec photo du ticket (P1) [US1]

**Test indépendant** : enregistrer une dépense avec photo lisible, illisible, puis sans photo, avec et sans réseau.

### Tests RED

- [ ] T045 [P] [US1] Unitaire `services/api/tests/unit/test_f8_expense_rules.py` + `packages/domain/tests/unit/expense.test.ts` : catégories, montant > 0, date bornée, rattachement parcelle/prorata/général, prorata figé au plus fort reste (R1-A3, A4, A5, A8, CL dépense sans campagne).
- [ ] T046 [P] [US1] Unitaire `services/api/tests/unit/test_f8_receipt_proposal.py` : proposition valide / hors bornes / catégorie inconnue / date future -> rejet (R1-A1, A2).
- [ ] T047 [P] [US1] Intégration `services/api/tests/integration/test_f8_expenses_api.py` : création (idempotence, rejeu), prorata (somme des parts = dépense), général, correction `reverse`/`replace`, lecture ouvrier 403, ferme étrangère 404 (R1-A3..A8, CL reçu envoyé deux fois).
- [ ] T048 [P] [US1] Intégration `services/api/tests/integration/test_f8_receipts_api.py` + `services/workers/tests/test_read_receipt.py` : envoi plafonné et typé, tâche `read_receipt` avec passerelle fictive -> `ready` + proposition, passerelle vide -> `unavailable`, réponse hors bornes -> `failed`, jamais d'écriture au registre (R1-A1, A2).
- [ ] T049 [P] [US1] Intégration synchro `services/api/tests/integration/test_f8_expenses_sync.py` : dépenses hors ligne rejouées sans perte ni doublon après 30 jours simulés (R1-A6, SC-004).
- [ ] T050 [US1] E2E service `services/api/tests/e2e/test_f8_us1_expense_e2e.py` : ticket -> proposition -> dépense modifiée -> prorata -> bilan parcelle impacté (R1-A1..A5).
- [ ] T051 [US1] [écran] [BLOQUÉ-DESIGN] E2E Maestro `apps/mobile/maestro/expense_receipt.yaml` (photo, proposition, correction, hors ligne « à envoyer ») ; états chargement/vide/erreur/hors ligne et RTL.

### Implémentation GREEN

- [ ] T052 [US1] `services/api/app/economics/{expenses,receipts}.py`, `services/api/app/routers/{expenses,receipts}.py`, `services/workers/tasks/read_receipt.py` (T045..T050).
- [ ] T053 [US1] View model mobile `apps/mobile/src/economics/viewModels/expenseForm.ts`, `localEconomics.ts` (prorata local identique au domaine), `pendingBadge.ts` + tests `apps/mobile/src/economics/__tests__/`.
- [ ] T054 [US1] [écran] [BLOQUÉ-DESIGN] `apps/mobile/src/screens/Expenses/` (F8-E1) avec `packages/ui` uniquement et clés i18n.

## Phase 4 : Récit 2 — Récolte et vente (P1) [US2]

**Test indépendant** : enregistrer une récolte puis plusieurs ventes, avec et sans réseau.

### Tests RED

- [ ] T055 [P] [US2] Unitaire `services/api/tests/unit/test_f8_sale_rules.py` + `packages/domain/tests/unit/sale.test.ts` : total = quantité × prix arrondi, quantité vendue <= récoltée, correction (R2-A2, A3, A5).
- [ ] T056 [P] [US2] Intégration `services/api/tests/integration/test_f8_harvests_sales_api.py` : récolte par owner/manager et par l'ouvrier (parcelle attribuée, sans champ monétaire), vente (409 `sale_exceeds_harvest`), acheteur proposé depuis l'historique, ouvrier 403 sur ventes, correction par écriture (R2-A1..A6).
- [ ] T057 [P] [US2] Intégration synchro `services/api/tests/integration/test_f8_harvests_sales_sync.py` : saisie hors ligne rejouée ; vente dépassant au rejeu -> conservée et `sync_conflict` visible (R2-A4, décision 12).
- [ ] T058 [US2] E2E service `services/api/tests/e2e/test_f8_us2_harvest_sale_e2e.py` : récolte -> ventes -> reste vendable -> dépassement refusé.
- [ ] T059 [US2] [écran] [BLOQUÉ-DESIGN] E2E Maestro `apps/mobile/maestro/harvest_sale.yaml` et `worker_no_amounts.yaml`.

### Implémentation GREEN

- [ ] T060 [US2] `services/api/app/economics/{harvests,sales}.py`, `services/api/app/routers/{harvests,sales}.py` (T055..T058).
- [ ] T061 [US2] View model `apps/mobile/src/economics/viewModels/harvestSale.ts` + tests.
- [ ] T062 [US2] [écran] [BLOQUÉ-DESIGN] `apps/mobile/src/screens/HarvestsSales/` (F8-E2).

## Phase 5 : Récit 3 — Bilan, marge, coût par ha et par kg (P1) [US3]

**Test indépendant** : jeu connu de dépenses, récoltes, ventes ; vérifier chaque total.

### Tests RED

- [ ] T063 [P] [US3] Unitaire `packages/domain/tests/unit/farm-economics.test.ts` + miroir Python : totaux, marge, coût/ha, coût/kg, « non disponible » sans récolte, charges générales séparées, campagne hors période (R3-A2..A5).
- [ ] T064 [P] [US3] Intégration `services/api/tests/integration/test_f8_economics_api.py` : bilan parcelle/campagne/ferme, marge par ha = somme des lignes, parcelle archivée consultable par owner/manager, ouvrier 403, cohérence REST = calcul local (R3-A1..A7).
- [ ] T065 [P] [US3] Intégration `apps/mobile/src/economics/__tests__/localEconomics.test.ts` : bilan recalculé sur données locales avec date de dernière synchro, identique au serveur (R3-A8, vecteurs partagés).
- [ ] T066 [US3] E2E service `services/api/tests/e2e/test_f8_us3_margin_e2e.py` : campagne complète -> marge/ha cohérente ; ouvrier sans aucun montant sur tous les chemins (SC-002, SC-005).
- [ ] T067 [US3] [écran] [BLOQUÉ-DESIGN] E2E Maestro `apps/mobile/maestro/economics_margin.yaml`.

### Implémentation GREEN

- [ ] T068 [US3] `services/api/app/economics/reading.py`, `services/api/app/routers/economics.py`, cache scopé (T063, T064, T066).
- [ ] T069 [US3] `apps/mobile/src/economics/{localEconomics,totalsVoice}.ts` (lecture vocale des totaux, FR-023) + tests.
- [ ] T070 [US3] [écran] [BLOQUÉ-DESIGN] `apps/mobile/src/screens/Economics/` (F8-E3).

## Phase 6 : Récit 4 — Stock d'intrants (P2) [US4]

**Test indépendant** : acheter, traiter via le journal, vérifier stock, coût et alerte.

### Tests RED

- [ ] T071 [P] [US4] Unitaire `packages/domain/tests/unit/stock-ledger.test.ts` + miroir Python : prix moyen pondéré, consommation, écart, coût inconnu, conversion d'unité compatible, seuil (R4-A2..A5).
- [ ] T072 [P] [US4] Intégration `services/api/tests/integration/test_f8_stock_operation_hook.py` : traitement de 2 L validé dans F6 -> stock -2 L ; annulation/correction -> mouvement correctif ; produit libre non suivi ; idempotence du hook ; coût imputé à la parcelle (R4-A1, A3, A7).
- [ ] T073 [P] [US4] Intégration `services/api/tests/integration/test_f8_stock_api.py` : achat, ajustement d'inventaire avec motif, produit retiré du catalogue (`expired_at`) exclu des nouveaux achats mais historique lisible (parité avec le routeur du catalogue), ouvrier 403 (R4-A8, A9, FR-024).
- [ ] T074 [P] [US4] Intégration `services/workers/tests/test_stock_alerts.py` : franchissement du seuil -> alerte dédoublonnée, destinataires owner/manager actifs seulement, préférences F3 (R4-A4).
- [ ] T075 [US4] E2E service `services/api/tests/e2e/test_f8_us4_stock_e2e.py` : achat -> opération -> stock et coût -> alerte.
- [ ] T076 [US4] [écran] [BLOQUÉ-DESIGN] E2E Maestro `apps/mobile/maestro/stock_consumption.yaml`.

### Implémentation GREEN

- [ ] T077 [US4] `services/api/app/economics/{stock,operation_hook}.py`, hook minimal dans `services/api/app/operations/service.py` (tracé dans `decisions.md`), `services/api/app/routers/stock.py`, `services/workers/tasks/{evaluate_stock_alerts,send_stock_alerts}.py` (T071..T075).
- [ ] T078 [US4] View model `apps/mobile/src/economics/viewModels/stock.ts` + tests.
- [ ] T079 [US4] [écran] [BLOQUÉ-DESIGN] `apps/mobile/src/screens/Stock/` (F8-E4).

## Phase 7 : Récit 5 — Prix du marché (P2) [US5]

**Test indépendant** : source disponible puis indisponible.

### Tests RED

- [ ] T080 [P] [US5] Unitaire `packages/domain/tests/unit/price-trend.test.ts` + miroir Python : médiane hebdomadaire 13 semaines, prix ancien > 14 jours, aucune extrapolation (R5-A1, A3).
- [ ] T081 [P] [US5] Intégration `services/api/tests/integration/test_f8_market_prices_api.py` + `services/workers/tests/test_refresh_market_prices.py` : source configurée -> prix avec source et date ; URL vide -> `available=false` et dernier relevé daté ; hôte non listé refusé ; rétention 92 jours / 500 lignes ; comparaison prix du marché / prix de vente de l'agriculteur sur la même période ; ouvrier 403 (R5-A1..A5, SC-006).
- [ ] T082 [US5] E2E service `services/api/tests/e2e/test_f8_us5_prices_e2e.py` : passerelle fictive -> écran de données -> passerelle coupée -> « non disponible ».
- [ ] T083 [US5] [écran] [BLOQUÉ-DESIGN] E2E Maestro `apps/mobile/maestro/market_prices.yaml`.

### Implémentation GREEN

- [ ] T084 [US5] `services/api/app/economics/market_prices.py`, `services/api/app/routers/market_prices.py`, `services/workers/tasks/refresh_market_prices.py` (T080..T082).
- [ ] T085 [US5] View model `apps/mobile/src/economics/viewModels/marketPrices.ts` + tests.
- [ ] T086 [US5] [écran] [BLOQUÉ-DESIGN] `apps/mobile/src/screens/MarketPrices/` (F8-E5).

## Phase 8 : Maquettes et catalogue (autorisés sans validation)

- [ ] T087 [P] Maquettes haute fidélité FR et AR des écrans F8-E1 à F8-E5 (4 états chacun, RTL, montants MAD) dans `docs/design/010-farm-economics/` ; **ne pas** créer `VALIDATION.md`.
- [ ] T088 [P] Stories Storybook des composants demandés (`AmountInput`, `ReceiptCapture`, `MarginCard`, `StockLevelBar`, `PriceSparkline`) sans modifier `packages/ui` hors demande formalisée dans `decisions.md` ; captures PNG FR/AR.
- [ ] T089 [P] Test de parité i18n `packages/i18n/tests/parity.test.ts` : toutes les clés F8 présentes en `ary`, `ar`, `fr`.

## Phase 9 : Finition et transverse

- [ ] T090 [P] Mesure `make apk-size` ; si dépassement, `specs/010-farm-economics/apk-budget.env` (<= 52 Mo) + section « Dérogation » dans `decisions.md` (G9). Bloqué tant qu'aucun écran n'est codé.
- [ ] T091 [P] Vérifier `make test-pyramid` : trois niveaux présents pour chaque module touché (`services/api`, `services/workers`, `packages/domain`, `apps/mobile` ; Maestro bloqué consigné dans `decisions.md`).
- [ ] T092 [P] Couverture du code métier F8 >= 80 % (domaine TS, `app/economics`, `app/domain`).
- [ ] T093 Revue de sécurité transverse : aucun montant côté ouvrier (tous chemins), aucun 404 différencié, aucune URL de stockage client, aucun envoi externe sans validation (G1, G5, G6).
- [ ] T094 **make check vert** : `make check-fast-cached` en fin de groupe, puis `make check-cached` (avec e2e) avant `/aylal.release` ; écrans/Maestro bloqués consignés ; SC-001 et SC-007 (chronométrage de saisie, quatre états, RTL) restent à mesurer en recette tant que les écrans sont bloqués.
- [ ] T095 **Documentation de fin de module (/aylal.docs)** : `docs/modules/010-farm-economics/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md,diagrams/*.mmd,img/*}` via `make diagrams`.

## Récits reportés (P3)

- Récit 6 (comparaison anonyme avec les fermes similaires) : exige l'accord explicite et révocable de partage et un seuil d'anonymat ; non planifié dans cette version.

## Dépendances

Phase 1 -> Phase 2 (RED puis GREEN) -> Phases 3, 4 (P1 ; US3 dépend de US1 et US2 pour ses données) -> Phase 5 -> Phases 6, 7 (P2, indépendantes entre elles) -> Phases 8, 9. Les tâches `[BLOQUÉ-DESIGN]` (T051, T054, T059, T062, T067, T070, T076, T079, T083, T086) attendent T004.
