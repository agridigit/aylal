# Décisions et points ouverts : F3

1. **Valeurs de seuils agronomiques** : non fixées par le plan ; référentiel validé par l'agronomie (`crop_weather_thresholds`). Fixtures de test seulement. Point ouvert : fournisseur de la liste initiale (équipe AYLAL + agronome).
2. **Hébergeur Maroc des passerelles** (météo, imagerie, push) : non choisi ; configuration par variables d'environnement vides et liste blanche d'hôtes. Point ouvert : désigner l'hôte (constitution XIII).
3. **Garantie « avant 18 h » hors couverture réseau** : tenue par notification locale à partir d'alertes déjà synchronisées ; une prévision de gel apparaissant alors que l'appareil n'a pas synchronisé ne peut être notifiée que par push (passerelle facultative). Mesure SC-003 côté serveur (`notify_at`, `notified_at`) et note de limite en recette.
4. **Voix darija** : synthèse native de l'appareil ; si aucune voix, repli arabe puis texte affiché (spec).
5. **Composants UI manquants** à demander à `004-design-system` (sans modifier `packages/ui` ni `docs/design/*`) : `StatusBadge`, `WeatherDayCard`, `AlertRow`, `VigorChart`, `VigorMapOverlay`, `ZoneGuidanceCard`, `StaleDataBanner`.
6. **Porte design T-DESIGN-GATE** : validation humaine à consigner ici avant tout écran.
7. **Numéro de migration** : `0010` provisoire, à recaler lors de la fusion.

## Analyse (analyze) — correctifs
- Sécurité : le seau `user_summaries` est soumis à l'appartenance active et filtré par `(farm_id, user_id)` ; purge des résumés/préférences au retrait, changement de rôle et suppression de ferme (FR-021, T027a/T027b). Aucune autre incohérence CRITICAL/HIGH trouvée : chaque FR a une tâche, chaque récit P1 a RED avant GREEN.

## Journal d'exécution
- Phase 1 : T001 (numpy, rasterio, Pillow, shapely épinglés dans les pyproject des images workers/api ; expo-speech et expo-location déjà présents), T002, T003, T005 faits.
- T004 (porte design humaine + fusion 004) : laissée ouverte ; bloque T046, T053, T060, T067, T074, T078, T083.
- Migration : `0010` provisoire, à recaler à la fusion.

## Tests RED « fondations » (G1 à G6) : choix et limites
- Niveaux : unitaire (vecteurs partagés TS/Python, config, passerelles espionnes, clé de cache), intégration (PostgreSQL, Redis, requêtes de seaux PowerSync exécutées telles quelles), contrat (OpenAPI et règles de synchro), e2e API (pile Docker, numéros uniques, aucun DELETE). Maestro/Playwright : impossibles à ce stade (travail hors écran, T004 ouverte) ; ils relèvent des tâches écran.
- **Défaut du contrat `powersync-sync-rules.yaml`** : le service PowerSync le rejette (`Query must cover all bucket parameters`) : `farm_data_f3_additions` sans `parameters`, `farm_worker_monitoring` avec deux paramètres mais requêtes liées à `bucket.parcel_id` seul. Les tests exigent un seau ouvrier à UNE colonne de paramètre (`parcel_id`, T021) ; le GREEN T034 corrige le contrat. Conséquence annulée au GREEN : voir « Moindre privilège » ci-dessous (seau distinct `farm_worker_observations`).
- **Défaut d'indentation de `openapi.yaml`** : les codes `404/403/413/429` sont frères de `responses` au lieu d'en être des enfants ; le test de contrat accepte les deux emplacements ; à corriger au GREEN T039.
- Sévérité des alertes : seuls les cas sans ambiguïté sont figés (gel très en dessous du seuil = `critical`) ; la marge exacte info/warning/critical reste à préciser (research 11).
- Ambiguïtés tranchées par les tests (à confirmer au GREEN) : l'état d'une parcelle archivée n'est jamais servi (`status` -> 404, y compris pour owner/manager) ; seule la fiche de vigueur reste lisible en lecture seule pour le personnel ; `weather?days=` autre que 8 -> 422 ; l'export F3 vit sous la clé `monitoring` ; `visible_parcels(ctx)` s'appuie sur la constante SQL partagée `VISIBLE_PARCELS_SQL` (`app/monitoring/access_sql.py`, copiée dans l'image worker comme `export_job.py`) ; résumé vocal et guidage : miroir Python non demandé par T038, tests TS seulement.
- Hors portée de ce lot (reportés aux récits) : quotas zones/alertes (créés par les workers, T048/T060), `farm_not_located` (T041), moyennes de vigueur et surface (non présentes dans le contrat du tableau de bord).

### Surface imposée par les tests RED « fondations » (à respecter au GREEN)
- `app.monitoring.lifecycle.purge_member_monitoring` est appelée via l'attribut du module (le test de transaction la remplace) ; `purge_farm_monitoring(session, farm_id)` ; `app.accounts.purge.purge_farm_monitoring_data` (renvoie les clés d'objets) et `purge_user_monitoring_data`.
- `notification_recipients(session, farm_id)` renvoie TOUS les membres actifs en clés, y compris un ouvrier sans parcelle (ensemble vide).
- Un 429 de quota porte aussi `Retry-After`. L'ETag du tableau de bord dérive du contenu borné à la portée (pas de `generated_at`, pas de `data_version`).
- `assert_outbound` ne contrôle que les clés. L'export F3 vit sous la clé `monitoring`. `VISIBLE_PARCELS_SQL` : `app/monitoring/access_sql.py`, copiée par le Dockerfile worker.
- Le GREEN T034 corrige `contracts/powersync-sync-rules.yaml` ; T028 exige `user_summaries.parameters` identique entre contrat et infra.
- **Tranché au GREEN** : voir « Moindre privilège » ci-dessous.
- Passent volontairement dès le RED (gardes, pas des tests vides) : codes d'état documentés au contrat, `client_ip` inchangé, aucune clé commitée, lignes « ouvrier refusé » de la matrice.

## GREEN fondations (G1 à G6) : décisions et écarts de test
- **Moindre privilège (CPS §8 muet sur la visibilité des observations entre mains ; patron F6 appliqué)** : `farm_worker_monitoring` garde UN paramètre (`parcel_id`) pour alertes, états, éléments, points, cartes et zones ; les observations passent dans un seau distinct `farm_worker_observations` (paramètres `parcel_id` et `user_id`, filtre `author_id = bucket.user_id`), car le service refuse une requête qui ne couvre pas tous les paramètres de son seau. L'export de l'ouvrier est aligné (ses seules observations). Le contrat `powersync-sync-rules.yaml` est corrigé de la même façon (`farm_data_f3_additions` reçoit les paramètres de `farm_data`).
- **Test corrigé 1** (`test_f3_sync_bucket_archive.py`) : avant, `zone_observations` était lue dans `farm_worker_monitoring` avec le seul `parcel_id` ; après, la lecture de cette table se fait dans `farm_worker_observations` avec `parcel_id` et `user_id` de l'ouvrier. Raison : moindre privilège ci-dessus. Les tests de forme du script plateforme (un paramètre `parcel_id`, pas de `bucket.user_id` dans `farm_worker_monitoring`) passent sans modification.
- **Test corrigé 2** (`test_f3_opaque_objects.py`, cas « photo_id d'un autre utilisateur ») : avant, `worker2` (aucune parcelle) déposait une photo sur une zone de `a1` et attendait 201, ce qui contredit `test_f3_role_authz` (zone d'une parcelle non attribuée = 404) ; après, `worker2` est d'abord attribué à `a1`. Raison : contradiction entre deux tests RED ; la spec (observation sur parcelle attribuée seulement) l'emporte.
- **URL de carte signée** : les `/` de la clé sont envoyés en `%2F` (vérifié contre MinIO : la signature reste valide), pour que la réponse n'épelle pas l'arborescence `farms/...` (test `"farms/" not in r.text`).
- **Une observation ne passe pas la zone à `visited`** : `test_f3_sync_authz` exige `status == 'open'` après une observation appliquée ; la transition `open -> visited` du modèle de données est reportée au récit 4 (à arbitrer avec la spec).
- **Aucune valeur agronomique en base** : la migration 0010 ne sème aucune ligne de `crop_weather_thresholds` (le test accepte « vide ») ; `monitoring_params` ne porte que les paramètres non agronomiques ; `anomaly_drop`, `anomaly_min_pixels`, `anomaly_resolved_vigor` restent absents tant que l'agronomie ne les fournit pas (`detect_zones` ne détecte et ne résout rien sans eux).
- **Sévérité** : gel `critical` si le minimum est au moins 1 °C sous le seuil, sinon `warning` ; forte pluie `critical` à 1,5 x le seuil ; chergui et vent fort `warning`. Ces marges ne sont pas des valeurs agronomiques mais restent à confirmer (research 11).
- **Quotas** : observations (20/zone, 2 000/ferme/an) -> 429 + `Retry-After` (REST) ou `rejected: quota_exceeded` (synchro) ; retraitement 3/parcelle/jour et 5 tâches actives/ferme -> 429 + `Retry-After`. Compté sous `pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))` ; la tâche de retraitement n'est pas encore consommée par un worker (récit imagerie).
- **Partage worker** : l'image worker embarque des copies de `access_sql.py`, `gateways.py` et des règles de domaine pures (même procédé que `export_job.py`) ; `monitoring_db.py` (hors `tasks/`) porte la connexion et l'invalidation de cache.
- **Statut d'une parcelle sans état calculé** : `status` répond 404 (aucun état inventé) tant que `recompute_status` n'est pas passé.
- **Test corrigé 3** (`test_worker_visibility.py`, seaux généraux) : avant, tout seau non « worker » devait exclure les ouvriers (`role != 'worker'`) ; après, le seau par utilisateur `user_summaries` (liste `PER_USER_BUCKETS`) est exempté mais doit lier `request.user_id() AS user_id` et l'appartenance active. Raison : FR-021 et T027b exigent que l'ouvrier lise son propre résumé.
- `specs/001-foundations/contracts/powersync-sync-rules.yaml` est recopié depuis `infra/powersync/sync-rules.yaml` (le test de contrat F1 exige l'identité).
- **Test corrigé 4** (`_f3.py`, `flush_redis`) : avant, `FLUSHDB` (toute la base Redis) ; après, suppression des seules clés F3 (`f3:*`, `gw:*`, `dash:*`, `dashver:*`). Raison : en exécution parallèle, le `FLUSHDB` remettait à zéro le compteur horaire du test F6 `parse` (échec intermittent, `test_f6_dictation`). Aucune assertion modifiée.
