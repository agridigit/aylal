"""F4 irrigation and water balance (specs/007-irrigation-water-balance/data-model.md).

Revision ID: 0012
Revises: 0011

- every farm table carries farm_id NOT NULL, cascades from farms and, when it concerns a parcel, a composite
  (farm_id, parcel_id) foreign key, so a cross-farm reference is refused by the database;
- parcel_archived_at is copied from parcels.archived_at by triggers (archive, restore, merge): the PowerSync rules need no join;
- irrigation_applied is fed by trigger from irrigation_events (done only) and carries neither author nor note;
- cancelled -> done is refused by trigger; events and analyses are never deleted by the application (no DELETE grant);
- NO agronomic value is inserted: crop_irrigation_params, soil_textures and irrigation_params stay empty until
  `import_irrigation_params` loads a file validated by agronomy (fixtures live in the tests only);
- anonymize_registry_operator (F6 maintenance function) also erases the author of irrigation events and analyses.
"""
from pathlib import Path

from alembic import op

revision = "0012"
down_revision = "0011"

PARCEL_TABLES = (
    "irrigation_systems", "irrigation_events", "irrigation_applied", "water_analyses", "water_balance_days", "irrigation_plans",
    "moisture_corrections",
)
FARM_TABLES = (
    "irrigation_jobs", "irrigation_notification_log", "moisture_corrections", "irrigation_plans", "water_balance_days",
    "water_analyses", "irrigation_applied", "irrigation_events", "irrigation_system_versions", "irrigation_systems",
)
GLOBAL_TABLES = ("weather_observed", "irrigation_params", "soil_textures", "crop_irrigation_params")
REASONS = (
    "'no_system','no_crop_coefficient','no_root_depth','no_depletion_fraction','no_soil_reference','no_soil_reserve',"
    "'no_effective_rain_method','no_weather','no_salinity_reference','gateway_not_configured','gateway_unreachable','stale'"
)
_GONE = "opérateur supprimé"

_ANON_F4 = f"""
CREATE OR REPLACE FUNCTION anonymize_registry_operator(p_user uuid) RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE n integer; as_operator uuid[]; as_author uuid[];
        BEGIN
            PERFORM set_config('aylal.registry_maintenance', 'on', true);
            as_author := ARRAY(SELECT id FROM operations WHERE author_id = p_user);
            as_operator := ARRAY(SELECT id FROM operations WHERE operator_user_id = p_user
                                 UNION SELECT operation_id FROM registry_entries WHERE operator_user_id = p_user);
            UPDATE registry_entries SET
                   operator_name = CASE WHEN operator_user_id = p_user THEN '{_GONE}' ELSE operator_name END,
                   operator_user_id = CASE WHEN operator_user_id = p_user THEN NULL ELSE operator_user_id END,
                   recorded_by = CASE WHEN recorded_by = p_user THEN NULL ELSE recorded_by END
             WHERE operator_user_id = p_user OR recorded_by = p_user;
            GET DIAGNOSTICS n = ROW_COUNT;
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
                OR (c.field = 'note' AND EXISTS (
                      SELECT 1 FROM operation_corrections p
                       WHERE p.farm_id = c.farm_id AND p.operation_id = c.operation_id AND p.field = 'note'
                         AND p.author_id = p_user AND (p.corrected_at, p.id) < (c.corrected_at, c.id)
                         AND NOT EXISTS (SELECT 1 FROM operation_corrections m
                                          WHERE m.farm_id = c.farm_id AND m.operation_id = c.operation_id AND m.field = 'note'
                                            AND (m.corrected_at, m.id) > (p.corrected_at, p.id)
                                            AND (m.corrected_at, m.id) < (c.corrected_at, c.id))));
            -- F4: the deleted account is erased from irrigation events (author and note) and water analyses; its reminder log goes
            UPDATE irrigation_events SET author_id = NULL, note = NULL, updated_at = clock_timestamp() WHERE author_id = p_user;
            UPDATE water_analyses SET author_id = NULL, updated_at = clock_timestamp() WHERE author_id = p_user;
            DELETE FROM irrigation_notification_log WHERE user_id = p_user;
            PERFORM set_config('aylal.registry_maintenance', 'off', true);
            RETURN n;
        END $$"""

SYNC = """updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            server_version bigint NOT NULL DEFAULT 1,
            field_versions jsonb NOT NULL DEFAULT '{}'::jsonb"""


def upgrade() -> None:
    # ---- global referentials: EMPTY at delivery ----
    op.execute(
        """
        CREATE TABLE crop_irrigation_params (
            crop_slug text NOT NULL,
            stage_key text NOT NULL,
            kc numeric,
            root_depth_m numeric,
            depletion_fraction numeric,
            ece_threshold_ds_m numeric,
            ece_max_ds_m numeric,
            validated boolean NOT NULL DEFAULT false,
            validated_by text,
            source text NOT NULL DEFAULT '',
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            PRIMARY KEY (crop_slug, stage_key)
        )"""
    )
    op.execute(
        """
        CREATE TABLE soil_textures (
            texture_key text PRIMARY KEY,
            available_water_mm_per_m numeric,
            validated_by text,
            source text NOT NULL DEFAULT '',
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )"""
    )
    op.execute(
        """
        CREATE TABLE irrigation_params (
            key text PRIMARY KEY,
            value jsonb NOT NULL,
            validated_by text,
            source text NOT NULL DEFAULT '',
            imported_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )"""
    )
    op.execute(
        """
        CREATE TABLE weather_observed (
            cell_id text NOT NULL,
            day date NOT NULL,
            rain_mm numeric NOT NULL CHECK (rain_mm >= 0),
            fetched_at timestamptz NOT NULL,
            PRIMARY KEY (cell_id, day)
        )"""
    )

    # ---- per farm ----
    op.execute(
        f"""
        CREATE TABLE irrigation_systems (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('drip', 'sprinkler', 'pivot', 'gravity')),
            emitter_flow_lph numeric CHECK (emitter_flow_lph > 0),
            emitter_spacing_m numeric CHECK (emitter_spacing_m > 0),
            row_spacing_m numeric CHECK (row_spacing_m > 0),
            pump_flow_m3h numeric CHECK (pump_flow_m3h > 0),
            sectors_count integer NOT NULL CHECK (sectors_count BETWEEN 1 AND 50),
            efficiency numeric CHECK (efficiency > 0 AND efficiency <= 1),
            efficiency_is_default boolean NOT NULL DEFAULT true,
            parcel_archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {SYNC},
            CHECK (pump_flow_m3h IS NOT NULL OR (kind = 'drip' AND emitter_flow_lph IS NOT NULL
                   AND emitter_spacing_m IS NOT NULL AND row_spacing_m IS NOT NULL)),
            UNIQUE (farm_id, parcel_id),
            UNIQUE (farm_id, id),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute(
        """
        CREATE TABLE irrigation_system_versions (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            system_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
            changed_by uuid,
            changed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (farm_id, system_id) REFERENCES irrigation_systems (farm_id, id) ON DELETE CASCADE,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX irrigation_system_versions_system ON irrigation_system_versions (system_id, changed_at)")
    op.execute(
        f"""
        CREATE TABLE irrigation_events (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            season_id uuid,
            operation_id uuid NOT NULL,
            performed_on date NOT NULL,
            sector_no integer CHECK (sector_no >= 1),
            input_mode text NOT NULL CHECK (input_mode IN ('duration', 'volume')),
            duration_min integer CHECK (duration_min BETWEEN 1 AND 1440),
            volume_m3 numeric CHECK (volume_m3 > 0),
            net_mm numeric,
            author_id uuid,
            note text CHECK (char_length(note) <= 500),
            status text NOT NULL DEFAULT 'done' CHECK (status IN ('done', 'cancelled')),
            parcel_archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {SYNC},
            UNIQUE (farm_id, id),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX irrigation_events_parcel_day ON irrigation_events (parcel_id, performed_on)")
    op.execute("CREATE INDEX irrigation_events_author ON irrigation_events (author_id) WHERE author_id IS NOT NULL")
    op.execute(
        """
        CREATE TABLE irrigation_applied (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            season_id uuid,
            performed_on date NOT NULL,
            sector_no integer,
            volume_m3 numeric,
            net_mm numeric,
            parcel_archived_at timestamptz,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX irrigation_applied_parcel_day ON irrigation_applied (parcel_id, performed_on)")
    op.execute(
        f"""
        CREATE TABLE water_analyses (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            water_source text CHECK (char_length(water_source) <= 80),
            ec_ds_m numeric NOT NULL CHECK (ec_ds_m > 0 AND ec_ds_m <= 100),
            analysed_on date NOT NULL,
            author_id uuid,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
            parcel_archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            {SYNC},
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX water_analyses_parcel ON water_analyses (parcel_id, analysed_on DESC)")
    op.execute(
        """
        CREATE TABLE water_balance_days (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            season_id uuid,
            day date NOT NULL,
            et0_mm numeric,
            et0_method text CHECK (et0_method IN ('gateway', 'hargreaves')),
            kc numeric,
            etc_mm numeric,
            rain_mm numeric,
            rain_source text CHECK (rain_source IN ('observed', 'forecast', 'ignored_greenhouse')),
            rain_eff_mm numeric,
            irrigation_net_mm numeric,
            taw_mm numeric,
            raw_mm numeric,
            depletion_mm numeric,
            moisture_source text,
            inputs_hash text,
            parcel_archived_at timestamptz,
            UNIQUE (parcel_id, day),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute(
        f"""
        CREATE TABLE irrigation_plans (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            season_id uuid,
            for_date date NOT NULL,
            kind text NOT NULL CHECK (kind IN ('irrigate', 'postpone_rain', 'no_need', 'rainfed_stress', 'unavailable')),
            total_minutes integer,
            sectors jsonb NOT NULL DEFAULT '[]'::jsonb,
            net_need_mm numeric,
            leaching_fraction numeric,
            stress_level text CHECK (stress_level IN ('none', 'watch', 'high')),
            confidence text NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
            assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
            worker_assumptions jsonb NOT NULL DEFAULT '[]'::jsonb,
            unavailable_reason text CHECK (unavailable_reason IN ({REASONS})),
            computed_at timestamptz NOT NULL,
            ready_before_7 boolean NOT NULL DEFAULT false,
            parcel_archived_at timestamptz,
            UNIQUE (parcel_id, for_date),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX irrigation_plans_farm_day ON irrigation_plans (farm_id, for_date)")
    op.execute(
        """
        CREATE TABLE moisture_corrections (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            measured_on date NOT NULL,
            source text NOT NULL,
            depletion_mm numeric NOT NULL CHECK (depletion_mm >= 0),
            received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            parcel_archived_at timestamptz,
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute(
        """
        CREATE TABLE irrigation_notification_log (
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            for_date date NOT NULL,
            sent_at timestamptz NOT NULL,
            PRIMARY KEY (farm_id, user_id, for_date)
        )"""
    )
    op.execute(
        """
        CREATE TABLE irrigation_jobs (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            parcel_id uuid NOT NULL,
            from_date date NOT NULL,
            state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed')),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX irrigation_jobs_farm ON irrigation_jobs (farm_id, state)")

    # ---- events -> irrigation_applied (done only, no author, no note); cancelled never comes back ----
    op.execute(
        """
        CREATE FUNCTION f4_event_applied() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.status = 'cancelled' AND NEW.status = 'done' THEN
                RAISE EXCEPTION 'irrigation_events: cancelled -> done is never allowed';
            END IF;
            IF TG_OP = 'INSERT' AND NEW.status = 'done' THEN
                INSERT INTO irrigation_applied (id, farm_id, parcel_id, season_id, performed_on, sector_no, volume_m3, net_mm)
                VALUES (NEW.id, NEW.farm_id, NEW.parcel_id, NEW.season_id, NEW.performed_on, NEW.sector_no, NEW.volume_m3, NEW.net_mm);
            ELSIF TG_OP = 'UPDATE' AND NEW.status = 'cancelled' THEN
                DELETE FROM irrigation_applied WHERE id = NEW.id AND farm_id = NEW.farm_id;
            END IF;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER irrigation_events_guard BEFORE UPDATE OF status ON irrigation_events"
        " FOR EACH ROW EXECUTE FUNCTION f4_event_applied()"
    )
    op.execute(
        "CREATE TRIGGER irrigation_events_applied AFTER INSERT OR UPDATE OF status ON irrigation_events"
        " FOR EACH ROW EXECUTE FUNCTION f4_event_applied()"
    )

    # ---- parcels.archived_at -> parcel_archived_at (archive, restore, merge) ----
    op.execute(
        """
        CREATE FUNCTION f4_init_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT archived_at INTO NEW.parcel_archived_at FROM parcels WHERE id = NEW.parcel_id AND farm_id = NEW.farm_id;
            RETURN NEW;
        END $$"""
    )
    for table in PARCEL_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_f4_init_archived_at BEFORE INSERT ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION f4_init_parcel_archived_at()"
        )
    updates = "\n".join(
        f"                UPDATE {t} SET parcel_archived_at = NEW.archived_at WHERE farm_id = NEW.farm_id AND parcel_id = NEW.id;"
        for t in PARCEL_TABLES
    )
    op.execute(
        f"""
        CREATE FUNCTION f4_copy_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.archived_at IS DISTINCT FROM OLD.archived_at THEN
{updates}
            END IF;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER parcels_f4_copy_archived_at AFTER UPDATE OF archived_at ON parcels"
        " FOR EACH ROW EXECUTE FUNCTION f4_copy_parcel_archived_at()"
    )

    # ---- rights: referentials are readable by everyone, events and analyses are never deleted by the application ----
    op.execute("GRANT SELECT ON crop_irrigation_params, soil_textures, irrigation_params TO PUBLIC")
    op.execute("REVOKE DELETE ON irrigation_events, water_analyses FROM PUBLIC")

    # ---- F6 maintenance function extended with the F4 columns (account deletion only) ----
    op.execute(_ANON_F4)
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid) FROM PUBLIC")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS parcels_f4_copy_archived_at ON parcels")
    for table in FARM_TABLES + GLOBAL_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for fn in ("f4_copy_parcel_archived_at()", "f4_init_parcel_archived_at()", "f4_event_applied()"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}")
    # restore the F6 function as of migration 0009
    op.execute(_previous_anon_body())
    op.execute("REVOKE EXECUTE ON FUNCTION anonymize_registry_operator(uuid) FROM PUBLIC")


def _previous_anon_body() -> str:
    text = Path(__file__).with_name("0009_anonymisation_corrections.py").read_text(encoding="utf-8")
    start = text.index('_NEW_ANON = f"""') + len('_NEW_ANON = f"""')
    return text[start:text.index('"""', start)].replace("{_GONE}", _GONE)
