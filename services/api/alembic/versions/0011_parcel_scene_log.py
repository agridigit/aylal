"""F3 scene log: one line per (parcel, scene) so a rejected cloudy scene keeps its trace (not synchronised).

Revision ID: 0011
Revises: 0010
"""
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE parcel_scene_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            scene_id uuid NOT NULL REFERENCES imagery_scenes(id) ON DELETE CASCADE,
            outcome text NOT NULL CHECK (outcome IN ('rejected_cloud', 'ok', 'error')),
            logged_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (parcel_id, scene_id),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS parcel_scene_log CASCADE")
