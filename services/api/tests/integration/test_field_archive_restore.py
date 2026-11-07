"""T061 - archived list, restore within 90 days, 404 after purge, 404 for the worker (CL)."""
from tests.helpers import auth, sql
from tests.integration._f2 import add_field, assign, new_user


def _world(make_farm):
    owner, worker = new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    field = add_field(farm, "Old")
    assign(farm, worker, field)
    return owner, worker, farm, field


def test_given_an_archived_field_then_it_is_listed_and_restorable_within_90_days(client, token_for, make_farm):
    owner, _, farm, field = _world(make_farm)
    h, base = auth(token_for(owner)), f"/v1/farms/{farm}/fields"
    assert client.delete(f"{base}/{field}", headers=h).status_code == 204
    row = sql("SELECT archived_at, purge_after FROM parcels WHERE id=$1", field)[0]
    assert 89 <= (row["purge_after"] - row["archived_at"]).days <= 90
    assert [f["id"] for f in client.get(f"{base}/archived", headers=h).json()["items"]] == [str(field)]
    assert client.post(f"{base}/{field}/restore", headers=h).status_code == 200
    assert client.get(f"{base}/archived", headers=h).json()["items"] == []


def test_given_a_field_past_its_purge_date_then_restore_returns_404(client, token_for, make_farm):
    owner, _, farm, field = _world(make_farm)
    h, base = auth(token_for(owner)), f"/v1/farms/{farm}/fields"
    client.delete(f"{base}/{field}", headers=h)
    sql("UPDATE parcels SET purge_after = now() - interval '1 day' WHERE id=$1", field)
    assert client.post(f"{base}/{field}/restore", headers=h).status_code == 404


def test_given_a_worker_then_archived_list_and_restore_are_404_or_403(client, token_for, make_farm):
    owner, worker, farm, field = _world(make_farm)
    base = f"/v1/farms/{farm}/fields"
    client.delete(f"{base}/{field}", headers=auth(token_for(owner)))
    hw = auth(token_for(worker))
    assert client.post(f"{base}/{field}/restore", headers=hw).status_code in (403, 404)
    items = client.get(f"{base}/archived", headers=hw)
    assert items.status_code in (403, 404) or items.json()["items"] == []
