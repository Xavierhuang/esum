"""Open sign-up: anyone can create their own private account, when the server allows it."""
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport

from opa.api.app import create_app
from opa.core.settings import Settings
from tests.conftest import Client

PASSWORD = "a long enough password"


@pytest.fixture
def settings(pg_url: str) -> Settings:
    return Settings(database_url=pg_url, mode="demo", model_provider="scripted", artifact_dir=tempfile.mkdtemp(),
                    internal_token="test-internal-token", signup_enabled=True, signup_max_owners=3, signup_per_ip_per_hour=5)


@pytest_asyncio.fixture
async def visitor(app):
    async with Client(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def sign_up(c, email, password=PASSWORD, **extra):
    return await c.post("/api/auth/signup", json={"email": email, "password": password, **extra})


async def test_sign_up_creates_a_signed_in_account_with_its_own_chat(visitor):
    assert (await visitor.get("/api/auth/options")).json() == {"signup": True}
    r = await sign_up(visitor, "  New.Person@Example.com ", time_zone="America/New_York")
    assert r.status_code == 204, r.text
    me = (await visitor.get("/api/me")).json()
    assert me["email"] == "new.person@example.com" and me["time_zone"] == "America/New_York"
    visitor.headers["x-csrf-token"] = me["csrf_token"]
    assert await visitor.default_conversation()

    async with Client(transport=visitor._transport, base_url="http://test") as again:
        await again.sign_in("new.person@example.com", PASSWORD)


async def test_the_same_email_cannot_sign_up_twice(visitor):
    assert (await sign_up(visitor, "dup@example.com")).status_code == 204
    r = await sign_up(visitor, "DUP@example.com")
    assert r.status_code == 409 and "sign in instead" in r.text


@pytest.mark.parametrize("email,password", [("not-an-email", PASSWORD), ("ok@example.com", "short")])
async def test_bad_email_or_short_password_is_refused(visitor, email, password):
    assert (await sign_up(visitor, email, password)).status_code == 422


async def test_accounts_never_see_each_other(app):
    clients = []
    for email in ("a@example.com", "b@example.com"):
        c = Client(transport=ASGITransport(app=app), base_url="http://test")
        assert (await sign_up(c, email)).status_code == 204
        c.headers["x-csrf-token"] = (await c.get("/api/me")).json()["csrf_token"]
        clients.append(c)
    a, b = clients
    secret_chat = (await a.post("/api/conversations", json={"title": "A's private plans"})).json()
    assert all(c["title"] != "A's private plans" for c in (await b.get("/api/conversations")).json())
    assert (await b.get(f"/api/conversations/{secret_chat['id']}/messages")).status_code == 404
    for c in clients:
        await c.aclose()


async def test_the_server_stops_taking_accounts_at_its_limit(visitor):
    for i in range(3):
        assert (await sign_up(visitor, f"user{i}@example.com")).status_code == 204
    r = await sign_up(visitor, "one-too-many@example.com")
    assert r.status_code == 403 and "not taking new accounts" in r.text


async def test_sign_up_attempts_are_limited_per_network(visitor):
    for i in range(5):
        await sign_up(visitor, f"bad{i}", "short")
    r = await sign_up(visitor, "real@example.com")
    assert r.status_code == 429


async def test_sign_up_is_off_unless_the_server_turns_it_on(pg_url, clock, sessionmaker, broker_client):
    s = Settings(database_url=pg_url, mode="demo", model_provider="scripted", artifact_dir=tempfile.mkdtemp(), internal_token="test-internal-token")
    app = create_app(settings=s, clock=clock, sessionmaker=sessionmaker, broker=broker_client)
    async with Client(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/auth/options")).json() == {"signup": False}
        r = await sign_up(c, "someone@example.com")
        assert r.status_code == 403 and "turned off" in r.text
