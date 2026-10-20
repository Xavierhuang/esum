"""The scripted replies `npm run dev` uses in demo mode run end to end against the demo account."""
import json
from pathlib import Path

import yaml

from opa.worker import model
from tests.helpers import connect, pending_approval, sent_messages, task_state, tool_results

DEMO_SCRIPT = yaml.safe_load((Path(model.__file__).parent / "demo_script.yaml").read_text())


async def test_demo_inbox_triage_runs_end_to_end(client, make_worker, sessionmaker, clock):
    conn = await connect(client, gmail="read_write")
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Go through my inbox and draft replies", "r1")
    w = make_worker(DEMO_SCRIPT)
    assert await w.run_once()
    results = await tool_results(sessionmaker, sub["task_id"])
    assert len(results) == 8 and not any(r.get("is_error") for r in results), results  # every scripted call is valid
    msgs = (await client.get(f"/api/conversations/{conv}/messages")).json()
    assert msgs[-1]["content"].startswith("Your inbox: 3 need a reply")

    for to in ("lena@acme-client.example", "jordan@friend.example"):
        ap = await pending_approval(client)
        assert {f["label"]: f["value"] for f in ap["preview"]["fields"]}["To"] == to
        r = await client.post(f"/api/approvals/{ap['id']}/decision", json={"decision": "allow_once", "expected_args_hash": ap["args_hash"]})
        assert r.json()["outcome"] == "approved"
        assert await w.run_once()
    assert (await task_state(client, sub["task_id"]))["state"] == "succeeded"
    assert [m["to"] for m in await sent_messages(sessionmaker, clock, conn["id"])] == ["lena@acme-client.example", "jordan@friend.example"]


async def test_demo_connect_and_notion_and_default(client, make_worker, sessionmaker):
    conv = await client.default_conversation()
    w = make_worker(DEMO_SCRIPT)
    first = await client.submit(conv, "Connect my accounts", "r1")
    assert await w.run_once()
    card = next(m for m in (await client.get(f"/api/conversations/{conv}/messages")).json() if m["connection_request"])
    assert {c["capability"]: c["after"] for c in card["connection_request"]["changes"]}["gmail"] == "read_write"
    assert (await task_state(client, first["task_id"]))["state"] == "succeeded"

    await connect(client)
    notion = await client.submit(conv, "Summarize my Notion meeting notes", "r2")
    assert await w.run_once()
    assert (await task_state(client, notion["task_id"]))["state"] == "succeeded"
    page = json.loads((await tool_results(sessionmaker, notion["task_id"]))[-1]["content"])
    assert page["data"]["content"]["untrusted"] is True

    other = await client.submit(conv, "What is the weather?", "r3")
    assert await w.run_once()
    assert (await task_state(client, other["task_id"]))["state"] == "succeeded"
    assert "demo mode" in (await client.get(f"/api/conversations/{conv}/messages")).json()[-1]["content"]
