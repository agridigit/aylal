# Tâches : F3 — Tableau de bord et monitoring

**Branche** : `006-dashboard-monitoring` | **Entrées** : spec.md, plan.md, data-model.md, research.md, contracts/, quickstart.md
**Règle** : test first strict. Dans chaque bloc, les tests RED (unitaire `tests/unit/`, intégration `tests/integration/`, contrat `tests/contract/`, bout en bout `tests/e2e/` des services ou `apps/mobile/maestro/`) viennent AVANT l'implémentation, DOIVENT échouer (commit `test(006-dashboard-monitoring): red - <sujet>`), puis GREEN (`feat(006-dashboard-monitoring): green - <sujet>`), puis REFACTOR. Aucun test modifié pour passer (sauf contradiction avec la spec, notée dans `decisions.md`). Tout s'exécute dans Docker (`make test`, `make test-api`, `make test-mobile`, `make e2e`).
**Notation** : `[P]` = fichiers différents, aucune dépendance en cours. `[USn]` = récit n de spec.md. Critères cités `Rn-Am` = récit n, scénario d'acceptation m ; `CL` = cas limite ; `G1`..`G7` = garde-fous de plan.md (`G<n>-RED` / `G<n>-GREEN`).
**Séparation** : les tâches **non-écran** (domaine, API, base, synchro, workers, view models) ne dépendent PAS de la porte design. Les tâches **`[écran]`** dépendent de **T004** (porte design) ET de la **fusion de `004-design-system` dans main** ; aucune ne démarre avant.
**Chemins** : API = `services/api/`, domaine = `packages/domain/`, mobile = `apps/mobile/`, workers = `services/workers/`. Tests : `services/api/tests/{unit,integration,contract,e2e}/`, `services/workers/tests/`, `packages/domain/tests/`, `apps/mobile/src/**/__tests__/`, `apps/mobile/maestro/`, `tests/platform/`.

## Phase 1 : Mise en place

- [x] T001 Ajouter aux Dockerfiles `services/workers/Dockerfile` (GDAL, `numpy`, `rasterio`, `Pillow`, `shapely` si absent) et `services/api/Dockerfile` (`Pillow`, `numpy` si requis) ; à `apps/mobile/package.json` : `expo-speech`, `expo-location` (`expo-notifications` déjà F6). Jamais sur l'hôte.
- [x] T002 [P] Créer les clés i18n vides `packages/i18n/locales/{ary,ar,fr}/{dashboard,weather,alerts,vigor,zones,status,summary}.json` et étendre `packages/i18n/tests/parity.test.ts` (« vigueur » / « humidité des plantes » seuls mots affichés, R3-A4).
- [x] T003 [P] Créer les squelettes vides (`services/api/app/monitoring/`, `services/api/app/routers/{dashboard,alerts,vigor,zones,summary}.py`, `services/api/app/sync/monitoring.py`, `services/workers/tasks/`, `packages/domain/vectors/`, `apps/mobile/src/monitoring/`) sans logique, pour que les RED importent des modules existants.
- [ ] T004 **T-DESIGN-GATE (humain, bloquante pour tout `[écran]`, G7)** : maquettes haute fidélité arabe + français **validées par un humain** (validation consignée dans `specs/006-dashboard-monitoring/decisions.md`), dans `docs/design/006-dashboard-monitoring/`, pour F3-E1 tableau de bord, F3-E2 météo 7 jours, F3-E3 alertes, F3-E4 fiche vigueur (carte + courbe), F3-E5 détail de l'état, F3-E6 zone à vérifier + guidage (P1) ; puis F3-E7 comparaison N-1, F3-E8 résumé vocal (P2). Conformes à `docs/design/aylal-design-system.md` (jetons, 4 états, RTL, boutons >= 48 dp, plein soleil, couleur d'état jamais seule : icône + phrase). **Dépendance externe** : fusion de `004-design-system` dans main (reconstruit `packages/ui`), vérifiée avant tout écran. F3 ne modifie NI `packages/ui` NI `docs/design/aylal-design-system.md` ; composants manquants (`StatusBadge`, `WeatherDayCard`, `AlertRow`, `VigorChart`, `VigorMapOverlay`, `ZoneGuidanceCard`, `StaleDataBanner`) demandés par une note ajoutée à `decisions.md`.
- [x] T005 [P] Ajouter à `specs/006-dashboard-monitoring/decisions.md` (**ajout en fin de fichier, sans écraser** les points 1 à 7 existants) une section « Journal d'exécution » : suivi des tâches `[écran]` bloquées, des écarts de test (le cas échéant) et du numéro de migration recalé.

## Phase 2 : Fondations non-écran G1 à G6 (bloquent tous les récits)

### Tests RED d'abord, regroupés par couche

#### Unitaire

- [x] T006 [P] **G4-RED plafonds (unitaire)** : vecteur `packages/domain/vectors/f3_limits.json` + `packages/domain/tests/monitoring-limits.test.ts` + miroir `services/api/tests/unit/test_f3_monitoring_limits.py` : `limit` <= 100 (défaut 50), série <= 24 mois et <= 400 points, N-1 <= 2 x 200, horizon météo 8 jours, alertes <= 1 000/ferme et <= 20/parcelle, zones <= 5/parcelle, <= 200/ferme, polygone <= 200 sommets, note <= 500, photo <= 3 Mo, <= 20 observations/zone, <= 2 000/ferme/an, lot sync <= 100, retraitement <= 3/parcelle/jour, <= 5 jobs imagerie/ferme, raster <= 500 Mo, fenêtre init <= 12 mois.
- [x] T007 [P] **G1-RED matrice de rôles (unitaire)** : vecteur `packages/domain/vectors/f3_roles.json` + `packages/domain/tests/roles.test.ts` (étendu, assertions existantes inchangées) + `services/api/tests/unit/test_f3_roles_matrix.py` : owner/manager/worker x `dashboard.read|weather.read|status.read|alert.read|vigor.read|zone.read|zone.observe|zone.dismiss|alert.dismiss|imagery.reprocess|summary.read|summary.settings` ; aucun champ financier.
- [x] T008 [P] **G2-RED clé de cache et portée (unitaire)** `services/api/tests/unit/test_f3_cache_key.py` : clé `dash:{farm_id}:{role}:{user_id si worker}:{sha256(ids visibles triés)}:{data_version}` ; deux rôles/portées distincts ne partagent jamais d'entrée ; le staff partage par ferme+rôle+empreinte ; changement de parcelles visibles ou de `data_version` change la clé.
- [x] T009 [P] **G5-RED configuration et Maroc (unitaire)** `services/api/tests/unit/test_f3_config.py` : `AYLAL_WEATHER_URL`, `AYLAL_IMAGERY_URL`, `AYLAL_PUSH_URL`, `AYLAL_EXTERNAL_ALLOWED_HOSTS` vides par défaut (`${VAR:-}` dans `docker-compose.yml`, aucune clé en dépôt) ; URL non vide hors liste blanche ou sans clé requise -> démarrage refusé hors dev/test ; **test d'inventaire d'imports** : aucun SDK de fournisseur étranger (FCM/Google, etc.) dans le code F3.
- [x] T010 [P] **G5-RED passerelles « non disponible » (unitaire)** `services/api/tests/unit/test_f3_gateways_unavailable.py` : URL vide ou hôte hors liste -> `availability: "unavailable"` avec `reason` (`gateway_not_configured`, `gateway_unreachable`, `stale`), **aucune valeur inventée, interpolée ou par défaut** (champs de valeurs absents, pas de 0 ni de moyenne) ; météo > 24 h -> `stale` ; adaptateur espion : zéro appel réseau si non configuré.
- [x] T011 [P] **G5-RED minimisation sortante (unitaire)** `services/api/tests/unit/test_f3_outbound_allowlist.py` : schéma d'allowlist à clés exactes — météo `{lat_r, lon_r}` (0,1°) + dates ; imagerie identifiant de tuile MGRS + date ; push `{device_token, alert_id opaque, locale}` ; aucun id de ferme/utilisateur, nom, numéro ni géométrie de parcelle.
- [x] T012 [P] **G6-RED IP de confiance (unitaire)** `services/api/tests/unit/test_f3_client_ip.py` : `X-Forwarded-For` ignoré si le pair socket n'est pas dans `AYLAL_TRUSTED_PROXIES` (en-tête falsifié), pris en compte si fiable (saut le plus à droite non fiable) ; tests F1/F6 existants inchangés et verts.
- [x] T013 [P] **G6-RED objets opaques (unitaire)** `services/api/tests/unit/test_f3_opaque_refs.py` : schémas `extra=forbid` refusent `photo_key`, `map_key`, `raster_key` et toute URL dans un corps ; motif CHECK des clés `farms/{farm_id}/vigor/{uuid}.png` et `farms/{farm_id}/zone-photos/{uuid}`.
- [x] T014 [P] Règles de domaine partagées RED : vecteurs `packages/domain/vectors/f3_{alert_rules,parcel_status,anomaly,cloud_rule,reliability,notify_schedule,summary,guidance}.json`, tests `packages/domain/tests/{weather-thresholds,alert-rules,vigor,anomaly,parcel-status,status-sources,imagery-reliability,notification-schedule,voice-summary,guidance}.test.ts` et miroir `services/api/tests/unit/test_f3_domain_rules.py` (seuils par culture/stade avec fixtures seulement, sévérité, dédoublonnage `dedup_key`, tri rouge puis orange, règle 80 % à 79,9/80,0 %, fiabilité < 0,3 ha/serre, calendrier de notification gel < 18 h, ordre du résumé rouges d'abord, cap/distance de guidage).

#### Intégration

- [x] T015 [P] **G1-RED 404 inter-ferme** `services/api/tests/integration/test_f3_farm_isolation.py` : pour CHAQUE route F3 (dashboard, états, météo, alertes, scènes, vigueur, comparaison, zones, observations, résumé, préférences, retraitement), non-membre, membre retiré, ferme inexistante et ferme supprimée (`farms.deleted_at`) -> **404 de corps identique** `{"detail":"not_found"}` ; objet d'une autre ferme -> 404 (`farm_id` dans le WHERE) ; FK composites `(farm_id, parcel_id)` refusent toute référence inter-ferme.
- [x] T016 [P] **G1-RED 403 par rôle** `services/api/tests/integration/test_f3_role_authz.py` : ouvrier -> 403 sur `zone.dismiss`, `alert.dismiss`, `imagery.reprocess` (parcelle attribuée) ; ouvrier sur parcelle non attribuée, archivée ou inconnue -> 404 identique ; owner/manager OK ; ouvrier autorisé sur `zone.observe` attribuée seulement.
- [x] T017 [P] **G1-RED synchro scopée** `services/api/tests/integration/test_f3_sync_authz.py` : `/v1/sync/upload` -> lot entier refusé 403 si une écriture viole le rôle (rien d'écrit) ; non-membre 404 ; champs serveur (`farm_id` existant, `author_id`, `photo_key`, `status` de zone, `parcel_archived_at`) ignorés/rejetés ; idempotence par `applied_ops`.
- [x] T018 **G1-RED parité de tous les chemins** `services/api/tests/integration/test_f3_path_parity.py` : matrice paramétrée rôle x ferme {propre, autre, inconnue, supprimée} x parcelle {attribuée, non attribuée, archivée, inconnue} x chemin {REST, sync upload, export, résumé, agrégat} -> statuts et contenus identiques ; **test d'inventaire** qui échoue si une route, une table ou une tâche worker F3 n'apparaît pas dans la matrice.
- [x] T019 [P] **G1-RED parcelle archivée/invisible masquée PARTOUT** `services/api/tests/integration/test_f3_archived_parcel_hidden.py` : un seul prédicat `visible_parcels(ctx)` (`app/monitoring/access.py`) ; parcelle archivée ou non attribuée absente de REST (dashboard, états, alertes, zones, vigueur, comparaison), de `sync/monitoring.py`, de l'export de l'ouvrier, de `accounts/purge.py`, des agrégats (compteurs, tri, résumé), des destinataires **et** parcelles par destinataire des workers de notification, des caches ; owner/manager : fiche historique (vigueur) lisible en lecture seule mais absente du tableau de bord, des agrégats, sans alerte générée (FR-019) ; staff retrouve l'historique archivé dans l'export.
- [x] T020 [P] **G2-RED agrégats sans fuite** `services/api/tests/integration/test_f3_aggregate_no_leak.py` : ferme à 10 parcelles dont 3 attribuées à l'ouvrier, une rouge invisible -> compteurs `counts.red/orange/green`, surface, moyenne de vigueur, `ETag`, ordre, résumé vocal et notification de l'ouvrier **invariants** quand une parcelle invisible change d'état ; égalité avec un calcul manuel sur ses seules parcelles ; aucun champ « total ferme » (`farms.area_ha`, nombre de parcelles) ; ouvrier sans parcelle -> 0 partout (ni 404 ni total) ; deux portées ne partagent jamais d'entrée de cache ; invalidation par `data_version`.
- [x] T021 [P] **G3-RED règles PowerSync valides** `tests/platform/test_powersync_rules_valid.sh` + cas F3 dans `scripts/validate-sync-rules.sh` et `scripts/validate-sync-rules.mjs` : `infra/powersync/sync-rules.yaml` accepté par le service ; **ni jointure, ni sous-requête** ; colonnes explicites (jamais `SELECT *`) ; `photo_key`, `map_key`, `raster_key` jamais synchronisés ; seau ouvrier par requête de paramètres à une colonne (`parcel_id`) ; météo (niveau ferme) en seau ouvrier par `farm_id` ; `parcel_archived_at IS NULL` ; `daily_summaries` par `(farm_id, user_id)` sous appartenance active (voir T027b) ; test d'intégration : archiver une parcelle retire ses lignes (états, alertes, zones, points) du seau ouvrier **et** staff (hors historique de vigueur). Doit échouer avant les règles.
- [x] T022 [P] **G4-RED plafonds avant tout calcul** `services/api/tests/integration/test_f3_limits_enforced.py` : taille de corps lue d'abord (413/422 immédiat, `body_limit.py`) ; `limit` 101, série > 24 mois ou > 400 points, horizon météo != 8 jours, note 501 car., polygone > 200 sommets, photo > 3 Mo ou signature non JPEG/WebP -> refus ; lot sync de 101 -> 413 `batch_too_large` **avant toute écriture** ; **espion sur l'adaptateur passerelle et sur la lecture de raster : zéro appel** lors d'un refus ; aucune liste non bornée.
- [x] T023 [P] **G4-RED quotas sous verrou** `services/api/tests/integration/test_f3_quota_race.py` : 2 requêtes concurrentes pour chaque quota (observations/ferme/an, jobs de retraitement <= 3/parcelle/jour, jobs imagerie <= 5/ferme, zones, alertes <= 20/parcelle) via REST ET `sync/monitoring.py` : un seul passe ; `pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` puis comptage puis écriture dans la même transaction ; workers : verrou `monitoring:{farm}` (un recalcul d'états ne s'exécute pas deux fois en concurrence).
- [x] T024 [P] **G5-RED passerelles absentes en intégration** `services/api/tests/integration/test_f3_gateways_degraded.py` : sans URL configurée, dashboard/météo/vigueur répondent 200 avec `availability: "unavailable"` et `reason`, dernières données datées conservées, aucune valeur inventée ; passerelle injoignable -> `gateway_unreachable` ; météo > 24 h -> `stale` ; budget global journalier et 1 appel par cellule 0,1° et par 3 h (verrou Redis) ; aucun appel déclenché par une requête utilisateur (lecture cache seulement).
- [x] T025 [P] **G6-RED objets opaques et URL signées** `services/api/tests/integration/test_f3_opaque_objects.py` : `GET …/vigor/scenes/{scene_id}/map` résout `(scene_id, farm_id, parcel_id)` après contrôle de visibilité puis renvoie une URL signée MinIO de 15 min ; scène d'une autre ferme ou parcelle invisible -> 404 identique ; expiration de l'URL ; forgerie de clé (`photo_key`/`map_key`) -> champ refusé ; `photo_id` inconnu / autre ferme / autre utilisateur / consommé / expiré (24 h) -> 422 `invalid_object_ref` identique (pas d'oracle) ; IDOR inter-ferme ; mêmes règles sur REST et `/v1/sync/upload` ; photo stockée sous `farms/{farm_id}/zone-photos/{uuid}` (clé serveur).
- [x] T026 [P] **G6-RED limiteur Redis et X-Forwarded-For** `services/api/tests/integration/test_f3_rate_limit.py` : routes coûteuses (photo, retraitement, séries, comparaison, résumé) -> 429 + `Retry-After` ; `X-Forwarded-For` falsifié depuis un pair non fiable ne change pas la clé ; depuis un proxy fiable pris en compte.
- [x] T027 [P] **G1-RED export et purge** `services/api/tests/integration/test_f3_export_purge.py` : tables F3 incluses dans `accounts/export.py` (jeton push d'autrui exclu) et `accounts/purge.py` ; migration `0010_dashboard_monitoring` : 10 tables, FK composites, triggers de recopie `parcel_archived_at` (archivage, restauration, fusion), `valid` colonne générée, seuils de FIXTURE seulement.
- [x] T027a [P] **G1-RED membre retiré** (FR-021) `services/api/tests/integration/test_f3_member_removal.py` : membre retiré, rôle changé ou ferme supprimée/purgée -> `daily_summaries` et `notification_prefs` de ce membre supprimés (même transaction) ; REST `summary/today` et `summary/settings` -> 404 ; `/v1/sync/upload` -> 404 ; export -> aucune ligne de ses résumés ; synchro : le seau `user_summaries` n'est plus ouvert (paramètre vide) et aucune ligne `farm_id`/`user_id` d'un autre membre n'est servie ; `worker_parcels` purgé -> seau `farm_worker_monitoring` vide. Matrice REST x sync x export. Doit échouer avant T032/T034.
- [x] T027b [P] **G3-RED seaux par utilisateur** : étendre T021 (`tests/platform/test_powersync_rules_valid.sh`) : `user_summaries` a pour paramètre `farm_members ... removed_at IS NULL` et pour données `farm_id = bucket.farm_id AND user_id = bucket.user_id` ; échec si un seau par utilisateur se base sur `request.user_id()` seul.

#### Contrat

- [x] T028 [P] Contrat REST : `services/api/tests/contract/test_f3_openapi_contract.py` valide toutes les routes F3 contre `specs/006-dashboard-monitoring/contracts/openapi.yaml` (statuts 404/403/413/422/429, `extra=forbid`, aucun champ clé de stockage) et `services/api/tests/contract/test_f3_sync_rules_contract.py` contre `contracts/powersync-sync-rules.yaml` ; génération Zod -> JSON Schema -> Pydantic cohérente (`scripts/gen-pydantic.sh`).

#### Bout en bout

- [x] T029 RED e2e (API) fondations : `services/api/tests/e2e/test_f3_foundation_e2e.py` (ouvrier avec 3 parcelles sur 10 : tableau de bord, états, alertes et résumé limités à sa portée ; archivage -> disparition ; passerelles vides -> « non disponible ») et `services/workers/tests/test_f3_worker_scope.py` (tâches workers n'utilisent que `visible_parcels`).

### GREEN (après lancement des RED ci-dessus, qui doivent échouer)

- [x] T030 **G1-GREEN** : `packages/domain/src/{roles,monitoring-limits}.ts`, `services/api/app/domain/{roles.py,monitoring_limits.py}`, vecteurs T006/T007 ; `services/api/app/monitoring/access.py` (`visible_parcels(ctx)`, `farm_context`/`require`) ; fait passer T006, T007, T015, T016, T019.
- [x] T031 **Migration** `services/api/alembic/versions/0010_dashboard_monitoring.py` (numéro recalé au prochain libre), `services/api/app/db/models.py` (+ 10 modèles), triggers de recopie `parcel_archived_at`, GRANT, CHECK ; fait passer T027.
- [x] T032 **G1-GREEN sync/export/purge/parité** : `services/api/app/sync/monitoring.py` (authorize + apply, même `access.py`), `services/api/app/accounts/{export.py,purge.py}` étendus ; fait passer T017, T018, T027, T027a (purge des résumés/préférences au retrait, changement de rôle et suppression de ferme).
- [x] T033 **G2-GREEN** : `services/api/app/monitoring/{service.py,cache.py}` (agrégats calculés sur `parcel_status WHERE <visible_parcels>`, clé de cache portée) ; fait passer T008, T020.
- [x] T034 **G3-GREEN** : `infra/powersync/sync-rules.yaml` étendu (colonnes explicites, seaux, dénormalisation), `scripts/validate-sync-rules.{sh,mjs}` ; fait passer T021, T027a, T027b, T028 (volet synchro).
- [x] T035 **G4-GREEN** : contrôles de plafonds avant parsing/I/O (`body_limit.py`), verrous par ferme et `monitoring:{farm}` dans `service.py`/`sync/monitoring.py`/workers ; fait passer T006, T022, T023.
- [x] T036 **G5-GREEN** : `services/api/app/monitoring/gateways.py` (liste blanche, `unavailable`, minimisation, `docker-compose.yml` avec `${VAR:-}`), validation de configuration au démarrage ; fait passer T009, T010, T011, T024.
- [x] T037 **G6-GREEN** : `services/api/app/monitoring/uploads.py` (`observation_uploads`, identifiants opaques, URL signées 15 min), `app/auth/client_ip.py` réutilisé, limiteur Redis sur routes F3 ; fait passer T012, T013, T025, T026.
- [x] T038 Domaine partagé GREEN : `packages/domain/src/{weather-thresholds,alert-rules,vigor,anomaly,parcel-status,status-sources,imagery-reliability,notification-schedule,voice-summary,guidance}.ts`, miroirs `services/api/app/domain/{weather_thresholds,alert_rules,vigor,anomaly,parcel_status,imagery_reliability,notification_schedule}.py` ; fait passer T014.
- [x] T039 GREEN contrat/e2e fondations : routeurs `services/api/app/routers/{dashboard,alerts,vigor,zones,summary}.py` (squelettes branchés sur `access.py`) ; fait passer T028, T029. REFACTOR sans changer le comportement.

## Phase 3 : Récit 1 — Météo de la ferme (P1) [US1]

**Test indépendant** : tableau de bord d'une ferme localisée, avec et sans réseau. **Dépend de** : Phase 2.

- [x] T040 [P] [US1] RED unitaire R1-A1, R1-A2, CL : `services/api/tests/unit/test_f3_weather_days.py` (8 jours J0 + 7, champs température/pluie/vent/humidité/icône, `stale` > 24 h), `packages/domain/tests/staleness.test.ts`, `apps/mobile/src/monitoring/__tests__/staleness.test.ts`.
- [x] T041 [P] [US1] RED intégration R1-A1, R1-A2, CL : `services/api/tests/integration/test_f3_weather.py` (`farm_weather` lu depuis le cache, ferme non localisée -> `unavailable`/invitation, ferme sans parcelle -> météo seule) et `services/workers/tests/test_refresh_weather.py` (1 appel par cellule 0,1°/3 h, verrou Redis).
- [x] T042 [P] [US1] RED contrat : `services/api/tests/contract/test_f3_weather_contract.py`.
- [x] T043 [US1] RED e2e (API) : `services/api/tests/e2e/test_f3_weather_e2e.py` (R1-A1, R1-A2 via données synchronisées datées).
- [ ] T044 [US1] GREEN : `services/api/app/monitoring/weather.py`, `services/workers/tasks/refresh_weather.py`, route météo/dashboard dans `services/api/app/routers/dashboard.py` ; fait passer T040 à T043.
- [ ] T045 [US1] GREEN view model hors écran : `apps/mobile/src/monitoring/viewModels/weatherViewModel.ts`, `apps/mobile/src/monitoring/staleness.ts` (+ `__tests__`).
- [ ] T046 [US1] [écran] RED puis GREEN F3-E1 `apps/mobile/src/screens/Dashboard/` (partie météo), F3-E2 `apps/mobile/src/screens/Weather7Days/` (+ `__tests__`, 4 états, RTL, Maestro `apps/mobile/maestro/{weather_offline,dashboard_30s}.yaml`) ; dépend de T004 + fusion 004.

## Phase 4 : Récit 2 — Alertes météo par culture et stade (P1) [US2]

**Test indépendant** : simuler chaque type de prévision sur une culture sensible. **Dépend de** : Phase 2, Récit 1.

- [x] T047 [P] [US2] RED unitaire R2-A1 à R2-A4 : `packages/domain/tests/alert-rules.test.ts` (vecteur `f3_alert_rules.json`) + `services/api/tests/unit/test_f3_alert_rules.py` (gel sensible/non sensible au stade, chergui, forte pluie, vent fort -> `advice_key=do_not_spray`, `dedup_key`, transitions `active/resolved/dismissed/expired`) + `packages/domain/tests/notification-schedule.test.ts` (gel notifié avant 18 h, `frost_notify_hour`=17).
- [x] T048 [P] [US2] RED intégration R2-A1 à R2-A4 : `services/api/tests/integration/test_f3_alerts.py` (alerte avec parcelle, gravité, raison ; 403 `alert.dismiss` ouvrier ; 20 actives/parcelle ; archivée -> aucune alerte) et `services/workers/tests/test_evaluate_alerts.py` (seuils de fixture, destinataires et parcelles par destinataire via `visible_parcels`, `notify_at`).
- [x] T049 [P] [US2] RED contrat : `services/api/tests/contract/test_f3_alerts_contract.py`.
- [x] T050 [US2] RED e2e (API) : `services/api/tests/e2e/test_f3_alerts_e2e.py` (gel à 48 h -> `notify_at` avant 18 h la veille ; gel non dépassé -> aucune alerte).
- [ ] T051 [US2] GREEN : `services/api/app/routers/alerts.py`, `services/workers/tasks/{evaluate_alerts.py,import_crop_thresholds.py}` (import validé par l'agronomie, aucune valeur de production inventée) ; fait passer T047 à T050.
- [ ] T052 [US2] GREEN non-écran mobile : `apps/mobile/src/monitoring/alertNotifications.ts` (notifications locales programmées depuis les alertes synchronisées, hors ligne) + view model + `__tests__`.
- [ ] T053 [US2] [écran] RED puis GREEN F3-E3 `apps/mobile/src/screens/Alerts/` (+ `__tests__`, Maestro `apps/mobile/maestro/frost_alert.yaml`) ; dépend de T004 + fusion 004.

## Phase 5 : Récit 3 — Vigueur par satellite (P1) [US3]

**Test indépendant** : créer une parcelle, historique, carte, courbe ; parcelle nuageuse ou petite. **Dépend de** : Phase 2.

- [x] T054 [P] [US3] RED unitaire R3-A2, R3-A3 : `packages/domain/tests/{vigor,imagery-reliability}.test.ts` + `services/api/tests/unit/test_f3_cloud_rule.py` (79,9 % rejetée, 80,0 % acceptée, `valid` généré) et fiabilité < 0,3 ha / serre.
- [x] T055 [P] [US3] RED intégration R3-A1 à R3-A4 : `services/api/tests/integration/test_f3_vigor.py` (scène `rejected_cloud` jamais affichée, dernière valide servie avec sa date ; libellés i18n sans « NDVI/NDMI » ; fenêtre <= 24 mois, <= 400 points ; reprocess 403 ouvrier) ; `services/workers/tests/test_ingest_imagery.py` (téléchargement par tuile, raster <= 500 Mo vérifié avant lecture, stats zonales dans le worker, géométrie jamais sortante) ; `services/workers/tests/test_backfill_parcel_vigor.py` (1 backfill actif/parcelle, 12 mois, `duration_s` mesuré).
- [x] T056 [P] [US3] RED contrat : `services/api/tests/contract/test_f3_vigor_contract.py`.
- [x] T057 [US3] RED e2e (API) : `services/api/tests/e2e/test_f3_vigor_e2e.py` (parcelle créée -> historique 12 mois publié ; SC-002 < 10 min mesuré sur jeu de test).
- [ ] T058 [US3] GREEN : `services/api/app/monitoring/imagery.py`, `services/api/app/routers/vigor.py`, `services/workers/tasks/{ingest_imagery.py,backfill_parcel_vigor.py}` ; fait passer T054 à T057.
- [ ] T059 [US3] GREEN view model + courbe : `apps/mobile/src/monitoring/viewModels/vigorViewModel.ts` (données de courbe plafonnées, rendu SVG/Skia sans bibliothèque lourde) + `__tests__`.
- [ ] T060 [US3] [écran] RED puis GREEN F3-E4 `apps/mobile/src/screens/ParcelVigor/` (+ `__tests__`, Maestro `apps/mobile/maestro/vigor_cloud.yaml`) ; dépend de T004 + fusion 004.

## Phase 6 : Récit 4 — Zones à vérifier et guidage (P1) [US4]

**Test indépendant** : série d'images avec une zone en baisse. **Dépend de** : Phase 5.

- [x] T061 [P] [US4] RED unitaire R4-A1, R4-A2 : `packages/domain/tests/{anomaly,guidance}.test.ts` (vecteurs `f3_anomaly.json`, `f3_guidance.json`) + `services/api/tests/unit/test_f3_anomaly.py` ; `apps/mobile/src/monitoring/__tests__/guidance.test.ts` (cap/distance hors réseau).
- [x] T062 [P] [US4] RED intégration R4-A1 à R4-A3 : `services/api/tests/integration/test_f3_zones.py` (zone délimitée, <= 5/parcelle, <= 200/ferme, polygone <= 200 sommets, observation rattachée via REST et `/v1/sync/upload`, transition `open -> visited`, `zone.dismiss` 403 ouvrier, ouvrier limité à ses parcelles) et `services/workers/tests/test_detect_zones.py`.
- [x] T063 [P] [US4] RED contrat : `services/api/tests/contract/test_f3_zones_contract.py`.
- [x] T064 [US4] RED e2e (API) : `services/api/tests/e2e/test_f3_zones_e2e.py` (nouvelle scène -> zone -> observation avec photo opaque -> `visited`).
- [ ] T065 [US4] GREEN : `services/api/app/monitoring/zones.py`, `services/api/app/routers/zones.py`, `services/workers/tasks/detect_zones.py`, observations dans `services/api/app/sync/monitoring.py` ; fait passer T061 à T064.
- [ ] T066 [US4] GREEN non-écran mobile : `apps/mobile/src/monitoring/guidance.ts` (expo-location, fonds MapLibre en cache) + view model + `__tests__`.
- [ ] T067 [US4] [écran] RED puis GREEN F3-E6 `apps/mobile/src/screens/ZoneGuidance/` (+ `__tests__`, Maestro `apps/mobile/maestro/zone_guidance.yaml`) ; dépend de T004 + fusion 004.

## Phase 7 : Récit 5 — État résumé en couleur (P1) [US5]

**Test indépendant** : combiner chaque source d'état. **Dépend de** : Récits 1 à 4 (sources).

- [x] T068 [P] [US5] RED unitaire R5-A1 à R5-A5 : `packages/domain/tests/{parcel-status,status-sources}.test.ts` (vecteur `f3_parcel_status.json` : combinaison, doute = orange, vert « rien à faire », tri rouge puis orange, sources F4/F5 absentes ignorées sans erreur) + `services/api/tests/unit/test_f3_parcel_status.py`.
- [x] T069 [P] [US5] RED intégration R5-A1 à R5-A4 : `services/api/tests/integration/test_f3_status.py` (`parcel_status_items` avec source expliquée, adaptateur F6 « opérations en retard » disponible, F4/F5 absents, aucun item pour source indisponible, ouvrier limité) et `services/workers/tests/test_recompute_status.py` (recalcul < 5 min après signal, verrou `monitoring:{farm}`).
- [x] T070 [P] [US5] RED contrat : `services/api/tests/contract/test_f3_status_contract.py`.
- [x] T071 [US5] RED e2e (API) : `services/api/tests/e2e/test_f3_status_e2e.py` (signaux météo + vigueur + opération en retard -> couleur, phrase, tri, détail).
- [ ] T072 [US5] GREEN : `services/api/app/monitoring/status_sources.py`, `services/workers/tasks/recompute_status.py`, routes d'état dans `services/api/app/routers/dashboard.py` ; fait passer T068 à T071.
- [ ] T073 [US5] GREEN view model : `apps/mobile/src/monitoring/viewModels/{dashboardViewModel,statusDetailViewModel}.ts` (tri, 200 parcelles < 2 s depuis SQLite) + `__tests__`.
- [ ] T074 [US5] [écran] RED puis GREEN F3-E1 (liste des parcelles par état) `apps/mobile/src/screens/Dashboard/`, F3-E5 `apps/mobile/src/screens/StatusDetail/` (+ `__tests__`, Maestro `apps/mobile/maestro/{status_detail,worker_scope}.yaml`) ; dépend de T004 + fusion 004.

## Phase 8 : Récit 6 — Comparaison N-1 (P2) [US6]

**Dépend de** : Récit 3.

- [ ] T075 [P] [US6] RED unitaire + intégration + contrat R6-A1, R6-A2 : `packages/domain/tests/vigor.test.ts` (alignement des dates), `services/api/tests/integration/test_f3_year_compare.py` (<= 2 x 200 points, sans historique N-1 -> message explicatif, jamais de courbe vide), `services/api/tests/contract/test_f3_compare_contract.py`.
- [ ] T076 [US6] RED e2e (API) : `services/api/tests/e2e/test_f3_year_compare_e2e.py`.
- [ ] T077 [US6] GREEN : route comparaison dans `services/api/app/routers/vigor.py` + view model `apps/mobile/src/monitoring/viewModels/yearCompareViewModel.ts` (+ `__tests__`).
- [ ] T078 [US6] [écran] RED puis GREEN F3-E7 `apps/mobile/src/screens/YearCompare/` (+ `__tests__`, Maestro `apps/mobile/maestro/year_compare.yaml`) ; dépend de T004 + fusion 004.

## Phase 9 : Récit 7 — Résumé vocal (P2) [US7]

**Dépend de** : Récits 2 et 5.

- [ ] T079 [P] [US7] RED unitaire R7-A1, R7-A2 : `packages/domain/tests/voice-summary.test.ts` (vecteur `f3_summary.json` : rouges d'abord, langue ary/ar/fr, portée du destinataire) + `apps/mobile/src/monitoring/__tests__/voiceSummary.test.ts` (repli arabe puis texte si pas de voix darija).
- [ ] T080 [P] [US7] RED intégration + contrat R7-A1 à R7-A3 : `services/api/tests/integration/test_f3_daily_summary.py` (un destinataire par ligne, payload limité à la portée, `summary_hour`, aucune fuite d'une parcelle invisible, 429 sur résumé) et `services/workers/tests/test_send_daily_summary.py`, `services/api/tests/contract/test_f3_summary_contract.py`.
- [ ] T081 [US7] RED e2e (API) : `services/api/tests/e2e/test_f3_summary_e2e.py`.
- [ ] T082 [US7] GREEN : `services/api/app/routers/summary.py`, `services/workers/tasks/send_daily_summary.py`, `apps/mobile/src/monitoring/voiceSummary.ts` (expo-speech, local, hors ligne) + view model + `__tests__`.
- [ ] T083 [US7] [écran] RED puis GREEN F3-E8 `apps/mobile/src/screens/VoiceSummary/` (+ `__tests__`, Maestro `apps/mobile/maestro/voice_summary.yaml`) ; dépend de T004 + fusion 004.

## Phase finale : Finition

- [ ] T084 Revue transverse non-écran : couverture >= 80 % du code métier F3, `scripts/check-test-pyramid.sh` vert (unitaire, intégration, contrat, e2e pour chaque récit P1), aucun `// eslint-disable`, aucune chaîne en dur, parité i18n.
- [ ] T085 **Mesure APK (`make apk-size`)** : construire (`make apk`) puis mesurer `app-release.apk` avec `scripts/check-apk-size.sh` après ajout d'`expo-speech` et `expo-location` (budget 40 Mo par défaut ; budget de branche possible via `specs/006-dashboard-monitoring/apk-budget.env` seulement si une dérogation est acceptée). **Rappel : toute dérogation au budget APK exige une section « Dérogation » dans `specs/006-dashboard-monitoring/decisions.md`** (valeur, mesure, cause, alternatives écartées, condition de réexamen ; plafond absolu 60 Mo ; décision humaine requise) ; ne jamais relâcher un seuil sans cette section.
- [ ] T086 **`make check` vert** (sync-rules, test-deps, test-pyramid, lint, typecheck, tests, coverage, test-visual, `apk-size`, diagrams, e2e) ; les tâches `[écran]` bloquées par T004/004 sont signalées dans `decisions.md` si non terminées.
- [ ] T087 **Documentation de fin de module (/aylal.docs)** : `docs/modules/006-dashboard-monitoring/{ingenieur.md,agriculteur.fr.md,agriculteur.ar.md}`, `diagrams/*.mmd` (flowchart, sequenceDiagram, erDiagram, stateDiagram-v2 des alertes/zones/scènes), rendus `img/*.svg` et `img/*.png` via `make diagrams`, image ET bloc de code source intégrés.

## Dépendances et exécution

- Phase 1 -> Phase 2 (RED T006-T029 dont T027a/T027b [P] possibles ensemble, puis GREEN T030 -> T031 -> T032..T039) -> récits P1 (R1 d'abord ; R2 et R3 après R1/Phase 2 ; R4 après R3 ; R5 après R1-R4) -> P2 (R6, R7).
- T004 (porte design + fusion 004) bloque UNIQUEMENT les tâches `[écran]` : T046, T053, T060, T067, T074, T078, T083. Tout le reste progresse sans elle.
- MVP : Phases 1-2 + Récit 1 non-écran, puis Récit 2.

## Récits reportés (P3)

Aucun récit P3 dans la spec : rien n'est reporté. Hors périmètre rappelé : irrigation F4 et risque sanitaire F5 (sources ignorées sans erreur), coûts F8, push tiers payant, TTS étranger.
