"""T026 - the Arq health task answers (AC1.1)."""
import asyncio

import worker


def test_health_task_returns_ok() -> None:
    assert asyncio.run(worker.health({})) == {"status": "ok"}


def test_health_task_is_registered_in_worker_settings() -> None:
    names = {getattr(f, "__name__", getattr(f, "name", "")) for f in worker.WorkerSettings.functions}
    assert "health" in names
