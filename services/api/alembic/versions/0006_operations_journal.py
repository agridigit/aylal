"""F6 operations journal and phyto registry.

Revision ID: 0006
Revises: 0005

Notes (specs/005-operations-journal/data-model.md, decisions.md):
- every farm table has a composite (farm_id, ...) foreign key, so a cross-farm reference is refused by the database;
- the registry (registry_entries, operation_corrections) is append-only: row triggers refuse UPDATE/DELETE and
  UPDATE/DELETE are revoked. The only exception is the SECURITY DEFINER pair anonymize_registry_operator /
  purge_expired_registry, which raises the transaction-local flag aylal.registry_maintenance; even then the trigger
  only lets the operator columns change (UPDATE) or lets rows go (DELETE, filtered on retain_until by the function);
- operations.product_lines (jsonb) is an addition to data-model.md: up to 5 product lines per treatment;
- parcels.archived_at is copied into operation_parcels.parcel_archived_at by triggers (archive, restore, merge)
  so the PowerSync worker rules need no join.
"""
from alembic import op

revision = "0006"
down_revision = "0005"

KEY = "^farms/[0-9a-f-]{36}/labels/[0-9a-f-]{36}$"
TYPES = "'phyto','fertilization','irrigation','tillage','sowing_planting','pruning','weeding','harvest','other'"
STATUSES = "'planned','done','pending_validation','validated','cancelled'"


def _key_check(column: str) -> str:
    return f"CHECK ({column} IS NULL OR ({column} ~ '{KEY}' AND split_part({column}, '/', 2) = farm_id::text))"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE catalog_versions (
            id uuid PRIMARY KEY,
            imported_at timestamptz NOT NULL,
            source_date date NOT NULL,
            row_count integer NOT NULL,
            checksum text NOT NULL
        )"""
    )
    op.execute(
        """
        CREATE TABLE phyto_products (
            id uuid PRIMARY KEY,
            name text NOT NULL,
            name_normalized text NOT NULL,
            registration_no text,
            holder text,
            active_ingredients jsonb NOT NULL DEFAULT '[]'::jsonb,
            homologation_expires_on date,
            expired_at timestamptz,
            catalog_version_id uuid NOT NULL REFERENCES catalog_versions(id)
        )"""
    )
    op.execute("CREATE INDEX phyto_products_name ON phyto_products (name_normalized text_pattern_ops)")
    op.execute(
        """
        CREATE TABLE phyto_product_uses (
            id uuid PRIMARY KEY,
            product_id uuid NOT NULL REFERENCES phyto_products(id) ON DELETE CASCADE,
            crop_slug text NOT NULL,
            target text,
            max_dose numeric,
            dose_unit text,
            dar_days integer,
            max_applications integer,
            interval_days integer
        )"""
    )
    op.execute("CREATE INDEX phyto_product_uses_product_crop ON phyto_product_uses (product_id, crop_slug)")

    op.execute(
        f"""
        CREATE TABLE operations (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            type text NOT NULL CHECK (type IN ({TYPES})),
            performed_on date NOT NULL
                CHECK (performed_on >= DATE '2000-01-01' AND performed_on <= current_date + interval '2 years'),
            status text NOT NULL CHECK (status IN ({STATUSES})),
            author_id uuid NOT NULL,
            operator_user_id uuid,
            operator_name text CHECK (char_length(operator_name) <= 80),
            note text CHECK (char_length(note) <= 500),
            season_id uuid,
            quantity_total numeric CHECK (quantity_total > 0),
            quantity_unit text,
            label_photo_key text {_key_check('label_photo_key')},
            product_id uuid REFERENCES phyto_products(id),
            free_product_name text CHECK (char_length(free_product_name) <= 80),
            dose numeric CHECK (dose > 0),
            dose_unit text,
            product_lines jsonb NOT NULL DEFAULT '[]'::jsonb,
            validated_by uuid,
            validated_at timestamptz,
            done_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            server_version bigint NOT NULL DEFAULT 1,
            field_versions jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            CHECK (product_id IS NULL OR free_product_name IS NULL),
            UNIQUE (farm_id, id)
        )"""
    )
    op.execute("CREATE INDEX operations_farm_date ON operations (farm_id, performed_on DESC, id)")
    op.execute("CREATE INDEX operations_farm_planned ON operations (farm_id) WHERE status = 'planned'")

    op.execute(
        f"""
        CREATE TABLE operation_parcels (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            operation_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            author_id uuid NOT NULL,
            type text NOT NULL CHECK (type IN ({TYPES})),
            performed_on date NOT NULL,
            status text NOT NULL CHECK (status IN ({STATUSES})),
            product_id uuid,
            free_product_name text,
            allocated_quantity numeric,
            allocated_dose numeric,
            dose_unit text,
            area_ha_snapshot numeric,
            crop_slug text,
            warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
            parcel_archived_at timestamptz,
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (operation_id, parcel_id),
            FOREIGN KEY (farm_id, operation_id) REFERENCES operations (farm_id, id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX operation_parcels_parcel ON operation_parcels (parcel_id, performed_on DESC)")
    op.execute("CREATE INDEX operation_parcels_farm ON operation_parcels (farm_id, performed_on DESC)")

    op.execute(
        """
        CREATE TABLE operation_reminders (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            operation_id uuid NOT NULL,
            parcel_id uuid,
            fire_on date NOT NULL,
            state text NOT NULL CHECK (state IN ('scheduled','fired','done','dismissed')),
            created_at timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (farm_id, operation_id) REFERENCES operations (farm_id, id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX operation_reminders_farm_state ON operation_reminders (farm_id, state, fire_on)")

    op.execute(
        """
        CREATE TABLE registry_entries (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            operation_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            entry_kind text NOT NULL CHECK (entry_kind IN ('application','reversal')),
            supersedes_id uuid REFERENCES registry_entries(id),
            performed_on date NOT NULL,
            parcel_name text NOT NULL,
            crop_name text,
            area_ha numeric,
            product_id uuid,
            product_name text NOT NULL,
            active_ingredients jsonb NOT NULL DEFAULT '[]'::jsonb,
            is_free_product boolean NOT NULL DEFAULT false,
            dose numeric,
            dose_unit text,
            allocated_quantity numeric,
            dar_days integer,
            max_dose numeric,
            catalog_version_id uuid,
            operator_name text NOT NULL,
            operator_user_id uuid,
            warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
            season_id uuid,
            recorded_by uuid NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            retain_until date NOT NULL,
            FOREIGN KEY (farm_id, operation_id) REFERENCES operations (farm_id, id)
        )"""
    )
    op.execute("CREATE INDEX registry_entries_farm_date ON registry_entries (farm_id, performed_on)")
    op.execute("CREATE INDEX registry_entries_parcel_date ON registry_entries (farm_id, parcel_id, performed_on)")
    op.execute("CREATE INDEX registry_entries_operator ON registry_entries (operator_user_id) WHERE operator_user_id IS NOT NULL")
    op.execute("CREATE INDEX registry_entries_retain ON registry_entries (retain_until)")
    op.execute("CREATE INDEX registry_entries_supersedes ON registry_entries (supersedes_id) WHERE supersedes_id IS NOT NULL")
    op.execute(
        """
        CREATE VIEW registry_current AS
        SELECT a.* FROM registry_entries a
        WHERE a.entry_kind = 'application'
          AND NOT EXISTS (SELECT 1 FROM registry_entries r WHERE r.supersedes_id = a.id AND r.entry_kind = 'reversal')"""
    )

    op.execute(
        """
        CREATE TABLE operation_corrections (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            operation_id uuid NOT NULL,
            field text NOT NULL,
            before jsonb,
            after jsonb,
            author_id uuid NOT NULL,
            corrected_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            source text NOT NULL CHECK (source IN ('manual','sync_conflict')),
            registry_entry_id uuid,
            FOREIGN KEY (farm_id, operation_id) REFERENCES operations (farm_id, id)
        )"""
    )
    op.execute("CREATE INDEX operation_corrections_operation ON operation_corrections (farm_id, operation_id, corrected_at)")

    op.execute(
        f"""
        CREATE TABLE label_uploads (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            object_key text NOT NULL UNIQUE,
            consumed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (object_key ~ '{KEY}' AND split_part(object_key, '/', 2) = farm_id::text)
        )"""
    )
    op.execute("CREATE INDEX label_uploads_pending ON label_uploads (created_at) WHERE consumed_at IS NULL")

    op.execute(
        """
        CREATE TABLE export_jobs (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            requested_by uuid NOT NULL,
            scope text NOT NULL CHECK (scope IN ('farm','parcel')),
            parcel_id uuid,
            period_from date NOT NULL,
            period_to date NOT NULL,
            format text NOT NULL CHECK (format IN ('pdf','xlsx','both')),
            lang text NOT NULL,
            state text NOT NULL CHECK (state IN ('queued','running','done','failed')),
            file_keys jsonb,
            sha256 text,
            row_count integer NOT NULL DEFAULT 0,
            expires_at timestamptz NOT NULL DEFAULT now() + interval '7 days',
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (period_to >= period_from)
        )"""
    )
    op.execute("CREATE UNIQUE INDEX export_jobs_one_active ON export_jobs (farm_id) WHERE state IN ('queued','running')")
    op.execute("CREATE INDEX export_jobs_farm_created ON export_jobs (farm_id, created_at)")

    # --- append-only registry -------------------------------------------------------------------
    op.execute(
        """
        CREATE FUNCTION registry_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('aylal.registry_maintenance', true) = 'on' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                IF (to_jsonb(NEW) - 'operator_name' - 'operator_user_id') = (to_jsonb(OLD) - 'operator_name' - 'operator_user_id') THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'registry_append_only';
        END $$"""
    )
    op.execute(
        """
        CREATE FUNCTION corrections_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'registry_append_only';
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER registry_entries_append_only BEFORE UPDATE OR DELETE ON registry_entries"
        " FOR EACH ROW EXECUTE FUNCTION registry_guard()"
    )
    op.execute(
        "CREATE TRIGGER operation_corrections_append_only BEFORE UPDATE OR DELETE ON operation_corrections"
        " FOR EACH ROW EXECUTE FUNCTION corrections_guard()"
    )
    op.execute("REVOKE UPDATE, DELETE ON registry_entries, operation_corrections FROM PUBLIC")
    op.execute(
        """
        DO $$ BEGIN
            IF (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
                REVOKE UPDATE, DELETE ON registry_entries, operation_corrections FROM CURRENT_USER;
            END IF;
        END $$"""
    )
    op.execute(
        """
        CREATE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer;
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            UPDATE registry_entries SET operator_user_id = NULL, operator_name = 'opérateur supprimé'
             WHERE operator_user_id = p_user;
            GET DIAGNOSTICS n = ROW_COUNT;
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""
    )
    op.execute(
        """
        CREATE FUNCTION purge_expired_registry(p_today date) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer;
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            DELETE FROM registry_entries WHERE retain_until < p_today;
            GET DIAGNOSTICS n = ROW_COUNT;
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""
    )
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid), purge_expired_registry(date) FROM PUBLIC")

    # --- parcels.archived_at -> operation_parcels.parcel_archived_at -----------------------------
    op.execute(
        """
        CREATE FUNCTION copy_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.archived_at IS DISTINCT FROM OLD.archived_at THEN
                UPDATE operation_parcels SET parcel_archived_at = NEW.archived_at, updated_at = now()
                 WHERE farm_id = NEW.farm_id AND parcel_id = NEW.id;
            END IF;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER parcels_copy_archived_at AFTER UPDATE OF archived_at ON parcels"
        " FOR EACH ROW EXECUTE FUNCTION copy_parcel_archived_at()"
    )
    op.execute(
        """
        CREATE FUNCTION init_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT archived_at INTO NEW.parcel_archived_at FROM parcels WHERE id = NEW.parcel_id AND farm_id = NEW.farm_id;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER operation_parcels_init_archived_at BEFORE INSERT ON operation_parcels"
        " FOR EACH ROW EXECUTE FUNCTION init_parcel_archived_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS parcels_copy_archived_at ON parcels")
    op.execute("DROP VIEW IF EXISTS registry_current")
    for table in (
        "export_jobs", "label_uploads", "operation_corrections", "registry_entries", "operation_reminders",
        "operation_parcels", "operations", "phyto_product_uses", "phyto_products", "catalog_versions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for fn in (
        "registry_guard()", "corrections_guard()", "anonymize_registry_operator(uuid)",
        "purge_expired_registry(date)", "copy_parcel_archived_at()", "init_parcel_archived_at()",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}")
