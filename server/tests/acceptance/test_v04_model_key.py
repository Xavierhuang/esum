"""Bring your own key: the owner pastes an API key for Anthropic, ZenMux or another Anthropic-compatible gateway.
It is checked once, sealed in the broker's vault, never shown again in full, and used for the owner's tasks."""
import json
import tempfile

import httpx2 as httpx  # the Anthropic SDK's own HTTP library
import pytest
from sqlalchemy import select

from opa.broker.service import Broker
from opa.broker.vault import generate_kek
from opa.core.settings import Settings
from opa.db.models import BrokerModelKey
from opa.worker.loop import Worker
from opa.worker.model import OwnerKeyAdapter

GOOD_KEY = "sk-good-key-0000-1234"
MODELS = {"claude-opus-5-5", "anthropic/claude-sonnet-4.5"}


class FakeProvider:
    """Speaks the Anthropic Messages API, like Anthropic itself and gateways such as ZenMux."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.reply = "Hello from your own key."

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        if request.headers.get("x-api-key") != GOOD_KEY:
            return httpx.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
        if body["model"] not in MODELS:
            return httpx.Response(404, json={"type": "error", "error": {"type": "not_found_error", "message": f"model: {body['model']}"}})
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "text", "text": self.reply}], "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 3, "output_tokens": 5},
        })


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def settings(pg_url: str) -> Settings:
    return Settings(database_url=pg_url, mode="live", model_provider="anthropic", lease_seconds=60, heartbeat_seconds=10,
                    artifact_dir=tempfile.mkdtemp(), internal_token="test-internal-token", tool_timeout_seconds=5, broker_kek=generate_kek())


@pytest.fixture
def broker(settings, sessionmaker, clock, provider) -> Broker:
    return Broker(settings, sessionmaker, clock, read_retry_base=0, model_transport=httpx.MockTransport(provider))


@pytest.fixture
def make_worker(settings, sessionmaker, clock, broker_client, provider):
    adapter = OwnerKeyAdapter(settings, broker_client, None, transport=httpx.MockTransport(provider))
    return lambda: Worker(settings, sessionmaker, adapter, clock=clock, broker=broker_client)


async def save(client, **over):
    body = {"provider": "anthropic", "model": "claude-opus-5-5", "api_key": GOOD_KEY, **over}
    return await client.put("/api/model-key", json=body)


async def test_live_mode_without_a_key_asks_for_one_first(client):
    me = (await client.get("/api/me")).json()
    assert me["needs_model_key"] is True and me["model_key"] is None and me["setup_required"] == []


async def test_a_key_is_checked_then_only_a_hint_ever_comes_back(client, sessionmaker, provider):
    r = await save(client)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["provider"] == "anthropic" and saved["key_hint"] == "…1234" and saved["model"] == "claude-opus-5-5"
    assert GOOD_KEY not in r.text
    assert len(provider.requests) == 1 and provider.requests[0].url.host == "api.anthropic.com"

    me = await client.get("/api/me")
    assert me.json()["needs_model_key"] is False and me.json()["model_key"]["key_hint"] == "…1234" and GOOD_KEY not in me.text
    async with sessionmaker() as db:
        row = await db.scalar(select(BrokerModelKey))
    assert GOOD_KEY.encode() not in row.secret_enc and row.key_hint == "…1234"


async def test_a_rejected_key_or_unknown_model_is_not_saved(client):
    r = await save(client, api_key="sk-wrong")
    assert r.status_code >= 400 and "rejected this key" in r.text
    r = await save(client, model="claude-nonexistent")
    assert r.status_code >= 400 and "claude-nonexistent" in r.text
    assert (await client.get("/api/model-key")).json() is None


async def test_zenmux_uses_its_own_address(client, provider):
    r = await save(client, provider="zenmux", model="anthropic/claude-sonnet-4.5")
    assert r.status_code == 200, r.text
    assert r.json()["base_url"] == "https://zenmux.ai/api/anthropic"
    req = provider.requests[-1]
    assert req.url.host == "zenmux.ai" and req.url.path == "/api/anthropic/v1/messages"


@pytest.mark.parametrize("base_url", ["http://gateway.example.com", "https://127.0.0.1", "https://localhost/api", "https://10.0.0.5/v1"])
async def test_a_custom_address_must_be_public_https(client, base_url, provider):
    r = await save(client, provider="custom", base_url=base_url)
    assert r.status_code >= 400, r.text
    assert provider.requests == []


async def test_removing_the_key_asks_for_one_again(client):
    assert (await save(client)).status_code == 200
    assert (await client.delete("/api/model-key")).status_code == 204
    assert (await client.get("/api/model-key")).json() is None
    assert (await client.get("/api/me")).json()["needs_model_key"] is True


async def test_tasks_run_on_the_owners_own_gateway_key(client, make_worker, provider):
    assert (await save(client, provider="zenmux", model="anthropic/claude-sonnet-4.5")).status_code == 200
    provider.reply = "Done, using ZenMux."
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Say hello", "r1")
    assert await make_worker().run_once()

    task = (await client.get(f"/api/tasks/{sub['task_id']}")).json()
    assert task["state"] == "succeeded", task
    msgs = (await client.get(f"/api/conversations/{conv}/messages")).json()
    assert msgs[-1]["role"] == "assistant" and msgs[-1]["content"] == "Done, using ZenMux."
    call = provider.requests[-1]
    body = json.loads(call.content)
    assert call.url.host == "zenmux.ai" and call.headers["x-api-key"] == GOOD_KEY
    assert "output_config" not in body and "fallbacks" not in body and "anthropic-beta" not in call.headers


async def test_without_a_key_the_task_says_how_to_fix_it(client, make_worker, provider):
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Say hello", "r1")
    assert await make_worker().run_once()
    task = (await client.get(f"/api/tasks/{sub['task_id']}")).json()
    assert task["state"] == "blocked" and "add yours" in (task["blocker_detail"] or "")
    assert provider.requests == []
