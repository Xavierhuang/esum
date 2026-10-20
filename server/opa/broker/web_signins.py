"""Saved website sign-ins (design section 9). The browser cookies for one site, sealed in the vault.

Only the broker can open them. The model never sees them: it learns that "a saved sign-in exists" and,
after the owner approves, the browser holds the cookies for that site for that one task.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select

from opa.browser import ops
from opa.core.ids import new_id
from opa.db.models import AuditLog, BrokerWebSignIn
from opa.sdk.contract import ConnectorError

MAX_STATE_BYTES = 256_000
MAX_COOKIES = 300
COOKIE_KEYS = ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite")


def clean_state(host: str, state: Any) -> dict[str, Any]:
    """Keep only what a sign-in needs: this site's cookies. Refuses anything malformed."""
    if not isinstance(state, dict) or not isinstance(state.get("cookies"), list):
        raise ConnectorError("invalid_input", "the sign-in has no cookies")
    cookies = []
    for c in state["cookies"][:MAX_COOKIES]:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not isinstance(c.get("value"), str) or not isinstance(c.get("domain"), str):
            raise ConnectorError("invalid_input", "a cookie is malformed")
        if not ops.cookie_in_scope(c["domain"], host):
            continue
        cookies.append({k: c[k] for k in COOKIE_KEYS if k in c})
    if not cookies:
        raise ConnectorError("invalid_input", f"there is no sign-in to save for {host}: sign in on the page first")
    out: dict[str, Any] = {"cookies": cookies}
    if len(json.dumps(out)) > MAX_STATE_BYTES:
        raise ConnectorError("invalid_input", "this sign-in is too large to save")
    return out


def _summary(r: BrokerWebSignIn) -> dict[str, Any]:
    return {"id": r.id, "host": r.host, "label": r.label, "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None}


class WebSignIns:
    def __init__(self, broker: Any) -> None:
        self.b = broker

    def _vault(self):
        if self.b.vault is None:
            raise ConnectorError("auth_required", "the broker has no key-encryption key (OPA_BROKER_KEK)")
        return self.b.vault

    @staticmethod
    def _audit(db, owner_id: str, type_: str, host: str, **data: Any) -> None:
        db.add(AuditLog(owner_id=owner_id, actor="broker", type=type_, subject_id=host, sanitized={"host": host, **data}))

    async def save(self, owner_id: str, host: str, label: str, state: Any) -> dict[str, Any]:
        vault = self._vault()
        host = ops.signin_host(host)
        label = " ".join(str(label).split())[:200]
        if "." not in host:
            raise ConnectorError("invalid_input", "this page has no website address to save a sign-in for")
        if not label:
            raise ConnectorError("invalid_input", "a name for this sign-in is required")
        sealed = clean_state(host, state)
        async with self.b.sm() as db, db.begin():
            row = await db.scalar(select(BrokerWebSignIn).where(BrokerWebSignIn.owner_id == owner_id, BrokerWebSignIn.host == host).with_for_update())
            if row is None:
                row = BrokerWebSignIn(id=new_id(), owner_id=owner_id, host=host, label=label, dek_wrapped=b"", secret_enc=b"")
                db.add(row)
            row.label = label
            row.dek_wrapped, row.secret_enc = vault.encrypt(sealed, row.id)
            await db.flush()
            await db.refresh(row)
            self._audit(db, owner_id, "web_signin.saved", host, label=label, cookies=len(sealed["cookies"]))
            return _summary(row)

    async def list_for(self, owner_id: str) -> list[dict[str, Any]]:
        async with self.b.sm() as db:
            rows = await db.scalars(select(BrokerWebSignIn).where(BrokerWebSignIn.owner_id == owner_id).order_by(BrokerWebSignIn.host))
            return [_summary(r) for r in rows]

    async def delete(self, owner_id: str, signin_id: str) -> dict[str, Any]:
        async with self.b.sm() as db, db.begin():
            row = await db.scalar(select(BrokerWebSignIn).where(BrokerWebSignIn.id == signin_id, BrokerWebSignIn.owner_id == owner_id))
            if row is None:
                raise ConnectorError("not_found", "no saved sign-in with that id")
            host = row.host
            await db.delete(row)
            self._audit(db, owner_id, "web_signin.deleted", host)
        return {"deleted": True}

    async def purge(self, owner_id: str) -> dict[str, Any]:
        async with self.b.sm() as db, db.begin():
            n = (await db.execute(delete(BrokerWebSignIn).where(BrokerWebSignIn.owner_id == owner_id))).rowcount
        return {"purged": n}

    async def _match(self, db, owner_id: str, url: str) -> BrokerWebSignIn | None:
        rows = await db.scalars(select(BrokerWebSignIn).where(BrokerWebSignIn.owner_id == owner_id))
        hits = [r for r in rows if ops.signin_applies(r.host, url)]
        return max(hits, key=lambda r: len(r.host), default=None)

    async def lookup(self, task_id: str, lease_token: str, url: str) -> dict[str, Any] | None:
        """Is there a saved sign-in for this address? Answers with its name only."""
        async with self.b.sm() as db:
            ctx = await self.b._task_context(db, task_id, lease_token)
            row = await self._match(db, ctx.owner_id, url)
            return None if row is None else {"host": row.host, "label": row.label}

    async def open(self, task_id: str, lease_token: str, url: str) -> dict[str, Any]:
        """The sealed cookies for this address, for the worker to hand to the browser. Called only after the owner approved."""
        vault = self._vault()
        async with self.b.sm() as db, db.begin():
            ctx = await self.b._task_context(db, task_id, lease_token)
            row = await self._match(db, ctx.owner_id, url)
            if row is None:
                raise ConnectorError("not_found", "there is no saved sign-in for this website")
            state = vault.decrypt(row.dek_wrapped, row.secret_enc, row.id)
            row.last_used_at = self.b.clock.now()
            self._audit(db, ctx.owner_id, "web_signin.used", row.host, task_id=task_id)
            return {"host": row.host, "label": row.label, "state": state}
