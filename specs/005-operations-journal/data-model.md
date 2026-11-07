# Modèle de données : F6

Migration `0006_operations_journal`. Types PostgreSQL ; UUID v7 générés côté client (idempotence). Toutes les tables de ferme portent `farm_id NOT NULL` et des clés étrangères **composites** `(farm_id, id)`.

## Référentiel (global, sans `farm_id`)

**phyto_products** : `id`, `name`, `name_normalized` (recherche), `registration_no`, `holder`, `active_ingredients jsonb` (liste `{name, concentration}`), `homologation_expires_on date NULL`, `expired_at timestamptz NULL`, `catalog_version_id`.
**phyto_product_uses** : `id`, `product_id`, `crop_slug` (réf. `crops.slug` F2), `target` (ravageur/maladie, texte), `max_dose numeric`, `dose_unit`, `dar_days int NULL`, `max_applications int NULL`, `interval_days int NULL`. Index `(product_id, crop_slug)`.
**catalog_versions** : `id`, `imported_at`, `source_date` (date affichée hors ligne), `row_count`, `checksum`.
Écriture réservée à l'import (rôle migrateur/worker) ; lecture par tout utilisateur authentifié.

## Opérations (par ferme)

**operations** : `id`, `farm_id`, `type` (`phyto|fertilization|irrigation|tillage|sowing_planting|pruning|weeding|harvest|other`), `performed_on date`, `status` (`planned|done|pending_validation|validated|cancelled`), `author_id`, `operator_user_id NULL`, `operator_name NULL` (≤ 80), `note` (≤ 500), `season_id NULL`, `quantity_total numeric NULL`, `quantity_unit NULL`, `label_photo_key NULL` (MinIO ; **serveur seulement** : posée à partir d'un `label_upload` vérifié, jamais lue d'un corps client, exposée uniquement par URL signée courte scopée ferme ; motif `farms/{farm_id}/labels/{uuid}`, `CHECK` sur le motif), `product_id NULL`, `free_product_name NULL` (≤ 80), `dose numeric NULL`, `dose_unit NULL`, `validated_by NULL`, `validated_at NULL`, `done_at NULL`, `created_at`, `updated_at`, `server_version`, `field_versions jsonb`.
Contraintes : `CHECK (product_id IS NULL OR free_product_name IS NULL)` ; `performed_on` borné ; aucune suppression physique (pas de DELETE en GRANT pour `phyto`).

**operation_parcels** (modèle de lecture dénormalisé, synchronisé) : `id`, `farm_id`, `operation_id`, `parcel_id`, `author_id`, `type`, `performed_on`, `status`, `product_id`, `free_product_name`, `allocated_quantity`, `allocated_dose`, `dose_unit`, `area_ha_snapshot`, `crop_slug`, `warnings jsonb`, `parcel_archived_at` (recopié par le serveur, triggers à l'archivage/restauration), `updated_at`. Unique `(operation_id, parcel_id)`. FK composite `(farm_id, parcel_id)`.

**operation_reminders** : `id`, `farm_id`, `operation_id`, `parcel_id NULL`, `fire_on date`, `state` (`scheduled|fired|done|dismissed`), `created_at`. Seuls les rappels des opérations `planned` existent ; ≤ 500 `scheduled` par ferme.

## Registre (append-only)

**registry_entries** : `id`, `farm_id`, `operation_id`, `parcel_id` (sans FK bloquante), `entry_kind` (`application|reversal`), `supersedes_id NULL` (FK sur `registry_entries.id`), `performed_on`, snapshot : `parcel_name`, `crop_name`, `area_ha`, `product_id NULL`, `product_name`, `active_ingredients jsonb`, `is_free_product bool`, `dose`, `dose_unit`, `allocated_quantity`, `dar_days NULL`, `max_dose NULL`, `catalog_version_id NULL`, `operator_name`, `operator_user_id NULL` (annulé à l'anonymisation par **insertion d'une écriture d'anonymisation** autorisée uniquement par la procédure `anonymize_registry_operator`, seule exception documentée et testée aux triggers), `warnings jsonb`, `season_id NULL`, `recorded_by`, `recorded_at`, `retain_until date` (= `performed_on` + 5 ans).
Triggers : `BEFORE UPDATE OR DELETE` -> `RAISE EXCEPTION 'registry_append_only'` (le contournement n'existe que par la fonction `SECURITY DEFINER` d'anonymisation et de purge après `retain_until`, exécutée par le worker). Index `(farm_id, performed_on)`, `(farm_id, parcel_id, performed_on)`.
**Vue** `registry_current` : `application` sans `reversal` référençant.

**operation_corrections** (append-only, mêmes triggers) : `id`, `farm_id`, `operation_id`, `field`, `before jsonb`, `after jsonb`, `author_id`, `corrected_at`, `source` (`manual|sync_conflict`), `registry_entry_id NULL`.

## Exports

**label_uploads** : `id` (identifiant opaque renvoyé au client = `label_photo_id`), `farm_id`, `user_id`, `object_key` (générée par le serveur, motif `farms/{farm_id}/labels/{uuid}`, `CHECK`), `consumed_at NULL`, `created_at`. Usage unique ; non rattachée sous 24 h -> purge de l'objet et de la ligne. Résolution d'un `label_photo_id` : `(id, farm_id, user_id)` doivent correspondre, sinon 422 `invalid_object_ref`.

**export_jobs** : `id`, `farm_id`, `requested_by`, `scope` (`farm|parcel`), `parcel_id NULL`, `period_from`, `period_to`, `format` (`pdf|xlsx|both`), `lang`, `state` (`queued|running|done|failed`), `file_keys jsonb` (**serveur seulement**, motif `farms/{farm_id}/exports/{job_id}/...`, jamais fournie ni renvoyée au client ; seule l'URL signée 15 min est exposée, après contrôle ferme), `sha256 NULL`, `row_count`, `expires_at`, `created_at`. Un seul job `queued|running` par ferme (index unique partiel).

## Transitions d'état d'une opération

```text
create (date future)        -> planned
create (date <= aujourd'hui)-> done (owner/manager => validated ; worker => pending_validation)
planned --mark_done--> done -> validated | pending_validation
pending_validation --validate (owner/manager)--> validated
planned --cancel--> cancelled        done|validated --correct--> reversal + application (statut conservé)
done|validated --cancel (owner/manager)--> reversal seul, status=cancelled
```
« En retard » = `planned` et `performed_on < aujourd'hui` (dérivé).

## Règles de validation

- Obligatoires : `type`, ≥ 1 parcelle, `performed_on`. Phyto : `product` et `dose` demandés, jamais exigés.
- ≤ 50 parcelles ; parcelles de la même ferme et visibles du rôle ; quantités > 0.
- Avertissements recalculés serveur ; ceux du client ne sont pas crus.
- Contrôle par parcelle (cultures différentes) ; produit libre -> `free_product_unchecked`.

## Données dénormalisées pour la synchro (voir G2)

`operation_parcels.{farm_id, author_id, parcel_archived_at}` ; un trigger serveur recopie `parcels.archived_at` dans `operation_parcels.parcel_archived_at` lors de l'archivage, la restauration, la fusion.
