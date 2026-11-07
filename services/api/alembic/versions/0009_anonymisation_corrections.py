"""F6 anonymisation: erase every note / operator_name correction still carrying the deleted account's text.

Revision ID: 0009
Revises: 0008

anonymize_registry_operator (SECURITY DEFINER, unchanged contract) now also blanks before/after of:
- `note` corrections of any operation authored by the deleted account,
- the `note` correction immediately following one written by the deleted account (its `before` holds that text),
- `operator_name` corrections of any operation the account ever operated (current operator or registry history).
Regulatory content and the corrections of other people on unrelated operations are never touched.
"""
from alembic import op

revision = "0009"
down_revision = "0008"

_GONE = "opérateur supprimé"

_OLD_ANON = f"""
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

_NEW_ANON = f"""
CREATE OR REPLACE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer; as_operator uuid[]; as_author uuid[];
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            as_author := ARRAY(SELECT id FROM operations WHERE author_id = p_user);
            -- operator now OR in the registry history (an operator_name correction may carry the old name)
            as_operator := ARRAY(SELECT id FROM operations WHERE operator_user_id = p_user
                                 UNION SELECT operation_id FROM registry_entries WHERE operator_user_id = p_user);
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
                OR (c.field = 'operator_name' AND c.operation_id = ANY(as_operator))
                OR (c.field = 'note' AND c.operation_id = ANY(as_author))
                -- the note correction that follows one written by the deleted account carries its text in `before`
                OR (c.field = 'note' AND EXISTS (
                      SELECT 1 FROM operation_corrections p
                       WHERE p.farm_id = c.farm_id AND p.operation_id = c.operation_id AND p.field = 'note'
                         AND p.author_id = p_user AND (p.corrected_at, p.id) < (c.corrected_at, c.id)
                         AND NOT EXISTS (SELECT 1 FROM operation_corrections m
                                          WHERE m.farm_id = c.farm_id AND m.operation_id = c.operation_id AND m.field = 'note'
                                            AND (m.corrected_at, m.id) > (p.corrected_at, p.id)
                                            AND (m.corrected_at, m.id) < (c.corrected_at, c.id))));
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""


def upgrade() -> None:
    op.execute(_NEW_ANON)
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid) FROM PUBLIC")


def downgrade() -> None:
    op.execute(_OLD_ANON)
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid) FROM PUBLIC")
