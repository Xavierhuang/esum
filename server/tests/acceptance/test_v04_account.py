"""Account basics for a server with open sign-up: assistant settings, changing the password, and closing the account."""
from httpx import ASGITransport
from sqlalchemy import func, select

from opa.db.models import AuditLog, Conversation, Owner, Session
from tests.conftest import Client

OLD = "correct horse battery"
NEW = "a brand new long password"


async def test_assistant_name_style_and_time_zone_are_saved(client):
    r = await client.patch("/api/me", json={"assistant_name": "Juniper", "response_style": "detailed", "time_zone": "Europe/Paris"})
    assert r.status_code == 200, r.text
    me = (await client.get("/api/me")).json()
    assert (me["assistant_name"], me["response_style"], me["time_zone"]) == ("Juniper", "detailed", "Europe/Paris")
    assert (await client.patch("/api/me", json={"time_zone": "Mars/Olympus"})).status_code == 422


async def test_changing_the_password_needs_the_current_one_and_signs_out_other_sessions(client, app):
    async with Client(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.sign_in()
        assert (await other.get("/api/me")).status_code == 200

        bad = await client.post("/api/me/password", json={"current_password": "wrong password!!", "new_password": NEW})
        assert bad.status_code == 403
        short = await client.post("/api/me/password", json={"current_password": OLD, "new_password": "short"})
        assert short.status_code == 422
        ok = await client.post("/api/me/password", json={"current_password": OLD, "new_password": NEW})
        assert ok.status_code == 204, ok.text

        assert (await client.get("/api/me")).status_code == 200  # this session stays signed in
        assert (await other.get("/api/me")).status_code == 401  # every other session is signed out

    async with Client(transport=ASGITransport(app=app), base_url="http://test") as again:
        assert (await again.post("/api/auth/login", json={"email": "owner@example.com", "password": OLD})).status_code == 401
        await again.sign_in(password=NEW)


async def test_deleting_the_account_removes_the_owner_and_everything_it_owned(client, owner, sessionmaker):
    await client.post("/api/conversations", json={"title": "goodbye"})
    wrong = await client.post("/api/me/delete-account", json={"confirm": "someone@else.com", "password": OLD})
    assert wrong.status_code == 422
    bad_pw = await client.post("/api/me/delete-account", json={"confirm": "owner@example.com", "password": "not my password"})
    assert bad_pw.status_code == 403

    r = await client.post("/api/me/delete-account", json={"confirm": "OWNER@example.com", "password": OLD})
    assert r.status_code == 204, r.text
    assert (await client.get("/api/me")).status_code == 401

    async with sessionmaker() as db:
        assert await db.get(Owner, owner.id) is None
        for model in (Conversation, Session, AuditLog):
            n = await db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner.id))
            assert n == 0, model.__tablename__


async def test_a_deleted_account_cannot_sign_in(client, app):
    assert (await client.post("/api/me/delete-account", json={"confirm": "owner@example.com", "password": OLD})).status_code == 204
    async with Client(transport=ASGITransport(app=app), base_url="http://test") as again:
        assert (await again.post("/api/auth/login", json={"email": "owner@example.com", "password": OLD})).status_code == 401
