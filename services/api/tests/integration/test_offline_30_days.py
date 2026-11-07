"""T042 - 1 000 records created and edited over 30 simulated days: 0 loss, 0 duplicate (AC3.3, SC-005)."""
import uuid

from tests.helpers import op, sql

N, DAYS, CHUNK = 1000, 30, 500


def _send(upload, token, ops):
    results = []
    for i in range(0, len(ops), CHUNK):
        results += upload(token, ops[i : i + CHUNK])["results"]
    return results


def test_given_30_days_offline_with_1000_records_when_reconnecting_then_nothing_is_lost_or_duplicated(
    client, token_for, make_farm, upload
) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: "editor"})
    token = token_for(user)
    ids = [uuid.uuid4() for _ in range(N)]
    queue = [op(farm, r, kind="put", fields={"title": f"r{n}", "quantity": 0}) for n, r in enumerate(ids)]
    expected = {r: {"title": f"r{n}", "quantity": 0} for n, r in enumerate(ids)}
    # the device only ever knew server_version 1 while offline; the server orders by arrival
    for day in range(1, DAYS + 1):
        for n in range(day % 7, N, 7):
            expected[ids[n]]["quantity"] = day
            queue.append(op(farm, ids[n], fields={"quantity": day}, base_version=1))
    total_ops = len(queue)
    _send(upload, token, queue)
    resend = _send(upload, token, queue)  # flaky network: whole queue replayed
    assert {r["status"] for r in resend} == {"duplicate"}
    rows = {r["id"]: r for r in sql("SELECT id, title, quantity FROM trial_records")}
    assert len(rows) == N
    assert sql("SELECT count(*) AS n FROM applied_ops")[0]["n"] == total_ops
    for rid, exp in expected.items():
        assert rows[rid]["title"] == exp["title"]
        assert float(rows[rid]["quantity"]) == exp["quantity"]
