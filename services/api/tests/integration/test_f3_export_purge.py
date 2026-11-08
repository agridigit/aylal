"""T027 - G1: F3 tables are in the personal-data export (another member's push token excluded) and in the purge."""
import asyncio

from tests.helpers import sql
from tests.integration._f3 import (  # noqa: F401
    seed_alert,
    seed_prefs,
    seed_scene,
    seed_summary,
    seed_worker_rows,
    seed_zone,
    world3,
)

EXPORT_KEYS = {"alerts", "parcel_status", "parcel_vigor_points", "attention_zones", "zone_observations", "daily_summaries", "notification_prefs"}


def _export(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)

    return asyncio.run(run())


def test_given_an_owner_then_the_export_carries_every_f3_section(world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    seed_summary(w["farm_a"], w["owner"])
    seed_prefs(w["farm_a"], w["owner"], "owner-token")
    m = _export(w["owner"])["monitoring"]
    assert EXPORT_KEYS <= set(m)
    assert len(m["alerts"]) >= 1 and len(m["parcel_status"]) == 10 and len(m["daily_summaries"]) == 1


def test_given_two_members_then_the_export_contains_only_my_preferences_and_never_another_push_token(world3):
    w = world3
    seed_prefs(w["farm_a"], w["owner"], "owner-token")
    seed_prefs(w["farm_a"], w["worker"], "worker-token")
    mine = _export(w["owner"])["monitoring"]
    assert [p["user_id"] for p in mine["notification_prefs"]] == [str(w["owner"])]
    assert "worker-token" not in str(mine)
    theirs = _export(w["worker"])["monitoring"]
    assert "owner-token" not in str(theirs) and "worker-token" in str(theirs)  # my own token is mine to export


def test_given_storage_keys_then_they_never_appear_in_the_export(world3):
    w = world3
    seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    text = str(_export(w["owner"])["monitoring"])
    assert "map_key" not in text and "raster_key" not in text and "photo_key" not in text and "/vigor/" not in text


def test_given_a_farm_purge_then_f3_rows_are_erased_and_object_keys_are_returned_for_removal(world3):
    from app.accounts.purge import purge_farm_monitoring_data
    from app.db.session import sessionmaker

    w = world3
    rows = seed_worker_rows(w["farm_a"], w["a1"], w["worker"])
    sql("UPDATE zone_observations SET photo_key=$2 WHERE id=$1", rows["observation"], f"farms/{w['farm_a']}/zone-photos/{rows['zone']}")
    seed_summary(w["farm_a"], w["owner"])
    seed_prefs(w["farm_a"], w["owner"])

    async def run():
        async with sessionmaker() as s:
            keys = await purge_farm_monitoring_data(s, w["farm_a"])
            await s.commit()
            return keys

    keys = asyncio.run(run())
    assert any("/vigor/" in k for k in keys) and any("/zone-photos/" in k for k in keys)
    assert all(k.startswith(f"farms/{w['farm_a']}/") for k in keys)
    for t in ("alerts", "parcel_status", "parcel_status_items", "parcel_vigor_points", "vigor_maps", "attention_zones", "zone_observations",
              "daily_summaries", "notification_prefs", "monitoring_jobs", "observation_uploads", "farm_weather"):
        assert sql(f"SELECT count(*) FROM {t} WHERE farm_id=$1", w["farm_a"])[0][0] == 0, t
    assert sql("SELECT count(*) FROM parcel_status WHERE farm_id=$1", w["farm_b"])[0][0] == 1  # other farms untouched


def test_given_a_user_purge_then_only_that_users_personal_f3_data_goes(world3):
    from app.accounts.purge import purge_user_monitoring_data
    from app.db.session import sessionmaker

    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    seed_summary(w["farm_a"], w["worker"])
    seed_summary(w["farm_a"], w["owner"])
    seed_prefs(w["farm_a"], w["worker"])
    sql("INSERT INTO zone_observations (id, farm_id, zone_id, parcel_id, author_id, note, created_at) VALUES (gen_random_uuid(),$1,$2,$3,$4,'n',now())",
        w["farm_a"], z, w["a1"], w["worker"])

    async def run():
        async with sessionmaker() as s:
            await purge_user_monitoring_data(s, w["worker"])
            await s.commit()

    asyncio.run(run())
    assert sql("SELECT count(*) FROM daily_summaries WHERE user_id=$1", w["worker"])[0][0] == 0
    assert sql("SELECT count(*) FROM notification_prefs WHERE user_id=$1", w["worker"])[0][0] == 0
    assert sql("SELECT count(*) FROM zone_observations WHERE author_id=$1", w["worker"])[0][0] == 0
    assert sql("SELECT count(*) FROM daily_summaries WHERE user_id=$1", w["owner"])[0][0] == 1
