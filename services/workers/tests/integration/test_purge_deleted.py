"""T054 - purge of accounts whose 30-day deletion period elapsed (R8-A1, FR-025)."""
import asyncio
import datetime as dt

from tasks.purge_deleted_accounts import DELETION_GRACE, purge_deleted

NOW = dt.datetime(2026, 12, 8, 12, 0, tzinfo=dt.UTC)


class FakeRepo:
    def __init__(self):
        self.calls = []

    async def purge_deleted_accounts(self, now):
        self.calls.append(now)
        return 2


def test_given_the_grace_then_it_is_30_days():
    assert DELETION_GRACE == dt.timedelta(days=30)


def test_given_the_task_when_run_then_the_repository_purges_with_the_current_time_and_returns_the_count():
    repo = FakeRepo()
    assert asyncio.run(purge_deleted({"repo": repo}, now=NOW)) == 2
    assert repo.calls == [NOW]


def test_given_the_worker_settings_then_the_deletion_purge_is_scheduled_and_registered():
    import worker

    assert purge_deleted in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
    assert purge_deleted in worker.WorkerSettings.functions
