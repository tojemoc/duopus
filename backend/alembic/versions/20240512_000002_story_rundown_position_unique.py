"""unique (rundown_id, position) on story

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_story_rundown_position",
        "story",
        ["rundown_id", "position"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_story_rundown_position", "story", type_="unique")
