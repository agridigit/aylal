"""F2 fields and crops: parcels extended, crops (+16 seed), seasons, field_blocks, field_commands.

Revision ID: 0004
Revises: 0003

Notes (specs/003-fields-crops/decisions.md):
- seasons.crop_id and the crops reference are checked by the API (a reference crop has farm_id NULL,
  which a composite FK cannot express); everything else uses composite (farm_id, ...) keys.
- crops.farm_id has no FK to farms: the shared reference rows (farm_id NULL) must survive a
  TRUNCATE farms CASCADE, and the farm purge deletes its free crops explicitly.
- seasons.parcel_archived_at / field_blocks.parcel_archived_at copy parcels.archived_at (set by the
  server in the archive/restore transaction) so the PowerSync rules need no join.
"""
from alembic import op

revision = "0004"
down_revision = "0003"

# slug, name_ary, name_ar, name_fr, cycle
CROPS = [
    ("olive", "الزيتون", "الزيتون", "Olivier", "perennial"),
    ("citrus", "الحامض", "الحوامض", "Agrumes", "perennial"),
    ("durum-wheat", "القمح الصلب", "القمح الصلب", "Blé dur", "annual"),
    ("soft-wheat", "القمح الطري", "القمح اللين", "Blé tendre", "annual"),
    ("barley", "الشعير", "الشعير", "Orge", "annual"),
    ("tomato", "ماطيشة", "الطماطم", "Tomate", "annual"),
    ("potato", "بطاطا", "البطاطس", "Pomme de terre", "annual"),
    ("onion", "البصلة", "البصل", "Oignon", "annual"),
    ("berries", "الفواكه الحمرا", "الفواكه الحمراء", "Fruits rouges", "perennial"),
    ("avocado", "الأفوكا", "الأفوكادو", "Avocatier", "perennial"),
    ("date-palm", "النخيل", "النخيل", "Palmier dattier", "perennial"),
    ("almond", "اللوز", "اللوز", "Amandier", "perennial"),
    ("grape", "الدالية", "العنب", "Vigne", "perennial"),
    ("sugar-beet", "الشمندر", "الشمندر السكري", "Betterave", "annual"),
    ("alfalfa", "الفصة", "الفصة", "Luzerne", "perennial"),
    ("silage-maize", "الذرة العلفية", "الذرة العلفية", "Maïs fourrager", "annual"),
]
SYNC = (
    "server_version bigint NOT NULL DEFAULT 1, field_versions jsonb NOT NULL DEFAULT '{}'::jsonb,"
    " updated_at timestamptz NOT NULL DEFAULT now()"
)


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute("ALTER TABLE parcels ALTER COLUMN vigor DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE parcels
            ADD COLUMN area_calc_ha numeric(10,4),
            ADD COLUMN area_declared_ha numeric(10,4) CHECK (area_declared_ha > 0),
            ADD COLUMN irrigation text CHECK (irrigation IN ('rainfed','gravity','sprinkler','drip','pivot')),
            ADD COLUMN greenhouse boolean NOT NULL DEFAULT false,
            ADD COLUMN soil text,
            ADD COLUMN source text NOT NULL DEFAULT 'draw_taps'
                CHECK (source IN ('draw_taps','draw_gps','import')),
            ADD COLUMN gps_accuracy_m real,
            ADD COLUMN status_summary text CHECK (status_summary IN ('ok','watch','act')),
            ADD COLUMN created_by uuid,
            ADD COLUMN archived_at timestamptz,
            ADD COLUMN purge_after timestamptz,
            ADD COLUMN merged_into_id uuid,
            ADD COLUMN server_version bigint NOT NULL DEFAULT 1,
            ADD COLUMN field_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
            ADD CONSTRAINT parcels_merged_into_fk FOREIGN KEY (farm_id, merged_into_id)
                REFERENCES parcels (farm_id, id)"""
    )
    op.execute("CREATE INDEX parcels_purge_after ON parcels (purge_after) WHERE archived_at IS NOT NULL")

    op.execute(
        f"""
        CREATE TABLE crops (
            id uuid PRIMARY KEY,
            farm_id uuid,
            slug text NOT NULL,
            name_ary text NOT NULL, name_ar text NOT NULL, name_fr text NOT NULL,
            cycle text NOT NULL CHECK (cycle IN ('perennial','annual')),
            photo_key text,
            varieties jsonb NOT NULL DEFAULT '[]'::jsonb,
            stages jsonb NOT NULL DEFAULT '[]'::jsonb,
            has_agronomy boolean NOT NULL DEFAULT false,
            validated boolean NOT NULL DEFAULT false,
            created_by uuid,
            archived_at timestamptz,
            {SYNC},
            UNIQUE (farm_id, id)
        )"""
    )
    op.execute("CREATE UNIQUE INDEX crops_reference_slug ON crops (slug) WHERE farm_id IS NULL")
    op.execute("CREATE UNIQUE INDEX crops_farm_slug ON crops (farm_id, slug) WHERE farm_id IS NOT NULL")
    for slug, ary, ar, fr, cycle in CROPS:
        op.execute(
            "INSERT INTO crops (id, farm_id, slug, name_ary, name_ar, name_fr, cycle, has_agronomy)"
            f" VALUES (gen_random_uuid(), NULL, {_q(slug)}, {_q(ary)}, {_q(ar)}, {_q(fr)}, {_q(cycle)}, true)"
        )

    op.execute(
        f"""
        CREATE TABLE seasons (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            field_id uuid NOT NULL,
            crop_id uuid NOT NULL REFERENCES crops(id),
            variety text CHECK (char_length(variety) <= 80),
            planting_year smallint CHECK (planting_year >= 1900),
            sowing_date date,
            started_at date NOT NULL,
            ended_at date,
            stage_estimated text,
            stage_corrected text,
            stage_corrected_at timestamptz,
            destination text,
            parcel_archived_at timestamptz,
            {SYNC},
            CHECK (NOT (planting_year IS NOT NULL AND sowing_date IS NOT NULL)),
            CHECK (ended_at IS NULL OR ended_at >= started_at),
            FOREIGN KEY (farm_id, field_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX seasons_field ON seasons (field_id)")
    op.execute("CREATE INDEX seasons_farm ON seasons (farm_id)")
    op.execute("CREATE UNIQUE INDEX seasons_one_active ON seasons (field_id, crop_id) WHERE ended_at IS NULL")

    op.execute(
        f"""
        CREATE TABLE field_blocks (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            field_id uuid NOT NULL,
            name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
            kind text NOT NULL CHECK (kind IN ('block','irrigation_sector')),
            geometry geometry(Polygon, 4326) NOT NULL,
            area_calc_ha numeric(10,4),
            archived_at timestamptz,
            parcel_archived_at timestamptz,
            {SYNC},
            FOREIGN KEY (farm_id, field_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX field_blocks_field ON field_blocks (field_id)")
    op.execute("CREATE INDEX field_blocks_geometry_gist ON field_blocks USING GIST (geometry)")

    op.execute(
        """
        CREATE TABLE field_commands (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            kind text NOT NULL CHECK (kind IN ('merge')),
            payload jsonb NOT NULL,
            created_by uuid,
            applied_at timestamptz,
            result jsonb
        )"""
    )
    op.execute("CREATE INDEX field_commands_farm ON field_commands (farm_id)")


def downgrade() -> None:
    for table in ("field_commands", "field_blocks", "seasons", "crops"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP INDEX IF EXISTS parcels_purge_after")
    op.execute("ALTER TABLE parcels DROP CONSTRAINT IF EXISTS parcels_merged_into_fk")
    op.execute(
        "ALTER TABLE parcels DROP COLUMN area_calc_ha, DROP COLUMN area_declared_ha,"
        " DROP COLUMN irrigation, DROP COLUMN greenhouse, DROP COLUMN soil, DROP COLUMN source,"
        " DROP COLUMN gps_accuracy_m, DROP COLUMN status_summary, DROP COLUMN created_by,"
        " DROP COLUMN archived_at, DROP COLUMN purge_after, DROP COLUMN merged_into_id,"
        " DROP COLUMN server_version, DROP COLUMN field_versions, DROP COLUMN updated_at"
    )
    op.execute("UPDATE parcels SET vigor = 0 WHERE vigor IS NULL")
    op.execute("ALTER TABLE parcels ALTER COLUMN vigor SET NOT NULL")
