"""Structured extraction: decisions, action items, topics; meeting extraction status.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _source_turn_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["meeting_id", "turn_idx"], ["turns.meeting_id", "turns.idx"], ondelete="CASCADE"
    )


def upgrade() -> None:
    op.add_column("meetings", sa.Column("extraction_status", sa.String(), nullable=False, server_default="pending"))
    op.add_column("meetings", sa.Column("extraction_error", sa.Text(), nullable=True))

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("turn_idx", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        _source_turn_fk(),
    )
    op.create_table(
        "action_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("turn_idx", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("due", sa.String(), nullable=True),
        _source_turn_fk(),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("meeting_id", sa.String(), nullable=False),
        sa.Column("turn_idx", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        _source_turn_fk(),
    )
    for table in ("decisions", "action_items", "topics"):
        op.create_index(f"ix_{table}_meeting_id", table, ["meeting_id"])


def downgrade() -> None:
    op.drop_table("topics")
    op.drop_table("action_items")
    op.drop_table("decisions")
    op.drop_column("meetings", "extraction_error")
    op.drop_column("meetings", "extraction_status")
