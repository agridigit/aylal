"""F6 registry hardening: wider anonymisation, chain-aware purge.

Revision ID: 0007
Revises: 0006

- anonymize_registry_operator also covers registry_entries.recorded_by, operations (author/operator) and the
  identifier-bearing corrections (note, operator_name); regulatory content (product, dose, dates) is untouched;
- corrections_guard opens ONE narrow exemption under aylal.registry_maintenance: blanking before/after of a
  note/operator_name correction (every other column must stay identical); no free UPDATE, no DELETE;
- purge_expired_registry works per chain (an application and its reversals go together, or not at all) and honours
  the recording-date floor for legacy rows computed as performed_on + years.
"""
from alembic import op

revision = "0007"
down_revision = "0006"

_OLD_GUARD = """
CREATE OR REPLACE FUNCTION corrections_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'registry_append_only';
END $$"""

_OLD_ANON = """
CREATE OR REPLACE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
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

_OLD_PURGE = """
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


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION corrections_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF current_setting('aylal.registry_maintenance', true) = 'on' AND TG_OP = 'UPDATE'
               AND NEW.field IN ('note', 'operator_name') AND NEW.before IS NULL AND NEW.after IS NULL
               AND (to_jsonb(NEW) - 'before' - 'after') = (to_jsonb(OLD) - 'before' - 'after') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'registry_append_only';
        END $$"""
    )
    op.execute(
        """
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
    )
    op.execute("DROP FUNCTION purge_expired_registry(date)")
    op.execute(
        """
        CREATE FUNCTION purge_expired_registry(p_today date, p_years integer DEFAULT 5) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer;
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            -- a chain = an application and the reversals that point at it; it goes only when ALL its members expired.
            -- A legacy row (retain_until <= performed_on + years) also keeps the recording-date floor.
            DELETE FROM registry_entries WHERE COALESCE(supersedes_id, id) IN (
                SELECT COALESCE(supersedes_id, id) FROM registry_entries
                 GROUP BY COALESCE(supersedes_id, id)
                HAVING max(CASE WHEN retain_until <= performed_on + make_interval(years => p_years)
                                THEN GREATEST(retain_until, (recorded_at AT TIME ZONE 'UTC')::date + make_interval(years => p_years))::date
                                ELSE retain_until END) < p_today);
            GET DIAGNOSTICS n = ROW_COUNT;
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""
    )
    op.execute("REVOKE EXECUTE ON FUNCTION purge_expired_registry(date, integer) FROM PUBLIC")


def downgrade() -> None:
    op.execute(_OLD_GUARD)
    op.execute(_OLD_ANON)
    op.execute("DROP FUNCTION purge_expired_registry(date, integer)")
    op.execute(_OLD_PURGE)
    op.execute("REVOKE EXECUTE ON FUNCTION purge_expired_registry(date) FROM PUBLIC")
