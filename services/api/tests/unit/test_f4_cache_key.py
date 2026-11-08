"""T009 - G2: cache key irr:{farm}:{role}:{sha256(sorted visible ids)}:{local date}:{data_version}; ETag bounded to the scope."""
import datetime as dt
import hashlib
import re
import uuid

FARM = uuid.UUID(int=1)
P = [uuid.UUID(int=100 + i) for i in range(4)]
DAY = dt.date(2026, 6, 4)


def key(role="worker", parcels=P[:3], day=DAY, version=1, farm=FARM):
    from app.irrigation.cache import advice_cache_key

    return advice_cache_key(farm, role, parcels, day, version)


def test_given_a_worker_then_the_key_has_the_documented_shape_without_any_user_id():
    parts = key().split(":")
    assert parts[:3] == ["irr", str(FARM), "worker"]
    assert re.fullmatch(r"[0-9a-f]{64}", parts[3]) and parts[4] == "2026-06-04" and parts[5] == "1" and len(parts) == 6


def test_given_the_visible_ids_then_the_digest_is_the_sha256_of_the_sorted_ids():
    expected = hashlib.sha256(",".join(sorted(str(p) for p in P[:3])).encode()).hexdigest()
    assert key().split(":")[3] == expected or key().split(":")[3] == hashlib.sha256("".join(sorted(str(p) for p in P[:3])).encode()).hexdigest()


def test_given_the_same_parcels_in_any_order_then_the_key_is_identical():
    assert key(parcels=P[:3]) == key(parcels=list(reversed(P[:3])))


def test_given_an_assignment_or_an_archive_change_then_the_key_changes():
    assert key(parcels=P[:3]) != key(parcels=P[:2]) and key(parcels=P[:3]) != key(parcels=P)


def test_given_a_role_change_then_the_key_changes():
    assert len({key("owner"), key("manager"), key("worker")}) == 3


def test_given_a_new_local_day_then_the_key_changes():
    assert key(day=DAY) != key(day=DAY + dt.timedelta(days=1))


def test_given_a_new_data_version_or_another_farm_then_the_key_changes():
    assert key(version=1) != key(version=2) and key() != key(farm=uuid.UUID(int=2))


def test_given_the_etag_then_it_is_bounded_to_the_scope():
    from app.irrigation.cache import advice_etag

    a = advice_etag(FARM, "worker", P[:3], DAY, 1)
    assert a == advice_etag(FARM, "worker", list(reversed(P[:3])), DAY, 1)
    assert a != advice_etag(FARM, "worker", P, DAY, 1) and a != advice_etag(FARM, "owner", P[:3], DAY, 1)
    assert all(str(p) not in a for p in P)
