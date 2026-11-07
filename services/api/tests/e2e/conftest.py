"""E2E tests go through the running stack API, so their SQL fixtures must use the stack database."""
import os

import pytest


@pytest.fixture(autouse=True)
def _stack_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AYLAL_DATABASE_URL", os.environ["AYLAL_STACK_DATABASE_URL"])
