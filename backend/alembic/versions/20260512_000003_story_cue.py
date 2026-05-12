"""story_cue table for sub-items and vMix automation per Next

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_cue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("vmix_function", sa.String(), nullable=True),
        sa.Column("vmix_input", sa.Integer(), nullable=True),
        sa.Column("vmix_params", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_id", "position", name="uq_story_cue_position"),
    )
    op.create_index("ix_story_cue_story_id", "story_cue", ["story_id"])
    op.create_index("ix_story_cue_position", "story_cue", ["position"])


def downgrade() -> None:
    op.drop_index("ix_story_cue_position", table_name="story_cue")
    op.drop_index("ix_story_cue_story_id", table_name="story_cue")
    op.drop_table("story_cue")
