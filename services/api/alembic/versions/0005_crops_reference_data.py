"""Reference crops: photo key and unvalidated phenology stages (specs/003-fields-crops/decisions.md).

Stage thresholds are placeholders marked validated=false until an agronomist signs them off.
"""
import json

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CEREAL = [("emergence", 0), ("tillering", 100), ("heading", 400), ("maturity", 800)]
ANNUAL = [("emergence", 0), ("vegetative", 100), ("flowering", 400), ("maturity", 800)]
PERENNIAL = [("dormancy", 0), ("budburst", 100), ("flowering", 300), ("fruit_set", 600), ("ripening", 1000)]
CEREALS = {"durum-wheat", "soft-wheat", "barley"}
SLUGS = [
    "olive", "citrus", "durum-wheat", "soft-wheat", "barley", "tomato", "potato", "onion", "berries",
    "avocado", "date-palm", "almond", "grape", "sugar-beet", "alfalfa", "silage-maize",
]


def _stages(slug: str, cycle: str) -> str:
    base = CEREAL if slug in CEREALS else ANNUAL if cycle == "annual" else PERENNIAL
    return json.dumps([{"key": k, "gdd_from": g} for k, g in base])


def upgrade() -> None:
    for slug in SLUGS:
        op.execute(
            f"UPDATE crops SET photo_key = 'crops/{slug}.webp', validated = false,"
            f" stages = (CASE WHEN cycle = 'annual' THEN '{_stages(slug, 'annual')}' ELSE '{_stages(slug, 'perennial')}' END)::jsonb"
            f" WHERE farm_id IS NULL AND slug = '{slug}'"
        )


def downgrade() -> None:
    op.execute("UPDATE crops SET photo_key = NULL, stages = '[]'::jsonb WHERE farm_id IS NULL")
