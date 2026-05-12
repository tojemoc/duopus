"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rundown",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("show_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rundown_title", "rundown", ["title"])
    op.create_index("ix_rundown_status", "rundown", ["status"])

    op.create_table(
        "story",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rundown_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("planned_duration", sa.Integer(), nullable=False),
        sa.Column("actual_duration", sa.Integer(), nullable=True),
        sa.Column("vmix_input", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["rundown_id"], ["rundown.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_rundown_id", "story", ["rundown_id"])
    op.create_index("ix_story_position", "story", ["position"])
    op.create_index("ix_story_status", "story", ["status"])

    op.create_table(
        "script",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id"),
    )
    op.create_index("ix_script_story_id", "script", ["story_id"])


def downgrade() -> None:
    op.drop_index("ix_script_story_id", table_name="script")
    op.drop_table("script")
    op.drop_index("ix_story_status", table_name="story")
    op.drop_index("ix_story_position", table_name="story")
    op.drop_index("ix_story_rundown_id", table_name="story")
    op.drop_table("story")
    op.drop_index("ix_rundown_status", table_name="rundown")
    op.drop_index("ix_rundown_title", table_name="rundown")
    op.drop_table("rundown")
