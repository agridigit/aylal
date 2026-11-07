# Modèle de données F2

Migration Alembic `0004_fields_crops` (réversible). UUID générés côté client pour les entités créées hors ligne. Toutes les tables portent `farm_id` ; les références entre tables passent par des **clés étrangères composites** incluant `farm_id` (aucune référence inter-ferme possible). Colonnes de synchro (comme F0) : `server_version`, `field_versions jsonb`, `updated_at`.

## `parcels` (Field, étend F0)
| Colonne | Type / règle |
| --- | --- |
| id, farm_id, name | existant ; `name` 1-80 car. ; `UNIQUE (farm_id, id)` déjà posé par F1 |
| geometry | `geometry(Polygon,4326)`, `ST_IsValid` et `ST_IsSimple`, 3 à 500 sommets, centroïde dans l'emprise Maroc ; GiST |
| area_calc_ha | `numeric(10,4)` ; **écrit par le serveur** (`ST_Area(geography)/10000`) |
| area_declared_ha | `numeric(10,4)` NULL, > 0 ; saisie de l'agriculteur |
| irrigation | `rainfed`,`gravity`,`sprinkler`,`drip`,`pivot` ou NULL (non renseigné) |
| greenhouse | boolean, défaut false |
| soil | texte NULL (référentiel sols CPS §17 ; défaut prudent appliqué par le domaine, pas stocké) |
| source | `draw_taps`,`draw_gps`,`import` |
| gps_accuracy_m | real NULL |
| status_summary | `ok`,`watch`,`act` ou NULL ; **écrit par le serveur (F3)**, NULL = couleur neutre |
| created_by | UUID, imposé = utilisateur courant |
| archived_at, purge_after | timestamptz NULL ; `purge_after = archived_at + 90 j` ; index partiel sur `purge_after` |
| merged_into_id | UUID NULL, FK composite `(farm_id, merged_into_id)` -> `parcels` |
| vigor | (F0) rendue nullable, retirée au REFACTOR |
Calculé, non stocké : `imagery_suitable = area_calc_ha >= 0.3 AND NOT greenhouse` (F3), avertissement de chevauchement.

## `crops` (référentiel + cultures libres)
`id`, `farm_id` NULL (référentiel partagé) ou ferme propriétaire, `slug` (unique si farm_id NULL), `name_ary`, `name_ar`, `name_fr`, `cycle` (`perennial`,`annual`), `photo_key` NULL, `varieties jsonb`, `stages jsonb` (liste ordonnée `{key, gdd_from, label_key}`), `has_agronomy` bool, `validated` bool, `created_by`, `archived_at`. Règles : lignes `farm_id IS NULL` en lecture seule (écriture client rejetée, 403) ; culture libre : `has_agronomy=false`, `stages` et Kc absents ; `UNIQUE (farm_id, id)` pour la FK composite (cultures libres) ; une campagne ne référence que le référentiel ou une culture libre de **sa** ferme (contrôle API + test inter-ferme). Seed : olivier, agrumes, blé dur, blé tendre, orge, tomate, pomme de terre, oignon, fruits rouges, avocatier, palmier dattier, amandier, vigne, betterave, luzerne, maïs fourrager.

## `seasons` (campagne)
| Colonne | Règle |
| --- | --- |
| id, farm_id, field_id | FK composite `(farm_id, field_id)` -> `parcels` |
| crop_id | référentiel ou culture libre de la ferme |
| variety | texte ≤ 80 NULL |
| planting_year | smallint NULL (pérenne), 1900 ≤ valeur ≤ année courante + 1 |
| sowing_date | date NULL (annuelle) ; CHECK `NOT (planting_year IS NOT NULL AND sowing_date IS NOT NULL)` ; cohérence avec `crops.cycle` vérifiée par le domaine/API |
| started_at | date obligatoire |
| ended_at | date NULL (NULL = active) ; ≥ `started_at` |
| stage_estimated | texte NULL (recalculé, écrasable) |
| stage_corrected, stage_corrected_at | corrigé par l'agriculteur, **jamais écrasé** par la réestimation |
| destination | texte NULL (facultatif) |
Index unique partiel `(field_id, crop_id) WHERE ended_at IS NULL`. Historique : une campagne n'est jamais supprimée, seulement clôturée ; elle disparaît avec la purge de sa parcelle.

## `field_blocks` (bloc ou secteur)
`id`, `farm_id`, `field_id` (FK composite), `name`, `kind` (`block`,`irrigation_sector`), `geometry geometry(Polygon,4326)`, `area_calc_ha` (serveur), `archived_at`. Règles : contenu dans la parcelle (tolérance 1 % de l'aire du bloc), pas de chevauchement entre blocs (tolérance 1 %), mêmes bornes de géométrie que `parcels`.

## `field_commands` (commandes hors ligne, insertion seule)
`id`, `farm_id`, `kind` (`merge`), `payload jsonb` (`survivor_id`, `merged_ids[]`), `created_by`, `applied_at`, `result jsonb` (`ok`, ou `error.code`). Idempotence par `applied_ops(op_id)`. Table locale de file d'envoi côté client ; lecture seule pour le client une fois appliquée.

## Rôles et visibilité
| Action | owner | manager | worker |
| --- | --- | --- | --- |
| Lire parcelles / campagnes / blocs | toutes | toutes | seulement attribuées (sinon 404) |
| Créer, modifier, découper, fusionner, archiver, restaurer, importer | oui | oui | 403 |
| Démarrer/clôturer campagne, corriger le stade | oui | oui | 403 |
| Créer une culture libre | oui | oui | 403 |
| Lire archivées | oui | oui | 404 |
| Lire campagnes/blocs d'une parcelle archivée | via archivées/restauration | via archivées/restauration | 404 (aucune synchro ni lecture dès l'archivage de la parcelle parente) |
Les ouvriers n'écrivent aucune de ces tables par REST ni par synchro (F2 ne leur ouvre aucune écriture ; le journal d'opérations F6 viendra).

## États
`parcels` : active -> archivée (<= 90 j, restaurable) -> purgée. Parcelle fusionnée : archivée avec `merged_into_id`. `seasons` : active (`ended_at` NULL) -> clôturée. `field_commands` : en attente -> appliquée | refusée.

## Export et suppression (loi 09-08)
`build_export` ajoute `fields[]`, `seasons[]`, `blocks[]`, `custom_crops[]` pour les fermes où l'utilisateur est membre selon son rôle (ouvrier : ses parcelles seulement). Purge de compte/ferme (F1) étendue en cascade : `field_commands`, `seasons`, `field_blocks`, `crops` libres, `parcels`.
