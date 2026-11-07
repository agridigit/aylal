"""T069 - invitations past their 30-day expiry are marked expired (R6-A3)."""
import asyncio
import datetime as dt

from tasks.expire_invitations import expire_invitations

NOW = dt.datetime(2026, 12, 8, 12, 0, tzinfo=dt.UTC)


class FakeRepo:
    def __init__(self):
        self.calls = []

    async def expire_invitations(self, now):
        self.calls.append(now)
        return 4


def test_given_the_task_when_run_then_the_repository_expires_with_the_current_time_and_returns_the_count():
    repo = FakeRepo()
    assert asyncio.run(expire_invitations({"repo": repo}, now=NOW)) == 4
    assert repo.calls == [NOW]


def test_given_the_worker_settings_then_the_expiry_is_scheduled_and_registered():
    import worker

    assert expire_invitations in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
    assert expire_invitations in worker.WorkerSettings.functions
