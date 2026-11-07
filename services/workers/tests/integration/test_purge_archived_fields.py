"""T061 - purge of fields archived for more than 90 days (CL); children go with them, fresh archives stay."""
import asyncio
import datetime as dt
import os
import uuid

import asyncpg
import pytest

NOW = dt.datetime.now(dt.UTC)
DSN = os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")
GEOM = "ST_SetSRID(ST_GeomFromText('POLYGON((-7.6 33.5,-7.59 33.5,-7.59 33.51,-7.6 33.51,-7.6 33.5))'),4326)"


class FakeRepo:
    def __init__(self):
        self.calls = []

    async def purge_archived_fields(self, now):
        self.calls.append(now)
        return 3


def test_given_the_task_when_run_then_the_repository_purges_with_the_current_time_and_returns_the_count():
    from tasks.purge_archived_fields import purge_archived_fields

    repo = FakeRepo()
    assert asyncio.run(purge_archived_fields({"repo": repo}, now=NOW)) == 3
    assert repo.calls == [NOW]


def test_given_the_worker_settings_then_the_field_purge_is_scheduled_and_registered():
    import worker
    from tasks.purge_archived_fields import purge_archived_fields

    assert purge_archived_fields in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
    assert purge_archived_fields in worker.WorkerSettings.functions


def test_given_archived_fields_when_purging_then_only_those_past_purge_after_are_deleted_with_their_children():
    from tasks.purge_archived_fields import SqlFieldRepo

    async def go():
        try:
            conn = await asyncpg.connect(DSN, timeout=5)
        except (OSError, asyncpg.PostgresError) as e:
            pytest.skip(f"database unreachable: {e}")
        farm, old, fresh, active = (uuid.uuid4() for _ in range(4))
        try:
            await conn.execute("INSERT INTO farms (id,name) VALUES ($1,'Purge')", farm)
            for fid, arch, after in (
                (old, NOW - dt.timedelta(days=91), NOW - dt.timedelta(days=1)),
                (fresh, NOW - dt.timedelta(days=10), NOW + dt.timedelta(days=80)),
                (active, None, None),
            ):
                await conn.execute(
                    f"INSERT INTO parcels (id,farm_id,name,geometry,archived_at,purge_after) VALUES ($1,$2,'F',{GEOM},$3,$4)",
                    fid, farm, arch, after,
                )
            await conn.execute(
                f"INSERT INTO field_blocks (id,farm_id,field_id,name,kind,geometry) VALUES ($1,$2,$3,'B','block',{GEOM})",
                uuid.uuid4(), farm, old,
            )
            assert await SqlFieldRepo(DSN).purge_archived_fields(NOW) >= 1
            left = {r[0] for r in await conn.fetch("SELECT id FROM parcels WHERE farm_id=$1", farm)}
            assert left == {fresh, active}
            assert await conn.fetchval("SELECT count(*) FROM field_blocks WHERE farm_id=$1", farm) == 0
        finally:
            await conn.execute("DELETE FROM field_blocks WHERE farm_id=$1", farm)
            await conn.execute("DELETE FROM parcels WHERE farm_id=$1", farm)
            await conn.execute("DELETE FROM farms WHERE id=$1", farm)
            await conn.close()

    asyncio.run(go())
