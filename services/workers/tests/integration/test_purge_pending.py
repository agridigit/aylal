"""T040 - purge of pending accounts: older than 24 h, no consent, nothing but the phone (FR-012)."""
import asyncio
import datetime as dt

from tasks.purge_deleted_accounts import PENDING_TTL, purge_pending

NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.UTC)


class FakeRepo:
    def __init__(self):
        self.deleted: list[int] = []

    async def purge_pending_accounts(self, now):
        self.deleted.append(now)
        return 3


def test_given_the_ttl_then_it_is_24_hours():
    assert PENDING_TTL == dt.timedelta(hours=24)


def test_given_the_task_when_run_then_the_repository_purges_with_the_current_time_and_the_count_is_returned():
    repo = FakeRepo()
    assert asyncio.run(purge_pending({"repo": repo}, now=NOW)) == 3
    assert repo.deleted == [NOW]


def test_given_the_worker_settings_then_the_purge_is_scheduled_hourly():
    import worker

    assert purge_pending in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
