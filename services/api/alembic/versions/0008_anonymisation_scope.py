"""F6 anonymisation scope, sync conflict versions and the stable read point for done operations.

Revision ID: 0008
Revises: 0007

- author_id / recorded_by become NULLable: deleting an account blanks ONLY the columns that point at it;
- registry_guard / corrections_guard open the maintenance exemption to exactly those columns
  (operator_name, operator_user_id, recorded_by ; author_id -> NULL and blanking of note/operator_name texts);
- anonymize_registry_operator (SECURITY DEFINER, EXECUTE revoked from PUBLIC) erases the operator only where the
  deleted account IS the operator, the author/recorder only where it IS the author/recorder, and a note only when
  the deleted account wrote it; regulatory content (product, dose, dates, parcel) is never touched;
- operation_corrections.server_version lets a stale sync patch be flagged `sync_conflict` field by field;
- view operations_done: stable read point for F4/F8 (done, pending_validation, validated lines only).
"""
from alembic import op

revision = "0008"
down_revision = "0007"

_GONE = "opérateur supprimé"

_OLD_REGISTRY_GUARD = """
CREATE OR REPLACE FUNCTION registry_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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

_OLD_CORRECTIONS_GUARD = """
CREATE OR REPLACE FUNCTION corrections_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('aylal.registry_maintenance', true) = 'on' AND TG_OP = 'UPDATE'
       AND NEW.field IN ('note', 'operator_name') AND NEW.before IS NULL AND NEW.after IS NULL
       AND (to_jsonb(NEW) - 'before' - 'after') = (to_jsonb(OLD) - 'before' - 'after') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'registry_append_only';
END $$"""

_OLD_ANON = """
CREATE OR REPLACE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
    PERFORM set_config('aylal.registry_maintenance', 'on', true);
    UPDATE registry_entries SET operator_user_id = NULL, operator_name = 'opérateur supprimé'
     WHERE operator_user_id = p_user OR recorded_by = p_user;
    GET DIAGNOSTICS n = ROW_COUNT;
    UPDATE operation_corrections c SET before = NULL, after = NULL
     WHERE c.field IN ('note', 'operator_name')
       AND (c.author_id = p_user OR EXISTS (SELECT 1 FROM operations o WHERE o.farm_id = c.farm_id AND o.id = c.operation_id
                                            AND (o.author_id = p_user OR o.operator_user_id = p_user)));
    UPDATE operations SET operator_user_id = NULL, operator_name = 'opérateur supprimé', note = NULL,
           updated_at = now(), server_version = server_version + 1
     WHERE author_id = p_user OR operator_user_id = p_user;
    PERFORM set_config('aylal.registry_maintenance', 'off', true);
    RETURN n;
END $$"""


def upgrade() -> None:
    op.execute("ALTER TABLE operations ALTER COLUMN author_id DROP NOT NULL")
    op.execute("ALTER TABLE operation_parcels ALTER COLUMN author_id DROP NOT NULL")
    op.execute("ALTER TABLE registry_entries ALTER COLUMN recorded_by DROP NOT NULL")
    op.execute("ALTER TABLE operation_corrections ALTER COLUMN author_id DROP NOT NULL")
    op.execute("ALTER TABLE operation_corrections ADD COLUMN server_version bigint")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION registry_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('aylal.registry_maintenance', true) = 'on' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                -- only the identity columns may change, and only towards "erased"
                IF (to_jsonb(NEW) - 'operator_name' - 'operator_user_id' - 'recorded_by')
                   = (to_jsonb(OLD) - 'operator_name' - 'operator_user_id' - 'recorded_by')
                   AND (NEW.recorded_by IS NULL OR NEW.recorded_by IS NOT DISTINCT FROM OLD.recorded_by)
                   AND (NEW.operator_user_id IS NULL OR NEW.operator_user_id IS NOT DISTINCT FROM OLD.operator_user_id) THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'registry_append_only';
        END $$"""
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION corrections_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('aylal.registry_maintenance', true) = 'on' AND TG_OP = 'UPDATE'
               AND (to_jsonb(NEW) - 'before' - 'after' - 'author_id') = (to_jsonb(OLD) - 'before' - 'after' - 'author_id')
               AND (NEW.author_id IS NULL OR NEW.author_id IS NOT DISTINCT FROM OLD.author_id)
               AND ((NEW.before IS NOT DISTINCT FROM OLD.before AND NEW.after IS NOT DISTINCT FROM OLD.after)
                    OR (NEW.field IN ('note', 'operator_name') AND NEW.before IS NULL AND NEW.after IS NULL)) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'registry_append_only';
        END $$"""
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer; as_operator uuid[];
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            as_operator := ARRAY(SELECT id FROM operations WHERE operator_user_id = p_user);
            -- operator role: identity erased only where the deleted account IS the operator; recorder role: id only
            UPDATE registry_entries SET
                   operator_name = CASE WHEN operator_user_id = p_user THEN '{_GONE}' ELSE operator_name END,
                   operator_user_id = CASE WHEN operator_user_id = p_user THEN NULL ELSE operator_user_id END,
                   recorded_by = CASE WHEN recorded_by = p_user THEN NULL ELSE recorded_by END
             WHERE operator_user_id = p_user OR recorded_by = p_user;
            GET DIAGNOSTICS n = ROW_COUNT;
            -- a note is erased only when the deleted account wrote it: its last note correction, else the author
            UPDATE operations o SET
                   note = CASE WHEN COALESCE((SELECT c.author_id FROM operation_corrections c
                                               WHERE c.farm_id = o.farm_id AND c.operation_id = o.id AND c.field = 'note'
                                               ORDER BY c.corrected_at DESC, c.id DESC LIMIT 1), o.author_id) = p_user
                               THEN NULL ELSE o.note END,
                   operator_name = CASE WHEN o.operator_user_id = p_user THEN '{_GONE}' ELSE o.operator_name END,
                   operator_user_id = CASE WHEN o.operator_user_id = p_user THEN NULL ELSE o.operator_user_id END,
                   author_id = CASE WHEN o.author_id = p_user THEN NULL ELSE o.author_id END,
                   updated_at = now(), server_version = o.server_version + 1
             WHERE o.author_id = p_user OR o.operator_user_id = p_user
                OR EXISTS (SELECT 1 FROM operation_corrections c WHERE c.farm_id = o.farm_id AND c.operation_id = o.id
                              AND c.field = 'note' AND c.author_id = p_user);
            UPDATE operation_parcels SET author_id = NULL, updated_at = now() WHERE author_id = p_user;
            UPDATE operation_corrections c SET
                   before = CASE WHEN c.field IN ('note', 'operator_name') THEN NULL ELSE c.before END,
                   after = CASE WHEN c.field IN ('note', 'operator_name') THEN NULL ELSE c.after END,
                   author_id = CASE WHEN c.author_id = p_user THEN NULL ELSE c.author_id END
             WHERE c.author_id = p_user
                OR (c.field = 'operator_name' AND c.operation_id = ANY(as_operator));
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""
    )
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid) FROM PUBLIC")
    op.execute(
        """
        CREATE VIEW operations_done AS
        SELECT l.operation_id, l.farm_id, l.parcel_id, l.type, l.performed_on, l.status, l.allocated_quantity, l.product_id
          FROM operation_parcels l WHERE l.status IN ('done', 'pending_validation', 'validated')"""
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS operations_done")
    op.execute(_OLD_ANON)
    op.execute(_OLD_CORRECTIONS_GUARD)
    op.execute(_OLD_REGISTRY_GUARD)
    op.execute("ALTER TABLE operation_corrections DROP COLUMN server_version")
    nil = "'00000000-0000-0000-0000-000000000000'"
    op.execute("SELECT set_config('aylal.registry_maintenance', 'on', true)")
    op.execute(f"UPDATE registry_entries SET recorded_by = {nil} WHERE recorded_by IS NULL")
    op.execute(f"UPDATE operation_corrections SET author_id = {nil} WHERE author_id IS NULL")
    op.execute("SELECT set_config('aylal.registry_maintenance', 'off', true)")
    op.execute(f"UPDATE operations SET author_id = {nil} WHERE author_id IS NULL")
    op.execute(f"UPDATE operation_parcels SET author_id = {nil} WHERE author_id IS NULL")
    op.execute("ALTER TABLE operation_corrections ALTER COLUMN author_id SET NOT NULL")
    op.execute("ALTER TABLE registry_entries ALTER COLUMN recorded_by SET NOT NULL")
    op.execute("ALTER TABLE operation_parcels ALTER COLUMN author_id SET NOT NULL")
    op.execute("ALTER TABLE operations ALTER COLUMN author_id SET NOT NULL")
