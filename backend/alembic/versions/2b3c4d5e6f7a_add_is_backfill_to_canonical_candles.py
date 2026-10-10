"""add is_backfill to canonical_candles

Revision ID: 2b3c4d5e6f7a
Revises: 1099604583d5
Create Date: 2026-10-09 05:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, Sequence[str], None] = '1099604583d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'canonical_candles',
        sa.Column('is_backfill', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('canonical_candles', 'is_backfill')
