"""T009 - G2: cache key eco:{farm_id}:{role}:{season_or_all}:{data_version}; a role or version change changes the key; the ETag is scoped."""
import uuid

FARM = uuid.UUID(int=1)
SEASON = uuid.UUID(int=77)


def key(role="owner", season=SEASON, version=1, farm=FARM):
    from app.economics.cache import economics_cache_key

    return economics_cache_key(farm, role, season, version)


def test_given_a_season_then_the_key_has_the_documented_shape():
    assert key() == f"eco:{FARM}:owner:{SEASON}:1"


def test_given_no_season_then_the_segment_is_all():
    assert key(season=None) == f"eco:{FARM}:owner:all:1"


def test_given_a_role_change_then_the_key_changes():
    assert len({key("owner"), key("manager"), key("worker")}) == 3


def test_given_a_new_data_version_a_new_season_or_another_farm_then_the_key_changes():
    assert key(version=1) != key(version=2) and key() != key(season=None) and key() != key(farm=uuid.UUID(int=2))


def test_given_the_etag_then_it_depends_on_the_content_and_the_scope_and_leaks_no_id():
    from app.economics.cache import economics_etag

    a = economics_etag(key(), {"margin_cents": 100})
    assert a == economics_etag(key(), {"margin_cents": 100})
    assert a != economics_etag(key(), {"margin_cents": 101}) and a != economics_etag(key("manager"), {"margin_cents": 100})
    assert str(FARM) not in a and str(SEASON) not in a
