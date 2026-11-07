"""Auth hardening: /v1/auth/dev-token exists only with AYLAL_ENABLE_DEV_TOKEN=1 and env dev/test."""
import uuid

import pytest
from fastapi.testclient import TestClient

STRONG = "s" * 40


def _post(client: TestClient) -> int:
    return client.post("/v1/auth/dev-token", json={"user_id": str(uuid.uuid4())}).status_code


def _set(monkeypatch: pytest.MonkeyPatch, env: str | None, flag: str | None) -> None:
    for key, value in (("AYLAL_ENV", env), ("AYLAL_ENABLE_DEV_TOKEN", flag)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("AYLAL_JWT_SECRET", STRONG)


@pytest.mark.parametrize("env", ["dev", "test"])
def test_given_flag_on_when_env_is_dev_or_test_then_dev_token_is_served(client, monkeypatch, env):
    _set(monkeypatch, env, "1")
    assert _post(client) == 200


@pytest.mark.parametrize("env", ["dev", "test"])
def test_given_dev_or_test_env_when_flag_absent_then_dev_token_is_404(client, monkeypatch, env):
    _set(monkeypatch, env, None)
    assert _post(client) == 404


@pytest.mark.parametrize("flag", ["0", "", "true"])
def test_given_dev_env_when_flag_is_not_exactly_1_then_dev_token_is_404(client, monkeypatch, flag):
    _set(monkeypatch, "dev", flag)
    assert _post(client) == 404


@pytest.mark.parametrize("env", ["prod", "staging", None])
def test_given_flag_on_when_env_is_not_dev_or_test_then_dev_token_is_404(client, monkeypatch, env):
    _set(monkeypatch, env, "1")
    assert _post(client) == 404
