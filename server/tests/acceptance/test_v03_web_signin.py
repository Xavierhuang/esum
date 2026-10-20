"""Saved website sign-ins: the owner signs in once in the live browser; the assistant can use that sign-in only
after approval, one task at a time, and never sees the cookie."""
import json
import tempfile

import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select, text

from opa.api.app import create_app
from opa.broker.vault import generate_kek
from opa.browser import ops
from opa.browser.app import create_browser_app
from opa.browser.client import BrowserClient
from opa.core.settings import Settings
from opa.db.models import AuditLog, Task
from opa.worker.loop import Worker
from opa.worker.model import ScriptedAdapter
from tests.browser_fixtures import SESSION_SECRET, browser_service, private_server, site, web_proxy  # noqa: F401  (fixtures)
from tests.conftest import Client
from tests.helpers import decide, pending_approval, script, task_state, tool_results


@pytest.fixture
def settings(pg_url: str) -> Settings:
    return Settings(database_url=pg_url, mode="demo", model_provider="scripted", lease_seconds=60, heartbeat_seconds=10,
                    artifact_dir=tempfile.mkdtemp(), internal_token="test-internal-token", tool_timeout_seconds=5, broker_kek=generate_kek())


@pytest_asyncio.fixture
async def browser_client(browser_service, settings):  # noqa: F811
    bc = BrowserClient("http://browser", settings.internal_token, transport=ASGITransport(app=create_browser_app(browser_service, settings.internal_token)))
    yield bc
    await bc.aclose()


@pytest.fixture
def app(settings, clock, sessionmaker, broker_client, browser_client):
    return create_app(settings=settings, clock=clock, sessionmaker=sessionmaker, broker=broker_client, browser=browser_client)


@pytest.fixture
def make_worker(settings, sessionmaker, clock, broker_client, browser_client):
    return lambda s=None, name=None: Worker(settings, sessionmaker, ScriptedAdapter(s), clock=clock, name=name, broker=broker_client, browser=browser_client)


def nav(url):
    return {"name": "browser__navigate", "input": {"url": url, "tab_id": None}}


async def sign_in_and_save(client, base, name="Personal account", page: str | None = "/login"):
    """The owner opens their own browser, signs in on the site, and saves the sign-in."""
    opened = (await client.post("/api/browser-sessions")).json()
    assert opened["control"] == "user" and opened["task_id"] is None
    if page:
        assert (await client.post(f"/api/browser-sessions/{opened['id']}/input", json={"type": "navigate", "url": f"{base}{page}"})).status_code == 200
    return opened, await client.post(f"/api/browser-sessions/{opened['id']}/save-signin", json={"name": name})


async def run_task(client, make_worker, steps, intent="check my account", rid="r1"):
    conv = await client.default_conversation()
    sub = await client.submit(conv, intent, rid)
    w = make_worker(script(*steps))
    assert await w.run_once()
    return sub["task_id"], w, conv


async def page_texts(sm, task_id):
    return [json.loads(r["content"])["data"]["content"]["text"] for r in await tool_results(sm, task_id)]


async def test_the_owner_saves_a_sign_in_and_only_the_name_comes_back(client, sessionmaker, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    _, r = await sign_in_and_save(client, base, "Personal account")
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["host"] == "site.test" and saved["label"] == "Personal account" and SESSION_SECRET not in r.text
    listing = await client.get("/api/web-signins")
    assert [s["id"] for s in listing.json()] == [saved["id"]] and SESSION_SECRET not in listing.text

    async with sessionmaker() as db:
        rows = (await db.execute(text("SELECT dek_wrapped, secret_enc FROM broker.web_signins"))).all()
    assert len(rows) == 1 and all(SESSION_SECRET.encode() not in bytes(col) for col in rows[0])  # sealed, not stored in the clear

    _, again = await sign_in_and_save(client, base, "Renamed account")  # saving the same site again replaces it
    assert again.json()["id"] == saved["id"] and [s["label"] for s in (await client.get("/api/web-signins")).json()] == ["Renamed account"]


async def test_nothing_to_save_without_a_signed_in_page(client, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    _, blank = await sign_in_and_save(client, base, page=None)
    assert blank.status_code == 409 and blank.json()["error"]["code"] == "invalid_input"  # no website open
    _, signed_out = await sign_in_and_save(client, base, page="/page2")  # a page that set no cookie
    assert signed_out.status_code == 422 and "sign in on the page first" in signed_out.json()["error"]["message"]
    assert (await client.get("/api/web-signins")).json() == []


async def test_without_a_saved_sign_in_the_assistant_browses_signed_out(client, make_worker, sessionmaker, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    task_id, _, _ = await run_task(client, make_worker, [{"tool_calls": [nav(f"{base}/account")]}, {"text": "Done."}])
    assert (await task_state(client, task_id))["state"] == "succeeded"
    assert await page_texts(sessionmaker, task_id) == ["Please sign in to see your account"]
    assert not any(SESSION_SECRET in c for c in site.cookies)


async def test_a_saved_sign_in_needs_approval_then_opens_signed_in_without_exposing_the_cookie(client, make_worker, sessionmaker, site, browser_service):  # noqa: F811
    base = f"http://site.test:{site.port}"
    await sign_in_and_save(client, base, "Personal account")
    site.hits.clear()
    site.cookies.clear()
    task_id, w, _ = await run_task(client, make_worker, [{"tool_calls": [nav(f"{base}/account")]}, {"tool_calls": [nav(f"{base}/account")]}, {"text": "Done."}])

    assert (await task_state(client, task_id))["state"] == "waiting_approval"
    assert site.hits == []  # nothing was opened before the owner decided
    ap = await pending_approval(client)
    fields = {f["label"]: f["value"] for f in ap["preview"]["fields"]}
    assert ap["preview"]["title"] == "Use your saved sign-in" and ap["account"] == "Web browser"
    assert fields["Signed in as"] == "Personal account (site.test)" and fields["Full address"] == f"{base}/account"
    assert SESSION_SECRET not in json.dumps(ap)

    await decide(client, ap)
    assert await w.run_once()
    assert (await task_state(client, task_id))["state"] == "succeeded"  # the second visit needed no new approval
    assert await page_texts(sessionmaker, task_id) == ["Signed in as owner@example.com"] * 2
    assert [SESSION_SECRET in c for c in site.cookies] == [True, True]

    async with sessionmaker() as db:
        checkpoint = json.dumps((await db.get(Task, task_id)).checkpoint)
        audit = list(await db.scalars(select(AuditLog).where(AuditLog.type.like("web_signin.%"))))
    assert SESSION_SECRET not in checkpoint  # the model's whole conversation never contained the cookie
    assert "web_signin.used" in {a.type for a in audit} and all(SESSION_SECRET not in json.dumps(a.sanitized) for a in audit)
    assert (await client.get("/api/web-signins")).json()[0]["last_used_at"] is not None
    assert [s.signed_in for s in browser_service.sessions.values() if s.task_id == task_id] == [{"site.test": "Personal account"}]


async def test_denying_the_sign_in_opens_nothing(client, make_worker, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    await sign_in_and_save(client, base)
    site.hits.clear()
    site.cookies.clear()
    task_id, w, _ = await run_task(client, make_worker, [{"tool_calls": [nav(f"{base}/account")]}, {"text": "ok"}])
    await decide(client, await pending_approval(client), "deny")
    await client.post(f"/api/tasks/{task_id}/resume")
    assert await w.run_once()
    assert site.hits == [] and not any(SESSION_SECRET in c for c in site.cookies)


async def test_deleting_a_sign_in_takes_it_away(client, make_worker, sessionmaker, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    _, r = await sign_in_and_save(client, base)
    assert (await client.delete(f"/api/web-signins/{r.json()['id']}")).status_code == 204
    assert (await client.get("/api/web-signins")).json() == []
    assert (await client.delete(f"/api/web-signins/{r.json()['id']}")).status_code == 404
    task_id, _, _ = await run_task(client, make_worker, [{"tool_calls": [nav(f"{base}/account")]}, {"text": "Done."}])
    assert (await task_state(client, task_id))["state"] == "succeeded"  # no approval was needed: there is nothing to use
    assert await page_texts(sessionmaker, task_id) == ["Please sign in to see your account"]


async def test_another_owner_cannot_see_or_remove_a_sign_in(client, app, other_owner, site):  # noqa: F811
    base = f"http://site.test:{site.port}"
    _, r = await sign_in_and_save(client, base)
    async with Client(transport=ASGITransport(app=app), base_url="http://test") as other:
        await other.sign_in("other@example.com", "another long password")
        assert (await other.get("/api/web-signins")).json() == []
        assert (await other.delete(f"/api/web-signins/{r.json()['id']}")).status_code == 404
    assert len((await client.get("/api/web-signins")).json()) == 1


async def test_taking_control_and_handing_back_needs_a_new_approval(client, make_worker, site, browser_service):  # noqa: F811
    base = f"http://site.test:{site.port}"
    await sign_in_and_save(client, base)
    task_id, w, conv = await run_task(client, make_worker, [
        {"tool_calls": [nav(f"{base}/account")]},
        {"tool_calls": [{"name": "ask_user", "input": {"question": "Anything else?"}}]},
        {"tool_calls": [nav(f"{base}/account")]},
        {"text": "Done."}])
    await decide(client, await pending_approval(client))
    assert await w.run_once()
    assert (await task_state(client, task_id))["state"] == "waiting_user"
    session = next(s for s in (await client.get("/api/browser-sessions")).json() if s["task_id"] == task_id)
    assert (await client.post(f"/api/browser-sessions/{session['id']}/takeover")).status_code == 200
    assert (await client.post(f"/api/browser-sessions/{session['id']}/resume")).status_code == 200
    assert browser_service.sessions[session["id"]].signed_in == {} and await browser_service.sessions[session["id"]].context.cookies() == []

    await client.submit(conv, "no", "r2", task_id=task_id)
    assert await w.run_once()
    assert (await task_state(client, task_id))["state"] == "waiting_approval"  # signed out again, so it must ask again
    assert (await pending_approval(client))["preview"]["title"] == "Use your saved sign-in"


def test_a_sign_in_covers_its_own_site_only():
    assert ops.signin_host("https://www.Example.com/path") == "example.com"
    assert ops.signin_applies("example.com", "https://app.example.com/x") and ops.signin_applies("example.com", "https://www.example.com")
    assert not ops.signin_applies("example.com", "https://notexample.com") and not ops.signin_applies("example.com", "https://example.com.evil.test")
    assert ops.cookie_in_scope(".example.com", "example.com") and ops.cookie_in_scope("app.example.com", "example.com")
    assert not ops.cookie_in_scope("evil.test", "example.com") and not ops.cookie_in_scope(".com", "example.com")
