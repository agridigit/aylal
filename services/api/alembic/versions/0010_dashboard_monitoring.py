"""F3 dashboard and monitoring (specs/006-dashboard-monitoring/data-model.md).

Revision ID: 0010
Revises: 0009

- 12 farm tables (every one carries farm_id NOT NULL and, when it concerns a parcel, a composite (farm_id, parcel_id)
  foreign key, so a cross-farm reference is refused by the database) and 5 global tables (no farm data);
- parcel_archived_at is copied from parcels.archived_at by triggers (archive, restore, merge) so the PowerSync rules
  need no join; it is initialised at insertion;
- parcel_vigor_points.valid is a generated column (clear_pct >= 80) and is never written;
- storage keys (map_key, photo_key, raster_key, object_key) follow a CHECKed pattern bound to the farm;
- NO agronomic value is seeded: crop_weather_thresholds stays empty until `import_crop_thresholds` loads a file
  validated by agronomy; monitoring_params only carries the non-agronomic parameters of the plan.
"""
from alembic import op

revision = "0010"
down_revision = "0009"

PARCEL_TABLES = (
    "alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones",
    "zone_observations",
)
UUID_RE = "[0-9a-f-]{36}"
FARM_TABLES = (
    "monitoring_jobs", "notification_prefs", "daily_summaries", "observation_uploads", "zone_observations",
    "attention_zones", "vigor_maps", "parcel_vigor_points", "parcel_status_items", "parcel_status", "alerts", "farm_weather",
)
GLOBAL_TABLES = ("weather_cells", "imagery_scenes", "imagery_tiles", "monitoring_params", "crop_weather_thresholds")


def _fk(extra: str = "") -> str:
    return f"FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE{extra}"


def upgrade() -> None:
    # ---- global reference data (no farm data) ----
    op.execute(
        """
        CREATE TABLE crop_weather_thresholds (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            crop_slug text NOT NULL,
            stage_key text NOT NULL,
            frost_c numeric,
            chergui_tmax_c numeric NOT NULL,
            chergui_rh_max_pct numeric NOT NULL,
            chergui_wind_kmh numeric NOT NULL,
            heavy_rain_mm_24h numeric NOT NULL,
            strong_wind_kmh numeric NOT NULL,
            source text NOT NULL,
            validated_by text,
            validated_at timestamptz,
            UNIQUE (crop_slug, stage_key)
        )"""
    )
    op.execute("CREATE TABLE monitoring_params (key text PRIMARY KEY, value jsonb NOT NULL)")
    op.execute(
        "INSERT INTO monitoring_params (key, value) VALUES ('cloud_min_clear_pct', '80'), ('min_area_ha', '0.3'),"
        " ('frost_notify_hour', '17'), ('summary_hour', '7'), ('weather_stale_hours', '24')"
    )
    op.execute("CREATE TABLE imagery_tiles (tile_id text PRIMARY KEY, last_ingested_on date)")
    op.execute(
        """
        CREATE TABLE imagery_scenes (
            id uuid PRIMARY KEY,
            tile_id text NOT NULL REFERENCES imagery_tiles(tile_id),
            acquired_on date NOT NULL,
            cloud_pct_scene numeric CHECK (cloud_pct_scene BETWEEN 0 AND 100),
            raster_key text NOT NULL,
            ingested_at timestamptz NOT NULL DEFAULT now()
        )"""
    )
    op.execute("CREATE INDEX imagery_scenes_tile ON imagery_scenes (tile_id, acquired_on DESC)")
    op.execute(
        "CREATE TABLE weather_cells (cell_id text PRIMARY KEY, fetched_at timestamptz NOT NULL,"
        " days jsonb NOT NULL DEFAULT '[]'::jsonb, source text)"
    )

    # ---- per farm ----
    op.execute(
        """
        CREATE TABLE farm_weather (
            farm_id uuid PRIMARY KEY REFERENCES farms(id) ON DELETE CASCADE,
            cell_id text,
            fetched_at timestamptz,
            availability text NOT NULL CHECK (availability IN ('ok', 'stale', 'unavailable')),
            reason text CHECK (reason IN ('gateway_not_configured', 'gateway_unreachable', 'farm_not_located', 'stale')),
            days jsonb NOT NULL DEFAULT '[]'::jsonb
        )"""
    )
    op.execute(
        f"""
        CREATE TABLE alerts (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            season_id uuid,
            crop_slug text,
            type text NOT NULL CHECK (type IN ('frost', 'chergui', 'heavy_rain', 'strong_wind')),
            severity text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
            source text NOT NULL DEFAULT 'forecast' CHECK (source = 'forecast'),
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'dismissed', 'expired')),
            forecast_day date NOT NULL,
            reason_key text NOT NULL,
            reason_params jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            advice_key text,
            notify_at timestamptz,
            notified_at timestamptz,
            revision integer NOT NULL DEFAULT 1,
            dedup_key text NOT NULL UNIQUE,
            parcel_archived_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (farm_id, id),
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX alerts_farm_status ON alerts (farm_id, status, forecast_day)")
    op.execute("CREATE INDEX alerts_parcel ON alerts (parcel_id)")
    op.execute(
        f"""
        CREATE TABLE parcel_status (
            parcel_id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            color text NOT NULL CHECK (color IN ('green', 'orange', 'red')),
            reason_key text NOT NULL,
            reason_params jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            rank integer NOT NULL DEFAULT 0,
            computed_at timestamptz NOT NULL,
            data_age_at timestamptz,
            imagery_reliability text NOT NULL DEFAULT 'ok' CHECK (imagery_reliability IN ('ok', 'low')),
            parcel_archived_at timestamptz,
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX parcel_status_farm ON parcel_status (farm_id, rank)")
    op.execute(
        f"""
        CREATE TABLE parcel_status_items (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            source text NOT NULL
                CHECK (source IN ('weather_alert', 'vigor_anomaly', 'overdue_operations', 'irrigation_need', 'health_risk')),
            severity text NOT NULL CHECK (severity IN ('watch', 'act')),
            reason_key text NOT NULL,
            reason_params jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            source_ref uuid,
            observed_at timestamptz NOT NULL,
            parcel_archived_at timestamptz,
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX parcel_status_items_parcel ON parcel_status_items (parcel_id)")
    op.execute(
        """
        CREATE TABLE parcel_vigor_points (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            scene_id uuid NOT NULL REFERENCES imagery_scenes(id),
            acquired_on date NOT NULL CHECK (acquired_on >= DATE '2017-01-01' AND acquired_on <= current_date),
            vigor_mean numeric NOT NULL,
            plant_moisture_mean numeric NOT NULL,
            clear_pct numeric NOT NULL CHECK (clear_pct BETWEEN 0 AND 100),
            valid boolean GENERATED ALWAYS AS (clear_pct >= 80) STORED,
            reliability text NOT NULL DEFAULT 'ok' CHECK (reliability IN ('ok', 'low')),
            season_id uuid,
            parcel_archived_at timestamptz,
            UNIQUE (parcel_id, scene_id),
            FOREIGN KEY (farm_id, parcel_id) REFERENCES parcels (farm_id, id) ON DELETE CASCADE
        )"""
    )
    op.execute("CREATE INDEX parcel_vigor_points_series ON parcel_vigor_points (parcel_id, acquired_on)")
    op.execute(
        f"""
        CREATE TABLE vigor_maps (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            scene_id uuid NOT NULL REFERENCES imagery_scenes(id),
            acquired_on date NOT NULL,
            map_key text NOT NULL CHECK (map_key ~ '^farms/{UUID_RE}/vigor/{UUID_RE}\\.png$'
                                         AND split_part(map_key, '/', 2) = farm_id::text),
            bounds jsonb NOT NULL DEFAULT '{{}}'::jsonb,
            parcel_archived_at timestamptz,
            UNIQUE (parcel_id, scene_id),
            {_fk()}
        )"""
    )
    op.execute(
        f"""
        CREATE TABLE attention_zones (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            geometry geometry(Polygon, 4326) NOT NULL,
            centroid geometry(Point, 4326) NOT NULL,
            detected_on date NOT NULL,
            drop_score numeric,
            area_ha numeric,
            status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'dismissed', 'visited', 'resolved')),
            reason_key text NOT NULL,
            parcel_archived_at timestamptz,
            UNIQUE (farm_id, id),
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX attention_zones_parcel ON attention_zones (parcel_id, status)")
    op.execute(
        f"""
        CREATE TABLE zone_observations (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            zone_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            author_id uuid NOT NULL,
            note text NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
            photo_key text CHECK (photo_key IS NULL OR (photo_key ~ '^farms/{UUID_RE}/zone-photos/{UUID_RE}$'
                                                       AND split_part(photo_key, '/', 2) = farm_id::text)),
            created_at timestamptz NOT NULL DEFAULT now(),
            parcel_archived_at timestamptz,
            FOREIGN KEY (farm_id, zone_id) REFERENCES attention_zones (farm_id, id) ON DELETE CASCADE,
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX zone_observations_zone ON zone_observations (zone_id)")
    op.execute("CREATE INDEX zone_observations_farm ON zone_observations (farm_id, created_at)")
    op.execute(
        """
        CREATE TABLE observation_uploads (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            object_key text NOT NULL,
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz
        )"""
    )
    op.execute(
        """
        CREATE TABLE daily_summaries (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            summary_date date NOT NULL,
            locale text NOT NULL CHECK (locale IN ('ary', 'ar', 'fr')),
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, farm_id, summary_date)
        )"""
    )
    op.execute(
        """
        CREATE TABLE notification_prefs (
            farm_id uuid NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            summary_hour integer NOT NULL DEFAULT 7 CHECK (summary_hour BETWEEN 0 AND 23),
            alerts_enabled boolean NOT NULL DEFAULT true,
            push_token text,
            PRIMARY KEY (farm_id, user_id)
        )"""
    )
    op.execute(
        f"""
        CREATE TABLE monitoring_jobs (
            id uuid PRIMARY KEY,
            farm_id uuid NOT NULL,
            parcel_id uuid NOT NULL,
            kind text NOT NULL CHECK (kind IN ('backfill', 'reprocess')),
            state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed')),
            requested_by uuid,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz,
            duration_s numeric,
            {_fk()}
        )"""
    )
    op.execute("CREATE INDEX monitoring_jobs_farm ON monitoring_jobs (farm_id, state)")
    op.execute("CREATE INDEX monitoring_jobs_parcel_day ON monitoring_jobs (parcel_id, created_at)")

    # ---- parcels.archived_at -> parcel_archived_at (archive, restore, merge) ----
    op.execute(
        """
        CREATE FUNCTION f3_init_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT archived_at INTO NEW.parcel_archived_at FROM parcels WHERE id = NEW.parcel_id AND farm_id = NEW.farm_id;
            RETURN NEW;
        END $$"""
    )
    for table in PARCEL_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_f3_init_archived_at BEFORE INSERT ON {table}"
            " FOR EACH ROW EXECUTE FUNCTION f3_init_parcel_archived_at()"
        )
    updates = "\n".join(
        f"                UPDATE {t} SET parcel_archived_at = NEW.archived_at WHERE farm_id = NEW.farm_id AND parcel_id = NEW.id;"
        for t in PARCEL_TABLES
    )
    op.execute(
        f"""
        CREATE FUNCTION f3_copy_parcel_archived_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.archived_at IS DISTINCT FROM OLD.archived_at THEN
{updates}
            END IF;
            RETURN NEW;
        END $$"""
    )
    op.execute(
        "CREATE TRIGGER parcels_f3_copy_archived_at AFTER UPDATE OF archived_at ON parcels"
        " FOR EACH ROW EXECUTE FUNCTION f3_copy_parcel_archived_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS parcels_f3_copy_archived_at ON parcels")
    for table in FARM_TABLES + GLOBAL_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS f3_copy_parcel_archived_at()")
    op.execute("DROP FUNCTION IF EXISTS f3_init_parcel_archived_at()")
