"""SqlAccountRepo / SqlInvitationRepo against a real PostgreSQL (stack database, rows created and removed here)."""
import asyncio
import datetime as dt
import os
import uuid

import asyncpg
import pytest

from tasks.expire_invitations import SqlInvitationRepo
from tasks.purge_deleted_accounts import SqlAccountRepo

DSN = os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")
NOW = dt.datetime.now(dt.UTC)


def run(fn):
    async def _go():
        try:
            conn = await asyncpg.connect(DSN, timeout=5)
        except (OSError, asyncpg.PostgresError) as e:  # limit: needs the compose database up
            pytest.skip(f"database unreachable: {e}")
        try:
            return await fn(conn)
        finally:
            await conn.close()

    return asyncio.run(_go())


def _user(phone_tail, **cols):
    uid = uuid.uuid4()
    return uid, dict(id=uid, phone_e164=f"+2129{phone_tail:08d}", **cols)


async def _insert_user(conn, u):
    await conn.execute(
        "INSERT INTO users (id, phone_e164, status, deletion_requested_at, created_at, display_name)"
        " VALUES ($1,$2,$3,$4,$5,$6)",
        u["id"], u["phone_e164"], u.get("status", "active"), u.get("deletion_requested_at"),
        u.get("created_at", NOW), u.get("display_name"),
    )


async def _cleanup(conn, ids, farms=()):
    await conn.execute("DELETE FROM invitations WHERE farm_id = ANY($1)", list(farms))
    await conn.execute("DELETE FROM farm_members WHERE user_id = ANY($1) OR farm_id = ANY($2)", list(ids), list(farms))
    await conn.execute("DELETE FROM farms WHERE id = ANY($1)", list(farms))
    await conn.execute("DELETE FROM refresh_tokens WHERE user_id = ANY($1)", list(ids))
    await conn.execute("DELETE FROM consents WHERE user_id = ANY($1)", list(ids))
    await conn.execute("DELETE FROM users WHERE id = ANY($1)", list(ids))


def test_given_accounts_past_and_inside_the_30_days_when_purging_then_only_the_elapsed_one_and_its_personal_data_go():
    async def scenario(conn):
        old, o = _user(uuid.uuid4().int % 10**7, status="deletion_requested", deletion_requested_at=NOW - dt.timedelta(days=31), display_name="Old")
        recent, r = _user(uuid.uuid4().int % 10**7, status="deletion_requested", deletion_requested_at=NOW - dt.timedelta(days=29), display_name="Recent")
        keeper, k = _user(uuid.uuid4().int % 10**7, display_name="Active")
        farm_solo, farm_shared = uuid.uuid4(), uuid.uuid4()
        ids = [old, recent, keeper]
        try:
            for u in (o, r, k):
                await _insert_user(conn, u)
            for uid in (old, recent):
                await conn.execute("INSERT INTO refresh_tokens (id,user_id,token_hash,family_id) VALUES ($1,$2,$3,$4)", uuid.uuid4(), uid, uuid.uuid4().hex, uuid.uuid4())
                await conn.execute("INSERT INTO consents (id,user_id,purpose,text_version) VALUES ($1,$2,'data_policy','v1')", uuid.uuid4(), uid)
            await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'Solo',$2)", farm_solo, old)
            await conn.execute("INSERT INTO farm_members (farm_id,user_id,role) VALUES ($1,$2,'owner')", farm_solo, old)
            await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'Shared',$2)", farm_shared, keeper)
            await conn.execute("INSERT INTO farm_members (farm_id,user_id,role) VALUES ($1,$2,'owner'),($1,$3,'worker')", farm_shared, keeper, old)

            purged = await SqlAccountRepo(DSN).purge_deleted_accounts(NOW)

            assert purged == 1
            assert await conn.fetchval("SELECT count(*) FROM users WHERE id = $1", old) == 0
            assert await conn.fetchval("SELECT count(*) FROM refresh_tokens WHERE user_id = $1", old) == 0
            assert await conn.fetchval("SELECT count(*) FROM consents WHERE user_id = $1", old) == 0
            assert await conn.fetchval("SELECT count(*) FROM farm_members WHERE user_id = $1", old) == 0
            assert await conn.fetchval("SELECT deleted_at IS NOT NULL FROM farms WHERE id = $1", farm_solo) is True
            assert await conn.fetchval("SELECT deleted_at FROM farms WHERE id = $1", farm_shared) is None
            assert await conn.fetchval("SELECT count(*) FROM farm_members WHERE farm_id = $1 AND user_id = $2", farm_shared, keeper) == 1
            assert await conn.fetchval("SELECT count(*) FROM users WHERE id = ANY($1)", [recent, keeper]) == 2
            assert await conn.fetchval("SELECT count(*) FROM consents WHERE user_id = $1", recent) == 1
        finally:
            await _cleanup(conn, ids, [farm_solo, farm_shared])

    run(scenario)


def test_given_pending_accounts_when_purging_pending_then_only_old_consentless_ones_go():
    async def scenario(conn):
        stale, s = _user(uuid.uuid4().int % 10**7, status="pending", created_at=NOW - dt.timedelta(hours=25))
        fresh, f = _user(uuid.uuid4().int % 10**7, status="pending", created_at=NOW - dt.timedelta(hours=1))
        consented, c = _user(uuid.uuid4().int % 10**7, status="pending", created_at=NOW - dt.timedelta(hours=25))
        ids = [stale, fresh, consented]
        try:
            for u in (s, f, c):
                await _insert_user(conn, u)
            await conn.execute("INSERT INTO consents (id,user_id,purpose,text_version) VALUES ($1,$2,'data_policy','v1')", uuid.uuid4(), consented)
            assert await SqlAccountRepo(DSN).purge_pending_accounts(NOW) >= 1
            left = {r[0] for r in await conn.fetch("SELECT id FROM users WHERE id = ANY($1)", ids)}
            assert left == {fresh, consented}
        finally:
            await _cleanup(conn, ids)

    run(scenario)


def test_given_invitations_past_and_inside_their_expiry_when_expiring_then_only_past_pending_ones_become_expired():
    async def scenario(conn):
        owner, o = _user(uuid.uuid4().int % 10**7)
        farm = uuid.uuid4()
        try:
            await _insert_user(conn, o)
            await conn.execute("INSERT INTO farms (id,name,owner_id) VALUES ($1,'F',$2)", farm, owner)
            rows = {}
            for tail, status, delta in ((1, "pending", -1), (2, "pending", 5), (3, "accepted", -1)):
                iid = uuid.uuid4()
                rows[iid] = status
                await conn.execute(
                    "INSERT INTO invitations (id,farm_id,phone_e164,role,status,invited_by,expires_at) VALUES ($1,$2,$3,'worker',$4,$5,$6)",
                    iid, farm, f"+21270000000{tail}", status, owner, NOW + dt.timedelta(days=delta),
                )
            assert await SqlInvitationRepo(DSN).expire_invitations(NOW) >= 1
            got = [r[0] for r in await conn.fetch("SELECT status FROM invitations WHERE farm_id=$1 ORDER BY phone_e164", farm)]
            assert got == ["expired", "pending", "accepted"]
        finally:
            await _cleanup(conn, [owner], [farm])

    run(scenario)
