"""Internal broker HTTP API. Reachable only on the internal network with the shared bearer token.
Never exposed to the browser, and no route accepts a URL or arbitrary HTTP request."""
from __future__ import annotations

import asyncio
import hmac
import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from opa.broker.service import Broker
from opa.sdk.contract import ConnectorError, ToolRequest, ToolResult

log = logging.getLogger("opa.broker")


class Lease(BaseModel):
    task_id: str
    lease_token: str


class ReadIn(BaseModel):
    request: ToolRequest
    lease_token: str


class PrepareIn(Lease):
    connection_id: str
    tool_name: str
    arguments: dict[str, Any]


class DispatchIn(Lease):
    action_id: str


class ExchangeIn(BaseModel):
    owner_id: str  # supplied by the authenticated API after it validated the OAuth state
    candidate_connection_id: str
    target_connection_id: str | None = None
    code: str
    code_verifier: str
    redirect_uri: str


class OwnedConnection(BaseModel):
    connection_id: str
    owner_id: str


class CalendarSyncIn(BaseModel):
    owner_id: str  # supplied by the scheduler from the automation row, never by the model
    connection_id: str
    calendar_id: str
    sync_token: str | None = None
    time_min: str


class ReconcileIn(BaseModel):
    action_id: str
    owner_id: str  # supplied by the authenticated API, never by the model


class SaveSignInIn(BaseModel):
    owner_id: str  # supplied by the authenticated API, which checked that the owner is driving that browser
    host: str
    label: str
    state: dict[str, Any]


class OwnedSignIn(BaseModel):
    owner_id: str
    signin_id: str


class OwnerOnly(BaseModel):
    owner_id: str


class SignInForTask(Lease):
    url: str


class SaveModelKeyIn(BaseModel):
    owner_id: str
    provider: str
    base_url: str | None = None
    model: str
    api_key: str


def create_broker_app(broker: Broker, *, sweep_interval: float | None = None) -> FastAPI:
    token = broker.settings.internal_token
    if not token:
        raise RuntimeError("OPA_INTERNAL_TOKEN must be set for the broker")
    app = FastAPI(title="OPA broker (internal)", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.broker = broker

    def auth(request: Request) -> None:
        supplied = request.headers.get("authorization", "")
        if not hmac.compare_digest(supplied, f"Bearer {token}"):
            raise HTTPException(status_code=401, detail="unauthorized")

    guarded = [Depends(auth)]

    @app.exception_handler(ConnectorError)
    async def connector_error(_req: Request, exc: ConnectorError):
        from fastapi.responses import JSONResponse

        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=400)

    @app.get("/internal/health")
    async def health():
        return {"ok": await broker.ping_db()}

    @app.post("/internal/tools", dependencies=guarded)
    async def tools(body: Lease) -> list[dict[str, Any]]:
        return await broker.list_tools(body.task_id, body.lease_token)

    @app.post("/internal/read", dependencies=guarded, response_model=ToolResult)
    async def read(body: ReadIn) -> ToolResult:
        return await broker.read(body.request, body.lease_token)

    @app.post("/internal/prepare", dependencies=guarded)
    async def prepare(body: PrepareIn) -> dict[str, Any]:
        return await broker.prepare(body.task_id, body.lease_token, body.connection_id, body.tool_name, body.arguments)

    @app.post("/internal/dispatch", dependencies=guarded, response_model=ToolResult)
    async def dispatch(body: DispatchIn) -> ToolResult:
        return await broker.dispatch(body.action_id, body.task_id, body.lease_token)

    @app.post("/internal/reconcile", dependencies=guarded)
    async def reconcile(body: ReconcileIn) -> dict[str, Any]:
        return await broker.reconcile(body.action_id, body.owner_id)

    @app.post("/internal/oauth/{provider}/exchange", dependencies=guarded)
    async def oauth_exchange(provider: str, body: ExchangeIn) -> dict[str, Any]:
        return await broker.oauth_exchange(provider, body.owner_id, body.candidate_connection_id, body.target_connection_id, body.code,
                                           body.code_verifier, body.redirect_uri)

    @app.post("/internal/connections/revoke", dependencies=guarded)
    async def revoke(body: OwnedConnection) -> dict[str, Any]:
        return await broker.revoke(body.connection_id, body.owner_id)

    @app.post("/internal/connections/purge", dependencies=guarded)
    async def purge(body: OwnedConnection) -> dict[str, Any]:
        return await broker.purge(body.connection_id, body.owner_id)

    @app.post("/internal/connections/health", dependencies=guarded)
    async def health_check(body: OwnedConnection) -> dict[str, Any]:
        return await broker.health(body.connection_id, body.owner_id)

    @app.post("/internal/calendar/sync", dependencies=guarded)
    async def calendar_sync(body: CalendarSyncIn) -> dict[str, Any]:
        return await broker.calendar_sync(body.owner_id, body.connection_id, body.calendar_id, body.sync_token, body.time_min)

    @app.post("/internal/web-signins/save", dependencies=guarded)
    async def signin_save(body: SaveSignInIn) -> dict[str, Any]:
        return await broker.web_signins.save(body.owner_id, body.host, body.label, body.state)

    @app.post("/internal/web-signins/list", dependencies=guarded)
    async def signin_list(body: OwnerOnly) -> list[dict[str, Any]]:
        return await broker.web_signins.list_for(body.owner_id)

    @app.post("/internal/web-signins/delete", dependencies=guarded)
    async def signin_delete(body: OwnedSignIn) -> dict[str, Any]:
        return await broker.web_signins.delete(body.owner_id, body.signin_id)

    @app.post("/internal/web-signins/purge", dependencies=guarded)
    async def signin_purge(body: OwnerOnly) -> dict[str, Any]:
        return await broker.web_signins.purge(body.owner_id)

    @app.post("/internal/web-signins/lookup", dependencies=guarded)
    async def signin_lookup(body: SignInForTask) -> dict[str, Any] | None:
        return await broker.web_signins.lookup(body.task_id, body.lease_token, body.url)

    @app.post("/internal/web-signins/open", dependencies=guarded)
    async def signin_open(body: SignInForTask) -> dict[str, Any]:
        return await broker.web_signins.open(body.task_id, body.lease_token, body.url)

    @app.post("/internal/model-key/save", dependencies=guarded)
    async def model_key_save(body: SaveModelKeyIn) -> dict[str, Any]:
        return await broker.model_keys.save(body.owner_id, body.provider, body.base_url, body.model, body.api_key)

    @app.post("/internal/model-key/get", dependencies=guarded)
    async def model_key_get(body: OwnerOnly) -> dict[str, Any] | None:
        return await broker.model_keys.get(body.owner_id)

    @app.post("/internal/model-key/delete", dependencies=guarded)
    async def model_key_delete(body: OwnerOnly) -> dict[str, Any]:
        return await broker.model_keys.delete(body.owner_id)

    @app.post("/internal/model-key/for-task", dependencies=guarded)
    async def model_key_for_task(body: Lease) -> dict[str, Any] | None:
        return await broker.model_keys.for_task(body.task_id, body.lease_token)

    if sweep_interval:
        @app.on_event("startup")
        async def start_sweep() -> None:
            async def loop() -> None:
                while True:
                    try:
                        await broker.sweep_stale_dispatches()
                    except Exception:
                        log.exception("sweep failed")
                    await asyncio.sleep(sweep_interval)
            app.state.sweeper = asyncio.create_task(loop())

    return app
