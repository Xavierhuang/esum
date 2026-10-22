"""Bring your own model key. The owner's API key for Anthropic, ZenMux or any Anthropic-compatible gateway,
sealed in the vault. The api only ever sees a hint ("…1234"); the worker gets the key for a running task.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import delete, select

from opa.core.ids import new_id
from opa.db.models import AuditLog, BrokerModelKey
from opa.sdk.contract import ConnectorError

PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {"label": "Anthropic", "base_url": None},
    "zenmux": {"label": "ZenMux", "base_url": "https://zenmux.ai/api/anthropic"},
    "custom": {"label": "Custom", "base_url": None},
}
USED_AT_RESOLUTION = timedelta(hours=1)


def clean_base_url(raw: str) -> str:
    url = raw.strip().rstrip("/")
    for suffix in ("/v1/messages", "/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ConnectorError("invalid_input", "the address must start with https://")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ConnectorError("invalid_input", "the address must not contain a user name, query or fragment")
    return url


async def _check_public_host(url: str) -> None:
    """The broker sits on the internal network, so a custom address must not point back into it."""
    host = urlsplit(url).hostname or ""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise ConnectorError("invalid_input", f"could not find {host}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ConnectorError("invalid_input", f"{host} is not a public address")


def _summary(r: BrokerModelKey) -> dict[str, Any]:
    return {"provider": r.provider, "provider_label": PROVIDERS[r.provider]["label"], "base_url": r.base_url, "model": r.model,
            "key_hint": r.key_hint, "updated_at": r.updated_at.isoformat(), "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None}


class ModelKeys:
    def __init__(self, broker: Any) -> None:
        self.b = broker

    def _vault(self):
        if self.b.vault is None:
            raise ConnectorError("auth_required", "the broker has no key-encryption key (OPA_BROKER_KEK)")
        return self.b.vault

    async def _verify(self, base_url: str | None, model: str, api_key: str) -> None:
        """One tiny request, so a wrong key or model fails here instead of in the owner's first chat."""
        import anthropic
        from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

        http_client = DefaultAsyncHttpxClient(transport=self.b.model_transport) if self.b.model_transport else None
        client = AsyncAnthropic(api_key=api_key, base_url=base_url, http_client=http_client, max_retries=0, timeout=30.0)
        where = urlsplit(base_url).hostname if base_url else "Anthropic"
        try:
            await client.messages.create(model=model, max_tokens=1, messages=[{"role": "user", "content": "Reply with OK."}])
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            raise ConnectorError("invalid_input", f"{where} rejected this key") from None
        except anthropic.NotFoundError:
            raise ConnectorError("invalid_input", f"{where} does not offer the model “{model}”") from None
        except anthropic.RateLimitError:
            return  # the key was accepted; the account is only busy right now
        except anthropic.BadRequestError as e:
            raise ConnectorError("invalid_input", f"{where} refused the test request: {str(e.message)[:200]}") from None
        except anthropic.APIStatusError as e:
            raise ConnectorError("provider_unavailable", f"{where} answered with an error ({e.status_code})") from None
        except anthropic.APIConnectionError:
            raise ConnectorError("provider_unavailable", f"could not reach {where}") from None
        finally:
            await client.close()

    async def save(self, owner_id: str, provider: str, base_url: str | None, model: str, api_key: str) -> dict[str, Any]:
        vault = self._vault()
        if provider not in PROVIDERS:
            raise ConnectorError("invalid_input", "choose Anthropic, ZenMux or Custom")
        api_key, model = api_key.strip(), model.strip()
        if not api_key or len(api_key) > 500 or any(c.isspace() for c in api_key):
            raise ConnectorError("invalid_input", "paste the whole API key, with no spaces")
        if not model or len(model) > 200 or any(c.isspace() for c in model):
            raise ConnectorError("invalid_input", "enter the model name, for example claude-opus-5-5")
        if provider == "custom":
            if not base_url:
                raise ConnectorError("invalid_input", "a custom provider needs its https:// address")
            base_url = clean_base_url(base_url)
            await _check_public_host(base_url)
        else:
            base_url = PROVIDERS[provider]["base_url"]
        await self._verify(base_url, model, api_key)
        async with self.b.sm() as db, db.begin():
            row = await db.scalar(select(BrokerModelKey).where(BrokerModelKey.owner_id == owner_id).with_for_update())
            if row is None:
                row = BrokerModelKey(id=new_id(), owner_id=owner_id, provider=provider, model=model, key_hint="", dek_wrapped=b"", secret_enc=b"")
                db.add(row)
            row.provider, row.base_url, row.model = provider, base_url, model
            row.key_hint = f"…{api_key[-4:]}"
            row.dek_wrapped, row.secret_enc = vault.encrypt({"api_key": api_key}, row.id)
            await db.flush()
            await db.refresh(row)
            db.add(AuditLog(owner_id=owner_id, actor="broker", type="model_key.saved", subject_id=provider,
                            sanitized={"provider": provider, "model": model, "base_url": base_url}))
            return _summary(row)

    async def get(self, owner_id: str) -> dict[str, Any] | None:
        async with self.b.sm() as db:
            row = await db.scalar(select(BrokerModelKey).where(BrokerModelKey.owner_id == owner_id))
            return _summary(row) if row else None

    async def delete(self, owner_id: str) -> dict[str, Any]:
        async with self.b.sm() as db, db.begin():
            n = (await db.execute(delete(BrokerModelKey).where(BrokerModelKey.owner_id == owner_id))).rowcount
            if n:
                db.add(AuditLog(owner_id=owner_id, actor="broker", type="model_key.deleted", subject_id="model_key", sanitized={}))
        return {"deleted": bool(n)}

    async def for_task(self, task_id: str, lease_token: str) -> dict[str, Any] | None:
        """The key for the owner of a running task, for the worker's next model call. None when the owner has none."""
        vault = self._vault()
        async with self.b.sm() as db, db.begin():
            ctx = await self.b._task_context(db, task_id, lease_token)
            row = await db.scalar(select(BrokerModelKey).where(BrokerModelKey.owner_id == ctx.owner_id))
            if row is None:
                return None
            secret = vault.decrypt(row.dek_wrapped, row.secret_enc, row.id)
            now = self.b.clock.now()
            if row.last_used_at is None or now - row.last_used_at > USED_AT_RESOLUTION:
                row.last_used_at = now
            return {"provider": row.provider, "base_url": row.base_url, "model": row.model, "api_key": secret["api_key"],
                    "version": row.updated_at.isoformat()}
