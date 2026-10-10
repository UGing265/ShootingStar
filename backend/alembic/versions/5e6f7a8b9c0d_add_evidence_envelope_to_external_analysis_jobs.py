"""add evidence_envelope_json to external_analysis_jobs

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-10-10 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5e6f7a8b9c0d'
down_revision: Union[str, Sequence[str], None] = '4d5e6f7a8b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'external_analysis_jobs',
        sa.Column('evidence_envelope_json', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('external_analysis_jobs', 'evidence_envelope_json')
