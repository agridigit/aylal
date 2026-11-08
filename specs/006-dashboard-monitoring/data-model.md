# Modèle de données : F3

Migration `0010_dashboard_monitoring` (numéro recalé au dernier libre). UUID v7. Toute table de ferme porte `farm_id NOT NULL` et des clés étrangères **composites** `(farm_id, parcel_id)`. Toute table synchronisée porte `parcel_archived_at` (recopié par triggers serveur depuis `parcels.archived_at`, y compris fusion) pour des règles PowerSync **sans jointure**.

## Référentiel / global (sans `farm_id`, aucune donnée personnelle)

**crop_weather_thresholds** : `id`, `crop_slug`, `stage_key`, `frost_c numeric NULL`, `chergui_tmax_c`, `chergui_rh_max_pct`, `chergui_wind_kmh`, `heavy_rain_mm_24h`, `strong_wind_kmh` (déconseille le traitement), `source`, `validated_by` (agronome), `validated_at`. Unique `(crop_slug, stage_key)`. Écriture par import seulement ; fixtures de test dans la migration, **aucune valeur agronomique de production**.
**monitoring_params** : `key`, `value jsonb` (`cloud_min_clear_pct`=80, `min_area_ha`=0.3, `frost_notify_hour`=17, `summary_hour`=7, `anomaly_drop`, `anomaly_min_pixels`, `weather_stale_hours`=24).
**imagery_tiles** : `tile_id` (MGRS), `last_ingested_on`. **imagery_scenes** : `id`, `tile_id`, `acquired_on`, `cloud_pct_scene`, `raster_key` (MinIO, serveur seulement, jamais exposé), `ingested_at`. Public, partagé entre fermes.
**weather_cells** : `cell_id` (`lat_r:lon_r`, pas 0,1°), `fetched_at`, `days jsonb` (8 jours : `date, tmin, tmax, rain_mm, wind_kmh, humidity_pct, icon_code`), `source`. Aucun lien vers une ferme.

## Par ferme

**farm_weather** (lecture dénormalisée, synchronisée) : `farm_id` (PK), `cell_id`, `fetched_at`, `availability` (`ok|stale|unavailable`), `reason NULL`, `days jsonb` (copie de la cellule). Pas de coordonnées de ferme.

**alerts** : `id`, `farm_id`, `parcel_id`, `season_id`, `crop_slug`, `type` (`frost|chergui|heavy_rain|strong_wind`), `severity` (`info|warning|critical`), `source` (`forecast`), `status` (`active|resolved|dismissed|expired`), `forecast_day date`, `reason_key`, `reason_params jsonb` (valeurs, seuil, stade), `advice_key NULL` (ex. `do_not_spray`), `notify_at timestamptz NULL`, `notified_at NULL`, `revision int`, `dedup_key` UNIQUE, `parcel_archived_at`, `created_at`, `updated_at`. CHECK `type`/`severity`/`status` ; ≤ 20 actives par parcelle (trigger).
**parcel_status** : `parcel_id` (PK), `farm_id`, `color` (`green|orange|red`), `reason_key`, `reason_params jsonb`, `rank int`, `computed_at`, `data_age_at` (plus ancienne source utilisée), `imagery_reliability` (`ok|low`), `parcel_archived_at`.
**parcel_status_items** : `id`, `farm_id`, `parcel_id`, `source` (`weather_alert|vigor_anomaly|overdue_operations|irrigation_need|health_risk`), `severity` (`watch|act`), `reason_key`, `reason_params`, `source_ref` (id d'alerte/zone/opération, **id serveur**), `observed_at`, `parcel_archived_at`. Aucun item pour une source indisponible.
**parcel_vigor_points** : `id`, `farm_id`, `parcel_id`, `scene_id`, `acquired_on`, `vigor_mean`, `plant_moisture_mean` (colonnes nommées côté code `ndvi_mean`/`ndmi_mean`, jamais exposées par ces noms dans l'UI), `clear_pct`, `valid bool` (clear_pct >= 80), `reliability`, `season_id NULL`, `parcel_archived_at`. Unique `(parcel_id, scene_id)`. Seuls `valid = true` sont publiés ; les rejetées gardent leur trace dans `parcel_scene_log` (id, parcel_id, scene_id, `rejected_cloud|ok|error`), non synchronisée.
**vigor_maps** : `id` (= `map_id` opaque), `farm_id`, `parcel_id`, `scene_id`, `acquired_on`, `map_key` (MinIO `farms/{farm_id}/vigor/{uuid}.png`, **serveur seulement**, CHECK sur le motif), `bounds` (bbox arrondie), `parcel_archived_at`. Servi par URL signée 15 min.
**attention_zones** : `id`, `farm_id`, `parcel_id`, `geometry Polygon`, `centroid Point`, `detected_on`, `drop_score`, `area_ha`, `status` (`open|dismissed|visited|resolved`), `reason_key`, `parcel_archived_at`. ≤ 5 ouvertes par parcelle.
**zone_observations** : `id` (UUID client, idempotence), `farm_id`, `zone_id`, `parcel_id`, `author_id`, `note` (≤ 500), `photo_key NULL` (serveur, motif `farms/{farm_id}/zone-photos/{uuid}`), `created_at`, `parcel_archived_at`. Écrite par `/v1/sync/upload`.
**observation_uploads** : `id` (= `photo_id` opaque), `farm_id`, `user_id`, `object_key` (serveur), `expires_at`, `consumed_at`. Usage unique, 24 h.
**daily_summaries** : `id`, `farm_id`, `user_id` (destinataire), `summary_date`, `locale`, `payload jsonb` (liste ordonnée `{parcel_id, color, reason_key}` **limitée à la portée du destinataire** + `weather_code`), `created_at`. Unique `(user_id, farm_id, summary_date)`. **Cycle de vie par utilisateur** : suppression du membre, changement de rôle (la portée change) et suppression/purge de ferme suppriment dans la même transaction ses `daily_summaries` et `notification_prefs` (jeton push compris) ; la synchro n'est ouverte que pour une appartenance active (`farm_members.removed_at IS NULL`).
**notification_prefs** : `farm_id`, `user_id`, `summary_hour` (0-23, défaut 7), `alerts_enabled bool`, `push_token NULL` (jeton opaque d'appareil, exclu des synchronisations et de l'export de ferme d'autrui). PK `(farm_id, user_id)`.
**monitoring_jobs** : `id`, `farm_id`, `parcel_id`, `kind` (`backfill|reprocess`), `state`, `requested_by`, `started_at`, `finished_at`, `duration_s` (mesure SC-002). Quota par ferme sous verrou.

## Relations

parcels 1-n alerts, parcel_status (1-1), parcel_status_items, parcel_vigor_points, vigor_maps, attention_zones ; attention_zones 1-n zone_observations ; imagery_scenes 1-n parcel_vigor_points (n-1 depuis parcelle : une scène de tuile sert plusieurs parcelles, fermes comprises) ; farms 1-1 farm_weather ; weather_cells 1-n farm_weather (copie).

## Règles de validation et transitions

- Alerte : `active -> resolved` (prévision disparue ou stade changé) ; `active -> dismissed` (staff) ; `active -> expired` (jour passé) ; `resolved -> active` si la prévision revient (même `dedup_key`, `revision`+1).
- Zone : `open -> visited` (observation enregistrée) ; `open -> dismissed` (staff) ; `open|visited -> resolved` (vigueur revenue au-dessus du seuil sur 2 scènes).
- Scène : `ingested -> ok | rejected_cloud | error` ; `rejected_cloud` n'écrit aucun point publié.
- Aucune suppression physique des alertes/zones par l'utilisateur ; purge de compte et archivage de parcelle (cascade 90 jours F2) uniquement.
- Contraintes : `clear_pct` entre 0 et 100 ; `valid = (clear_pct >= 80)` en colonne générée ; fenêtre `acquired_on` bornée (>= 2017-01-01, <= aujourd'hui) ; pas de `farm_id` modifiable.
