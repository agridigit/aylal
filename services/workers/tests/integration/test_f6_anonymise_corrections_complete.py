"""Review finding 1: no operation_corrections row may keep the text of a deleted account (note / operator_name)."""
import contextlib
import datetime as dt
import uuid

from tests.integration.test_f6_anonymise_account_data import _register
from tests.integration.test_sql_account_repo import _cleanup, _insert_user, _user, run

TODAY = dt.date.today()
GONE_TEXT = "texte ecrit par Gone 0612345678"
GONE_NAME = "Ahmed Gone 0612345678"


async def _op(conn, w, oid, author, operator, name, note):
    await conn.execute(
        "INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, operator_user_id, operator_name, note,"
        " free_product_name, dose, dose_unit) VALUES ($1,$2,'phyto',$3,'validated',$4,$5,$6,$7,'Prod X',2,'L/ha')",
        oid, w["farm"], TODAY, author, operator, name, note)


async def _corr(conn, w, oid, author, field, before, after):
    cid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO operation_corrections (id, farm_id, operation_id, field, before, after, author_id, source)"
        " VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,'manual')", cid, w["farm"], oid, field, before, after, author)
    return cid


async def _world(conn):
    gone, g = _user(uuid.uuid4().int % 10**7, display_name="Gone")
    keeper, k = _user(uuid.uuid4().int % 10**7, display_name="Keeper")
    w = dict(gone=gone, keeper=keeper, farm=uuid.uuid4(), parcel=uuid.uuid4(), **{n: uuid.uuid4() for n in ("op_a1", "op_a2", "op_b", "op_k")})
    await _insert_user(conn, g)
    await _insert_user(conn, k)
    await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'F',$2)", w["farm"], keeper)
    await conn.execute("INSERT INTO farm_members (farm_id,user_id,role) VALUES ($1,$2,'owner'),($1,$3,'manager')", w["farm"], keeper, gone)
    await conn.execute("INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1,$2,'P1',"
        "ST_SetSRID(ST_GeomFromText('POLYGON((-7.5 33.5,-7.49 33.5,-7.49 33.51,-7.5 33.51,-7.5 33.5))'),4326),0.5)", w["parcel"], w["farm"])
    # a1: authored by the deleted account, its note then corrected by somebody else
    await _op(conn, w, w["op_a1"], gone, keeper, "Karim", "note de Gone")
    w["a1_note"] = await _corr(conn, w, w["op_a1"], keeper, "note", '"note de Gone"', '"reecrit par Keeper"')
    w["a1_dose"] = await _corr(conn, w, w["op_a1"], keeper, "dose", "2", "3")
    # a2: authored by keeper; keeper corrects, then Gone corrects, then keeper corrects again (before holds Gone's text)
    await _op(conn, w, w["op_a2"], keeper, keeper, "Karim", "note finale")
    w["a2_before_gone"] = await _corr(conn, w, w["op_a2"], keeper, "note", '"origine Keeper"', '"v2 Keeper"')
    w["a2_gone"] = await _corr(conn, w, w["op_a2"], gone, "note", '"v2 Keeper"', f'"{GONE_TEXT}"')
    w["a2_after_gone"] = await _corr(conn, w, w["op_a2"], keeper, "note", f'"{GONE_TEXT}"', '"note finale"')
    # b: Gone WAS the operator (history of the registry), then somebody else became the current operator
    await _op(conn, w, w["op_b"], keeper, keeper, "Karim", "n")
    for kind, operator, name in (("application", gone, GONE_NAME), ("reversal", gone, GONE_NAME), ("application", keeper, "Karim")):
        names, marks, vals, _ = _register(conn, w["farm"], w["op_b"], w["parcel"], entry_kind=kind, operator_user_id=operator,
                                          operator_name=name, recorded_by=keeper)
        await conn.execute(f"INSERT INTO registry_entries ({names}) VALUES ({marks})", *vals)
    w["b_name"] = await _corr(conn, w, w["op_b"], keeper, "operator_name", f'"{GONE_NAME}"', '"Karim"')
    # k: nothing to do with Gone
    await _op(conn, w, w["op_k"], keeper, keeper, "Karim", "k")
    w["k_note"] = await _corr(conn, w, w["op_k"], keeper, "note", '"avant"', '"apres"')
    w["k_name"] = await _corr(conn, w, w["op_k"], keeper, "operator_name", '"Karim"', '"Karim K"')
    return w


async def _teardown(conn, w):
    with contextlib.suppress(Exception):
        await conn.execute("SELECT set_config('aylal.registry_maintenance','on',false)")
        await conn.execute("DELETE FROM farm_members WHERE farm_id=$1", w["farm"])
        await conn.execute("DELETE FROM farms WHERE id=$1", w["farm"])
        await _cleanup(conn, [w["gone"], w["keeper"]])


def _scenario(check):
    async def go(conn):
        w = await _world(conn)
        try:
            await conn.fetch("SELECT anonymize_registry_operator($1::uuid)", w["gone"])
            await check(conn, w)
        finally:
            await _teardown(conn, w)

    run(go)


async def _row(conn, cid):
    return await conn.fetchrow("SELECT author_id, before::text AS b, after::text AS a FROM operation_corrections WHERE id=$1", cid)


def test_given_a_note_correction_by_another_user_on_an_operation_authored_by_the_deleted_account_when_anonymising_then_it_is_erased():
    async def check(conn, w):
        r = await _row(conn, w["a1_note"])
        assert r["b"] is None and r["a"] is None and r["author_id"] == w["keeper"]
        d = await _row(conn, w["a1_dose"])
        assert (d["b"], d["a"]) == ("2", "3")

    _scenario(check)


def test_given_a_note_correction_following_one_written_by_the_deleted_account_when_anonymising_then_the_one_carrying_its_text_is_erased():
    async def check(conn, w):
        after = await _row(conn, w["a2_after_gone"])
        assert after["b"] is None and after["a"] is None and after["author_id"] == w["keeper"]
        gone = await _row(conn, w["a2_gone"])
        assert gone["b"] is None and gone["a"] is None and gone["author_id"] is None
        # the correction written by the other person BEFORE the deleted account's one carries none of its text
        kept = await _row(conn, w["a2_before_gone"])
        assert (kept["b"], kept["a"]) == ('"origine Keeper"', '"v2 Keeper"')

    _scenario(check)


def test_given_operator_name_corrections_on_an_operation_the_deleted_account_once_operated_when_anonymising_then_they_are_erased():
    async def check(conn, w):
        r = await _row(conn, w["b_name"])
        assert r["b"] is None and r["a"] is None and r["author_id"] == w["keeper"]
        cur = await conn.fetchrow("SELECT operator_user_id, operator_name FROM operations WHERE id=$1", w["op_b"])
        assert cur["operator_user_id"] == w["keeper"] and cur["operator_name"] == "Karim"

    _scenario(check)


def test_given_corrections_of_other_people_on_unrelated_operations_when_anonymising_then_they_are_unchanged():
    async def check(conn, w):
        n = await _row(conn, w["k_note"])
        o = await _row(conn, w["k_name"])
        assert (n["b"], n["a"], n["author_id"]) == ('"avant"', '"apres"', w["keeper"])
        assert (o["b"], o["a"], o["author_id"]) == ('"Karim"', '"Karim K"', w["keeper"])

    _scenario(check)
