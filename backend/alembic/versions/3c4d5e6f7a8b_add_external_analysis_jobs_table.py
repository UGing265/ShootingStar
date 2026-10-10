"""add external_analysis_jobs table

Revision ID: 3c4d5e6f7a8b
Revises: 2b3c4d5e6f7a
Create Date: 2026-10-10 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '3c4d5e6f7a8b'
down_revision: Union[str, Sequence[str], None] = '2b3c4d5e6f7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'external_analysis_jobs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('snapshot_id', sa.String(length=64), nullable=False),
        sa.Column('snapshot_hash', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('timeframe', sa.String(length=16), nullable=False),
        sa.Column('prediction_time_t_ms', sa.BigInteger(), nullable=False),
        sa.Column('purchase_price_p', sa.Float(), nullable=False),
        sa.Column('horizon_minutes', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False),
        sa.Column('context_variant', sa.String(length=16), nullable=False),
        sa.Column('prompt_version', sa.String(length=32), nullable=False),
        sa.Column('model_id', sa.String(length=64), nullable=False),
        sa.Column('key_index', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('direction', sa.String(length=16), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('evidence_times_json', sa.Text(), nullable=True),
        sa.Column('lesson_ids_json', sa.Text(), nullable=True),
        sa.Column('raw_output_json', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=True),
        sa.Column('user_vote', sa.String(length=16), nullable=True),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('outcome', sa.String(length=32), nullable=True),
        sa.Column('is_revealed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('outcome_evaluated_at_ms', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_external_analysis_jobs_snapshot_id', 'external_analysis_jobs', ['snapshot_id'])
    op.create_index('ix_external_analysis_jobs_prediction_time_t_ms', 'external_analysis_jobs', ['prediction_time_t_ms'])
    op.create_index('ix_external_analysis_jobs_status', 'external_analysis_jobs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_external_analysis_jobs_status', table_name='external_analysis_jobs')
    op.drop_index('ix_external_analysis_jobs_prediction_time_t_ms', table_name='external_analysis_jobs')
    op.drop_index('ix_external_analysis_jobs_snapshot_id', table_name='external_analysis_jobs')
    op.drop_table('external_analysis_jobs')
