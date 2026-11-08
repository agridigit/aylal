# Modèle de données : F4 — Irrigation et bilan hydrique

Migration `0012_irrigation_water_balance` (provisoire). Toutes les tables de ferme portent `farm_id` et des clés étrangères composites `(farm_id, parcel_id)`. Colonnes de synchro communes (`SYNC` de F2 : `updated_at`, `server_version`, `field_versions`). Aucune valeur agronomique n'est insérée par la migration (fixtures de test seulement).

## Tables de ferme

| Table | Colonnes principales | Règles |
| --- | --- | --- |
| `irrigation_systems` | `id`, `farm_id`, `parcel_id`, `kind` (`drip`/`sprinkler`/`pivot`/`gravity`), `emitter_flow_lph`, `emitter_spacing_m`, `row_spacing_m`, `pump_flow_m3h`, `sectors_count`, `efficiency` (null = défaut du type), `efficiency_is_default` (calculée), `parcel_archived_at` | 1 active par parcelle (`UNIQUE (farm_id, parcel_id)`). `drip` : (`emitter_flow_lph`, `emitter_spacing_m`, `row_spacing_m`) **ou** `pump_flow_m3h` ; autres : `pump_flow_m3h` obligatoire. Tout débit/écartement > 0 ; `sectors_count` 1..50 ; `efficiency` 0 < e <= 1. Parcelle `irrigation = rainfed` -> écriture refusée (422). Validation partagée avec le domaine |
| `irrigation_system_versions` | `id`, `farm_id`, `system_id`, `parcel_id`, `snapshot jsonb`, `changed_by`, `changed_at` | Historique (<= 50 par installation), jamais supprimé |
| `irrigation_events` | `id` (idempotence client), `farm_id`, `parcel_id`, `season_id`, `operation_id` (serveur, `uuid5(NS_F4, farm_id:event_id)`), `performed_on`, `sector_no` (null = tous), `input_mode` (`duration`/`volume`), `duration_min`, `volume_m3`, `net_mm` (dérivé), `author_id`, `note`, `status` (`done`/`cancelled`), `parcel_archived_at` | `performed_on` : <= aujourd'hui local, >= aujourd'hui − 400 j (horloge injectée). `duration_min` 1..1440 ; `volume_m3` > 0 ; les dérivés (`volume_m3`/`duration_min` complémentaire, `net_mm`) sont **recalculés côté serveur** depuis l'installation. `operation_id` **dérivé côté serveur**, jamais lu du client (le client ne choisit pas la clé primaire de `operations`). Pas de DELETE : `status='cancelled'` |
| `irrigation_applied` | `id` (= event id), `farm_id`, `parcel_id`, `season_id`, `performed_on`, `sector_no`, `volume_m3`, `net_mm`, `parcel_archived_at` | **Lecture dénormalisée sans auteur ni note**, alimentée par trigger depuis `irrigation_events` (done uniquement) : sert au bilan et à la consommation de tous les rôles (G3) |
| `water_analyses` | `id`, `farm_id`, `parcel_id`, `water_source` (libellé libre <= 80), `ec_ds_m`, `analysed_on`, `author_id`, `parcel_archived_at` | `0 < ec_ds_m <= 100` ; `analysed_on` <= aujourd'hui local ; <= 50 par parcelle ; jamais supprimée (annulation par `status`) ; non synchronisée aux ouvriers |
| `water_balance_days` | `id`, `farm_id`, `parcel_id`, `season_id`, `day` (date locale), `et0_mm`, `et0_method` (`gateway`/`hargreaves`), `kc`, `etc_mm`, `rain_mm`, `rain_source` (`observed`/`forecast`/`ignored_greenhouse`), `rain_eff_mm`, `irrigation_net_mm`, `taw_mm`, `raw_mm`, `depletion_mm`, `moisture_source` (null/`sensor:<id>`), `inputs_hash`, `parcel_archived_at` | Journal du bilan, **rejouable** ; `UNIQUE (parcel_id, season_id, day)` ; fenêtre <= 400 jours ; écrit par worker/serveur sous verrou de ferme. Synchronisé en lecture seule (mobile recalcule aussi) |
| `irrigation_plans` | `id`, `farm_id`, `parcel_id`, `season_id`, `for_date`, `kind` (`irrigate`/`postpone_rain`/`no_need`/`rainfed_stress`/`unavailable`), `total_minutes`, `sectors jsonb [{sector_no, minutes, volume_m3}]`, `net_need_mm`, `leaching_fraction`, `stress_level` (`none`/`watch`/`high`), `confidence` (`high`/`medium`/`low`), `assumptions jsonb [{key, value, source}]`, `worker_assumptions jsonb` (vue ouvrier, voir « Vue ouvrier »), `unavailable_reason`, `computed_at`, `ready_before_7` (bool), `parcel_archived_at` | **Nom attendu par F3** (`status_sources._TABLE_OF`) ; une ligne par (parcelle, jour) ; l'ancien conseil n'est jamais écrasé s'il reste le « dernier connu » sans nouveau calcul valide ; `UNIQUE (parcel_id, for_date)` ; `assumptions` = clés i18n + valeurs, aucun texte |
| `irrigation_jobs` | `id`, `farm_id`, `parcel_id`, `from_date`, `state` (`queued`/`running`/`done`/`failed`) | Recalculs coalescés : 1 job `queued` par parcelle (date la plus ancienne), <= 5 actifs par ferme ; créé sous le verrou de ferme |
| `moisture_corrections` | `id`, `farm_id`, `parcel_id`, `measured_on`, `source`, `depletion_mm`, `received_at` | Écrit par le service interne `ingest_moisture` (F9) ; aucune route ; lu par le bilan |
| `irrigation_notification_log` | `farm_id`, `user_id`, `for_date`, `sent_at` | **Par utilisateur** : appartenance active exigée ; purgée à la sortie, au changement de rôle, à la suppression de ferme |
| `weather_observed` (globale) | `cell_id`, `day`, `rain_mm`, `fetched_at` | Pluies observées par cellule 0,1° (worker, passerelle facultative) ; PK `(cell_id, day)` ; aucune donnée de ferme |

## Référentiels (globaux, **vides** à la livraison)

| Table | Colonnes | Notes |
| --- | --- | --- |
| `crop_irrigation_params` | `crop_slug`, `stage_key`, `kc`, `root_depth_m`, `depletion_fraction`, `ece_threshold_ds_m`, `ece_max_ds_m`, `validated`, `validated_by`, `source`, `imported_at` | Clé de stade = `crops.stages[].key` (F2). Import par `import_irrigation_params` ; ligne absente -> `unavailable` |
| `soil_textures` | `texture_key`, `available_water_mm_per_m`, `validated_by`, `source` | `parcels.soil` mappé par clé ; défaut prudent = ligne de réserve minimale |
| `irrigation_params` | `key`, `value jsonb`, `validated_by`, `source` | Clés : `effective_rain` (`{method, params}`), `leaching_max`, `stress_watch_ratio`, `stale_plan_hours`... |

## Entités du domaine (Zod -> JSON Schema -> Pydantic)

`IrrigationSystemInput`, `IrrigationEventInput`, `WaterAnalysisInput`, `BalanceInputs`, `BalanceDay`, `Advice` (`kind`, `sectors`, `total_minutes`, `confidence`, `assumptions[]`, `unavailable_reason`), `Assumption` (`key`, `value`, `source`), `StressLevel`.

## Relations

`parcels 1-1 irrigation_systems` ; `irrigation_systems 1-n irrigation_system_versions` ; `parcels 1-n irrigation_events 1-1 operations` (via `operation_id` dérivé par le serveur) ; `irrigation_events 1-1 irrigation_applied` ; `seasons 1-n water_balance_days` ; `parcels 1-n irrigation_plans` ; `parcels 1-n water_analyses`.

## Transitions d'état

- `irrigation_events.status` : `done` -> `cancelled` (jamais l'inverse ; l'annulation déclenche le recalcul à la date de l'événement).
- `irrigation_plans.kind` : recalculé chaque nuit et à chaque météo reçue ; devient `unavailable` seulement s'il n'existe aucun conseil valide antérieur (sinon l'ancien est servi avec sa date et `confidence=low`, FR-017).

## Vue ouvrier « worker-safe » (G1, décisions point 19)

`assumptions` et `leaching_fraction` peuvent révéler l'analyse d'eau (ECw, source d'eau, âge de l'analyse), le sol (réserve utile) ou la salinité : ils ne sont **jamais** servis au rôle ouvrier. `irrigation_plans.worker_assumptions` est écrite par le serveur dans la **même transaction** que `assumptions` (jamais par trigger libre, jamais par le client), par `app/irrigation/worker_view.py` (miroir `packages/domain/src/advice-worker-view.ts`, vecteur `f4_worker_view.json`) : **liste blanche** de clés (`et0`, `kc`, `effective_rain`, `efficiency`, `application_rate`, `rain_source`) ; toute autre clé est écartée (deny-by-default, y compris les clés futures). `water_balance_days.taw_mm`, `raw_mm` et `moisture_source` ne sont pas servis à l'ouvrier. `leaching_fraction` n'est pas servie à l'ouvrier (la durée conseillée, elle, reste servie : l'ouvrier doit l'exécuter). `unavailable_reason` reste servi (code générique, aucune valeur de ferme). Cette vue est la seule source pour : seau PowerSync `farm_worker_irrigation`, REST `getAdvice`/`listAdvice`, export de l'ouvrier, rappels et notifications.

## Visibilité (G1)

`visible_parcels(ctx)` = `farm_id = :farm AND archived_at IS NULL` (+ attribution pour l'ouvrier). Appliqué à : toutes les lectures REST, `sync/irrigation.py`, `export.py`, `purge.py`, agrégats de consommation, calcul de bilan/rappels (parcelle archivée exclue pour tous les calculs et notifications). `parcel_archived_at` recopié par trigger serveur à l'archivage, la restauration et la fusion.

## Export et suppression (FR-021)

`accounts/export.py` ajoute la clé `irrigation` (installations + versions, événements, analyses, plans, bilans) ; l'export de l'ouvrier ne contient que ses événements sur ses parcelles non archivées ; s'il inclut un jour des plans, ce serait uniquement la vue `worker_assumptions` (aucune analyse d'eau, aucun sol, aucun `leaching_fraction`). `accounts/purge.py` : suppression de ferme -> `ON DELETE CASCADE` depuis `farms` (aucun DELETE explicite sur les tables protégées) ; sortie de membre -> journaux de notification supprimés, `author_id` conservé ; suppression de compte -> `author_id` mis à NULL par la fonction de maintenance F6 étendue (et `note` vidée si le compte en est l'auteur), journaux supprimés.
