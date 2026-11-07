"""F1 account, onboarding and farm: users, consents, OTP, sessions, roles, invitations, geo reference.

Revision ID: 0002
Revises: 0001

Deviations from data-model.md (see specs/002-account-onboarding-farm/decisions.md):
- farms.owner_id / farms.location stay nullable at database level (F0 rows, fixtures); the API
  and the sync layer enforce them.
- No FK to users on farm_members.user_id, farms.owner_id, invitations.invited_by (sync can create
  a farm before the users row exists).
"""
from alembic import op

revision = "0002"
down_revision = "0001"

# (id, name_fr, name_ar, province name_fr, province name_ar, commune name_fr, commune name_ar,
#  lon_min, lat_min, lon_max, lat_max) - coarse reference boxes around the main city of each
#  region; the official HCP/ANCFCC import replaces them (decisions.md).
GEO = [
    (1, "Tanger-Tétouan-Al Hoceïma", "طنجة تطوان الحسيمة", "Tanger-Assilah", "طنجة أصيلة", "Tanger", "طنجة", -5.95, 35.70, -5.70, 35.85),
    (2, "L'Oriental", "الشرق", "Oujda-Angad", "وجدة أنجاد", "Oujda", "وجدة", -2.05, 34.60, -1.80, 34.75),
    (3, "Fès-Meknès", "فاس مكناس", "Fès", "فاس", "Fès", "فاس", -5.15, 33.95, -4.90, 34.10),
    (4, "Rabat-Salé-Kénitra", "الرباط سلا القنيطرة", "Rabat", "الرباط", "Rabat", "الرباط", -6.95, 33.95, -6.75, 34.10),
    (5, "Béni Mellal-Khénifra", "بني ملال خنيفرة", "Béni Mellal", "بني ملال", "Béni Mellal", "بني ملال", -6.45, 32.28, -6.25, 32.40),
    (6, "Casablanca-Settat", "الدار البيضاء سطات", "Casablanca", "الدار البيضاء", "Casablanca", "الدار البيضاء", -7.75, 33.45, -7.45, 33.70),
    (7, "Marrakech-Safi", "مراكش آسفي", "Marrakech", "مراكش", "Marrakech", "مراكش", -8.10, 31.55, -7.85, 31.72),
    (8, "Drâa-Tafilalet", "درعة تافيلالت", "Errachidia", "الرشيدية", "Errachidia", "الرشيدية", -4.55, 31.88, -4.35, 32.00),
    (9, "Souss-Massa", "سوس ماسة", "Agadir Ida-Outanane", "أكادير إداوتنان", "Agadir", "أكادير", -9.70, 30.35, -9.50, 30.50),
    (10, "Guelmim-Oued Noun", "كلميم واد نون", "Guelmim", "كلميم", "Guelmim", "كلميم", -10.15, 28.92, -9.95, 29.05),
    (11, "Laâyoune-Sakia El Hamra", "العيون الساقية الحمراء", "Laâyoune", "العيون", "Laâyoune", "العيون", -13.30, 27.05, -13.05, 27.20),
    (12, "Dakhla-Oued Ed-Dahab", "الداخلة وادي الذهب", "Oued Ed-Dahab", "وادي الذهب", "Dakhla", "الداخلة", -16.05, 23.60, -15.85, 23.78),
]


def _q(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _load_geo() -> None:
    for i, rf, ra, pf, pa, cf, ca, x0, y0, x1, y1 in GEO:
        op.execute(f"INSERT INTO geo_regions (id, name_fr, name_ar) VALUES ({i}, {_q(rf)}, {_q(ra)})")
        op.execute(
            "INSERT INTO geo_provinces (id, name_fr, name_ar, parent_id)"
            f" VALUES ({i}, {_q(pf)}, {_q(pa)}, {i})"
        )
        ring = f"{x0} {y0}, {x0} {y1}, {x1} {y1}, {x1} {y0}, {x0} {y0}"
        op.execute(
            "INSERT INTO geo_communes (id, name_fr, name_ar, parent_id, geom) VALUES"
            f" ({i}, {_q(cf)}, {_q(ca)}, {i}, ST_GeomFromText('MULTIPOLYGON((({ring})))', 4326))"
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE geo_regions (
            id integer PRIMARY KEY, name_ar text NOT NULL, name_fr text NOT NULL
        )"""
    )
    op.execute(
        """
        CREATE TABLE geo_provinces (
            id integer PRIMARY KEY, name_ar text NOT NULL, name_fr text NOT NULL,
            parent_id integer NOT NULL REFERENCES geo_regions(id)
        )"""
    )
    op.execute(
        """
        CREATE TABLE geo_communes (
            id integer PRIMARY KEY, name_ar text NOT NULL, name_fr text NOT NULL,
            parent_id integer NOT NULL REFERENCES geo_provinces(id),
            geom geometry(MultiPolygon, 4326) NOT NULL
        )"""
    )
    op.execute("CREATE INDEX geo_communes_geom_gist ON geo_communes USING GIST (geom)")
    op.execute("CREATE INDEX geo_communes_parent ON geo_communes (parent_id)")
    _load_geo()

    op.execute(
        """
        CREATE TABLE users (
            id uuid PRIMARY KEY,
            phone_e164 text NOT NULL UNIQUE,
            display_name text CHECK (char_length(display_name) BETWEEN 1 AND 80),
            language text CHECK (language IN ('ary', 'ar', 'fr')),
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'active', 'deletion_requested')),
            onboarding_step text,
            deletion_requested_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute(
        """
        CREATE TABLE consents (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            purpose text NOT NULL,
            text_version text NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT now(),
            withdrawn_at timestamptz
        )"""
    )
    op.execute("CREATE INDEX consents_user ON consents (user_id)")
    op.execute(
        """
        CREATE TABLE otp_challenges (
            id uuid PRIMARY KEY,
            phone_e164 text NOT NULL,
            code_hash text NOT NULL,
            channel text NOT NULL DEFAULT 'sms' CHECK (channel IN ('sms', 'whatsapp')),
            expires_at timestamptz NOT NULL,
            failed_attempts integer NOT NULL DEFAULT 0,
            locked_until timestamptz,
            last_sent_at timestamptz NOT NULL DEFAULT now(),
            consumed_at timestamptz
        )"""
    )
    op.execute("CREATE INDEX otp_challenges_phone ON otp_challenges (phone_e164)")
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash text NOT NULL UNIQUE,
            device_id text,
            family_id uuid NOT NULL,
            rotated_at timestamptz,
            revoked_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute("CREATE INDEX refresh_tokens_user ON refresh_tokens (user_id)")

    op.execute(
        """
        ALTER TABLE farms
            ADD COLUMN owner_id uuid,
            ADD COLUMN location geometry(Point, 4326),
            ADD COLUMN commune_id integer REFERENCES geo_communes(id),
            ADD COLUMN area_ha numeric CHECK (area_ha >= 0),
            ADD COLUMN deleted_at timestamptz"""
    )
    op.execute("CREATE INDEX farms_location_gist ON farms USING GIST (location)")

    op.execute("ALTER TABLE farm_members DROP CONSTRAINT farm_members_role_check")
    op.execute("UPDATE farm_members SET role = 'manager' WHERE role = 'editor'")
    op.execute("UPDATE farm_members SET role = 'worker' WHERE role = 'viewer'")
    op.execute(
        "ALTER TABLE farm_members ADD CONSTRAINT farm_members_role_check"
        " CHECK (role IN ('owner', 'manager', 'worker'))"
    )
    op.execute(
        "ALTER TABLE farm_members"
        " ADD COLUMN added_at timestamptz NOT NULL DEFAULT now(),"
        " ADD COLUMN removed_at timestamptz"
    )
    op.execute("CREATE UNIQUE INDEX farm_members_one_owner ON farm_members (farm_id) WHERE role = 'owner'")
    op.execute("CREATE INDEX farm_members_user ON farm_members (user_id)")

    op.execute("ALTER TABLE parcels ADD CONSTRAINT parcels_farm_id_id_key UNIQUE (farm_id, id)")
    op.execute(
        """
        CREATE TABLE worker_parcels (
            farm_id uuid NOT NULL,
            user_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            assigned_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (farm_id, user_id, parcel_id),
            FOREIGN KEY (farm_id, user_id) REFERENCES farm_members (farm_id, user_id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute(
        """
        CREATE TABLE invitations (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            phone_e164 text NOT NULL,
            role text NOT NULL CHECK (role IN ('manager', 'worker')),
            status text NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'accepted', 'cancelled', 'expired')),
            invited_by uuid NOT NULL,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute(
        "CREATE UNIQUE INDEX invitations_pending_phone ON invitations (farm_id, phone_e164)"
        " WHERE status = 'pending'"
    )
    op.execute("CREATE INDEX invitations_phone ON invitations (phone_e164)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS invitations")
    op.execute("DROP TABLE IF EXISTS worker_parcels")
    op.execute("ALTER TABLE parcels DROP CONSTRAINT IF EXISTS parcels_farm_id_id_key")
    op.execute("DROP INDEX IF EXISTS farm_members_user")
    op.execute("DROP INDEX IF EXISTS farm_members_one_owner")
    op.execute("ALTER TABLE farm_members DROP COLUMN IF EXISTS removed_at, DROP COLUMN IF EXISTS added_at")
    op.execute("ALTER TABLE farm_members DROP CONSTRAINT farm_members_role_check")
    op.execute("UPDATE farm_members SET role = 'editor' WHERE role = 'manager'")
    op.execute("UPDATE farm_members SET role = 'viewer' WHERE role = 'worker'")
    op.execute(
        "ALTER TABLE farm_members ADD CONSTRAINT farm_members_role_check"
        " CHECK (role IN ('owner', 'editor', 'viewer'))"
    )
    op.execute("DROP INDEX IF EXISTS farms_location_gist")
    op.execute(
        "ALTER TABLE farms DROP COLUMN IF EXISTS deleted_at, DROP COLUMN IF EXISTS area_ha,"
        " DROP COLUMN IF EXISTS commune_id, DROP COLUMN IF EXISTS location,"
        " DROP COLUMN IF EXISTS owner_id"
    )
    for table in (
        "refresh_tokens", "otp_challenges", "consents", "users",
        "geo_communes", "geo_provinces", "geo_regions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
