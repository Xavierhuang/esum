"""Core tools: ask_user, post_update, and note. Connector tools arrive via the broker in M2.

ask_user and post_update write to the conversation, so the worker runs them itself (see loop.py)."""
from __future__ import annotations

from typing import Any


class LocalTools:
    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "ask_user",
                "description": "Ask the owner a clarifying question and pause until they reply.",
                "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"], "additionalProperties": False},
            },
            {
                "name": "post_update",
                "description": "Post a message to the owner's chat now and keep working, without waiting for a reply. Use it to share a summary "
                               "before proposing changes, or progress on long work. The final answer still goes in your last reply.",
                "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False},
            },
            {
                "name": "note",
                "description": "Record an intermediate finding as a task output. Use before the final answer.",
                "input_schema": {"type": "object", "properties": {"key": {"type": "string"}, "text": {"type": "string"}}, "required": ["key", "text"], "additionalProperties": False},
            },
        ]

    async def execute(self, name: str, args: dict[str, Any], *, owner_id: str, task_id: str) -> dict[str, Any]:
        if name == "note":
            key = str(args.get("key", "")).strip()
            if not key:
                return {"ok": False, "content": "invalid_input: key is required"}
            return {"ok": True, "content": f"noted {key}", "output_key": f"note:{key}", "output_value": str(args.get("text", ""))}
        return {"ok": False, "content": f"unknown tool {name}"}
