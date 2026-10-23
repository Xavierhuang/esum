from __future__ import annotations

import hmac
import re
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opa.core.canonical import sha256_hex
from opa.core.clock import Clock
from opa.core.errors import Conflict, Forbidden, Invalid, Throttled, Unauthorized
from opa.core.settings import Settings
from opa.db.models import AuditLog, LoginAttempt, Owner, Session

SESSION_COOKIE = "opa_session"
CSRF_HEADER = "x-csrf-token"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


async def _throttle(db: AsyncSession, key: str, settings: Settings, clock: Clock) -> None:
    window_start = clock.now() - timedelta(minutes=settings.login_window_minutes)
    await db.execute(delete(LoginAttempt).where(LoginAttempt.at < window_start))
    count = await db.scalar(
        select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == key, LoginAttempt.at >= window_start)
    )
    if (count or 0) >= settings.login_max_attempts:
        raise Throttled("too many login attempts; try again later")


async def login(
    db: AsyncSession, settings: Settings, clock: Clock, email: str, password: str, client_ip: str
) -> tuple[Session, str]:
    email = email.strip().lower()
    await _throttle(db, f"email:{email}", settings, clock)
    await _throttle(db, f"ip:{client_ip}", settings, clock)
    owner = await db.scalar(select(Owner).where(Owner.email == email))
    ok = owner is not None and verify_password(owner.password_hash, password)
    if not ok:
        # The caller records the failed attempt in its own committed transaction,
        # because raising here rolls back the request transaction.
        raise Unauthorized("invalid credentials")
    return await start_session(db, settings, clock, owner)


async def start_session(db: AsyncSession, settings: Settings, clock: Clock, owner: Owner) -> tuple[Session, str]:
    raw = secrets.token_urlsafe(32)
    sess = Session(
        owner_id=owner.id,
        token_hash=sha256_hex(raw),
        csrf_secret=secrets.token_urlsafe(32),
        expires_at=clock.now() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(sess)
    await db.flush()
    return sess, raw


async def resolve_session(db: AsyncSession, clock: Clock, raw_token: str | None) -> Session | None:
    if not raw_token:
        return None
    sess = await db.scalar(select(Session).where(Session.token_hash == sha256_hex(raw_token)))
    if sess is None or sess.expires_at <= clock.now():
        return None
    return sess


def check_csrf(request: Request, sess: Session) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    supplied = request.headers.get(CSRF_HEADER, "")
    if not hmac.compare_digest(supplied, sess.csrf_secret):
        raise Unauthorized("missing or invalid CSRF token", code="csrf_failed", status=403)


async def record_failed_attempt(sessionmaker, clock: Clock, email: str, client_ip: str) -> None:
    async with sessionmaker() as db, db.begin():
        db.add(LoginAttempt(key=f"email:{email.strip().lower()}", at=clock.now()))
        db.add(LoginAttempt(key=f"ip:{client_ip}", at=clock.now()))


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 12


def check_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise Invalid(f"use a password of at least {MIN_PASSWORD} characters")
    if len(password) > 1024:
        raise Invalid("that password is too long")


async def confirm_password(sessionmaker, db: AsyncSession, settings: Settings, clock: Clock, owner: Owner, password: str, client_ip: str) -> None:
    """Re-checks the signed-in owner's password before a sensitive change. Wrong guesses count like failed logins."""
    await _throttle(db, f"email:{owner.email}", settings, clock)
    if not verify_password(owner.password_hash, password):
        await record_failed_attempt(sessionmaker, clock, owner.email, client_ip)
        raise Forbidden("that is not your current password", code="wrong_password")


async def signup(db: AsyncSession, settings: Settings, clock: Clock, email: str, password: str, time_zone: str | None) -> Owner:
    """Open sign-up: a new, separate owner. Every record is scoped to its owner, so accounts never see each other."""
    if not settings.signup_enabled:
        raise Forbidden("sign-up is turned off on this server", code="signup_disabled")
    email = email.strip().lower()
    if len(email) > 320 or not EMAIL_RE.match(email):
        raise Invalid("enter a valid email address")
    check_new_password(password)
    zone = "UTC"
    if time_zone:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(time_zone)
            zone = time_zone
        except (ZoneInfoNotFoundError, ValueError):
            pass
    if await db.scalar(select(Owner.id).where(Owner.email == email)):
        raise Conflict("an account with this email already exists: sign in instead", code="email_taken")
    if (await db.scalar(select(func.count()).select_from(Owner)) or 0) >= settings.signup_max_owners:
        raise Forbidden("this server is not taking new accounts right now", code="signup_full")
    owner = Owner(email=email, password_hash=hash_password(password), time_zone=zone)
    db.add(owner)
    await db.flush()
    db.add(AuditLog(owner_id=owner.id, actor="owner", type="owner.signed_up", subject_id=owner.id, sanitized={}))
    return owner


async def throttle_signup(sessionmaker, settings: Settings, clock: Clock, client_ip: str) -> None:
    """At most a few sign-up attempts per address per hour, counted whether or not they succeed."""
    key = f"signup:{client_ip}"
    async with sessionmaker() as db, db.begin():
        since = clock.now() - timedelta(hours=1)
        count = await db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == key, LoginAttempt.at >= since))
        if (count or 0) >= settings.signup_per_ip_per_hour:
            raise Throttled("too many sign-up attempts from this network; try again later")
        db.add(LoginAttempt(key=key, at=clock.now()))
