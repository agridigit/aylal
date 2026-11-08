"""T032 - G7: e2e/test hygiene and determinism: unique phones, Redis per worker, farm isolation, clock-driven worker hours, no real sleep."""
import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
FORBIDDEN_SQL = re.compile(r"DELETE\s+FROM\s+(operations|registry_entries|irrigation_events|water_analyses)\b", re.I)
REAL_SLEEP = re.compile(r"(?<![\w.])(time\.sleep|asyncio\.sleep)\(\s*([2-9]|\d{2,}|[1-9]\.\d*[1-9])")


def _code_lines(path):
    """Lines of code only: comments and docstrings can name what the scan forbids."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'"""(?:.|\n)*?"""', lambda m: "\n" * m.group(0).count("\n"), text)
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        if code.strip():
            yield i, code


def _f4_test_files():
    files = sorted(p for p in TESTS.rglob("*.py") if p.name.startswith(("test_f4_", "_f4")) and p.name != Path(__file__).name)
    assert len(files) >= 20, "F4 test files not found"
    return files


def test_given_the_f4_tests_then_none_calls_flushdb_or_deletes_from_a_protected_table():
    for p in _f4_test_files():
        for i, code in _code_lines(p):
            assert not re.search(r"flushdb|flushall", code, re.I), f"{p.name}:{i}"
            assert not FORBIDDEN_SQL.search(code), f"{p.name}:{i} {code.strip()}"


def test_given_the_e2e_phone_generator_then_numbers_are_unique_per_call_and_per_run():
    from tests.e2e._f4 import unique_phone

    numbers = {unique_phone() for _ in range(500)}
    assert len(numbers) == 500 and all(re.fullmatch(r"\+2126\d{8}", n) for n in numbers)


def test_given_the_f4_e2e_files_then_every_phone_comes_from_the_generator_and_never_a_literal():
    files = sorted((TESTS / "e2e").glob("*f4*.py"))
    assert files, "no F4 e2e file"
    for p in files:
        for i, code in _code_lines(p):
            assert not re.search(r"\+2126\d{8}", code), f"{p.name}:{i} hardcoded phone"


def test_given_xdist_workers_then_each_gets_its_own_redis_database_and_the_f4_keys_are_prefixed():
    import os

    url = os.environ["AYLAL_REDIS_URL"]
    worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    if worker.startswith("gw") and worker[2:].isdigit():
        assert url.rsplit("/", 1)[1] == str(1 + int(worker[2:]) % 15)
    from tests.integration._f4 import flush_f4_redis

    flush_f4_redis()  # only f4:*, irr:*, irrver:*, gw:* keys: never the whole database


def test_given_two_worlds_then_each_test_owns_a_unique_farm_and_unique_phones(world4):
    from tests.helpers import sql

    w = world4
    phones = [r[0] for r in sql("SELECT phone_e164 FROM users WHERE id = ANY($1)", [w["owner"], w["manager"], w["worker"], w["worker2"], w["owner_b"], w["outsider"]])]
    assert len(set(phones)) == 6 and w["farm_a"] != w["farm_b"]


def test_given_the_worker_clock_then_the_03_00_local_run_and_ready_before_7_are_driven_by_the_injected_clock():
    import datetime as dt

    from app.domain.clock import AdvancingClock
    from app.irrigation.plans import ready_before_7, scheduled_run_at

    clock = AdvancingClock(dt.datetime(2026, 6, 4, 1, 0, tzinfo=dt.UTC))
    run_at = scheduled_run_at(clock.now())
    assert run_at.astimezone(dt.timezone(dt.timedelta(hours=1))).hour == 3 and run_at.astimezone(dt.timezone(dt.timedelta(hours=1))).minute == 0
    assert ready_before_7(clock.now()) is True
    clock.advance(dt.timedelta(hours=7))  # 08:00 UTC = 09:00 local
    assert ready_before_7(clock.now()) is False


def test_given_the_f4_tests_then_none_sleeps_for_real_time():
    for p in _f4_test_files():
        for i, code in _code_lines(p):
            assert not REAL_SLEEP.search(code), f"{p.name}:{i} {code.strip()}"


def test_given_the_f4_tests_then_none_reads_the_system_clock():
    pattern = re.compile(r"(datetime\.now|date\.today|datetime\.utcnow|time\.time\(\))")
    for p in _f4_test_files():
        for i, code in _code_lines(p):
            assert not pattern.search(code), f"{p.name}:{i} {code.strip()}"
