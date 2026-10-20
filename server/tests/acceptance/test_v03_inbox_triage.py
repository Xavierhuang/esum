"""v0.3 inbox triage: the summary comes first, then one reply draft at a time that the owner can send,
edit and send, skip (the task carries on), or deny (the task stops)."""
import json

from sqlalchemy import select

from opa.db.models import Action, Approval, AuditLog
from tests.helpers import (action_of, call, connect, decide, pending_approval, script, send_call, sent_messages, task_state,
                           tool_results, when)

TRIAGE_QUERY = "in:inbox is:unread category:primary newer_than:1d"


def reply(conn_id: str, to: str, subject: str, body: str, message_id: str) -> dict:
    return send_call(conn_id, to=[to], subject=subject, body=body, in_reply_to_message_id=message_id)


def triage_script(conn_id: str) -> dict:
    return script(
        {"tool_calls": [{"name": "skill__load", "input": {"name": "inbox-triage"}}]},
        {"tool_calls": [call("gmail.search_messages", conn_id, query=TRIAGE_QUERY, max_results=25, page_token=None)]},
        {"tool_calls": [call("gmail.get_message", conn_id, message_id=m) for m in ("m021", "m022", "m023")]},
        {"tool_calls": [{"name": "post_update", "input": {"text": "Your inbox: 3 need a reply, 1 FYI. Drafts below."}}]},
        {"tool_calls": [reply(conn_id, "lena@acme-client.example", "Re: Call on Friday", "Monday at 3pm works. Talk then!", "m021")]},
        {"tool_calls": [reply(conn_id, "jordan@friend.example", "Re: Coffee next week?", "Wednesday works, see you then!", "m023")]},
        {"text": "Sent your reply to Lena; skipped Jordan."},
    )


async def _messages(client, conv: str) -> list[dict]:
    r = await client.get(f"/api/conversations/{conv}/messages")
    assert r.status_code == 200, r.text
    return r.json()


async def test_demo_inbox_supports_the_triage_query(client, make_worker, sessionmaker):
    conn = await connect(client)
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Go through my inbox", "r1")
    w = make_worker(script({"tool_calls": [call("gmail.search_messages", conn["id"], query=TRIAGE_QUERY, max_results=25, page_token=None)]}, {"text": "done"}))
    assert await w.run_once()
    data = json.loads((await tool_results(sessionmaker, sub["task_id"]))[0]["content"])["data"]
    # Unread primary mail from the last day, newest first; promotions, updates, read and old mail are left out,
    # and the sign-in code is withheld.
    assert [m["id"] for m in data["messages"]] == ["m021", "m024", "m022", "m023"]
    assert data["filtered_count"] == 1
    assert all("UNREAD" in m["labels"] for m in data["messages"])


async def test_demo_inbox_understands_categories_dates_and_negation(client, make_worker, sessionmaker):
    conn = await connect(client)
    conv = await client.default_conversation()
    queries = ["category:promotions", "is:unread -category:primary newer_than:1d", "to:lena older_than:2d", "after:2026/09/26 from:marcus"]
    sub = await client.submit(conv, "search", "r1")
    w = make_worker(script({"tool_calls": [call("gmail.search_messages", conn["id"], query=q, max_results=25, page_token=None) for q in queries]},
                           {"text": "done"}))
    assert await w.run_once()
    ids = [[m["id"] for m in json.loads(r["content"])["data"]["messages"]] for r in await tool_results(sessionmaker, sub["task_id"])]
    assert ids == [["m026"], ["m026", "m025", "m027"], ["m020"], ["m022"]]


async def test_triage_posts_the_summary_then_edit_send_and_skip(client, make_worker, sessionmaker, clock):
    conn = await connect(client, gmail="read_write")
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Go through my inbox and draft replies", "r1")
    task_id = sub["task_id"]
    w = make_worker(triage_script(conn["id"]))
    assert await w.run_once()

    # The summary is in the chat before the first draft is decided, and nothing has been sent.
    assert (await task_state(client, task_id))["state"] == "waiting_approval"
    assistant = [m["content"] for m in await _messages(client, conv) if m["role"] == "assistant"]
    assert assistant == ["Your inbox: 3 need a reply, 1 FYI. Drafts below."]
    assert await sent_messages(sessionmaker, clock, conn["id"]) == []

    # Edit the first draft and send the edited version.
    first = await pending_approval(client)
    fields = {f["label"]: f["value"] for f in first["preview"]["fields"]}
    assert fields["To"] == "lena@acme-client.example" and fields["Subject"] == "Re: Call on Friday"
    r = await client.post(f"/api/approvals/{first['id']}/decision", json={
        "decision": "edit_and_allow", "expected_args_hash": first["args_hash"], "edits": {"body": "Tuesday at 2pm works better for me. Talk then!"}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["outcome"] == "approved" and out["approval"]["id"] != first["id"]
    assert out["approval"]["preview"]["edited_by_owner"] is True
    assert (await task_state(client, task_id))["state"] == "queued"
    assert await w.run_once()

    sent = await sent_messages(sessionmaker, clock, conn["id"])
    assert [(m["to"], m["subject"], m["body"]) for m in sent] == [("lena@acme-client.example", "Re: Call on Friday", "Tuesday at 2pm works better for me. Talk then!")]
    async with sessionmaker() as db:
        original = await db.get(Action, first["action_id"])
        assert (original.state, original.resolution) == ("cancelled", "edited_by_owner")
        assert original.canonical_args["body"] == "Monday at 3pm works. Talk then!"  # what the assistant proposed is kept as proposed
        assert (await db.get(Approval, first["id"])).state == "invalidated"
        audit = (await db.scalars(select(AuditLog).where(AuditLog.type == "approval.edited"))).one()
        assert audit.sanitized["replaces"] == original.id and audit.sanitized["fields"] == ["body"]
    results = await tool_results(sessionmaker, task_id)
    assert "the owner edited this" in json.loads(results[-1]["content"])["data"]["note"]

    # Skip the second draft: nothing is sent and the task finishes instead of blocking.
    second = await pending_approval(client)
    assert {f["label"]: f["value"] for f in second["preview"]["fields"]}["To"] == "jordan@friend.example"
    r = await decide(client, second, "skip")
    assert r.status_code == 200 and r.json()["outcome"] == "skipped"
    assert (await task_state(client, task_id))["state"] == "queued"
    assert await w.run_once()
    t = await task_state(client, task_id)
    assert t["state"] == "succeeded", t
    assert len(await sent_messages(sessionmaker, clock, conn["id"])) == 1
    skipped = json.loads((await tool_results(sessionmaker, task_id))[-1]["content"])
    assert skipped["error"]["code"] == "skipped_by_owner"
    assert (await action_of(sessionmaker, task_id)).resolution == "skipped"


async def _waiting_send(client, make_worker, conn, **over):
    conv = await client.default_conversation()
    sub = await client.submit(conv, "Email Priya", "r1")
    w = make_worker(script({"tool_calls": [send_call(conn["id"], **over)]}, {"text": "Done."}))
    assert await w.run_once()
    return sub["task_id"], w, await pending_approval(client)


async def test_edit_needs_the_reviewed_version_and_valid_fields(client, make_worker, sessionmaker, clock):
    conn = await connect(client, gmail="read_write")
    task_id, w, ap = await _waiting_send(client, make_worker, conn)
    edit = lambda edits, h=None: client.post(f"/api/approvals/{ap['id']}/decision",  # noqa: E731
                                             json={"decision": "edit_and_allow", "expected_args_hash": h or ap["args_hash"], "edits": edits})
    assert (await edit({"body": "x"}, h="0" * 64)).status_code == 409
    r = await edit({"subject": "two\nlines"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    assert (await edit({"body": "x" * 100_001})).status_code == 422
    assert (await pending_approval(client))["id"] == ap["id"]  # rejected edits change nothing

    # An edit that changes nothing approves what was shown, with no replacement.
    r = await edit({"subject": ap["preview"]["payload"]["subject"]})
    assert r.json()["outcome"] == "approved" and r.json()["approval"]["id"] == ap["id"]
    assert await w.run_once()
    assert [m["subject"] for m in await sent_messages(sessionmaker, clock, conn["id"])] == ["Metrics for Thursday"]


async def test_tampering_with_an_edited_email_after_approval_is_rejected(client, make_worker, sessionmaker, clock):
    from sqlalchemy import text

    conn = await connect(client, gmail="read_write")
    task_id, w, ap = await _waiting_send(client, make_worker, conn)
    r = await client.post(f"/api/approvals/{ap['id']}/decision", json={"decision": "edit_and_allow", "expected_args_hash": ap["args_hash"], "edits": {"body": "edited"}})
    edited = r.json()["approval"]
    async with sessionmaker() as db, db.begin():
        await db.execute(text("""UPDATE actions SET canonical_args = jsonb_set(canonical_args, '{to}', '["attacker@evil.example"]') WHERE id = :a"""),
                         {"a": edited["action_id"]})
    assert await w.run_once()
    assert await sent_messages(sessionmaker, clock, conn["id"]) == []
    assert (await action_of(sessionmaker, task_id)).state == "cancelled"


async def test_only_email_can_be_edited(client, make_worker):
    conn = await connect(client, calendar="read_write")
    conv = await client.default_conversation()
    await client.submit(conv, "Add an event", "r1")
    w = make_worker(script({"tool_calls": [call("calendar.create_event", conn["id"], calendar_id="primary", summary="Focus", description=None, location=None,
                                                start=when("2026-10-01T09:00:00"), end=when("2026-10-01T10:00:00"), confirm_past=False)]}, {"text": "ok"}))
    assert await w.run_once()
    ap = await pending_approval(client)
    r = await client.post(f"/api/approvals/{ap['id']}/decision", json={"decision": "edit_and_allow", "expected_args_hash": ap["args_hash"], "edits": {"body": "x"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_editable"


async def test_deny_still_stops_the_task(client, make_worker):
    conn = await connect(client, gmail="read_write")
    task_id, _, ap = await _waiting_send(client, make_worker, conn)
    assert (await decide(client, ap, "deny")).json()["outcome"] == "denied"
    t = await task_state(client, task_id)
    assert t["state"] == "blocked" and t["blocker_code"] == "approval_denied"


async def test_post_update_needs_text(client, make_worker, sessionmaker):
    conv = await client.default_conversation()
    sub = await client.submit(conv, "progress", "r1")
    w = make_worker(script({"tool_calls": [{"name": "post_update", "input": {"text": "  "}}]}, {"text": "done"}))
    assert await w.run_once()
    res = json.loads((await tool_results(sessionmaker, sub["task_id"]))[0]["content"])
    assert res["error"]["code"] == "invalid_input"
    assert [m["role"] for m in await _messages(client, conv)] == ["user", "assistant"]
