"""T069 (US4) - R4-A1..A3: Python mirror of packages/domain/tests/consumption-us4.test.ts (the shared consumption rule)."""
import pytest


def _summary(parcels):
    from app.domain.consumption import summarise_consumption

    return summarise_consumption({"parcels": parcels})


def test_given_irrigations_on_a_2_ha_parcel_then_the_volume_and_the_volume_per_hectare_are_given():
    out = _summary([{"parcel_id": "a", "volume_m3": 120, "area_ha": 2}])
    assert out["parcels"][0]["volume_m3_per_ha"] == 60 and out["total_m3"] == 120 and out["empty"] is False


def test_given_two_parcels_of_different_areas_then_each_ratio_is_its_own_volume_over_its_own_area():
    out = _summary([{"parcel_id": "a", "volume_m3": 100, "area_ha": 1}, {"parcel_id": "b", "volume_m3": 150, "area_ha": 5}])
    assert [p["volume_m3_per_ha"] for p in out["parcels"]] == [100, 30] and out["total_m3"] == 250


def test_given_a_season_without_irrigation_then_the_state_is_empty_with_zero_totals():
    assert _summary([])["empty"] is True and _summary([])["total_m3"] == 0
    assert _summary([{"parcel_id": "a", "volume_m3": 0, "area_ha": 2}])["empty"] is True


@pytest.mark.parametrize("area", [None, 0])
def test_given_a_missing_or_zero_area_then_the_ratio_is_null_never_infinite(area):
    p = _summary([{"parcel_id": "a", "volume_m3": 50, "area_ha": area}])["parcels"][0]
    assert p["volume_m3_per_ha"] is None and p["volume_m3"] == 50


def test_given_the_api_aggregate_then_it_uses_the_shared_rule_and_not_a_private_division():
    import inspect

    from app.irrigation import consumption

    assert "summarise_consumption" in inspect.getsource(consumption)
