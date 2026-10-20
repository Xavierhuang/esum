"""v03 saved website sign-ins

Revision ID: 6e8b3f1d2a47
Revises: d41f7a2c9e18
Create Date: 2026-10-20 09:12:03.418265
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '6e8b3f1d2a47'
down_revision = 'd41f7a2c9e18'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('web_signins',
    sa.Column('id', sa.String(length=26), nullable=False),
    sa.Column('owner_id', sa.String(length=26), nullable=False),
    sa.Column('host', sa.String(length=255), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('dek_wrapped', sa.LargeBinary(), nullable=False),
    sa.Column('secret_enc', sa.LargeBinary(), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', 'host'),
    schema='broker'
    )
    op.create_index(op.f('ix_broker_web_signins_owner_id'), 'web_signins', ['owner_id'], unique=False, schema='broker')


def downgrade() -> None:
    op.drop_index(op.f('ix_broker_web_signins_owner_id'), table_name='web_signins', schema='broker')
    op.drop_table('web_signins', schema='broker')
