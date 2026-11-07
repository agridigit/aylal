"""Initial schema: farms, members, parcels, trial records, idempotency and conflict journal.

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None

TABLES = "farms, farm_members, parcels, trial_records, sync_conflicts"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        CREATE TABLE farms (
            id uuid PRIMARY KEY,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute(
        """
        CREATE TABLE farm_members (
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
            PRIMARY KEY (farm_id, user_id)
        )"""
    )
    op.execute(
        """
        CREATE TABLE parcels (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
            geometry geometry(Polygon, 4326) NOT NULL,
            vigor real NOT NULL CHECK (vigor BETWEEN 0 AND 1)
        )"""
    )
    op.execute("CREATE INDEX parcels_geometry_gist ON parcels USING GIST (geometry)")
    op.execute(
        """
        CREATE TABLE trial_records (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            author_id uuid NOT NULL,
            title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
            note text CHECK (char_length(note) <= 2000),
            quantity numeric CHECK (quantity >= 0 AND quantity <= 1000000),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            server_version bigint NOT NULL DEFAULT 1,
            field_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
            deleted_at timestamptz,
            has_conflict boolean NOT NULL DEFAULT false
        )"""
    )
    op.execute("CREATE INDEX trial_records_farm ON trial_records (farm_id)")
    op.execute(
        """
        CREATE TABLE applied_ops (
            op_id uuid PRIMARY KEY,
            record_id uuid NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now(),
            result jsonb NOT NULL
        )"""
    )
    op.execute(
        """
        CREATE TABLE sync_conflicts (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            record_id uuid NOT NULL,
            field text NOT NULL,
            discarded_value jsonb,
            kept_value jsonb,
            discarded_by uuid NOT NULL,
            base_version bigint NOT NULL,
            server_version bigint NOT NULL,
            detected_at timestamptz NOT NULL DEFAULT now(),
            acknowledged_at timestamptz
        )"""
    )
    op.execute("CREATE INDEX sync_conflicts_record ON sync_conflicts (record_id)")
    op.execute(f"CREATE PUBLICATION powersync FOR TABLE {TABLES}")


def downgrade() -> None:
    op.execute("DROP PUBLICATION IF EXISTS powersync")
    for table in (
        "sync_conflicts", "applied_ops", "trial_records", "parcels", "farm_members", "farms"
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
