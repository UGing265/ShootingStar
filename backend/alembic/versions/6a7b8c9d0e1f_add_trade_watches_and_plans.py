"""add trade_watches, candidate_plans, and trade_observations tables

Revision ID: 6a7b8c9d0e1f
Revises: 5e6f7a8b9c0d
Create Date: 2026-10-10 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '6a7b8c9d0e1f'
down_revision: Union[str, Sequence[str], None] = '5e6f7a8b9c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trade_watches',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('operator_id', sa.String(length=64), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='WATCHING'),
        sa.Column('position_state', sa.String(length=32), nullable=False, server_default='FLAT'),
        sa.Column('strategy_version', sa.String(length=64), nullable=False),
        sa.Column('risk_config_json', sa.Text(), nullable=False),
        sa.Column('symbol_filters_json', sa.Text(), nullable=False),
        sa.Column('active_candidate_id', sa.String(length=64), nullable=True),
        sa.Column('execution_mode', sa.String(length=32), nullable=True),
        sa.Column('opened_at_ms', sa.BigInteger(), nullable=True),
        sa.Column('deadline_ms', sa.BigInteger(), nullable=True),
        sa.Column('closed_at_ms', sa.BigInteger(), nullable=True),
        sa.Column('lease_owner', sa.String(length=128), nullable=True),
        sa.Column('lease_expires_at_ms', sa.BigInteger(), nullable=True),
        sa.Column('lease_token', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_trade_watches_operator_id', 'trade_watches', ['operator_id'])
    op.create_index('ix_trade_watches_symbol', 'trade_watches', ['symbol'])

    op.create_table(
        'candidate_plans',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('watch_id', sa.String(length=64), sa.ForeignKey('trade_watches.id'), nullable=True),
        sa.Column('strategy_version', sa.String(length=64), nullable=False),
        sa.Column('rule_config_hash', sa.String(length=64), nullable=False),
        sa.Column('decision_time_ms', sa.BigInteger(), nullable=False),
        sa.Column('available_cutoff_ms', sa.BigInteger(), nullable=False),
        sa.Column('entry_zone_json', sa.Text(), nullable=False),
        sa.Column('confirmation_json', sa.Text(), nullable=False),
        sa.Column('invalidation_json', sa.Text(), nullable=False),
        sa.Column('stop_price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('target_price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('wait_expires_at_ms', sa.BigInteger(), nullable=False),
        sa.Column('horizon_ms', sa.BigInteger(), nullable=False, server_default='1800000'),
        sa.Column('probability_json', sa.Text(), nullable=True),
        sa.Column('reasons_json', sa.Text(), nullable=True),
        sa.Column('candidate_state', sa.String(length=32), nullable=False, server_default='WAITING'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_candidate_plans_watch_id', 'candidate_plans', ['watch_id'])

    op.create_table(
        'trade_observations',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('candidate_id', sa.String(length=64), nullable=False),
        sa.Column('watch_id', sa.String(length=64), nullable=True),
        sa.Column('observation_type', sa.String(length=16), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False),
        sa.Column('price', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('remaining_quantity', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('fees_paid', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('actual_time_ms', sa.BigInteger(), nullable=False),
        sa.Column('receipt_time_ms', sa.BigInteger(), nullable=False),
        sa.Column('is_off_plan', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_risk_breach', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('reconciled_sl_breach', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('exit_reason', sa.String(length=32), nullable=True),
        sa.Column('realized_pnl_usdt', sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('idempotency_key', name='uq_trade_obs_idempotency_key'),
    )
    op.create_index('ix_trade_observations_idempotency_key', 'trade_observations', ['idempotency_key'])
    op.create_index('ix_trade_observations_candidate_id', 'trade_observations', ['candidate_id'])
    op.create_index('ix_trade_observations_watch_id', 'trade_observations', ['watch_id'])


def downgrade() -> None:
    op.drop_table('trade_observations')
    op.drop_table('candidate_plans')
    op.drop_table('trade_watches')
