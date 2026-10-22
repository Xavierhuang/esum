"""v04 bring your own model key

Revision ID: 9c2e4b7a1f30
Revises: 6e8b3f1d2a47
Create Date: 2026-10-21 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '9c2e4b7a1f30'
down_revision = '6e8b3f1d2a47'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('model_keys',
    sa.Column('id', sa.String(length=26), nullable=False),
    sa.Column('owner_id', sa.String(length=26), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('base_url', sa.String(length=500), nullable=True),
    sa.Column('model', sa.String(length=200), nullable=False),
    sa.Column('key_hint', sa.String(length=16), nullable=False),
    sa.Column('dek_wrapped', sa.LargeBinary(), nullable=False),
    sa.Column('secret_enc', sa.LargeBinary(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id'),
    schema='broker'
    )


def downgrade() -> None:
    op.drop_table('model_keys', schema='broker')
