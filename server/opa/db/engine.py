from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from opa.core.settings import Settings, get_settings


def engine_options(settings: Settings | None = None) -> dict:
    """Maps the `broker` schema onto OPA_BROKER_SCHEMA when a host does not allow creating it."""
    s = settings or get_settings()
    if s.broker_schema == "broker":
        return {}
    return {"execution_options": {"schema_translate_map": {"broker": s.broker_schema}}}


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True, **engine_options())


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


def reset_engine_cache() -> None:
    """Used by tests after changing OPA_DATABASE_URL."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    get_settings.cache_clear()
