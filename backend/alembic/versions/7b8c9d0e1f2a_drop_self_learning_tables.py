"""drop self-learning tables and report lesson references

Revision ID: 7b8c9d0e1f2a
Revises: 6a7b8c9d0e1f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7b8c9d0e1f2a'
down_revision: Union[str, Sequence[str], None] = '6a7b8c9d0e1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('lesson_review_events')
    op.drop_table('lesson_revisions')
    op.drop_table('lessons')
    op.drop_table('pattern_hits')
    op.drop_table('pattern_rules')
    op.drop_column('external_analysis_jobs', 'lesson_ids_json')


def downgrade() -> None:
    op.add_column('external_analysis_jobs', sa.Column('lesson_ids_json', sa.Text(), nullable=True))

    op.create_table(
        'pattern_rules',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('definition_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'pattern_hits',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('rule_id', sa.String(length=64), nullable=False),
        sa.Column('detected_time_ms', sa.BigInteger(), nullable=False),
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('timeframe', sa.String(length=16), nullable=False),
        sa.Column('outcome_return_30m', sa.Float(), nullable=True),
        sa.Column('outcome_label', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['pattern_rules.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pattern_hits_detected_time_ms'), 'pattern_hits', ['detected_time_ms'], unique=False)

    op.create_table(
        'lessons',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('current_revision_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lessons_status', 'lessons', ['status'])
    op.create_table(
        'lesson_revisions',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('lesson_id', sa.String(length=64), sa.ForeignKey('lessons.id'), nullable=False),
        sa.Column('revision_number', sa.Integer(), nullable=False),
        sa.Column('short_definition', sa.Text(), nullable=False),
        sa.Column('caveats', sa.Text(), nullable=False),
        sa.Column('source_snippet', sa.Text(), nullable=True),
        sa.Column('reviewer', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lesson_revisions_lesson_id', 'lesson_revisions', ['lesson_id'])
    op.create_table(
        'lesson_review_events',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('lesson_id', sa.String(length=64), nullable=False),
        sa.Column('revision_id', sa.String(length=64), nullable=True),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('reviewer', sa.String(length=128), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lesson_review_events_lesson_id', 'lesson_review_events', ['lesson_id'])
