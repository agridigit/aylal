"""T075 - the year comparison response is a documented schema: both curves capped at 200 points, each point carrying its day of campaign."""
import datetime as dt

from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, seed_season_at, seed_vigor_points, world3  # noqa: F401

PATH = "/farms/{farm_id}/parcels/{parcel_id}/vigor/compare"
POINT = {"day_of_campaign", "acquired_on", "vigor", "plant_moisture"}


def _schema():
    return SPEC["components"]["schemas"].get("YearCompare")


def test_given_the_contract_then_the_comparison_names_both_curves_with_at_most_200_points_each():
    s = _schema()
    assert s is not None, "components.schemas.YearCompare is missing"
    assert set(s["required"]) == {"reference_available", "current", "previous"}
    for k in ("current", "previous"):
        assert s["properties"][k]["maxItems"] == 200
        assert POINT <= set(s["properties"][k]["items"]["properties"])
        assert s["properties"][k]["items"]["properties"]["day_of_campaign"]["type"] == "integer"


def test_given_the_contract_then_the_route_returns_that_schema_and_documents_404():
    responses = SPEC["paths"][PATH]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/YearCompare"}
    assert "404" in responses


def test_given_a_parcel_with_two_campaigns_when_comparing_then_the_body_validates(client, token_for, world3):
    w = world3
    start = dt.date.today() - dt.timedelta(days=100)
    seed_season_at(w["farm_a"], w["p"][8], start)
    seed_vigor_points(w["farm_a"], w["p"][8], [start + dt.timedelta(days=10)])
    seed_vigor_points(w["farm_a"], w["p"][8], [start.replace(year=start.year - 1) + dt.timedelta(days=10)])
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['p'][8]}/vigor/compare")
    assert r.status_code == 200
    assert_valid("YearCompare", r.json())


def test_given_a_parcel_without_reference_when_comparing_then_the_body_still_validates(client, token_for, world3):
    w = world3
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['p'][9]}/vigor/compare")
    assert r.status_code == 200
    assert_valid("YearCompare", r.json())
