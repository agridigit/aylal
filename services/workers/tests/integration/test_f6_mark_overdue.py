"""T060 - R4-A4: the worker task `mark_overdue_operations` flags reminders of planned operations whose date has passed.

It never changes an operation status (overdue is derived) and never touches done, cancelled or future operations.
"""
import asyncio
import datetime as dt
import uuid

from tests.integration.test_sql_account_repo import run

from tasks.mark_overdue_operations import SqlOverdueRepo, mark_overdue_operations

TODAY = dt.date(2026, 11, 7)


class FakeRepo:
    def __init__(self):
        self.calls = []

    async def mark_overdue(self, today):
        self.calls.append(today)
        return 3


def test_given_the_task_when_run_then_the_repository_marks_with_the_given_day_and_returns_the_count():
    repo = FakeRepo()
    assert asyncio.run(mark_overdue_operations({"repo": repo}, today=TODAY)) == 3
    assert repo.calls == [TODAY]


def test_given_the_worker_settings_then_the_task_is_scheduled_daily_and_registered():
    import worker

    assert mark_overdue_operations in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
    assert mark_overdue_operations in worker.WorkerSettings.functions


def test_given_planned_operations_against_a_real_database_then_only_past_planned_reminders_are_flagged_and_statuses_are_untouched():
    async def scenario(conn):
        farm, author = uuid.uuid4(), uuid.uuid4()
        past, today_op, future, done, cancelled = (uuid.uuid4() for _ in range(5))
        try:
            await conn.execute("INSERT INTO farms (id, name) VALUES ($1, 'F')", farm)
            rows = [(past, "planned", TODAY - dt.timedelta(days=2), "scheduled"), (today_op, "planned", TODAY, "scheduled"),
                    (future, "planned", TODAY + dt.timedelta(days=2), "scheduled"), (done, "validated", TODAY - dt.timedelta(days=3), "done"),
                    (cancelled, "cancelled", TODAY - dt.timedelta(days=3), "dismissed")]
            for oid, status, day, state in rows:
                await conn.execute("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,'irrigation',$3,$4,$5)",
                                   oid, farm, day, status, author)
                await conn.execute("INSERT INTO operation_reminders (id, farm_id, operation_id, fire_on, state) VALUES ($1,$2,$3,$4,$5)",
                                   uuid.uuid4(), farm, oid, day, state)
            changed = await SqlOverdueRepo().mark_overdue(TODAY)
            again = await SqlOverdueRepo().mark_overdue(TODAY)
            states = {r["operation_id"]: r["state"] for r in await conn.fetch("SELECT operation_id, state FROM operation_reminders WHERE farm_id=$1", farm)}
            statuses = {r["id"]: r["status"] for r in await conn.fetch("SELECT id, status FROM operations WHERE farm_id=$1", farm)}
            return changed, again, states, statuses, (past, today_op, future, done, cancelled)
        finally:
            await conn.execute("DELETE FROM farms WHERE id=$1", farm)

    changed, again, states, statuses, (past, today_op, future, done, cancelled) = run(scenario)
    assert changed == 2 and again == 0
    assert states[past] == "fired" and states[today_op] == "fired"
    assert states[future] == "scheduled" and states[done] == "done" and states[cancelled] == "dismissed"
    assert statuses[past] == "planned" and statuses[done] == "validated" and statuses[cancelled] == "cancelled"
