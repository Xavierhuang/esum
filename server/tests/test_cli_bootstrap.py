"""`opa bootstrap-owner`: creates only the first owner, and --reset-password changes only the named account."""
import pytest
from sqlalchemy import select

from opa.api.auth import verify_password
from opa.cli import bootstrap_owner_row
from opa.db.models import Owner


async def test_reset_changes_only_the_named_account(sessionmaker, owner, other_owner):
    async with sessionmaker() as db, db.begin():
        assert await bootstrap_owner_row(db, other_owner.email.upper(), "a new long password", reset_password=True) == "password reset"
    async with sessionmaker() as db:
        rows = {o.email: o for o in await db.scalars(select(Owner))}
    assert verify_password(rows[other_owner.email].password_hash, "a new long password")
    assert not verify_password(rows[owner.email].password_hash, "a new long password")


async def test_reset_of_an_unknown_email_and_a_second_owner_are_refused(sessionmaker, owner):
    async with sessionmaker() as db, db.begin():
        with pytest.raises(ValueError, match="no account"):
            await bootstrap_owner_row(db, "nobody@example.com", "a new long password", reset_password=True)
        with pytest.raises(ValueError, match="already exists"):
            await bootstrap_owner_row(db, "second@example.com", "a new long password", reset_password=False)


async def test_creates_the_first_owner(sessionmaker):
    async with sessionmaker() as db, db.begin():
        assert await bootstrap_owner_row(db, " First@Example.com ", "a new long password", reset_password=False) == "owner created"
    async with sessionmaker() as db:
        assert await db.scalar(select(Owner.email)) == "first@example.com"
