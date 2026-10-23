from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import delete

from opa import __version__
from opa.api.auth import (SESSION_COOKIE, check_new_password, confirm_password, hash_password, login, record_failed_attempt, signup,
                          start_session, throttle_signup)
from opa.core.errors import Unauthorized
from opa.api.deps import ClockDep, DbDep, OwnerDep, SessionDep, SettingsDep
from opa.api.schemas import AuthOptionsOut, DeleteAccountIn, LoginIn, MeOut, PasswordChangeIn, PreferencesIn, SignupIn
from opa.core.errors import Invalid
from opa.data.erase import erase_owner
from opa.db.models import AuditLog, Owner, Session
from opa.worker.model import setup_problems

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", status_code=204)
async def post_login(body: LoginIn, request: Request, response: Response, db: DbDep, settings: SettingsDep, clock: ClockDep) -> Response:
    ip = request.client.host if request.client else "unknown"
    try:
        sess, raw = await login(db, settings, clock, body.email, body.password, ip)
    except Unauthorized:
        await record_failed_attempt(request.app.state.sessionmaker, clock, body.email, ip)
        raise
    response.set_cookie(
        SESSION_COOKIE, raw, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/",
        max_age=settings.session_ttl_hours * 3600,
    )
    response.status_code = 204
    return response


def _set_session_cookie(response: Response, settings, raw: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, raw, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


@router.get("/auth/options", response_model=AuthOptionsOut)
async def auth_options(settings: SettingsDep) -> AuthOptionsOut:
    """What the sign-in page may offer before anyone is signed in."""
    return AuthOptionsOut(signup=settings.signup_enabled)


@router.post("/auth/signup", status_code=204)
async def post_signup(body: SignupIn, request: Request, response: Response, db: DbDep, settings: SettingsDep, clock: ClockDep) -> Response:
    """Creates a new private account and signs it in. Off unless OPA_SIGNUP_ENABLED is set."""
    if settings.signup_enabled:
        await throttle_signup(request.app.state.sessionmaker, settings, clock, request.client.host if request.client else "unknown")
    owner = await signup(db, settings, clock, body.email, body.password, body.time_zone)
    _sess, raw = await start_session(db, settings, clock, owner)
    _set_session_cookie(response, settings, raw)
    response.status_code = 204
    return response


@router.post("/auth/logout", status_code=204)
async def post_logout(response: Response, db: DbDep, sess: SessionDep) -> Response:
    await db.execute(delete(Session).where(Session.id == sess.id))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


async def model_key_state(request: Request, owner_id: str, settings) -> tuple[dict | None, bool]:
    """The owner's saved model key (as a hint) and whether the app must ask for one before chatting."""
    wants_key = settings.mode == "live" and settings.model_provider == "anthropic" and not settings.anthropic_api_key
    broker = request.app.state.broker
    if broker is None:
        return None, False
    try:
        key = await broker.get_model_key(owner_id)
    except Exception:  # noqa: BLE001 - never block the app on this; the worker reports a missing key itself
        return None, False
    return key, wants_key and key is None


@router.get("/me", response_model=MeOut)
async def get_me(request: Request, owner: OwnerDep, sess: SessionDep, settings: SettingsDep) -> MeOut:
    key, needs = await model_key_state(request, owner.id, settings)
    return MeOut(
        id=owner.id, email=owner.email, time_zone=owner.time_zone, assistant_name=owner.assistant_name,
        response_style=owner.response_style, mode=settings.mode, setup_required=setup_problems(settings),
        csrf_token=sess.csrf_secret, approval_mode=owner.preferences.get("approval_mode", "ask_writes"), version=__version__,
        default_model=settings.model_id, model_key=key, needs_model_key=needs,
    )


@router.patch("/me", response_model=MeOut)
async def patch_me(body: PreferencesIn, request: Request, owner: OwnerDep, sess: SessionDep, settings: SettingsDep) -> MeOut:
    if body.time_zone is not None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(body.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise Invalid("time_zone must be an IANA zone such as America/Los_Angeles") from None
        owner.time_zone = body.time_zone
    if body.approval_mode is not None:
        owner.preferences = {**owner.preferences, "approval_mode": body.approval_mode}
    if body.assistant_name is not None:
        owner.assistant_name = body.assistant_name
    if body.response_style is not None:
        owner.response_style = body.response_style
    return await get_me(request, owner, sess, settings)


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/me/password", status_code=204)
async def change_password(body: PasswordChangeIn, request: Request, response: Response, db: DbDep, owner: OwnerDep, sess: SessionDep,
                          settings: SettingsDep, clock: ClockDep) -> Response:
    """Changes the password after re-checking the current one, and signs out every other session."""
    await confirm_password(request.app.state.sessionmaker, db, settings, clock, owner, body.current_password, _ip(request))
    check_new_password(body.new_password)
    owner.password_hash = hash_password(body.new_password)
    await db.execute(delete(Session).where(Session.owner_id == owner.id, Session.id != sess.id))
    db.add(AuditLog(owner_id=owner.id, actor="owner", type="owner.password_changed", subject_id=owner.id, sanitized={}))
    response.status_code = 204
    return response


@router.post("/me/delete-account", status_code=204)
async def delete_account(body: DeleteAccountIn, request: Request, response: Response, db: DbDep, owner: OwnerDep,
                         settings: SettingsDep, clock: ClockDep) -> Response:
    """Deletes everything the owner has (as delete-all does), then the account and its sign-ins. Needs the email and password."""
    if body.confirm.strip().lower() != owner.email.lower():
        raise Invalid("type your account email address exactly to confirm", code="confirmation_required")
    await confirm_password(request.app.state.sessionmaker, db, settings, clock, owner, body.password, _ip(request))
    owner_id = owner.id
    await erase_owner(request.app.state.sessionmaker, settings, clock, owner_id, request.app.state.broker, request.app.state.browser)
    db.expunge(owner)
    await db.execute(delete(AuditLog).where(AuditLog.owner_id == owner_id))
    await db.execute(delete(Owner).where(Owner.id == owner_id))  # sessions and any remaining rows cascade
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response
