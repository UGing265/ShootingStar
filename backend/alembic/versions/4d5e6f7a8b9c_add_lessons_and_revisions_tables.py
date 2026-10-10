"""add lessons and revisions tables

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-10-10 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '4d5e6f7a8b9c'
down_revision: Union[str, Sequence[str], None] = '3c4d5e6f7a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. lessons table
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

    # 2. lesson_revisions table
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

    # 3. lesson_review_events table
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


def downgrade() -> None:
    op.drop_index('ix_lesson_review_events_lesson_id', table_name='lesson_review_events')
    op.drop_table('lesson_review_events')

    op.drop_index('ix_lesson_revisions_lesson_id', table_name='lesson_revisions')
    op.drop_table('lesson_revisions')

    op.drop_index('ix_lessons_status', table_name='lessons')
    op.drop_table('lessons')
