"""T008 - G2: cache key dash:{farm}:{role}:{user if worker}:{sha256(sorted visible ids)}:{data_version}."""
import re
import uuid

FARM = uuid.uuid4()
U1, U2 = uuid.uuid4(), uuid.uuid4()
P = [uuid.uuid4() for _ in range(4)]


def key(role="worker", user=U1, parcels=P[:3], version=1):
    from app.monitoring.cache import dashboard_cache_key

    return dashboard_cache_key(FARM, role, user, parcels, version)


def test_given_a_worker_then_the_key_has_the_documented_shape():
    k = key()
    parts = k.split(":")
    assert parts[:4] == ["dash", str(FARM), "worker", str(U1)]
    assert re.fullmatch(r"[0-9a-f]{64}", parts[4]) and parts[5] == "1"


def test_given_staff_then_the_user_id_is_not_part_of_the_key_so_staff_share_by_farm_role_and_scope():
    assert str(U1) not in key("owner", U1) and key("owner", U1) == key("owner", U2)
    assert key("manager", U1) == key("manager", U2)


def test_given_two_roles_with_the_same_visible_parcels_then_keys_differ():
    assert key("owner") != key("manager") != key("worker")


def test_given_two_workers_with_identical_parcels_then_keys_differ():
    assert key(user=U1) != key(user=U2)


def test_given_the_visible_parcels_change_or_the_data_version_changes_then_the_key_changes():
    assert key(parcels=P[:3]) != key(parcels=P[:2]) and key(parcels=P[:3]) != key(parcels=P)
    assert key(version=1) != key(version=2)


def test_given_the_same_parcels_in_any_order_then_the_key_is_identical():
    assert key(parcels=P[:3]) == key(parcels=list(reversed(P[:3])))


def test_given_a_worker_scope_and_a_staff_scope_then_they_never_share_an_entry():
    assert key("worker", parcels=P) != key("owner", parcels=P)
